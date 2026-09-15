"""Offline checks of actual notebook cells, never notebook/kernel/cloud execution."""

import ast
import hashlib
import importlib.util
import json
import re
import socket
from importlib.metadata import distribution, version
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import nbformat
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pytest
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier
from snowflake.snowpark import DataFrame, Session, functions as sf
from snowflake.snowpark.types import (
    DoubleType, LongType, StringType, StructField, StructType,
)


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK_PATH = ROOT / "notebooks/03_mlops.ipynb"
DAILY_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY"
LABEL_TABLE = "BCAST_PLATFORM_HANDSON.RAW.DEVICE_LABELS"
OUTPUT_TABLE = "BCAST_PLATFORM_HANDSON.ML.PREDICTIONS"


class Expression:
    """Minimal pandas evaluator for the expression subset used in cell 4.

    Not a SQL compiler or Snowflake semantics verification. Avoids SDK local
    aggregate-cast gaps and conditional numeric truncation in local mocks.
    """

    def __init__(self, evaluate):
        self.evaluate = evaluate
        self.name = None

    def cast(self, datatype):
        assert datatype == "double"
        return Expression(lambda frame: np.asarray(self.evaluate(frame), dtype=float))

    def alias(self, name):
        self.name = name
        return self

    def __eq__(self, other):
        return Expression(lambda frame: self.evaluate(frame) == other)

    def __gt__(self, other):
        return Expression(lambda frame: self.evaluate(frame) > other)

    def __truediv__(self, other):
        return Expression(lambda frame: self.evaluate(frame) / other.evaluate(frame))


class Conditional:
    def __init__(self, condition, value):
        self.condition, self.value = condition, value

    def otherwise(self, other):
        return Expression(lambda frame: pd.Series(
            np.where(self.condition.evaluate(frame), self.value.evaluate(frame), other.evaluate(frame)),
            index=frame.index,
        ))


def column(name):
    return Expression(lambda frame: frame[name])


def aggregate_sum(expression):
    expression = column(expression) if isinstance(expression, str) else expression
    return Expression(lambda frame: pd.Series(expression.evaluate(frame)).sum(min_count=1))


PANDAS_FUNCTIONS = SimpleNamespace(
    sum=aggregate_sum, col=column, when=Conditional,
    lit=lambda value: Expression(lambda frame: value),
)


class PandasTable:
    def __init__(self, frame):
        self.frame = frame.copy()

    def group_by(self, key):
        def aggregate(*expressions):
            rows = [
                {key: identifier, **{expression.name: float(expression.evaluate(group)) for expression in expressions}}
                for identifier, group in self.frame.groupby(key, dropna=False)
            ]
            return PandasTable(pd.DataFrame(rows))

        return SimpleNamespace(agg=aggregate)

    def with_column(self, name, expression):
        return PandasTable(self.frame.assign(**{name: expression.evaluate(self.frame)}))

    def select(self, *columns):
        return PandasTable(self.frame[list(columns)])

    def sort(self, column_name):
        return PandasTable(self.frame.sort_values(column_name))

    def limit(self, number):
        return PandasTable(self.frame.head(number))

    def to_pandas(self):
        return self.frame.reset_index(drop=True).copy()


def pandas_session(daily, labels):
    tables = {DAILY_TABLE: daily, LABEL_TABLE: labels}
    return SimpleNamespace(table=lambda name: PandasTable(tables[name]))


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError("Network access is forbidden in offline notebook tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    monkeypatch.setattr(socket, "getaddrinfo", blocked)


@pytest.fixture(scope="session")
def notebook():
    original = NOTEBOOK_PATH.read_bytes()
    document = nbformat.reads(original.decode(), as_version=4)
    yield document
    assert NOTEBOOK_PATH.read_bytes() == original, "Notebook changed during offline tests"


def execute_cell(notebook, index, namespace, enable_save=False):
    tree = ast.parse(notebook.cells[index].source)
    if enable_save:
        assignment = tree.body[0]
        assert isinstance(assignment, ast.Assign)
        assert assignment.targets[0].id == "SAVE_RESULTS"
        assert assignment.value.value is False
        assignment.value = ast.Constant(value=True)
        ast.fix_missing_locations(tree)
    exec(compile(tree, f"{NOTEBOOK_PATH}:cell[{index}]", "exec"), namespace)


def namespace_for(notebook):
    assignments = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in ast.parse(notebook.cells[2].source).body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in {"FEATURE_COLUMNS", "MODEL_NAME", "MODEL_VERSION"}
    }
    return dict(
        assignments, np=np, pd=pd, sklearn=sklearn, sf=sf,
        DecisionTreeClassifier=DecisionTreeClassifier, DummyClassifier=DummyClassifier,
        train_test_split=train_test_split, accuracy_score=accuracy_score,
        balanced_accuracy_score=balanced_accuracy_score, StructType=StructType,
        StructField=StructField, StringType=StringType, LongType=LongType,
    )


def test_initial_cell_sets_registry_execution_context(notebook, monkeypatch):
    session = MagicMock()
    session.get_current_role.return_value = 'BCAST_PLATFORM_ENGINEER_ROLE'
    monkeypatch.setattr('snowflake.snowpark.context.get_active_session', lambda: session)
    execute_cell(notebook, 2, {})
    session.use_warehouse.assert_called_once_with('BCAST_PLATFORM_COMMON_WH')
    session.use_database.assert_called_once_with('BCAST_PLATFORM_HANDSON')
    session.use_schema.assert_called_once_with('ML')


@pytest.fixture(scope="session")
def parquet_data(tmp_path_factory):
    directory = tmp_path_factory.mktemp("mlops_parquet")
    spec = importlib.util.spec_from_file_location("mlops_generator", ROOT / "scripts/generate_data.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    generator.generate(directory)
    files = sorted(directory.glob("*.parquet"))
    assert len(files) == 6
    for path in files:
        assert path.read_bytes()[:4] == b"PAR1"
        assert path.read_bytes()[-4:] == b"PAR1"
        metadata = pq.ParquetFile(path).metadata
        assert all(
            metadata.row_group(group).column(column).compression == "ZSTD"
            for group in range(metadata.num_row_groups)
            for column in range(metadata.num_columns)
        )
    raw = pd.concat([pd.read_parquet(path) for path in files if path.name.startswith("viewing")])
    labels = pd.read_parquet(directory / "device_labels.parquet")
    fullwidth = {"ＮＥＷＳ": "NEWS", "ＤＲＡＭＡ": "DRAMA", "ＶＡＲＩＥＴＹ": "VARIETY", "ＡＮＩＭＥ": "ANIME", "ＳＰＯＲＴＳ": "SPORTS"}
    raw["GENRE"] = raw.GENRE.str.strip(" 　").str.upper().replace(fullwidth)
    raw["VIEW_MINUTES"] = (raw.VIEW_TO - raw.VIEW_FROM).dt.total_seconds() / 60
    raw["VIEW_DATE"] = raw.VIEW_FROM.dt.date
    daily = raw.groupby(["NETWORK_ID", "DEVICE_ID", "VIEW_DATE", "GENRE"], as_index=False).agg(
        SESSION_COUNT=("EVENT_ID", "size"), VIEW_MINUTES=("VIEW_MINUTES", "sum")
    )
    return daily, labels, raw


@pytest.fixture
def local_session():
    session = Session.builder.config("local_testing", True).create()
    yield session
    session.close()


@pytest.fixture
def features(notebook, parquet_data):
    daily, labels, _ = parquet_data
    namespace = namespace_for(notebook)
    namespace.update(session=pandas_session(daily, labels), sf=PANDAS_FUNCTIONS)
    execute_cell(notebook, 4, namespace)
    return namespace


def test_nbformat_and_all_python_asts(notebook):
    nbformat.validate(notebook)
    assert len(notebook.cells) == 14
    assert [index for index, cell in enumerate(notebook.cells) if cell.cell_type == "code"] == [2, 4, 6, 8, 10, 12]
    for index, cell in enumerate(notebook.cells):
        assert cell.id
        if cell.cell_type == "code":
            ast.parse(cell.source, filename=f"cell[{index}]")
    print("NOTEBOOK_SHA256", hashlib.sha256(NOTEBOOK_PATH.read_bytes()).hexdigest())


def test_setup_declares_ml_creation_and_common_wh_permissions():
    sql = (ROOT / "sql/01_setup.sql").read_text()
    statements = [re.sub(r"\s+", " ", statement).upper() for statement in sql.split(";")]
    for privilege in ["USAGE", "CREATE TABLE", "CREATE MODEL", "CREATE NOTEBOOK", "CREATE STAGE"]:
        assert any(
            "GRANT " in statement and privilege in statement
            and "ON SCHEMA BCAST_PLATFORM_HANDSON.ML TO ROLE BCAST_PLATFORM_ENGINEER_ROLE" in statement
            for statement in statements
        )
    assert "GRANT USAGE ON WAREHOUSE BCAST_PLATFORM_COMMON_WH TO ROLE BCAST_PLATFORM_ENGINEER_ROLE" in sql


def test_parquet_known100_and_feature_aggregation(features, parquet_data):
    _, labels, raw = parquet_data
    assert len(raw) == 18000
    assert labels.loc[~labels.LABEL_AVAILABLE, "TARGET_SPORTS_FAN"].isna().all()
    assert labels.loc[labels.LABEL_AVAILABLE, "TARGET_SPORTS_FAN"].value_counts().to_dict() == {0: 50, 1: 50}
    actual = features["features_pdf"].set_index("DEVICE_ID")
    expected = raw.groupby("DEVICE_ID").agg(TOTAL_MINUTES=("VIEW_MINUTES", "sum"), TOTAL_SESSIONS=("EVENT_ID", "size"))
    np.testing.assert_allclose(actual.TOTAL_MINUTES, expected.TOTAL_MINUTES)
    np.testing.assert_array_equal(actual.TOTAL_SESSIONS, expected.TOTAL_SESSIONS)
    for genre in ["NEWS", "DRAMA", "VARIETY", "ANIME", "SPORTS"]:
        genre_minutes = raw.loc[raw.GENRE == genre].groupby("DEVICE_ID").VIEW_MINUTES.sum().reindex(actual.index, fill_value=0)
        np.testing.assert_allclose(actual[genre + "_SHARE"], genre_minutes / expected.TOTAL_MINUTES)
    assert len(features["known_pdf"]) == 100
    assert not {"DEVICE_ID", "LABEL_AVAILABLE", "TARGET_SPORTS_FAN"} & set(features["FEATURE_COLUMNS"])


@pytest.mark.parametrize("defect, message", [
    ("missing_device", "200"), ("extra_device", "200"), ("duplicate_label", "重複"),
    ("mismatched_id", "D0001"), ("zero_minutes", "欠損"), ("infinite_minutes", "欠損"),
    ("missing_flag", "フラグ"), ("known99", "既知100"), ("unknown_target", "既知100"),
    ("missing_known_target", "0/1"), ("invalid_target", "0/1"), ("unbalanced", "各クラス50"),
])
def test_cell4_rejects_invalid_inputs(notebook, parquet_data, defect, message):
    daily, labels, _ = parquet_data
    daily, labels = daily.copy(), labels.copy()
    if defect == "missing_device":
        daily = daily[daily.DEVICE_ID != "D0200"]
    elif defect == "extra_device":
        daily = pd.concat([daily, daily.iloc[:1].assign(DEVICE_ID="D0201")], ignore_index=True)
    elif defect == "duplicate_label":
        labels.loc[1, "DEVICE_ID"] = labels.loc[0, "DEVICE_ID"]
    elif defect == "mismatched_id":
        labels.loc[0, "DEVICE_ID"] = "WRONG"
    elif defect in {"zero_minutes", "infinite_minutes"}:
        daily.loc[daily.DEVICE_ID == "D0001", "VIEW_MINUTES"] = 0 if defect == "zero_minutes" else np.inf
    elif defect == "missing_flag":
        labels["LABEL_AVAILABLE"] = labels.LABEL_AVAILABLE.astype(object)
        labels.loc[0, "LABEL_AVAILABLE"] = None
    elif defect == "known99":
        labels.loc[0, ["LABEL_AVAILABLE", "TARGET_SPORTS_FAN"]] = [False, np.nan]
    elif defect == "unknown_target":
        labels.loc[199, "TARGET_SPORTS_FAN"] = 0
    elif defect == "missing_known_target":
        labels.loc[0, "TARGET_SPORTS_FAN"] = np.nan
    elif defect == "invalid_target":
        labels.loc[0, "TARGET_SPORTS_FAN"] = 2
    else:
        labels.loc[0, "TARGET_SPORTS_FAN"] = 1 - labels.loc[0, "TARGET_SPORTS_FAN"]
    namespace = namespace_for(notebook)
    namespace.update(session=pandas_session(daily, labels), sf=PANDAS_FUNCTIONS)
    with pytest.raises(ValueError, match=message):
        execute_cell(notebook, 4, namespace)


def test_cell6_real_training_and_heldout_metrics(notebook, features):
    execute_cell(notebook, 6, features)
    train, heldout = features["train_pdf"], features["evaluation_pdf"]
    assert len(train) == 80 and len(heldout) == 20
    assert set(train.DEVICE_ID).isdisjoint(heldout.DEVICE_ID)
    assert train.TARGET_SPORTS_FAN.value_counts().to_dict() == {0: 40, 1: 40}
    assert heldout.TARGET_SPORTS_FAN.value_counts().to_dict() == {0: 10, 1: 10}
    assert isinstance(features["model"], DecisionTreeClassifier)
    assert features["model"].max_depth == 3 and features["model"].min_samples_leaf == 8
    assert features["model"].tree_.n_node_samples[0] == 80
    baseline_predictions = features["baseline"].predict(features["evaluation_features"])
    metrics = {
        "scope": "offline regenerated true Parquet; pandas dbt equivalent and cell4 expression mock",
        "seed": 20260701, "split_seed": 42, "train": 80, "heldout": 20,
        "accuracy": features["heldout_accuracy"],
        "balanced_accuracy": balanced_accuracy_score(features["evaluation_labels"], features["evaluation_predictions"]),
        "baseline_accuracy": features["baseline_accuracy"],
        "baseline_balanced_accuracy": balanced_accuracy_score(features["evaluation_labels"], baseline_predictions),
        "confusion_matrix_labels_0_1": confusion_matrix(features["evaluation_labels"], features["evaluation_predictions"], labels=[0, 1]).tolist(),
        "versions": {name: version(name) for name in ["scikit-learn", "pandas", "numpy", "pyarrow", "snowflake-snowpark-python", "snowflake-ml-python"]},
    }
    assert metrics["baseline_accuracy"] == metrics["baseline_balanced_accuracy"] == 0.5
    first_predictions = features["evaluation_predictions"].copy()
    execute_cell(notebook, 6, features)
    np.testing.assert_array_equal(first_predictions, features["evaluation_predictions"])
    print("OFFLINE_METRICS", json.dumps(metrics, sort_keys=True))


@pytest.mark.parametrize("replacement", ["NOT_A_DEVICE", None])
def test_cell4_rejects_matching_noncanonical_or_null_ids(notebook, parquet_data, replacement):
    daily, labels, _ = parquet_data
    daily, labels = daily.copy(), labels.copy()
    daily.loc[daily.DEVICE_ID == "D0200", "DEVICE_ID"] = replacement
    labels.loc[labels.DEVICE_ID == "D0200", "DEVICE_ID"] = replacement
    namespace = namespace_for(notebook)
    namespace.update(session=pandas_session(daily, labels), sf=PANDAS_FUNCTIONS)
    with pytest.raises(ValueError, match="欠損" if replacement is None else "D0001"):
        execute_cell(notebook, 4, namespace)


@pytest.fixture
def inference_namespace(notebook, local_session):
    namespace = namespace_for(notebook)
    namespace["features_pdf"] = pd.DataFrame({
        name: np.arange(200, dtype=float) + offset
        for offset, name in enumerate(namespace["FEATURE_COLUMNS"])
    }).assign(DEVICE_ID=[f"D{number:04d}" for number in range(1, 201)])
    namespace["session"] = MagicMock(wraps=local_session)
    namespace["registered_version"] = MagicMock(
        model_name=namespace["MODEL_NAME"], version_name=namespace["MODEL_VERSION"],
    )
    namespace["registered_name"] = namespace["MODEL_NAME"]
    namespace["registered_version_name"] = namespace["MODEL_VERSION"]
    return namespace


def output_fixture(namespace):
    output = namespace["features_pdf"][namespace["FEATURE_COLUMNS"]].drop_duplicates().copy()
    output["OUTPUT_FEATURE_0"] = (output.TOTAL_MINUTES.astype(int) % 2).astype(int)
    return output.sample(frac=1, random_state=12).reset_index(drop=True)


def mock_registry_output(namespace, output):
    result = MagicMock(spec=DataFrame)
    result.limit.return_value.to_pandas.return_value = output
    namespace["registered_version"].run.return_value = result
    return result


@pytest.mark.parametrize("duplicate_features", [False, True])
def test_cell10_aligns_shuffled_features_and_preserves_ids(notebook, inference_namespace, duplicate_features):
    namespace = inference_namespace
    if duplicate_features:
        namespace["features_pdf"].loc[1, namespace["FEATURE_COLUMNS"]] = namespace["features_pdf"].loc[0, namespace["FEATURE_COLUMNS"]].to_numpy()
    output = output_fixture(namespace)
    result = mock_registry_output(namespace, output)
    execute_cell(notebook, 10, namespace)
    actual = namespace["prediction_pdf"]
    assert actual.DEVICE_ID.is_unique and len(actual) == 200
    assert set(actual.DEVICE_ID) == set(namespace["features_pdf"].DEVICE_ID)
    expected = namespace["features_pdf"].set_index("DEVICE_ID").TOTAL_MINUTES.astype(int) % 2
    pd.testing.assert_series_equal(actual.set_index("DEVICE_ID").PREDICTED_SPORTS_FAN, expected, check_names=False)
    args, kwargs = namespace["registered_version"].run.call_args
    assert isinstance(args[0], DataFrame)
    assert args[0] is namespace["prediction_sdf"]
    assert args[0].count() == (199 if duplicate_features else 200)
    assert list(args[0].columns) == namespace["FEATURE_COLUMNS"]
    assert all(isinstance(field.datatype, DoubleType) for field in args[0].schema.fields)
    expected_input = namespace["features_pdf"][namespace["FEATURE_COLUMNS"]].drop_duplicates().reset_index(drop=True)
    pd.testing.assert_frame_equal(args[0].to_pandas(), expected_input)
    assert kwargs == {"function_name": "predict"}
    namespace["session"].create_dataframe.assert_called_once()
    result.limit.assert_called_once_with(201)
    result.limit.return_value.to_pandas.assert_called_once_with()
    result.to_pandas.assert_not_called()


@pytest.mark.parametrize("defect, exception, message", [
    ("predictions_only", RuntimeError, "入力列"), ("non_pandas", RuntimeError, "表へ変換"),
    ("extra_output", RuntimeError, "一つ"), ("no_output", RuntimeError, "一つ"),
    ("missing_row", ValueError, "行数"), ("duplicate_row", ValueError, "一意性"),
    ("null_prediction", ValueError, "0/1"), ("invalid_prediction", ValueError, "0/1"),
    ("changed_feature", ValueError, "対応"), ("extra_row", ValueError, "行数"),
])
def test_cell10_rejects_unsafe_registry_outputs(notebook, inference_namespace, defect, exception, message):
    namespace = inference_namespace
    output = output_fixture(namespace)
    if defect == "predictions_only":
        output = output[["OUTPUT_FEATURE_0"]]
    elif defect == "non_pandas":
        output = output.to_numpy()
    elif defect == "extra_output":
        output["EXTRA"] = 1
    elif defect == "no_output":
        output = output.drop(columns="OUTPUT_FEATURE_0")
    elif defect == "missing_row":
        output = output.iloc[:-1]
    elif defect == "duplicate_row":
        output.iloc[1] = output.iloc[0]
    elif defect == "null_prediction":
        output.loc[0, "OUTPUT_FEATURE_0"] = np.nan
    elif defect == "invalid_prediction":
        output.loc[0, "OUTPUT_FEATURE_0"] = 2
    elif defect == "extra_row":
        output = pd.concat([output, output.iloc[:1]], ignore_index=True)
    else:
        output.loc[0, "TOTAL_MINUTES"] += 0.000001
    result = mock_registry_output(namespace, output)
    with pytest.raises(exception, match=message):
        execute_cell(notebook, 10, namespace)
    result.limit.assert_called_once_with(201)


@pytest.mark.parametrize("failure_stage", ["run", "collect"])
def test_cell10_registry_failure_propagates(notebook, inference_namespace, failure_stage):
    namespace = inference_namespace
    result = mock_registry_output(namespace, output_fixture(namespace))
    failing_call = namespace["registered_version"].run if failure_stage == "run" else result.limit.return_value.to_pandas
    failing_call.side_effect = RuntimeError("Warehouse inference failed")
    with pytest.raises(RuntimeError, match="Warehouse inference failed"):
        execute_cell(notebook, 10, namespace)
    assert "prediction_pdf" not in namespace


@pytest.mark.parametrize("existing", ["absent", "other_version", "same_version", "bad_models", "bad_versions", "permission_error", "log_error"])
def test_cell8_registry_guard_never_drops(notebook, existing):
    namespace = namespace_for(notebook)
    registry = MagicMock()
    registry.show_models.return_value = pd.DataFrame({"name": [] if existing == "absent" else [namespace["MODEL_NAME"]]})
    registry.get_model.return_value.show_versions.return_value = pd.DataFrame({"name": ["V1" if existing == "same_version" else "V2"]})
    if existing == "bad_models":
        registry.show_models.return_value = pd.DataFrame({"unexpected": [1]})
    if existing == "bad_versions":
        registry.get_model.return_value.show_versions.return_value = pd.DataFrame({"unexpected": [1]})
    if existing == "permission_error":
        registry.show_models.side_effect = PermissionError("Denied")
    if existing == "log_error":
        registry.log_model.side_effect = RuntimeError("Dependency resolution failed")
    namespace.update(session=MagicMock(), Registry=MagicMock(return_value=registry), model=object(),
                     train_features=pd.DataFrame({"FEATURE": range(80)}), heldout_accuracy=0.6, baseline_accuracy=0.5)
    if existing in {"same_version", "bad_models", "bad_versions", "permission_error", "log_error"}:
        with pytest.raises((RuntimeError, PermissionError)):
            execute_cell(notebook, 8, namespace)
        if existing != "log_error":
            registry.log_model.assert_not_called()
    else:
        execute_cell(notebook, 8, namespace)
        args, kwargs = registry.log_model.call_args
        assert args[0] is namespace["model"]
        assert kwargs["version_name"] == "V1" and kwargs["target_platforms"] == ["WAREHOUSE"]
        assert kwargs["options"] == {"relax_version": False}
        assert kwargs["conda_dependencies"] == ["scikit-learn==" + sklearn.__version__]
        assert len(kwargs["sample_input_data"]) == 10
        assert namespace["registered_version"] is registry.log_model.return_value
    assert all("delete" not in str(call).lower() and "drop" not in str(call).lower() for call in registry.mock_calls)


def test_cell12_false_intentionally_stops_before_write(notebook):
    namespace = namespace_for(notebook)
    namespace["session"] = MagicMock()
    with pytest.raises(RuntimeError, match="SAVE_RESULTS"):
        execute_cell(notebook, 12, namespace)
    namespace["session"].create_dataframe.assert_not_called()


@pytest.fixture
def save_namespace(notebook):
    namespace = namespace_for(notebook)
    namespace.update(session=MagicMock(), registered_name="SPORTS_INTEREST_MODEL", registered_version_name="V2",
                     registered_version=SimpleNamespace(model_name="SPORTS_INTEREST_MODEL", version_name="V2"),
                     prediction_pdf=pd.DataFrame({"DEVICE_ID": [f"D{number:04d}" for number in range(1, 201)], "PREDICTED_SPORTS_FAN": [0, 1] * 100, "TARGET_SPORTS_FAN": [1] * 200}))
    namespace["session"].create_dataframe.return_value.with_column.return_value = namespace["session"].create_dataframe.return_value
    return namespace


def test_cell12_enabled_in_memory_writes_contract_to_local_mock(notebook, local_session, save_namespace):
    """Use an aware clock fixture for the SDK mock's naive-current-timestamp gap."""
    namespace = save_namespace
    namespace["session"] = MagicMock(wraps=local_session)
    clock = sf.lit(pd.Timestamp("2026-09-15T09:30:00+09:00").to_pydatetime())
    namespace["sf"] = SimpleNamespace(
        lit=sf.lit, current_timestamp=MagicMock(return_value=clock),
        convert_timezone=MagicMock(wraps=sf.convert_timezone),
    )
    local_session.create_dataframe([("stale",)], schema=["OLD"]).write.save_as_table(OUTPUT_TABLE)
    execute_cell(notebook, 12, namespace, enable_save=True)
    result = local_session.table(OUTPUT_TABLE).to_pandas()
    assert list(result.columns) == ["DEVICE_ID", "PREDICTED_SPORTS_FAN", "MODEL_NAME", "MODEL_VERSION", "PREDICTED_AT"]
    assert len(result) == 200 and result.DEVICE_ID.is_unique and not result.isna().any().any()
    assert set(result.DEVICE_ID) == set(namespace["prediction_pdf"].DEVICE_ID)
    assert set(result.MODEL_NAME) == {"SPORTS_INTEREST_MODEL"} and set(result.MODEL_VERSION) == {"V2"}
    assert local_session.table(OUTPUT_TABLE).schema.fields[-1].datatype.tz.name == "NTZ"
    assert result.PREDICTED_AT.eq(pd.Timestamp("2026-09-15T00:30:00")).all()
    namespace["sf"].current_timestamp.assert_called_once_with()
    namespace["sf"].convert_timezone.assert_called_once()
    pd.testing.assert_frame_equal(
        result[["DEVICE_ID", "PREDICTED_SPORTS_FAN"]],
        namespace["prediction_pdf"][["DEVICE_ID", "PREDICTED_SPORTS_FAN"]], check_dtype=False,
    )
    namespace["session"].table.assert_called_once_with(OUTPUT_TABLE)


def test_cell12_write_failure_propagates(notebook, save_namespace):
    namespace = save_namespace
    session = namespace["session"]
    session.create_dataframe.return_value.write.mode.return_value.save_as_table.side_effect = PermissionError("Denied")
    with pytest.raises(PermissionError, match="Denied"):
        execute_cell(notebook, 12, namespace, enable_save=True)
    session.table.assert_not_called()


@pytest.mark.parametrize("defect, message", [
    ("missing_row", "200台"), ("extra_row", "200台"), ("null_id", "欠損"),
    ("duplicate_id", "重複"), ("noncanonical_id", "端末ID"),
    ("null_prediction", "0/1"), ("invalid_prediction", "0/1"),
    ("stale_name", "モデルの版"), ("stale_version", "モデルの版"),
    ("old_invalid_predictions", "重複"),
])
def test_cell12_rejects_invalid_or_stale_predictions_before_write(notebook, save_namespace, defect, message):
    namespace = save_namespace
    predictions = namespace["prediction_pdf"]
    if defect == "missing_row":
        namespace["prediction_pdf"] = predictions.iloc[:-1]
    elif defect == "extra_row":
        namespace["prediction_pdf"] = pd.concat([predictions, predictions.iloc[:1]], ignore_index=True)
    elif defect == "null_id":
        predictions.loc[0, "DEVICE_ID"] = None
    elif defect == "duplicate_id":
        predictions.loc[0, "DEVICE_ID"] = predictions.loc[1, "DEVICE_ID"]
    elif defect == "noncanonical_id":
        predictions.loc[0, "DEVICE_ID"] = "NOT_A_DEVICE"
    elif defect == "null_prediction":
        predictions.loc[0, "PREDICTED_SPORTS_FAN"] = np.nan
    elif defect == "invalid_prediction":
        predictions.loc[0, "PREDICTED_SPORTS_FAN"] = 2
    elif defect == "stale_name":
        namespace["registered_name"] = "OLD_MODEL"
    elif defect == "stale_version":
        namespace["registered_version_name"] = "V1"
    else:
        predictions["DEVICE_ID"] = "D0001"
        predictions["PREDICTED_SPORTS_FAN"] = 2
    with pytest.raises(ValueError, match=message):
        execute_cell(notebook, 12, namespace, enable_save=True)
    namespace["session"].create_dataframe.assert_not_called()
    namespace["session"].table.assert_not_called()


@pytest.mark.parametrize("defect, exception, message", [
    ("none", None, None), ("missing_row", RuntimeError, "保存後確認"),
    ("extra_row", RuntimeError, "保存後確認"), ("duplicate_id", RuntimeError, "保存後確認"),
    ("changed_id", AssertionError, "DEVICE_ID"),
    ("changed_prediction", AssertionError, "PREDICTED_SPORTS_FAN"),
    ("wrong_name", RuntimeError, "モデル版"), ("wrong_version", RuntimeError, "モデル版"),
    ("null_time", RuntimeError, "保存日時"), ("read_error", PermissionError, "Read denied"),
])
def test_cell12_validates_readback(notebook, save_namespace, defect, exception, message, capsys):
    namespace = save_namespace
    session = namespace["session"]
    saved = namespace["prediction_pdf"][["DEVICE_ID", "PREDICTED_SPORTS_FAN"]].assign(
        MODEL_NAME=namespace["registered_name"], MODEL_VERSION=namespace["registered_version_name"],
        PREDICTED_AT=pd.Timestamp("2026-09-15T00:00:00"),
    )
    if defect == "missing_row":
        saved = saved.iloc[:-1]
    elif defect == "extra_row":
        saved = pd.concat([saved, saved.iloc[:1]], ignore_index=True)
    elif defect == "duplicate_id":
        saved.loc[0, "DEVICE_ID"] = saved.loc[1, "DEVICE_ID"]
    elif defect == "changed_id":
        saved.loc[0, "DEVICE_ID"] = "NOT_A_DEVICE"
    elif defect == "changed_prediction":
        saved.loc[0, "PREDICTED_SPORTS_FAN"] = 1 - saved.loc[0, "PREDICTED_SPORTS_FAN"]
    elif defect == "wrong_name":
        saved.loc[0, "MODEL_NAME"] = "WRONG_MODEL"
    elif defect == "wrong_version":
        saved.loc[0, "MODEL_VERSION"] = "V1"
    elif defect == "null_time":
        saved.loc[0, "PREDICTED_AT"] = pd.NaT
    result = session.table.return_value
    result.limit.return_value.to_pandas.return_value = saved.sample(frac=1, random_state=24)
    if defect == "read_error":
        result.limit.return_value.to_pandas.side_effect = PermissionError("Read denied")
    if exception:
        with pytest.raises(exception, match=message):
            execute_cell(notebook, 12, namespace, enable_save=True)
        assert "保存・照合しました" not in capsys.readouterr().out
    else:
        execute_cell(notebook, 12, namespace, enable_save=True)
        assert "保存・照合しました" in capsys.readouterr().out
    session.create_dataframe.return_value.write.mode.assert_called_once_with("overwrite")
    session.create_dataframe.return_value.write.mode.return_value.save_as_table.assert_called_once_with(OUTPUT_TABLE)
    session.table.assert_called_once_with(OUTPUT_TABLE)
    result.limit.assert_called_once_with(201)
    result.limit.return_value.to_pandas.assert_called_once_with()


def test_installed_sdk_snowpark_preserves_features_without_order_guarantee():
    package = distribution("snowflake-ml-python")
    path = Path(package.locate_file("snowflake/ml/model/_client/ops/model_ops.py"))
    tree = ast.parse(path.read_text())
    implementations = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == "invoke_method"]
    implementation = max(implementations, key=lambda node: len(node.body))
    branch = next(node for node in ast.walk(implementation) if isinstance(node, ast.If) and ast.unparse(node.test) == "not isinstance(X, dataframe.DataFrame)")
    flags = {node.targets[0].id: ast.literal_eval(node.value) for node in branch.body if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"keep_order", "output_with_input_features"}}
    assert flags == {"keep_order": True, "output_with_input_features": False}
    snowpark_flags = {node.targets[0].id: ast.literal_eval(node.value) for node in branch.orelse if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"keep_order", "output_with_input_features"}}
    assert snowpark_flags == {"keep_order": False, "output_with_input_features": True}
    assert "s_df = X" in ast.unparse(branch.orelse)
    drop_branch = next(node for node in ast.walk(implementation) if isinstance(node, ast.If) and ast.unparse(node.test) == "not output_with_input_features")
    assert "df_res.drop(*cols_to_drop)" in ast.unparse(drop_branch)
    return_branch = next(node for node in implementation.body if isinstance(node, ast.If) and any(isinstance(child, ast.Return) for child in node.orelse))
    assert ast.unparse(return_branch.orelse) == "return df_res"
    print("SDK_STATIC_EVIDENCE", package.version, str(path), branch.lineno, drop_branch.lineno)
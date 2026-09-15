import ast
from datetime import date
from pathlib import Path
import re
import sqlite3
import sys
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import streamlit as st
from streamlit.testing.v1 import AppTest
from snowflake.snowpark.exceptions import SnowparkSQLException
import yaml


APP_DIR = Path(__file__).resolve().parents[1]
ROOT = APP_DIR.parent
sys.path.insert(0, str(APP_DIR))
import queries


VIEWING_ROWS = [
    ("NW01", "D0001", "2026-07-01", "SPORTS", 2, 20.0),
    ("NW01", "D0001", "2026-07-01", "NEWS", 1, 10.0),
    ("NW02", "D0001", "2026-07-02", "SPORTS", 3, 30.0),
    ("NW01", "D0002", "2026-07-01", "DRAMA", 1, 15.0),
    ("NW02", "D0003", "2026-07-03", "NEWS", 1, 5.0),
]
PREDICTION_ROWS = [
    ("D0001", 1, "SPORTS_INTEREST_MODEL", "V1", "2026-08-01 12:00:00"),
    ("D0002", 0, "SPORTS_INTEREST_MODEL", "V1", "2026-08-01 12:00:00"),
    ("D0999", 1, "SPORTS_INTEREST_MODEL", "V1", "2026-08-01 12:00:00"),
]
START = date(2026, 7, 1)
END = date(2026, 7, 3)


def fixture_query(sql, params=(), rows=None, predictions=None):
    with sqlite3.connect(":memory:") as database:
        database.execute("CREATE TABLE viewing (NETWORK_ID TEXT, DEVICE_ID TEXT, VIEW_DATE TEXT, GENRE TEXT, SESSION_COUNT INTEGER, VIEW_MINUTES REAL)")
        database.execute("CREATE TABLE predictions (DEVICE_ID TEXT, PREDICTED_SPORTS_FAN INTEGER, MODEL_NAME TEXT, MODEL_VERSION TEXT, PREDICTED_AT TEXT)")
        database.executemany("INSERT INTO viewing VALUES (?, ?, ?, ?, ?, ?)", VIEWING_ROWS if rows is None else rows)
        database.executemany("INSERT INTO predictions VALUES (?, ?, ?, ?, ?)", PREDICTION_ROWS if predictions is None else predictions)
        local_sql = sql.replace(queries.COMMON_TABLE, "viewing").replace(queries.PREDICTIONS_TABLE, "predictions")
        return pd.read_sql_query(local_sql, database, params=params)


class QueryTests(unittest.TestCase):
    def test_unique_reach_across_dates_stations_genres(self):
        result = fixture_query(*queries.aggregate_query("summary", START, END, queries.NETWORKS)).iloc[0]
        self.assertEqual(result["DISTINCT_REACH"], 3)
        self.assertEqual(result["TOTAL_SESSIONS"], 8)
        self.assertEqual(result["TOTAL_MINUTES"], 80)
        for group in ("daily", "network", "genre"):
            breakdown = fixture_query(*queries.aggregate_query(group, START, END, queries.NETWORKS))
            self.assertGreater(breakdown["DISTINCT_REACH"].sum(), 3)

    def test_filter_values_are_bound(self):
        sql, params = queries.aggregate_query("summary", START, START, ["NW01"])
        self.assertNotIn("2026-07-01", sql)
        self.assertNotIn("NW01", sql)
        self.assertEqual(sql.count("?"), len(params))
        self.assertEqual(params, ("2026-07-01", "2026-07-01", "NW01"))
        result = fixture_query(sql, params).iloc[0]
        self.assertEqual(result["DISTINCT_REACH"], 2)
        self.assertEqual(result["TOTAL_SESSIONS"], 4)

    def test_invalid_filters_rejected(self):
        for networks in ([], ["NW99"], ["NW01' OR 1=1 --"]):
            with self.assertRaises(ValueError):
                queries.aggregate_query("summary", START, END, networks)
        with self.assertRaises(ValueError):
            queries.aggregate_query("summary", END, START, ["NW01"])
        with self.assertRaises(ValueError):
            queries.aggregate_query("summary", None, END, ["NW01"])
        with self.assertRaises(KeyError):
            queries.aggregate_query("NETWORK_ID; SELECT 1", START, END, ["NW01"])

    def test_empty_results_are_zero_not_nan(self):
        result = fixture_query(*queries.aggregate_query("summary", START, END, ["NW05"])).iloc[0]
        self.assertEqual(result.tolist(), [0, 0, 0])

    def test_prediction_join_counts_each_selected_device_once(self):
        result = fixture_query(*queries.prediction_query(START, END, queries.NETWORKS))
        self.assertEqual(result["DEVICE_COUNT"].sum(), 3)
        self.assertEqual(result["DEVICE_COUNT"].tolist(), [1, 1, 1])
        self.assertIn("予測なし", result["PREDICTION_GROUP"].tolist())
        self.assertEqual(result["MODEL_VERSION"].dropna().unique().tolist(), ["V1"])

    def test_duplicate_prediction_does_not_fan_out(self):
        duplicates = PREDICTION_ROWS + [PREDICTION_ROWS[0]]
        health = fixture_query(queries.PREDICTION_HEALTH_SQL, predictions=duplicates).iloc[0]
        self.assertNotEqual(health["ROW_COUNT"], health["DEVICE_COUNT"])
        result = fixture_query(*queries.prediction_query(START, END, queries.NETWORKS), predictions=duplicates)
        self.assertEqual(result["DEVICE_COUNT"].sum(), 3)

    def test_missing_and_invalid_predictions(self):
        health = fixture_query(queries.PREDICTION_HEALTH_SQL, predictions=[]).iloc[0]
        self.assertEqual(health["ROW_COUNT"], 0)
        for invalid in (None, 2):
            rows = [("D0001", invalid, "SPORTS_INTEREST_MODEL", "V1", "2026-08-01")]
            health = fixture_query(queries.PREDICTION_HEALTH_SQL, predictions=rows).iloc[0]
            self.assertEqual(health["INVALID_COUNT"], 1)
        health = fixture_query(queries.PREDICTION_HEALTH_SQL, predictions=[(None, 1, "model", "V1", "2026-08-01")]).iloc[0]
        self.assertNotEqual(health["ROW_COUNT"], health["DEVICE_COUNT"])

    def test_exception_classifier_does_not_hide_invalid_columns(self):
        self.assertTrue(queries.unavailable_object(SnowparkSQLException("absent", sql_error_code=2003)))
        self.assertFalse(queries.unavailable_object(SnowparkSQLException("invalid identifier", sql_error_code=904)))


class AppTests(unittest.TestCase):
    def setUp(self):
        st.cache_data.clear()
        self.rows = VIEWING_ROWS
        self.predictions = PREDICTION_ROWS
        self.failure = None
        self.calls = []
        connection = Mock()
        connection.session.return_value.sql.side_effect = self.mock_sql
        self.connection_patch = patch("streamlit.connection", return_value=connection)
        self.connection_patch.start()
        self.addCleanup(self.connection_patch.stop)
        self.app = AppTest.from_file(str(APP_DIR / "streamlit_app.py"), default_timeout=20)

    def mock_sql(self, sql, params):
        self.calls.append((sql, params))
        if queries.PREDICTIONS_TABLE in sql and self.failure is not None:
            raise self.failure
        return Mock(to_pandas=lambda: fixture_query(sql, params, rows=self.rows, predictions=self.predictions))

    def assert_no_crash(self):
        self.assertFalse(self.app.exception, str(self.app.exception))

    def test_initial_two_tabs_no_prediction_query(self):
        self.app.run()
        self.assert_no_crash()
        self.assertEqual(len(self.app.tabs), 2)
        self.assertEqual([metric.value for metric in self.app.metric], ["3", "80.0", "8"])
        self.assertFalse(any(queries.PREDICTIONS_TABLE in sql for sql, params in self.calls))

    def test_prediction_success(self):
        self.app.run().checkbox[0].check().run()
        self.assert_no_crash()
        self.assertEqual(self.app.dataframe[-1].value["端末数"].sum(), 3)

    def test_prediction_missing_keeps_metrics(self):
        self.failure = SnowparkSQLException("absent", sql_error_code=2003)
        self.app.run().checkbox[0].check().run()
        self.assert_no_crash()
        self.assertEqual(len(self.app.metric), 3)
        self.assertTrue(any("未作成" in item.value for item in self.app.info))

    def test_prediction_unexpected_sql_error_is_not_missing(self):
        self.failure = SnowparkSQLException("bad column", sql_error_code=904)
        self.app.run().checkbox[0].check().run()
        self.assert_no_crash()
        self.assertTrue(any("未作成とは限りません" in item.value for item in self.app.error))
        self.assertEqual(len(self.app.metric), 3)

    def test_prediction_empty(self):
        self.predictions = []
        self.app.run().checkbox[0].check().run()
        self.assert_no_crash()
        self.assertTrue(any("予測テーブルは空" in item.value for item in self.app.info))

    def test_prediction_duplicates_rejected(self):
        self.predictions = PREDICTION_ROWS + [PREDICTION_ROWS[0]]
        self.app.run().checkbox[0].check().run()
        self.assert_no_crash()
        self.assertTrue(any("重複端末" in item.value for item in self.app.error))

    def test_prediction_invalid_class_rejected(self):
        self.predictions = [("D0001", 2, "model", "V1", "2026-08-01")]
        self.app.run().checkbox[0].check().run()
        self.assert_no_crash()
        self.assertTrue(any("不正なクラス" in item.value for item in self.app.error))
        self.assertEqual(len(self.app.metric), 3)

    def test_common_missing_stops_with_actionable_message(self):
        with patch("streamlit.connection") as connection:
            connection.return_value.session.return_value.sql.side_effect = SnowparkSQLException("absent", sql_error_code=2003)
            self.app.run()
        self.assert_no_crash()
        self.assertTrue(any("共通マート作成" in item.value for item in self.app.error))
        self.assertFalse(self.app.metric)

    def test_empty_common(self):
        self.rows = []
        self.app.run()
        self.assert_no_crash()
        self.assertTrue(any("COMMON.VIEWING_DAILY は空" in item.value for item in self.app.info))

    def test_single_day_single_station(self):
        self.app.run().multiselect[0].set_value(["NW01"]).run()
        self.app.date_input[0].set_value((START, START)).run()
        self.assert_no_crash()
        self.assertEqual([metric.value for metric in self.app.metric], ["2", "45.0", "4"])

    def test_station_empty_and_date_incomplete(self):
        self.app.run().multiselect[0].set_value([]).run()
        self.assert_no_crash()
        self.assertFalse(self.app.metric)
        self.app.multiselect[0].set_value(["NW01"]).run()
        self.app.date_input[0].set_value((START,)).run()
        self.assert_no_crash()
        self.assertFalse(self.app.metric)
        self.assertTrue(any("終了日" in item.value for item in self.app.info))

    def test_station_with_no_data(self):
        self.app.run().multiselect[0].set_value(["NW05"]).run()
        self.assert_no_crash()
        self.assertFalse(self.app.metric)
        self.assertTrue(any("視聴データはありません" in item.value for item in self.app.info))

    def test_refresh_updates_cached_data(self):
        self.app.run()
        self.rows = VIEWING_ROWS[:2]
        self.app.button[0].click().run()
        self.assert_no_crash()
        self.assertEqual(self.app.metric[0].value, "1")


class ArtifactTests(unittest.TestCase):
    def test_agent_spec_and_copy_text_match(self):
        sql = (ROOT / "sql/05_agent.sql").read_text()
        docs = (ROOT / "docs/agent_texts.md").read_text()
        spec = yaml.safe_load(sql.split("$$")[1])
        blocks = re.findall(r"```text\n(.*?)\n```", docs, flags=re.DOTALL)
        self.assertEqual(spec["models"], {"orchestration": "auto"})
        self.assertEqual(len(spec["tools"]), 1)
        tool = spec["tools"][0]["tool_spec"]
        self.assertEqual(tool["name"], "SV_VIEWING")
        self.assertEqual(tool["type"], "cortex_analyst_text_to_sql")
        resources = spec["tool_resources"]["SV_VIEWING"]
        self.assertEqual(resources["semantic_view"], "BCAST_PLATFORM_HANDSON.MART.SV_VIEWING")
        self.assertEqual(resources["execution_environment"], {
            "type": "warehouse", "warehouse": "BCAST_PLATFORM_COMMON_WH", "query_timeout": 120,
        })
        for text in [tool["description"], spec["instructions"]["response"], spec["instructions"]["orchestration"]]:
            self.assertIn(text.strip(), blocks)
        for sample in spec["instructions"]["sample_questions"]:
            self.assertIn(sample["question"], blocks)
        self.assertIn(blocks[2], sql)
        self.assertIn(blocks[1], sql)

    def test_semantic_scope_and_metric_expressions(self):
        sql = (ROOT / "sql/04_semantic.sql").read_text()
        self.assertIn("viewing.distinct_reach AS COUNT(DISTINCT DEVICE_ID)", sql)
        self.assertIn("viewing.total_minutes AS SUM(VIEW_MINUTES)", sql)
        self.assertIn("viewing.total_sessions AS SUM(SESSION_COUNT)", sql)
        definition = sql.split("CREATE SEMANTIC VIEW", 1)[1].split(";", 1)[0]
        self.assertEqual(re.findall(r"AS (BCAST_PLATFORM_HANDSON\.[A-Z_]+\.[A-Z_]+)", definition), [queries.COMMON_TABLE])
        for token in ("ML.", "CORTEX SEARCH", "AI_VERIFIED_QUERIES"):
            self.assertNotIn(token, definition)

    def test_new_database_scoped_and_no_remote_assets(self):
        for file_path in [ROOT / "sql/04_semantic.sql", ROOT / "sql/05_agent.sql"]:
            sql = file_path.read_text()
            sql = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
            for token in ("BCAST_VIEWING_HANDSON", "BCAST_HANDSON_WH", "ALTER USER", "TO ROLE PUBLIC", "CREATE OR REPLACE"):
                self.assertNotIn(token, sql)
        for file_path in (APP_DIR / "queries.py", APP_DIR / "streamlit_app.py"):
            source = file_path.read_text()
            ast.parse(source)
            for token in ("https://", "http://", "unsafe_allow_html", "TARGET_SPORTS_FAN", "LABEL_AVAILABLE"):
                self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
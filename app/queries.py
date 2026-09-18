from datetime import date
from math import isfinite
import re


COMMON_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY"
MINUTE_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.MINUTE_AUDIENCE"
PREDICTIONS_TABLE = "BCAST_PLATFORM_HANDSON.ML.PREDICTIONS"
NETWORKS = ("NW01", "NW02", "NW03", "NW04", "NW05")
DATASET_VERSION = "F1_SIGNAL_V2"
EXPECTED_DEVICES = 20000
MODEL_VERSION_PATTERN = r"V([2-9]|[1-9][0-9]+)"

BOUNDS_SQL = f"""
SELECT MIN(VIEW_DATE) AS DATE_MIN, MAX(VIEW_DATE) AS DATE_MAX
FROM {COMMON_TABLE}
"""

PREDICTION_HEALTH_SQL = f"""
SELECT COUNT(*) AS ROW_COUNT,
       COUNT(DISTINCT DEVICE_ID) AS DEVICE_COUNT,
       COUNT(DISTINCT PREDICTION_THRESHOLD) AS THRESHOLD_COUNT,
       MIN(PREDICTION_THRESHOLD) AS PREDICTION_THRESHOLD,
       COUNT(DISTINCT MODEL_VERSION) AS MODEL_VERSION_COUNT,
       MIN(MODEL_VERSION) AS HEALTH_MODEL_VERSION,
       COUNT(DISTINCT DATASET_VERSION) AS DATASET_VERSION_COUNT,
       MIN(DATASET_VERSION) AS DATASET_VERSION,
       COALESCE(SUM(CASE
           WHEN REGEXP_LIKE(DEVICE_ID, 'C[0-9]{{6}}')
                AND DEVICE_ID BETWEEN 'C000001' AND 'C020000'
                AND PROB_F1 BETWEEN 0.0 AND 1.0
                AND PROB_F1 NOT IN ('NaN'::FLOAT, 'inf'::FLOAT, '-inf'::FLOAT)
                AND PREDICTION_THRESHOLD BETWEEN 0.0 AND 1.0
                AND PREDICTION_THRESHOLD NOT IN ('NaN'::FLOAT, 'inf'::FLOAT, '-inf'::FLOAT)
                AND PREDICTED_HAS_F1 IN (0, 1)
                AND PREDICTED_HAS_F1 = CASE WHEN PROB_F1 >= PREDICTION_THRESHOLD THEN 1 ELSE 0 END
                AND MODEL_NAME = 'TV_F1_PRESENCE_MODEL'
                AND REGEXP_LIKE(MODEL_VERSION, '{MODEL_VERSION_PATTERN}')
                AND DATASET_VERSION = '{DATASET_VERSION}'
                AND PREDICTED_AT IS NOT NULL THEN 0 ELSE 1
       END), 0) AS INVALID_COUNT
FROM {PREDICTIONS_TABLE}
"""

AGGREGATES = """
COUNT(DISTINCT DEVICE_ID) AS DISTINCT_REACH,
COALESCE(SUM(VIEW_MINUTES), 0) AS TOTAL_MINUTES,
COALESCE(SUM(SESSION_COUNT), 0) AS TOTAL_SESSIONS
"""

GROUPS = {
    "summary": (),
    "daily": ("VIEW_DATE",),
    "network": ("NETWORK_ID",),
    "genre": ("GENRE",),
}


def viewing_filter(start_date, end_date, networks):
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("開始日と終了日を指定してください。")
    if start_date > end_date:
        raise ValueError("開始日は終了日以前にしてください。")
    selected = tuple(dict.fromkeys(networks))
    if not selected or any(network not in NETWORKS for network in selected):
        raise ValueError("NW01 から NW05 の局を1つ以上選んでください。")
    placeholders = ", ".join("?" for network in selected)
    predicate = f"VIEW_DATE BETWEEN ? AND ? AND NETWORK_ID IN ({placeholders})"
    return predicate, (start_date.isoformat(), end_date.isoformat(), *selected)


def aggregate_query(group, start_date, end_date, networks):
    columns = GROUPS[group]
    predicate, params = viewing_filter(start_date, end_date, networks)
    dimensions = ", ".join(columns)
    projection = f"{dimensions}, " if columns else ""
    grouping = f"GROUP BY {dimensions} ORDER BY {dimensions}" if columns else ""
    return (
        f"SELECT {projection}{AGGREGATES} FROM {COMMON_TABLE} "
        f"WHERE {predicate} {grouping}",
        params,
    )


def prediction_query(start_date, end_date, networks):
    predicate, params = viewing_filter(start_date, end_date, networks)
    return f"""
WITH selected_devices AS (
    SELECT DISTINCT DEVICE_ID FROM {COMMON_TABLE} WHERE {predicate}
), unique_predictions AS (
    SELECT DEVICE_ID, MAX(PROB_F1) AS PROB_F1,
           MAX(PREDICTED_HAS_F1) AS PREDICTED_HAS_F1,
           MAX(MODEL_NAME) AS MODEL_NAME, MAX(MODEL_VERSION) AS MODEL_VERSION,
           MAX(PREDICTED_AT) AS PREDICTED_AT
    FROM {PREDICTIONS_TABLE}
    GROUP BY DEVICE_ID
    HAVING COUNT(*) = 1
), prediction_counts AS (
SELECT CASE
           WHEN prediction.PREDICTED_HAS_F1 = 1 THEN 'F1同居あり（予測1）'
           WHEN prediction.PREDICTED_HAS_F1 = 0 THEN 'F1同居なし（予測0）'
           ELSE '予測なし'
       END AS PREDICTION_GROUP,
       CASE WHEN prediction.PROB_F1 = 1.0 THEN 9
            WHEN prediction.PROB_F1 BETWEEN 0.0 AND 1.0
                 THEN FLOOR(prediction.PROB_F1 * 10)
            ELSE NULL END AS PROBABILITY_BIN,
       COUNT(*) AS DEVICE_COUNT,
       prediction.MODEL_NAME, prediction.MODEL_VERSION,
       MIN(prediction.PREDICTED_AT) AS FIRST_PREDICTED_AT,
       MAX(prediction.PREDICTED_AT) AS LAST_PREDICTED_AT
FROM selected_devices AS selected
LEFT JOIN unique_predictions AS prediction
  ON selected.DEVICE_ID = prediction.DEVICE_ID
GROUP BY PREDICTION_GROUP, PROBABILITY_BIN, prediction.MODEL_NAME, prediction.MODEL_VERSION
), health AS (
{PREDICTION_HEALTH_SQL}
), selected_health AS (
    SELECT COUNT(*) AS SELECTED_DEVICE_COUNT, COALESCE(SUM(CASE
        WHEN REGEXP_LIKE(DEVICE_ID, 'C[0-9]{{6}}')
             AND DEVICE_ID BETWEEN 'C000001' AND 'C020000' THEN 0 ELSE 1
    END), 0) AS INVALID_SELECTED_IDS
    FROM selected_devices
)
SELECT health.ROW_COUNT, health.DEVICE_COUNT AS HEALTH_DEVICE_COUNT,
       health.INVALID_COUNT, health.THRESHOLD_COUNT, health.PREDICTION_THRESHOLD,
       health.MODEL_VERSION_COUNT, health.HEALTH_MODEL_VERSION,
       health.DATASET_VERSION_COUNT, health.DATASET_VERSION,
       selected_health.INVALID_SELECTED_IDS, selected_health.SELECTED_DEVICE_COUNT,
       prediction_counts.*
FROM health CROSS JOIN selected_health LEFT JOIN prediction_counts ON 1 = 1
ORDER BY PREDICTION_GROUP, PROBABILITY_BIN, MODEL_NAME, MODEL_VERSION
""", params


class PredictionValidationError(ValueError):
    pass


def validate_prediction_snapshot(result):
    health_columns = (
        "ROW_COUNT", "HEALTH_DEVICE_COUNT", "INVALID_COUNT", "THRESHOLD_COUNT",
        "PREDICTION_THRESHOLD", "MODEL_VERSION_COUNT", "HEALTH_MODEL_VERSION",
        "DATASET_VERSION_COUNT", "DATASET_VERSION", "INVALID_SELECTED_IDS",
        "SELECTED_DEVICE_COUNT",
    )
    display_columns = (
        "PREDICTION_GROUP", "PROBABILITY_BIN", "DEVICE_COUNT", "MODEL_NAME",
        "MODEL_VERSION", "FIRST_PREDICTED_AT", "LAST_PREDICTED_AT",
    )
    if result.empty or not set(health_columns + display_columns).issubset(result.columns):
        raise PredictionValidationError("予測の検証結果を取得できません。ゼロ件として扱わず、列定義と第3章の出力を確認してください。")
    if len(result[list(health_columns)].drop_duplicates()) != 1:
        raise PredictionValidationError("予測の検証結果が一貫していません。再読込してください。")
    health = result.iloc[0]
    if health["ROW_COUNT"] == 0:
        return None, result.iloc[:0]
    threshold = health["PREDICTION_THRESHOLD"]
    if (
        health[list(health_columns)].isna().any()
        or health["ROW_COUNT"] != EXPECTED_DEVICES
        or health["HEALTH_DEVICE_COUNT"] != EXPECTED_DEVICES
        or health["INVALID_COUNT"] != 0
        or health["INVALID_SELECTED_IDS"] != 0
        or health["THRESHOLD_COUNT"] != 1
        or health["MODEL_VERSION_COUNT"] != 1
        or health["DATASET_VERSION_COUNT"] != 1
        or health["DATASET_VERSION"] != DATASET_VERSION
        or not re.fullmatch(MODEL_VERSION_PATTERN, str(health["HEALTH_MODEL_VERSION"]))
        or not isfinite(float(threshold))
        or not 0 <= float(threshold) <= 1
    ):
        raise PredictionValidationError(
            "予測データを表示できません。20,000端末（C000001〜C020000）の全件・重複端末・欠損・"
            "不正なクラスや確率・保存閾値・端末ID・モデル情報を確認してください。"
            "F1_SIGNAL_V2、単一のV2以降のモデルバージョン、単一の有限な閾値（0〜1）が必要です。"
            "V1や旧形式は第3章で再推論・保存してから再読込してください。"
        )
    predictions = result.loc[result["DEVICE_COUNT"].notna(), list(display_columns)].copy()
    counts = predictions["DEVICE_COUNT"]
    if (
        not 0 <= health["SELECTED_DEVICE_COUNT"] <= EXPECTED_DEVICES
        or counts.sum() != health["SELECTED_DEVICE_COUNT"]
        or not counts.map(lambda count: isfinite(float(count)) and count > 0 and count == int(count)).all()
        or not predictions["PREDICTION_GROUP"].isin(["F1同居あり（予測1）", "F1同居なし（予測0）"]).all()
        or not predictions["PROBABILITY_BIN"].isin(range(10)).all()
        or not predictions["MODEL_NAME"].eq("TV_F1_PRESENCE_MODEL").all()
        or not predictions["MODEL_VERSION"].eq(health["HEALTH_MODEL_VERSION"]).all()
        or predictions[["FIRST_PREDICTED_AT", "LAST_PREDICTED_AT"]].isna().any().any()
    ):
        raise PredictionValidationError("予測件数・分布と検証結果が一致しません。予測なしをゼロに置き換えず、共通マートと第3章の出力を確認してください。")
    return float(threshold), predictions


def minute_query(view_date, networks):
    predicate, params = viewing_filter(view_date, view_date, networks)
    return (
        f"SELECT NETWORK_ID, VIEW_DATE, MINUTE_AT, VIEWING_DEVICES FROM {MINUTE_TABLE} "
        f"WHERE {predicate} ORDER BY MINUTE_AT, NETWORK_ID",
        params,
    )


def unavailable_object(error):
    return (
        str(getattr(error, "sql_error_code", "")).lstrip("0") in {"2003", "2043"}
        or getattr(error, "sqlstate", None) == "42S02"
    )
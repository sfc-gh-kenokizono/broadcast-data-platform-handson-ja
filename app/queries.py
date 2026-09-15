from datetime import date


COMMON_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY"
PREDICTIONS_TABLE = "BCAST_PLATFORM_HANDSON.ML.PREDICTIONS"
NETWORKS = ("NW01", "NW02", "NW03", "NW04", "NW05")

BOUNDS_SQL = f"""
SELECT MIN(VIEW_DATE) AS DATE_MIN, MAX(VIEW_DATE) AS DATE_MAX
FROM {COMMON_TABLE}
"""

PREDICTION_HEALTH_SQL = f"""
SELECT COUNT(*) AS ROW_COUNT,
       COUNT(DISTINCT DEVICE_ID) AS DEVICE_COUNT,
       COALESCE(SUM(CASE
           WHEN PREDICTED_SPORTS_FAN IN (0, 1)
                AND MODEL_NAME IS NOT NULL AND MODEL_VERSION IS NOT NULL
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
    SELECT DEVICE_ID, MAX(PREDICTED_SPORTS_FAN) AS PREDICTED_SPORTS_FAN,
           MAX(MODEL_NAME) AS MODEL_NAME, MAX(MODEL_VERSION) AS MODEL_VERSION,
           MAX(PREDICTED_AT) AS PREDICTED_AT
    FROM {PREDICTIONS_TABLE}
    GROUP BY DEVICE_ID
    HAVING COUNT(*) = 1
), prediction_counts AS (
SELECT CASE
           WHEN prediction.PREDICTED_SPORTS_FAN = 1 THEN 'スポーツ関心あり（予測1）'
           WHEN prediction.PREDICTED_SPORTS_FAN = 0 THEN 'スポーツ関心なし（予測0）'
           ELSE '予測なし'
       END AS PREDICTION_GROUP,
       COUNT(*) AS DEVICE_COUNT,
       prediction.MODEL_NAME, prediction.MODEL_VERSION,
       MIN(prediction.PREDICTED_AT) AS FIRST_PREDICTED_AT,
       MAX(prediction.PREDICTED_AT) AS LAST_PREDICTED_AT
FROM selected_devices AS selected
LEFT JOIN unique_predictions AS prediction
  ON selected.DEVICE_ID = prediction.DEVICE_ID
GROUP BY PREDICTION_GROUP, prediction.MODEL_NAME, prediction.MODEL_VERSION
), health AS (
{PREDICTION_HEALTH_SQL}
)
SELECT health.ROW_COUNT, health.DEVICE_COUNT AS HEALTH_DEVICE_COUNT,
       health.INVALID_COUNT, prediction_counts.*
FROM health LEFT JOIN prediction_counts ON 1 = 1
ORDER BY PREDICTION_GROUP, MODEL_NAME, MODEL_VERSION
""", params


def unavailable_object(error):
    return (
        str(getattr(error, "sql_error_code", "")).lstrip("0") in {"2003", "2043"}
        or getattr(error, "sqlstate", None) == "42S02"
    )
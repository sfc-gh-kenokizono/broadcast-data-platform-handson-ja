from datetime import date


COMMON_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY"
MINUTE_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.MINUTE_AUDIENCE"
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
           WHEN REGEXP_LIKE(DEVICE_ID, 'C[0-9]{{6}}')
                AND DEVICE_ID BETWEEN 'C000001' AND 'C020000'
                AND PROB_F1 BETWEEN 0.0 AND 1.0
                AND PROB_F1 NOT IN ('NaN'::FLOAT, 'inf'::FLOAT, '-inf'::FLOAT)
                AND PREDICTED_HAS_F1 IN (0, 1)
                AND PREDICTED_HAS_F1 = CASE WHEN PROB_F1 >= 0.5 THEN 1 ELSE 0 END
                AND MODEL_NAME = 'TV_F1_PRESENCE_MODEL'
                AND REGEXP_LIKE(MODEL_VERSION, 'V[1-9][0-9]*')
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
    SELECT COALESCE(SUM(CASE
        WHEN REGEXP_LIKE(DEVICE_ID, 'C[0-9]{{6}}')
             AND DEVICE_ID BETWEEN 'C000001' AND 'C020000' THEN 0 ELSE 1
    END), 0) AS INVALID_SELECTED_IDS
    FROM selected_devices
)
SELECT health.ROW_COUNT, health.DEVICE_COUNT AS HEALTH_DEVICE_COUNT,
       health.INVALID_COUNT, selected_health.INVALID_SELECTED_IDS, prediction_counts.*
FROM health CROSS JOIN selected_health LEFT JOIN prediction_counts ON 1 = 1
ORDER BY PREDICTION_GROUP, PROBABILITY_BIN, MODEL_NAME, MODEL_VERSION
""", params


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
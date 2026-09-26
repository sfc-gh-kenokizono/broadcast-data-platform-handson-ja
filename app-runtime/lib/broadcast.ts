export const NETWORKS = ["NW01", "NW02", "NW03", "NW04", "NW05"] as const

export const COMMON_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.VIEWING_DAILY"
export const MINUTE_TABLE = "BCAST_PLATFORM_HANDSON.COMMON.MINUTE_AUDIENCE"
export const PREDICTIONS_TABLE = "BCAST_PLATFORM_HANDSON.ML.PREDICTIONS"
export const AGENT_NAME = "BCAST_PLATFORM_HANDSON.MART.VIEWING_AGENT"
export const QUERY_WAREHOUSE = "BCAST_PLATFORM_COMMON_WH"

export type Network = (typeof NETWORKS)[number]
export type DashboardView = "summary" | "trends" | "predictions" | "minute"

export interface DashboardFilters {
  from: string
  to: string
  networks: Network[]
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/

export function isIsoDate(value: string): boolean {
  if (!ISO_DATE.test(value)) return false
  const date = new Date(`${value}T00:00:00Z`)
  return !Number.isNaN(date.valueOf()) && date.toISOString().slice(0, 10) === value
}

export function parseNetworks(value: string | null): Network[] {
  if (!value) throw new Error("放送局を1つ以上選んでください。")
  const requested = [...new Set(value.split(",").filter(Boolean))]
  if (requested.length === 0 || requested.some((network) => !NETWORKS.includes(network as Network))) {
    throw new Error("放送局はNW01からNW05の範囲で指定してください。")
  }
  return requested as Network[]
}

export function parseFilters(params: URLSearchParams): DashboardFilters {
  const from = params.get("from") ?? ""
  const to = params.get("to") ?? ""
  if (!isIsoDate(from) || !isIsoDate(to) || from > to) {
    throw new Error("有効な開始日と終了日を指定してください。")
  }
  return { from, to, networks: parseNetworks(params.get("networks")) }
}

export function viewingPredicate(networkCount: number): string {
  if (!Number.isInteger(networkCount) || networkCount < 1 || networkCount > NETWORKS.length) {
    throw new Error("放送局数が不正です。")
  }
  return `VIEW_DATE BETWEEN ? AND ? AND NETWORK_ID IN (${Array(networkCount).fill("?").join(", ")})`
}

export function filterBinds(filters: DashboardFilters): string[] {
  return [filters.from, filters.to, ...filters.networks]
}

export function aggregateSql(
  dimensions: readonly string[],
  filters: DashboardFilters,
): { sql: string; binds: string[] } {
  const allowed = new Set(["VIEW_DATE", "NETWORK_ID", "GENRE"])
  if (dimensions.some((dimension) => !allowed.has(dimension))) throw new Error("集計軸が不正です。")
  const projection = dimensions.length ? `${dimensions.join(", ")}, ` : ""
  const grouping = dimensions.length ? ` GROUP BY ${dimensions.join(", ")} ORDER BY ${dimensions.join(", ")}` : ""
  return {
    sql: `SELECT ${projection}COUNT(DISTINCT DEVICE_ID) AS DISTINCT_REACH, COALESCE(SUM(VIEW_MINUTES), 0) AS TOTAL_MINUTES, COALESCE(SUM(SESSION_COUNT), 0) AS TOTAL_SESSIONS FROM ${COMMON_TABLE} WHERE ${viewingPredicate(filters.networks.length)}${grouping}`,
    binds: filterBinds(filters),
  }
}

export function shiftPeriod(filters: DashboardFilters): DashboardFilters {
  const from = new Date(`${filters.from}T00:00:00Z`)
  const to = new Date(`${filters.to}T00:00:00Z`)
  const days = Math.round((to.valueOf() - from.valueOf()) / 86_400_000) + 1
  const previousTo = new Date(from.valueOf() - 86_400_000)
  const previousFrom = new Date(previousTo.valueOf() - (days - 1) * 86_400_000)
  return {
    from: previousFrom.toISOString().slice(0, 10),
    to: previousTo.toISOString().slice(0, 10),
    networks: filters.networks,
  }
}

export function minuteSql(filters: DashboardFilters, date: string): { sql: string; binds: string[] } {
  if (!isIsoDate(date)) throw new Error("有効な分析日を指定してください。")
  const minuteFilters = { ...filters, from: date, to: date }
  return {
    sql: `SELECT NETWORK_ID, VIEW_DATE, MINUTE_AT, VIEWING_DEVICES FROM ${MINUTE_TABLE} WHERE ${viewingPredicate(filters.networks.length)} ORDER BY MINUTE_AT, NETWORK_ID`,
    binds: filterBinds(minuteFilters),
  }
}

export function predictionSql(filters: DashboardFilters): { sql: string; binds: string[] } {
  return {
    sql: `WITH selected_devices AS (
      SELECT DISTINCT DEVICE_ID FROM ${COMMON_TABLE} WHERE ${viewingPredicate(filters.networks.length)}
    ), health AS (
      SELECT COUNT(*) AS ROW_COUNT, COUNT(DISTINCT DEVICE_ID) AS DEVICE_COUNT,
        COUNT(DISTINCT PREDICTION_THRESHOLD) AS THRESHOLD_COUNT,
        MIN(PREDICTION_THRESHOLD) AS PREDICTION_THRESHOLD,
        COUNT(DISTINCT MODEL_VERSION) AS MODEL_VERSION_COUNT,
        MIN(MODEL_VERSION) AS MODEL_VERSION,
        COUNT(DISTINCT PREDICTED_AT) AS PREDICTED_AT_COUNT,
        COUNT(DISTINCT DATASET_VERSION) AS DATASET_VERSION_COUNT,
        MIN(DATASET_VERSION) AS DATASET_VERSION,
        COUNT_IF((REGEXP_LIKE(DEVICE_ID, 'C[0-9]{6}')
          AND DEVICE_ID BETWEEN 'C000001' AND 'C020000'
          AND PROB_F1 BETWEEN 0.0 AND 1.0
          AND PREDICTION_THRESHOLD = 0.50
          AND PREDICTED_HAS_F1 IN (0, 1)
          AND PREDICTED_HAS_F1 = IFF(PROB_F1 >= PREDICTION_THRESHOLD, 1, 0)
          AND MODEL_NAME = 'TV_F1_PRESENCE_MODEL'
          AND REGEXP_LIKE(MODEL_VERSION, 'V[1-9][0-9]*')
          AND DATASET_VERSION = 'F1_SIGNAL_V2'
          AND PREDICTED_AT IS NOT NULL) IS NOT TRUE) AS INVALID_COUNT
      FROM ${PREDICTIONS_TABLE}
    ), selected_predictions AS (
      SELECT prediction.PREDICTED_HAS_F1,
        IFF(prediction.PROB_F1 = 1.0, 9, FLOOR(prediction.PROB_F1 * 10)) AS PROBABILITY_BIN,
        COUNT(*) AS DEVICE_COUNT
      FROM selected_devices selected
      JOIN ${PREDICTIONS_TABLE} prediction USING (DEVICE_ID)
      GROUP BY 1, 2
    )
    SELECT health.*, selected_predictions.PREDICTED_HAS_F1,
      selected_predictions.PROBABILITY_BIN, selected_predictions.DEVICE_COUNT
    FROM health LEFT JOIN selected_predictions ON TRUE
    ORDER BY PREDICTED_HAS_F1, PROBABILITY_BIN`,
    binds: filterBinds(filters),
  }
}

export interface PredictionHealth {
  rowCount: number
  deviceCount: number
  threshold: number
  modelVersion: string
  datasetVersion: string
}

export function validatePredictionRows(rows: Record<string, unknown>[]): PredictionHealth | null {
  if (rows.length === 0) throw new Error("予測の検証結果を取得できません。")
  const first = rows[0]
  const rowCount = Number(first.ROW_COUNT)
  if (rowCount === 0) return null
  const health: PredictionHealth = {
    rowCount,
    deviceCount: Number(first.DEVICE_COUNT),
    threshold: Number(first.PREDICTION_THRESHOLD),
    modelVersion: String(first.MODEL_VERSION ?? ""),
    datasetVersion: String(first.DATASET_VERSION ?? ""),
  }
  const valid = health.rowCount === 20_000
    && health.deviceCount === 20_000
    && Number(first.INVALID_COUNT) === 0
    && Number(first.THRESHOLD_COUNT) === 1
    && health.threshold === 0.5
    && Number(first.MODEL_VERSION_COUNT) === 1
    && /^V[1-9][0-9]*$/.test(health.modelVersion)
    && Number(first.PREDICTED_AT_COUNT) === 1
    && Number(first.DATASET_VERSION_COUNT) === 1
    && health.datasetVersion === "F1_SIGNAL_V2"
  if (!valid) throw new Error("予測スナップショットが20,000端末・単一モデル版・閾値0.50の検証条件を満たしていません。")
  return health
}

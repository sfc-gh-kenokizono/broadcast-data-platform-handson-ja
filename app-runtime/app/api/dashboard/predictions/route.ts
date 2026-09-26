import { parseFilters, predictionSql, QUERY_WAREHOUSE, validatePredictionRows } from "@/lib/broadcast"
import { querySnowflake } from "@/lib/snowflake"

export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  try {
    const filters = parseFilters(new URL(request.url).searchParams)
    const { sql, binds } = predictionSql(filters)
    const rows = await querySnowflake(sql, { binds, warehouse: QUERY_WAREHOUSE })
    const health = validatePredictionRows(rows)
    return Response.json({ health, rows: health ? rows.filter((row) => row.DEVICE_COUNT !== null) : [] })
  } catch (error) {
    const message = error instanceof Error ? error.message : "予測結果を取得できませんでした。"
    console.error("Failed to load prediction snapshot", error)
    return Response.json({ error: message }, { status: message.includes("指定") || message.includes("放送局") ? 400 : 500 })
  }
}

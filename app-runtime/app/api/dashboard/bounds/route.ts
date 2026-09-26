import { querySnowflake } from "@/lib/snowflake"
import { COMMON_TABLE, MINUTE_TABLE, QUERY_WAREHOUSE } from "@/lib/broadcast"

export const dynamic = "force-dynamic"

export async function GET() {
  try {
    const rows = await querySnowflake(
      `SELECT daily.DATE_MIN, daily.DATE_MAX, minute.MINUTE_DATE_MIN, minute.MINUTE_DATE_MAX
       FROM (SELECT MIN(VIEW_DATE) DATE_MIN, MAX(VIEW_DATE) DATE_MAX FROM ${COMMON_TABLE}) daily
       CROSS JOIN (SELECT MIN(VIEW_DATE) MINUTE_DATE_MIN, MAX(VIEW_DATE) MINUTE_DATE_MAX FROM ${MINUTE_TABLE}) minute`,
      { warehouse: QUERY_WAREHOUSE },
    )
    if (!rows[0]?.DATE_MIN || !rows[0]?.DATE_MAX) {
      return Response.json({ error: "共通マートに視聴データがありません。" }, { status: 404 })
    }
    return Response.json(rows[0])
  } catch (error) {
    console.error("Failed to load dashboard bounds", error)
    return Response.json({ error: "分析可能期間を取得できませんでした。" }, { status: 500 })
  }
}

import { aggregateSql, parseFilters, QUERY_WAREHOUSE, shiftPeriod } from "@/lib/broadcast"
import { querySnowflake } from "@/lib/snowflake"

export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  try {
    const filters = parseFilters(new URL(request.url).searchParams)
    const previousFilters = shiftPeriod(filters)
    const [summaryQuery, dailyQuery, networkQuery, previousQuery] = [
      aggregateSql([], filters),
      aggregateSql(["VIEW_DATE"], filters),
      aggregateSql(["NETWORK_ID"], filters),
      aggregateSql([], previousFilters),
    ]
    const [summary, daily, network, previous] = await Promise.all([
      querySnowflake(summaryQuery.sql, { binds: summaryQuery.binds, warehouse: QUERY_WAREHOUSE }),
      querySnowflake(dailyQuery.sql, { binds: dailyQuery.binds, warehouse: QUERY_WAREHOUSE }),
      querySnowflake(networkQuery.sql, { binds: networkQuery.binds, warehouse: QUERY_WAREHOUSE }),
      querySnowflake(previousQuery.sql, { binds: previousQuery.binds, warehouse: QUERY_WAREHOUSE }),
    ])
    return Response.json({ summary: summary[0], previous: previous[0], daily, network, previousPeriod: previousFilters })
  } catch (error) {
    const message = error instanceof Error ? error.message : "経営サマリーを取得できませんでした。"
    const status = message.includes("指定") || message.includes("放送局") ? 400 : 500
    console.error("Failed to load executive summary", error)
    return Response.json({ error: message }, { status })
  }
}

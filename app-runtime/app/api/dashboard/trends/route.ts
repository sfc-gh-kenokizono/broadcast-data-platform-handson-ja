import { aggregateSql, parseFilters, QUERY_WAREHOUSE } from "@/lib/broadcast"
import { querySnowflake } from "@/lib/snowflake"

export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  try {
    const filters = parseFilters(new URL(request.url).searchParams)
    const queries = [
      aggregateSql(["VIEW_DATE"], filters),
      aggregateSql(["NETWORK_ID"], filters),
      aggregateSql(["GENRE"], filters),
      aggregateSql(["NETWORK_ID", "GENRE"], filters),
    ]
    const [daily, network, genre, networkGenre] = await Promise.all(
      queries.map(({ sql, binds }) => querySnowflake(sql, { binds, warehouse: QUERY_WAREHOUSE })),
    )
    return Response.json({ daily, network, genre, networkGenre })
  } catch (error) {
    const message = error instanceof Error ? error.message : "視聴トレンドを取得できませんでした。"
    console.error("Failed to load viewing trends", error)
    return Response.json({ error: message }, { status: message.includes("指定") || message.includes("放送局") ? 400 : 500 })
  }
}

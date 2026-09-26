import { minuteSql, parseFilters, QUERY_WAREHOUSE } from "@/lib/broadcast"
import { querySnowflake } from "@/lib/snowflake"

export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  try {
    const url = new URL(request.url)
    const filters = parseFilters(url.searchParams)
    const { sql, binds } = minuteSql(filters, url.searchParams.get("date") ?? "")
    const rows = await querySnowflake(sql, { binds, warehouse: QUERY_WAREHOUSE })
    return Response.json({ rows })
  } catch (error) {
    const message = error instanceof Error ? error.message : "毎分パルスを取得できませんでした。"
    console.error("Failed to load minute pulse", error)
    return Response.json({ error: message }, { status: message.includes("指定") || message.includes("放送局") ? 400 : 500 })
  }
}

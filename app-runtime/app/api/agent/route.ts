import { AGENT_NAME, QUERY_WAREHOUSE } from "@/lib/broadcast"
import { buildAgentPayload, normalizeAgentResponse, parseAgentRequest } from "@/lib/agent"
import { querySnowflakeLongRunning } from "@/lib/snowflake"

export const dynamic = "force-dynamic"

export async function POST(request: Request) {
  try {
    const agentRequest = parseAgentRequest(await request.json())
    const payload = buildAgentPayload(agentRequest)
    const rows = await querySnowflakeLongRunning(
      `SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(?, ?, TRUE)) AS RESPONSE`,
      {
        callersRights: true,
        warehouse: QUERY_WAREHOUSE,
        binds: [AGENT_NAME, payload],
        maxWaitMs: 900_000,
      },
    )
    return Response.json(normalizeAgentResponse(rows[0]?.RESPONSE))
  } catch (error) {
    const message = error instanceof Error ? error.message : "VIEWING_AGENTへの問い合わせに失敗しました。"
    console.error("Agent request failed", error)
    return Response.json({ error: message }, { status: message.includes("入力") || message.includes("文字") || message.includes("ID") ? 400 : 500 })
  }
}

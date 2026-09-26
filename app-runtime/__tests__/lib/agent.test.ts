import { describe, expect, it } from "vitest"
import { buildAgentPayload, normalizeAgentResponse, parseAgentRequest } from "@/lib/agent"

describe("agent request handling", () => {
  it("validates and builds a first-turn payload", () => {
    const request = parseAgentRequest({ message: " 局別リーチを比較して " })
    const payload = JSON.parse(buildAgentPayload(request))
    expect(payload.messages[0].content[0].text).toBe("局別リーチを比較して")
    expect(payload.stream).toBe(false)
    expect(payload.thread_id).toBeUndefined()
  })

  it("requires both thread identifiers for follow-ups", () => {
    expect(() => parseAgentRequest({ message: "続けて", threadId: 10 })).toThrow("両方")
    const request = parseAgentRequest({ message: "続けて", threadId: 10, parentMessageId: 20 })
    expect(JSON.parse(buildAgentPayload(request))).toMatchObject({ thread_id: 10, parent_message_id: 20 })
  })

  it("normalizes JSON strings returned by Snowflake", () => {
    expect(normalizeAgentResponse('{"status":"completed"}').status).toBe("completed")
  })
})

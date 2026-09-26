export const MAX_AGENT_MESSAGE_LENGTH = 2_000

export interface AgentRequest {
  message: string
  threadId?: number
  parentMessageId?: number
}

export interface AgentContent {
  type: string
  text?: string
  table?: unknown
  chart?: { chart_spec?: string }
  tool_result?: unknown
}

export interface AgentResponse {
  role?: string
  content?: AgentContent[]
  warnings?: { code?: string; message?: string }[]
  metadata?: {
    thread_id?: number
    assistant_message_id?: number
    run_id?: string
  }
  status?: string
}

export function parseAgentRequest(value: unknown): AgentRequest {
  if (!value || typeof value !== "object") throw new Error("質問を入力してください。")
  const body = value as Record<string, unknown>
  const message = typeof body.message === "string" ? body.message.trim() : ""
  if (!message || message.length > MAX_AGENT_MESSAGE_LENGTH) {
    throw new Error(`質問は1文字以上${MAX_AGENT_MESSAGE_LENGTH.toLocaleString()}文字以内で入力してください。`)
  }
  const threadId = parseOptionalId(body.threadId)
  const parentMessageId = parseOptionalId(body.parentMessageId)
  if ((threadId === undefined) !== (parentMessageId === undefined)) {
    throw new Error("会話IDと親メッセージIDは両方指定してください。")
  }
  return { message, threadId, parentMessageId }
}

function parseOptionalId(value: unknown): number | undefined {
  if (value === undefined || value === null) return undefined
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    throw new Error("会話IDが不正です。")
  }
  return value
}

export function buildAgentPayload(request: AgentRequest): string {
  return JSON.stringify({
    ...(request.threadId !== undefined && {
      thread_id: request.threadId,
      parent_message_id: request.parentMessageId,
    }),
    messages: [{ role: "user", content: [{ type: "text", text: request.message }] }],
    background: false,
    stream: false,
    tool_choice: { type: "auto" },
  })
}

export function normalizeAgentResponse(value: unknown): AgentResponse {
  if (typeof value === "string") {
    try {
      return JSON.parse(value) as AgentResponse
    } catch {
      throw new Error("Agent応答をJSONとして解釈できませんでした。")
    }
  }
  if (!value || typeof value !== "object") throw new Error("Agentから有効な応答がありませんでした。")
  return value as AgentResponse
}

"use client"

import { useState } from "react"
import { Bot, RotateCcw, Send, Sparkles, User, WandSparkles } from "lucide-react"
import { VegaEmbed } from "react-vega"
import type { AgentContent, AgentResponse } from "@/lib/agent"

const SAMPLE_QUESTIONS = [
  "2026年5月1日から7月31日の全5局の日別総視聴時間の推移を、折れ線グラフで表示してください",
  "2026年5月1日から7月31日の放送局別リーチを比較してください",
  "2026年7月1日から7日のNW01のジャンル別総視聴時間を教えてください",
]

interface ChatMessage {
  role: "user" | "assistant"
  text?: string
  response?: AgentResponse
}

export function AgentWorkspace() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [threadId, setThreadId] = useState<number>()
  const [parentMessageId, setParentMessageId] = useState<number>()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState("")

  async function sendQuestion(question: string) {
    const message = question.trim()
    if (!message || pending) return
    setMessages((current) => [...current, { role: "user", text: message }])
    setInput("")
    setPending(true)
    setError("")
    try {
      const response = await fetch("/api/agent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, threadId, parentMessageId }),
      })
      const body = await response.json()
      if (!response.ok) throw new Error(body.error ?? "Agentへの問い合わせに失敗しました。")
      const agentResponse = body as AgentResponse
      setMessages((current) => [...current, { role: "assistant", response: agentResponse }])
      if (agentResponse.metadata?.thread_id !== undefined) setThreadId(agentResponse.metadata.thread_id)
      if (agentResponse.metadata?.assistant_message_id !== undefined) setParentMessageId(agentResponse.metadata.assistant_message_id)
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Agentへの問い合わせに失敗しました。")
    } finally {
      setPending(false)
    }
  }

  function resetConversation() {
    setMessages([])
    setThreadId(undefined)
    setParentMessageId(undefined)
    setError("")
  }

  return <div className="agent-layout">
    <section className="agent-intro">
      <span className="agent-orb"><WandSparkles size={25}/></span>
      <p className="eyebrow">CORTEX AGENT</p>
      <h2>視聴データへ自然言語で質問</h2>
      <p>VIEWING_AGENTがSemantic Viewを使い、期間・局・ジャンル別の視聴実績を分析します。</p>
      <div className="agent-facts"><span><Sparkles size={15}/> SV_VIEWING</span><span>日本語応答</span><span>グラフ生成</span></div>
      <div className="sample-list"><strong>質問例</strong>{SAMPLE_QUESTIONS.map((question)=><button key={question} onClick={()=>sendQuestion(question)} disabled={pending} type="button">{question}</button>)}</div>
      <p className="agent-note">リーチはテレビ端末数です。F1在籍予測はこのAgentの対象外です。</p>
    </section>
    <section className="chat-panel">
      <div className="chat-heading"><div><span>VIEWING_AGENT</span><small>{threadId ? `Thread ${threadId}` : "新しい会話"}</small></div><button onClick={resetConversation} type="button" aria-label="会話をリセット"><RotateCcw size={17}/></button></div>
      <div className="chat-messages">
        {messages.length===0 && <div className="chat-empty"><Bot size={36}/><strong>視聴実績について質問してください</strong><span>結果に応じて、回答、表、グラフを表示します。</span></div>}
        {messages.map((message,index)=><Message key={index} message={message}/>) }
        {pending && <div className="message assistant"><span className="avatar"><Bot size={17}/></span><div className="message-body thinking"><i/><i/><i/><span>分析計画を立て、Semantic Viewを問い合わせています。</span></div></div>}
        {error && <div className="chat-error">{error}</div>}
      </div>
      <form className="chat-composer" onSubmit={(event)=>{event.preventDefault();void sendQuestion(input)}}>
        <textarea value={input} onChange={(event)=>setInput(event.target.value)} placeholder="期間、放送局、指標を日本語で質問" maxLength={2000} rows={2}/>
        <button disabled={pending || !input.trim()} type="submit" aria-label="質問を送信"><Send size={18}/></button>
      </form>
    </section>
  </div>
}

function Message({ message }: { message: ChatMessage }) {
  if (message.role === "user") return <div className="message user"><span className="avatar"><User size={17}/></span><div className="message-body"><p>{message.text}</p></div></div>
  const content = message.response?.content ?? []
  return <div className="message assistant"><span className="avatar"><Bot size={17}/></span><div className="message-body agent-response">
    {content.filter((item)=>item.type!=="thinking" && item.type!=="tool_use" && item.type!=="tool_result").map((item,index)=><AgentContentBlock key={index} content={item}/>) }
    {message.response?.warnings?.map((warning,index)=><div className="agent-warning" key={`${warning.code}-${index}`}>{warning.message}</div>)}
    {content.every((item)=>!["text","table","chart"].includes(item.type)) && <p>Agentは応答を完了しましたが、表示可能な回答本文がありませんでした。</p>}
  </div></div>
}

function AgentContentBlock({ content }: { content: AgentContent }) {
  if (content.type === "text" && content.text) return <p className="agent-text">{content.text}</p>
  if (content.type === "chart" && content.chart?.chart_spec) {
    try {
      const spec = JSON.parse(content.chart.chart_spec)
      return <div className="agent-chart"><VegaEmbed spec={{ ...spec, width: "container", autosize: { type: "fit", contains: "padding" } }} options={{ actions: false }}/></div>
    } catch {
      return <div className="agent-warning">グラフ仕様を表示できませんでした。</div>
    }
  }
  if (content.type === "table" && content.table) return <AgentTable table={content.table}/>
  return null
}

function AgentTable({ table }: { table: unknown }) {
  const value = table as { title?: string; result_set?: { resultSetMetaData?: { rowType?: { name: string }[] }; data?: unknown[][] } }
  const columns = value.result_set?.resultSetMetaData?.rowType?.map((column)=>column.name) ?? []
  const rows = value.result_set?.data ?? []
  if (!columns.length) return null
  return <div className="agent-table"><strong>{value.title ?? "分析結果"}</strong><div className="data-table-wrap"><table className="data-table"><thead><tr>{columns.map((column)=><th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={index}>{row.map((cell,cellIndex)=><td key={cellIndex}>{String(cell ?? "-")}</td>)}</tr>)}</tbody></table></div></div>
}

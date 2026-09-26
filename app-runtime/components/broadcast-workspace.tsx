"use client"

import { useEffect, useMemo, useState } from "react"
import { BarChart3, Bot, Clock3, LayoutDashboard, RadioTower, RefreshCw, Sparkles } from "lucide-react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import { AgentWorkspace } from "@/components/agent-workspace"
import { Dashboard } from "@/components/dashboard"
import { NETWORKS, type DashboardView, type Network } from "@/lib/broadcast"

type WorkspaceMode = "dashboard" | "agent"

interface Bounds {
  DATE_MIN: string
  DATE_MAX: string
  MINUTE_DATE_MIN: string
  MINUTE_DATE_MAX: string
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  const data = await response.json()
  if (!response.ok) throw new Error(data.error ?? "データを取得できませんでした。")
  return data as T
}

export function BroadcastWorkspace() {
  const queryClient = useQueryClient()
  const [mode, setMode] = useState<WorkspaceMode>("dashboard")
  const [view, setView] = useState<DashboardView>("summary")
  const [networks, setNetworks] = useState<Network[]>([...NETWORKS])
  const [from, setFrom] = useState("")
  const [to, setTo] = useState("")
  const { data: bounds, error: boundsError, isLoading } = useQuery({
    queryKey: ["bounds"],
    queryFn: () => fetchJson<Bounds>("/api/dashboard/bounds"),
  })

  useEffect(() => {
    if (bounds && !from && !to) {
      setFrom(String(bounds.DATE_MIN).slice(0, 10))
      setTo(String(bounds.DATE_MAX).slice(0, 10))
    }
  }, [bounds, from, to])

  const queryString = useMemo(() => {
    const params = new URLSearchParams({ from, to, networks: networks.join(",") })
    return params.toString()
  }, [from, to, networks])

  function toggleNetwork(network: Network) {
    setNetworks((current) => current.includes(network)
      ? current.filter((candidate) => candidate !== network)
      : [...current, network].sort() as Network[])
  }

  return (
    <main className="workspace-shell">
      <aside className="control-rail">
        <div className="rail-heading">
          <span>ANALYSIS CONTROL</span>
          <h2>視聴条件</h2>
        </div>
        <div className="field-group">
          <label>視聴期間</label>
          <input type="date" min={String(bounds?.DATE_MIN ?? "").slice(0, 10)} max={String(bounds?.DATE_MAX ?? "").slice(0, 10)} value={from} onChange={(event) => setFrom(event.target.value)} />
          <input type="date" min={String(bounds?.DATE_MIN ?? "").slice(0, 10)} max={String(bounds?.DATE_MAX ?? "").slice(0, 10)} value={to} onChange={(event) => setTo(event.target.value)} />
        </div>
        <div className="field-group">
          <label>放送局</label>
          <div className="network-grid">
            {NETWORKS.map((network) => (
              <button
                className={networks.includes(network) ? "network-chip active" : "network-chip"}
                key={network}
                onClick={() => toggleNetwork(network)}
                type="button"
              >
                {network}
              </button>
            ))}
          </div>
        </div>
        <div className="field-group">
          <label>分析ビュー</label>
          {[
            ["summary", "経営サマリー", LayoutDashboard],
            ["trends", "視聴トレンド", BarChart3],
            ["predictions", "F1在籍予測", Sparkles],
            ["minute", "毎分パルス", Clock3],
          ].map(([value, label, Icon]) => (
            <button key={String(value)} className={view === value ? "view-button active" : "view-button"} onClick={() => { setMode("dashboard"); setView(value as DashboardView) }} type="button">
              <Icon size={17} />{String(label)}
            </button>
          ))}
        </div>
        <button className="refresh-button" onClick={() => queryClient.invalidateQueries()} type="button">
          <RefreshCw size={16} />データを再読み込み
        </button>
        <div className="rail-meta">
          <span>データ期間</span>
          <strong>{bounds ? `${String(bounds.DATE_MIN).slice(0, 10)} - ${String(bounds.DATE_MAX).slice(0, 10)}` : "取得中"}</strong>
          <small>すべて教材用の合成データです。</small>
        </div>
      </aside>

      <section className="workspace-main">
        <div className="mode-tabs" role="tablist">
          <button className={mode === "dashboard" ? "active" : ""} onClick={() => setMode("dashboard")} type="button"><LayoutDashboard size={17} />分析ダッシュボード</button>
          <button className={mode === "agent" ? "active" : ""} onClick={() => setMode("agent")} type="button"><Bot size={17} />VIEWING_AGENT</button>
        </div>

        <div className="hero-panel">
          <div>
            <p className="eyebrow"><RadioTower size={15} /> BROADCAST DATA PLATFORM</p>
            <h1>5局横断 視聴インテリジェンス</h1>
            <p>実績、コンテンツ傾向、毎分の動き、検証済みのF1在籍予測を分析し、同じ画面からVIEWING_AGENTへ質問できます。</p>
          </div>
          <div className="hero-badges"><span>{networks.length}局</span><span>{from || "-"} - {to || "-"}</span><span>{mode === "agent" ? "Agent" : "Dashboard"}</span></div>
        </div>

        {isLoading && <div className="state-panel">分析可能期間を取得しています。</div>}
        {boundsError && <div className="state-panel error">{boundsError.message}</div>}
        {!isLoading && !boundsError && networks.length === 0 && <div className="state-panel">放送局を1つ以上選んでください。</div>}
        {!isLoading && !boundsError && networks.length > 0 && from && to && mode === "dashboard" && (
          <Dashboard view={view} filters={{ from, to, networks }} queryString={queryString} bounds={bounds!} />
        )}
        {!isLoading && !boundsError && mode === "agent" && <AgentWorkspace />}
      </section>
    </main>
  )
}

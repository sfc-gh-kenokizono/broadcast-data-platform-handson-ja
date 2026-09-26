"use client"

import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import { Sparkles } from "lucide-react"
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
  Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts"
import type { DashboardFilters, DashboardView } from "@/lib/broadcast"
import { ChartTooltip, formatTick, getYAxisWidth } from "@/components/chart-utils"

const COLORS = ["#29b5e8", "#11567f", "#2eb88a", "#ffb020", "#e5484d", "#805ad5", "#d36b9a", "#73859a"]

interface DashboardProps {
  view: DashboardView
  filters: DashboardFilters
  queryString: string
  bounds: { MINUTE_DATE_MIN: string; MINUTE_DATE_MAX: string }
}

type Row = Record<string, string | number | null>

async function fetchData(url: string) {
  const response = await fetch(url)
  const body = await response.json()
  if (!response.ok) throw new Error(body.error ?? "データを取得できませんでした。")
  return body
}

function number(row: Row | undefined, key: string): number {
  return Number(row?.[key] ?? 0)
}

function formatNumber(value: number, digits = 0) {
  return value.toLocaleString("ja-JP", { maximumFractionDigits: digits })
}

function delta(current: number, previous: number) {
  if (!previous) return null
  const change = (current / previous - 1) * 100
  return `${change >= 0 ? "+" : ""}${change.toFixed(1)}% 前期間比`
}

function Metric({ label, value, subvalue }: { label: string; value: string; subvalue?: string | null }) {
  return <div className="metric"><span>{label}</span><strong>{value}</strong>{subvalue && <small>{subvalue}</small>}</div>
}

function Panel({ title, caption, children }: { title: string; caption?: string; children: React.ReactNode }) {
  return <section className="analysis-panel"><div className="panel-title"><h3>{title}</h3>{caption && <p>{caption}</p>}</div>{children}</section>
}

function ViewIntro({ kicker, title, description }: { kicker: string; title: string; description: string }) {
  return <div className="view-intro"><span>{kicker}</span><h2>{title}</h2><p>{description}</p></div>
}

function State({ loading, error, empty }: { loading: boolean; error: Error | null; empty?: boolean }) {
  if (loading) return <div className="state-panel">Snowflakeから分析データを取得しています。</div>
  if (error) return <div className="state-panel error">{error.message}</div>
  if (empty) return <div className="state-panel">この条件に該当するデータはありません。</div>
  return null
}

export function Dashboard(props: DashboardProps) {
  if (props.view === "summary") return <SummaryView {...props} />
  if (props.view === "trends") return <TrendsView {...props} />
  if (props.view === "predictions") return <PredictionsView {...props} />
  return <MinuteView {...props} />
}

function SummaryView({ queryString }: DashboardProps) {
  const { data, error, isLoading } = useQuery({ queryKey: ["summary", queryString], queryFn: () => fetchData(`/api/dashboard/summary?${queryString}`) })
  const summary = data?.summary as Row | undefined
  const previous = data?.previous as Row | undefined
  const daily = (data?.daily ?? []) as Row[]
  const network = (data?.network ?? []) as Row[]
  const avg = number(summary, "DISTINCT_REACH") ? number(summary, "TOTAL_MINUTES") / number(summary, "DISTINCT_REACH") : 0
  const previousAvg = number(previous, "DISTINCT_REACH") ? number(previous, "TOTAL_MINUTES") / number(previous, "DISTINCT_REACH") : 0
  if (isLoading || error || !summary) return <State loading={isLoading} error={error as Error | null} />
  return <>
    <ViewIntro kicker="EXECUTIVE OVERVIEW" title="視聴ポートフォリオの全体像" description="重複を除いた端末リーチと視聴量を、選択期間の直前にある同日数の期間と比較します。" />
    <div className="metric-grid">
      <Metric label="重複除外リーチ" value={`${formatNumber(number(summary, "DISTINCT_REACH"))}台`} subvalue={delta(number(summary, "DISTINCT_REACH"), number(previous, "DISTINCT_REACH"))} />
      <Metric label="総視聴時間" value={`${formatNumber(number(summary, "TOTAL_MINUTES") / 60, 1)}時間`} subvalue={delta(number(summary, "TOTAL_MINUTES"), number(previous, "TOTAL_MINUTES"))} />
      <Metric label="視聴区間" value={`${formatNumber(number(summary, "TOTAL_SESSIONS"))}回`} subvalue={delta(number(summary, "TOTAL_SESSIONS"), number(previous, "TOTAL_SESSIONS"))} />
      <Metric label="1台あたり視聴" value={`${formatNumber(avg, 1)}分`} subvalue={delta(avg, previousAvg)} />
    </div>
    <div className="definition-strip"><strong>重複除外リーチ</strong><span>同じテレビ端末が複数局を見ても、共通のDEVICE_IDで1台と数えます。人・世帯・視聴率ではありません。</span></div>
    <div className="dashboard-grid two-one">
      <Panel title="重複除外リーチの推移" caption="日別の重複なし端末数">
        <ResponsiveContainer width="100%" height={310}><LineChart data={daily}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="VIEW_DATE" tickFormatter={(value) => String(value).slice(5,10)}/><YAxis width={getYAxisWidth(daily, "DISTINCT_REACH")} tickFormatter={formatTick}/><Tooltip content={<ChartTooltip />}/><Line type="monotone" dataKey="DISTINCT_REACH" name="リーチ" stroke={COLORS[0]} strokeWidth={3} dot={false}/></LineChart></ResponsiveContainer>
      </Panel>
      <Panel title="総視聴時間の局別構成">
        <ResponsiveContainer width="100%" height={310}><PieChart><Pie data={network} dataKey="TOTAL_MINUTES" nameKey="NETWORK_ID" innerRadius={65} outerRadius={105}>{network.map((row, index) => <Cell key={String(row.NETWORK_ID)} fill={COLORS[index]}/>)}</Pie><Tooltip content={<ChartTooltip />}/><Legend/></PieChart></ResponsiveContainer>
      </Panel>
    </div>
    <Panel title="局別パフォーマンス"><DataTable rows={network} columns={["NETWORK_ID", "DISTINCT_REACH", "TOTAL_MINUTES", "TOTAL_SESSIONS"]}/></Panel>
  </>
}

function TrendsView({ queryString }: DashboardProps) {
  const { data, error, isLoading } = useQuery({ queryKey: ["trends", queryString], queryFn: () => fetchData(`/api/dashboard/trends?${queryString}`) })
  const daily = (data?.daily ?? []) as Row[]
  const network = (data?.network ?? []) as Row[]
  const genre = (data?.genre ?? []) as Row[]
  if (isLoading || error || daily.length === 0) return <State loading={isLoading} error={error as Error | null} empty={!isLoading && !error && daily.length === 0}/>
  return <>
    <ViewIntro kicker="AUDIENCE TREND" title="局とコンテンツの視聴傾向" description="日々の変化、局別パフォーマンス、ジャンル構成を同じ条件で比較します。" />
    <Panel title="日別の総視聴時間"><ResponsiveContainer width="100%" height={320}><AreaChart data={daily}><defs><linearGradient id="minutesArea" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor={COLORS[0]} stopOpacity={0.45}/><stop offset="95%" stopColor={COLORS[0]} stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="VIEW_DATE" tickFormatter={(value) => String(value).slice(5,10)}/><YAxis width={getYAxisWidth(daily, "TOTAL_MINUTES")} tickFormatter={formatTick}/><Tooltip content={<ChartTooltip />}/><Area type="monotone" dataKey="TOTAL_MINUTES" name="総視聴時間（分）" stroke={COLORS[0]} fill="url(#minutesArea)" strokeWidth={2}/></AreaChart></ResponsiveContainer></Panel>
    <div className="dashboard-grid halves">
      <Panel title="局別の視聴量"><ResponsiveContainer width="100%" height={320}><BarChart data={network} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tickFormatter={formatTick}/><YAxis type="category" dataKey="NETWORK_ID" width={55}/><Tooltip content={<ChartTooltip />}/><Bar dataKey="TOTAL_MINUTES" name="総視聴時間（分）" radius={[0,5,5,0]}>{network.map((row,index)=><Cell key={String(row.NETWORK_ID)} fill={COLORS[index]}/>)}</Bar></BarChart></ResponsiveContainer></Panel>
      <Panel title="ジャンル別の視聴量"><ResponsiveContainer width="100%" height={320}><BarChart data={genre} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tickFormatter={formatTick}/><YAxis type="category" dataKey="GENRE" width={75}/><Tooltip content={<ChartTooltip />}/><Bar dataKey="TOTAL_MINUTES" name="総視聴時間（分）" fill={COLORS[2]} radius={[0,5,5,0]}/></BarChart></ResponsiveContainer></Panel>
    </div>
    <Panel title="局 × ジャンルの視聴量"><DataTable rows={(data?.networkGenre ?? []) as Row[]} columns={["NETWORK_ID", "GENRE", "DISTINCT_REACH", "TOTAL_MINUTES", "TOTAL_SESSIONS"]}/></Panel>
  </>
}

function PredictionsView({ queryString }: DashboardProps) {
  const [enabled, setEnabled] = useState(false)
  const { data, error, isLoading } = useQuery({ queryKey: ["predictions", queryString], queryFn: () => fetchData(`/api/dashboard/predictions?${queryString}`), enabled })
  const rows = (data?.rows ?? []) as Row[]
  const counts = useMemo(() => {
    const grouped = new Map<number, number>()
    rows.forEach((row) => grouped.set(Number(row.PREDICTED_HAS_F1), (grouped.get(Number(row.PREDICTED_HAS_F1)) ?? 0) + Number(row.DEVICE_COUNT)))
    return [{ label: "F1在籍なし", value: grouped.get(0) ?? 0 }, { label: "F1在籍あり", value: grouped.get(1) ?? 0 }]
  }, [rows])
  const histogram = useMemo(() => Array.from({ length: 10 }, (_, bin) => ({ label: `${(bin/10).toFixed(1)}-${((bin+1)/10).toFixed(1)}`, value: rows.filter((row) => Number(row.PROBABILITY_BIN) === bin).reduce((sum,row)=>sum+Number(row.DEVICE_COUNT),0) })), [rows])
  return <>
    <ViewIntro kicker="MLOPS IN ACTION" title="検証済みモデルの予測を業務画面へ" description="20,000端末の完全性を確認した単一モデル版だけを表示します。期間・局は表示対象端末の絞り込みです。" />
    {!enabled && <div className="activation-panel"><Sparkles size={28}/><div><strong>予測スナップショットを読み込みますか</strong><p>オンにするまでML.PREDICTIONSへ問い合わせません。</p></div><button onClick={()=>setEnabled(true)} type="button">予測を表示</button></div>}
    {enabled && (isLoading || error) && (
      <State loading={isLoading} error={error as Error | null}/>
    )}
    {enabled && data?.health === null && <div className="state-panel">予測テーブルは空です。</div>}
    {enabled && data?.health && <>
      <div className="metric-grid"><Metric label="対象端末" value={`${formatNumber(counts.reduce((sum,item)=>sum+item.value,0))}台`}/><Metric label="F1在籍あり予測" value={`${formatNumber(counts[1].value)}台`}/><Metric label="保存閾値" value={Number(data.health.threshold).toFixed(2)}/><Metric label="モデル版" value={String(data.health.modelVersion)}/></div>
      <div className="dashboard-grid halves"><Panel title="予測ラベルの構成"><ResponsiveContainer width="100%" height={320}><PieChart><Pie data={counts} dataKey="value" nameKey="label" innerRadius={65} outerRadius={105}>{counts.map((item,index)=><Cell key={item.label} fill={[COLORS[1],COLORS[2]][index]}/>)}</Pie><Tooltip content={<ChartTooltip />}/><Legend/></PieChart></ResponsiveContainer></Panel><Panel title="予測確率の分布"><ResponsiveContainer width="100%" height={320}><BarChart data={histogram}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="label"/><YAxis tickFormatter={formatTick}/><Tooltip content={<ChartTooltip />}/><Bar dataKey="value" name="端末数" fill={COLORS[0]} radius={[4,4,0,0]}/></BarChart></ResponsiveContainer></Panel></div>
      <div className="definition-strip warning"><strong>教材用予測</strong><span>合成世帯へのF1在籍予測であり、実際の視聴者属性、実人数、全国推計ではありません。</span></div>
    </>}
  </>
}

function MinuteView({ filters, queryString, bounds }: DashboardProps) {
  const [date, setDate] = useState(String(bounds.MINUTE_DATE_MIN).slice(0,10))
  const [enabled, setEnabled] = useState(false)
  const { data, error, isLoading } = useQuery({ queryKey: ["minute", queryString, date], queryFn: () => fetchData(`/api/dashboard/minute?${queryString}&date=${date}`), enabled })
  const rows = (data?.rows ?? []) as Row[]
  const chartRows = useMemo(() => {
    const byTime = new Map<string, Row>()
    rows.forEach((row) => {
      const key = String(row.MINUTE_AT)
      byTime.set(key, { ...(byTime.get(key) ?? { MINUTE_AT: key }), [String(row.NETWORK_ID)]: Number(row.VIEWING_DEVICES) })
    })
    return [...byTime.values()]
  }, [rows])
  const peaks = useMemo(() => filters.networks.map((network) => rows.filter((row)=>row.NETWORK_ID===network).sort((a,b)=>Number(b.VIEWING_DEVICES)-Number(a.VIEWING_DEVICES))[0]).filter(Boolean), [rows, filters.networks])
  return <>
    <ViewIntro kicker="MINUTE-BY-MINUTE" title="放送局ごとの毎分パルス" description="その1分間に少しでも視聴した端末数を、欠損補間や局間合計をせずに表示します。" />
    <div className="inline-controls"><label>分析日<input type="date" min={String(bounds.MINUTE_DATE_MIN).slice(0,10)} max={String(bounds.MINUTE_DATE_MAX).slice(0,10)} value={date} onChange={(event)=>{setDate(event.target.value);setEnabled(false)}}/></label><button onClick={()=>setEnabled(true)} type="button">毎分系列を表示</button></div>
    {enabled && (isLoading || error || rows.length===0) && (
      <State loading={isLoading} error={error as Error | null} empty={!isLoading&&!error&&rows.length===0}/>
    )}
    {enabled && rows.length>0 && <><div className="metric-grid"><Metric label="全局中の最大値" value={`${formatNumber(Math.max(...rows.map((row)=>Number(row.VIEWING_DEVICES))))}台`}/><Metric label="ピーク局" value={String(peaks.sort((a,b)=>Number(b.VIEWING_DEVICES)-Number(a.VIEWING_DEVICES))[0]?.NETWORK_ID)}/><Metric label="分析日" value={date}/><Metric label="表示系列" value={`${filters.networks.length}局`}/></div><Panel title={`${date} の毎分視聴パルス`}><ResponsiveContainer width="100%" height={420}><LineChart data={chartRows}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="MINUTE_AT" tickFormatter={(value)=>new Date(String(value)).toLocaleTimeString("ja-JP",{hour:"2-digit",minute:"2-digit"})}/><YAxis tickFormatter={formatTick}/><Tooltip content={<ChartTooltip />}/><Legend/>{filters.networks.map((network,index)=><Line key={network} type="monotone" dataKey={network} stroke={COLORS[index]} strokeWidth={2} dot={false} connectNulls={false}/>)}</LineChart></ResponsiveContainer></Panel><Panel title="局別ピーク"><DataTable rows={peaks} columns={["NETWORK_ID","MINUTE_AT","VIEWING_DEVICES"]}/></Panel></>}
  </>
}

function DataTable({ rows, columns }: { rows: Row[]; columns: string[] }) {
  return <div className="data-table-wrap"><table className="data-table"><thead><tr>{columns.map((column)=><th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row,index)=><tr key={`${index}-${columns.map((column)=>row[column]).join("-")}`}>{columns.map((column)=><td key={column}>{typeof row[column] === "number" ? formatNumber(Number(row[column]),2) : String(row[column] ?? "-")}</td>)}</tr>)}</tbody></table></div>
}

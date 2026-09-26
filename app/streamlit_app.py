"""5局の視聴実績と検証済みF1在籍予測を横断分析するStreamlitアプリ。"""

from datetime import timedelta

import altair as alt
import pandas as pd
import streamlit as st
from snowflake.snowpark.exceptions import SnowparkSQLException, SnowparkSessionException

from queries import (
    BOUNDS_SQL,
    NETWORKS,
    PredictionValidationError,
    aggregate_query,
    minute_query,
    prediction_query,
    unavailable_object,
    validate_prediction_snapshot,
)


st.set_page_config(page_title="5局横断 視聴インテリジェンス", page_icon="❄", layout="wide")

FONT = "Inter, Hiragino Sans, Noto Sans JP, Yu Gothic, sans-serif"
SNOWFLAKE_BLUE = "#29B5E8"
DEEP_BLUE = "#11567F"
NAVY = "#172B4D"
TEAL = "#2EB88A"
AMBER = "#FFB020"
CORAL = "#E5484D"
NETWORK_COLORS = [SNOWFLAKE_BLUE, DEEP_BLUE, TEAL, AMBER, CORAL]

st.markdown(
    """
    <style>
    .block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1500px;}
    [data-testid="stSidebar"] {background: linear-gradient(180deg, #f3faff 0%, #ffffff 62%);}
    .hero {padding:1.35rem 1.6rem; border:1px solid #d7edf7; border-radius:16px;
      background:linear-gradient(115deg,#edf9fe 0%,#fff 58%,#f3f7ff 100%); margin-bottom:1rem;}
    .hero-kicker {color:#1687b8; font-size:.75rem; font-weight:700; letter-spacing:.12em;}
    .hero h1 {color:#172b4d; font-size:2rem; margin:.2rem 0 .35rem;}
    .hero p {color:#52677c; margin:0; max-width:980px; line-height:1.65;}
    .section-label {color:#1687b8; font-size:.73rem; font-weight:700; letter-spacing:.1em; margin-bottom:.15rem;}
    .insight {border-left:4px solid #29b5e8; background:#f5fbfe; border-radius:0 10px 10px 0;
      padding:.8rem 1rem; color:#304b62; margin:.45rem 0 1rem;}
    .tag {display:inline-block; padding:.18rem .5rem; border-radius:999px; background:#eaf7fc;
      color:#157da8; font-size:.72rem; font-weight:600; margin-right:.25rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def styled(chart):
    """全チャートへ共通の視認性設定を適用します。"""
    return (
        chart.configure_axis(
            labelFont=FONT, titleFont=FONT, labelColor="#52677c", titleColor=NAVY,
            gridColor="#edf2f6", domainColor="#d8e1e8", labelFontSize=11, titleFontSize=12,
        )
        .configure_legend(labelFont=FONT, titleFont=FONT, labelColor="#40566d", titleColor=NAVY, orient="bottom")
        .configure_title(font=FONT, fontSize=15, color=NAVY, anchor="start")
        .configure_view(strokeWidth=0)
    )


def section_header(kicker, title, caption):
    st.markdown(f'<div class="section-label">{kicker}</div>', unsafe_allow_html=True)
    st.subheader(title)
    st.caption(caption)


def metric_delta(current, previous):
    if previous in (None, 0) or pd.isna(previous):
        return "比較期間なし"
    return f"{(current / previous - 1) * 100:+.1f}% 前期間比"


def to_hours(minutes):
    return f"{float(minutes) / 60:,.1f}時間"


@st.cache_data(ttl=60, max_entries=128, show_spinner=False)
def query(sql, params=()):
    """SQLとバインド値をSnowflakeへ渡し、結果をpandasの表で返します。"""
    connection = st.connection("snowflake")
    return connection.session().sql(sql, params=list(params)).to_pandas()


def load_aggregate(group, start_date, end_date, networks):
    return query(*aggregate_query(group, start_date, end_date, networks))


if st.sidebar.button("再読み込み"):
    query.clear()
    st.rerun()

try:
    bounds = query(BOUNDS_SQL).iloc[0]
except SnowparkSessionException:
    st.error("Snowflakeとの接続が切れました。アプリを再起動して再接続してください。")
    st.stop()
except SnowparkSQLException:
    st.error("COMMON.VIEWING_DAILYを取得できません。第2章の共通マートと権限を確認してください。")
    st.stop()

if pd.isna(bounds["DATE_MIN"]) or pd.isna(bounds["DATE_MAX"]):
    st.info("COMMON.VIEWING_DAILYは空です。共通マート作成後に再読み込みしてください。")
    st.stop()

date_min = pd.Timestamp(bounds["DATE_MIN"]).date()
date_max = pd.Timestamp(bounds["DATE_MAX"]).date()
minute_date_min = pd.Timestamp(bounds["MINUTE_DATE_MIN"]).date()
minute_date_max = pd.Timestamp(bounds["MINUTE_DATE_MAX"]).date()

with st.sidebar:
    st.markdown("## :material/tune: 分析条件")
    selected_networks = st.multiselect("放送局", NETWORKS, default=list(NETWORKS))
    selected_dates = st.date_input(
        "視聴期間", value=(date_min, date_max), min_value=date_min, max_value=date_max,
        key="viewing_dates",
    )
    st.markdown("---")
    st.markdown("**分析ビュー**")
    view = st.selectbox(
        "表示する分析",
        ["経営サマリー", "視聴トレンド", "F1在籍予測", "毎分パルス"],
        label_visibility="collapsed",
    )
    st.caption(f"データ期間  {date_min:%Y/%m/%d} - {date_max:%Y/%m/%d}")
    st.caption("結果キャッシュ  60秒")

if not selected_networks:
    st.info("放送局を1つ以上選んでください。")
    st.stop()
if len(selected_dates) != 2:
    st.info("開始日と終了日を選んでください。")
    st.stop()

date_from, date_to = selected_dates
if date_from > date_to:
    st.warning("開始日は終了日以前にしてください。")
    st.stop()

st.markdown(
    """
    <div class="hero">
      <div class="hero-kicker">BROADCAST DATA PLATFORM</div>
      <h1>5局横断 視聴インテリジェンス</h1>
      <p>局ごとの視聴区間を共通マートへ統合し、実績、コンテンツ傾向、毎分の動き、検証済みのF1在籍予測を同じ画面で分析します。集計はSnowflake、表示と対話はStreamlitが担当します。</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    f'<span class="tag">{len(selected_networks)}局</span>'
    f'<span class="tag">{date_from:%Y/%m/%d} - {date_to:%Y/%m/%d}</span>'
    f'<span class="tag">{view}</span>',
    unsafe_allow_html=True,
)

try:
    if view == "経営サマリー":
        section_header(
            "EXECUTIVE OVERVIEW",
            "視聴ポートフォリオの全体像",
            "5局重複除外リーチは、選択した局のどれかを1回以上見たテレビ端末を、局をまたいで重複除外した台数です。",
        )
        summary = load_aggregate("summary", date_from, date_to, selected_networks).iloc[0]
        period_days = (date_to - date_from).days + 1
        previous_to = date_from - timedelta(days=1)
        previous_from = previous_to - timedelta(days=period_days - 1)
        has_previous = previous_from >= date_min
        previous = load_aggregate("summary", previous_from, previous_to, selected_networks).iloc[0] if has_previous else None

        if summary["DISTINCT_REACH"] == 0:
            st.info("この期間・放送局に視聴データはありません。")
        else:
            avg_minutes = summary["TOTAL_MINUTES"] / summary["DISTINCT_REACH"]
            previous_avg = previous["TOTAL_MINUTES"] / previous["DISTINCT_REACH"] if previous is not None and previous["DISTINCT_REACH"] else None
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("重複除外リーチ", f"{int(summary['DISTINCT_REACH']):,}台", metric_delta(summary["DISTINCT_REACH"], previous["DISTINCT_REACH"] if previous is not None else None))
            k2.metric("総視聴時間", to_hours(summary["TOTAL_MINUTES"]), metric_delta(summary["TOTAL_MINUTES"], previous["TOTAL_MINUTES"] if previous is not None else None))
            k3.metric("視聴区間", f"{int(summary['TOTAL_SESSIONS']):,}回", metric_delta(summary["TOTAL_SESSIONS"], previous["TOTAL_SESSIONS"] if previous is not None else None))
            k4.metric("1台あたり視聴", f"{avg_minutes:,.1f}分", metric_delta(avg_minutes, previous_avg))

            st.markdown(
                '<div class="insight"><b>5局重複除外リーチとは</b><br>'
                '例: 同じテレビ端末がNW01とNW02を見た場合、各局のリーチではそれぞれ1台なので単純合計は2台です。'
                '5局重複除外リーチでは端末IDで名寄せして1台と数えます。人・世帯・視聴率ではなく、教材上のテレビ端末数です。</div>',
                unsafe_allow_html=True,
            )
            daily = load_aggregate("daily", date_from, date_to, selected_networks)
            network = load_aggregate("network", date_from, date_to, selected_networks)
            daily["VIEW_DATE"] = pd.to_datetime(daily["VIEW_DATE"])
            daily = daily.set_index("VIEW_DATE").reindex(pd.date_range(date_from, date_to)).rename_axis("VIEW_DATE").reset_index()
            daily["REACH_7D"] = daily["DISTINCT_REACH"].rolling(7, min_periods=7).mean()
            trend = daily.melt("VIEW_DATE", ["DISTINCT_REACH", "REACH_7D"], "SERIES", "VALUE")
            trend["SERIES"] = trend["SERIES"].map({"DISTINCT_REACH": "日次", "REACH_7D": "7日移動平均"})

            left, right = st.columns([1.6, 1])
            with left:
                with st.container(border=True):
                    chart = alt.Chart(trend).mark_line(strokeWidth=2.4).encode(
                        x=alt.X("VIEW_DATE:T", title=None),
                        y=alt.Y("VALUE:Q", title="リーチ（台）", scale=alt.Scale(zero=False)),
                        color=alt.Color("SERIES:N", title=None, scale=alt.Scale(range=[SNOWFLAKE_BLUE, NAVY])),
                        strokeDash=alt.StrokeDash("SERIES:N", title=None),
                        tooltip=[alt.Tooltip("VIEW_DATE:T", title="日付"), alt.Tooltip("SERIES:N", title="系列"), alt.Tooltip("VALUE:Q", title="台数", format=",.0f")],
                    ).properties(height=320, title="5局重複除外リーチの推移")
                    st.altair_chart(styled(chart), use_container_width=True)
            with right:
                with st.container(border=True):
                    share = alt.Chart(network).mark_arc(innerRadius=58, outerRadius=105).encode(
                        theta=alt.Theta("TOTAL_MINUTES:Q"),
                        color=alt.Color("NETWORK_ID:N", title="局", scale=alt.Scale(range=NETWORK_COLORS)),
                        tooltip=[alt.Tooltip("NETWORK_ID:N", title="局"), alt.Tooltip("TOTAL_MINUTES:Q", title="視聴分", format=",.0f")],
                    ).properties(height=320, title="総視聴時間の局別構成")
                    st.altair_chart(styled(share), use_container_width=True)

            with st.container(border=True):
                st.markdown("**局別パフォーマンス**")
                st.dataframe(network.rename(columns={
                    "NETWORK_ID": "放送局", "DISTINCT_REACH": "リーチ（端末）",
                    "TOTAL_MINUTES": "総視聴時間（分）", "TOTAL_SESSIONS": "総視聴回数",
                }), hide_index=True, use_container_width=True)

    elif view == "視聴トレンド":
        section_header("AUDIENCE TREND", "局とコンテンツの視聴傾向", "日々の変化、局別パフォーマンス、ジャンル構成を同じ条件で比較します。")
        daily = load_aggregate("daily", date_from, date_to, selected_networks)
        network = load_aggregate("network", date_from, date_to, selected_networks)
        genre = load_aggregate("genre", date_from, date_to, selected_networks)
        network_genre = load_aggregate("network_genre", date_from, date_to, selected_networks)
        if daily.empty:
            st.info("この期間・放送局に視聴データはありません。")
        else:
            daily["VIEW_DATE"] = pd.to_datetime(daily["VIEW_DATE"])
            with st.container(border=True):
                chart = alt.Chart(daily).mark_area(
                    line={"color": SNOWFLAKE_BLUE, "strokeWidth": 2}, color=SNOWFLAKE_BLUE, opacity=.2
                ).encode(
                    x=alt.X("VIEW_DATE:T", title=None),
                    y=alt.Y("TOTAL_MINUTES:Q", title="総視聴時間（分）", scale=alt.Scale(zero=False)),
                    tooltip=[alt.Tooltip("VIEW_DATE:T", title="日付"), alt.Tooltip("TOTAL_MINUTES:Q", title="視聴分", format=",.1f")],
                ).properties(height=330, title="日別の総視聴時間")
                st.altair_chart(styled(chart), use_container_width=True)

            c1, c2 = st.columns(2)
            with c1:
                with st.container(border=True):
                    bars = alt.Chart(network).mark_bar(cornerRadiusEnd=4).encode(
                        x=alt.X("TOTAL_MINUTES:Q", title="総視聴時間（分）"),
                        y=alt.Y("NETWORK_ID:N", title=None, sort="-x"),
                        color=alt.Color("NETWORK_ID:N", title="局", scale=alt.Scale(range=NETWORK_COLORS)),
                        tooltip=[alt.Tooltip("NETWORK_ID:N", title="局"), alt.Tooltip("DISTINCT_REACH:Q", title="リーチ", format=",.0f"), alt.Tooltip("TOTAL_MINUTES:Q", title="視聴分", format=",.1f")],
                    ).properties(height=330, title="局別の視聴量")
                    st.altair_chart(styled(bars), use_container_width=True)
            with c2:
                with st.container(border=True):
                    genre_chart = alt.Chart(genre).mark_bar(color=TEAL, cornerRadiusEnd=4).encode(
                        x=alt.X("TOTAL_MINUTES:Q", title="総視聴時間（分）"),
                        y=alt.Y("GENRE:N", title=None, sort="-x"),
                        tooltip=[alt.Tooltip("GENRE:N", title="ジャンル"), alt.Tooltip("DISTINCT_REACH:Q", title="リーチ", format=",.0f"), alt.Tooltip("TOTAL_MINUTES:Q", title="視聴分", format=",.1f")],
                    ).properties(height=330, title="ジャンル別の視聴量")
                    st.altair_chart(styled(genre_chart), use_container_width=True)

            with st.container(border=True):
                heat = alt.Chart(network_genre).mark_rect(cornerRadius=3).encode(
                    x=alt.X("GENRE:N", title="ジャンル"),
                    y=alt.Y("NETWORK_ID:N", title="放送局"),
                    color=alt.Color("TOTAL_MINUTES:Q", title="視聴分", scale=alt.Scale(scheme="blues")),
                    tooltip=[alt.Tooltip("NETWORK_ID:N", title="局"), alt.Tooltip("GENRE:N", title="ジャンル"), alt.Tooltip("DISTINCT_REACH:Q", title="リーチ", format=",.0f"), alt.Tooltip("TOTAL_MINUTES:Q", title="視聴分", format=",.1f")],
                ).properties(height=280, title="局 × ジャンルの視聴ヒートマップ")
                st.altair_chart(styled(heat), use_container_width=True)
            st.caption("全区間を視聴開始日と開始時ジャンルへ計上する教材用集計です。番組ごとの厳密な視聴時間ではありません。")

    elif view == "F1在籍予測":
        section_header("MLOPS IN ACTION", "検証済みモデルの予測を業務画面へ", "第3章で評価・登録・推論した単一モデル版だけを、全件検証後に表示します。")
        st.caption("F1は20〜34歳の女性です。表示するのはテレビに対応する合成世帯へのF1在籍予測で、現在の視聴者属性や実人数ではありません。")
        if not st.checkbox("予測結果を表示", value=False):
            st.info("チェックを入れるまでML.PREDICTIONSへ問い合わせません。視聴実績だけを使う場合はオフのままで構いません。")
        else:
            result = query(*prediction_query(date_from, date_to, selected_networks))
            threshold, predictions = validate_prediction_snapshot(result)
            if threshold is None:
                st.info("予測テーブルは空です。第3章のモデル登録・推論完了後に再読み込みしてください。")
            elif predictions.empty:
                st.info("この期間・放送局に視聴データはありません。")
            else:
                counts = predictions.groupby("PREDICTION_GROUP")["DEVICE_COUNT"].sum()
                model_version = result.iloc[0]["HEALTH_MODEL_VERSION"]
                positive = int(counts.get("F1在籍あり（予測1）", 0))
                negative = int(counts.get("F1在籍なし（予測0）", 0))
                total = positive + negative
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("対象端末", f"{total:,}台")
                m2.metric("F1在籍あり予測", f"{positive:,}台", f"{positive / total:.1%}" if total else None)
                m3.metric("保存閾値", f"{threshold:.2f}")
                m4.metric("モデル版", str(model_version))

                left, right = st.columns(2)
                count_frame = counts.rename_axis("PREDICTION_GROUP").reset_index(name="DEVICE_COUNT")
                with left:
                    with st.container(border=True):
                        donut = alt.Chart(count_frame).mark_arc(innerRadius=65, outerRadius=110).encode(
                            theta=alt.Theta("DEVICE_COUNT:Q"),
                            color=alt.Color("PREDICTION_GROUP:N", title="予測", scale=alt.Scale(range=[TEAL, DEEP_BLUE])),
                            tooltip=[alt.Tooltip("PREDICTION_GROUP:N", title="予測"), alt.Tooltip("DEVICE_COUNT:Q", title="端末数", format=",.0f")],
                        ).properties(height=350, title="予測ラベルの構成")
                        st.altair_chart(styled(donut), use_container_width=True)

                histogram = predictions.dropna(subset=["PROBABILITY_BIN"]).groupby("PROBABILITY_BIN")["DEVICE_COUNT"].sum().reindex(range(10), fill_value=0).reset_index()
                histogram["BIN_LABEL"] = histogram["PROBABILITY_BIN"].map(lambda bucket: f"{bucket / 10:.1f}–{(bucket + 1) / 10:.1f}")
                with right:
                    with st.container(border=True):
                        hist_chart = alt.Chart(histogram).mark_bar(color=SNOWFLAKE_BLUE, cornerRadiusTopLeft=3, cornerRadiusTopRight=3).encode(
                            x=alt.X("BIN_LABEL:N", title="F1在籍確率", sort=list(histogram["BIN_LABEL"])),
                            y=alt.Y("DEVICE_COUNT:Q", title="端末数"),
                            tooltip=[alt.Tooltip("BIN_LABEL:N", title="確率帯"), alt.Tooltip("DEVICE_COUNT:Q", title="端末数", format=",.0f")],
                        ).properties(height=350, title="予測確率の分布")
                        st.altair_chart(styled(hist_chart), use_container_width=True)

                st.markdown(
                    '<div class="insight"><b>MLOpsから業務利用までを同じ基盤で接続</b><br>'
                    'Notebookで評価したモデル、Model Registryの版、保存した閾値、推論結果をSnowflake内で管理し、Streamlitは検証済みスナップショットだけを表示します。</div>',
                    unsafe_allow_html=True,
                )
                st.warning("合成データで学習した教材用予測です。現実の世帯の確率・精度・人数を保証せず、正解ラベルは表示しません。")

    else:
        section_header("MINUTE-BY-MINUTE", "放送局ごとの毎分パルス", "その1分間に少しでも視聴した端末数を、欠損補間や局間合計をせずに表示します。")
        minute_default = min(max(date_from, minute_date_min), minute_date_max)
        minute_date = st.date_input(
            "分析日", value=minute_default, min_value=minute_date_min, max_value=minute_date_max,
            key="minute_date",
        )
        if not st.checkbox("分別曲線を表示", value=False):
            st.info("日付を選び、チェックを入れると毎分マートを取得します。")
        else:
            minute_data = query(*minute_query(minute_date, selected_networks))
            if minute_data.empty:
                st.info("この日・放送局に分別の視聴データはありません。")
            else:
                minute_data["MINUTE_AT"] = pd.to_datetime(minute_data["MINUTE_AT"])
                peaks = minute_data.loc[minute_data.groupby("NETWORK_ID")["VIEWING_DEVICES"].idxmax()].copy()
                p1, p2, p3 = st.columns(3)
                top_peak = peaks.loc[peaks["VIEWING_DEVICES"].idxmax()]
                p1.metric("全局中の最大値", f"{int(top_peak['VIEWING_DEVICES']):,}台")
                p2.metric("ピーク局", top_peak["NETWORK_ID"])
                p3.metric("ピーク時刻", pd.Timestamp(top_peak["MINUTE_AT"]).strftime("%H:%M"))
                with st.container(border=True):
                    lines = alt.Chart(minute_data).mark_line(strokeWidth=1.8).encode(
                        x=alt.X("MINUTE_AT:T", title="時刻", axis=alt.Axis(format="%H:%M")),
                        y=alt.Y("VIEWING_DEVICES:Q", title="分内視聴端末数", scale=alt.Scale(zero=False)),
                        color=alt.Color("NETWORK_ID:N", title="局", scale=alt.Scale(range=NETWORK_COLORS)),
                        tooltip=[alt.Tooltip("MINUTE_AT:T", title="時刻", format="%H:%M"), alt.Tooltip("NETWORK_ID:N", title="局"), alt.Tooltip("VIEWING_DEVICES:Q", title="台数", format=",.0f")],
                    ).properties(height=430, title=f"{minute_date:%Y/%m/%d} の毎分視聴パルス")
                    st.altair_chart(styled(lines), use_container_width=True)
                with st.container(border=True):
                    st.markdown("**局別ピーク**")
                    peak_display = peaks[["NETWORK_ID", "MINUTE_AT", "VIEWING_DEVICES"]].sort_values("VIEWING_DEVICES", ascending=False).rename(columns={"NETWORK_ID": "放送局", "MINUTE_AT": "ピーク時刻", "VIEWING_DEVICES": "ピーク端末数"})
                    st.dataframe(peak_display, hide_index=True, use_container_width=True)
                st.caption("分内視聴端末数は同時視聴者数ではありません。局別の値を足して全局リーチにはせず、欠損もゼロ補完・補間しません。")

except SnowparkSessionException:
    st.error("Snowflakeとの接続が切れました。表示済みの値は更新されていません。アプリを再起動してください。")
except SnowparkSQLException as error:
    if unavailable_object(error):
        st.info("必要な共通マートまたは予測テーブルが未作成、または参照権限がありません。第2章・第3章と所有者権限を確認してください。")
    else:
        st.error("分析データの取得に失敗しました。列定義、権限、ウェアハウスを確認してください。")
except PredictionValidationError as error:
    st.error(str(error))
except (ValueError, TypeError, KeyError, OverflowError):
    st.error("取得結果の形式が不正です。第2章・第3章の出力と列定義を確認してください。")

st.markdown("---")
st.caption("Data: BCAST_PLATFORM_HANDSON.COMMON / ML  |  Compute: BCAST_PLATFORM_COMMON_WH  |  すべて教材用の合成データです。")
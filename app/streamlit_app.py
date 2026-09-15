import pandas as pd
import streamlit as st
from snowflake.snowpark.exceptions import SnowparkSQLException

from queries import (
    BOUNDS_SQL,
    NETWORKS,
    PREDICTION_HEALTH_SQL,
    aggregate_query,
    prediction_query,
    unavailable_object,
)


st.set_page_config(page_title="5局の視聴データ", layout="wide")
st.title("5局の視聴データ")
st.caption("合成データによる教材です。リーチの単位は端末であり、実在の人数・世帯数ではありません。")


@st.cache_data(ttl=60, max_entries=64, show_spinner=False)
def query(sql, params=()):
    connection = st.connection("snowflake")
    return connection.session().sql(sql, params=list(params)).to_pandas()


if st.sidebar.button("再読込"):
    query.clear()

try:
    bounds = query(BOUNDS_SQL).iloc[0]
except SnowparkSQLException:
    st.error("COMMON.VIEWING_DAILY を取得できません。dbt の共通マート作成とアプリ実行ロールの権限を確認してください。")
    st.stop()

if pd.isna(bounds["DATE_MIN"]) or pd.isna(bounds["DATE_MAX"]):
    st.info("COMMON.VIEWING_DAILY は空です。共通マート作成後に再読込してください。")
    st.stop()

date_min = pd.Timestamp(bounds["DATE_MIN"]).date()
date_max = pd.Timestamp(bounds["DATE_MAX"]).date()
with st.sidebar:
    selected_networks = st.multiselect("放送局", NETWORKS, default=list(NETWORKS))
    selected_dates = st.date_input(
        "視聴期間", value=(date_min, date_max), min_value=date_min, max_value=date_max
    )

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

st.caption(f"視聴期間: {date_from} ～ {date_to} ／ 放送局: {', '.join(selected_networks)}")
counts_tab, predictions_tab = st.tabs(["視聴実績・推移", "スポーツ関心の予測"])

with counts_tab:
    try:
        summary = query(*aggregate_query("summary", date_from, date_to, selected_networks)).iloc[0]
        if summary["DISTINCT_REACH"] == 0:
            st.info("この期間・放送局に視聴データはありません。")
        else:
            reach_column, minutes_column, sessions_column = st.columns(3)
            reach_column.metric("期間全体のリーチ（端末）", f"{int(summary['DISTINCT_REACH']):,}")
            minutes_column.metric("総視聴時間（分）", f"{float(summary['TOTAL_MINUTES']):,.1f}")
            sessions_column.metric("総視聴回数", f"{int(summary['TOTAL_SESSIONS']):,}")
            daily = query(*aggregate_query("daily", date_from, date_to, selected_networks))
            daily["VIEW_DATE"] = pd.to_datetime(daily["VIEW_DATE"])
            daily = daily.set_index("VIEW_DATE").reindex(pd.date_range(date_from, date_to))
            daily.index.name = "視聴日"
            st.subheader("日別リーチ（選択局の重複を除く）")
            st.line_chart(daily[["DISTINCT_REACH"]].rename(columns={"DISTINCT_REACH": "端末数"}))
            st.caption("日別・局別・ジャンル別のリーチを足しても、期間全体のリーチにはなりません。欠損日の線は補間しません。")
            st.subheader("日別の総視聴時間（分）")
            st.line_chart(daily[["TOTAL_MINUTES"]].rename(columns={"TOTAL_MINUTES": "視聴時間（分）"}))
            for group, label in (("network", "放送局"), ("genre", "ジャンル")):
                breakdown = query(*aggregate_query(group, date_from, date_to, selected_networks))
                st.subheader(f"{label}別")
                st.dataframe(breakdown.rename(columns={
                    "NETWORK_ID": "放送局", "GENRE": "ジャンル",
                    "DISTINCT_REACH": "リーチ（端末）", "TOTAL_MINUTES": "総視聴時間（分）",
                    "TOTAL_SESSIONS": "総視聴回数",
                }), hide_index=True)
    except SnowparkSQLException:
        st.error("視聴実績の集計に失敗しました。共通マートの列・権限・ウェアハウスを確認してください。")

with predictions_tab:
    st.caption("合成の二値スポーツ関心ラベルを学習した予測クラスです。確率・実測属性・性年代ではありません。")
    st.caption("視聴期間・局は対象端末を絞ります。予測そのものの学習期間や予測日時を絞る操作ではありません。")
    if st.checkbox("予測結果を表示", value=False):
        try:
            health = query(PREDICTION_HEALTH_SQL).iloc[0]
            if health["ROW_COUNT"] == 0:
                st.info("予測テーブルは空です。第3章のモデル登録・推論完了後に再読込してください。")
            elif health["ROW_COUNT"] != health["DEVICE_COUNT"] or health["INVALID_COUNT"]:
                st.error("予測データに重複端末・欠損・不正なクラスがあります。第3章の出力を確認してください。")
            else:
                predictions = query(*prediction_query(date_from, date_to, selected_networks))
                if predictions.empty:
                    st.info("この期間・放送局に視聴データはありません。")
                else:
                    counts = predictions.groupby("PREDICTION_GROUP")["DEVICE_COUNT"].sum()
                    st.bar_chart(counts.rename("端末数"))
                    st.dataframe(predictions.rename(columns={
                        "PREDICTION_GROUP": "予測クラス", "DEVICE_COUNT": "端末数",
                        "MODEL_NAME": "モデル", "MODEL_VERSION": "バージョン",
                        "FIRST_PREDICTED_AT": "最初の予測日時", "LAST_PREDICTED_AT": "最後の予測日時",
                    }), hide_index=True)
                    st.caption("予測なしも含む対象端末数です。モデルとバージョンごとの内訳を示しています。")
        except SnowparkSQLException as error:
            if unavailable_object(error):
                st.info("ML.PREDICTIONS が未作成、または参照権限がありません。第3章と ML スキーマの権限を確認してください。視聴実績はそのまま利用できます。")
            else:
                st.error("予測結果の取得に失敗しました。未作成とは限りません。列定義・権限・ウェアハウスを確認してください。視聴実績はそのまま利用できます。")
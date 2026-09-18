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
except SnowparkSessionException:
    st.error("Snowflakeとの接続が切れました。アプリを再起動して再接続してください。解消しない場合は講師へ確認してください。")
    st.stop()
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
        "視聴期間", value=(date_min, date_max), min_value=date_min, max_value=date_max,
        key="viewing_dates",
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
counts_tab, predictions_tab, minute_tab = st.tabs(["視聴実績・推移", "F1同居の予測", "分内視聴端末数"])

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
    except SnowparkSessionException:
        st.error("Snowflakeとの接続が切れました。表示済みの値は更新されていません。アプリを再起動して再接続してください。")
    except SnowparkSQLException:
        st.error("視聴実績の集計に失敗しました。共通マートの列・権限・ウェアハウスを確認してください。")

with predictions_tab:
    st.caption("F1は20〜34歳の女性です。テレビに対応する合成世帯のF1同居を予測します。予測ラベルは、モデルとともに保存した閾値以上を1とします。")
    st.caption("いま見ている人の属性、実際のF1視聴者数、人数、確認済みの世帯数ではありません。確率の合計もこれらの数にはなりません。")
    st.caption("教師が学習可能な傾向を設計した合成データです。現実の世帯の同居確率・予測精度を保証しません。確率が十分に校正されているとは限らず、0・1は予測ラベルであり、正解ラベルは表示しません。")
    st.caption("視聴期間・局は対象端末を絞ります。予測そのものの学習期間や予測日時を絞る操作ではありません。")
    st.caption("教材の対象は2026-05-01〜2026-07-31、全20,000端末です。予測はF1_SIGNAL_V2のみを表示し、検証と分布を同じSQL結果から取得します（キャッシュ最大60秒）。")
    if st.checkbox("予測結果を表示", value=False):
        try:
            result = query(*prediction_query(date_from, date_to, selected_networks))
            threshold, predictions = validate_prediction_snapshot(result)
            if threshold is None:
                st.info("予測テーブルは空です。第3章のモデル登録・推論完了後に再読込してください。")
            else:
                st.caption(
                    f"保存閾値: {threshold!r}（以上を予測1） ／ "
                    f"モデル: TV_F1_PRESENCE_MODEL {result.iloc[0]['HEALTH_MODEL_VERSION']} ／ "
                    "データセット: F1_SIGNAL_V2"
                )
                if predictions.empty:
                    st.info("この期間・放送局に視聴データはありません。")
                else:
                    counts = predictions.groupby("PREDICTION_GROUP")["DEVICE_COUNT"].sum()
                    st.subheader("予測ラベル別の端末数")
                    st.bar_chart(counts.rename("端末数"))
                    histogram = predictions.dropna(subset=["PROBABILITY_BIN"]).groupby(
                        "PROBABILITY_BIN"
                    )["DEVICE_COUNT"].sum().reindex(range(10), fill_value=0)
                    histogram.index = [
                        f"{bucket / 10:.1f}以上 {(bucket + 1) / 10:.1f}{'以下' if bucket == 9 else '未満'}"
                        for bucket in range(10)
                    ]
                    histogram.index.name = "F1同居確率"
                    st.subheader("F1同居確率の分布")
                    st.bar_chart(histogram.rename("端末数"))
                    st.caption("選択期間・局の対象端末を0.1刻みで数えています。最後の区間には確率1.0も含みます。")
                    prediction_counts = predictions.groupby(
                        ["PREDICTION_GROUP", "MODEL_NAME", "MODEL_VERSION"], dropna=False
                    ).agg(
                        DEVICE_COUNT=("DEVICE_COUNT", "sum"),
                        FIRST_PREDICTED_AT=("FIRST_PREDICTED_AT", "min"),
                        LAST_PREDICTED_AT=("LAST_PREDICTED_AT", "max"),
                    ).reset_index()
                    st.dataframe(prediction_counts.rename(columns={
                        "PREDICTION_GROUP": "予測クラス", "DEVICE_COUNT": "端末数",
                        "MODEL_NAME": "モデル", "MODEL_VERSION": "バージョン",
                        "FIRST_PREDICTED_AT": "最初の保存日時（UTC）", "LAST_PREDICTED_AT": "最後の保存日時（UTC）",
                    }), hide_index=True)
                    st.caption("全件検証済みの単一モデルバージョンによる対象端末数です。日時は推論開始時刻ではなく、結果を保存したUTC時刻です。")
        except SnowparkSessionException:
            st.error("予測結果を取得する接続が切れました。アプリを再起動して再接続してください。表示済みの実績は更新されていません。")
        except SnowparkSQLException as error:
            if unavailable_object(error):
                st.info("ML.PREDICTIONS が未作成、または参照権限がありません。第3章と ML スキーマの権限を確認してください。視聴実績はそのまま利用できます。")
            else:
                st.error("予測結果の取得に失敗しました。未作成とは限りません。旧形式の場合は第3章でPREDICTION_THRESHOLD・DATASET_VERSIONを含む予測を再作成してください。列定義・権限・ウェアハウスも確認してください。ゼロ件としては扱いません。視聴実績はそのまま利用できます。")
        except PredictionValidationError as error:
            st.error(str(error))
        except (ValueError, TypeError, KeyError, OverflowError):
            st.error("予測の検証結果の形式が不正です。第3章の出力・列定義を確認してください。予測は表示しません。")

with minute_tab:
    minute_date = st.date_input(
        "分別曲線の視聴日", value=date_from, min_value=date_min, max_value=date_max,
        key="minute_date",
    )
    st.caption("選んだ1日と放送局の分内視聴端末数です。上の視聴期間とは別に、この日付を使います。")
    st.caption("その1分間に少しでも視聴した端末を局ごとに数えます。同じ瞬間の視聴端末数ではありません。局別の値を足しても、局をまたぐ正確なリーチにはなりません。")
    if st.checkbox("分別曲線を表示", value=False):
        try:
            minute_data = query(*minute_query(minute_date, selected_networks))
            if minute_data.empty:
                st.info("この日・放送局に分別の視聴データはありません。")
            else:
                minute_data["MINUTE_AT"] = pd.to_datetime(minute_data["MINUTE_AT"])
                curves = minute_data.pivot(
                    index="MINUTE_AT", columns="NETWORK_ID", values="VIEWING_DEVICES"
                ).reindex(
                    index=pd.date_range(minute_date, periods=1440, freq="min"),
                    columns=selected_networks,
                )
                curves.index.name = "視聴時刻（1分単位）"
                st.line_chart(curves)
                st.caption("全5局を選ぶと5本の系列です。欠損はゼロ埋め・補間せず、合計線も作りません。")
        except SnowparkSessionException:
            st.error("分別曲線を取得する接続が切れました。アプリを再起動して再接続してください。")
        except SnowparkSQLException as error:
            if unavailable_object(error):
                st.info("COMMON.MINUTE_AUDIENCE が未作成、または参照権限がありません。第2章の共通マートと所有者の権限を確認してください。")
            else:
                st.error("分別曲線の取得に失敗しました。列定義・権限・ウェアハウスを確認してください。未作成やゼロ件とは限りません。")
        except ValueError:
            st.error("分別データの時刻または局・分の一意性を確認してください。分別曲線の表示を停止しました。")
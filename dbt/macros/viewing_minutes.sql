{# 整形済みの各区間を、開始を含み終了を含まない範囲と重なる1分ごとの行へ展開します。
   日付は各分の時刻から決めるため、日付をまたぐ区間は翌日の行も生成します。 #}
{% macro viewing_minutes(clean_relation) %}
select
    clean.EVENT_ID,
    clean.NETWORK_ID,
    clean.DEVICE_ID,
    dateadd('minute', minute_offset.VALUE::integer, date_trunc('minute', clean.VIEW_FROM)) as MINUTE_AT,
    to_date(MINUTE_AT) as VIEW_DATE
from {{ clean_relation }} as clean,
lateral flatten(input => array_generate_range(
    0,
    datediff('minute', date_trunc('minute', clean.VIEW_FROM), date_trunc('minute', clean.VIEW_TO))
      + iff(clean.VIEW_TO = date_trunc('minute', clean.VIEW_TO), 0, 1)
)) as minute_offset
{% endmacro %}

{# 分展開済みの行から、局・日・分ごとに端末IDを重複除外して数えます。秒単位の同時視聴数や人数ではありません。 #}
{% macro minute_audience(minutes_relation) %}
select NETWORK_ID, VIEW_DATE, MINUTE_AT,
       count(distinct DEVICE_ID)::integer as VIEWING_DEVICES
from {{ minutes_relation }}
group by NETWORK_ID, VIEW_DATE, MINUTE_AT
{% endmacro %}
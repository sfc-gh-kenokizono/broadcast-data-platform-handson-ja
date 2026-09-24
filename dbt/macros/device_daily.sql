{# 整形済みログを受け取り、局・端末・開始日・ジャンルごとの視聴回数と時間を返します。
   日付をまたぐ区間も全時間を開始日に計上します。番組の境界で分割した視聴時間ではありません。 #}
{% macro device_daily(clean_relation) %}
select
    NETWORK_ID,
    DEVICE_ID,
    to_date(VIEW_FROM) as VIEW_DATE,
    GENRE,
    count(*)::integer as SESSION_COUNT,
    sum(VIEW_MINUTES)::float as VIEW_MINUTES
from {{ clean_relation }}
group by NETWORK_ID, DEVICE_ID, to_date(VIEW_FROM), GENRE
{% endmacro %}
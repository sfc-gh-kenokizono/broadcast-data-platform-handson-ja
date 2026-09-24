{# 作成済みの5局の分別マートを縦につなぎ、局・日・分ごとの視聴端末数を共通マートにします。
   元ログや展開途中の行は統合しません。局別端末数の合計は、局をまたぐ重複除外済みリーチではありません。 #}
{{ config(alias='MINUTE_AUDIENCE') }}

{% for station in ['nw01', 'nw02', 'nw03', 'nw04', 'nw05'] %}
select NETWORK_ID, VIEW_DATE, MINUTE_AT, VIEWING_DEVICES
from {{ ref('mart_minute_audience_' ~ station) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
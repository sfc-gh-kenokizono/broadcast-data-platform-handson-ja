{{ config(alias='MINUTE_AUDIENCE') }}

{% for station in ['nw01', 'nw02', 'nw03', 'nw04', 'nw05'] %}
select NETWORK_ID, VIEW_DATE, MINUTE_AT, VIEWING_DEVICES
from {{ ref('mart_minute_audience_' ~ station) }}
{% if not loop.last %}union all{% endif %}
{% endfor %}
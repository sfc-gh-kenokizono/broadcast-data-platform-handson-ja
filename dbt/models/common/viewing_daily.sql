{# 作成済みの5局の日次マートを縦につなぎ、局・端末・開始日・ジャンル別の共通マートにします。
   局ごとの行を保つため、局をまたぐリーチは利用時に端末IDの重複を除いて数えます。 #}
{{ config(alias='VIEWING_DAILY') }}

select NETWORK_ID, DEVICE_ID, VIEW_DATE, GENRE, SESSION_COUNT, VIEW_MINUTES
from {{ ref('mart_device_daily_nw01') }}
union all
select NETWORK_ID, DEVICE_ID, VIEW_DATE, GENRE, SESSION_COUNT, VIEW_MINUTES
from {{ ref('mart_device_daily_nw02') }}
union all
select NETWORK_ID, DEVICE_ID, VIEW_DATE, GENRE, SESSION_COUNT, VIEW_MINUTES
from {{ ref('mart_device_daily_nw03') }}
union all
select NETWORK_ID, DEVICE_ID, VIEW_DATE, GENRE, SESSION_COUNT, VIEW_MINUTES
from {{ ref('mart_device_daily_nw04') }}
union all
select NETWORK_ID, DEVICE_ID, VIEW_DATE, GENRE, SESSION_COUNT, VIEW_MINUTES
from {{ ref('mart_device_daily_nw05') }}
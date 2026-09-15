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
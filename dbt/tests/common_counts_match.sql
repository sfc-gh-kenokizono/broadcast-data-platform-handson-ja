{{ config(tags=['common']) }}

with expected as (
    select 'NW01' as NETWORK_ID, count(*) as ROW_COUNT
    from {{ ref('mart_device_daily_nw01') }}
    union all
    select 'NW02', count(*) from {{ ref('mart_device_daily_nw02') }}
    union all
    select 'NW03', count(*) from {{ ref('mart_device_daily_nw03') }}
    union all
    select 'NW04', count(*) from {{ ref('mart_device_daily_nw04') }}
    union all
    select 'NW05', count(*) from {{ ref('mart_device_daily_nw05') }}
), actual as (
    select NETWORK_ID, count(*) as ROW_COUNT
    from {{ ref('viewing_daily') }}
    group by NETWORK_ID
)
select
    coalesce(expected.NETWORK_ID, actual.NETWORK_ID) as NETWORK_ID,
    expected.ROW_COUNT as EXPECTED_ROWS,
    coalesce(actual.ROW_COUNT, 0) as ACTUAL_ROWS
from expected
full outer join actual on expected.NETWORK_ID = actual.NETWORK_ID
where expected.ROW_COUNT is null
   or expected.ROW_COUNT != coalesce(actual.ROW_COUNT, 0)
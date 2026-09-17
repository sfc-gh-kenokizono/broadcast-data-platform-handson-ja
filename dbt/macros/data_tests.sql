{% test unique_grain(model, columns) %}
select {{ columns | join(', ') }}, count(*) as ROW_COUNT
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% test not_null_columns(model, columns) %}
select *
from {{ model }}
where
{% for column in columns %}
    {{ column }} is null{% if not loop.last %} or{% endif %}
{% endfor %}
{% endtest %}

{% macro invalid_intervals(clean_relation) %}
select EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, VIEW_MINUTES
from {{ clean_relation }}
where VIEW_TO <= VIEW_FROM
   or datediff('nanosecond', VIEW_FROM, VIEW_TO) > 86400000000000
   or VIEW_MINUTES <= 0
   or abs(VIEW_MINUTES - datediff('nanosecond', VIEW_FROM, VIEW_TO) / 60000000000.0) > 0.000000001
   or VIEW_FROM is null
   or VIEW_TO is null
   or VIEW_MINUTES is null
{% endmacro %}

{% test synthetic_device_id(model, column_name) %}
select {{ column_name }}
from {{ model }}
where {{ column_name }} is null
   or not regexp_like({{ column_name }}, 'C[0-9]{6}')
   or try_to_number(substr({{ column_name }}, 2)) not between 1 and 20000
{% endtest %}

{% macro station_volume_matches(raw_relation, clean_relation, daily_relation) %}
with raw_valid as (
    select distinct EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE
    from {{ raw_relation }}
    where VIEW_TO > VIEW_FROM
      and datediff('nanosecond', VIEW_FROM, VIEW_TO) <= 86400000000000
), expected as (
    select count(*) as SESSIONS,
           coalesce(sum(datediff('nanosecond', VIEW_FROM, VIEW_TO) / 60000000000.0), 0) as MINUTES
    from raw_valid
), clean as (
    select count(*) as SESSIONS, coalesce(sum(VIEW_MINUTES), 0) as MINUTES
    from {{ clean_relation }}
), daily as (
    select coalesce(sum(SESSION_COUNT), 0) as SESSIONS, coalesce(sum(VIEW_MINUTES), 0) as MINUTES
    from {{ daily_relation }}
), expected_daily as (
    select NETWORK_ID, DEVICE_ID, to_date(VIEW_FROM) as VIEW_DATE, GENRE,
           count(*) as SESSIONS, sum(VIEW_MINUTES) as MINUTES
    from {{ clean_relation }}
    group by NETWORK_ID, DEVICE_ID, to_date(VIEW_FROM), GENRE
), daily_differences as (
    select expected_daily.DEVICE_ID
    from expected_daily full outer join {{ daily_relation }} as actual_daily
      on expected_daily.NETWORK_ID = actual_daily.NETWORK_ID
     and expected_daily.DEVICE_ID = actual_daily.DEVICE_ID
     and expected_daily.VIEW_DATE = actual_daily.VIEW_DATE
     and expected_daily.GENRE = actual_daily.GENRE
    where expected_daily.DEVICE_ID is null or actual_daily.DEVICE_ID is null
       or expected_daily.SESSIONS != actual_daily.SESSION_COUNT
       or abs(expected_daily.MINUTES - actual_daily.VIEW_MINUTES) > greatest(0.000001, abs(expected_daily.MINUTES) * 0.000000001)
)
select expected.SESSIONS as EXPECTED_SESSIONS, clean.SESSIONS as CLEAN_SESSIONS,
       daily.SESSIONS as DAILY_SESSIONS, expected.MINUTES as EXPECTED_MINUTES,
       clean.MINUTES as CLEAN_MINUTES, daily.MINUTES as DAILY_MINUTES
from expected cross join clean cross join daily
where expected.SESSIONS = 0
   or expected.SESSIONS != clean.SESSIONS
   or clean.SESSIONS != daily.SESSIONS
   or abs(expected.MINUTES - clean.MINUTES) > greatest(0.000001, abs(expected.MINUTES) * 0.000000001)
   or abs(clean.MINUTES - daily.MINUTES) > greatest(0.000001, abs(clean.MINUTES) * 0.000000001)
   or exists (select 1 from daily_differences)
{% endmacro %}

{% macro minute_expansion_matches(clean_relation, minutes_relation) %}
with expected as (
    select EVENT_ID, NETWORK_ID, DEVICE_ID,
           date_trunc('minute', VIEW_FROM) as FIRST_MINUTE,
           date_trunc('minute', dateadd('nanosecond', -1, VIEW_TO)) as LAST_MINUTE,
           datediff('minute', FIRST_MINUTE, LAST_MINUTE) + 1 as EXPECTED_MINUTES
    from {{ clean_relation }}
), actual as (
    select EVENT_ID, NETWORK_ID, DEVICE_ID, count(*) as ACTUAL_MINUTES,
           count(distinct MINUTE_AT) as DISTINCT_MINUTES,
           min(MINUTE_AT) as FIRST_MINUTE, max(MINUTE_AT) as LAST_MINUTE,
           count_if(MINUTE_AT is null or MINUTE_AT != date_trunc('minute', MINUTE_AT)
                    or VIEW_DATE is null or VIEW_DATE != to_date(MINUTE_AT)) as INVALID_BUCKETS
    from {{ minutes_relation }}
    group by EVENT_ID, NETWORK_ID, DEVICE_ID
)
select expected.EVENT_ID as EXPECTED_EVENT, actual.EVENT_ID as ACTUAL_EVENT,
       expected.EXPECTED_MINUTES, actual.ACTUAL_MINUTES, actual.DISTINCT_MINUTES
from expected full outer join actual
  on expected.EVENT_ID = actual.EVENT_ID
 and expected.NETWORK_ID = actual.NETWORK_ID and expected.DEVICE_ID = actual.DEVICE_ID
where expected.EVENT_ID is null or actual.EVENT_ID is null
   or expected.EXPECTED_MINUTES != actual.ACTUAL_MINUTES
   or actual.ACTUAL_MINUTES != actual.DISTINCT_MINUTES
   or expected.FIRST_MINUTE != actual.FIRST_MINUTE
   or expected.LAST_MINUTE != actual.LAST_MINUTE
   or actual.INVALID_BUCKETS > 0
{% endmacro %}

{% macro minute_audience_matches(minutes_relation, audience_relation) %}
with expected as (
    select NETWORK_ID, VIEW_DATE, MINUTE_AT, count(distinct DEVICE_ID) as VIEWING_DEVICES
    from {{ minutes_relation }} group by NETWORK_ID, VIEW_DATE, MINUTE_AT
), actual as (
    select NETWORK_ID, VIEW_DATE, MINUTE_AT, VIEWING_DEVICES from {{ audience_relation }}
)
select coalesce(expected.NETWORK_ID, actual.NETWORK_ID) as NETWORK_ID,
       coalesce(expected.MINUTE_AT, actual.MINUTE_AT) as MINUTE_AT,
       expected.VIEWING_DEVICES as EXPECTED_DEVICES, actual.VIEWING_DEVICES as ACTUAL_DEVICES
from expected full outer join actual
  on expected.NETWORK_ID = actual.NETWORK_ID
 and expected.VIEW_DATE = actual.VIEW_DATE and expected.MINUTE_AT = actual.MINUTE_AT
where expected.NETWORK_ID is null or actual.NETWORK_ID is null
   or expected.VIEWING_DEVICES != actual.VIEWING_DEVICES
{% endmacro %}

{% macro common_totals_match(kind) %}
{% set daily = kind == 'daily' %}
with expected as (
    {% for station in ['nw01', 'nw02', 'nw03', 'nw04', 'nw05'] %}
    select '{{ station | upper }}' as NETWORK_ID, count(*) as ROW_COUNT,
           {% if daily %}
           coalesce(sum(SESSION_COUNT), 0) as TOTAL_COUNT, coalesce(sum(VIEW_MINUTES), 0) as TOTAL_MINUTES
           {% else %}
           coalesce(sum(VIEWING_DEVICES), 0) as TOTAL_COUNT, 0 as TOTAL_MINUTES
           {% endif %}
    from {{ ref(('mart_device_daily_' if daily else 'mart_minute_audience_') ~ station) }}
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
), actual as (
    select NETWORK_ID, count(*) as ROW_COUNT,
           {% if daily %}
           coalesce(sum(SESSION_COUNT), 0) as TOTAL_COUNT, coalesce(sum(VIEW_MINUTES), 0) as TOTAL_MINUTES
           {% else %}
           coalesce(sum(VIEWING_DEVICES), 0) as TOTAL_COUNT, 0 as TOTAL_MINUTES
           {% endif %}
    from {{ ref('viewing_daily' if daily else 'minute_audience') }}
    group by NETWORK_ID
)
select coalesce(expected.NETWORK_ID, actual.NETWORK_ID) as NETWORK_ID,
       expected.ROW_COUNT as EXPECTED_ROWS, actual.ROW_COUNT as ACTUAL_ROWS,
       expected.TOTAL_COUNT as EXPECTED_COUNT, actual.TOTAL_COUNT as ACTUAL_COUNT,
       expected.TOTAL_MINUTES as EXPECTED_MINUTES, actual.TOTAL_MINUTES as ACTUAL_MINUTES
from expected full outer join actual on expected.NETWORK_ID = actual.NETWORK_ID
where expected.NETWORK_ID is null or actual.NETWORK_ID is null
   or expected.ROW_COUNT = 0 or expected.ROW_COUNT != actual.ROW_COUNT
   or expected.TOTAL_COUNT != actual.TOTAL_COUNT
   or abs(expected.TOTAL_MINUTES - actual.TOTAL_MINUTES) > greatest(0.000001, abs(expected.TOTAL_MINUTES) * 0.000000001)
{% endmacro %}
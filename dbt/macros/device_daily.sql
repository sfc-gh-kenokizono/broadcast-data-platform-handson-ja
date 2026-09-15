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
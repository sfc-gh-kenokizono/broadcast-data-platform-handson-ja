{% macro clean_viewing(raw_relation) %}
with normalized as (
    select
        EVENT_ID,
        NETWORK_ID,
        DEVICE_ID,
        VIEW_FROM,
        VIEW_TO,
        upper(trim(GENRE, ' 　')) as GENRE_KEY
    from {{ raw_relation }}
)
select
    EVENT_ID,
    NETWORK_ID,
    DEVICE_ID,
    VIEW_FROM,
    VIEW_TO,
    case GENRE_KEY
        when 'ＮＥＷＳ' then 'NEWS'
        when 'ＤＲＡＭＡ' then 'DRAMA'
        when 'ＶＡＲＩＥＴＹ' then 'VARIETY'
        when 'ＡＮＩＭＥ' then 'ANIME'
        when 'ＳＰＯＲＴＳ' then 'SPORTS'
        else GENRE_KEY
    end as GENRE,
    (datediff('millisecond', VIEW_FROM, VIEW_TO) / 60000.0)::float as VIEW_MINUTES
from normalized
{% endmacro %}
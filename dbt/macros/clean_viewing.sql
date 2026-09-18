{% macro clean_viewing(raw_relation) %}
with deduplicated as (
    select distinct EVENT_ID, NETWORK_ID, DEVICE_ID, VIEW_FROM, VIEW_TO, GENRE
    from {{ raw_relation }}
    where VIEW_TO > VIEW_FROM
      and datediff('nanosecond', VIEW_FROM, VIEW_TO) <= 86400000000000
), normalized as (
    select
        EVENT_ID,
        NETWORK_ID,
        DEVICE_ID,
        VIEW_FROM,
        VIEW_TO,
        upper(trim(GENRE, ' \t\r\n　')) as GENRE_KEY
    from deduplicated
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
        when 'ＭＵＳＩＣ' then 'MUSIC'
        when 'ＭＯＶＩＥ' then 'MOVIE'
        when 'ＩＮＦＯ' then 'INFO'
        else GENRE_KEY
    end as GENRE,
    datediff('nanosecond', VIEW_FROM, VIEW_TO)::float / 60000000000.0 as VIEW_MINUTES
from normalized
{% endmacro %}
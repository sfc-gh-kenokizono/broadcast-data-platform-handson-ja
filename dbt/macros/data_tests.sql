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
   or VIEW_MINUTES <= 0
   or VIEW_FROM is null
   or VIEW_TO is null
   or VIEW_MINUTES is null
{% endmacro %}
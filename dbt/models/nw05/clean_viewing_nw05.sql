{{ config(alias='CLEAN_VIEWING') }}
{{ clean_viewing(source('raw', 'VIEWING_LOG_NW05')) }}
{# NW01の元ログから完全重複と不正な視聴区間を除き、ジャンル表記・視聴時間（分）を整えます。 #}
{{ config(alias='CLEAN_VIEWING') }}
{{ clean_viewing(source('raw', 'VIEWING_LOG_NW01')) }}
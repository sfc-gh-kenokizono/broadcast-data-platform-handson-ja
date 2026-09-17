{{ config(tags=['nw02']) }}
{{ minute_expansion_matches(ref('clean_viewing_nw02'), ref('viewing_minutes_nw02')) }}
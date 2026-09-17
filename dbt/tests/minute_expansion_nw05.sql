{{ config(tags=['nw05']) }}
{{ minute_expansion_matches(ref('clean_viewing_nw05'), ref('viewing_minutes_nw05')) }}
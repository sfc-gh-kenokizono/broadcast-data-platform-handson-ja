{{ config(tags=['nw04']) }}
{{ minute_expansion_matches(ref('clean_viewing_nw04'), ref('viewing_minutes_nw04')) }}
{{ config(tags=['nw01']) }}
{{ minute_expansion_matches(ref('clean_viewing_nw01'), ref('viewing_minutes_nw01')) }}
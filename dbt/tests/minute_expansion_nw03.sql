{{ config(tags=['nw03']) }}
{{ minute_expansion_matches(ref('clean_viewing_nw03'), ref('viewing_minutes_nw03')) }}
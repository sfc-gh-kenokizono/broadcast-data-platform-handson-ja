{{ config(tags=['nw03']) }}
{{ minute_audience_matches(ref('viewing_minutes_nw03'), ref('mart_minute_audience_nw03')) }}
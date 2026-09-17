{{ config(tags=['nw05']) }}
{{ minute_audience_matches(ref('viewing_minutes_nw05'), ref('mart_minute_audience_nw05')) }}
{{ config(tags=['nw04']) }}
{{ minute_audience_matches(ref('viewing_minutes_nw04'), ref('mart_minute_audience_nw04')) }}
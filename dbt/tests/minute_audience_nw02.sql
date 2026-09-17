{{ config(tags=['nw02']) }}
{{ minute_audience_matches(ref('viewing_minutes_nw02'), ref('mart_minute_audience_nw02')) }}
{{ config(tags=['nw01']) }}
{{ minute_audience_matches(ref('viewing_minutes_nw01'), ref('mart_minute_audience_nw01')) }}
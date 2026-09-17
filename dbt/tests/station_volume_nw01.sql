{{ config(tags=['nw01']) }}
{{ station_volume_matches(source('raw', 'VIEWING_LOG_NW01'), ref('clean_viewing_nw01'), ref('mart_device_daily_nw01')) }}
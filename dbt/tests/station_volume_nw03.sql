{{ config(tags=['nw03']) }}
{{ station_volume_matches(source('raw', 'VIEWING_LOG_NW03'), ref('clean_viewing_nw03'), ref('mart_device_daily_nw03')) }}
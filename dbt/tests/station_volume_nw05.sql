{{ config(tags=['nw05']) }}
{{ station_volume_matches(source('raw', 'VIEWING_LOG_NW05'), ref('clean_viewing_nw05'), ref('mart_device_daily_nw05')) }}
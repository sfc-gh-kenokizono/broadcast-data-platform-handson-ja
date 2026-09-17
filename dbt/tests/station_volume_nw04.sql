{{ config(tags=['nw04']) }}
{{ station_volume_matches(source('raw', 'VIEWING_LOG_NW04'), ref('clean_viewing_nw04'), ref('mart_device_daily_nw04')) }}
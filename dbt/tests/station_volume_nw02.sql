{{ config(tags=['nw02']) }}
{{ station_volume_matches(source('raw', 'VIEWING_LOG_NW02'), ref('clean_viewing_nw02'), ref('mart_device_daily_nw02')) }}
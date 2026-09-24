{# NW02の有効な元ログ・整形後・日次集計を照合し、空の入力や回数・時間の不一致があれば比較結果を返します。0行ならPASSです。 #}
{{ config(tags=['nw02']) }}
{{ station_volume_matches(source('raw', 'VIEWING_LOG_NW02'), ref('clean_viewing_nw02'), ref('mart_device_daily_nw02')) }}
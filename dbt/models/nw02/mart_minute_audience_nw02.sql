{# NW02の分ごとの視聴行から、同じ分の端末重複を除いて数えます。人数や同一瞬間の視聴数ではありません。 #}
{{ config(alias='MART_MINUTE_AUDIENCE') }}
{{ minute_audience(ref('viewing_minutes_nw02')) }}
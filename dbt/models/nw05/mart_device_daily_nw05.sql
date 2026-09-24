{# NW05の整形済みログを端末・開始日・ジャンル別に集計し、視聴回数と合計時間（分）を作ります。 #}
{{ config(alias='MART_DEVICE_DAILY') }}
{{ device_daily(ref('clean_viewing_nw05')) }}
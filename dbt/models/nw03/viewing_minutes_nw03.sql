{# NW03の整形済み視聴区間を、少しでも重なる1分ごとの行へ展開します。終了時刻は区間に含めません。 #}
{{ config(alias='VIEWING_MINUTES') }}
{{ viewing_minutes(ref('clean_viewing_nw03')) }}
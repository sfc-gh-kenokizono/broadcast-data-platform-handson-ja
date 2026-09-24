{# 5局の日次マートと共通マートを局別に照合し、行数・視聴回数・時間の不一致や空の局などを返します。0行ならPASSです。 #}
{{ config(tags=['common']) }}
{{ common_totals_match('daily') }}
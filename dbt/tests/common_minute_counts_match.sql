{# 5局の分別マートと共通マートを局別に照合し、行数・延べ端末数の不一致や不正な日時などを返します。0行ならPASSです。 #}
{{ config(tags=['common']) }}
{{ common_totals_match('minute') }}
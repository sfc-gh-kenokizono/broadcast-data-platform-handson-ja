{# NW03の整形済みログで、欠損・長さが不正な区間・視聴分数の不一致を返します。結果が0行ならPASSです。 #}
{{ config(tags=['nw03']) }}
{{ invalid_intervals(ref('clean_viewing_nw03')) }}
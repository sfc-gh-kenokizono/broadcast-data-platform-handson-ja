{# NW01の整形済み区間と分展開を照合し、イベントごとの行数・端末・時刻範囲などの不一致を返します。0行ならPASSです。 #}
{{ config(tags=['nw01']) }}
{{ minute_expansion_matches(ref('clean_viewing_nw01'), ref('viewing_minutes_nw01')) }}
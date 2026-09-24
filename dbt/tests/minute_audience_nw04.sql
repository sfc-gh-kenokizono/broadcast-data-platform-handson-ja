{# NW04の分展開から端末を重複除外して数え直し、分別マートと件数・日時が合わない行を返します。0行ならPASSです。 #}
{{ config(tags=['nw04']) }}
{{ minute_audience_matches(ref('viewing_minutes_nw04'), ref('mart_minute_audience_nw04')) }}
{# モデルの保存先スキーマ名を決めます。指定があればその名前をそのまま使い、なければtarget.schemaを使います。
   NW01などにtargetの接頭辞を付けないための命名処理であり、アクセス権限を制限する処理ではありません。 #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
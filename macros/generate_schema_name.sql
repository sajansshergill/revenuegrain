{#-
  Use the custom schema name verbatim instead of prefixing it with the
  target schema. Keeps mart schemas clean (core / finance / customer_success)
  across dev, ci, and prod targets.
-#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
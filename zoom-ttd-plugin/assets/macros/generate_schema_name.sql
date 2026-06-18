{#
    Custom schema naming for the Slim-CI scratch-schema pattern.

    - In a PR CI run, the workflow sets DBT_PR_SCHEMA=PR_<number>. Each model's
      configured +schema (bronze/silver/gold) is then prefixed with it, so a PR
      builds into PR_42_BRONZE / PR_42_SILVER / PR_42_GOLD -- isolated and
      droppable on merge/close.
    - On main (DBT_PR_SCHEMA unset), models build into the ZOOM_* production
      schemas: ZOOM_BRONZE / ZOOM_SILVER / ZOOM_GOLD.
#}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set pr = env_var('DBT_PR_SCHEMA', '') | trim -%}

    {%- if pr != '' -%}
        {%- if custom_schema_name is none -%}
            {{ pr | trim | upper }}
        {%- else -%}
            {{ (pr ~ '_' ~ custom_schema_name) | trim | upper }}
        {%- endif -%}
    {%- elif custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ ('ZOOM_' ~ custom_schema_name) | trim | upper }}
    {%- endif -%}
{%- endmacro %}

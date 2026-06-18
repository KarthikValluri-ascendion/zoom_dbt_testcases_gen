{#
    drop_pr_schemas  --  Slim-CI teardown

    Drops the per-PR scratch schemas after a pull request is merged or closed.
    Invoked from the teardown workflow:

        dbt run-operation drop_pr_schemas --args '{pr: PR_42}'
#}

{% macro drop_pr_schemas(pr) %}
    {%- if not execute -%}{{ return('') }}{%- endif -%}
    {%- set pr_clean = pr | trim | upper -%}
    {%- if pr_clean == '' -%}
        {{ exceptions.raise_compiler_error("drop_pr_schemas: `pr` arg is required, e.g. --args '{pr: PR_42}'") }}
    {%- endif -%}
    {%- for layer in ['BRONZE', 'SILVER', 'GOLD'] -%}
        {%- set sch = pr_clean ~ '_' ~ layer -%}
        {{ log("zoom-ttd: dropping schema " ~ target.database ~ "." ~ sch, info=true) }}
        {%- do run_query("drop schema if exists " ~ target.database ~ "." ~ sch ~ " cascade") -%}
    {%- endfor -%}
{% endmacro %}

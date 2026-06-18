{#
    ttd_intercept_coverage  --  the COVERAGE GATE (interceptor)

    Wired to dbt's `on-run-start` hook. BEFORE any model materializes, this macro
    walks the compiled graph and ABORTS the run if any in-scope model has zero
    tests (generic/schema, singular, OR native unit test).

    Why on-run-START (fail fast)? We do not want to spend Snowflake credits
    building models that ship without a single test. The gate fails the run
    immediately, so a pull request turns red before anything is built.

    Controls (dbt vars):
      - ttd_enforce          (default true)  -> set false to bypass the gate
      - ttd_exempt_prefixes  (default [])    -> model-name prefixes to skip (e.g. ['brz_'])
#}

{% macro ttd_intercept_coverage() %}
    {#-- run only at execute time (skips `dbt parse`) --#}
    {%- if not execute -%}{{ return('') }}{%- endif -%}

    {%- if not var('ttd_enforce', true) -%}
        {{ log("zoom-ttd: coverage gate BYPASSED (ttd_enforce=false)", info=true) }}
        {{ return('') }}
    {%- endif -%}

    {%- set exempt = var('ttd_exempt_prefixes', []) -%}

    {#-- 1. the COVERED set: every model unique_id that at least one test depends on --#}
    {%- set covered = [] -%}
    {%- for node in graph.nodes.values() -%}
        {%- if node.resource_type in ['test', 'unit_test'] -%}
            {%- for dep in node.depends_on.nodes -%}
                {%- if dep.startswith('model.') and dep not in covered -%}
                    {%- do covered.append(dep) -%}
                {%- endif -%}
            {%- endfor -%}
        {%- endif -%}
    {%- endfor -%}

    {#-- 2. in-scope models that are NOT covered (honoring exempt prefixes) --#}
    {%- set uncovered = [] -%}
    {%- for uid, node in graph.nodes.items() -%}
        {%- if node.resource_type == 'model' -%}
            {#-- namespace() so the flag survives the inner loop (Jinja scoping) --#}
            {%- set ns = namespace(is_exempt=false) -%}
            {%- for p in exempt -%}
                {%- if node.name.startswith(p) -%}{%- set ns.is_exempt = true -%}{%- endif -%}
            {%- endfor -%}
            {%- if (not ns.is_exempt) and (uid not in covered) -%}
                {%- do uncovered.append(node.name) -%}
            {%- endif -%}
        {%- endif -%}
    {%- endfor -%}

    {#-- 3. fail fast if anything is uncovered --#}
    {%- if uncovered | length > 0 -%}
        {%- set lines = [] -%}
        {%- for m in uncovered | sort -%}{%- do lines.append('  - ' ~ m) -%}{%- endfor -%}
        {%- set banner -%}
================================================================================
>>> TTD COVERAGE GATE FAILED  (zoom-ttd interceptor)
================================================================================
The following model(s) have NO tests (schema, singular, or unit) and may not be
deployed. Every model must ship with at least one test.

{{ lines | join('\n') }}

Fix options:
  * run  /zoom-ttd:build   (auto-scaffold functional + unit tests), or
  * add tests by hand, or
  * bypass for a local experiment with  --vars 'ttd_enforce: false'
================================================================================
        {%- endset -%}
        {{ exceptions.raise_compiler_error(banner) }}
    {%- else -%}
        {{ log("zoom-ttd: coverage gate PASSED -- every in-scope model has at least one test.", info=true) }}
    {%- endif -%}
{% endmacro %}

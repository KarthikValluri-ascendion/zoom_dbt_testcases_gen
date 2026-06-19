# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A runnable demo of **Test-Then-Deploy (TTD)** for dbt + Snowflake: a coverage gate that blocks
any untested model from building/merging, plus GitHub Actions **Slim CI with deferral** so PRs
build only changed models into an ephemeral schema. It has two halves that must stay in sync:

1. A **Zoom-themed medallion dbt project** (root of this repo).
2. The **`zoom-ttd` Claude Code plugin** (`zoom-ttd-plugin/`) that enforces, grades, and
   auto-generates tests for that project.

`fct_meetings` is the intentional fixture: it ships with **no hand-written tests** so the gate
catches it. Its tests live only in generated `_ttd_stub__fct_meetings.yml` / `_ttd_unit__fct_meetings.yml`
files, which `demo-reset` strips to return to the RED state. **Do not add hand-written tests to
`fct_meetings`** (e.g. in `_gold__models.yml` or a singular test that `ref`s it) — that would
permanently mark it covered and break the RED→GREEN demo.

## Environment & running

Snowflake credentials come from env vars (see `profiles.yml`, profile `zoom_ttd`). For any local
dbt/script run, export them and point dbt at the repo-local profile:

```bash
export DBT_PROFILES_DIR=. \
  SNOWFLAKE_ACCOUNT=QUMTAAX-IO32337 SNOWFLAKE_USER=KARTHIKVALLURI \
  SNOWFLAKE_PASSWORD='<pw>' SNOWFLAKE_ROLE=ACCOUNTADMIN \
  SNOWFLAKE_WAREHOUSE=COMPUTE_WH SNOWFLAKE_DATABASE=DB01
```

The shell is PowerShell by default; the Bash tool is also available (use it for the `export` form above).

## Common commands

```bash
dbt deps                      # install dbt_utils (required once)
dbt seed && dbt build         # full build WITH the gate (prod/main scenario). Expect PASS=37.
dbt build --vars 'ttd_enforce: false'   # build BYPASSING the gate (bootstrap / debugging)

# TTD workflow — always via the orchestrator, run from the repo root:
python zoom-ttd-plugin/assets/scripts/zttd.py enforce        # run the gate read-only (RED report)
python zoom-ttd-plugin/assets/scripts/zttd.py build          # scaffold -> build -> gen unit tests -> test -> grade
python zoom-ttd-plugin/assets/scripts/zttd.py gen-unit-tests fct_meetings
python zoom-ttd-plugin/assets/scripts/zttd.py grade          # write artifacts/grades.json + scorecard
python zoom-ttd-plugin/assets/scripts/zttd.py demo-reset     # delete generated tests -> back to RED

# Run a single / subset of tests:
dbt test --select fct_meetings                       # all tests on one model
dbt test --select test_type:unit                     # only unit tests
dbt test --select test_type:singular                 # only singular tests
dbt test --select test_name:test_fct_meetings_characterization
```

The same `/zoom-ttd:<cmd>` slash commands exist once the plugin is installed
(`/plugin marketplace add <repo>/zoom-ttd-plugin` then `/plugin install zoom-ttd@zoom-ci-standards`).
The skills just invoke the `zttd.py` commands above.

## Architecture

### The coverage gate (interceptor)
`zoom-ttd-plugin/assets/macros/ttd_intercept_coverage.sql` is wired to `on-run-start` in
`dbt_project.yml`, so it fires on `dbt build`/`compile`/`test` (not `parse`). It walks
`graph.nodes`, collects every model a `test` or `unit_test` depends on, and
`raise_compiler_error`s if any in-scope model is uncovered. Controlled by vars `ttd_enforce`
(default true) and `ttd_exempt_prefixes` (`['brz_']` — bronze is pass-through and exempt). The
macro reaches the project because `macro-paths` includes `zoom-ttd-plugin/assets/macros`.

> Jinja gotcha that bit this code once: a `{% set flag = true %}` inside a `{% for %}` does **not**
> escape the loop. Use `namespace()` (as the exempt-prefix check does).

### Slim CI scratch schemas
`generate_schema_name.sql` reads `DBT_PR_SCHEMA`. In a PR run CI sets `DBT_PR_SCHEMA=PR_<n>`, so
models land in `PR_<n>_BRONZE/SILVER/GOLD`; unset (main/local) → `ZOOM_BRONZE/SILVER/GOLD`.
`drop_pr_schemas.sql` (via `dbt run-operation`) tears those down on PR close.

### Graders vs. interceptor
The interceptor answers "any test? yes/no". `graders.py` answers "is the model tested across the
logic it contains?" It regex-detects four categories from each model's `raw_code`
(conditional_logic / dedup / string_transform / edge_case) and grades **A** (functional + unit),
**B** (tested, no unit), **F** (untested). Output → `artifacts/grades.json`, `scorecard.md/.csv`;
`build_dashboard.py` renders the HTML. `graders.py` also embeds each model's per-test source
(generic type/column/args, singular SQL, unit `given`/`expect`) under a `tests_detail` key in
`grades.json`; the dashboard turns the **Tests (g/s/u)** counts into links that expand those
written test cases inline (all embedded, so the HTML stays self-contained/offline).

### Test generators
- `scaffold_tests.py` (pre-build, no warehouse): parses the manifest, writes `_ttd_stub__<model>.yml`
  with not_null/unique on the **grain key only** (never blanket not_null — that would fail on
  legitimately-nullable columns like `engagement_score`).
- `generate_unit_tests.py` (post-build, needs warehouse): **key-correlated characterization** —
  samples the built model's own rows (→ `expect` + grain keys), then pulls upstream rows whose key
  is in that set (→ `given`). This is why multi-table facts produce a *passing* mocked-input test
  instead of a degenerate empty join. These are drift tests, not correctness proofs.

All scripts resolve the project root by walking up to `dbt_project.yml` (`_common.py`) and must be
run from within the project tree. `zttd.py build` internally runs an `--vars 'ttd_enforce: false'`
compile before `gen-unit-tests` (the generator needs `compiled_code`).

### Models
`seeds/raw_*` (deliberately messy: dup rows, mixed-case, nulls, clock skew) → `models/bronze/brz_*`
(pass-through) → `models/silver/slv_*` (the real CASE/QUALIFY/cast/COALESCE logic) →
`models/gold/{dim_accounts,dim_hosts,fct_meetings}`. Seeds force raw columns to `varchar` via
`seeds/_seeds__properties.yml` so the silver casts are genuine transforms.

## CI workflows (`.github/workflows/`)
- `prod-state.yml` (push to main): builds prod with the gate, publishes `target/manifest.json` to a
  dedicated **`prod-state` branch** (`state/manifest.json`) — the deferral baseline (no dbt Cloud).
- `pr-ci.yml` (PR): restores `prod-state`, runs the gate, then
  `dbt build --select state:modified+ --defer --state prod/state --favor-state`, then grades. Make
  the `slim-ci` job a **required status check** on main.
- `pr-teardown.yml` (PR closed): `dbt run-operation drop_pr_schemas`.

## Conventions
- dbt 1.11 + dbt-snowflake; unit tests require ≥1.8. Generic-test args nest under `arguments:`
  (1.11 deprecation) — follow the existing `_silver__models.yml` / `_gold__models.yml` style.
- `profiles.yml` is committed but **secret-free** (env_var only). Never hardcode credentials.
- Generated test files use the `_ttd_stub__` / `_ttd_unit__` prefixes; `demo-reset` removes exactly
  these under `models/`. Keep that contract intact.

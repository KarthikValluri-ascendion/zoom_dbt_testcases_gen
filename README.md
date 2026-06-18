# Zoom Test-Then-Deploy (TTD) — dbt + Snowflake + GitHub Actions Slim CI

> A CI/CD quality gate that **no dbt model can reach production without tests**, and
> that keeps Snowflake credits low by building **only the models a PR changed** in a
> throwaway schema. Built for a free GitHub account with dbt Core — no dbt Cloud.

This repo is a complete, runnable demo:

- a **Zoom-themed medallion** pipeline (bronze → silver → gold, 1 fact + 2 dimensions),
- the **`zoom-ttd` plugin** — a from-scratch Claude Code plugin with an *interceptor*
  (coverage gate), *graders* (A/B/F scorecard), and *generators* (auto-write functional
  + unit tests),
- three **GitHub Actions workflows** implementing **Slim CI with deferral**.

---

## 1. The business problem (why this matters to Zoom)

A developer changes a dbt model and opens a pull request. Two risks:

1. **Untested logic ships.** Reviewers can't catch every missing test by eye. Bad data
   reaches production dashboards.
2. **CI is expensive.** Rebuilding the *entire* warehouse on every PR burns Snowflake
   credits.

This solution fixes both:

| Risk | Our control |
|------|-------------|
| Untested model merges | **Interceptor** blocks the build (and the merge) until every model has a test |
| "Has tests" ≠ "tests the right things" | **Graders** score each model A/B/F on its *actual* logic |
| Full-warehouse rebuilds | **Slim CI + deferral** builds only changed models into an ephemeral `PR_<n>` schema |
| Schema sprawl | **Teardown** drops the PR schema on merge/close |

---

## 2. The pipeline (what's being tested)

```
seeds (raw_*)          bronze (brz_*)        silver (slv_*)            gold
─────────────          ─────────────         ─────────────            ────
raw_meetings      →    brz_meetings     →    slv_meetings        →    fct_meetings   (FACT)
raw_participants  →    brz_participants →    slv_participants     ↘   dim_accounts   (DIM)
raw_accounts      →    brz_accounts     →    slv_accounts         →   dim_hosts      (DIM)
   (messy on purpose)   (pass-through)        (the real logic)        (stars)
```

The seeds are deliberately messy so the transforms — and therefore the tests — are
meaningful. The silver/gold models exercise the four logic categories the graders score:

- **Conditional logic** — `CASE` status/tier/lifecycle mappings
- **De-duplication** — `QUALIFY ROW_NUMBER()` on duplicate meetings & join events
- **String / data transforms** — `TRIM/UPPER/INITCAP`, `::timestamp`/`::date` casts
- **Edge cases** — `COALESCE` on null durations, clock-skew clamps, `NULLIF` divide-by-zero
  guards, `LEAST(...)` caps

`fct_meetings` deliberately ships **without tests** — it is the RED fixture the gate catches.

---

## 3. The `zoom-ttd` plugin — three moving parts

Lives in [`zoom-ttd-plugin/`](zoom-ttd-plugin/). Install it as a local marketplace:

```
/plugin marketplace add  <absolute path to this repo>/zoom-ttd-plugin
/plugin install zoom-ttd@zoom-ci-standards
```

| Part | File | What it does |
|------|------|--------------|
| **Interceptor** | `assets/macros/ttd_intercept_coverage.sql` | `on-run-start` gate: aborts the build *before* anything materializes if any in-scope model has no test. Fail-fast = no wasted credits. |
| **Graders** | `assets/scripts/graders.py` | Detects each model's logic categories from its SQL, then grades **A** (functional + unit), **B** (tested, no unit), **F** (untested). Writes `artifacts/grades.json` + scorecard. |
| **Generators** | `scaffold_tests.py`, `generate_unit_tests.py` | Auto-write functional stubs (no warehouse) and **characterization unit tests** by sampling real rows and running the model on mocked inputs. |

Slash commands: `/zoom-ttd:{enforce, scaffold, gen-unit-tests, grade, build, dashboard, demo-reset}`.

> **Honesty note for the client:** generated unit tests are *characterization* tests —
> they pin current behaviour to catch drift, not to prove correctness. A human reviews
> them. Functional stubs only test the grain key (never blanket `not_null`), so a
> generated stub can never fail a correct build.

### The RED → GREEN demo (run locally)

```bash
# from the repo root, with SNOWFLAKE_* env vars exported (see §5):
export DBT_PROFILES_DIR=.

/zoom-ttd:demo-reset        # delete generated tests -> fct_meetings is untested (RED)
/zoom-ttd:enforce           # gate FAILS: ">>> TTD COVERAGE GATE FAILED ... fct_meetings"
/zoom-ttd:build             # scaffold -> build -> gen unit tests -> run -> grade  (GREEN)
/zoom-ttd:dashboard         # open artifacts/zoom_ttd_scorecard.html
```

Verified output: gate **PASS**, **A=3 B=3 F=0** of 6 models; the auto-generated
`_ttd_unit__fct_meetings.yml` captures the coalesce-to-0, the `NULLIF` divide guard
(engagement = null for the cancelled meeting), and the `LEAST` cap (engagement = 100).

---

## 4. CI/CD in plain English (for someone new to it)

A **workflow** is a YAML file in `.github/workflows/` that GitHub runs automatically on
an **event** (a push, a pull request). It runs **jobs** on a fresh Linux machine
(a **runner**); each job runs **steps** (shell commands). **Secrets** are encrypted
values (like your Snowflake password) that the workflow reads but nobody can see.

Two ideas make this "Slim CI":

- **`state:modified+`** — build only the models that changed in this PR, plus the models
  downstream of them. Not the whole project.
- **`--defer --state <prod manifest>`** — for anything you did *not* rebuild, read it
  from **production** instead. So a one-line change to `fct_meetings` builds *only*
  `fct_meetings`, reading `slv_*` and `dim_*` straight from prod.

A **required status check** + **branch protection** means: the PR cannot be merged until
this workflow is green.

> **Coming from GitLab?** It maps 1:1: `.gitlab-ci.yml` → a workflow file; stages/jobs →
> jobs/steps; CI/CD variables → GitHub secrets; required pipelines → required status
> checks; dbt Cloud state → the `prod-state` branch pattern below.

### The three workflows in this repo

| File | Trigger | What it does |
|------|---------|--------------|
| [`.github/workflows/prod-state.yml`](.github/workflows/prod-state.yml) | push to `main` | Builds full prod (gate ON), publishes `target/manifest.json` to the **`prod-state`** branch. This manifest is the deferral baseline. |
| [`.github/workflows/pr-ci.yml`](.github/workflows/pr-ci.yml) | pull request | **The gate.** Runs the interceptor, then `dbt build --select state:modified+ --defer --state prod/state` into `PR_<n>_*`, then grades. Make this a **required check**. |
| [`.github/workflows/pr-teardown.yml`](.github/workflows/pr-teardown.yml) | PR closed | Drops the `PR_<n>_*` scratch schemas. |

---

## 5. Step-by-step: stand it up on GitHub (first time)

**Prerequisites:** Python 3.11, `pip install dbt-snowflake`, `git`, and the GitHub CLI
(`gh auth login`).

1. **Confirm it works locally.** Export your Snowflake env vars and run a build:
   ```bash
   export DBT_PROFILES_DIR=. \
     SNOWFLAKE_ACCOUNT=QUMTAAX-IO32337 SNOWFLAKE_USER=KARTHIKVALLURI \
     SNOWFLAKE_PASSWORD='********' SNOWFLAKE_ROLE=ACCOUNTADMIN \
     SNOWFLAKE_WAREHOUSE=COMPUTE_WH SNOWFLAKE_DATABASE=DB01
   dbt deps && dbt seed && dbt build           # should end: PASS=37 ERROR=0
   ```

2. **Create the repo and push:**
   ```bash
   gh repo create zoom-ttd-demo --private --source . --remote origin
   git add . && git commit -m "Zoom TTD: medallion + plugin + Slim CI"
   git push -u origin main
   ```

3. **Add the Snowflake secrets** (GitHub → Settings → Secrets and variables → Actions,
   or via CLI):
   ```bash
   gh secret set SNOWFLAKE_ACCOUNT   -b QUMTAAX-IO32337
   gh secret set SNOWFLAKE_USER      -b KARTHIKVALLURI
   gh secret set SNOWFLAKE_PASSWORD  -b '********'
   gh secret set SNOWFLAKE_ROLE      -b ACCOUNTADMIN
   gh secret set SNOWFLAKE_WAREHOUSE -b COMPUTE_WH
   gh secret set SNOWFLAKE_DATABASE  -b DB01
   ```
   > ⚠️ **Security:** for a quick demo we reuse the `ACCOUNTADMIN` login. Before any real
   > use, create a dedicated low-privilege CI role (CREATE SCHEMA + USAGE on `DB01` and
   > `COMPUTE_WH` only) and use those credentials instead. `profiles.yml` is committed but
   > **secret-free** — it only references env vars.

4. **Bootstrap production state.** The push to `main` triggers `prod-state.yml`. Watch it
   in the **Actions** tab; when it finishes, a **`prod-state`** branch exists holding
   `state/manifest.json`. (Re-run it from the Actions tab if you added secrets after the
   first push.)

5. **Protect `main`.** Settings → Branches → Add rule for `main` → check **Require status
   checks to pass before merging** → select **`slim-ci`** → also check **Require branches
   to be up to date**.

6. **Demo the gate on a PR:**
   ```bash
   git checkout -b feat/engagement-tweak
   /zoom-ttd:demo-reset                 # strip fct_meetings' tests
   git commit -am "WIP: change fct_meetings, forgot tests"
   git push -u origin feat/engagement-tweak
   gh pr create --fill
   ```
   The `slim-ci` check turns **red** with the `TTD COVERAGE GATE FAILED` banner — **merge
   is blocked.** 🔴

7. **Go green:**
   ```bash
   /zoom-ttd:build                      # regenerate functional + unit tests
   git commit -am "Add functional + unit tests for fct_meetings"
   git push
   ```
   CI re-runs: gate passes, only `fct_meetings(+)` builds into `PR_<n>_GOLD` (the rest
   deferred to prod), tests pass, scorecard posts. The check turns **green.** 🟢 Merge it.

8. On merge, `prod-state.yml` refreshes the manifest and `pr-teardown.yml` drops the
   `PR_<n>_*` schemas.

---

## 6. Why this is the WOW factor

- **It can't be bypassed.** The gate is a required status check, enforced by the build
  itself — not a reviewer remembering to look. *Test-Then-Deploy, literally.*
- **It grades quality, not just presence.** "Do you have a test?" becomes "are you testing
  your conditional logic, your de-dup, your null edges?" — on an executive scorecard.
- **It writes the tests for you.** A failing gate is one command from green; the unit-test
  generator samples real rows and runs the model to capture behaviour automatically.
- **It saves Snowflake credits.** Slim CI + deferral builds *one* model instead of the
  whole graph; the scratch schema is ephemeral and auto-dropped.
- **It needs nothing Zoom doesn't already have.** Free GitHub account, dbt Core, GitHub
  Actions — a clean GitLab→GitHub parity story with no dbt Cloud licence.

---

## Repo map

```
testcases_dbt/
├── dbt_project.yml                 # wires the interceptor on-run-start
├── profiles.yml                    # env-var driven, secret-free
├── models/{bronze,silver,gold}/    # the medallion (+ generated _ttd_*__ test files)
├── tests/                          # 2 singular tests
├── seeds/                          # messy Zoom-themed raw data
├── zoom-ttd-plugin/                # the from-scratch plugin (interceptor + graders + generators + skills)
├── .github/workflows/              # prod-state.yml, pr-ci.yml, pr-teardown.yml
└── artifacts/                      # grades.json, scorecard.md/.csv, zoom_ttd_scorecard.html
```

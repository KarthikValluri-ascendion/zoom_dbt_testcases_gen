# Zoom Test-Then-Deploy — Demo Runbook

> A step-by-step script you can run **and** present. Each step says exactly what to
> type, what the client should look at, where the **Interceptor** and **Graders** kick
> in, and what each step reads (**input**) and writes (**output**). Boxes marked
> 🟢 **New to CI/CD?** explain a concept in plain English. Boxes marked 💡 **WOW** are
> your talking points.

---

## 0. The 60-second pitch (say this first)

> "Today a developer can change a dbt model and merge it to production **without a single
> test**. Bad data reaches Zoom's dashboards, and nobody notices until someone downstream
> does. On top of that, every pull request rebuilds the **whole** warehouse — burning
> Snowflake credits for models that didn't even change.
>
> This demo fixes both. We built a **quality gate that physically blocks any untested
> model from merging** (Test-Then-Deploy), and a **Slim CI** pipeline that builds **only
> the models a PR touched** into a throwaway schema. It runs on a free GitHub account with
> dbt Core — no dbt Cloud licence — so it's a clean **GitLab → GitHub** parity story."

💡 **WOW:** Three custom pieces make this work, all built from scratch: an **Interceptor**
(the gate), **Graders** (an A/B/F scorecard of *test quality*, not just presence), and
**Generators** (it writes the missing tests for you).

---

## 1. One-time setup

### 1a. Tools & credentials
```bash
# from the repo root
pip install -r requirements.txt        # dbt-snowflake + helpers
dbt deps                               # installs dbt_utils (once)

# point dbt at the repo-local profile and supply Snowflake creds via env vars
export DBT_PROFILES_DIR=. \
  SNOWFLAKE_ACCOUNT=QUMTAAX-IO32337 SNOWFLAKE_USER=KARTHIKVALLURI \
  SNOWFLAKE_PASSWORD='********'  SNOWFLAKE_ROLE=ACCOUNTADMIN \
  SNOWFLAKE_WAREHOUSE=COMPUTE_WH SNOWFLAKE_DATABASE=DB01
```
> 🟢 **New to CI/CD?** `profiles.yml` is committed to the repo but contains **no
> passwords** — it only references env vars like `SNOWFLAKE_PASSWORD`. The real secret
> lives on your machine (and later, in GitHub's encrypted Secrets). Never paste the
> password into a file.

### 1b. Install the plugin ("the master plugin")
The one plugin that carries everything is **`zoom-ttd`**. It's published through a small
local **marketplace** called **`zoom-ci-standards`**. Install it inside Claude Code:

```
/plugin marketplace add  C:\Users\karthik.valluri\OneDrive - ascendion\Desktop\dbt_demos\testcases_dbt\zoom-ttd-plugin
/plugin install          zoom-ttd@zoom-ci-standards
```
Then confirm it loaded:
```
/zoom-ttd:enforce          # should resolve and run (it's the gate, read-only)
```
> 🟢 **New to plugins?** A *marketplace* is just a catalogue (here, a folder on disk). A
> *plugin* is the thing you install from it. `zoom-ttd@zoom-ci-standards` reads as
> "install plugin **zoom-ttd** from marketplace **zoom-ci-standards**." After install you
> get seven `/zoom-ttd:*` slash commands.

**The seven commands (this is the whole toolkit):**

| Command | One-liner |
|---|---|
| `/zoom-ttd:enforce` | Run the Interceptor read-only → RED/GREEN coverage report |
| `/zoom-ttd:grade` | Run the Graders → A/B/F scorecard |
| `/zoom-ttd:scaffold` | Auto-write functional test stubs (no warehouse needed) |
| `/zoom-ttd:gen-unit-tests` | Auto-write mocked-input unit tests (samples real rows) |
| `/zoom-ttd:build` | The big one: scaffold → build → gen-unit → test → grade |
| `/zoom-ttd:dashboard` | Render the executive HTML scorecard |
| `/zoom-ttd:demo-reset` | Delete generated tests → back to the RED starting state |

---

## 2. SEE THE PROBLEM in Snowflake (do this before fixing anything)

First populate the warehouse, **bypassing the gate** so the messy fact actually builds:
```bash
dbt seed
dbt build --vars "ttd_enforce: false"      # expect PASS=33 (gate OFF on purpose)
```
> 🟢 **New to dbt?** `seed` loads the CSV sample data; `build` runs every model and test.
> The `--vars 'ttd_enforce: false'` flag turns our gate **off** for this one run — we
> *want* the untested model to build so we can look at the damage it could do.

Now open **`snowflake_explore.sql`** in a Snowflake worksheet and run it top to bottom.
Talking points for each block:

1. **`ZOOM_BRONZE.RAW_MEETINGS`** — mixed-case host emails, cryptic status codes
   (`O/S/E/C`), a **NULL** duration (cancelled meeting `M0005`), and a **duplicate** row
   (`M0008` twice). *"This is the reality of raw event data."*
2. **The duplicate-counting queries** — prove `M0008` (and duplicate participant joins)
   exist in raw.
3. **`ZOOM_SILVER.SLV_MEETINGS`** — same data, now clean: words instead of codes, emails
   normalized, the duplicate gone, the NULL duration coalesced to 0.
4. **`ZOOM_GOLD.FCT_MEETINGS`** — the engagement score, with three fragile edge cases:
   **NULL** for the cancelled meeting (divide-by-zero guard), **0** for meetings with no
   participants, and **100** where the score is capped.

💡 **WOW:** "Every one of those edge cases is the result of a deliberate line of SQL —
`coalesce`, `nullif`, `least(100, …)`. **There is no test protecting any of them.** A
one-character change to that formula ships silently. That's the risk we're about to close."

---

## 3. The command sequence: RED → GREEN

Run these in order. This is the heart of the demo.

| # | Command | What it does (plain English) | Interceptor? | Graders? | Input → Output |
|---|---|---|:---:|:---:|---|
| 1 | `/zoom-ttd:demo-reset` | Strips the generated tests so `fct_meetings` is untested again — the **RED** starting line | — | — | deletes `models/**/_ttd_stub__*.yml`, `_ttd_unit__*.yml` |
| 2 | `/zoom-ttd:enforce` | Runs the gate read-only. **FAILS** with a banner naming `fct_meetings` | ✅ **fires** | — | reads dbt `graph.nodes` → prints `>>> TTD COVERAGE GATE FAILED … fct_meetings` |
| 3 | `/zoom-ttd:grade` | Scores every model. `fct_meetings` = **F** (untested) | — | ✅ **fires** | reads `target/manifest.json` → writes `artifacts/grades.json`, `scorecard.md/.csv` |
| 4 | `/zoom-ttd:build` | The fix: scaffolds a stub, builds, **generates a unit test from real rows**, runs all tests, regrades → **GREEN** | ✅ (build re-checks) | ✅ (final step) | manifest + live warehouse rows → `_ttd_stub__fct_meetings.yml`, `_ttd_unit__fct_meetings.yml`, refreshed scorecard |
| 5 | `/zoom-ttd:dashboard` | Renders the executive HTML scorecard to open in a browser (click any **Tests g/s/u** count to view that model's written test cases inline) | — | — | reads `grades.json` → writes `artifacts/zoom_ttd_scorecard.html` |

### Step 2 — the money shot (RED)
`/zoom-ttd:enforce` aborts with:
```
>>> TTD COVERAGE GATE FAILED
    The following model(s) ship with no test and cannot be built/merged:
      - fct_meetings
```
💡 **WOW:** "Notice it failed **before building anything** — no warehouse compute was
spent. The gate is fail-fast by design, so a missing test never costs a Snowflake credit."

### Step 4 — self-healing (GREEN)
`/zoom-ttd:build` runs the whole chain and ends green. Two artifacts it writes are worth
showing on screen:
- **`models/gold/_ttd_stub__fct_meetings.yml`** — functional tests (not_null/unique on the
  grain key). *"It only asserts the grain key, so a generated stub can never fail a correct
  build."*
- **`models/gold/_ttd_unit__fct_meetings.yml`** — a **characterization unit test**: the
  generator sampled real `slv_meetings`/`slv_participants` rows, ran the model on those
  mocked inputs, and captured the output — **including** the NULL engagement (cancelled),
  the 0 (no participants), and the 100 cap.

💡 **WOW:** "The gate didn't just complain — it **wrote the tests for us** by running the
model on real data. A failing PR is one command away from green."

---

## 4. What the Interceptor and Graders actually are

> 🟢 **The Interceptor (the gate).** It's a single dbt macro
> (`ttd_intercept_coverage.sql`) wired to dbt's `on-run-start` hook, so it runs at the very
> start of every `dbt build`/`compile`/`test`. It walks dbt's internal graph
> (`graph.nodes`), collects every model that some test or unit-test depends on, and if any
> in-scope model isn't in that set it **aborts the run with a compiler error**. Bronze
> pass-through models (`brz_*`) are exempt. *Fail-fast = nothing materializes, no credits
> burned.*
>
> **Input:** the dbt graph. **Output:** PASS (silent) or a hard FAIL banner.

> 🟢 **The Graders (the scorecard).** A Python script (`graders.py`) that goes beyond
> "any test? yes/no." For each model it **regex-detects the kinds of logic** it contains —
> conditional (`CASE`), de-dup (`QUALIFY`/`ROW_NUMBER`), string/data transforms
> (`TRIM/UPPER/::cast`), edge cases (`COALESCE/NULLIF`) — then grades:
> **A** = functional **and** unit tests; **B** = tested but no unit test; **F** = untested.
>
> **Input:** `target/manifest.json` (compiled SQL + test graph).
> **Output:** `artifacts/grades.json` + `scorecard.md/.csv` + the HTML dashboard.

**Current scorecard (what GREEN looks like):**

| Gate | A | B | F | of |
|:---:|:---:|:---:|:---:|:---:|
| **PASS** | 3 | 3 | 0 | 6 models |

`fct_meetings`, `slv_meetings`, `slv_participants` = **A**; `dim_accounts`, `dim_hosts`,
`slv_accounts` = **B**; nothing is **F**.

💡 **WOW:** "This turns a vague 'do we have tests?' into an executive metric: *are we
testing the conditional logic, the de-dup, the null edges?* — per model, on one scorecard."

---

## 5. CI/CD in plain English + the three workflows

> 🟢 **The five words you need.** A **workflow** is a YAML file in `.github/workflows/`
> that GitHub runs automatically on an **event** (a push, a pull request). It runs **jobs**
> on a fresh Linux machine called a **runner**; each job runs **steps** (shell commands).
> **Secrets** are encrypted values (your Snowflake password) the workflow can read but no
> human can see. A **required status check** + **branch protection** means *the PR cannot
> be merged until this workflow passes.*

> 🟢 **What makes it "Slim CI."** Two flags:
> - `--select state:modified+` → build **only the models that changed** in this PR (plus
>   the ones downstream of them), not the whole project.
> - `--defer --state <prod manifest>` → for anything you did **not** rebuild, read it
>   straight from **production**. So a one-line change to `fct_meetings` builds *only*
>   `fct_meetings`, reading `slv_*`/`dim_*` from prod.

**GitLab → GitHub parity (for the Zoom team coming from GitLab):**

| GitLab | GitHub Actions |
|---|---|
| `.gitlab-ci.yml` | a workflow file in `.github/workflows/` |
| stages / jobs | jobs / steps |
| CI/CD variables | encrypted **Secrets** |
| required pipeline | **required status check** |
| dbt Cloud state | the **`prod-state` branch** pattern (free; no dbt Cloud) |

**The three workflows in the repo:**

| File | Trigger | What it does | Interceptor / Graders |
|---|---|---|---|
| `.github/workflows/prod-state.yml` | push to `main` | Builds full prod (gate ON), publishes `target/manifest.json` to a dedicated **`prod-state`** branch — the deferral baseline | Interceptor runs (full build) |
| `.github/workflows/pr-ci.yml` | pull request | **The gate.** Runs the Interceptor, then the slim deferred build into `PR_<n>_*`, then the Graders | ✅ both |
| `.github/workflows/pr-teardown.yml` | PR closed | Drops the `PR_<n>_*` scratch schemas | — |

> 🟢 **Why a `prod-state` branch?** Deferral needs a "what does prod look like right now?"
> snapshot (a dbt *manifest*). dbt Cloud sells this; we get it free by having the `main`
> workflow commit the manifest to a side branch the PR workflow reads. Pure GitHub, zero
> licence.

---

## 6. The CI demo on a real PR (the Slim-CI money shot)

This shows the gate blocking a merge, then the credit-saving slim build.

```bash
git checkout -b feat/engagement-tweak
/zoom-ttd:demo-reset                      # strip fct_meetings' tests (simulate a careless dev)
git commit -am "WIP: tweak fct_meetings, forgot the tests"
git push -u origin feat/engagement-tweak
gh pr create --fill
```
1. **The `slim-ci` check turns 🔴 RED** — the Interceptor fails `dbt compile` with the
   `TTD COVERAGE GATE FAILED` banner. **Merge is blocked.** *(Show the red X on the PR.)*

```bash
/zoom-ttd:build                           # regenerate functional + unit tests
git commit -am "Add functional + unit tests for fct_meetings"
git push
```
2. **CI re-runs and turns 🟢 GREEN** — gate passes; only `fct_meetings(+)` builds into
   `PR_<n>_GOLD`; everything else is **deferred to prod**; tests pass; the scorecard posts.
3. **Merge** → `prod-state.yml` refreshes the baseline manifest and `pr-teardown.yml` drops
   the `PR_<n>_*` schemas.

💡 **WOW:** "Watch the green build log — it built **one** model, not all 37. The PR schema
is ephemeral and auto-dropped on merge. That's the Snowflake-credit story, live."

---

## 7. WOW summary (closing slide)

- **It can't be bypassed.** The gate is a *required status check* enforced by the build
  itself — not a reviewer remembering to look. *Test-Then-Deploy, literally.*
- **It grades quality, not just presence.** A/B/F per model against its *actual* logic.
- **It writes the tests for you.** A failing gate is one command from green; the generator
  samples real rows and runs the model to capture behaviour.
- **It saves Snowflake credits.** Slim CI + deferral builds one model instead of the whole
  graph, in a throwaway schema that's auto-dropped.
- **It needs nothing Zoom doesn't already have.** Free GitHub account, dbt Core, GitHub
  Actions — a clean GitLab → GitHub parity story, no dbt Cloud licence.

---

## Appendix — reset to a clean RED state

To re-run the demo from scratch:
```
/zoom-ttd:demo-reset      # deletes the generated _ttd_stub__ / _ttd_unit__ files
/zoom-ttd:enforce         # confirms fct_meetings is RED again
```
> ⚠️ **Never hand-write tests on `fct_meetings`** (in `_gold__models.yml` or a singular
> test that `ref`s it). That would permanently mark it covered and break the RED → GREEN
> demo. Its tests are supposed to exist only in the generated `_ttd_*__fct_meetings.yml`
> files, which `demo-reset` strips.
>
> ⚠️ **Before real production use**, swap the demo `ACCOUNTADMIN` credentials for a
> dedicated low-privilege CI role (CREATE SCHEMA + USAGE on `DB01` and `COMPUTE_WH` only).

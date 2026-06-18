# zoom-ttd — Test-Then-Deploy standard

**Principle: no model ships without a test.** Every dbt model carries at least one
test (schema, singular, or unit). The rule is enforced mechanically, on every
build, by an `on-run-start` interceptor — not by a code-review checkbox.

## The three moving parts
1. **Interceptor** (`ttd_intercept_coverage`, on-run-start): fails the run *before*
   anything materializes if an in-scope model has zero tests. Bronze is exempt.
2. **Graders** (`graders.py`): score every model **A/B/F** on coverage of the
   logic it actually contains — conditional, edge-case, de-duplication,
   string/data transforms. A = functional + unit; B = tested but no unit;
   F = untested.
3. **Generators** (`scaffold_tests.py`, `generate_unit_tests.py`): when the gate
   fails, auto-produce functional stubs and runnable characterization unit tests
   so going green is one command (`/zoom-ttd:build`).

## Honesty about generated tests
- Functional stubs test only the grain key (never blanket not_null) so a stub
  can't fail a correct build. Review and tighten them.
- Unit tests are **characterization**: real sampled inputs → captured output.
  They catch drift, not correctness. A human must confirm the captured behaviour
  is the *desired* behaviour.

## CI
The gate runs in GitHub Actions Slim CI: a PR builds only `state:modified+` into
an ephemeral `PR_<n>_*` schema, deferring unbuilt parents to production. A
required status check blocks merge until the gate, the slim build, and the unit
tests are green.

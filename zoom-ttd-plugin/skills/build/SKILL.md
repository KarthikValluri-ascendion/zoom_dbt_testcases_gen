---
name: build
description: Full Test-Then-Deploy cycle - scaffold functional stubs, dbt build behind the gate, generate unit tests, run tests, then grade.
argument-hint: "[<dbt build args>]"
---

# /zoom-ttd:build

From the dbt project root, run:

```
python zoom-ttd-plugin/assets/scripts/zttd.py build $ARGUMENTS
```

Sequence:
1. **scaffold** functional stubs for any uncovered model (so the gate can pass),
2. **dbt build** with the on-run-start interceptor active,
3. **generate** characterization unit tests for the freshly-stubbed models,
4. **run** the unit + singular tests,
5. **grade** every model and write the scorecard.

Report each phase's result; if the gate fails at step 2, surface the banner.

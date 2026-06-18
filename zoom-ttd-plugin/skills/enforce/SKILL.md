---
name: enforce
description: Run the on-run-start coverage interceptor (read-only) and report any model with no schema, singular, or unit test.
argument-hint: "[<dbt selector args>]"
---

# /zoom-ttd:enforce

From the dbt project root, run:

```
python zoom-ttd-plugin/assets/scripts/zttd.py enforce $ARGUMENTS
```

This compiles the project, which fires the `ttd_intercept_coverage` macro on
`on-run-start`. If any in-scope model lacks a test the gate raises a
`TTD COVERAGE GATE FAILED` banner and the command exits non-zero. Report the
banner verbatim and list the uncovered models.

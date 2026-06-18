---
name: scaffold
description: Generate functional (schema) test stubs for any dbt model that has no tests. Pre-build, no warehouse needed.
argument-hint: "[<model_name> ...]"
---

# /zoom-ttd:scaffold

From the dbt project root, run:

```
python zoom-ttd-plugin/assets/scripts/zttd.py scaffold $ARGUMENTS
```

This parses the project and writes `_ttd_stub__<model>.yml` (not_null + unique on
the grain key, not_null on other key columns) next to every uncovered, in-scope
model. The bronze layer (`brz_`) is exempt. Report which stubs were created and
remind the user to review and tighten them.

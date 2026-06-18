---
name: demo-reset
description: Delete generated functional stubs + unit tests so the fact model is untested again - the RED starting state for the Red->Green demo.
argument-hint: ""
---

# /zoom-ttd:demo-reset

From the dbt project root, run:

```
python zoom-ttd-plugin/assets/scripts/zttd.py demo-reset
```

This removes every `_ttd_stub__*.yml` and `_ttd_unit__*.yml` under `models/`,
returning `fct_meetings` to its untested state. The next `dbt build` (or
`/zoom-ttd:enforce`) will FAIL the coverage gate -- the RED starting point for
demonstrating the gate, then `/zoom-ttd:build` to go GREEN.

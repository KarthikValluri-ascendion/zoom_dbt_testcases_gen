---
name: grade
description: Grade every model A/B/F on test coverage of its actual logic (conditional, edge, dedup, string/transform) and write the scorecard.
argument-hint: ""
---

# /zoom-ttd:grade

From the dbt project root, run:

```
python zoom-ttd-plugin/assets/scripts/zttd.py grade
```

This statically detects the logic categories in each model and scores it:
**A** = functional + unit test, **B** = tested but no unit test, **F** = untested.
It writes `artifacts/grades.json`, `artifacts/scorecard.md`, and
`artifacts/scorecard.csv`. Summarize the gate result and the per-model grades.

---
name: dashboard
description: Build the self-contained HTML test-coverage scorecard from the latest grades. Opens offline in any browser.
argument-hint: ""
---

# /zoom-ttd:dashboard

From the dbt project root, run:

```
python zoom-ttd-plugin/assets/scripts/zttd.py grade
python zoom-ttd-plugin/assets/scripts/zttd.py dashboard
```

The first command refreshes `artifacts/grades.json`; the second renders
`artifacts/zoom_ttd_scorecard.html` (gate badge, grade distribution, per-model
table, medallion lineage). Tell the user the file path to open.

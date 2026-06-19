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

In the per-model table, each non-zero count in the **Tests (g/s/u)** column is a
link: clicking it expands an inline panel with the *written* test cases for that
model — generic tests (type + column + args), singular test SQL, and unit-test
`given`/`expect` rows. The detail is embedded in the HTML (it comes from
`grades.json` → `tests_detail`), so the page stays self-contained and works
offline. Mention this so the user knows they can drill into the actual tests.

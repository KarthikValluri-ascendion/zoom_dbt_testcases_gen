---
name: gen-unit-tests
description: Generate characterization unit tests (mocked inputs -> captured output) for models that lack one. Needs a warehouse and a built model.
argument-hint: "[<model_name> ...]"
---

# /zoom-ttd:gen-unit-tests

From the dbt project root, run:

```
python zoom-ttd-plugin/assets/scripts/zttd.py gen-unit-tests $ARGUMENTS
```

For each target model this samples the model's own built output (the `expect`
rows + grain keys), pulls the key-correlated upstream rows (the `given` inputs),
and writes a runnable `_ttd_unit__<model>.yml`. These are CHARACTERIZATION tests:
they pin current behaviour to catch drift, not correctness -- tell the user to
review them. If a faithful fixture can't be built automatically, a skeleton is
written for manual completion.

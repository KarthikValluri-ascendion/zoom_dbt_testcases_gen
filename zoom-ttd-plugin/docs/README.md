# zoom-ttd plugin

A from-scratch Claude Code plugin that turns "every dbt model must be tested"
into an enforced, automated workflow for dbt + Snowflake, wired for GitHub
Actions Slim CI.

## What's inside
```
zoom-ttd-plugin/
├── .claude-plugin/
│   ├── plugin.json          # plugin manifest
│   └── marketplace.json     # local marketplace "zoom-ci-standards"
├── assets/
│   ├── CLAUDE.global.md     # the standard
│   ├── zoom-ttd-config.json # defaults (exempt prefixes, grade rules, ...)
│   ├── macros/
│   │   ├── ttd_intercept_coverage.sql  # THE INTERCEPTOR (on-run-start gate)
│   │   ├── generate_schema_name.sql    # per-PR scratch schema (Slim CI)
│   │   └── drop_pr_schemas.sql         # Slim CI teardown
│   └── scripts/
│       ├── zttd.py                 # orchestrator CLI
│       ├── scaffold_tests.py       # functional stub generator
│       ├── generate_unit_tests.py  # characterization unit-test generator
│       ├── graders.py              # A/B/F grader + scorecard
│       └── build_dashboard.py      # self-contained HTML scorecard
└── skills/                  # /zoom-ttd:{scaffold,enforce,gen-unit-tests,grade,build,dashboard,demo-reset}
```

## Install (local marketplace)
```
/plugin marketplace add  <absolute path to>/testcases_dbt/zoom-ttd-plugin
/plugin install zoom-ttd@zoom-ci-standards
```
The slash commands run the scripts in this folder (the plugin lives inside the
dbt project), so paths resolve from the project root.

## Wire into a dbt project
`dbt_project.yml`:
```yaml
macro-paths: ["macros", "zoom-ttd-plugin/assets/macros"]
on-run-start: ["{{ ttd_intercept_coverage() }}"]
vars:
  ttd_enforce: true
  ttd_exempt_prefixes: ['brz_']
```

## Commands
| Skill | Does |
|-------|------|
| `/zoom-ttd:enforce` | run the interceptor, report uncovered models |
| `/zoom-ttd:scaffold` | generate functional stubs (no warehouse) |
| `/zoom-ttd:gen-unit-tests` | generate characterization unit tests (warehouse) |
| `/zoom-ttd:grade` | grade A/B/F + write the scorecard |
| `/zoom-ttd:build` | scaffold → build → gen-unit → test → grade |
| `/zoom-ttd:dashboard` | render the HTML scorecard |
| `/zoom-ttd:demo-reset` | delete generated tests (back to RED) |

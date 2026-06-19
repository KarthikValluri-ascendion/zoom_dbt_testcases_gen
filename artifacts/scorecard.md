# zoom-ttd Test Coverage Scorecard

**Gate:** PASS &nbsp;|&nbsp; **A:** 3 &nbsp; **B:** 3 &nbsp; **F:** 0 &nbsp; (of 6 models)

| Model | Layer | Grade | Status | Logic categories | Unit-covered | Tests (g/s/u) |
|-------|-------|:-----:|--------|------------------|--------------|---------------|
| `fct_meetings` | zoom_gold | **A** | FULLY COVERED | edge_case | edge_case | 3/0/1 |
| `slv_meetings` | zoom_silver | **A** | FULLY COVERED | conditional_logic, dedup, string_transform, edge_case | conditional_logic, dedup, string_transform, edge_case | 4/1/1 |
| `slv_participants` | zoom_silver | **A** | FULLY COVERED | conditional_logic, dedup, string_transform | conditional_logic, dedup, string_transform | 3/1/1 |
| `dim_accounts` | zoom_gold | **B** | FUNCTIONAL ONLY | conditional_logic | - | 3/0/0 |
| `dim_hosts` | zoom_gold | **B** | FUNCTIONAL ONLY | dedup | - | 3/0/0 |
| `slv_accounts` | zoom_silver | **B** | FUNCTIONAL ONLY | conditional_logic, string_transform | - | 3/1/0 |

_Grades: A = functional + unit; B = tested but no unit; F = untested._

"""Grade every in-scope model A / B / F on test coverage of its actual logic.

The on-run-start interceptor only answers "any test? yes/no". The grader answers
"is the model tested across the logic it actually contains?" -- the four
categories the client cares about: conditional logic, edge cases, de-duplication,
and string/data transforms.

For each model we statically detect which categories its SQL uses, then look at
what tests exist:
  A = has functional (schema) test(s) AND a unit test (mocked inputs exercise the
      logic categories)
  B = has functional and/or singular test(s) but NO unit test
  F = no tests at all (also blocked by the interceptor)

Writes artifacts/grades.json, artifacts/scorecard.md, artifacts/scorecard.csv.
Pure manifest analysis -- no warehouse needed.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from _common import load_config, load_manifest, project_root, in_scope_models

CATEGORY_PATTERNS = {
    "conditional_logic": re.compile(r"\bcase\b|\biff\s*\(|\bdecode\s*\(", re.IGNORECASE),
    "dedup": re.compile(r"\bqualify\b|row_number\s*\(\s*\)\s*over|\bdistinct\b", re.IGNORECASE),
    "string_transform": re.compile(
        r"\b(trim|upper|lower|initcap|concat|substr|replace)\s*\(|::\s*(date|timestamp)|"
        r"\bcast\s*\(|\bdate_trunc\s*\(|\bdatediff\s*\(",
        re.IGNORECASE,
    ),
    "edge_case": re.compile(r"\b(coalesce|nullif|ifnull|zeroifnull|least|greatest)\s*\(", re.IGNORECASE),
}


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*|/\*.*?\*/", " ", sql, flags=re.DOTALL)


def detect_categories(raw_sql: str) -> list[str]:
    sql = _strip_comments(raw_sql or "")
    return [cat for cat, pat in CATEGORY_PATTERNS.items() if pat.search(sql)]


def _norm_path(p: str) -> str:
    return (p or "").replace("\\", "/")


def _generic_detail(node: dict) -> dict:
    tm = node.get("test_metadata") or {}
    kwargs = {
        k: v
        for k, v in (tm.get("kwargs") or {}).items()
        if k not in ("column_name", "model")
    }
    return {
        "name": node.get("name", ""),
        "type": tm.get("name", ""),
        "column": node.get("column_name") or "",
        "args": kwargs,
        "file": _norm_path(node.get("original_file_path", "")),
    }


def _singular_detail(node: dict) -> dict:
    return {
        "name": node.get("name", ""),
        "sql": node.get("raw_code", "") or "",
        "file": _norm_path(node.get("original_file_path", "")),
    }


def _unit_detail(node: dict) -> dict:
    return {
        "name": node.get("name", ""),
        "given": node.get("given", []),
        "expect": node.get("expect", {}),
        "file": _norm_path(node.get("original_file_path", "")),
    }


def _empty_detail() -> dict:
    return {"generic": [], "singular": [], "unit": []}


def collect_tests(manifest: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    """Return (counts, details) keyed by model unique_id.

    counts:  unique_id -> {'generic': n, 'singular': n, 'unit': n}
    details: unique_id -> {'generic': [...], 'singular': [...], 'unit': [...]}
             where each entry carries enough to render the written test
             (type/column/args, singular SQL, or unit given/expect) in the
             dashboard -- no warehouse needed, it all lives in the manifest.
    """
    counts: dict[str, dict] = {}
    details: dict[str, dict] = {}
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") != "test":
            continue
        if node.get("test_metadata"):
            kind, entry = "generic", _generic_detail(node)
        else:
            kind, entry = "singular", _singular_detail(node)
        for dep in node.get("depends_on", {}).get("nodes", []):
            if dep.startswith("model."):
                counts.setdefault(dep, {"generic": 0, "singular": 0, "unit": 0})[kind] += 1
                details.setdefault(dep, _empty_detail())[kind].append(entry)
    for node in manifest.get("unit_tests", {}).values():
        entry = _unit_detail(node)
        for dep in node.get("depends_on", {}).get("nodes", []):
            if dep.startswith("model."):
                counts.setdefault(dep, {"generic": 0, "singular": 0, "unit": 0})["unit"] += 1
                details.setdefault(dep, _empty_detail())["unit"].append(entry)
    return counts, details


def grade_model(node: dict, tests: dict, details: dict) -> dict:
    t = tests.get(node["unique_id"], {"generic": 0, "singular": 0, "unit": 0})
    d = details.get(node["unique_id"], _empty_detail())
    categories = detect_categories(node.get("raw_code", ""))
    has_functional = t["generic"] > 0
    has_singular = t["singular"] > 0
    has_unit = t["unit"] > 0

    if not (has_functional or has_singular or has_unit):
        grade, status = "F", "UNTESTED"
    elif has_unit and has_functional:
        grade, status = "A", "FULLY COVERED"
    elif has_unit:
        grade, status = "A", "UNIT COVERED"
    else:
        grade, status = "B", "FUNCTIONAL ONLY"

    # which categories are exercised by a unit test (our coverage signal)
    covered = categories if has_unit else []
    return {
        "model": node["name"],
        "layer": node.get("schema", "").lower() or node.get("name", "").split("_")[0],
        "categories": categories,
        "categories_covered": covered,
        "tests": t,
        "tests_detail": d,
        "grade": grade,
        "status": status,
    }


def main(argv: list[str]) -> int:
    cfg = load_config()
    exempt = cfg.get("exempt_prefixes", [])
    root = project_root()
    manifest = load_manifest(root)

    tests, details = collect_tests(manifest)
    models = in_scope_models(manifest, exempt)

    grades = [grade_model(node, tests, details) for node in models.values()]
    grades.sort(key=lambda g: (g["grade"] != "F", g["grade"], g["model"]))

    n = len(grades)
    counts = {"A": 0, "B": 0, "F": 0}
    for g in grades:
        counts[g["grade"]] += 1
    gate = "PASS" if counts["F"] == 0 else "FAIL"
    run = {
        "gate": gate,
        "models_total": n,
        "grade_A": counts["A"],
        "grade_B": counts["B"],
        "grade_F": counts["F"],
        "failing_models": [g["model"] for g in grades if g["grade"] == "F"],
    }

    art = root / "artifacts"
    art.mkdir(exist_ok=True)
    (art / "grades.json").write_text(
        json.dumps({"run": run, "models": grades}, indent=2), encoding="utf-8"
    )

    # markdown scorecard
    md = [
        "# zoom-ttd Test Coverage Scorecard",
        "",
        f"**Gate:** {gate} &nbsp;|&nbsp; **A:** {counts['A']} &nbsp; **B:** {counts['B']} &nbsp; **F:** {counts['F']} &nbsp; (of {n} models)",
        "",
        "| Model | Layer | Grade | Status | Logic categories | Unit-covered | Tests (g/s/u) |",
        "|-------|-------|:-----:|--------|------------------|--------------|---------------|",
    ]
    for g in grades:
        t = g["tests"]
        md.append(
            f"| `{g['model']}` | {g['layer']} | **{g['grade']}** | {g['status']} | "
            f"{', '.join(g['categories']) or '-'} | {', '.join(g['categories_covered']) or '-'} | "
            f"{t['generic']}/{t['singular']}/{t['unit']} |"
        )
    md += ["", "_Grades: A = functional + unit; B = tested but no unit; F = untested._", ""]
    (art / "scorecard.md").write_text("\n".join(md), encoding="utf-8")

    # csv
    with (art / "scorecard.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "layer", "grade", "status", "categories", "categories_covered",
                    "generic_tests", "singular_tests", "unit_tests"])
        for g in grades:
            t = g["tests"]
            w.writerow([g["model"], g["layer"], g["grade"], g["status"],
                        "|".join(g["categories"]), "|".join(g["categories_covered"]),
                        t["generic"], t["singular"], t["unit"]])

    # console summary
    print(f"\nzoom-ttd grade gate: {gate}  (A={counts['A']} B={counts['B']} F={counts['F']} of {n})")
    for g in grades:
        print(f"  {g['grade']}  {g['model']:<22} [{', '.join(g['categories']) or '-'}]")
    print(f"\nWrote {art/'grades.json'}, scorecard.md, scorecard.csv")
    return 0 if gate == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

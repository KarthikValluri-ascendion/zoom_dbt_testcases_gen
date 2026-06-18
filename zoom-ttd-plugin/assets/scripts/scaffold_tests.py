"""Scaffold functional (schema) test stubs for any in-scope model that has no
tests. Pre-build, no warehouse needed.

For each uncovered model we emit `_ttd_stub__<model>.yml` next to the model with
not_null/unique on the grain key and not_null on any other key columns. We
deliberately do NOT blanket-test every column (nullable columns such as a guarded
ratio would fail not_null), so a generated stub always passes a correct build.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from _common import load_config, load_manifest, project_root, in_scope_models, covered_model_ids

_COMMENT = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def _strip_comments(sql: str) -> str:
    return _COMMENT.sub(" ", sql)


def _final_select_columns(raw_sql: str) -> list[str]:
    """Best-effort extraction of the final SELECT's output column names."""
    sql = _strip_comments(raw_sql)
    lowered = sql.lower()

    # locate the last top-level (paren-depth 0) `select`
    depth = 0
    select_pos = -1
    for m in re.finditer(r"[()]|\bselect\b", lowered):
        tok = m.group()
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
        elif depth == 0:
            select_pos = m.end()
    if select_pos == -1:
        return []

    # find the matching top-level `from` after it
    depth = 0
    from_pos = len(sql)
    for m in re.finditer(r"[()]|\bfrom\b", lowered[select_pos:]):
        tok = m.group()
        if tok == "(":
            depth += 1
        elif tok == ")":
            depth -= 1
        elif depth == 0:
            from_pos = select_pos + m.start()
            break

    col_blob = sql[select_pos:from_pos]

    # split on top-level commas
    parts, buf, depth = [], [], 0
    for ch in col_blob:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))

    cols = []
    for part in parts:
        expr = part.strip()
        if not expr:
            continue
        # `... as alias`  ->  alias
        m = re.search(r"\bas\s+([a-z_][a-z0-9_]*)\s*$", expr, re.IGNORECASE)
        if m:
            cols.append(m.group(1).lower())
            continue
        # bare `table.column` or `column`
        token = re.split(r"\s+", expr)[-1]
        token = token.split(".")[-1].strip('"').lower()
        if re.fullmatch(r"[a-z_][a-z0-9_]*", token):
            cols.append(token)
    # de-dup, preserve order
    seen, ordered = set(), []
    for c in cols:
        if c not in seen:
            seen.add(c)
            ordered.append(c)
    return ordered


def _stub_yaml(model_name: str, cols: list[str]) -> str:
    key_cols = [c for c in cols if c.endswith("_id") or c.endswith("_key")]
    lines = [
        "version: 2",
        "",
        "# AUTO-GENERATED functional test stub by zoom-ttd (scaffold).",
        "# Review and tighten -- then `dbt build` will pass the coverage gate.",
        "models:",
        f"  - name: {model_name}",
        f'    description: "TODO: document {model_name}."',
        "    columns:",
    ]
    if key_cols:
        grain = key_cols[0]
        lines.append(f"      - name: {grain}")
        lines.append("        data_tests: [not_null, unique]")
        for c in key_cols[1:]:
            lines.append(f"      - name: {c}")
            lines.append("        data_tests: [not_null]")
    elif cols:
        lines.append(f"      - name: {cols[0]}")
        lines.append("        data_tests: [not_null]")
    lines += [
        "",
        "# A characterization unit test (mocked inputs -> captured output) is generated",
        f"# separately into _ttd_unit__{model_name}.yml by `/zoom-ttd:gen-unit-tests`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    cfg = load_config()
    exempt = cfg.get("exempt_prefixes", [])
    prefix = cfg.get("stub_prefix", "_ttd_stub__")
    root = project_root()
    manifest = load_manifest(root)

    covered = covered_model_ids(manifest)
    models = in_scope_models(manifest, exempt)

    written = []
    for uid, node in models.items():
        if uid in covered:
            continue
        name = node["name"]
        model_file = root / node["original_file_path"]
        stub_file = model_file.parent / f"{prefix}{name}.yml"
        if stub_file.exists():
            print(f"  - {name}: stub already exists, skipping")
            continue
        cols = _final_select_columns(node.get("raw_code", ""))
        stub_file.write_text(_stub_yaml(name, cols), encoding="utf-8")
        written.append(name)
        print(f"  + scaffolded {stub_file.relative_to(root)}  (cols: {', '.join(cols) or 'none'})")

    if written:
        print(f"\nzoom-ttd: scaffolded functional stubs for {len(written)} model(s): {', '.join(written)}")
    else:
        print("\nzoom-ttd: no uncovered models -- nothing to scaffold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

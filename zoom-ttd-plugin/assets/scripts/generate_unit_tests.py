"""Generate characterization unit tests (mocked inputs -> captured output) for
in-scope models that have a functional stub but no unit test yet.

Strategy: KEY-CORRELATED characterization.
  1. Sample N rows of the model's OWN built output  -> these become `expect`,
     and their grain-key values are the correlation keys.
  2. For each upstream, pull the rows whose grain key is in that set -> `given`.
Because the given inputs are exactly the real rows that produce the sampled
output, the resulting unit test runs the model on mocked data and passes -- and
it pins the conditional / dedup / string / edge-case behaviour against drift.

These are CHARACTERIZATION tests: they catch behavioural drift, not correctness.
Human review is expected. Requires a warehouse and an already-built model.
"""
from __future__ import annotations

import sys
from pathlib import Path

from _common import (
    capture, load_config, load_manifest, project_root,
    parse_dbt_show_json, in_scope_models,
)

NO_GATE = ["--vars", "ttd_enforce: false"]


def show_inline(root: Path, sql: str, limit: int = 5000) -> list[dict]:
    cp = capture(["dbt", "show", "--inline", sql, "--output", "json", "--limit", str(limit), *NO_GATE], cwd=root)
    return parse_dbt_show_json(cp.stdout)


def show_model(root: Path, name: str, limit: int) -> list[dict]:
    cp = capture(["dbt", "show", "--select", name, "--output", "json", "--limit", str(limit), *NO_GATE], cwd=root)
    return parse_dbt_show_json(cp.stdout)


def column_types(root: Path, node: dict) -> dict[str, str]:
    db = node["database"]
    sch = node["schema"].upper()
    tbl = (node.get("identifier") or node.get("alias") or node["name"]).upper()
    sql = (
        f"select column_name, data_type from {db}.information_schema.columns "
        f"where table_schema = '{sch}' and table_name = '{tbl}' order by ordinal_position"
    )
    rows = show_inline(root, sql, limit=500)
    return {r["column_name"].lower(): str(r["data_type"]).upper() for r in rows}


def _norm_ts(val: str) -> str:
    return val.replace("T", " ").split(".")[0] if isinstance(val, str) else val


def _sql_literal(val, sqltype: str) -> str:
    if val is None:
        return "null"
    t = sqltype.upper()
    if any(k in t for k in ("NUMBER", "DECIMAL", "INT", "FLOAT", "DOUBLE", "REAL")):
        return str(val)
    if "BOOLEAN" in t:
        return "true" if val in (True, "true", "True", 1) else "false"
    if "TIMESTAMP" in t or "DATETIME" in t:
        return f"'{_norm_ts(val)}'::timestamp_ntz"
    if t == "DATE":
        return f"'{str(val).split('T')[0]}'"  # date cast applied by surrounding context
    return "'" + str(val).replace("'", "''") + "'"


def _yaml_scalar(val) -> str:
    if val is None:
        return ""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    return "'" + str(val).replace("'", "''") + "'"


def _yaml_rows(rows: list[dict], indent: str) -> list[str]:
    out = []
    for r in rows:
        pairs = ", ".join(f"{k}: {_yaml_scalar(v)}" for k, v in r.items())
        out.append(f"{indent}- {{{pairs}}}")
    return out


def grain_key(cols: list[str]) -> str | None:
    for c in cols:
        if c.endswith("_id") or c.endswith("_key"):
            return c
    return cols[0] if cols else None


def gen_for_model(root: Path, manifest: dict, node: dict, sample: int) -> tuple[bool, str]:
    """Return (ok, yaml_text). ok=False means a skeleton was produced."""
    name = node["name"]

    expect_rows = show_model(root, name, sample)
    if not expect_rows:
        return False, _skeleton(name, [])

    cols = list(expect_rows[0].keys())
    key = grain_key(cols)
    keys = [r.get(key) for r in expect_rows if r.get(key) is not None]
    if not keys:
        return False, _skeleton(name, [])
    key_list = ", ".join(_yaml_scalar(k) if isinstance(k, str) else str(k) for k in keys)

    # upstream model dependencies
    upstreams = [
        manifest["nodes"][d]
        for d in node.get("depends_on", {}).get("nodes", [])
        if d.startswith("model.") and d in manifest["nodes"]
    ]
    if not upstreams:
        return False, _skeleton(name, cols)

    given_blocks: list[str] = []
    any_rows = False
    for up in upstreams:
        up_name = up["name"]
        up_types = column_types(root, up)
        rel = up["relation_name"]
        if key in up_types:
            sql = f"select * from {rel} where {key} in ({key_list})"
        else:
            sql = f"select * from {rel} limit {sample}"
        rows = show_inline(root, sql, limit=5000)
        given_blocks.append(f"      - input: ref('{up_name}')")
        if rows:
            any_rows = True
            given_blocks.append("        rows:")
            given_blocks.extend(_yaml_rows(rows, "          "))
        else:
            # An upstream with no correlated rows is the legitimate optional
            # side of a left join (e.g. meetings with no participants), not a
            # failure: mock it as an empty input so the model still reproduces
            # the captured `expect` (coalesce -> 0). Bailing to a skeleton here
            # made generation flaky on the row sample.
            given_blocks.append("        rows: []")
    if not any_rows:
        # every input came back empty -> output genuinely can't be reproduced
        return False, _skeleton(name, cols)

    lines = [
        "version: 2",
        "",
        f"# AUTO-GENERATED characterization unit test by zoom-ttd (gen-unit-tests).",
        f"# Mocked inputs -> captured output. Pins current behaviour; review before trusting.",
        "unit_tests:",
        f"  - name: test_{name}_characterization",
        f'    description: "Characterization of {name} on key-correlated sampled rows."',
        f"    model: {name}",
        "    given:",
        *given_blocks,
        "    expect:",
        "      rows:",
        *_yaml_rows(expect_rows, "        "),
        "",
    ]
    return True, "\n".join(lines)


def _skeleton(name: str, cols: list[str]) -> str:
    cols_hint = ", ".join(cols) if cols else "<output columns>"
    return "\n".join([
        "version: 2",
        "",
        "# AUTO-GENERATED skeleton by zoom-ttd. The automatic key-correlated sampler",
        f"# could not build a faithful fixture for `{name}` (e.g. an uncorrelated",
        "# multi-input join). Fill in given/expect by hand, then this passes the gate.",
        "unit_tests:",
        f"  - name: test_{name}_characterization",
        f"    model: {name}",
        "    given:",
        "      - input: ref('<upstream_model>')",
        "        rows:",
        "          - { }",
        "    expect:",
        "      rows: []",
        f"    # output columns: {cols_hint}",
        "",
    ])


def _targets(root: Path, manifest: dict, cfg: dict, argv: list[str]) -> list[dict]:
    exempt = cfg.get("exempt_prefixes", [])
    stub_prefix = cfg.get("stub_prefix", "_ttd_stub__")
    unit_prefix = cfg.get("unit_prefix", "_ttd_unit__")
    models = in_scope_models(manifest, exempt)
    by_name = {n["name"]: n for n in models.values()}

    if argv:
        return [by_name[a] for a in argv if a in by_name]

    # default: models that have a stub but no unit test file yet
    targets = []
    for node in models.values():
        mdir = (root / node["original_file_path"]).parent
        has_stub = (mdir / f"{stub_prefix}{node['name']}.yml").exists()
        has_unit = (mdir / f"{unit_prefix}{node['name']}.yml").exists()
        if has_stub and not has_unit:
            targets.append(node)
    return targets


def main(argv: list[str]) -> int:
    cfg = load_config()
    sample = cfg.get("sample_rows", 8)
    unit_prefix = cfg.get("unit_prefix", "_ttd_unit__")
    root = project_root()
    manifest = load_manifest(root)

    targets = _targets(root, manifest, cfg, argv)
    if not targets:
        print("zoom-ttd: no models need unit-test generation.")
        return 0

    for node in targets:
        name = node["name"]
        print(f"\nzoom-ttd: generating characterization unit test for {name} ...")
        ok, text = gen_for_model(root, manifest, node, sample)
        out = (root / node["original_file_path"]).parent / f"{unit_prefix}{name}.yml"
        out.write_text(text, encoding="utf-8")
        status = "OK" if ok else "SKELETON (needs manual completion)"
        print(f"  -> wrote {out.relative_to(root)}  [{status}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

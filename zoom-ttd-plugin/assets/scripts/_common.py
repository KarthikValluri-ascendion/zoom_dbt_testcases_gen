"""Shared helpers for the zoom-ttd scripts.

All scripts are run from the dbt project root (the directory containing
dbt_project.yml). They shell out to `dbt` and read target/manifest.json.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPTS_DIR.parents[1]          # .../zoom-ttd-plugin
CONFIG_PATH = PLUGIN_ROOT / "assets" / "zoom-ttd-config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def project_root() -> Path:
    """Find the dbt project root by walking up from the current directory."""
    here = Path.cwd().resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "dbt_project.yml").exists():
            return candidate
    sys.exit("zoom-ttd: could not find dbt_project.yml (run from the dbt project root).")


def manifest_path(root: Path | None = None) -> Path:
    return (root or project_root()) / "target" / "manifest.json"


def load_manifest(root: Path | None = None) -> dict:
    p = manifest_path(root)
    if not p.exists():
        sys.exit(f"zoom-ttd: {p} not found. Run `dbt parse` or `dbt compile` first.")
    return json.loads(p.read_text(encoding="utf-8"))


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> subprocess.CompletedProcess:
    print(f"\n$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(cwd or project_root()), check=check)


def capture(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd or project_root()), capture_output=True, text=True
    )


def parse_dbt_show_json(stdout: str) -> list[dict]:
    """Pull the row list out of `dbt show --output json` output, tolerating logs.

    dbt emits a JSON object like {"show": [ {col: val, ...}, ... ]}. Lower-cases
    keys for stable downstream access.
    """
    idx = stdout.find("{")
    while idx != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(stdout[idx:])
            if isinstance(obj, dict) and "show" in obj:
                return [{str(k).lower(): v for k, v in row.items()} for row in obj["show"]]
        except json.JSONDecodeError:
            pass
        idx = stdout.find("{", idx + 1)
    return []


def in_scope_models(manifest: dict, exempt_prefixes: list[str]) -> dict[str, dict]:
    """Return {unique_id: node} for project models not matching an exempt prefix."""
    out = {}
    for uid, node in manifest.get("nodes", {}).items():
        if node.get("resource_type") != "model":
            continue
        if node.get("package_name") != manifest.get("metadata", {}).get("project_name"):
            # only this project's models
            if node.get("package_name") not in (None, manifest.get("metadata", {}).get("project_name")):
                continue
        name = node.get("name", "")
        if any(name.startswith(p) for p in exempt_prefixes):
            continue
        out[uid] = node
    return out


def covered_model_ids(manifest: dict) -> set[str]:
    """Model unique_ids that at least one test or unit_test depends on."""
    covered: set[str] = set()
    for node in manifest.get("nodes", {}).values():
        if node.get("resource_type") == "test":
            covered.update(d for d in node.get("depends_on", {}).get("nodes", []) if d.startswith("model."))
    for node in manifest.get("unit_tests", {}).values():
        covered.update(d for d in node.get("depends_on", {}).get("nodes", []) if d.startswith("model."))
    return covered

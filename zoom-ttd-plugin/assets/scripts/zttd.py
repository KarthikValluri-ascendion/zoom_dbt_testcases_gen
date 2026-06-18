"""zoom-ttd orchestrator CLI.

Run from the dbt project root:

  python zoom-ttd-plugin/assets/scripts/zttd.py <command> [args]

Commands:
  scaffold        generate functional (schema) test stubs for untested models
  enforce         run the on-run-start interceptor (reports uncovered models)
  gen-unit-tests  generate characterization unit tests (mocked inputs)
  grade           grade every model A/B/F and write the scorecard
  build           scaffold -> dbt build -> gen-unit-tests -> dbt test -> grade
  test            run unit + singular tests
  dashboard       build the self-contained HTML scorecard
  demo-reset      delete generated stubs + unit tests (return to the RED state)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
PY = sys.executable


def _root() -> Path:
    here = Path.cwd().resolve()
    for c in [here, *here.parents]:
        if (c / "dbt_project.yml").exists():
            return c
    sys.exit("zoom-ttd: run from the dbt project root (no dbt_project.yml found).")


def dbt(root: Path, *args: str) -> int:
    cmd = ["dbt", *args]
    print(f"\n$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd, cwd=str(root)).returncode


def script(root: Path, name: str, *args: str) -> int:
    cmd = [PY, str(SCRIPTS / name), *args]
    print(f"\n$ python {name} {' '.join(args)}".rstrip(), flush=True)
    return subprocess.run(cmd, cwd=str(root)).returncode


def _stubbed_models(root: Path) -> list[str]:
    names = []
    for p in (root / "models").rglob("_ttd_stub__*.yml"):
        names.append(p.name[len("_ttd_stub__"):-len(".yml")])
    return names


def cmd_scaffold(root: Path, args: list[str]) -> int:
    if dbt(root, "parse") != 0:
        return 1
    return script(root, "scaffold_tests.py", *args)


def cmd_enforce(root: Path, args: list[str]) -> int:
    # `dbt compile` fires the on-run-start interceptor; let it do the talking.
    rc = dbt(root, "compile", *args)
    if rc == 0:
        print("\nzoom-ttd: coverage gate PASSED.")
    else:
        print("\nzoom-ttd: coverage gate FAILED (see banner above).")
    return rc


def cmd_gen_unit(root: Path, args: list[str]) -> int:
    # need a compiled manifest; bypass the gate for this internal compile
    if dbt(root, "compile", "--vars", "ttd_enforce: false") != 0:
        return 1
    return script(root, "generate_unit_tests.py", *args)


def cmd_grade(root: Path, args: list[str]) -> int:
    if dbt(root, "parse") != 0:
        return 1
    return script(root, "graders.py", *args)


def cmd_test(root: Path, args: list[str]) -> int:
    rc = dbt(root, "test", "--select", "test_type:unit", *args)
    rc2 = dbt(root, "test", "--select", "test_type:singular", *args)
    return rc or rc2


def cmd_dashboard(root: Path, args: list[str]) -> int:
    return script(root, "build_dashboard.py", *args)


def cmd_demo_reset(root: Path, args: list[str]) -> int:
    removed = 0
    for pattern in ("_ttd_stub__*.yml", "_ttd_unit__*.yml"):
        for p in (root / "models").rglob(pattern):
            p.unlink()
            print(f"  - removed {p.relative_to(root)}")
            removed += 1
    print(f"\nzoom-ttd: demo-reset removed {removed} generated test file(s). "
          "The next `dbt build` will FAIL the coverage gate (RED state).")
    return 0


def cmd_build(root: Path, args: list[str]) -> int:
    # 1. scaffold functional stubs so the gate can pass
    if cmd_scaffold(root, []) != 0:
        return 1
    # 2. build with the gate ON
    if dbt(root, "build", *args) != 0:
        print("\nzoom-ttd: dbt build failed (gate or model error).")
        return 1
    # 3. generate characterization unit tests for the freshly-stubbed models
    stubbed = _stubbed_models(root)
    if stubbed:
        if dbt(root, "compile", "--vars", "ttd_enforce: false") != 0:
            return 1
        script(root, "generate_unit_tests.py", *stubbed)
        # 4. run the generated unit tests + singular tests
        cmd_test(root, [])
    # 5. grade + scorecard
    script(root, "graders.py")
    return 0


COMMANDS = {
    "scaffold": cmd_scaffold,
    "enforce": cmd_enforce,
    "gen-unit-tests": cmd_gen_unit,
    "grade": cmd_grade,
    "test": cmd_test,
    "dashboard": cmd_dashboard,
    "demo-reset": cmd_demo_reset,
    "build": cmd_build,
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd not in COMMANDS:
        print(f"zoom-ttd: unknown command '{cmd}'.\n{__doc__}")
        return 2
    return COMMANDS[cmd](_root(), rest)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

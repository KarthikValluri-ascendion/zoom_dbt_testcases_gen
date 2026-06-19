"""Build a self-contained HTML test-coverage scorecard from artifacts/grades.json.

Opens offline in any browser. Run `python zttd.py grade` first to produce
grades.json.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

from _common import project_root

GRADE_COLOR = {"A": "#1a7f37", "B": "#9a6700", "F": "#cf222e"}


def _safe_id(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


def _count_cell(model_id: str, t: dict) -> str:
    """Render the g/s/u cell, each non-zero count a link to its detail group."""
    parts = []
    for kind, key in (("generic", "g"), ("singular", "s"), ("unit", "u")):
        n = t.get(kind, 0)
        if n:
            parts.append(
                f'<a class="tl" onclick="tl(\'{model_id}\',\'{kind}\')" '
                f'title="show {kind} tests">{n}</a>'
            )
        else:
            parts.append(f'<span class="z">{n}</span>')
    return " / ".join(parts)


def _render_generic(items: list[dict]) -> str:
    if not items:
        return "<p class='none'>No generic (schema) tests.</p>"
    rows = []
    for it in items:
        args = it.get("args") or {}
        extra = ""
        if args:
            kv = ", ".join(f"{html.escape(str(k))}={html.escape(json.dumps(v))}"
                           for k, v in args.items())
            extra = f' <span class="args">({kv})</span>'
        col = it.get("column")
        on = f" on <code>{html.escape(col)}</code>" if col else ""
        rows.append(
            f'<li><code>{html.escape(it.get("type",""))}</code>{on}{extra}'
            f'<span class="file">{html.escape(it.get("file",""))}</span></li>'
        )
    return f"<ul class='glist'>{''.join(rows)}</ul>"


def _render_singular(items: list[dict]) -> str:
    if not items:
        return "<p class='none'>No singular tests.</p>"
    blocks = []
    for it in items:
        blocks.append(
            f'<div class="tcase"><div class="tname"><code>{html.escape(it.get("name",""))}</code>'
            f'<span class="file">{html.escape(it.get("file",""))}</span></div>'
            f'<pre>{html.escape(it.get("sql","").strip())}</pre></div>'
        )
    return "".join(blocks)


def _render_unit(items: list[dict]) -> str:
    if not items:
        return "<p class='none'>No unit tests.</p>"
    blocks = []
    for it in items:
        given = it.get("given", [])
        expect = it.get("expect", {})
        blocks.append(
            f'<div class="tcase"><div class="tname"><code>{html.escape(it.get("name",""))}</code>'
            f'<span class="file">{html.escape(it.get("file",""))}</span></div>'
            f'<div class="ulabel">given</div>'
            f'<pre>{html.escape(json.dumps(given, indent=2))}</pre>'
            f'<div class="ulabel">expect</div>'
            f'<pre>{html.escape(json.dumps(expect, indent=2))}</pre></div>'
        )
    return "".join(blocks)


def _detail_row(model_id: str, detail: dict, ncols: int) -> str:
    """Hidden row holding the three test groups; toggled by the count links."""
    groups = (
        f'<div class="tg" id="g_{model_id}_generic"><h4>Generic / schema tests</h4>'
        f'{_render_generic(detail.get("generic", []))}</div>'
        f'<div class="tg" id="g_{model_id}_singular"><h4>Singular tests</h4>'
        f'{_render_singular(detail.get("singular", []))}</div>'
        f'<div class="tg" id="g_{model_id}_unit"><h4>Unit tests</h4>'
        f'{_render_unit(detail.get("unit", []))}</div>'
    )
    return (
        f'<tr class="detail" id="d_{model_id}" style="display:none">'
        f'<td colspan="{ncols}">{groups}</td></tr>'
    )


def main(argv: list[str]) -> int:
    root = project_root()
    gj = root / "artifacts" / "grades.json"
    if not gj.exists():
        sys.exit("zoom-ttd: artifacts/grades.json not found. Run `python zttd.py grade` first.")
    data = json.loads(gj.read_text(encoding="utf-8"))
    run, models = data["run"], data["models"]

    gate_color = "#1a7f37" if run["gate"] == "PASS" else "#cf222e"

    NCOLS = 7
    rows = []
    for m in models:
        t = m["tests"]
        mid = _safe_id(m["model"])
        detail = m.get("tests_detail", {"generic": [], "singular": [], "unit": []})
        rows.append(f"""
      <tr>
        <td><code>{m['model']}</code></td>
        <td>{m['layer']}</td>
        <td style="text-align:center"><span class="grade" style="background:{GRADE_COLOR.get(m['grade'],'#666')}">{m['grade']}</span></td>
        <td>{m['status']}</td>
        <td>{', '.join(m['categories']) or '&ndash;'}</td>
        <td>{', '.join(m['categories_covered']) or '&ndash;'}</td>
        <td style="text-align:center" class="tcell">{_count_cell(mid, t)}</td>
      </tr>""")
        rows.append(_detail_row(mid, detail, NCOLS))

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>zoom-ttd Coverage Scorecard</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0; background:#f6f8fa; color:#1f2328; }}
  header {{ background:#0b5cff; color:#fff; padding:24px 32px; }}
  header h1 {{ margin:0; font-size:22px; }}
  header p {{ margin:4px 0 0; opacity:.9; font-size:13px; }}
  .wrap {{ max-width:1080px; margin:24px auto; padding:0 16px; }}
  .cards {{ display:flex; gap:16px; margin-bottom:24px; flex-wrap:wrap; }}
  .card {{ background:#fff; border:1px solid #d0d7de; border-radius:10px; padding:16px 20px; flex:1; min-width:140px; }}
  .card .n {{ font-size:30px; font-weight:700; }}
  .card .l {{ font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:#656d76; }}
  .gate {{ color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; background:{gate_color}; }}
  table {{ width:100%; border-collapse:collapse; background:#fff; border:1px solid #d0d7de; border-radius:10px; overflow:hidden; }}
  th, td {{ padding:10px 12px; text-align:left; border-bottom:1px solid #eaeef2; font-size:13px; }}
  th {{ background:#f6f8fa; font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#656d76; }}
  code {{ background:#eef1f4; padding:1px 5px; border-radius:4px; font-size:12px; }}
  .grade {{ color:#fff; font-weight:700; padding:2px 9px; border-radius:6px; display:inline-block; min-width:18px; text-align:center; }}
  .lin {{ background:#fff; border:1px solid #d0d7de; border-radius:10px; padding:16px 20px; margin-top:24px; font-size:13px; }}
  .lin code {{ font-size:12px; }}
  footer {{ text-align:center; color:#656d76; font-size:12px; margin:24px; }}
  .tcell {{ white-space:nowrap; }}
  a.tl {{ color:#0b5cff; font-weight:700; cursor:pointer; text-decoration:none; }}
  a.tl:hover {{ text-decoration:underline; }}
  .tcell .z {{ color:#afb6be; }}
  tr.detail td {{ background:#fbfcfe; padding:0; }}
  tr.detail .tg {{ padding:14px 18px; border-top:2px solid #0b5cff; }}
  tr.detail h4 {{ margin:0 0 10px; font-size:12px; text-transform:uppercase; letter-spacing:.04em; color:#0b5cff; }}
  tr.detail .none {{ margin:0; color:#656d76; font-size:13px; }}
  tr.detail ul.glist {{ margin:0; padding-left:18px; }}
  tr.detail ul.glist li {{ margin:3px 0; font-size:13px; }}
  tr.detail .args {{ color:#656d76; }}
  tr.detail .file {{ color:#8a929b; font-size:11px; margin-left:8px; }}
  tr.detail .tcase {{ margin-bottom:14px; }}
  tr.detail .tname {{ font-size:13px; margin-bottom:4px; }}
  tr.detail .ulabel {{ font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:#656d76; margin:6px 0 2px; }}
  tr.detail pre {{ margin:0; background:#0d1117; color:#e6edf3; padding:10px 12px; border-radius:8px;
                   font-size:12px; line-height:1.45; overflow:auto; max-height:340px; }}
</style></head>
<body>
<header>
  <h1>Zoom Test-Then-Deploy &mdash; Coverage Scorecard</h1>
  <p>Generated by the zoom-ttd grader &middot; every model graded A/B/F on the logic it actually contains</p>
</header>
<div class="wrap">
  <div class="cards">
    <div class="card"><div class="l">Gate</div><div class="n"><span class="gate">{run['gate']}</span></div></div>
    <div class="card"><div class="l">Models</div><div class="n">{run['models_total']}</div></div>
    <div class="card"><div class="l">Grade A</div><div class="n" style="color:#1a7f37">{run['grade_A']}</div></div>
    <div class="card"><div class="l">Grade B</div><div class="n" style="color:#9a6700">{run['grade_B']}</div></div>
    <div class="card"><div class="l">Grade F</div><div class="n" style="color:#cf222e">{run['grade_F']}</div></div>
  </div>

  <table>
    <thead><tr>
      <th>Model</th><th>Layer</th><th>Grade</th><th>Status</th>
      <th>Logic categories</th><th>Unit-covered</th><th>Tests (g/s/u)</th>
    </tr></thead>
    <tbody>{''.join(rows)}
    </tbody>
  </table>

  <div class="lin">
    <strong>Medallion lineage</strong><br>
    <code>seeds (raw_*)</code> &rarr; <code>bronze (brz_*)</code> &rarr;
    <code>silver (slv_*)</code> &rarr; <code>gold (dim_*, fct_meetings)</code><br><br>
    <strong>Grades:</strong> A = functional + unit test (logic categories exercised) &middot;
    B = tested but no unit test &middot; F = untested (blocked by the on-run-start interceptor).<br><br>
    <strong>Tip:</strong> click any count in the <em>Tests (g/s/u)</em> column to view the written test cases inline.
  </div>
</div>
<footer>zoom-ttd &middot; tests (g/s/u) = generic / singular / unit &middot; click a count to see the test source</footer>
<script>
  function tl(id, kind) {{
    var row = document.getElementById('d_' + id);
    var target = document.getElementById('g_' + id + '_' + kind);
    if (!row || !target) return;
    var groups = row.querySelectorAll('.tg');
    var isOpen = row.style.display !== 'none' && target.style.display !== 'none';
    groups.forEach(function (g) {{ g.style.display = 'none'; }});
    if (isOpen) {{
      row.style.display = 'none';
    }} else {{
      row.style.display = 'table-row';
      target.style.display = 'block';
    }}
  }}
</script>
</body></html>"""

    out = root / "artifacts" / "zoom_ttd_scorecard.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"zoom-ttd: wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

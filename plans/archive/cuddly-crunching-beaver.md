# Plan: TASK-375/376/377 — SLO, PromptRegression, DebtScan Health Widgets

## Context
Continuing the Health tab widget suite. Three new API endpoints + dashboard widgets, each following the established blueprint pattern (`_load_tool` → call internal functions → return JSON; `pollXDetailed()` in `dashboard_panels.js`). TASK-374 established the last widget (ThreatModel); these three complete the core health visibility set.

## Current State
- 374 tasks merged, 2075 tests passing, master branch
- Health tab has 5 widgets: health-detailed, gates, policy, context-window, threat-model
- All blueprints follow `_load_tool()` + `_get_app()` lazy-import pattern

## TASK-375: SLODashboardWidget

### New files
- `solo_builder/api/blueprints/slo.py` — `GET /health/slo`
- `solo_builder/tests/test_slo_dashboard_widget.py` — ~25 tests

### Modified files
- `solo_builder/api/app.py` — import + register `slo_bp`
- `solo_builder/api/dashboard.html` — add `slo-detailed-content` div after threat-model section
- `solo_builder/api/static/dashboard_panels.js` — add `export async function pollSloDetailed()`
- `solo_builder/api/static/dashboard.js` — add to import + `tick()` Promise.all
- `claude/allowed_files.txt` — add new files

### Blueprint: GET /health/slo
Uses `_load_tool("slo_check")` then calls internal functions:
```python
sc = _load_tool("slo_check")
records = sc._load_records(sc.METRICS_PATH)
if len(records) >= sc.DEFAULT_MIN_RECORDS:
    results = [sc._check_slo003(records), sc._check_slo005(records)]
    ok = all(r["status"] == "ok" for r in results)
else:
    results = []
    ok = True  # insufficient data — not a failure
return jsonify({"ok": ok, "records": len(records), "results": results})
```
Response: `{ok, records, results:[{slo, target, value, status, detail}]}`

### JS widget: pollSloDetailed()
- Fetches `/health/slo`; target el: `slo-detailed-content`
- Header: `SLO${d.ok ? " — OK" : " — breaches detected"}` (green/red)
- Per-result rows: status badge (ok=green, breach=red, no_data/skip=dim), SLO ID, value vs target
- Empty: "Insufficient metrics data."

### Tests (~25)
- HTML: div present, inside health tab, after threat-model, loading placeholder
- Panels JS: exported, endpoint, content div, ok flag, slo/status/value rendered, replaceChildren, empty state
- Main JS: imported, called in tick, import regex
- Endpoint integration: 200, ok key, records key, results list, json content-type

---

## TASK-376: PromptRegressionAPI

### New files
- `solo_builder/api/blueprints/prompt_regression.py` — `GET /health/prompt-regression`
- `solo_builder/tests/test_prompt_regression_api.py` — ~25 tests

### Modified files
- `solo_builder/api/app.py` — import + register `prompt_regression_bp`
- `solo_builder/api/dashboard.html` — add `prompt-regression-detailed-content` div
- `solo_builder/api/static/dashboard_panels.js` — add `pollPromptRegressionDetailed()`
- `solo_builder/api/static/dashboard.js` — add to import + tick
- `claude/allowed_files.txt` — add new files

### Blueprint: GET /health/prompt-regression
```python
prc = _load_tool("prompt_regression_check")
report = prc.run_checks(settings_path=settings_path)
d = report.to_dict()
return jsonify({"ok": d["passed"], **d})
```
Response: `{ok, passed, total, failed, results:[{name, passed, errors}]}`

### JS widget: pollPromptRegressionDetailed()
- Fetches `/health/prompt-regression`; target el: `prompt-regression-detailed-content`
- Header: `Prompts: N templates — OK/FAIL` (green/red based on `d.ok`)
- Per-result rows: OK/FAIL badge, template name; if errors → dim sub-line with first error
- Empty (no templates): "No templates registered."

### Tests (~25)
- HTML: div present, inside health tab, loading placeholder
- Panels JS: exported, endpoint, content div, ok/passed/total rendered, template name, replaceChildren
- Main JS: imported, called in tick, import regex
- Endpoint integration: 200, ok/passed/total/failed/results keys, json content-type

---

## TASK-377: DebtScanDashboardWidget

### New files
- `solo_builder/api/blueprints/debt_scan.py` — `GET /health/debt-scan`
- `solo_builder/tests/test_debt_scan_dashboard_widget.py` — ~25 tests

### Modified files
- `solo_builder/api/app.py` — import + register `debt_scan_bp`
- `solo_builder/api/dashboard.html` — add `debt-scan-detailed-content` div
- `solo_builder/api/static/dashboard_panels.js` — add `pollDebtScanDetailed()`
- `solo_builder/api/static/dashboard.js` — add to import + tick
- `claude/allowed_files.txt` — add new files

### Blueprint: GET /health/debt-scan
```python
ds = _load_tool("debt_scan")
items = ds.scan()   # returns list[DebtItem(path, line, marker, text)]
count = len(items)
ok = count == 0
results = [{"path": str(i.path), "line": i.line, "marker": i.marker, "text": i.text}
           for i in items[:20]]  # cap at 20 for response size
return jsonify({"ok": ok, "count": count, "results": results})
```
Response: `{ok, count, results:[{path, line, marker, text}]}`

### JS widget: pollDebtScanDetailed()
- Fetches `/health/debt-scan`; target el: `debt-scan-detailed-content`
- Header: `Debt: N items` (green if 0, yellow if >0)
- Per-result rows: marker badge (TODO/FIXME/HACK), file:line, text excerpt (truncated)
- Empty: "No debt items found."

### Tests (~25)
- HTML: div present, inside health tab, loading placeholder
- Panels JS: exported, endpoint, content div, count/ok rendered, marker/path/text, replaceChildren, empty state
- Main JS: imported, called in tick, import regex
- Endpoint integration: 200, ok/count/results keys, json content-type

---

## Key Patterns (reuse across all three)

**Blueprint boilerplate** (identical to `threat_model.py`):
```python
from flask import Blueprint, jsonify
import importlib.util, sys
from pathlib import Path
_TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools"
def _load_tool(name): ...  # cache in sys.modules
def _get_app(): from api.app import app, SETTINGS_PATH; return app, SETTINGS_PATH
```

**Test boilerplate** (identical to `test_threat_model_dashboard_widget.py`):
- `_Base` class with `setUp`/`tearDown` patching STATE_PATH + SETTINGS_PATH + rate limiter
- `patch.object(bp_mod, "_load_tool", return_value=mock_mod)` for endpoint tests
- HTML tests read file directly; JS tests grep file content

**Commit sequence** (per task, same as recent tasks):
1. `start_task.ps1` (with stash)
2. Implement + test
3. Run full suite
4. Add to `allowed_files.txt`
5. `CLAUDE_ALLOW_NEW_FILES=1 git commit`
6. Merge `--no-ff` to master
7. Update CHANGELOG

---

## Verification
After all three tasks:
```
python -m pytest solo_builder/tests/ solo_builder/api/test_app.py -q --tb=no
```
Expected: ~2150 tests passing (2075 + ~25×3).

Health tab widget order (bottom to top of addition):
health-detailed → gates → policy → context-window → threat-model → slo → prompt-regression → debt-scan

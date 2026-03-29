# Plan: Three-Step Sprint — Mutmut score, Depth pass batch 7, TASK-420

## Context
Previous mutmut background run failed (wrong flag `--paths-to-mutate` not supported in mutmut 3.5.0).
The edge-case tests from the prior plan were already merged (v8.3.7), improving score from 85% → 90.2%.
Now: run mutmut correctly, do depth pass batch 7 on three thin test files, and implement TASK-420
(per-subtask timing — `started_at` / `output_updated_at` fields in executor.py). The dashboard JS
already renders these fields; only the backend is missing.

Current: master @ v8.3.13, 5426 tests, 0 failures.

---

## Step 1: Run mutmut (background, immediately)

**Problem**: mutmut 3.5.0 in WSL doesn't support `--paths-to-mutate` flag. It reads config from
`setup.cfg [mutmut]` or `pyproject.toml [tool.mutmut]`. The `pyproject.toml` config points to
multiple directories (slow). To target only `dag_transitions.py`, create a temporary `setup.cfg`
at the repo root.

**Actions:**
1. Write `setup.cfg` at repo root with:
   ```ini
   [mutmut]
   paths_to_mutate = solo_builder/utils/dag_transitions.py
   runner = python -m pytest solo_builder/tests/ -x -q --tb=no
   tests_dir = solo_builder/tests/
   ```
2. From WSL, run `python3 -m mutmut run` in background (will take ~5-10 min)
3. When done: `python3 -m mutmut results` → report killed/survived/timeout counts + score
4. Delete `setup.cfg` after results retrieved (keep pyproject.toml config intact)

---

## Step 2: Depth pass batch 7 — three thin test files

Target: `test_blueprint_load_tool.py` (25 tests), `test_ci_quality_gate.py` (26 tests), `test_dag_cmds_tools.py` (21 tests)

### test_blueprint_load_tool.py → add `TestBlueprintLoadToolRoutes` (~8 tests)
The file already has a `TestBlueprintLoadToolDeep` class. Add a new class testing the endpoint responses:
- `GET /health/ci-quality` returns 200 + JSON with `ok` bool + `checks` list
- `GET /health/context-window` returns 200 + JSON with `ok` bool
- `GET /health/debt-scan` returns 200 + JSON with `ok` bool
- `GET /health/pre-release` returns 200 + JSON
- `GET /health/prompt-regression` returns 200 + JSON
- Response `ok` is bool type for each endpoint
- `checks` list length > 0 when present
- Each check dict has expected keys

Use the `_Base` test class pattern from `test_live_summary_blueprint.py` (patched STATE_PATH + Flask test client).

**Source**: `solo_builder/api/blueprints/` (ci_quality.py, context_window.py, debt_scan.py, etc.)

### test_ci_quality_gate.py → add `TestCiQualityGateDeep` (~8 tests)
- `ToolResult` is a namedtuple — `._fields` contains expected field names
- `ToolResult._fields` includes `name`, `ok`, `output`, `duration`
- `_tool_definitions()` returns list of 7+ dicts
- Each tool dict has `name` (str) and `cmd` (str)
- Tool names are unique (no duplicates)
- `_run_tool()` is callable
- Output truncated to 600 chars when long (create fake tool cmd that outputs >600 chars)
- `run_gate(skip={"nonexistent"})` doesn't crash

**Source**: `tools/ci_quality_gate.py`

### test_dag_cmds_tools.py → add `TestDagCmdsToolsDeep2` (~8 tests)
- `dag_stats` on 2 tasks returns `total=2`
- `dag_stats` counts Running subtasks
- `validate_dag` on valid dag returns `[]`
- `validate_dag` on dag with missing `branches` key returns non-empty list
- `DagCommandsMixin` has `_cmd_depends`
- `DagCommandsMixin` has `_cmd_heal`
- `DagCommandsMixin` has `_cmd_snapshot`
- `dag_cmds_module.MAX_SUBTASKS_PER_BRANCH` is int

---

## Step 3: TASK-420 — Per-subtask timing (started_at + output_updated_at)

**Discovery**: The dashboard JS (`dashboard_tasks.js` lines ~1791-1813) already renders `started_at`
and `output_updated_at` fields. The backend just doesn't populate them. This is a 3-line backend
change + smoke tests.

### executor.py changes

**Where `started_at` is set** — when subtask transitions Pending → Running (executor.py ~line 375):
```python
if status == "Pending":
    st_data["status"]      = "Running"
    st_data["last_update"] = step
    st_data["started_at"]  = _dt.datetime.now(_dt.timezone.utc).isoformat()  # ← ADD
    st_data.setdefault("history", []).append({"status": "Running", "step": step})
    actions[st_name] = "started"
```
Note: `_dt` is already imported at line 220 (`import datetime as _dt`).

**Where `output_updated_at` is set** — three locations where `st_data["output"]` is assigned:
- ~line 506: SDK tool-use result
- ~line 569: Claude subprocess result
- ~line 611: SDK direct result

Add after each `st_data["output"] = ...`:
```python
st_data["output_updated_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat()
```

**Do NOT add to `DEFAULT_SUBTASK_FIELDS`** — these are set at runtime, not as defaults.
This avoids breaking `test_state_integrity.py::test_default_subtask_fields_includes_all_required`.

### Smoke tests — add `TestSubtaskTimingSmoke` to `test_executor_timing.py` (~8 tests)
- `started_at` set when subtask transitions to Running
- `started_at` is ISO-8601 string
- `started_at` contains `T` (datetime separator)
- `output_updated_at` set when output is populated
- `output_updated_at` is ISO-8601 string
- Subtask already Running does not get `started_at` reset on second `execute_step`
- `started_at` not present on Pending subtask before any step
- Dashboard JS contains `started_at` field reference (static assertion)

---

## Files Modified

### Step 1 (temp, deleted after):
- `setup.cfg` (create, then delete)

### Step 2:
- `solo_builder/tests/test_blueprint_load_tool.py`
- `solo_builder/tests/test_ci_quality_gate.py`
- `solo_builder/tests/test_dag_cmds_tools.py`
- `CHANGELOG.md`, `pyproject.toml` (v8.3.14)

### Step 3:
- `solo_builder/runners/executor.py` (~3 lines added)
- `solo_builder/tests/test_executor_timing.py` (new class)
- `CHANGELOG.md`, `pyproject.toml` (v8.3.15)
- `claude/TASK_ACTIVE.md`, `claude/JOURNAL.md`, `claude/TASK_QUEUE.md`

---

## Verification

```bash
# After step 2:
python -m pytest tests/test_blueprint_load_tool.py tests/test_ci_quality_gate.py tests/test_dag_cmds_tools.py -q --tb=short

# After step 3:
python -m pytest tests/test_executor_timing.py -q --tb=short

# Full suite:
python -m pytest tests/ -q --tb=short 2>&1 | tail -3

# Mutmut score (after WSL run completes):
wsl python3 -m mutmut results
```

## Expected Outcome
- +24 new depth pass tests (v8.3.14)
- +8 TASK-420 timing tests (v8.3.15)
- Mutmut score: target ≥92% (was 90.2% before batch 7, some survivors may be killed by new tests)
- Total: ~5458+ tests, 0 failures

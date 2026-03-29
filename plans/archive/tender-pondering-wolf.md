# Plan: AAWO + Solo Builder Integration

## Context
AAWO is a deterministic control plane that scores/selects agents and routes tasks using repo signals. Solo Builder is a DAG-based task executor with opportunistic runner dispatch. Currently Solo Builder has no explicit agent selection — it picks a runner (SDK/Claude/Anthropic) based on availability, not task semantics. Integrating AAWO gives Solo Builder:
1. **Intelligent routing** — `action_type` and `tools` auto-populated based on what AAWO thinks is the right agent for the task
2. **Repo health visibility** — AAWO snapshot signals surfaced in Solo Builder's `/health/detailed` API

---

## Approach: Subprocess Bridge (not Python import)

AAWO uses bare-name imports (no `__init__.py`), has a naming collision with Solo Builder on `models.py`, and requires `sys.path` mutation. Import is not viable. Instead:
- Add `--json` output flag to AAWO's `route` and `snapshot` subcommands
- Create a thin `aawo_bridge.py` in Solo Builder that spawns AAWO via subprocess and parses JSON stdout
- Graceful fallback (returns `None`) if AAWO is unavailable or times out

---

## Implementation Steps

### Step 1: AAWO — Add `--json` flag
**File:** `Autonomous Agent Workflow Orchestrator/agent-runtime/main.py`

Add `--json` argparse flag to the `route` and `snapshot` subcommand parsers. When passed, emit a single JSON object to stdout instead of human-readable output.

`route --json` output shape:
```json
{
  "task": "...",
  "selected_agent_id": "testing_agent",
  "score": 3.0,
  "reasoning": ["keyword match: 'test'"],
  "fallback": false,
  "policy_blocked": false
}
```

`snapshot --json` output shape: the existing `_snapshot_to_dict` return value, `json.dumps`'d.

Verify manually: `python agent-runtime/main.py route --task "run tests" --json`

---

### Step 2: Bridge Module (new file)
**File:** `Solo Builder/solo_builder/utils/aawo_bridge.py`

Key functions:
```python
def route_task(description: str, repo_path: str = ".") -> Optional[dict]
def get_snapshot(repo_path: str = ".") -> Optional[dict]
def enrich_subtask(st_data: dict, description: str, repo_path: str = ".") -> dict
def resolve_executor_config(agent_id: str) -> Optional[dict]
```

`enrich_subtask` logic:
- If `st_data` already has both `action_type` and `tools` → return unchanged (never override explicit authoring)
- Call `route_task(description)` → get `selected_agent_id`
- Look up agent in `_BUILTIN_MAPPING` → get `{"action_type": ..., "tools": ...}`
- Inject into `st_data`; store routing metadata in `st_data["_aawo_routing"]`
- Return `st_data` unchanged on any failure

Builtin agent → Solo Builder mapping:
| AAWO Agent | action_type | tools |
|---|---|---|
| testing_agent | read_only | Read,Grep,Glob |
| security_agent | analysis | Read,Grep,Glob,Bash |
| devops_agent | file_edit | Read,Grep,Glob,Bash,Write,Edit |
| architect_agent | full_execution | Read,Grep,Glob,Bash,Write,Edit,WebFetch,WebSearch |
| orchestration_agent | analysis | Read,Grep,Glob,Bash |
| repo_analyzer_agent | read_only | Read,Grep,Glob |

Override via `settings.json` key `"AAWO_AGENT_MAPPING"` (optional).

Security: subprocess always uses `shell=False` with explicit args list.

AAWO path resolved from: `AAWO_RUNTIME_PATH` env var, else sibling directory (`../Autonomous Agent Workflow Orchestrator/agent-runtime/main.py`). Returns `None` if not found.

---

### Step 3: Executor Wiring
**File:** `Solo Builder/solo_builder/runners/executor.py`

Add `aawo_repo_path: str = "."` param to `Executor.__init__`.

In `execute_step`, in the `elif status == "Running":` block, **after** reading `st_tools`, `description`, `action_type` from `st_data` and **before** the HITL gate:

```python
# AAWO enrichment — only when subtask has no explicit config
if not (st_tools and action_type):
    from utils.aawo_bridge import enrich_subtask as _aawo_enrich
    _aawo_enrich(st_data, description, repo_path=self._aawo_repo_path)
    st_tools    = st_data.get("tools", "").strip()
    action_type = st_data.get("action_type", "").strip()

# existing HITL gate continues...
if st_tools:
```

Update `Executor` instantiation in `solo_builder_cli.py` to pass `aawo_repo_path="."`.

---

### Step 4: Health Endpoint — `repo_health` Check
**File:** `Solo Builder/solo_builder/api/blueprints/health_detailed.py`

Add a fifth check block after the existing four (`state_valid`, `config_drift`, `metrics_alerts`, `slo_status`), following the same `try/except Exception` pattern:

```python
try:
    from utils.aawo_bridge import get_snapshot as _aawo_snapshot
    _snap = _aawo_snapshot(repo_path=".")
    if _snap:
        repo_health_check = {
            "ok": True, "available": True,
            "signals": _snap.get("signals", {}),
            "complexity": _snap.get("complexity", {}).get("value", "unknown"),
            "file_count": _snap.get("complexity", {}).get("file_count", 0),
            "risk_factors": _snap.get("risk_factors", []),
            "captured_at": _snap.get("captured_at", ""),
        }
    else:
        repo_health_check = {"ok": True, "available": False, "signals": {}, "risk_factors": []}
except Exception as exc:
    repo_health_check = {"ok": True, "available": False, "error": str(exc)}
```

Add `"repo_health": repo_health_check` to the `checks` dict. `repo_health.ok` is always `True` — AAWO unavailability is informational, never a health gate failure. `overall_ok` excludes `repo_health` explicitly.

---

### Step 5: Settings (optional config)
**File:** `Solo Builder/solo_builder/config/settings.json`

Optionally add:
```json
"AAWO_TIMEOUT": 10,
"AAWO_REPO_PATH": ".",
"AAWO_AGENT_MAPPING": {}
```
Bridge works with defaults if these keys are absent.

---

## Files Changed

| File | Change |
|---|---|
| `AAWO/agent-runtime/main.py` | Add `--json` flag to `route` + `snapshot` subcommand parsers |
| `SB/utils/aawo_bridge.py` | **New file** — bridge module |
| `SB/runners/executor.py` | Add `aawo_repo_path` param; insert `enrich_subtask` call before HITL gate |
| `SB/api/blueprints/health_detailed.py` | Add `repo_health` check block |
| `SB/config/settings.json` | Add optional AAWO config keys |

---

## Tests to Write

### `SB/tests/test_aawo_bridge.py` (~16 tests)
- `test_route_task_returns_dict_on_success` — subprocess returns valid JSON → parsed dict returned
- `test_route_task_returns_none_on_timeout` — `TimeoutExpired` → None
- `test_route_task_returns_none_on_nonzero_exit` — rc=1 → None
- `test_route_task_returns_none_when_aawo_not_found` — path doesn't exist → None
- `test_route_task_returns_none_on_json_error` — invalid stdout → None
- `test_get_snapshot_returns_dict_on_success`
- `test_get_snapshot_returns_none_on_timeout`
- `test_enrich_subtask_sets_action_type_and_tools` — mocked `route_task` returns `testing_agent` → st_data enriched
- `test_enrich_subtask_skips_if_already_configured` — both fields set → no subprocess called
- `test_enrich_subtask_skips_on_policy_blocked`
- `test_enrich_subtask_skips_on_none`
- `test_resolve_executor_config_known_agent` — `testing_agent` → correct dict
- `test_resolve_executor_config_unknown_agent` → None
- `test_load_mapping_merges_settings_override`
- `test_subprocess_uses_shell_false` — security invariant
- `test_subprocess_args_is_list` — security invariant

### `SB/tests/test_health_detailed.py` — new class (~7 tests)
- `test_repo_health_key_present`
- `test_repo_health_available_false_when_none`
- `test_repo_health_available_true_when_snapshot_returned`
- `test_repo_health_signals_propagated`
- `test_repo_health_ok_true_even_when_unavailable`
- `test_repo_health_exception_does_not_affect_overall_ok`
- `test_repo_health_risk_factors_propagated`

### Executor wiring tests (~3 tests)
- `test_executor_calls_enrich_when_subtask_missing_config`
- `test_executor_skips_enrich_when_subtask_has_both_fields`
- `test_executor_uses_aawo_enriched_tools_in_hitl_gate`

Total: ~26 new tests across both projects.

---

## Verification

1. `python agent-runtime/main.py route --task "add tests" --json` → clean JSON output
2. `python agent-runtime/main.py snapshot --repo . --json` → clean JSON output
3. In Solo Builder: `python -m pytest tests/test_aawo_bridge.py -v` → all pass
4. Create a subtask with no `action_type`/`tools`, run one executor step, confirm `_aawo_routing` key appears in st_data
5. `curl localhost:5000/health/detailed | jq .checks.repo_health` → `available: true` with signals
6. Kill AAWO (rename main.py), re-run step 4 → subtask proceeds unchanged (graceful fallback)
7. Full test suite: `python -m pytest tests/ -v` → all existing + new tests pass

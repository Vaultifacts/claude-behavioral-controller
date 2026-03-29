# Quality Gate Monitor — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 functional backbone — session state, notification router, Layers 0/ENV/1/1.5/2/3/4, and a `qg monitor` dashboard — delivering TP/FP/FN/TN classification, mid-task monitoring, and per-session quality scores.

**Architecture:** New components are standalone Python hook scripts plus two shared modules (`qg_session_state.py`, `qg_notification_router.py`). Existing `precheck-hook.py` and `quality-gate.py` are extended in-place; new hooks are separate files. Session state is a JSON file with `O_CREAT|O_EXCL` atomic locking (Windows-compatible, no `fcntl`). Layer 3 FN detection in Phase 1 is rule-based (LAZINESS text + MEMORY_OVER_VERIFICATION); Haiku FN prompt extension deferred to Phase 2.

**Tech Stack:** Python 3.13, JSON, Claude Code hooks (SessionStart / UserPromptSubmit / PreToolUse / PostToolUse / Stop), pytest 8.3.4

**Spec:** `~/.claude/docs/superpowers/specs/2026-03-28-quality-monitor-design.md`

---

## Implementation Notes

1. **Write-protected paths:** `~/.claude/hooks/` and `~/.claude/settings.json` block Claude's Write/Edit tools. Write all hook files using the **staging pattern**: Write tool → `~/.claude/scripts/staging/<file>.py`, then `cp` via Bash. Settings registration uses the `update-config` skill.

2. **Staging pattern:**
   ```bash
   cp ~/.claude/scripts/staging/qg_foo.py ~/.claude/hooks/qg_foo.py
   ```

3. **Test location:** `~/.claude/scripts/tests/`. Import hook modules via:
   ```python
   sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
   ```

4. **Run tests:** `PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/<file>.py -v`

5. **Run regression battery:** `PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-regression.py`

6. **Hook stdout conventions:**
   - SessionStart / UserPromptSubmit: plain text stdout → injected as additionalContext
   - PreToolUse: `{"decision": "block", "reason": "..."}` to block; `{"additionalContext": "..."}` to advise; nothing to pass
   - PostToolUse: nothing (logging only)
   - Stop: `{"decision": "block", "reason": "..."}` or `{"continue": true}`

7. **quality-gate.py SMOKE comment IDs** are stable anchors for patching: `# SMOKE:13` (mechanical block print) and `# SMOKE:9` (LLM block print). Use these to locate exact lines.

---

## File Structure

### New Files
| File | Responsibility |
|---|---|
| `~/.claude/qg-rules.json` | All tunable config for all layers |
| `~/.claude/hooks/qg_session_state.py` | Session state: read/write/lock/migrate/prune |
| `~/.claude/hooks/qg_notification_router.py` | Priority routing, dedup, CRITICAL queuing |
| `~/.claude/hooks/qg_layer0.py` | SessionStart: inject previous session unresolved events |
| `~/.claude/hooks/qg_layer_env.py` | SessionStart + PreToolUse: environment validation |
| `~/.claude/hooks/qg_layer15.py` | PreToolUse: tool use rule validation |
| `~/.claude/hooks/qg_layer2.py` | PostToolUse: mid-task monitoring (8 categories) |
| `~/.claude/hooks/precheck_hook_ext.py` | Testable helper functions for Layer 1 (DEEP heuristic, Jaccard) |
| `~/.claude/scripts/tests/test_qg_session_state.py` | Unit tests: session state |
| `~/.claude/scripts/tests/test_qg_notification_router.py` | Unit tests: notification router |
| `~/.claude/scripts/tests/test_qg_layers.py` | Unit tests: Layers 1/1.5/2/ENV |

### Modified Files
| File | Change |
|---|---|
| `~/.claude/hooks/precheck-hook.py` | Layer 1: DEEP heuristic, Jaccard pivot, success criteria, FN injection, SCOPE_CREEP clearing |
| `~/.claude/hooks/quality-gate.py` | Layer 3: TP/FP/FN/TN classification + Layer 4: rolling session summary (appended after line 905) |
| `~/.claude/scripts/qg-feedback.py` | New subcommands: `qg monitor`, `qg analyze`, `qg integrity`, `qg rules` |
| `~/.claude/settings.json` | 5 new hook registrations (via update-config skill) |

---

### Task 0: Scaffold

**Files:**
- Create: `~/.claude/qg-rules.json`
- Create dirs: `~/.claude/scripts/tests/`, `~/.claude/scripts/staging/`

- [ ] **Step 1: Create directories**
```bash
mkdir -p ~/.claude/scripts/tests ~/.claude/scripts/staging
```

- [ ] **Step 2: Write `~/.claude/qg-rules.json`** (use Write tool — not in hooks dir):
```json
{
  "schema_version": 1,
  "layer0": {
    "injection_max_chars": 2000,
    "pattern_retirement_sessions": 5
  },
  "layer1": {
    "deep_min_length": 300,
    "deep_scope_keywords": ["redesign", "migrate", "refactor all", "rewrite", "rebuild", "overhaul"],
    "codebase_scan_timeout_sec": 3
  },
  "layer15": {
    "repeat_violation_threshold": 3,
    "rules": [
      {"id": "edit-without-read", "condition": "edit_without_read", "action": "warn"},
      {"id": "bash-instead-of-tool", "condition": "bash_grep_cat_find", "action": "info"},
      {"id": "write-outside-scope", "condition": "write_outside_scope", "action": "warn"}
    ]
  },
  "layer2": {
    "events_per_turn_limit": 5,
    "loop_same_tool_count": 3,
    "loop_same_dir_count": 5
  },
  "layer4": {
    "session_retention_count": 30,
    "quality_score_weights": {"fn": 3, "l2_critical": 2, "fp": 1},
    "category_complexity_weights": {
      "MECHANICAL": 1.0, "ASSUMPTION": 1.0,
      "OVERCONFIDENCE": 1.2, "PLANNING": 1.3, "DEEP": 1.5
    }
  },
  "layer6": {"pattern_min_sessions": 3, "pattern_min_pct": 15, "pattern_retirement_sessions": 3},
  "layer9": {"calibration_staleness_sessions": 30, "min_responses_before_recalibration": 5},
  "layer10": {"rotation_threshold_lines": 10000, "integrity_check_interval_days": 7}
}
```

- [ ] **Step 3: Commit**
```bash
cd ~/.claude && git add qg-rules.json scripts/tests/ scripts/staging/
git commit -m "feat(qg-monitor): scaffold phase 1 — qg-rules.json, test/staging dirs [AUTO]"
```

---

### Task 1: Session State Module

**Files:**
- Create: `~/.claude/scripts/staging/qg_session_state.py` → `~/.claude/hooks/qg_session_state.py`
- Create: `~/.claude/scripts/tests/test_qg_session_state.py`

- [ ] **Step 1: Write failing tests** — create `~/.claude/scripts/tests/test_qg_session_state.py`:
```python
import sys, os, time, tempfile, unittest
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss

class TestSessionState(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def tearDown(self):
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def test_read_returns_empty_when_file_missing(self):
        state = ss.read_state()
        self.assertIsNone(state['session_uuid'])
        self.assertEqual(state['schema_version'], 1)
        self.assertIn('notification_pending_criticals', state)

    def test_write_and_read_roundtrip(self):
        state = ss.read_state()
        state['session_uuid'] = 'test-abc'
        ss.write_state(state)
        result = ss.read_state()
        self.assertEqual(result['session_uuid'], 'test-abc')

    def test_staleness_resets_on_old_file(self):
        state = ss.read_state()
        state['session_uuid'] = 'old-uuid'
        state['session_start_ts'] = time.time() - 90000  # 25h ago
        ss.write_state(state)
        result = ss.read_state()
        self.assertIsNone(result['session_uuid'])

    def test_update_state_partial(self):
        ss.update_state(session_uuid='xyz-789', active_task_id='t1')
        result = ss.read_state()
        self.assertEqual(result['session_uuid'], 'xyz-789')
        self.assertEqual(result['active_task_id'], 't1')

    def test_lock_silently_fails_on_contention(self):
        open(self.tmp + '.lock', 'w').close()  # Pre-create lock
        state = ss.read_state()
        state['session_uuid'] = 'should-not-persist'
        ss.write_state(state)  # Should silently fail — lock is held
        result = ss.read_state()
        self.assertIsNone(result['session_uuid'])  # Not written
        os.unlink(self.tmp + '.lock')

    def test_migration_adds_missing_fields(self):
        import json
        with open(self.tmp, 'w') as f:
            json.dump({'schema_version': 0, 'session_uuid': 'v0',
                       'session_start_ts': time.time()}, f)
        result = ss.read_state()
        self.assertIn('layer2_unresolved_events', result)
        self.assertIn('notification_pending_criticals', result)
        self.assertEqual(result['session_uuid'], 'v0')

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests — verify they fail**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_session_state.py -v 2>&1 | head -5
```
Expected: `ModuleNotFoundError: No module named 'qg_session_state'`

- [ ] **Step 3: Write implementation** — create `~/.claude/scripts/staging/qg_session_state.py`:
```python
#!/usr/bin/env python3
"""Session state management for Quality Gate Monitor.
Windows-compatible: uses O_CREAT|O_EXCL atomic lockfile instead of fcntl.
"""
import json, os, time

STATE_PATH = os.path.expanduser('~/.claude/qg-session-state.json')
LOCK_PATH = STATE_PATH + '.lock'
SCHEMA_VERSION = 1
MAX_SIZE_BYTES = 1_048_576  # 1MB


def _acquire_lock(timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(0.05)
    return False


def _release_lock():
    try:
        os.unlink(LOCK_PATH)
    except FileNotFoundError:
        pass


def _empty_state():
    return {
        'schema_version': SCHEMA_VERSION,
        'session_uuid': None,
        'session_start_ts': 0,
        'active_task_id': None,
        'active_subtask_id': None,
        'active_task_description': '',
        'task_success_criteria': [],
        'layer1_task_category': None,
        'layer1_scope_files': [],
        'layer2_unresolved_events': [],
        'layer2_elevated_scrutiny': False,
        'layer2_turn_event_count': 0,
        'layer2_turn_history': [],
        'layer15_session_reads': [],
        'layer15_override_pending': None,
        'layer15_turn_warnings': [],
        'layer15_violation_counts': {},
        'layer19_impact_cache': {},
        'layer35_recovery_events': [],
        'layer25_syntax_failure': False,
        'layer3_pending_fn_alert': None,
        'layer3_last_response_claims': [],
        'layer_env_baseline': {},
        'layer_env_test_baseline': [],
        'layer8_regression_expected': False,
        'last_integrity_check_ts': 0,
        'notification_delivery': [],
        'notification_pending_criticals': [],
    }


def _is_stale(data):
    return (time.time() - data.get('session_start_ts', 0)) > 86400


def _migrate(data):
    if data.get('schema_version', 0) >= SCHEMA_VERSION:
        return data
    for k, v in _empty_state().items():
        if k not in data:
            data[k] = v
    data['schema_version'] = SCHEMA_VERSION
    return data


def _prune_turn_scoped(data):
    # Only prune space-heavy session-scoped lists. Do NOT reset turn-scoped
    # dedup fields (layer15_turn_warnings, layer2_turn_event_count) — those are
    # tiny and resetting them mid-turn would cause Layer 1.5 to re-warn on
    # already-warned rules within the same turn.
    if data.get('layer2_unresolved_events'):
        data['layer2_unresolved_events'] = data['layer2_unresolved_events'][-10:]
    if data.get('notification_delivery'):
        data['notification_delivery'] = data['notification_delivery'][-20:]
    if data.get('layer3_last_response_claims'):
        data['layer3_last_response_claims'] = data['layer3_last_response_claims'][-5:]
    return data


def read_state():
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if _is_stale(data):
            return _empty_state()
        return _migrate(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_state()


def write_state(data):
    if not _acquire_lock():
        return  # Silent fail on lock contention
    try:
        data['schema_version'] = SCHEMA_VERSION
        content = json.dumps(data, ensure_ascii=False)
        if len(content.encode('utf-8')) > MAX_SIZE_BYTES:
            data = _prune_turn_scoped(data)
            content = json.dumps(data, ensure_ascii=False)
        with open(STATE_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
    finally:
        _release_lock()


def update_state(**kwargs):
    data = read_state()
    data.update(kwargs)
    write_state(data)
```

- [ ] **Step 4: Copy to hooks dir**
```bash
cp ~/.claude/scripts/staging/qg_session_state.py ~/.claude/hooks/qg_session_state.py
```

- [ ] **Step 5: Run tests — verify they pass**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_session_state.py -v
```
Expected: `6 passed`

- [ ] **Step 6: Commit**
```bash
cd ~/.claude
git add hooks/qg_session_state.py scripts/staging/qg_session_state.py scripts/tests/test_qg_session_state.py
git commit -m "feat(qg-monitor): add session state module with atomic locking and migration [AUTO]"
```

---

### Task 2: Notification Router

**Files:**
- Create: `~/.claude/scripts/staging/qg_notification_router.py` → `~/.claude/hooks/qg_notification_router.py`
- Create: `~/.claude/scripts/tests/test_qg_notification_router.py`

- [ ] **Step 1: Write failing tests** — create `~/.claude/scripts/tests/test_qg_notification_router.py`:
```python
import sys, os, tempfile, unittest
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
import qg_notification_router as router

class TestNotificationRouter(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'
        router.ss = ss
        router._turn_critical_count = 0
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def tearDown(self):
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except FileNotFoundError: pass

    def test_info_returns_none(self):
        result = router.notify('INFO', 'layer2', 'LAZINESS', 'foo.py', 'msg', 'pretooluse')
        self.assertIsNone(result)

    def test_critical_immediate_in_pretooluse(self):
        result = router.notify('CRITICAL', 'layer2', 'LOOP', 'foo.py', 'looping!', 'pretooluse')
        self.assertIsNotNone(result)
        self.assertIn('additionalContext', result)
        self.assertIn('looping!', result['additionalContext'])

    def test_critical_queued_from_stop(self):
        router.notify('CRITICAL', 'layer3', 'FN', None, 'missed failure', 'stop')
        state = ss.read_state()
        self.assertEqual(len(state['notification_pending_criticals']), 1)
        self.assertEqual(state['notification_pending_criticals'][0]['message'], 'missed failure')

    def test_dedup_within_60s(self):
        router.notify('WARNING', 'layer2', 'LAZINESS', 'foo.py', 'first', 'pretooluse')
        router.notify('WARNING', 'layer2', 'LAZINESS', 'foo.py', 'second', 'pretooluse')
        state = ss.read_state()
        dropped = [d for d in state['notification_delivery'] if d.get('status') == 'dropped']
        self.assertEqual(len(dropped), 1)

    def test_rate_limit_queues_4th_critical(self):
        for i in range(4):
            router.notify('CRITICAL', 'layer2', f'CAT{i}', f'f{i}.py', f'msg{i}', 'pretooluse')
        state = ss.read_state()
        queued = [p for p in state['notification_pending_criticals']]
        self.assertGreaterEqual(len(queued), 1)

    def test_flush_pending_criticals_clears_queue(self):
        router.notify('CRITICAL', 'layer3', 'FN', None, 'alert!', 'stop')
        result = router.flush_pending_criticals()
        self.assertIsNotNone(result)
        self.assertIn('alert!', result)
        state = ss.read_state()
        self.assertEqual(len(state['notification_pending_criticals']), 0)

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests — verify they fail**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_notification_router.py -v 2>&1 | head -5
```

- [ ] **Step 3: Write implementation** — create `~/.claude/scripts/staging/qg_notification_router.py`:
```python
#!/usr/bin/env python3
"""Notification Router for Quality Gate Monitor.
Priority: CRITICAL > WARNING > INFO
hook_context: 'pretooluse', 'posttooluse', 'stop', 'sessionstart', 'async'
"""
import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MAX_CRITICALS_PER_TURN = 3
DEDUP_WINDOW_SEC = 60
_turn_critical_count = 0


def _dedup_key(layer, category, file_path):
    return f'{layer}:{category}:{file_path or ""}'


def _is_duplicate(state, layer, category, file_path):
    key = _dedup_key(layer, category, file_path)
    now = time.time()
    for d in state.get('notification_delivery', []):
        if d.get('dedup_key') == key and (now - d.get('ts', 0)) < DEDUP_WINDOW_SEC:
            return True
    return False


def _record(state, layer, category, file_path, message, status):
    state.setdefault('notification_delivery', []).append({
        'dedup_key': _dedup_key(layer, category, file_path),
        'layer': layer, 'category': category, 'file': file_path,
        'message': message[:200], 'status': status, 'ts': time.time(),
    })


def notify(priority, layer, category, file_path, message, hook_context):
    """Route notification. Returns {'additionalContext': ...} for immediate CRITICAL, else None."""
    global _turn_critical_count

    state = ss.read_state()

    if priority == 'INFO':
        _record(state, layer, category, file_path, message, 'logged')
        ss.write_state(state)
        return None

    if _is_duplicate(state, layer, category, file_path):
        _record(state, layer, category, file_path, message, 'dropped')
        ss.write_state(state)
        return None

    if priority == 'WARNING':
        _record(state, layer, category, file_path, message, 'queued_warning')
        ss.write_state(state)
        return None

    # CRITICAL
    if hook_context in ('pretooluse', 'posttooluse'):
        if _turn_critical_count >= MAX_CRITICALS_PER_TURN:
            state.setdefault('notification_pending_criticals', []).append({
                'layer': layer, 'category': category, 'file': file_path,
                'message': message, 'ts': time.time(), 'status': 'queued',
            })
            _record(state, layer, category, file_path, message, 'queued')
            ss.write_state(state)
            return None
        _turn_critical_count += 1
        _record(state, layer, category, file_path, message, 'delivered')
        ss.write_state(state)
        return {'additionalContext': f'[monitor:CRITICAL:{layer}:{category}] {message}'}
    else:
        # stop / sessionstart / async — queue for next PreToolUse
        state.setdefault('notification_pending_criticals', []).append({
            'layer': layer, 'category': category, 'file': file_path,
            'message': message, 'ts': time.time(), 'status': 'queued',
        })
        _record(state, layer, category, file_path, message, 'queued')
        ss.write_state(state)
        return None


def flush_pending_criticals():
    """Flush up to 3 queued CRITICALs. Called by Layer 1.5 at PreToolUse entry."""
    state = ss.read_state()
    pending = state.get('notification_pending_criticals', [])
    if not pending:
        return None
    batch = pending[:3]
    state['notification_pending_criticals'] = pending[3:]
    for p in batch:
        p['status'] = 'delivered'
    ss.write_state(state)
    lines = [f"[monitor:CRITICAL:{p['layer']}:{p['category']}] {p['message']}" for p in batch]
    return '\n'.join(lines)


def flush_warnings():
    """Collect queued WARNINGs for Stop-time batch delivery. Returns text or None."""
    state = ss.read_state()
    warnings = [d for d in state.get('notification_delivery', [])
                if d.get('status') == 'queued_warning']
    if not warnings:
        return None
    for d in warnings:
        d['status'] = 'delivered'
    ss.write_state(state)
    return '\n'.join(f"[monitor:WARNING:{w['layer']}:{w['category']}] {w['message']}"
                     for w in warnings)


def reset_turn_counter():
    global _turn_critical_count
    _turn_critical_count = 0
```

- [ ] **Step 4: Copy to hooks dir**
```bash
cp ~/.claude/scripts/staging/qg_notification_router.py ~/.claude/hooks/qg_notification_router.py
```

- [ ] **Step 5: Run tests**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_notification_router.py -v
```
Expected: `6 passed`

- [ ] **Step 6: Commit**
```bash
cd ~/.claude
git add hooks/qg_notification_router.py scripts/staging/qg_notification_router.py scripts/tests/test_qg_notification_router.py
git commit -m "feat(qg-monitor): add notification router with dedup, rate limiting, CRITICAL queuing [AUTO]"
```

---

### Task 3: Layer ENV — Environment Validation

**Files:**
- Create: `~/.claude/scripts/staging/qg_layer_env.py` → `~/.claude/hooks/qg_layer_env.py`
- Create: `~/.claude/scripts/tests/test_qg_layers.py` (initial ENV tests)

- [ ] **Step 1: Write failing tests** — create `~/.claude/scripts/tests/test_qg_layers.py`:
```python
import sys, os, tempfile, unittest
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))


class TestLayerEnvValidation(unittest.TestCase):
    def test_validate_git_branch_match(self):
        from qg_layer_env import validate_git_branch
        ok, msg = validate_git_branch('main', lambda: 'main')
        self.assertTrue(ok)

    def test_validate_git_branch_mismatch(self):
        from qg_layer_env import validate_git_branch
        ok, msg = validate_git_branch('main', lambda: 'feature/foo')
        self.assertFalse(ok)
        self.assertIn('main', msg)

    def test_validate_required_tools_present(self):
        from qg_layer_env import validate_required_tools
        ok, missing = validate_required_tools(['python', 'git'])
        self.assertTrue(ok)
        self.assertEqual(missing, [])

    def test_validate_required_tools_missing(self):
        from qg_layer_env import validate_required_tools
        ok, missing = validate_required_tools(['nonexistent_tool_qg_xyz'])
        self.assertFalse(ok)
        self.assertIn('nonexistent_tool_qg_xyz', missing)

    def test_validate_env_var_present(self):
        from qg_layer_env import validate_env_vars
        os.environ['QG_TEST_VAR_PHASE1'] = 'yes'
        ok, missing = validate_env_vars(['QG_TEST_VAR_PHASE1'])
        del os.environ['QG_TEST_VAR_PHASE1']
        self.assertTrue(ok)

    def test_validate_env_var_missing(self):
        from qg_layer_env import validate_env_vars
        ok, missing = validate_env_vars(['QG_DEFINITELY_NOT_SET_XYZ'])
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run tests — verify they fail**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py -v 2>&1 | head -5
```

- [ ] **Step 3: Write implementation** — create `~/.claude/scripts/staging/qg_layer_env.py`:
```python
#!/usr/bin/env python3
"""Layer ENV — Environment Validation.
SessionStart: validates environment, captures baseline.
PreToolUse: re-validates if file path is outside working directory.
Dispatches on payload['hook_event_name'].
"""
import json, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

ENV_CONFIG_PATH = os.path.expanduser('~/.claude/qg-env.json')


def validate_git_branch(expected_branch, get_branch_fn=None):
    """Returns (ok, message). Testable via get_branch_fn injection."""
    if get_branch_fn is None:
        try:
            r = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                               capture_output=True, text=True, timeout=3)
            current = r.stdout.strip()
        except Exception:
            return True, ''  # Non-git or git unavailable — not an error
    else:
        current = get_branch_fn()
    if current == expected_branch:
        return True, ''
    return False, f'Expected branch {expected_branch!r}, current is {current!r}'


def validate_required_tools(tools):
    """Returns (ok, missing_list)."""
    missing = [t for t in tools if shutil.which(t) is None]
    return (not missing), missing


def validate_env_vars(vars_list):
    """Returns (ok, missing_list)."""
    missing = [v for v in vars_list if not os.environ.get(v)]
    return (not missing), missing


def load_env_config():
    try:
        with open(ENV_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_session_start(payload):
    config = load_env_config()
    baseline = {'working_dir': os.getcwd(), 'ts': time.time()}
    messages = []

    if config:
        expected_branch = config.get('git_branch')
        if expected_branch and not config.get('skip_git', False):
            ok, msg = validate_git_branch(expected_branch)
            if not ok:
                sev = config.get('git_branch_severity', 'warning').upper()
                messages.append(f'[ENV:{sev}] Git branch: {msg}')

        required_tools = config.get('required_tools', [])
        if required_tools:
            ok, missing = validate_required_tools(required_tools)
            if not ok:
                messages.append(f'[ENV:WARNING] Missing tools: {", ".join(missing)}')

        required_env = config.get('required_env_vars', [])
        if required_env:
            ok, missing = validate_env_vars(required_env)
            if not ok:
                messages.append(f'[ENV:WARNING] Missing env vars: {", ".join(missing)}')

        if config.get('working_dir'):
            baseline['working_dir'] = config['working_dir']

    ss.update_state(layer_env_baseline=baseline)
    if messages:
        print('\n'.join(messages))


def run_pre_tool_use(payload):
    tool_input = payload.get('tool_input', {})
    fp = tool_input.get('file_path', '') or tool_input.get('path', '')
    if not fp:
        return
    state = ss.read_state()
    wd = state.get('layer_env_baseline', {}).get('working_dir', '')
    if not wd:
        return
    norm_fp = os.path.normpath(os.path.abspath(fp))
    norm_wd = os.path.normpath(os.path.abspath(wd))
    if not norm_fp.startswith(norm_wd):
        print(json.dumps({'additionalContext':
            f'[ENV:WARNING] {fp!r} is outside working directory {wd!r}'}))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    event = payload.get('hook_event_name', '')
    if event == 'SessionStart':
        run_session_start(payload)
    elif event == 'PreToolUse':
        run_pre_tool_use(payload)


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Copy to hooks dir**
```bash
cp ~/.claude/scripts/staging/qg_layer_env.py ~/.claude/hooks/qg_layer_env.py
```

- [ ] **Step 5: Run tests**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py::TestLayerEnvValidation -v
```
Expected: `6 passed`

- [ ] **Step 6: Commit**
```bash
cd ~/.claude
git add hooks/qg_layer_env.py scripts/staging/qg_layer_env.py scripts/tests/test_qg_layers.py
git commit -m "feat(qg-monitor): add layer ENV environment validation hook [AUTO]"
```

---

### Task 4: Layer 0 — Session Start Context Injection

**Files:**
- Create: `~/.claude/scripts/staging/qg_layer0.py` → `~/.claude/hooks/qg_layer0.py`

- [ ] **Step 1: Write implementation** — create `~/.claude/scripts/staging/qg_layer0.py`:
```python
#!/usr/bin/env python3
"""Layer 0 — Session Start Context Injection.
Phase 1: injects unresolved events from previous session (item 7 of spec).
Items 1-6 (cross-session pattern injection via qg-cross-session.json) are
no-ops until Phase 3 when Layer 6 is implemented.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

HISTORY_PATH = os.path.expanduser('~/.claude/qg-session-history.md')
SESSION_UUID_RE = re.compile(r'^session_uuid:\s*(\S+)', re.MULTILINE)
UNRESOLVED_RE = re.compile(r'^- UNRESOLVED:\s*(.+)', re.MULTILINE)


def find_previous_session_unresolved():
    """Find unresolved items from most recent previous session entry."""
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []

    state = ss.read_state()
    current_uuid = state.get('session_uuid')

    entries = re.split(r'(?=^## Session )', content, flags=re.MULTILINE)
    for entry in entries:
        uuids = SESSION_UUID_RE.findall(entry)
        if not uuids:
            continue
        if uuids[0] == current_uuid:
            continue
        return UNRESOLVED_RE.findall(entry)
    return []


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    # Phase 1: items 1-6 (qg-cross-session.json) are no-ops
    # Item 7: inject unresolved events from previous session
    unresolved = find_previous_session_unresolved()
    if unresolved:
        lines = ['[monitor:Layer0] Unresolved issues from previous session (highest priority):']
        for item in unresolved[:5]:
            lines.append(f'  - {item}')
        print('\n'.join(lines))


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: Copy to hooks dir**
```bash
cp ~/.claude/scripts/staging/qg_layer0.py ~/.claude/hooks/qg_layer0.py
```

- [ ] **Step 3: Smoke test**
```bash
echo '{"hook_event_name": "SessionStart"}' | PYTHONIOENCODING=utf-8 python ~/.claude/hooks/qg_layer0.py
```
Expected: No output (no history file yet). Exit 0.

- [ ] **Step 4: Commit**
```bash
cd ~/.claude
git add hooks/qg_layer0.py scripts/staging/qg_layer0.py
git commit -m "feat(qg-monitor): add layer 0 session start context injection hook [AUTO]"
```

---

### Task 5: Layer 1 Extension — precheck-hook.py

**Files:**
- Create: `~/.claude/scripts/staging/precheck_hook_ext.py` → `~/.claude/hooks/precheck_hook_ext.py`
- Rewrite: `~/.claude/scripts/staging/precheck-hook.py` → `~/.claude/hooks/precheck-hook.py`
- Add tests to: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Add Layer 1 tests** (append to `test_qg_layers.py`):
```python
class TestLayer1Pivot(unittest.TestCase):
    def test_same_topic_not_a_pivot(self):
        from precheck_hook_ext import jaccard_similarity
        score = jaccard_similarity("fix the login bug in auth.py", "fix the login button color")
        self.assertGreaterEqual(score, 0.3)

    def test_different_topic_is_pivot(self):
        from precheck_hook_ext import jaccard_similarity
        score = jaccard_similarity("fix login bug", "create dashboard component with charts")
        self.assertLess(score, 0.3)

    def test_empty_active_task_never_pivot(self):
        from precheck_hook_ext import jaccard_similarity
        score = jaccard_similarity("", "do something")
        self.assertGreaterEqual(score, 0.3)


class TestLayer1Deep(unittest.TestCase):
    def test_short_message_not_deep(self):
        from precheck_hook_ext import detect_deep
        self.assertFalse(detect_deep("fix typo in readme"))

    def test_long_with_scope_keyword_is_deep(self):
        from precheck_hook_ext import detect_deep
        msg = "Please migrate the entire authentication " * 15 + " redesign all routes"
        self.assertTrue(detect_deep(msg))

    def test_long_without_scope_keyword_not_deep(self):
        from precheck_hook_ext import detect_deep
        msg = "Please update the documentation for all the functions we added " * 10
        self.assertFalse(detect_deep(msg))
```

- [ ] **Step 2: Run tests — verify they fail**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py::TestLayer1Pivot ~/.claude/scripts/tests/test_qg_layers.py::TestLayer1Deep -v 2>&1 | head -5
```

- [ ] **Step 3: Write `precheck_hook_ext.py`** — create `~/.claude/scripts/staging/precheck_hook_ext.py`:
```python
#!/usr/bin/env python3
"""Testable helper functions for precheck-hook.py Layer 1 extension."""
import json, os, re


def tokenize(text):
    return set(re.findall(r'\b\w+\b', text.lower()))


def jaccard_similarity(text_a, text_b):
    """Jaccard similarity [0,1]. Empty text_a returns 1.0 (not a pivot)."""
    if not text_a.strip():
        return 1.0
    a, b = tokenize(text_a), tokenize(text_b)
    union = len(a | b)
    return len(a & b) / union if union > 0 else 1.0


def detect_deep(message):
    """Heuristic: message is DEEP if long enough AND contains a scope keyword."""
    try:
        with open(os.path.expanduser('~/.claude/qg-rules.json'), 'r', encoding='utf-8') as f:
            rules = json.load(f).get('layer1', {})
        min_len = rules.get('deep_min_length', 300)
        keywords = rules.get('deep_scope_keywords',
                             ["redesign", "migrate", "refactor all", "rewrite", "rebuild"])
    except Exception:
        min_len, keywords = 300, ["redesign", "migrate", "refactor all", "rewrite", "rebuild"]
    if len(message) < min_len:
        return False
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in keywords)


def infer_scope_files(message):
    """Extract file paths mentioned in the request."""
    return re.findall(r'[\w./\\-]+\.(?:py|js|ts|json|yaml|yml|md|sh|txt|html|css)', message)
```

- [ ] **Step 4: Write updated `precheck-hook.py`** — create `~/.claude/scripts/staging/precheck-hook.py`:
```python
#!/usr/bin/env python3
"""Pre-check hook: classifies user request and enforces Layer 1 pre-task behaviors."""
import json, os, re, sys, time, urllib.request, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from precheck_hook_ext import jaccard_similarity, detect_deep, infer_scope_files

DIRECTIVES = {
    "OVERCONFIDENCE": "Before citing test results, counts, or specific outputs — run the command and quote the result inline.",
    "ASSUMPTION": "Before claiming anything about code, file contents, or system state — use Grep or Read to verify first.",
    "MECHANICAL": "Before editing or writing a file — use the Read tool to read it first.",
    "PLANNING": "Before listing next steps — verify each candidate item is not already implemented using Grep or Bash. Never suggest items from memory without checking current code.",
    "DEEP": "This is a DEEP task. Read relevant files before planning. Confirm scope. Do not start editing until you understand what exists.",
}

PROMPT = """Classify this user request into ONE category:

OVERCONFIDENCE: Response will cite specific test counts, file counts, line numbers, or command outputs without running tools.
ASSUMPTION: Response will describe code behavior, function signatures, or file contents without reading files.
MECHANICAL: Response will edit, create, or modify files.
PLANNING: Response will suggest next steps, remaining work, or what to do next.
NONE: General questions, conversation, or tasks that do not fit the above.

Request: "{message}"

One word only: OVERCONFIDENCE, ASSUMPTION, MECHANICAL, PLANNING, or NONE."""


def extract_message(payload):
    msg = payload.get("message", payload.get("prompt", ""))
    if isinstance(msg, dict):
        return msg.get("content", "") or msg.get("text", "")
    if isinstance(msg, list):
        for block in msg:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
        return ""
    return msg if isinstance(msg, str) else ""


def _run_layer1(message, category, state):
    """Layer 1: update session state, return extra output lines."""
    extra = []

    # Behavior 11: deliver pending FN alert from previous turn
    fn_alert = state.get('layer3_pending_fn_alert')
    if fn_alert:
        extra.append(fn_alert)
        state['layer3_pending_fn_alert'] = None

    # Behavior 10: SCOPE_CREEP clearing on explicit user approval
    approval_kws = ('proceed', "that's fine", 'go ahead', 'continue', 'ok')
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in approval_kws):
        state['layer2_unresolved_events'] = [
            e for e in state.get('layer2_unresolved_events', [])
            if e.get('category') != 'SCOPE_CREEP'
        ]

    # Pivot detection (behavior 4+5)
    active_desc = state.get('active_task_description', '')
    pivot = jaccard_similarity(active_desc, message) < 0.3 if active_desc else False
    if pivot:
        state['active_task_id'] = str(uuid.uuid4())[:8]
        state['layer2_unresolved_events'] = [
            e for e in state.get('layer2_unresolved_events', [])
            if e.get('category') != 'SCOPE_CREEP'
        ]

    # Update active task context
    state['active_task_description'] = message
    state['layer1_task_category'] = category

    # Infer scope files (behavior 2)
    scope = infer_scope_files(message)
    if scope:
        state['layer1_scope_files'] = scope

    # Success criteria stub (behavior 3)
    state['task_success_criteria'] = [f'Task classified as {category}. Criteria TBD (Phase 2).']

    # Reset per-turn counters on new user turn
    state['layer2_turn_event_count'] = 0
    state['layer15_turn_warnings'] = []

    return extra, state


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    message = extract_message(payload).strip()
    if len(message) < 5:
        return

    # Existing Ollama classification (unchanged)
    body = json.dumps({
        "model": "qwen2.5:7b-instruct",
        "prompt": PROMPT.format(message=message[:500]),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 10},
    }).encode()

    category = "NONE"
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = json.loads(resp.read()).get("response", "").strip().upper()
        category = raw.split()[0] if raw else "NONE"
    except Exception:
        pass

    # DEEP override: runs after Ollama
    if detect_deep(message):
        category = "DEEP"

    output_lines = []
    directive = DIRECTIVES.get(category)
    if directive:
        output_lines.append(f"[pre-check:{category}] {directive}")

    # Layer 1 session state update
    try:
        import qg_session_state as _ss
        state = _ss.read_state()
        if not state.get('session_uuid'):
            state['session_uuid'] = str(uuid.uuid4())[:8]
            state['session_start_ts'] = time.time()
            state['active_task_id'] = str(uuid.uuid4())[:8]
        extra, state = _run_layer1(message, category, state)
        output_lines = extra + output_lines
        _ss.write_state(state)
    except Exception:
        pass

    for line in output_lines:
        print(line)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Copy both files to hooks dir**
```bash
cp ~/.claude/scripts/staging/precheck_hook_ext.py ~/.claude/hooks/precheck_hook_ext.py
cp ~/.claude/scripts/staging/precheck-hook.py ~/.claude/hooks/precheck-hook.py
```

- [ ] **Step 6: Run Layer 1 tests**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py::TestLayer1Pivot ~/.claude/scripts/tests/test_qg_layers.py::TestLayer1Deep -v
```
Expected: `6 passed`

- [ ] **Step 7: Smoke test the hook**
```bash
echo '{"message": "fix the typo in readme.md"}' | PYTHONIOENCODING=utf-8 python ~/.claude/hooks/precheck-hook.py
```
Expected: `[pre-check:MECHANICAL] Before editing or writing a file...`

- [ ] **Step 8: Commit**
```bash
cd ~/.claude
git add hooks/precheck-hook.py hooks/precheck_hook_ext.py scripts/staging/precheck-hook.py scripts/staging/precheck_hook_ext.py
git commit -m "feat(qg-monitor): extend precheck-hook.py with layer 1 — DEEP heuristic, pivot detection, FN injection [AUTO]"
```

---

### Task 6: Layer 1.5 — PreToolUse Validation

**Files:**
- Create: `~/.claude/scripts/staging/qg_layer15.py` → `~/.claude/hooks/qg_layer15.py`
- Add tests to: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Add Layer 1.5 tests** (append to `test_qg_layers.py`):
```python
class TestLayer15Rules(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except: pass

    def test_edit_without_read_triggers_warn(self):
        from qg_layer15 import evaluate_rules
        import qg_session_state as ss
        state = ss.read_state()  # No reads in session
        result = evaluate_rules('Edit', {'file_path': 'foo.py'}, state)
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'warn')
        self.assertEqual(result['rule_id'], 'edit-without-read')

    def test_edit_with_prior_read_passes(self):
        from qg_layer15 import evaluate_rules
        import qg_session_state as ss
        state = ss.read_state()
        state['layer15_session_reads'] = ['foo.py']
        result = evaluate_rules('Edit', {'file_path': 'foo.py'}, state)
        self.assertIsNone(result)

    def test_bash_grep_triggers_info(self):
        from qg_layer15 import evaluate_rules
        import qg_session_state as ss
        state = ss.read_state()
        result = evaluate_rules('Bash', {'command': 'grep -r foo .'}, state)
        self.assertIsNotNone(result)
        self.assertEqual(result['action'], 'info')

    def test_read_tracking_updates_state(self):
        from qg_layer15 import handle_read_tracking
        import qg_session_state as ss
        ss.update_state()
        handle_read_tracking('Read', {'file_path': 'bar.py'})
        state = ss.read_state()
        self.assertIn('bar.py', state['layer15_session_reads'])
```

- [ ] **Step 2: Run tests — verify they fail**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py::TestLayer15Rules -v 2>&1 | head -5
```

- [ ] **Step 3: Write implementation** — create `~/.claude/scripts/staging/qg_layer15.py`:
```python
#!/usr/bin/env python3
"""Layer 1.5 — PreToolUse Rule Validation.
Warns or blocks based on rules in qg-rules.json.
Flushes queued CRITICALs from Stop/async contexts at entry.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss
import qg_notification_router as router

RULES_PATH = os.path.expanduser('~/.claude/qg-rules.json')
BASH_TOOL_RE = re.compile(r'\b(grep|cat|find|head|tail|sed|awk)\b')


def _load_rules():
    try:
        with open(RULES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('layer15', {})
    except Exception:
        return {}


def evaluate_rules(tool_name, tool_input, state):
    """Returns first matching rule violation dict or None."""
    reads = state.get('layer15_session_reads', [])
    fp = tool_input.get('file_path', '') if isinstance(tool_input, dict) else ''
    cmd = tool_input.get('command', '') if isinstance(tool_input, dict) else ''

    if tool_name == 'Edit' and fp and fp not in reads:
        return {'rule_id': 'edit-without-read', 'action': 'warn',
                'message': f'Editing {fp!r} without a prior Read this session.'}

    if tool_name == 'Bash' and BASH_TOOL_RE.search(cmd):
        return {'rule_id': 'bash-instead-of-tool', 'action': 'info',
                'message': 'Use Grep/Read/Glob tools instead of Bash for file operations.'}

    if tool_name in ('Write', 'Edit') and fp:
        scope = state.get('layer1_scope_files', [])
        if scope and not any(fp.endswith(s) or s in fp for s in scope):
            return {'rule_id': 'write-outside-scope', 'action': 'warn',
                    'message': f'{fp!r} is outside task scope.'}

    return None


def handle_read_tracking(tool_name, tool_input):
    if tool_name == 'Read':
        fp = (tool_input or {}).get('file_path', '')
        if fp:
            state = ss.read_state()
            reads = state.get('layer15_session_reads', [])
            if fp not in reads:
                reads.append(fp)
                state['layer15_session_reads'] = reads
                ss.write_state(state)


def main():
    router.reset_turn_counter()

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {})

    # Always track reads first — before any early return — so a Read tool call
    # that coincides with a critical flush still registers in layer15_session_reads.
    handle_read_tracking(tool_name, tool_input)

    # Behavior 0: flush queued CRITICALs from Stop/async contexts
    pending = router.flush_pending_criticals()
    if pending:
        print(json.dumps({'additionalContext': pending}))
        return

    state = ss.read_state()

    # Check override token
    override = state.get('layer15_override_pending')
    if override:
        hit = evaluate_rules(tool_name, tool_input, state)
        if hit and hit['rule_id'] == override.get('rule_id'):
            state['layer15_override_pending'] = None
            ss.write_state(state)
            return  # Override consumed — skip block

    result = evaluate_rules(tool_name, tool_input, state)
    if result is None:
        return

    rule_id = result['rule_id']

    # Dedup within turn
    turn_warnings = state.get('layer15_turn_warnings', [])
    if rule_id in turn_warnings:
        return
    turn_warnings.append(rule_id)
    state['layer15_turn_warnings'] = turn_warnings

    # Track repeat violations
    counts = state.get('layer15_violation_counts', {})
    counts[rule_id] = counts.get(rule_id, 0) + 1
    state['layer15_violation_counts'] = counts
    ss.write_state(state)

    rules_cfg = _load_rules()
    threshold = rules_cfg.get('repeat_violation_threshold', 3)
    if counts[rule_id] >= threshold:
        router.notify('CRITICAL', 'layer15', rule_id, None,
                      f'Rule {rule_id!r} violated {counts[rule_id]}x this session.', 'pretooluse')

    action = result['action']
    message = result['message']
    if action == 'info':
        print(json.dumps({'additionalContext': f'[monitor:INFO:layer1.5] {message}'}))
    elif action == 'warn':
        print(json.dumps({'additionalContext': f'[monitor:WARN:layer1.5] {message}'}))
    elif action == 'block':
        print(json.dumps({'decision': 'block', 'reason': f'[layer1.5] {message}'}))


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Copy to hooks dir**
```bash
cp ~/.claude/scripts/staging/qg_layer15.py ~/.claude/hooks/qg_layer15.py
```

- [ ] **Step 5: Run tests**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py::TestLayer15Rules -v
```
Expected: `4 passed`

- [ ] **Step 6: Commit**
```bash
cd ~/.claude
git add hooks/qg_layer15.py scripts/staging/qg_layer15.py
git commit -m "feat(qg-monitor): add layer 1.5 PreToolUse rule validation hook [AUTO]"
```

---

### Task 7: Layer 2 — Mid-task Monitoring

**Files:**
- Create: `~/.claude/scripts/staging/qg_layer2.py` → `~/.claude/hooks/qg_layer2.py`
- Add tests to: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Add Layer 2 tests** (append to `test_qg_layers.py`):
```python
class TestLayer2Detection(unittest.TestCase):
    def setUp(self):
        import qg_session_state as ss
        self.tmp = tempfile.mktemp(suffix='.json')
        ss.STATE_PATH = self.tmp
        ss.LOCK_PATH = self.tmp + '.lock'

    def tearDown(self):
        import qg_session_state as ss
        for p in [self.tmp, self.tmp + '.lock']:
            try: os.unlink(p)
            except: pass

    def _state(self, **kwargs):
        import qg_session_state as ss
        s = ss.read_state()
        s.update(kwargs)
        return s

    def test_laziness_edit_without_read(self):
        from qg_layer2 import detect_all_events
        state = self._state(layer15_session_reads=[])
        evts = detect_all_events('Edit', {'file_path': 'foo.py'}, '', state, [])
        cats = [e['category'] for e in evts]
        self.assertIn('LAZINESS', cats)

    def test_laziness_suppressed_with_prior_read(self):
        from qg_layer2 import detect_all_events
        state = self._state(layer15_session_reads=['foo.py'])
        evts = detect_all_events('Edit', {'file_path': 'foo.py'}, '', state, [])
        cats = [e['category'] for e in evts]
        self.assertNotIn('LAZINESS', cats)

    def test_incorrect_tool_bash_grep(self):
        from qg_layer2 import detect_all_events
        state = self._state()
        evts = detect_all_events('Bash', {'command': 'grep -r foo .'}, 'output', state, [])
        cats = [e['category'] for e in evts]
        self.assertIn('INCORRECT_TOOL', cats)
        info = next(e for e in evts if e['category'] == 'INCORRECT_TOOL')
        self.assertEqual(info['severity'], 'info')

    def test_error_ignored(self):
        from qg_layer2 import detect_all_events
        state = self._state()
        prev = [{'tool': 'Bash', 'response': 'error: command failed\nexit code: 1'}]
        evts = detect_all_events('Edit', {'file_path': 'x.py'}, '', state, prev)
        cats = [e['category'] for e in evts]
        self.assertIn('ERROR_IGNORED', cats)

    def test_loop_detected(self):
        from qg_layer2 import detect_loop
        history = [('Read', 'foo.py')] * 3
        evt = detect_loop('Read', 'foo.py', history, threshold=3)
        self.assertIsNotNone(evt)
        self.assertEqual(evt['category'], 'LOOP_DETECTED')

    def test_scope_creep(self):
        from qg_layer2 import detect_all_events
        state = self._state(layer1_scope_files=['auth.py'])
        evts = detect_all_events('Write', {'file_path': 'dashboard.py'}, '', state, [])
        cats = [e['category'] for e in evts]
        self.assertIn('SCOPE_CREEP', cats)
```

- [ ] **Step 2: Run tests — verify they fail**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py::TestLayer2Detection -v 2>&1 | head -5
```

- [ ] **Step 3: Write implementation** — create `~/.claude/scripts/staging/qg_layer2.py`:
```python
#!/usr/bin/env python3
"""Layer 2 — Mid-task Monitoring (PostToolUse).
Detects 8 quality violation categories from observable tool patterns.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
BASH_TOOL_RE = re.compile(r'\b(grep|cat|find|head|tail)\b')
ERROR_RE = re.compile(
    r'(error|exception|traceback|failed|exit code [1-9]|errno|not found|permission denied)',
    re.IGNORECASE)


def _write_event(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


def detect_loop(tool_name, target, history, threshold=3):
    """history: list of (tool_name, target) tuples."""
    count = sum(1 for t, tgt in history if t == tool_name and tgt == target)
    if count >= threshold:
        return {'category': 'LOOP_DETECTED', 'severity': 'critical',
                'detection_signal': f'{tool_name} on {target!r} called {count} times'}
    return None


def detect_all_events(tool_name, tool_input, tool_response, state, prev_calls):
    """Return list of violation event dicts for this tool call."""
    events = []
    reads = state.get('layer15_session_reads', [])
    scope = state.get('layer1_scope_files', [])
    fp = (tool_input or {}).get('file_path', '')
    cmd = (tool_input or {}).get('command', '')

    # LAZINESS: Edit without prior Read
    if tool_name == 'Edit' and fp and fp not in reads:
        events.append({'category': 'LAZINESS', 'severity': 'warning',
                       'detection_signal': f'Edit on {fp!r} without prior Read'})

    # INCORRECT_TOOL: Bash instead of dedicated tool
    if tool_name == 'Bash' and BASH_TOOL_RE.search(cmd):
        events.append({'category': 'INCORRECT_TOOL', 'severity': 'info',
                       'detection_signal': f'Use Grep/Read/Glob instead: {cmd[:60]!r}'})

    # ERROR_IGNORED: prior call had error, current non-read tool fires anyway
    if tool_name not in ('Read', 'Glob', 'Grep'):
        for prev in prev_calls[-3:]:
            if ERROR_RE.search(prev.get('response', '')):
                events.append({'category': 'ERROR_IGNORED', 'severity': 'critical',
                               'detection_signal': 'Error in prior tool output ignored'})
                break

    # SCOPE_CREEP: Write/Edit outside layer1_scope_files
    if tool_name in ('Write', 'Edit') and fp and scope:
        if not any(fp.endswith(s) or s in fp for s in scope):
            events.append({'category': 'SCOPE_CREEP', 'severity': 'warning',
                           'detection_signal': f'{fp!r} outside task scope'})

    return events


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {})
    tool_response = str(payload.get('tool_response', ''))

    state = ss.read_state()

    try:
        with open(os.path.expanduser('~/.claude/qg-rules.json'), 'r', encoding='utf-8') as f:
            l2_rules = json.load(f).get('layer2', {})
    except Exception:
        l2_rules = {}

    loop_threshold = l2_rules.get('loop_same_tool_count', 3)
    events_limit = l2_rules.get('events_per_turn_limit', 5)

    turn_history = state.get('layer2_turn_history', [])
    target_key = (tool_input or {}).get('file_path', '') or str((tool_input or {}).get('command', ''))[:30]
    prev_calls = [{'tool': e['tool'], 'response': e.get('resp', '')} for e in turn_history[-3:]]

    events = detect_all_events(tool_name, tool_input, tool_response, state, prev_calls)

    # Loop detection
    history_tuples = [(e['tool'], e['target']) for e in turn_history]
    loop_evt = detect_loop(tool_name, target_key, history_tuples, threshold=loop_threshold)
    if loop_evt:
        events.append(loop_evt)

    # Rate limiting
    turn_count = state.get('layer2_turn_event_count', 0)
    events = events[:max(0, events_limit - turn_count)]

    # Elevated scrutiny
    if sum(1 for e in events if e.get('severity') == 'critical') >= 3:
        state['layer2_elevated_scrutiny'] = True

    state['layer2_turn_event_count'] = turn_count + len(events)
    turn_history.append({'tool': tool_name, 'target': target_key,
                         'resp': tool_response[:200]})
    state['layer2_turn_history'] = turn_history[-20:]

    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    wd = os.getcwd()
    unresolved = state.get('layer2_unresolved_events', [])

    for evt in events:
        record = {
            'event_id': str(uuid.uuid4()),
            'ts': ts,
            'session_uuid': state.get('session_uuid', ''),
            'working_dir': wd,
            'task_id': state.get('active_task_id', ''),
            'layer': 'layer2',
            'status': 'open',
            **evt,
        }
        _write_event(record)
        unresolved.append(record)

    state['layer2_unresolved_events'] = unresolved[-50:]
    ss.write_state(state)


if __name__ == '__main__':
    main()
```

- [ ] **Step 4: Copy to hooks dir**
```bash
cp ~/.claude/scripts/staging/qg_layer2.py ~/.claude/hooks/qg_layer2.py
```

- [ ] **Step 5: Run tests**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/test_qg_layers.py::TestLayer2Detection -v
```
Expected: `6 passed`

- [ ] **Step 6: Commit**
```bash
cd ~/.claude
git add hooks/qg_layer2.py scripts/staging/qg_layer2.py
git commit -m "feat(qg-monitor): add layer 2 mid-task monitoring PostToolUse hook (8 categories) [AUTO]"
```

---

### Task 8: Layers 3 + 4 Extension — quality-gate.py

**Files:**
- Modify: `~/.claude/hooks/quality-gate.py` (patch via Bash)
- Create: `~/.claude/scripts/staging/qg_layer34_ext.py` (functions to append)

**Note:** Layer 3 FN detection is rule-based in Phase 1 (LAZINESS text + MEMORY_OVER_VERIFICATION). The Haiku FN prompt extension is Phase 2.

- [ ] **Step 1: Verify exact anchor lines in quality-gate.py**
```bash
grep -n "SMOKE:13\|SMOKE:9" ~/.claude/hooks/quality-gate.py
grep -n "continue.*True" ~/.claude/hooks/quality-gate.py
```
Then print the exact text of both anchor regions — needed to confirm variable names match the patch strings:
```bash
# Show the 3 lines at SMOKE:13 anchor
grep -n -A2 "SMOKE:13" ~/.claude/hooks/quality-gate.py
# Show the 3 lines at SMOKE:9 anchor (confirm whether variable is 'reason' or 'block_reason' in the print)
grep -n -A2 "SMOKE:9" ~/.claude/hooks/quality-gate.py
# Show the exact continue-True print line (confirm indentation)
grep -n "continue.*True" ~/.claude/hooks/quality-gate.py
```
**Critical:** If the SMOKE:9 print uses `reason` instead of `block_reason`, update `old2` in Step 3 to match the actual variable name. If the pass-path print has different indentation, update `old3` accordingly.

- [ ] **Step 2: Write the extension module** — create `~/.claude/scripts/staging/qg_layer34_ext.py`:
```python
# ── Quality Gate Monitor — Layer 3 + Layer 4 Extension ───────────────────────
# This file is APPENDED to quality-gate.py. All quality-gate.py globals are
# available (json, os, re, datetime, _response_hash, LOG_PATH, etc.)
import uuid as _uuid_mod, time as _time_mod

_QG_MONITOR = os.path.join(os.path.expanduser('~/.claude'), 'qg-monitor.jsonl')
_QG_HISTORY = os.path.join(os.path.expanduser('~/.claude'), 'qg-session-history.md')
_QG_ARCHIVE = os.path.join(os.path.expanduser('~/.claude'), 'qg-session-archive.md')

_LAZINESS_TEXT_RE = re.compile(
    r'\b(done|completed?|fixed|all (?:tests?|checks?) pass|verified|confirmed|finished)\b',
    re.IGNORECASE)
_STATED_HIGH_RE = re.compile(r"\b(I'?m certain|definitely|I know|this will work|confirmed)\b", re.IGNORECASE)
_STATED_MED_RE = re.compile(r"\b(I believe|should|likely|expect)\b", re.IGNORECASE)
_STATED_LOW_RE = re.compile(r"\b(might|possibly|I think|probably)\b", re.IGNORECASE)
_VERIFY_OUTPUT_RE = re.compile(r'(===|---|\d+ passed|\d+ failed|exit code \d|>>|\$\s)')


def _qg_load_ss():
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import qg_session_state as _ss
        return _ss.read_state(), _ss
    except Exception:
        return {}, None


def _compute_confidence(gate_blocked, block_category, state):
    base = 0.70 if gate_blocked else 0.75
    score = base
    if gate_blocked:
        if block_category in ('MECHANICAL', 'OVERCONFIDENCE'):
            score += 0.15
        elif block_category == 'PLANNING':
            score -= 0.10
    unresolved = [e for e in state.get('layer2_unresolved_events', []) if e.get('status') == 'open']
    score -= min(len(unresolved) * 0.10, 0.30)
    criticals = [e for e in unresolved if e.get('severity') == 'critical']
    score -= min(len(criticals) * 0.15, 0.30)
    if state.get('layer2_elevated_scrutiny'):
        score -= 0.20
    return max(0.01, min(0.99, score))


def _detect_fn_signals(response, state):
    signals = []
    if response and _LAZINESS_TEXT_RE.search(response):
        if not _VERIFY_OUTPUT_RE.search(response):
            signals.append('claimed completion without verification output')
    prev_claims = state.get('layer3_last_response_claims', [])
    for claim in prev_claims:
        if claim and len(claim) > 10 and claim.lower() in (response or '').lower():
            signals.append(f'repeated unverified claim: {claim[:60]}')
            break
    return signals


def _extract_stated_certainty(response):
    if _STATED_HIGH_RE.search(response or ''):
        return 'high'
    if _STATED_MED_RE.search(response or ''):
        return 'medium'
    if _STATED_LOW_RE.search(response or ''):
        return 'low'
    return 'none'


def _write_monitor_event(event):
    try:
        with open(_QG_MONITOR, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _layer3_run(gate_blocked, block_reason, response, tool_names, user_request):
    """Classify response as TP/FP/FN/TN. Returns (verdict, tag_for_block_msg)."""
    state, _ss = _qg_load_ss()
    if _ss is None:
        return 'UNKNOWN', ''

    block_cat = (block_reason or '').split(':')[0].strip() if block_reason else ''
    confidence = _compute_confidence(gate_blocked, block_cat, state)
    stated_certainty = _extract_stated_certainty(response)

    if gate_blocked:
        verdict = 'TP' if confidence >= 0.60 else 'FP'
        fn_signals = []
    else:
        fn_signals = _detect_fn_signals(response, state)
        verdict = 'FN' if fn_signals else 'TN'

    conf_level = 'certain' if confidence >= 0.85 else ('probable' if confidence >= 0.60 else 'uncertain')

    event = {
        'event_id': str(_uuid_mod.uuid4()),
        'ts': _time_mod.strftime('%Y-%m-%dT%H:%M:%S'),
        'working_dir': os.getcwd(),
        'session_uuid': state.get('session_uuid', ''),
        'task_id': state.get('active_task_id', ''),
        'layer': 'layer3',
        'verdict': verdict,
        'confidence': round(confidence, 3),
        'confidence_level': conf_level,
        'stated_certainty': stated_certainty,
        'block_reason': (block_reason or '')[:120],
        'L2_events': [e['category'] for e in state.get('layer2_unresolved_events', [])[:5]],
        'tools_before': list(tool_names or [])[:5],
        'response_hash': _response_hash(response)[:8] if response else '',
    }
    _write_monitor_event(event)

    # Update session state
    claims = re.findall(r'\b(?:the|this|my) \w+ (?:is|are|works?|pass(?:es)?)\b', response or '')
    state['layer3_last_response_claims'] = claims[:5]
    state['layer25_syntax_failure'] = False  # Clear per-turn flag

    if verdict == 'FN':
        reason = fn_signals[0] if fn_signals else 'unverified claims'
        state['layer3_pending_fn_alert'] = f'[monitor] Missed Failure — {reason}'
        try:
            import qg_notification_router as _nr
            _nr.notify('CRITICAL', 'layer3', 'FN', None, f'Missed Failure: {reason}', 'stop')
        except Exception:
            pass

    # Layer 1.5 override detection
    if gate_blocked and response and re.search(r'Override \[[\w-]+\]:', response):
        m = re.search(r'Override \[([\w-]+)\]:\s*(.+)', response)
        if m:
            state['layer15_override_pending'] = {
                'rule_id': m.group(1), 'justification': m.group(2)[:200],
                'ts': _time_mod.time(),
            }

    # Flush WARNING notifications
    try:
        import qg_notification_router as _nr
        warnings_text = _nr.flush_warnings()
    except Exception:
        warnings_text = None

    _ss.write_state(state)
    tag = f' [monitor:{verdict}:{conf_level}]' if verdict in ('TP', 'FP') else ''
    return verdict, tag, warnings_text


def _layer4_checkpoint(state, _ss):
    """Write rolling session summary entry to qg-session-history.md."""
    if not _ss:
        return
    try:
        session_uuid = state.get('session_uuid', 'unknown')
        ts = _time_mod.strftime('%Y-%m-%dT%H:%M:%S')

        # Collect Layer 3 events for this session
        l3_events = []
        if os.path.exists(_QG_MONITOR):
            with open(_QG_MONITOR, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        if e.get('session_uuid') == session_uuid and e.get('layer') == 'layer3':
                            l3_events.append(e)
                    except Exception:
                        pass

        tp = sum(1 for e in l3_events if e.get('verdict') == 'TP')
        fp = sum(1 for e in l3_events if e.get('verdict') == 'FP')
        fn = sum(1 for e in l3_events if e.get('verdict') == 'FN')
        tn = sum(1 for e in l3_events if e.get('verdict') == 'TN')
        total = len(l3_events)

        l2_criticals = len([e for e in state.get('layer2_unresolved_events', [])
                            if e.get('severity') == 'critical' and e.get('status') == 'open'])
        cat = state.get('layer1_task_category', 'UNKNOWN')
        cw = {'MECHANICAL': 1.0, 'ASSUMPTION': 1.0, 'OVERCONFIDENCE': 1.2,
              'PLANNING': 1.3, 'DEEP': 1.5}.get(cat, 1.0)
        score = round((fn * 3 + l2_criticals * 2 + fp) / (total * cw), 3) if total > 0 else 0.0

        entry = (
            f'## Session {ts}\n'
            f'session_uuid: {session_uuid}\n'
            f'quality_score: {score}\n'
            f'TP: {tp}  FP: {fp}  FN: {fn}  TN: {tn}  total: {total}\n'
            f'L2_criticals: {l2_criticals}\n'
            f'category: {cat}\n'
            f'recovery_rate: N/A (Phase 2)\n\n'
        )

        history = ''
        if os.path.exists(_QG_HISTORY):
            with open(_QG_HISTORY, 'r', encoding='utf-8') as f:
                history = f.read()

        uuid_pat = re.escape(session_uuid)
        if re.search(f'session_uuid: {uuid_pat}', history):
            history = re.sub(
                f'## Session[^\n]*\nsession_uuid: {uuid_pat}.*?(?=^## Session|\Z)',
                entry, history, flags=re.MULTILINE | re.DOTALL)
        else:
            history = entry + history

        entries = re.split(r'(?=^## Session )', history, flags=re.MULTILINE)
        if len(entries) > 30:
            with open(_QG_ARCHIVE, 'a', encoding='utf-8') as f:
                f.write('\n'.join(entries[30:]))
            entries = entries[:30]

        with open(_QG_HISTORY, 'w', encoding='utf-8') as f:
            f.write('\n'.join(entries))
    except Exception:
        pass
```

- [ ] **Step 3: Patch quality-gate.py — append extension and wire up calls**

```bash
python -c "
import os, re

qg = os.path.expanduser('~/.claude/hooks/quality-gate.py')
ext = os.path.expanduser('~/.claude/scripts/staging/qg_layer34_ext.py')

with open(qg, 'r', encoding='utf-8') as f:
    content = f.read()
with open(ext, 'r', encoding='utf-8') as f:
    ext_content = f.read()

# Patch 1: mechanical block (SMOKE:13 is on the log_decision line just before print)
# Insert layer3 call + modify the print to include _l3_tag
old1 = '''            log_decision('BLOCK', block_reason, user_request, tool_names, complexity, response)  # SMOKE:13
            print(json.dumps({\"decision\": \"block\", \"reason\": f\"QUALITY GATE: {block_reason}\"}))'''
new1 = '''            log_decision('BLOCK', block_reason, user_request, tool_names, complexity, response)  # SMOKE:13
            try:
                _l3_verdict, _l3_tag, _ = _layer3_run(True, block_reason, response, tool_names, user_request)
            except Exception:
                _l3_tag = ''
            print(json.dumps({\"decision\": \"block\", \"reason\": f\"QUALITY GATE: {block_reason}{_l3_tag}\"}))'''
assert old1 in content, 'SMOKE:13 anchor not found — check Step 1 output and update old1'
content = content.replace(old1, new1, 1)
assert new1 in content, 'Patch 1 did not land — string mismatch'

# Patch 2: LLM block (SMOKE:9)
# NOTE: If Step 1 shows the print at SMOKE:9 uses 'reason' not 'block_reason', update old2 below.
old2 = '''        log_decision('BLOCK', reason, user_request, tool_names, complexity, response)  # SMOKE:9
        print(json.dumps({\"decision\": \"block\", \"reason\": block_reason}))'''
new2 = '''        log_decision('BLOCK', reason, user_request, tool_names, complexity, response)  # SMOKE:9
        try:
            _l3_verdict2, _l3_tag2, _ = _layer3_run(True, reason, response, tool_names, user_request)
        except Exception:
            _l3_tag2 = ''
        print(json.dumps({\"decision\": \"block\", \"reason\": block_reason + _l3_tag2}))'''
assert old2 in content, 'SMOKE:9 anchor not found — check Step 1 output and update old2'
content = content.replace(old2, new2, 1)
assert new2 in content, 'Patch 2 did not land — string mismatch'

# Patch 3: pass path — add layer3/4 before print continue
# NOTE: If Step 1 shows different indentation on the continue-True line, update old3 below.
old3 = '    print(json.dumps({\"continue\": True}))'
new3 = '''    try:
        _l3_verdict3, _l3_tag3, _l3_warnings = _layer3_run(False, None, response, tool_names, user_request)
        _l3_state3, _l3_ss3 = _qg_load_ss()
        _layer4_checkpoint(_l3_state3, _l3_ss3)
    except Exception:
        pass
    print(json.dumps({\"continue\": True}))'''
assert old3 in content, 'Pass-path anchor not found — check Step 1 output and update old3'
content = content.replace(old3, new3, 1)
assert new3 in content, 'Patch 3 did not land — string mismatch'

# Append extension functions
content = content.rstrip() + chr(10) + chr(10) + ext_content

with open(qg, 'w', encoding='utf-8') as f:
    f.write(content)
print('quality-gate.py patched — all 3 anchors confirmed')
"
```

- [ ] **Step 4: Verify patch applied**
```bash
grep -n "_layer3_run\|_layer4_checkpoint\|_qg_load_ss" ~/.claude/hooks/quality-gate.py | head -10
```
Expected: 3 calls visible (one each in mechanical block, LLM block, pass path).

- [ ] **Step 5: Run regression battery — verify no accuracy change**
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-regression.py 2>&1 | tail -5
```
Expected: Same accuracy as baseline. If any regressions, check that the string replacements landed correctly.

- [ ] **Step 6: Commit**
```bash
cd ~/.claude
git add hooks/quality-gate.py scripts/staging/qg_layer34_ext.py
git commit -m "feat(qg-monitor): extend quality-gate.py with layer 3 classification and layer 4 session summary [AUTO]"
```

---

### Task 9: Dashboard — qg monitor command

**Files:**
- Modify: `~/.claude/scripts/qg-feedback.py`
- Create: `~/.claude/scripts/staging/qg_monitor_funcs.py`

- [ ] **Step 1: Verify insertion point**
```bash
grep -n "def main\|Unknown command\|elif cmd ==" ~/.claude/scripts/qg-feedback.py | tail -10
```
Expected: `else:` with `print(f'Unknown command: {cmd}')` visible near end of main().

- [ ] **Step 2: Write new command functions** — create `~/.claude/scripts/staging/qg_monitor_funcs.py`:
```python
def cmd_monitor():
    """qg monitor — unified quality gate dashboard."""
    import json, os
    from collections import Counter

    CLAUDE_DIR = os.path.expanduser('~/.claude')
    monitor_path = f'{CLAUDE_DIR}/qg-monitor.jsonl'
    history_path = f'{CLAUDE_DIR}/qg-session-history.md'
    state_path = f'{CLAUDE_DIR}/qg-session-state.json'

    print('=== Quality Gate Monitor Dashboard ===')
    print()

    session_uuid = None
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        session_uuid = state.get('session_uuid')
        print(f"Session:  {session_uuid or '(none)'}")
        print(f"Task:     {state.get('active_task_description', '')[:70] or '(none)'}")
        print(f"Category: {state.get('layer1_task_category', 'UNKNOWN')}")
        l2_open = [e for e in state.get('layer2_unresolved_events', []) if e.get('status') == 'open']
        print(f"L2 open:  {len(l2_open)} unresolved")
        if l2_open:
            for cat, cnt in Counter(e['category'] for e in l2_open).most_common():
                print(f"          {cat}: {cnt}")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Session state: not available")
    print()

    all_events, sess_events = [], []
    try:
        with open(monitor_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get('layer') == 'layer3':
                        all_events.append(e)
                        if session_uuid and e.get('session_uuid') == session_uuid:
                            sess_events.append(e)
                except Exception:
                    pass
    except FileNotFoundError:
        pass

    def _stats(evts, label):
        tp = sum(1 for e in evts if e.get('verdict') == 'TP')
        fp = sum(1 for e in evts if e.get('verdict') == 'FP')
        fn = sum(1 for e in evts if e.get('verdict') == 'FN')
        tn = sum(1 for e in evts if e.get('verdict') == 'TN')
        print(f"{label}: TP={tp} FP={fp} FN={fn} TN={tn} (total={len(evts)})")

    _stats(sess_events, 'Session ')
    _stats(all_events,  'All-time')
    print()

    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            history = f.read()
        entries = [e for e in history.split('## Session') if e.strip()]
        if entries:
            print('--- Most Recent Session Summary ---')
            print('## Session' + entries[0][:500].rstrip())
    except FileNotFoundError:
        print('No session history yet.')

    print()
    print('Commands: qg analyze | qg integrity | qg rules')


def cmd_analyze():
    """qg analyze — trigger cross-session analysis (Phase 3 feature)."""
    print('Layer 6 cross-session analysis: Phase 3 feature. Not yet available.')
    print('Layer 9 confidence calibration: Phase 3 feature. Not yet available.')
    print('Use qg monitor to view current session stats.')


def cmd_integrity():
    """qg integrity — audit trail integrity check."""
    import json, os
    path = os.path.expanduser('~/.claude/qg-monitor.jsonl')
    if not os.path.exists(path):
        print('qg-monitor.jsonl not found — no events logged yet.')
        return
    total = bad = 0
    seen_ids = set()
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            total += 1
            try:
                e = json.loads(line)
                eid = e.get('event_id', '')
                if eid in seen_ids:
                    print(f'  Line {i}: duplicate event_id {eid!r}')
                    bad += 1
                seen_ids.add(eid)
            except json.JSONDecodeError:
                print(f'  Line {i}: invalid JSON')
                bad += 1
    print(f'Audit trail: {total} lines, {bad} issue(s).')
    print('Integrity: OK' if bad == 0 else 'Integrity: ISSUES FOUND')


def cmd_rules():
    """qg rules — view pending rule suggestions (Layer 7 preview)."""
    import os
    path = os.path.expanduser('~/.claude/qg-rule-suggestions.md')
    if not os.path.exists(path):
        print('No pending rule suggestions. (Layer 7 is a Phase 3 feature.)')
        return
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())
```

- [ ] **Step 3: Inject functions and new elif branches into qg-feedback.py**
```bash
python -c "
import os

fb = os.path.expanduser('~/.claude/scripts/qg-feedback.py')
funcs = os.path.expanduser('~/.claude/scripts/staging/qg_monitor_funcs.py')

with open(fb, 'r', encoding='utf-8') as f:
    content = f.read()
with open(funcs, 'r', encoding='utf-8') as f:
    new_funcs = f.read()

# Insert functions before main()
assert '\ndef main():' in content, 'Could not find def main() — check qg-feedback.py for correct blank-line prefix'
content = content.replace('\ndef main():', chr(10) + new_funcs + '\ndef main():', 1)
assert 'def cmd_monitor' in content, 'Function injection failed — new_funcs not inserted'

# Add elif branches before the else
old_else = \"    else:\n        print(f'Unknown command: {cmd}')\"
assert old_else in content, 'old_else anchor not found — check indentation/text in qg-feedback.py main()'
new_branches = \"\"\"    elif cmd == 'monitor':
        cmd_monitor()
    elif cmd == 'analyze':
        cmd_analyze()
    elif cmd == 'integrity':
        cmd_integrity()
    elif cmd == 'rules':
        if len(sys.argv) >= 3 and sys.argv[2] in ('apply', 'reject'):
            print('Rule apply/reject (Layer 7) is a Phase 3 feature.')
        else:
            cmd_rules()
    \"\"\" + old_else

content = content.replace(old_else, new_branches, 1)
assert \"elif cmd == 'monitor'\" in content, 'elif injection failed'

with open(fb, 'w', encoding='utf-8') as f:
    f.write(content)
print('qg-feedback.py updated — all injections confirmed')
"
```

- [ ] **Step 4: Test the dashboard**
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py monitor
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py integrity
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py analyze
```
Expected: Each command runs without error and prints output.

- [ ] **Step 5: Commit**
```bash
cd ~/.claude
git add scripts/qg-feedback.py scripts/staging/qg_monitor_funcs.py
git commit -m "feat(qg-monitor): add qg monitor/analyze/integrity/rules dashboard commands [AUTO]"
```

---

### Task 10: Hook Registration

**Files:**
- Modify: `~/.claude/settings.json` (via update-config skill — write-protected)

- [ ] **Step 1: Invoke the update-config skill**

Use `@superpowers:update-config`. Register 5 new hooks:

**SessionStart** — add after existing SessionStart entries:
```json
{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer0.py" }
{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer_env.py" }
```

**PreToolUse** — add after existing PreToolUse entries (both match `*`):
```json
{ "matcher": "*", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer_env.py" }] }
{ "matcher": "*", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer15.py" }] }
```

**PostToolUse** — add after existing PostToolUse entries:
```json
{ "matcher": "*", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer2.py" }] }
```

**Note:** `qg_layer_env.py` dispatches on `hook_event_name` internally — the same file handles both SessionStart and PreToolUse calls.

- [ ] **Step 2: Verify registration**

Read `~/.claude/settings.json` and confirm all 5 new entries appear in the correct hook event sections.

- [ ] **Step 3: Commit** (settings.json commit handled by update-config skill)

---

### Task 11: Full Regression and Smoke Validation

**Files:** None changed.

- [ ] **Step 1: Run all unit tests**
```bash
PYTHONIOENCODING=utf-8 python -m pytest ~/.claude/scripts/tests/ -v 2>&1 | tail -15
```
Expected: All tests pass.

- [ ] **Step 2: Run regression battery**
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-regression.py 2>&1 | tail -5
```
Expected: Same accuracy as before Phase 1 changes. If accuracy drops: re-read Task 8 patch instructions and verify the string replacements applied to the correct lines.

- [ ] **Step 3: Live smoke test** — start a Claude Code session, run a few tool calls, then:
```bash
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py monitor
```
Expected: Dashboard shows session UUID, L2 events, Layer 3 TP/FP/FN/TN counts.

- [ ] **Step 4: Verify qg-monitor.jsonl is being written**
```bash
tail -3 ~/.claude/qg-monitor.jsonl 2>/dev/null || echo "(not yet written)"
```
Expected: JSON lines with `"layer": "layer2"` or `"layer": "layer3"` events.

- [ ] **Step 5: Final commit**
```bash
cd ~/.claude
git status
git commit -m "feat(qg-monitor): phase 1 complete — layers 0/ENV/1/1.5/2/3/4 + dashboard [AUTO]"
```

---

## Phase 1 Complete

After Task 11 passes, Phase 1 delivers:
- **TP/FP/FN/TN** classification on every response (`qg-monitor.jsonl`)
- **Mid-task monitoring** alerts for LAZINESS, INCORRECT_TOOL, ERROR_IGNORED, LOOP_DETECTED, SCOPE_CREEP
- **Pre-task enforcement** (DEEP heuristic, pivot detection, FN delivery, SCOPE_CREEP clearing)
- **Tool use validation** (edit-without-read, bash-instead-of-tool, write-outside-scope)
- **Per-session quality scores** with rolling history (`qg-session-history.md`)
- **`qg monitor`** unified dashboard

**Next:** Phase 2 plan — Layers 1.7, 1.8, 1.9, 3.5, 4.5, 5 (correctness and recovery).

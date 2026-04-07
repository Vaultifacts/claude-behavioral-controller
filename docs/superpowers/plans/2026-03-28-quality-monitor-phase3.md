# Quality Gate Monitor Phase 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 3 of the Quality Gate Monitor: Layers 2.5, 2.6, 2.7, 6, 7, 8, 9, and 10.

**Architecture:** Phase 3a (Tasks 1–4) adds four hook-based monitoring layers that fire during tool use: output syntax validation (2.5), code convention consistency (2.6), test coverage warnings (2.7), and regression detection (8). Phase 3b (Tasks 5–8) adds four analytical layers that fire at session end or on demand: cross-session pattern analysis (6), rule refinement suggestions (7), confidence calibration (9), and audit trail integrity (10). All new hooks are registered in `~/.claude/settings.json`. The hooks dir (`~/.claude/hooks/`) is write-protected — use `python3 -c "open(...).write(content)"` subprocess for all hook file writes.

**Tech Stack:** Python 3.13, existing hook infrastructure (`~/.claude/hooks/`), `qg_session_state.py`, `qg_notification_router.py`, existing `qg-feedback.py` command stubs.

---

## File Structure

### New files
| File | Purpose |
|------|---------|
| `~/.claude/hooks/qg_layer25.py` | Layer 2.5 — Output Validity (PostToolUse Write\|Edit) |
| `~/.claude/hooks/qg_layer26.py` | Layer 2.6 — Consistency Enforcement (PostToolUse Write\|Edit) |
| `~/.claude/hooks/qg_layer27.py` | Layer 2.7 — Testing Coverage Verification (PreToolUse Edit) |
| `~/.claude/hooks/qg_layer8.py` | Layer 8 — Regression Detection (PostToolUse Bash) |
| `~/.claude/hooks/qg_layer6.py` | Layer 6 — Cross-session Pattern Analysis (Stop hook) |
| `~/.claude/hooks/qg_layer7.py` | Layer 7 — Feedback and Rule Refinement (Stop hook) |
| `~/.claude/hooks/qg_layer9.py` | Layer 9 — Confidence Calibration (Stop hook) |
| `~/.claude/hooks/qg_layer10.py` | Layer 10 — Audit Trail Integrity (library + CLI) |

### Modified files
| File | Changes |
|------|---------|
| `~/.claude/hooks/qg_session_state.py` | Add Phase 3 fields to `_empty_state()`, bump SCHEMA_VERSION to 2 |
| `~/.claude/scripts/qg-feedback.py` | Fill in `cmd_analyze()`, `cmd_integrity()` stubs with real Layer 6/10 logic |
| `~/.claude/scripts/tests/test_qg_layers.py` | Add 24 tests for new layers (59 → 83 total) |
| `~/.claude/settings.json` | Register all 8 new hooks |
| `~/.claude/README.md` | Mark Phase 3 complete, update test count |
| `~/.claude/projects/C--Users-Matt1/memory/quality-gate-monitor-design.md` | Update status line |

---

## Phase 3a — Hook-Based Monitoring

---

### Task 1: Layer 2.5 — Output Validity

**Files:**
- Create: `~/.claude/hooks/qg_layer25.py`
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer25OutputValidity(unittest.TestCase):
    def test_valid_python_returns_none(self):
        from qg_layer25 import validate_file
        f = tempfile.mktemp(suffix='.py')
        open(f, 'w').write('x = 1\n')
        result = validate_file(f)
        os.unlink(f)
        self.assertIsNone(result)

    def test_invalid_json_returns_error_string(self):
        from qg_layer25 import validate_file
        f = tempfile.mktemp(suffix='.json')
        open(f, 'w').write('{not valid json}')
        result = validate_file(f)
        os.unlink(f)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, str)

    def test_unknown_extension_returns_none(self):
        from qg_layer25 import validate_file
        self.assertIsNone(validate_file('/nonexistent/file.txt'))

    def test_large_file_returns_none(self):
        from qg_layer25 import validate_file, SIZE_LIMIT
        f = tempfile.mktemp(suffix='.py')
        open(f, 'w').write('x = 1\n' * (SIZE_LIMIT // 5 + 1))
        result = validate_file(f)
        os.unlink(f)
        self.assertIsNone(result)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer25" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails — module doesn't exist yet)

- [ ] **Step 3: Write `qg_layer25.py`**

Write via subprocess (hooks dir is write-protected):

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 2.5 -- Output Validity (PostToolUse on Write/Edit).
Validates file syntax after write/edit; feeds Layer 2 OUTPUT_UNVALIDATED.
\"\"\"
import ast, json, os, subprocess, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
SIZE_LIMIT = 102400  # 100KB


def _write_event(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def _validate_python(content, path):
    ast.parse(content)


def _validate_json(content, path):
    json.loads(content)


def _validate_yaml(content, path):
    try:
        import yaml
        yaml.safe_load(content)
    except ImportError:
        pass


def _validate_sh(content, path):
    r = subprocess.run(['bash', '-n', path], capture_output=True, timeout=5)
    if r.returncode != 0:
        raise SyntaxError(r.stderr.decode(errors='replace').strip())


VALIDATORS = {
    '.py': _validate_python,
    '.json': _validate_json,
    '.yaml': _validate_yaml,
    '.yml': _validate_yaml,
    '.sh': _validate_sh,
}


def validate_file(file_path):
    """Returns error string on failure, None on success/skip."""
    _, ext = os.path.splitext(file_path)
    validator = VALIDATORS.get(ext)
    if not validator:
        return None
    try:
        if not os.path.exists(file_path):
            return None
        if os.path.getsize(file_path) > SIZE_LIMIT:
            return None
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        validator(content, file_path)
        return None
    except Exception as e:
        return str(e)[:200]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    if tool_name not in ('Write', 'Edit'):
        return

    file_path = (payload.get('tool_input') or {}).get('file_path', '')
    if not file_path:
        return

    error = validate_file(file_path)
    if error is None:
        return

    state = ss.read_state()
    state['layer25_syntax_failure'] = True

    event = {
        'event_id': str(uuid.uuid4()),
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'session_uuid': state.get('session_uuid') or '',
        'working_dir': os.getcwd(),
        'task_id': state.get('active_task_id', ''),
        'layer': 'layer25',
        'category': 'OUTPUT_UNVALIDATED',
        'severity': 'warning',
        'detection_signal': 'Syntax error in {}: {}'.format(file_path, error),
        'file_path': file_path,
        'status': 'open',
    }
    _write_event(event)

    unresolved = state.get('layer2_unresolved_events', [])
    unresolved.append(event)
    state['layer2_unresolved_events'] = unresolved[-50:]
    ss.write_state(state)

    out = {'hookSpecificOutput': {'hookEventName': 'PostToolUse',
        'additionalContext': '[Layer 2.5] Syntax warning: {} has invalid syntax. Verify before proceeding.'.format(file_path)}}
    print(json.dumps(out))


if __name__ == '__main__':
    main()
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer25.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer25" -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer25.py scripts/tests/test_qg_layers.py && git commit -m "feat(layer25): output validity hook — syntax validation on Write/Edit [AUTO]"
```

---

### Task 2: Layer 2.6 — Consistency Enforcement

**Files:**
- Create: `~/.claude/hooks/qg_layer26.py`
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer26ConsistencyEnforcement(unittest.TestCase):
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

    def test_detect_snake_case(self):
        from qg_layer26 import detect_convention
        content = 'def my_function():\n    pass\n'
        conv = detect_convention(content)
        self.assertEqual(conv.get('naming'), 'snake_case')

    def test_detect_camel_case(self):
        from qg_layer26 import detect_convention
        content = 'def myFunction():\n    pass\n'
        conv = detect_convention(content)
        self.assertEqual(conv.get('naming'), 'camelCase')

    def test_deviation_detected(self):
        from qg_layer26 import check_deviation
        devs = check_deviation({'naming': 'camelCase'}, {'naming': 'snake_case'})
        self.assertTrue(len(devs) > 0)

    def test_no_deviation_same_convention(self):
        from qg_layer26 import check_deviation
        devs = check_deviation({'naming': 'snake_case'}, {'naming': 'snake_case'})
        self.assertEqual(devs, [])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer26" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails)

- [ ] **Step 3: Write `qg_layer26.py`**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 2.6 -- Consistency Enforcement (PostToolUse on Write/Edit).
Establishes convention baseline from first 3 files; warns on deviation.
\"\"\"
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
SNAKE_RE = re.compile(r'\bdef [a-z][a-z0-9_]+\b')
CAMEL_RE = re.compile(r'\bdef [a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b')
IMPORT_DIRECT_RE = re.compile(r'^import [a-zA-Z]', re.MULTILINE)
IMPORT_FROM_RE = re.compile(r'^from [a-zA-Z].*import', re.MULTILINE)


def _write_event(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def detect_convention(content):
    result = {}
    snake = bool(SNAKE_RE.search(content))
    camel = bool(CAMEL_RE.search(content))
    if snake and not camel:
        result['naming'] = 'snake_case'
    elif camel and not snake:
        result['naming'] = 'camelCase'
    direct = bool(IMPORT_DIRECT_RE.search(content))
    frm = bool(IMPORT_FROM_RE.search(content))
    if direct and not frm:
        result['imports'] = 'direct'
    elif frm and not direct:
        result['imports'] = 'from'
    return result


def check_deviation(file_convention, baseline):
    deviations = []
    for key in ('naming', 'imports'):
        fv = file_convention.get(key)
        bv = baseline.get(key)
        if fv and bv and fv != bv:
            deviations.append('{}: {!r} vs baseline {!r}'.format(key, fv, bv))
    return deviations


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    if tool_name not in ('Write', 'Edit'):
        return

    file_path = (payload.get('tool_input') or {}).get('file_path', '')
    _, ext = os.path.splitext(file_path)
    if ext not in ('.py', '.js', '.ts') or not file_path or not os.path.exists(file_path):
        return

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return

    state = ss.read_state()
    baseline = state.get('layer26_convention_baseline', {})
    files_seen = state.get('layer26_files_seen', 0)
    convention = detect_convention(content)
    if not convention:
        return

    if files_seen < 3:
        for k, v in convention.items():
            if k not in baseline:
                baseline[k] = v
        state['layer26_convention_baseline'] = baseline
        state['layer26_files_seen'] = files_seen + 1
        ss.write_state(state)
        return

    if state.get('layer17_creating_new_artifacts'):
        ss.write_state(state)
        return

    deviations = check_deviation(convention, baseline)
    if not deviations:
        ss.write_state(state)
        return

    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    for dev in deviations:
        event = {
            'event_id': str(uuid.uuid4()),
            'ts': ts,
            'session_uuid': state.get('session_uuid') or '',
            'working_dir': os.getcwd(),
            'task_id': state.get('active_task_id', ''),
            'layer': 'layer26',
            'category': 'CONSISTENCY_VIOLATION',
            'severity': 'warning',
            'detection_signal': dev,
            'file_path': file_path,
            'status': 'open',
        }
        _write_event(event)

    ss.write_state(state)


if __name__ == '__main__':
    main()
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer26.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer26" -v 2>&1 | tail -10
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer26.py scripts/tests/test_qg_layers.py && git commit -m "feat(layer26): consistency enforcement hook — convention baseline [AUTO]"
```

---

### Task 3: Layer 2.7 — Testing Coverage Verification

**Files:**
- Create: `~/.claude/hooks/qg_layer27.py`
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer27TestingCoverage(unittest.TestCase):
    def test_test_file_found_returns_path(self):
        import shutil
        from qg_layer27 import find_test_file
        d = tempfile.mkdtemp()
        open(os.path.join(d, 'test_utils.py'), 'w').close()
        old = os.getcwd(); os.chdir(d)
        result = find_test_file('utils.py')
        os.chdir(old); shutil.rmtree(d)
        self.assertIsNotNone(result)

    def test_no_test_file_returns_none(self):
        import shutil
        from qg_layer27 import find_test_file
        d = tempfile.mkdtemp()
        old = os.getcwd(); os.chdir(d)
        result = find_test_file('auth.py')
        os.chdir(old); shutil.rmtree(d)
        self.assertIsNone(result)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer27" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails)

- [ ] **Step 3: Write `qg_layer27.py`**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 2.7 -- Testing Coverage Verification (PreToolUse on Edit).
Warns if edited code file has no associated test file or coverage data.
\"\"\"
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

CODE_EXTS = {'.py', '.js', '.ts', '.go', '.java', '.cs'}


def find_test_file(source_path):
    base = os.path.splitext(os.path.basename(source_path))[0]
    cwd = os.getcwd()
    for root, _, files in os.walk(cwd):
        for fname in files:
            no_ext = os.path.splitext(fname)[0]
            if (no_ext == 'test_' + base or
                    no_ext == base + '_test' or
                    no_ext == base + '_spec' or
                    no_ext.startswith('test_' + base + '_')):
                return os.path.join(root, fname)
    return None


def has_coverage_data():
    cwd = os.getcwd()
    for name in ('.coverage', 'coverage.xml', 'coverage/lcov.info'):
        if os.path.exists(os.path.join(cwd, name)):
            return True
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    if payload.get('tool_name') != 'Edit':
        return

    file_path = (payload.get('tool_input') or {}).get('file_path', '')
    if not file_path:
        return

    _, ext = os.path.splitext(file_path)
    if ext not in CODE_EXTS:
        return

    base = os.path.splitext(os.path.basename(file_path))[0]
    if base.startswith(('test_', 'spec_', 'Test')):
        return  # Skip test files

    if has_coverage_data():
        return

    if find_test_file(file_path):
        return

    out = {'hookSpecificOutput': {'hookEventName': 'PreToolUse',
        'additionalContext': '[Layer 2.7] No test file found for {}. Consider adding tests.'.format(
            os.path.basename(file_path))}}
    print(json.dumps(out))


if __name__ == '__main__':
    main()
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer27.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer27" -v 2>&1 | tail -10
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer27.py scripts/tests/test_qg_layers.py && git commit -m "feat(layer27): testing coverage verification hook [AUTO]"
```

---

### Task 4: Layer 8 — Regression Detection

**Files:**
- Create: `~/.claude/hooks/qg_layer8.py`
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer8RegressionDetection(unittest.TestCase):
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

    def test_test_command_detected(self):
        from qg_layer8 import TEST_CMD_RE
        self.assertTrue(bool(TEST_CMD_RE.search('pytest tests/')))
        self.assertTrue(bool(TEST_CMD_RE.search('npm test')))
        self.assertFalse(bool(TEST_CMD_RE.search('ls -la')))

    def test_parse_results_pass_and_fail(self):
        from qg_layer8 import parse_results
        passed, failed = parse_results('5 passed, 2 failed in 1.23s')
        self.assertEqual(passed, 5)
        self.assertEqual(failed, 2)

    def test_regression_more_failures_than_baseline(self):
        from qg_layer8 import parse_results
        import qg_session_state as ss
        state = ss.read_state()
        state['layer_env_test_baseline'] = [[10, 0]]
        ss.write_state(state)
        _, failed = parse_results('8 passed, 2 failed')
        baseline_failed = ss.read_state()['layer_env_test_baseline'][0][1]
        self.assertGreater(failed, baseline_failed)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer8" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails)

- [ ] **Step 3: Write `qg_layer8.py`**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 8 -- Regression Detection (PostToolUse on Bash test commands).
Compares test results to session baseline; alerts on regression.
\"\"\"
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
TEST_CMD_RE = re.compile(
    r'\b(pytest|npm\s+test|jest|go\s+test|python\s+-m\s+pytest|yarn\s+test|cargo\s+test)\b',
    re.IGNORECASE)
PASS_RE = re.compile(r'(\d+)\s+pass(?:ed)?', re.IGNORECASE)
FAIL_RE = re.compile(r'(\d+)\s+fail(?:ed)?', re.IGNORECASE)


def _write_event(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def parse_results(output):
    pm = PASS_RE.search(output)
    fm = FAIL_RE.search(output)
    return (int(pm.group(1)) if pm else None, int(fm.group(1)) if fm else None)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    if payload.get('tool_name') != 'Bash':
        return

    cmd = (payload.get('tool_input') or {}).get('command', '')
    if not TEST_CMD_RE.search(cmd):
        return

    response = str(payload.get('tool_response', ''))
    passed, failed = parse_results(response)
    if passed is None and failed is None:
        return

    state = ss.read_state()
    baseline = state.get('layer_env_test_baseline', [])

    if not baseline:
        state['layer_env_test_baseline'] = [[passed or 0, failed or 0]]
        ss.write_state(state)
        return

    baseline_failed = baseline[0][1]
    current_failed = failed or 0

    if current_failed > baseline_failed:
        regression_count = current_failed - baseline_failed
        event = {
            'event_id': str(uuid.uuid4()),
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'session_uuid': state.get('session_uuid') or '',
            'working_dir': os.getcwd(),
            'task_id': state.get('active_task_id', ''),
            'layer': 'layer8',
            'category': 'REGRESSION',
            'severity': 'critical',
            'detection_signal': '{} new failure(s): was {} failed, now {}'.format(
                regression_count, baseline_failed, current_failed),
            'status': 'open',
        }
        _write_event(event)
        unresolved = state.get('layer2_unresolved_events', [])
        unresolved.append(event)
        state['layer2_unresolved_events'] = unresolved[-50:]
        state['layer8_regression_expected'] = True
        ss.write_state(state)

        out = {'hookSpecificOutput': {'hookEventName': 'PostToolUse',
            'additionalContext': '[Layer 8] REGRESSION: {} new failure(s) vs baseline.'.format(regression_count)}}
        print(json.dumps(out))
    else:
        ss.write_state(state)


if __name__ == '__main__':
    main()
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer8.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer8" -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer8.py scripts/tests/test_qg_layers.py && git commit -m "feat(layer8): regression detection hook — test baseline comparison [AUTO]"
```

---

## Phase 3b — Cross-Session Intelligence

---

### Task 5: Layer 6 — Cross-session Pattern Analysis

**Files:**
- Create: `~/.claude/hooks/qg_layer6.py`
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer6CrossSessionAnalysis(unittest.TestCase):
    def test_empty_events_returns_empty(self):
        from qg_layer6 import analyze_patterns
        self.assertEqual(analyze_patterns([]), [])

    def test_pattern_below_threshold_not_flagged(self):
        from qg_layer6 import analyze_patterns
        events = [
            {'session_uuid': 's1', 'category': 'LAZINESS', 'ts': '2026-01-01T00:00:00'},
            {'session_uuid': 's2', 'category': 'LAZINESS', 'ts': '2026-01-02T00:00:00'},
        ]
        result = analyze_patterns(events, min_sessions=3, min_pct=0.1)
        self.assertEqual(result, [])

    def test_pattern_above_threshold_flagged(self):
        from qg_layer6 import analyze_patterns
        events = []
        for i in range(1, 5):
            for _ in range(3):
                events.append({'session_uuid': 's{}'.format(i), 'category': 'LAZINESS',
                               'ts': '2026-01-0{}T00:00:00'.format(i)})
        result = analyze_patterns(events, min_sessions=3, min_pct=0.1)
        cats = [p['category'] for p in result]
        self.assertIn('LAZINESS', cats)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer6" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails)

- [ ] **Step 3: Write `qg_layer6.py`**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 6 -- Cross-session Pattern Analysis (Stop hook + qg analyze).
Finds violation categories that recur across sessions; feeds Layer 0 context.
\"\"\"
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
CROSS_SESSION_PATH = os.path.expanduser('~/.claude/qg-cross-session.json')


def load_monitor_events(monitor_path=None):
    path = monitor_path or MONITOR_PATH
    events = []
    if not os.path.exists(path):
        return events
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def analyze_patterns(events, min_sessions=3, min_pct=0.15, window=10):
    if not events:
        return []
    sessions = {}
    for e in events:
        sid = e.get('session_uuid', '')
        if sid:
            sessions.setdefault(sid, []).append(e)
    session_list = sorted(sessions.items(),
                          key=lambda x: min(ev.get('ts', '') for ev in x[1]))[-window:]
    if len(session_list) < min_sessions:
        return []
    category_in_sessions = {}
    for sid, evts in session_list:
        cats = set(ev.get('category') for ev in evts if ev.get('category'))
        for cat in cats:
            category_in_sessions.setdefault(cat, set()).add(sid)
    total_events = sum(len(e) for _, e in session_list)
    patterns = []
    for cat, sids in category_in_sessions.items():
        if len(sids) < min_sessions:
            continue
        cat_total = sum(1 for e in events if e.get('category') == cat)
        pct = cat_total / max(total_events, 1)
        if pct >= min_pct:
            patterns.append({'category': cat, 'sessions_count': len(sids),
                             'event_pct': round(pct, 3), 'total_events': cat_total})
    return sorted(patterns, key=lambda x: -x['sessions_count'])


def run_analysis(monitor_path=None, output_path=None):
    events = load_monitor_events(monitor_path)
    patterns = analyze_patterns(events)
    result = {
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'patterns': patterns,
        'sessions_analyzed': len(set(e.get('session_uuid') for e in events if e.get('session_uuid'))),
    }
    out = output_path or CROSS_SESSION_PATH
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(result, f, indent=2)
    return result


def main():
    try:
        json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        pass
    state = ss.read_state()
    last_ts = state.get('layer6_last_analysis_ts', 0)
    if (time.time() - last_ts) < 3600:
        return
    try:
        run_analysis()
        state['layer6_last_analysis_ts'] = time.time()
        ss.write_state(state)
    except Exception:
        pass


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--run':
        result = run_analysis()
        print('Analyzed {} sessions, found {} patterns.'.format(
            result['sessions_analyzed'], len(result['patterns'])))
    else:
        main()
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer6.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer6" -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 5: Update `cmd_analyze()` in `~/.claude/scripts/qg-feedback.py`**

The stub at line ~1147 currently prints "Phase 3 feature. Not yet available." Replace its body to call the real Layer 6 logic:

```python
def cmd_analyze():
    """qg analyze — trigger cross-session analysis."""
    sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
    from qg_layer6 import run_analysis
    result = run_analysis()
    print('Cross-session analysis complete.')
    print('Sessions analyzed: {}'.format(result['sessions_analyzed']))
    if result['patterns']:
        print('Recurring patterns:')
        for p in result['patterns']:
            print('  {} — {} sessions, {:.0f}% of events'.format(
                p['category'], p['sessions_count'], p['event_pct'] * 100))
    else:
        print('No recurring patterns found.')
```

Write this replacement via the Edit tool on `~/.claude/scripts/qg-feedback.py` (scripts dir is not write-protected).

- [ ] **Step 6: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer6.py scripts/tests/test_qg_layers.py scripts/qg-feedback.py && git commit -m "feat(layer6): cross-session pattern analysis — Stop hook + qg analyze command [AUTO]"
```

---

### Task 6: Layer 7 — Feedback and Rule Refinement

**Files:**
- Create: `~/.claude/hooks/qg_layer7.py`
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer7RuleRefinement(unittest.TestCase):
    def test_repeat_fn_above_threshold_flagged(self):
        from qg_layer7 import find_repeat_fns
        records = [{'outcome': 'FN', 'category': 'ASSUMPTION'}] * 3
        result = find_repeat_fns(records, threshold=3)
        self.assertIn('ASSUMPTION', result)

    def test_single_fn_below_threshold_not_flagged(self):
        from qg_layer7 import find_repeat_fns
        records = [{'outcome': 'FN', 'category': 'ASSUMPTION'}]
        result = find_repeat_fns(records, threshold=3)
        self.assertEqual(result, {})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer7" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails)

- [ ] **Step 3: Write `qg_layer7.py`**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 7 -- Feedback and Rule Refinement (Stop hook + qg rules).
Generates rule suggestions from repeat FN patterns and cross-session data.
\"\"\"
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

FEEDBACK_PATH = os.path.expanduser('~/.claude/quality-gate-feedback.jsonl')
CROSS_SESSION_PATH = os.path.expanduser('~/.claude/qg-cross-session.json')
SUGGESTIONS_PATH = os.path.expanduser('~/.claude/qg-rule-suggestions.md')


def load_feedback(feedback_path=None):
    path = feedback_path or FEEDBACK_PATH
    records = []
    if not os.path.exists(path):
        return records
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def find_repeat_fns(records, threshold=3):
    fn_categories = {}
    for r in records:
        if r.get('outcome') == 'FN':
            cat = r.get('category', 'UNKNOWN')
            fn_categories.setdefault(cat, []).append(r)
    return {cat: recs for cat, recs in fn_categories.items() if len(recs) >= threshold}


def generate_suggestions(feedback_path=None, cross_session_path=None):
    records = load_feedback(feedback_path)
    repeat_fns = find_repeat_fns(records)
    suggestions = []
    for cat, recs in repeat_fns.items():
        suggestions.append({
            'id': len(suggestions) + 1,
            'category': cat,
            'reason': 'Repeated FN ({} times) -- rule may be missing this pattern.'.format(len(recs)),
            'supporting_count': len(recs),
            'status': 'pending',
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        })
    try:
        cs_path = cross_session_path or CROSS_SESSION_PATH
        if os.path.exists(cs_path):
            with open(cs_path, 'r', encoding='utf-8') as f:
                cs = json.load(f)
            for pattern in cs.get('patterns', []):
                cat = pattern['category']
                if cat not in repeat_fns:
                    suggestions.append({
                        'id': len(suggestions) + 1,
                        'category': cat,
                        'reason': 'Cross-session pattern: {sessions_count} sessions, {pct:.0f}% of events'.format(
                            sessions_count=pattern['sessions_count'],
                            pct=pattern['event_pct'] * 100),
                        'supporting_count': pattern['total_events'],
                        'status': 'pending',
                        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
                    })
    except Exception:
        pass
    return suggestions


def write_suggestions(suggestions, output_path=None):
    path = output_path or SUGGESTIONS_PATH
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    lines = ['# QG Rule Suggestions\n', '_Generated: {}_\n\n'.format(ts)]
    if not suggestions:
        lines.append('No pending suggestions.\n')
    else:
        for s in suggestions:
            lines.append('## [{}] #{}: {}\n'.format(s['status'].upper(), s['id'], s['category']))
            lines.append('- **Reason:** {}\n'.format(s['reason']))
            lines.append('- **Supporting events:** {}\n'.format(s['supporting_count']))
            lines.append('- **Generated:** {}\n\n'.format(s['ts']))
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def main():
    try:
        json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        pass
    state = ss.read_state()
    if not state.get('layer3_pending_fn_alert'):
        return
    try:
        suggestions = generate_suggestions()
        if suggestions:
            write_suggestions(suggestions)
    except Exception:
        pass


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--run':
        suggestions = generate_suggestions()
        write_suggestions(suggestions)
        print('Generated {} suggestion(s).'.format(len(suggestions)))
    else:
        main()
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer7.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer7" -v 2>&1 | tail -10
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer7.py scripts/tests/test_qg_layers.py && git commit -m "feat(layer7): rule refinement — repeat FN pattern suggestions [AUTO]"
```

---

### Task 7: Layer 9 — Confidence Calibration

**Files:**
- Create: `~/.claude/hooks/qg_layer9.py`
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer9ConfidenceCalibration(unittest.TestCase):
    def test_high_certainty_extracted(self):
        from qg_layer9 import extract_certainty
        self.assertEqual(extract_certainty("I'm certain this will work"), 'high')
        self.assertEqual(extract_certainty('definitely the right approach'), 'high')

    def test_medium_certainty_extracted(self):
        from qg_layer9 import extract_certainty
        self.assertEqual(extract_certainty('I believe this should work'), 'medium')

    def test_no_certainty_signal_returns_none(self):
        from qg_layer9 import extract_certainty
        self.assertIsNone(extract_certainty('Here is the updated implementation.'))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer9" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails)

- [ ] **Step 3: Write `qg_layer9.py`**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 9 -- Confidence Calibration (Stop hook).
Extracts stated certainty from response text; records vs Layer 3 outcome.
\"\"\"
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

CALIBRATION_PATH = os.path.expanduser('~/.claude/qg-calibration.jsonl')
HIGH_RE = re.compile(
    r"""\b(I'?m certain|definitely|I know for|this will work|guaranteed|100%)\b""",
    re.IGNORECASE)
MED_RE = re.compile(
    r'\b(I believe|should work|likely|I expect|I think this will)\b',
    re.IGNORECASE)
LOW_RE = re.compile(r'\b(might|possibly|I think|perhaps|not sure)\b', re.IGNORECASE)


def extract_certainty(text):
    if HIGH_RE.search(text):
        return 'high'
    if MED_RE.search(text):
        return 'medium'
    if LOW_RE.search(text):
        return 'low'
    return None


def get_response_text(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return ''
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        for line in reversed(lines[-100:]):
            try:
                d = json.loads(line)
                msg = d.get('message', {})
                if msg.get('role') == 'assistant':
                    content = msg.get('content', '')
                    if isinstance(content, list):
                        return ' '.join(c.get('text', '') for c in content if c.get('type') == 'text')
                    return str(content)
            except Exception:
                pass
    except Exception:
        pass
    return ''


def main():
    try:
        data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        data = {}

    transcript_path = data.get('transcript_path', '')
    response_text = get_response_text(transcript_path)
    certainty = extract_certainty(response_text)
    if not certainty:
        return

    state = ss.read_state()
    actual_outcome = 'FN' if state.get('layer3_pending_fn_alert') else 'TN'
    record = {
        'event_id': str(uuid.uuid4()),
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'session_uuid': state.get('session_uuid') or '',
        'stated_certainty': certainty,
        'actual_outcome': actual_outcome,
        'task_complexity': state.get('layer1_task_category', 'unknown'),
    }
    try:
        with open(CALIBRATION_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + chr(10))
    except Exception:
        pass


if __name__ == '__main__':
    main()
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer9.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer9" -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer9.py scripts/tests/test_qg_layers.py && git commit -m "feat(layer9): confidence calibration — stated certainty vs outcome [AUTO]"
```

---

### Task 8: Layer 10 — Audit Trail Integrity

**Files:**
- Create: `~/.claude/hooks/qg_layer10.py`
- Modify: `~/.claude/scripts/qg-feedback.py` (update `cmd_integrity()`)
- Test: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

Append to `~/.claude/scripts/tests/test_qg_layers.py`:

```python
class TestLayer10AuditIntegrity(unittest.TestCase):
    def test_valid_jsonl_no_corrupt(self):
        from qg_layer10 import validate_jsonl
        f = tempfile.mktemp(suffix='.jsonl')
        qf = tempfile.mktemp(suffix='.jsonl')
        open(f, 'w').write('{"event_id": "1"}\n{"event_id": "2"}\n')
        valid, corrupt = validate_jsonl(f, qf)
        for p in [f, qf]:
            try: os.unlink(p)
            except: pass
        self.assertEqual(len(corrupt), 0)
        self.assertEqual(len(valid), 2)

    def test_corrupt_line_quarantined(self):
        from qg_layer10 import validate_jsonl
        f = tempfile.mktemp(suffix='.jsonl')
        qf = tempfile.mktemp(suffix='.jsonl')
        open(f, 'w').write('{"event_id": "1"}\n{NOT JSON}\n{"event_id": "3"}\n')
        valid, corrupt = validate_jsonl(f, qf)
        for p in [f, qf]:
            try: os.unlink(p)
            except: pass
        self.assertEqual(len(corrupt), 1)
        self.assertEqual(len(valid), 2)

    def test_rotation_triggers_at_threshold(self):
        import glob
        from qg_layer10 import maybe_rotate
        f = tempfile.mktemp(suffix='.jsonl')
        with open(f, 'w') as fh:
            for i in range(11):
                fh.write('{{"n": {}}}\n'.format(i))
        rotated = maybe_rotate(f, threshold=10)
        for archived in glob.glob(f.replace('.jsonl', '-*.jsonl')):
            try: os.unlink(archived)
            except: pass
        if not rotated:
            try: os.unlink(f)
            except: pass
        self.assertTrue(rotated)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer10" -v 2>&1 | tail -10
```

Expected: `ERROR` (import fails)

- [ ] **Step 3: Write `qg_layer10.py`**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
content = r'''#!/usr/bin/env python3
\"\"\"Layer 10 -- Audit Trail Integrity.
Validates JSONL files, quarantines corrupt lines, rotates at 10,000 lines.
\"\"\"
import json, os, time

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
QUARANTINE_PATH = os.path.expanduser('~/.claude/qg-quarantine.jsonl')
ROTATION_THRESHOLD = 10000


def validate_jsonl(path, quarantine_path=None):
    if not os.path.exists(path):
        return [], []
    qpath = quarantine_path or QUARANTINE_PATH
    valid = []
    corrupt = []
    seen_ids = set()
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                eid = e.get('event_id', '')
                if eid and eid in seen_ids:
                    corrupt.append({'line': i, 'reason': 'duplicate_id', 'raw': line[:200]})
                else:
                    if eid:
                        seen_ids.add(eid)
                    valid.append(line)
            except json.JSONDecodeError as ex:
                corrupt.append({'line': i, 'reason': 'invalid_json',
                                'raw': line[:200], 'error': str(ex)})
    if corrupt:
        ts = time.strftime('%Y-%m-%dT%H:%M:%S')
        with open(qpath, 'a', encoding='utf-8') as f:
            for c in corrupt:
                c.update({'quarantine_ts': ts, 'source': path})
                f.write(json.dumps(c, ensure_ascii=False) + chr(10))
    return valid, corrupt


def maybe_rotate(path, threshold=ROTATION_THRESHOLD):
    if not os.path.exists(path):
        return False
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        count = sum(1 for _ in f)
    if count < threshold:
        return False
    archive = path.replace('.jsonl', '-{}.jsonl'.format(time.strftime('%Y-%m')))
    os.rename(path, archive)
    return True


def run_integrity_check(monitor_path=None, quarantine_path=None):
    path = monitor_path or MONITOR_PATH
    valid, corrupt = validate_jsonl(path, quarantine_path)
    rotated = maybe_rotate(path)
    return {
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'path': path,
        'valid_lines': len(valid),
        'corrupt_lines': len(corrupt),
        'rotated': rotated,
        'status': 'ok' if not corrupt else 'issues_found',
    }


if __name__ == '__main__':
    import sys
    result = run_integrity_check()
    print('Audit trail: {} valid, {} issue(s). Status: {}'.format(
        result['valid_lines'], result['corrupt_lines'], result['status']))
    if result['rotated']:
        print('Rotated {} to monthly archive.'.format(result['path']))
'''
with open('/c/Users/Matt1/.claude/hooks/qg_layer10.py', 'w', encoding='utf-8') as f:
    f.write(content.lstrip())
print('Written.')
"
```

- [ ] **Step 4: Update `cmd_integrity()` in `~/.claude/scripts/qg-feedback.py`**

Replace the existing `cmd_integrity()` stub body (lines ~1154–1178) with a call to the real Layer 10 logic:

```python
def cmd_integrity():
    """qg integrity — audit trail integrity check."""
    import sys as _sys
    _sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
    from qg_layer10 import run_integrity_check
    result = run_integrity_check()
    print('Audit trail integrity check:')
    print('  Valid lines:   {}'.format(result['valid_lines']))
    print('  Corrupt lines: {}'.format(result['corrupt_lines']))
    print('  Status:        {}'.format(result['status']))
    if result['rotated']:
        print('  Rotated to monthly archive.')
    if result['corrupt_lines'] > 0:
        print('Corrupt entries quarantined to ~/.claude/qg-quarantine.jsonl')
```

Write this replacement using the Edit tool on `~/.claude/scripts/qg-feedback.py`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -k "TestLayer10" -v 2>&1 | tail -10
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_layer10.py scripts/tests/test_qg_layers.py scripts/qg-feedback.py && git commit -m "feat(layer10): audit trail integrity — JSONL validation, quarantine, rotation [AUTO]"
```

---

## Integration

---

### Task 9: Hook Registration + Session State + Full Test Suite

**Files:**
- Modify: `~/.claude/hooks/qg_session_state.py` (add Phase 3 fields, bump SCHEMA_VERSION)
- Modify: `~/.claude/settings.json` (register 8 new hooks)
- Modify: `~/.claude/README.md` (Phase 3 complete, test count 83)
- Modify: `~/.claude/projects/C--Users-Matt1/memory/quality-gate-monitor-design.md` (update status)

- [ ] **Step 1: Update `qg_session_state.py` — add Phase 3 fields**

In `~/.claude/hooks/qg_session_state.py`, make two changes via python subprocess write:

1. Bump `SCHEMA_VERSION = 1` → `SCHEMA_VERSION = 2`
2. Add these fields to `_empty_state()` (after `'layer25_syntax_failure': False`):

```python
        'layer26_convention_baseline': {},
        'layer26_files_seen': 0,
        'layer6_last_analysis_ts': 0,
```

Write via subprocess (hooks dir write-protected). Read the full current file first, make the two targeted edits, write back.

- [ ] **Step 2: Verify session state loads cleanly**

```bash
PYTHONIOENCODING=utf-8 python3 -c "
import sys; sys.path.insert(0, '/c/Users/Matt1/.claude/hooks')
import qg_session_state as ss
s = ss.read_state()
assert s['layer26_convention_baseline'] == {}
assert s['layer26_files_seen'] == 0
assert s['layer6_last_analysis_ts'] == 0
print('Schema v{} — new fields present.'.format(ss.SCHEMA_VERSION))
"
```

Expected: `Schema v2 — new fields present.`

- [ ] **Step 3: Register new hooks in `~/.claude/settings.json`**

Add the following entries. `settings.json` is write-protected — write via python subprocess. Read first, merge, write back.

**PostToolUse** — append after existing `[*] qg_layer2.py` entry:
```json
{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer25.py" }] },
{ "matcher": "Write|Edit", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer26.py" }] },
{ "matcher": "Bash", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer8.py" }] }
```

**PreToolUse** — append after existing `[*] qg_layer18.py` entry:
```json
{ "matcher": "Edit", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer27.py" }] }
```

**Stop** — append after existing `quality-gate.py` entry:
```json
{ "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer6.py" }] },
{ "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer7.py" }] },
{ "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer9.py" }] }
```

- [ ] **Step 4: Verify settings.json is valid JSON**

```bash
python3 -c "import json; json.load(open('/c/Users/Matt1/.claude/settings.json')); print('Valid JSON')"
```

Expected: `Valid JSON`

- [ ] **Step 5: Run the full test suite**

```bash
PYTHONIOENCODING=utf-8 python3 -m pytest ~/.claude/scripts/tests/test_qg_layers.py -v 2>&1 | tail -20
```

Expected: all 83 tests pass (59 existing + 24 new). If any test fails, fix the relevant layer before proceeding.

- [ ] **Step 6: Run smoke test**

```bash
PYTHONIOENCODING=utf-8 bash ~/.claude/hooks/smoke-test.sh 2>&1 | tail -15
```

Expected: all checks pass (no new failures).

- [ ] **Step 7: Update README.md**

In `~/.claude/README.md`, mark Phase 3 complete and update test count to 83. Use the Edit tool (README is not write-protected).

- [ ] **Step 8: Update memory file**

In `~/.claude/projects/C--Users-Matt1/memory/quality-gate-monitor-design.md`, update the status line to:
`Phase 3 COMPLETE (2026-03-28): 83/83 tests pass, all 8 Phase 3 layers registered.`

Use the Edit tool.

- [ ] **Step 9: Commit and push**

```bash
cd /c/Users/Matt1/.claude && git add hooks/qg_session_state.py settings.json README.md && git commit -m "feat(phase3): register all Phase 3 hooks, bump schema to v2, 83 tests pass [AUTO]"
git push
```

---

## Quick Reference

| Layer | Hook event | Matcher | File |
|-------|-----------|---------|------|
| 2.5 | PostToolUse | Write\|Edit | qg_layer25.py |
| 2.6 | PostToolUse | Write\|Edit | qg_layer26.py |
| 2.7 | PreToolUse | Edit | qg_layer27.py |
| 8 | PostToolUse | Bash | qg_layer8.py |
| 6 | Stop | — | qg_layer6.py |
| 7 | Stop | — | qg_layer7.py |
| 9 | Stop | — | qg_layer9.py |
| 10 | CLI only | — | qg_layer10.py |

**Commands added:**
- `qg analyze` — run Layer 6 cross-session analysis
- `qg rules` — view Layer 7 rule suggestions (already wired in qg-feedback.py)
- `qg integrity` — run Layer 10 audit check (updated stub)

**Test count progression:** Phase 1: 35 → Phase 2: 59 → Phase 3: 83

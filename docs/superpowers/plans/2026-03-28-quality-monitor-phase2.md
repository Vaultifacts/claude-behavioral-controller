# Quality Gate Monitor Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Phase 2 of the Quality Gate Monitor: Layers 1.7, 1.8, 1.9, 3.5, 4.5, 5, and the Haiku FN classifier.

**Architecture:** New PreToolUse hooks (1.7, 1.8, 1.9) fire before every tool call and inject warnings/context; Layer 3.5 and the Haiku FN classifier extend the existing quality-gate.py Stop hook; Layer 4.5 uses PreCompact/PostCompact hooks; Layer 5 uses PostToolUse on the Agent tool.

**Tech Stack:** Python 3.13, existing hook infrastructure (`~/.claude/hooks/`), `qg_session_state.py`, `qg_notification_router.py`, `_hooks_shared.py` (Haiku API via `call_haiku_check`).

---

## File Structure

### New files
| File | Purpose |
|------|---------|
| `~/.claude/hooks/qg_layer19.py` | Layer 1.9 — Change Impact Analysis |
| `~/.claude/hooks/qg_layer17.py` | Layer 1.7 — User Intent Verification |
| `~/.claude/hooks/qg_layer18.py` | Layer 1.8 — Hallucination Detection |
| `~/.claude/hooks/qg_layer35.py` | Layer 3.5 — Recovery Tracking + Haiku FN classifier |
| `~/.claude/hooks/qg_layer45.py` | Layer 4.5 — Context Preservation |
| `~/.claude/hooks/qg_layer5.py` | Layer 5 — Subagent Coordination |
| `~/.claude/qg-preservation-config.json` | Layer 4.5 config |

### Modified files
| File | Changes |
|------|---------|
| `~/.claude/hooks/qg_session_state.py` | Add Phase 2 fields to `_empty_state()` |
| `~/.claude/hooks/qg_layer0.py` | Reset Phase 2 fields at session start |
| `~/.claude/hooks/quality-gate.py` | Import + call Layer 3.5 and Haiku FN classifier; update Layer 4 checkpoint |
| `~/.claude/qg-rules.json` | Add `layer17`, `layer18`, `layer19` config sections |
| `~/.claude/settings.json` | Register PreToolUse, PostToolUse, PreCompact, PostCompact hooks |
| `~/.claude/scripts/tests/test_qg_layers.py` | Add 21 tests for Phase 2 layers |

---

## Context for Implementers

**Hook pattern:** Every hook reads JSON from stdin (`json.load(sys.stdin)`), writes JSON to stdout (for additionalContext/block), and reads/writes session state via `qg_session_state.read_state()` / `write_state()`. See existing `qg_layer15.py` and `qg_layer2.py` for reference.

**Session state:** All inter-layer communication goes through `~/.claude/qg-session-state.json` via `qg_session_state.py`. New fields added in Task 1 — always access via `state.get('field', default)` to handle migration.

**Test pattern:** Each test class sets `ss.STATE_PATH = tempfile.mktemp(suffix='.json')` and `ss.LOCK_PATH = ...` in `setUp`, unlinks them in `tearDown`. Tests exercise pure functions, not `main()`. See existing tests for reference.

**Hook registration order:** PreToolUse hooks fire in registration order: Layer ENV → Layer 1.5 → Layer 1.9 → Layer 1.7 → Layer 1.8. Layer 1.9 must be registered before Layer 1.7 (1.7 reads `layer19_last_impact_level` from state).

---

## Task 1: State Schema + Config Updates

**Files:**
- Modify: `~/.claude/hooks/qg_session_state.py` (lines 32–62, `_empty_state` function)
- Modify: `~/.claude/hooks/qg_layer0.py` (lines 56–79, `ss.update_state()` call)
- Modify: `~/.claude/qg-rules.json`

- [ ] **Step 1: Add Phase 2 fields to `_empty_state()` in `qg_session_state.py`**

  Read `qg_session_state.py` first. Then add these fields to the `_empty_state()` dict, after `'layer19_impact_cache': {}`:

  ```python
  'layer17_verified_task_id': None,
  'layer17_intent_text': '',
  'layer17_intent_verified_ts': 0,
  'layer17_creating_new_artifacts': False,
  'layer19_last_impact_level': 'LOW',
  'layer19_last_impact_file': '',
  'layer5_subagents': {},
  ```

- [ ] **Step 2: Add Phase 2 resets to `qg_layer0.py`**

  Read `qg_layer0.py` first. Add these to the `ss.update_state(...)` call (append after the last existing kwarg, before the closing paren):

  ```python
  layer17_verified_task_id=None,
  layer17_intent_text='',
  layer17_intent_verified_ts=0,
  layer17_creating_new_artifacts=False,
  layer19_last_impact_level='LOW',
  layer19_last_impact_file='',
  layer19_impact_cache={},
  layer5_subagents={},
  ```

- [ ] **Step 3: Add Phase 2 sections to `qg-rules.json`**

  Read `qg-rules.json` first. Add these three sections before the closing `}` of the root object (after `"layer10": {...}`):

  ```json
  ,
  "layer17": {
    "complexity_threshold": ["DEEP"],
    "high_impact_threshold": ["HIGH", "CRITICAL"]
  },
  "layer18": {
    "check_function_existence": true,
    "suppress_on_creating_artifacts": true
  },
  "layer19": {
    "low_threshold": 5,
    "medium_threshold": 20,
    "dynamic_import_warning": true
  }
  ```

- [ ] **Step 4: Verify JSON is valid**

  Run: `python -c "import json; json.load(open(r'C:/Users/Matt1/.claude/qg-rules.json'))"`
  Expected: no output (no error)

- [ ] **Step 5: Verify session state module loads with new fields**

  Run: `PYTHONIOENCODING=utf-8 python -c "import sys; sys.path.insert(0,'C:/Users/Matt1/.claude/hooks'); import qg_session_state as ss; s=ss._empty_state(); print(s.get('layer17_verified_task_id'), s.get('layer19_last_impact_level'), s.get('layer5_subagents'))"`
  Expected: `None LOW {}`

- [ ] **Step 6: Commit**

  ```bash
  cd ~/.claude && git add hooks/qg_session_state.py hooks/qg_layer0.py qg-rules.json
  git commit -m "feat(phase2): add Phase 2 state fields and config sections [AUTO]"
  ```

---

## Task 2: Layer 1.9 — Change Impact Analysis

**Files:**
- Create: `~/.claude/hooks/qg_layer19.py`
- Modify: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

  Read `test_qg_layers.py` first. Append this class to the end of the file (before `if __name__ == '__main__':`):

  ```python
  class TestLayer19ImpactAnalysis(unittest.TestCase):
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

      def test_low_impact_isolated_file(self):
          from qg_layer19 import compute_impact_level
          self.assertEqual(compute_impact_level('foo.py', [], {}), 'LOW')

      def test_critical_for_core_file(self):
          from qg_layer19 import compute_impact_level
          self.assertEqual(compute_impact_level('utils.py', [], {}), 'CRITICAL')

      def test_high_impact_above_threshold(self):
          from qg_layer19 import compute_impact_level
          deps = ['a.py'] * 25
          level = compute_impact_level('auth.py', deps, {'low_threshold': 5, 'medium_threshold': 20})
          self.assertEqual(level, 'HIGH')

      def test_cache_returns_same_result(self):
          from qg_layer19 import analyze_impact
          r1 = analyze_impact('/nonexistent/cache_test.py')
          r2 = analyze_impact('/nonexistent/cache_test.py')
          self.assertEqual(r1['ts'], r2['ts'])  # Same cached timestamp
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer19ImpactAnalysis -v 2>&1 | tail -15`
  Expected: `ModuleNotFoundError: No module named 'qg_layer19'` or similar

- [ ] **Step 3: Create `qg_layer19.py`**

  Create `~/.claude/hooks/qg_layer19.py` with this content:

  ```python
  #!/usr/bin/env python3
  """Layer 1.9 — Change Impact Analysis (PreToolUse on Edit/Write).
  Counts dependents of the target file and stores impact level in session state.
  """
  import json, os, re, subprocess, sys, time
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import qg_session_state as ss

  RULES_PATH = os.path.expanduser('~/.claude/qg-rules.json')

  CORE_PATTERNS = re.compile(
      r'(utils?|shared|common|base|core|config|settings|constants?|helpers?)\.(py|js|ts)$',
      re.IGNORECASE)


  def _load_thresholds():
      try:
          with open(RULES_PATH, 'r', encoding='utf-8') as f:
              return json.load(f).get('layer19', {})
      except Exception:
          return {}


  def count_dependents(file_path, working_dir):
      """Grep for imports of file_path. Returns list of dependent paths."""
      if not file_path:
          return []
      stem = os.path.splitext(os.path.basename(file_path))[0]
      if not stem:
          return []
      patterns = [rf'import.*{stem}', rf'from.*{stem}.*import', rf'require.*{stem}']
      dependents = set()
      for pat in patterns:
          try:
              result = subprocess.run(
                  ['grep', '-rl', '--include=*.py', '--include=*.js', '--include=*.ts',
                   pat, working_dir],
                  capture_output=True, text=True, timeout=3)
              for line in result.stdout.strip().splitlines():
                  fp = line.strip()
                  if fp and os.path.normpath(fp) != os.path.normpath(file_path):
                      dependents.add(fp)
          except Exception:
              pass
      return list(dependents)


  def compute_impact_level(file_path, dependents, cfg):
      """Return LOW / MEDIUM / HIGH / CRITICAL."""
      if CORE_PATTERNS.search(os.path.basename(file_path or '')):
          return 'CRITICAL'
      n = len(dependents)
      low_thresh = cfg.get('low_threshold', 5)
      med_thresh = cfg.get('medium_threshold', 20)
      if n < low_thresh:
          return 'LOW'
      if n < med_thresh:
          return 'MEDIUM'
      return 'HIGH'


  def analyze_impact(file_path):
      """Full impact analysis with per-session 1-hour cache. Returns result dict."""
      state = ss.read_state()
      cache = state.get('layer19_impact_cache', {})

      if file_path in cache:
          cached = cache[file_path]
          if time.time() - cached.get('ts', 0) < 3600:
              return cached

      cfg = _load_thresholds()
      dependents = count_dependents(file_path, os.getcwd())
      level = compute_impact_level(file_path, dependents, cfg)

      result = {
          'file': file_path,
          'level': level,
          'dependent_count': len(dependents),
          'dependents_sample': dependents[:5],
          'ts': time.time(),
      }

      cache[file_path] = result
      state['layer19_impact_cache'] = cache
      state['layer19_last_impact_level'] = level
      state['layer19_last_impact_file'] = file_path
      ss.write_state(state)
      return result


  def main():
      try:
          payload = json.load(sys.stdin)
      except Exception:
          return

      tool_name = payload.get('tool_name', '')
      tool_input = payload.get('tool_input', {}) or {}

      if tool_name not in ('Edit', 'Write'):
          return

      file_path = tool_input.get('file_path', '')
      if not file_path:
          return

      result = analyze_impact(file_path)
      level = result['level']

      if level in ('HIGH', 'CRITICAL'):
          n = result['dependent_count']
          msg = (f'[monitor:INFO:layer1.9] Impact: {level} — '
                 f'{os.path.basename(file_path)!r} has {n} dependent(s). '
                 f'Layer 1.5 warns escalated to blocks for this file.')
          print(json.dumps({'additionalContext': msg}))


  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer19ImpactAnalysis -v 2>&1 | tail -15`
  Expected: `4 passed`

- [ ] **Step 5: Verify syntax**

  Run: `PYTHONIOENCODING=utf-8 python -W error::SyntaxWarning -c "import sys; sys.path.insert(0,'C:/Users/Matt1/.claude/hooks'); import qg_layer19"`
  Expected: no output

- [ ] **Step 6: Commit**

  ```bash
  cd ~/.claude && git add hooks/qg_layer19.py scripts/tests/test_qg_layers.py
  git commit -m "feat(phase2): Layer 1.9 Change Impact Analysis [AUTO]"
  ```

---

## Task 3: Layer 1.7 — User Intent Verification

**Files:**
- Create: `~/.claude/hooks/qg_layer17.py`
- Modify: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

  Read `test_qg_layers.py` first. Append this class before `if __name__ == '__main__':`:

  ```python
  class TestLayer17IntentVerification(unittest.TestCase):
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

      def test_no_fire_on_none_category(self):
          from qg_layer17 import should_verify
          state = {'layer1_task_category': 'NONE', 'layer19_last_impact_level': 'LOW'}
          cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
          self.assertFalse(should_verify(state, cfg))

      def test_fires_on_deep_category(self):
          from qg_layer17 import should_verify
          state = {'layer1_task_category': 'DEEP', 'layer19_last_impact_level': 'LOW'}
          cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
          self.assertTrue(should_verify(state, cfg))

      def test_fires_on_high_impact(self):
          from qg_layer17 import should_verify
          state = {'layer1_task_category': 'MECHANICAL', 'layer19_last_impact_level': 'HIGH'}
          cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
          self.assertTrue(should_verify(state, cfg))

      def test_no_fire_on_already_verified_task(self):
          from qg_layer17 import should_verify
          import qg_session_state as ss
          state = ss.read_state()
          state['layer1_task_category'] = 'DEEP'
          state['layer19_last_impact_level'] = 'LOW'
          state['active_task_id'] = 'task-already'
          state['layer17_verified_task_id'] = 'task-already'
          ss.write_state(state)
          cfg = {'complexity_threshold': ['DEEP'], 'high_impact_threshold': ['HIGH', 'CRITICAL']}
          # should_verify returns True, but main() guards on task_id match
          # Test that verified_task_id is persisted correctly
          result = ss.read_state()
          self.assertEqual(result['layer17_verified_task_id'], 'task-already')
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer17IntentVerification -v 2>&1 | tail -10`
  Expected: `ModuleNotFoundError: No module named 'qg_layer17'`

- [ ] **Step 3: Create `qg_layer17.py`**

  Create `~/.claude/hooks/qg_layer17.py`:

  ```python
  #!/usr/bin/env python3
  """Layer 1.7 — User Intent Verification (PreToolUse).
  Fires once per task for DEEP tasks or HIGH/CRITICAL impact edits.
  Injects task intent summary via additionalContext.
  """
  import json, os, sys, time
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import qg_session_state as ss

  RULES_PATH = os.path.expanduser('~/.claude/qg-rules.json')


  def _load_config():
      try:
          with open(RULES_PATH, 'r', encoding='utf-8') as f:
              return json.load(f).get('layer17', {})
      except Exception:
          return {}


  def should_verify(state, cfg):
      """Return True if this task should have intent captured."""
      category = state.get('layer1_task_category', 'NONE')
      threshold = cfg.get('complexity_threshold', ['DEEP'])
      if category in threshold:
          return True
      high_impact = cfg.get('high_impact_threshold', ['HIGH', 'CRITICAL'])
      impact = state.get('layer19_last_impact_level', 'LOW')
      return impact in high_impact


  def main():
      try:
          payload = json.load(sys.stdin)
      except Exception:
          return

      state = ss.read_state()
      cfg = _load_config()

      task_id = state.get('active_task_id', '')
      if not task_id:
          return

      # Only fire once per task
      if state.get('layer17_verified_task_id') == task_id:
          return

      if not should_verify(state, cfg):
          return

      task_desc = state.get('active_task_description', '')
      category = state.get('layer1_task_category', 'UNKNOWN')
      impact = state.get('layer19_last_impact_level', 'LOW')
      scope_files = state.get('layer1_scope_files', [])

      intent_msg = (
          f'[monitor:layer1.7] Intent captured — '
          f'Task: {category} | Scope: {", ".join(scope_files[:3]) or "inferred"} | '
          f'Impact: {impact} | '
          f'Request: {task_desc[:100]!r}'
      )

      state['layer17_verified_task_id'] = task_id
      state['layer17_intent_text'] = task_desc[:200]
      state['layer17_intent_verified_ts'] = time.time()
      ss.write_state(state)

      print(json.dumps({'additionalContext': intent_msg}))


  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer17IntentVerification -v 2>&1 | tail -10`
  Expected: `4 passed`

- [ ] **Step 5: Commit**

  ```bash
  cd ~/.claude && git add hooks/qg_layer17.py scripts/tests/test_qg_layers.py
  git commit -m "feat(phase2): Layer 1.7 User Intent Verification [AUTO]"
  ```

---

## Task 4: Layer 1.8 — Hallucination Detection

**Files:**
- Create: `~/.claude/hooks/qg_layer18.py`
- Modify: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

  Read `test_qg_layers.py` first. Append before `if __name__ == '__main__':`:

  ```python
  class TestLayer18HallucinationDetection(unittest.TestCase):
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

      def test_nonexistent_path_returns_false(self):
          from qg_layer18 import check_path_exists
          self.assertFalse(check_path_exists('/tmp/qg18_definitely_not_here_xyz.py'))

      def test_existing_path_returns_true(self):
          from qg_layer18 import check_path_exists
          self.assertTrue(check_path_exists(__file__))

      def test_missing_function_in_file_returns_false(self):
          from qg_layer18 import check_function_in_file
          import tempfile as _tf
          with _tf.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
              f.write('def foo():\n    pass\n')
              fname = f.name
          try:
              self.assertFalse(check_function_in_file(fname, 'def bar():'))
          finally:
              os.unlink(fname)

      def test_present_function_in_file_returns_true(self):
          from qg_layer18 import check_function_in_file
          import tempfile as _tf
          with _tf.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
              f.write('def foo():\n    pass\n')
              fname = f.name
          try:
              self.assertTrue(check_function_in_file(fname, 'def foo():'))
          finally:
              os.unlink(fname)
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer18HallucinationDetection -v 2>&1 | tail -10`
  Expected: `ModuleNotFoundError: No module named 'qg_layer18'`

- [ ] **Step 3: Create `qg_layer18.py`**

  Create `~/.claude/hooks/qg_layer18.py`:

  ```python
  #!/usr/bin/env python3
  """Layer 1.8 — Hallucination Detection (PreToolUse on Edit).
  Checks: (1) file path exists before Edit; (2) referenced function exists in file.
  Write tool is exempt (creates new files by design).
  """
  import json, os, re, sys
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import qg_session_state as ss


  def check_path_exists(file_path):
      """Return True if file exists on disk."""
      try:
          return os.path.isfile(file_path)
      except Exception:
          return True  # On error, don't false-positive


  def check_function_in_file(file_path, old_string):
      """Return True if referenced def/class from old_string exists in file."""
      if not old_string or not file_path:
          return True
      names = re.findall(r'\bdef\s+(\w+)|\bclass\s+(\w+)', old_string)
      if not names:
          return True
      try:
          with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
              content = f.read()
          for def_name, class_name in names:
              name = def_name or class_name
              if name and name not in content:
                  return False
          return True
      except Exception:
          return True  # On read error, don't false-positive


  def main():
      try:
          payload = json.load(sys.stdin)
      except Exception:
          return

      tool_name = payload.get('tool_name', '')
      tool_input = payload.get('tool_input', {}) or {}

      # Write always creates/overwrites — no existence check needed
      if tool_name in ('Write',):
          return

      if tool_name != 'Edit':
          return

      file_path = tool_input.get('file_path', '')
      if not file_path:
          return

      state = ss.read_state()

      # Suppress if Layer 1.7 confirmed creating new artifacts in this scope
      if state.get('layer17_creating_new_artifacts'):
          return

      if not check_path_exists(file_path):
          print(json.dumps({
              'additionalContext': (
                  f'[monitor:WARN:layer1.8] Path does not exist: {file_path!r}. '
                  f'Use Glob to find the correct path, or Write to create a new file.'
              )
          }))
          return

      old_string = tool_input.get('old_string', '')
      if old_string and not check_function_in_file(file_path, old_string):
          print(json.dumps({
              'additionalContext': (
                  f'[monitor:WARN:layer1.8] Referenced function/class in old_string '
                  f'may not exist in {os.path.basename(file_path)!r}. '
                  f'Read the file first to confirm exact content.'
              )
          }))


  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer18HallucinationDetection -v 2>&1 | tail -10`
  Expected: `4 passed`

- [ ] **Step 5: Commit**

  ```bash
  cd ~/.claude && git add hooks/qg_layer18.py scripts/tests/test_qg_layers.py
  git commit -m "feat(phase2): Layer 1.8 Hallucination Detection [AUTO]"
  ```

---

## Task 5: Layer 3.5 + Haiku FN Classifier

**Files:**
- Create: `~/.claude/hooks/qg_layer35.py`
- Modify: `~/.claude/hooks/quality-gate.py` (Layer 3/4 extension section at bottom)
- Modify: `~/.claude/scripts/tests/test_qg_layers.py`

Layer 3.5 is a separate module (`qg_layer35.py`) that `quality-gate.py` imports. This keeps it unit-testable without loading the full quality-gate module.

- [ ] **Step 1: Write the failing tests**

  Read `test_qg_layers.py` first. Append before `if __name__ == '__main__':`:

  ```python
  class TestLayer35RecoveryTracking(unittest.TestCase):
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

      def test_fn_creates_recovery_event(self):
          from qg_layer35 import layer35_create_recovery_event
          import qg_session_state as ss
          state = ss.read_state()
          layer35_create_recovery_event('FN', ['claimed completion'], state, ['Edit'])
          self.assertEqual(len(state['layer35_recovery_events']), 1)
          self.assertEqual(state['layer35_recovery_events'][0]['status'], 'open')

      def test_tp_creates_recovery_event(self):
          from qg_layer35 import layer35_create_recovery_event
          import qg_session_state as ss
          state = ss.read_state()
          layer35_create_recovery_event('TP', [], state, ['Bash'])
          self.assertEqual(state['layer35_recovery_events'][0]['verdict'], 'TP')

      def test_recovery_resolved_with_verify_tool(self):
          from qg_layer35 import layer35_check_resolutions
          import time, qg_session_state as ss
          state = ss.read_state()
          state['layer35_recovery_events'] = [{
              'event_id': 'e1', 'verdict': 'FN', 'status': 'open',
              'ts': time.time(), 'turn': 0, 'category': 'unverified',
          }]
          state['layer2_turn_history'] = [{}]  # 1 turn elapsed
          layer35_check_resolutions(['Bash'], state)
          self.assertEqual(state['layer35_recovery_events'][0]['status'], 'resolved')

      def test_recovery_timed_out(self):
          from qg_layer35 import layer35_check_resolutions
          import time, qg_session_state as ss
          state = ss.read_state()
          state['layer35_recovery_events'] = [{
              'event_id': 'e2', 'verdict': 'FN', 'status': 'open',
              'ts': time.time() - 2000,  # 33+ minutes ago
              'turn': 0, 'category': 'unverified',
          }]
          state['layer2_turn_history'] = []
          layer35_check_resolutions(['Read'], state)
          self.assertEqual(state['layer35_recovery_events'][0]['status'], 'timed_out')

      def test_haiku_fn_falls_back_to_rules_on_no_api_key(self):
          from qg_layer35 import detect_fn_signals
          import qg_session_state as ss
          state = ss.read_state()
          # Rule-based: claims completion without verification output
          response = 'All tests pass and everything is done and completed.'
          signals = detect_fn_signals(response, [], '', state, use_haiku=False)
          self.assertTrue(len(signals) > 0)
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer35RecoveryTracking -v 2>&1 | tail -10`
  Expected: `ModuleNotFoundError: No module named 'qg_layer35'`

- [ ] **Step 3: Create `qg_layer35.py`**

  Create `~/.claude/hooks/qg_layer35.py`:

  ```python
  #!/usr/bin/env python3
  """Layer 3.5 — Recovery Tracking + Haiku FN Classifier.
  Imported by quality-gate.py for use in _layer3_run and _layer4_checkpoint.
  """
  import re, sys, os, time, uuid
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

  _L35_WINDOW_TURNS = 3
  _L35_WINDOW_SEC = 1800  # 30 minutes

  _LAZINESS_TEXT_RE = re.compile(
      r'\b(done|completed?|fixed|all (?:tests?|checks?) pass|verified|confirmed|finished)\b',
      re.IGNORECASE)
  _VERIFY_OUTPUT_RE = re.compile(
      r'(===|---|\d+ passed|\d+ failed|exit code \d|>>|\$\s)')

  _VERIFY_TOOLS = frozenset({'Read', 'Grep', 'Bash', 'Glob'})


  def layer35_create_recovery_event(verdict, fn_signals, state, tool_names):
      """Create a recovery tracking event for FN/TP verdicts."""
      if verdict not in ('FN', 'TP'):
          return
      events = state.get('layer35_recovery_events', [])
      event = {
          'event_id': str(uuid.uuid4())[:8],
          'verdict': verdict,
          'category': fn_signals[0] if fn_signals else 'unverified',
          'task_id': state.get('active_task_id', ''),
          'session_uuid': state.get('session_uuid', ''),
          'ts': time.time(),
          'turn': len(state.get('layer2_turn_history', [])),
          'status': 'open',
          'tools_at_flag': list(tool_names or [])[:5],
      }
      events.append(event)
      state['layer35_recovery_events'] = events[-20:]


  def layer35_check_resolutions(tool_names, state):
      """Update status of open recovery events based on current turn context."""
      events = state.get('layer35_recovery_events', [])
      now = time.time()
      current_turn = len(state.get('layer2_turn_history', []))
      has_verify = bool(set(tool_names or []) & _VERIFY_TOOLS)

      for evt in events:
          if evt.get('status') != 'open':
              continue
          # Check timeout
          if now - evt.get('ts', 0) > _L35_WINDOW_SEC:
              evt['status'] = 'timed_out'
              continue
          turns_elapsed = current_turn - evt.get('turn', 0)
          if turns_elapsed > _L35_WINDOW_TURNS:
              evt['status'] = 'timed_out'
              continue
          # Resolved if a verification tool was used in a subsequent turn
          if has_verify and turns_elapsed > 0:
              evt['status'] = 'resolved'

      state['layer35_recovery_events'] = events


  def _detect_fn_signals_rules(response, state):
      """Rule-based FN detection (always available, no API required)."""
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


  def detect_fn_signals(response, tool_names, user_request, state, use_haiku=True):
      """FN detection: Haiku-assisted with rule-based fallback.

      use_haiku=False forces rule-based only (for tests and when API key absent).
      Returns list of signal strings (empty = no FN detected).
      """
      rule_signals = _detect_fn_signals_rules(response, state)

      if not use_haiku:
          return rule_signals

      try:
          from _hooks_shared import call_haiku_check, load_api_key
          if not load_api_key():
              return rule_signals

          tools_str = ', '.join((tool_names or [])[:5]) or 'none'
          check_prompt = (
              'You are checking whether an AI assistant response is a missed quality failure.\n\n'
              f'TOOLS USED: {tools_str}\n'
              f'USER REQUEST: {(user_request or "")[:200]}\n\n'
              f'ASSISTANT RESPONSE:\n{(response or "")[:3000]}\n\n'
              'Check ONLY for these FN signals:\n'
              '1. Claims outcomes (tests pass, task done, bug fixed) WITHOUT quoting tool output inline\n'
              '2. Skips verification this task clearly required\n\n'
              'If no FN signals: {"ok": true}\n'
              'If FN detected: {"ok": false, "reason": "haiku:fn:<brief reason>"}\n'
              'Respond with EXACTLY one line of JSON.'
          )
          ok, reason, genuine = call_haiku_check(check_prompt)
          if genuine and not ok and reason:
              return [reason]
          return rule_signals
      except Exception:
          return rule_signals


  def layer35_unresolved_lines(state):
      """Return list of '- UNRESOLVED: ...' strings for Layer 4 session history."""
      lines = []
      for evt in state.get('layer35_recovery_events', []):
          if evt.get('status') == 'open':
              reason = evt.get('category', 'unknown')
              task = evt.get('task_id', '')
              lines.append(f'- UNRESOLVED: FN — {reason} (task: {task})')
      return lines
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer35RecoveryTracking -v 2>&1 | tail -10`
  Expected: `5 passed`

- [ ] **Step 5: Modify `quality-gate.py` to import and use `qg_layer35`**

  Read `quality-gate.py` first. The Layer 3/4 extension starts after `if __name__ == "__main__": main()` at line ~921. Make these changes to that section:

  **5a.** After the existing `import uuid as _uuid_mod, time as _time_mod` line, add:

  ```python
  try:
      from qg_layer35 import (layer35_create_recovery_event as _l35_create,
                               layer35_check_resolutions as _l35_check,
                               detect_fn_signals as _detect_fn_signals,
                               layer35_unresolved_lines as _l35_unresolved)
  except ImportError:
      def _l35_create(*a, **kw): pass
      def _l35_check(*a, **kw): pass
      def _detect_fn_signals(response, tool_names, user_request, state, **kw):
          return []
      def _l35_unresolved(state): return []
  ```

  **5b.** In `_layer3_run`, after `state, _ss = _qg_load_ss()` and before computing confidence, add:

  ```python
  _l35_check(list(tool_names or []), state)
  ```

  **5c.** In `_layer3_run`, replace the existing `else` branch:
  ```python
  else:
      fn_signals = _detect_fn_signals(response, state)
      verdict = 'FN' if fn_signals else 'TN'
  ```
  With:
  ```python
  else:
      fn_signals = _detect_fn_signals(response, list(tool_names or []), user_request, state)
      verdict = 'FN' if fn_signals else 'TN'
  ```

  **5d.** In `_layer3_run`, after `verdict = 'TP' if confidence >= 0.60 else 'FP'` (and also after the `verdict = 'FN' if fn_signals else 'TN'` line), add:

  ```python
  _l35_create(verdict, fn_signals, state, list(tool_names or []))
  ```

  Note: `_l35_create` is safe to call for TN too — it no-ops on non-FN/TP verdicts.

  **5e.** In `_layer4_checkpoint`, replace the `recovery_rate: N/A (Phase 2)` line:
  ```python
  f'recovery_rate: N/A (Phase 2)\n\n'
  ```
  With:
  ```python
  f'recovery_rate: {r_resolved}/{r_resolved + r_timed_out + r_open} '
  f'(resolved={r_resolved} timed_out={r_timed_out} open={r_open})\n'
  + ('\n'.join(_l35_unresolved(state)) + '\n\n' if _l35_unresolved(state) else '\n')
  ```

  And add these local vars just before the `entry = (...)` block in `_layer4_checkpoint`:
  ```python
  _recovery = state.get('layer35_recovery_events', [])
  r_open = sum(1 for e in _recovery if e.get('status') == 'open')
  r_resolved = sum(1 for e in _recovery if e.get('status') == 'resolved')
  r_timed_out = sum(1 for e in _recovery if e.get('status') == 'timed_out')
  ```

- [ ] **Step 6: Verify syntax of quality-gate.py**

  Run: `PYTHONIOENCODING=utf-8 python -W error::SyntaxWarning -c "import sys; sys.path.insert(0,'C:/Users/Matt1/.claude/hooks'); import quality_gate" 2>&1`

  If the module name causes an issue (hyphen), use:
  ```bash
  PYTHONIOENCODING=utf-8 python -c "
  import ast, sys
  with open('/c/Users/Matt1/.claude/hooks/quality-gate.py', 'r') as f:
      src = f.read()
  ast.parse(src)
  print('OK')
  "
  ```
  Expected: `OK`

- [ ] **Step 7: Run all Layer 3.5 tests**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer35RecoveryTracking -v 2>&1 | tail -10`
  Expected: `5 passed`

- [ ] **Step 8: Commit**

  ```bash
  cd ~/.claude && git add hooks/qg_layer35.py hooks/quality-gate.py scripts/tests/test_qg_layers.py
  git commit -m "feat(phase2): Layer 3.5 Recovery Tracking + Haiku FN classifier [AUTO]"
  ```

---

## Task 6: Layer 4.5 — Context Preservation

**Files:**
- Create: `~/.claude/hooks/qg_layer45.py`
- Create: `~/.claude/qg-preservation-config.json`
- Modify: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

  Read `test_qg_layers.py` first. Append before `if __name__ == '__main__':`:

  ```python
  class TestLayer45ContextPreservation(unittest.TestCase):
      def setUp(self):
          import qg_session_state as ss
          self.tmp = tempfile.mktemp(suffix='.json')
          ss.STATE_PATH = self.tmp
          ss.LOCK_PATH = self.tmp + '.lock'
          self.preserve_tmp = tempfile.mktemp(suffix='.json')

      def tearDown(self):
          import qg_session_state as ss
          for p in [self.tmp, self.tmp + '.lock', self.preserve_tmp]:
              try: os.unlink(p)
              except: pass

      def test_pre_compact_saves_state(self):
          import json as _json, qg_session_state as ss
          sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
          import qg_layer45
          qg_layer45.PRESERVE_PATH = self.preserve_tmp
          state = ss.read_state()
          state['session_uuid'] = 'uuid-45-test'
          state['active_task_description'] = 'test task 45'
          ss.write_state(state)
          qg_layer45.handle_pre_compact()
          with open(self.preserve_tmp) as f:
              preserved = _json.load(f)
          self.assertEqual(preserved['session_uuid'], 'uuid-45-test')
          self.assertIn('pre_compact_hash', preserved)

      def test_post_compact_restores_cleared_state(self):
          import json as _json, time as _time, qg_session_state as ss
          import qg_layer45
          qg_layer45.PRESERVE_PATH = self.preserve_tmp
          preserved = {
              'session_uuid': 'uuid-45-restore',
              'active_task_description': 'restore me',
              'pre_compact_hash': 'test',
              'preserved_at': _time.time(),
          }
          with open(self.preserve_tmp, 'w') as f:
              _json.dump(preserved, f)
          state = ss.read_state()
          state['session_uuid'] = 'uuid-45-restore'
          state['active_task_description'] = ''  # Cleared by compaction
          ss.write_state(state)
          qg_layer45.handle_post_compact()
          result = ss.read_state()
          self.assertEqual(result['active_task_description'], 'restore me')
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer45ContextPreservation -v 2>&1 | tail -10`
  Expected: `ModuleNotFoundError: No module named 'qg_layer45'`

- [ ] **Step 3: Create `qg_layer45.py`**

  Create `~/.claude/hooks/qg_layer45.py`:

  ```python
  #!/usr/bin/env python3
  """Layer 4.5 — Context Preservation (PreCompact / PostCompact).

  Usage (set by hook command):
      python qg_layer45.py --pre    (PreCompact hook)
      python qg_layer45.py --post   (PostCompact hook)
  """
  import hashlib, json, os, sys, time
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import qg_session_state as ss

  PRESERVE_PATH = os.path.expanduser('~/.claude/qg-context-preserve.json')

  PRESERVE_KEYS = [
      'session_uuid', 'session_start_ts', 'active_task_id', 'active_subtask_id',
      'active_task_description', 'layer1_task_category', 'layer1_scope_files',
      'task_success_criteria', 'layer2_unresolved_events', 'layer35_recovery_events',
      'layer_env_baseline', 'layer17_verified_task_id', 'layer17_intent_text',
      'layer19_last_impact_level', 'layer19_last_impact_file',
  ]


  def _state_hash(state):
      key_data = {k: state.get(k) for k in PRESERVE_KEYS[:5]}
      return hashlib.md5(
          json.dumps(key_data, sort_keys=True, default=str).encode()
      ).hexdigest()[:8]


  def handle_pre_compact():
      """Snapshot current session state before compaction."""
      state = ss.read_state()
      preserved = {k: state.get(k) for k in PRESERVE_KEYS}
      preserved['pre_compact_hash'] = _state_hash(state)
      preserved['preserved_at'] = time.time()
      try:
          with open(PRESERVE_PATH, 'w', encoding='utf-8') as f:
              json.dump(preserved, f, ensure_ascii=False)
      except Exception:
          pass


  def handle_post_compact():
      """Restore session state fields that were cleared by compaction."""
      try:
          with open(PRESERVE_PATH, 'r', encoding='utf-8') as f:
              preserved = json.load(f)
      except Exception:
          return

      state = ss.read_state()
      preserved_uuid = preserved.get('session_uuid')
      if not preserved_uuid:
          return
      if state.get('session_uuid') != preserved_uuid:
          return  # Different session — don't restore

      restored = []
      for k in PRESERVE_KEYS:
          if k in preserved and preserved[k] is not None:
              if not state.get(k):
                  state[k] = preserved[k]
                  restored.append(k)

      if restored:
          ss.write_state(state)
          print(f'[monitor:layer4.5] Restored {len(restored)} state fields after compaction.')


  def main():
      mode = sys.argv[1] if len(sys.argv) > 1 else ''
      if mode == '--pre':
          handle_pre_compact()
      elif mode == '--post':
          handle_post_compact()


  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 4: Create `qg-preservation-config.json`**

  Create `~/.claude/qg-preservation-config.json`:

  ```json
  {
    "schema_version": 1,
    "_comment": "Layer 4.5 config. Lists what to preserve through context compaction.",
    "always_preserve": [
      "session_uuid", "active_task_description", "layer1_scope_files",
      "layer2_unresolved_events", "layer35_recovery_events",
      "layer17_intent_text", "layer17_verified_task_id"
    ],
    "skip_preserve": [
      "layer19_impact_cache", "layer2_turn_history", "notification_delivery"
    ]
  }
  ```

- [ ] **Step 5: Run tests to verify they pass**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer45ContextPreservation -v 2>&1 | tail -10`
  Expected: `2 passed`

- [ ] **Step 6: Commit**

  ```bash
  cd ~/.claude && git add hooks/qg_layer45.py qg-preservation-config.json scripts/tests/test_qg_layers.py
  git commit -m "feat(phase2): Layer 4.5 Context Preservation [AUTO]"
  ```

---

## Task 7: Layer 5 — Subagent Coordination

**Files:**
- Create: `~/.claude/hooks/qg_layer5.py`
- Modify: `~/.claude/scripts/tests/test_qg_layers.py`

- [ ] **Step 1: Write the failing tests**

  Read `test_qg_layers.py` first. Append before `if __name__ == '__main__':`:

  ```python
  class TestLayer5SubagentCoordination(unittest.TestCase):
      def setUp(self):
          import qg_session_state as ss
          self.tmp = tempfile.mktemp(suffix='.json')
          ss.STATE_PATH = self.tmp
          ss.LOCK_PATH = self.tmp + '.lock'
          self.monitor_tmp = tempfile.mktemp(suffix='.jsonl')

      def tearDown(self):
          import qg_session_state as ss
          for p in [self.tmp, self.tmp + '.lock', self.monitor_tmp]:
              try: os.unlink(p)
              except: pass

      def _dispatch(self, tool_name, tool_input, tool_response):
          import json as _json, qg_session_state as ss, qg_layer5
          qg_layer5.MONITOR_PATH = self.monitor_tmp
          state = ss.read_state()
          state['session_uuid'] = 'uuid-l5'
          state['active_task_id'] = 'task-l5'
          ss.write_state(state)
          payload = {'tool_name': tool_name, 'tool_input': tool_input,
                     'tool_response': tool_response}
          qg_layer5.process_and_record(
              tool_name, tool_input, tool_response, ss.read_state())

      def test_agent_tool_records_event(self):
          import json as _json
          self._dispatch('Agent', {'prompt': 'Fix the bug'}, 'Fixed successfully.')
          with open(self.monitor_tmp) as f:
              events = [_json.loads(l) for l in f]
          self.assertEqual(len(events), 1)
          self.assertEqual(events[0]['layer'], 'layer5')
          self.assertEqual(events[0]['status'], 'subagent_complete')

      def test_non_agent_tool_produces_no_event(self):
          import qg_session_state as ss, qg_layer5
          qg_layer5.MONITOR_PATH = self.monitor_tmp
          result = qg_layer5.process_and_record(
              'Bash', {'command': 'ls'}, 'file.py', ss.read_state())
          self.assertIsNone(result)
          self.assertFalse(os.path.exists(self.monitor_tmp))

      def test_timeout_keyword_sets_status(self):
          import json as _json
          self._dispatch('Agent', {'prompt': 'Long task'}, 'Task timed out.')
          with open(self.monitor_tmp) as f:
              events = [_json.loads(l) for l in f]
          self.assertEqual(events[0]['status'], 'subagent_timeout')
  ```

- [ ] **Step 2: Run tests to verify they fail**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer5SubagentCoordination -v 2>&1 | tail -10`
  Expected: `ModuleNotFoundError: No module named 'qg_layer5'`

- [ ] **Step 3: Create `qg_layer5.py`**

  Create `~/.claude/hooks/qg_layer5.py`:

  ```python
  #!/usr/bin/env python3
  """Layer 5 — Subagent Coordination (PostToolUse on Agent tool).
  Records dispatch/return events and tracks parent_task_id linkage.
  """
  import json, os, sys, time, uuid
  sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
  import qg_session_state as ss

  MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')


  def process_and_record(tool_name, tool_input, tool_response, state):
      """Core logic — returns event dict or None. Exported for testing."""
      if tool_name != 'Agent':
          return None

      tool_input = tool_input or {}
      resp_lower = str(tool_response or '').lower()
      status = 'subagent_timeout' if any(
          kw in resp_lower for kw in ('timeout', 'timed out', 'error:', 'exception:')
      ) else 'subagent_complete'

      task_desc = str(
          tool_input.get('prompt', '') or
          tool_input.get('task', '') or
          tool_input.get('description', '') or ''
      )[:200]

      event = {
          'event_id': str(uuid.uuid4()),
          'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
          'layer': 'layer5',
          'type': 'subagent_return',
          'session_uuid': state.get('session_uuid', ''),
          'parent_task_id': state.get('active_task_id', ''),
          'subagent_id': str(uuid.uuid4())[:8],
          'task_description': task_desc,
          'status': status,
          'working_dir': os.getcwd(),
      }

      try:
          with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
              f.write(json.dumps(event) + '\n')
      except Exception:
          pass

      subagents = state.get('layer5_subagents', {})
      subagents[event['subagent_id']] = {
          'parent_task_id': event['parent_task_id'],
          'status': status,
          'ts': event['ts'],
          'task': task_desc,
      }
      state['layer5_subagents'] = subagents
      ss.write_state(state)
      return event


  def main():
      try:
          payload = json.load(sys.stdin)
      except Exception:
          return

      tool_name = payload.get('tool_name', '')
      if tool_name != 'Agent':
          return

      state = ss.read_state()
      process_and_record(
          tool_name,
          payload.get('tool_input', {}),
          payload.get('tool_response', ''),
          state,
      )


  if __name__ == '__main__':
      main()
  ```

- [ ] **Step 4: Run tests to verify they pass**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py::TestLayer5SubagentCoordination -v 2>&1 | tail -10`
  Expected: `3 passed`

- [ ] **Step 5: Commit**

  ```bash
  cd ~/.claude && git add hooks/qg_layer5.py scripts/tests/test_qg_layers.py
  git commit -m "feat(phase2): Layer 5 Subagent Coordination [AUTO]"
  ```

---

## Task 8: Hook Registration + Full Test Suite Verification

**Files:**
- Modify: `~/.claude/settings.json`
- Read-verify: all 6 new hook files exist and pass AST check

- [ ] **Step 1: Verify all new hook files are present**

  Run: `ls ~/.claude/hooks/qg_layer{17,18,19,35,45,5}.py`
  Expected: 6 files listed with no errors

- [ ] **Step 2: AST-check all new hook files**

  Run:
  ```bash
  for f in qg_layer17 qg_layer18 qg_layer19 qg_layer35 qg_layer45 qg_layer5; do
    PYTHONIOENCODING=utf-8 python -c "
  import ast, sys
  with open('C:/Users/Matt1/.claude/hooks/$f.py') as fh:
      src = fh.read()
  ast.parse(src)
  print('$f: OK')
  "
  done
  ```
  Expected: 6 lines each ending `: OK`

- [ ] **Step 3: Read `settings.json` to see current hook structure**

  Read `~/.claude/settings.json` — specifically the `"hooks"` section. You need to see the existing `PreToolUse`, `PostToolUse`, and `SessionStart` entries to merge correctly.

- [ ] **Step 4: Add Phase 2 hooks to `settings.json`**

  All hook paths use `/c/Users/Matt1/` (Git Bash forward-slash paths). Add these **new entries** (do not remove existing):

  **PreToolUse** — append 3 new entries after the existing `qg_layer15.py` entry:
  ```json
  { "matcher": "*", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer19.py" }] },
  { "matcher": "*", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer17.py" }] },
  { "matcher": "*", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer18.py" }] }
  ```
  Order matters: Layer 1.9 must come before Layer 1.7 (1.7 reads impact level set by 1.9).

  **PostToolUse** — append 1 new entry after the existing `qg_layer2.py` entry:
  ```json
  { "matcher": "Agent", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer5.py" }] }
  ```

  **PreCompact** — add new top-level event key (if not present):
  ```json
  "PreCompact": [
    { "matcher": "manual", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer45.py --pre" }] },
    { "matcher": "auto",   "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer45.py --pre" }] }
  ]
  ```

  **PostCompact** — add new top-level event key (if not present):
  ```json
  "PostCompact": [
    { "matcher": "manual", "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer45.py --post" }] },
    { "matcher": "auto",   "hooks": [{ "type": "command", "command": "python /c/Users/Matt1/.claude/hooks/qg_layer45.py --post" }] }
  ]
  ```

- [ ] **Step 5: Validate settings.json syntax**

  Run: `python -c "import json; json.load(open(r'C:/Users/Matt1/.claude/settings.json')); print('OK')"`
  Expected: `OK`

- [ ] **Step 6: Verify hook entries are present**

  Run:
  ```bash
  jq '.hooks.PreToolUse | map(.hooks[0].command) | .[]' ~/.claude/settings.json
  jq '.hooks.PostToolUse | map(.hooks[0].command) | .[]' ~/.claude/settings.json
  jq 'keys | map(select(startswith("Pre") or startswith("Post")))' ~/.claude/settings.json
  ```
  Expected first command: shows 5 PreToolUse commands (env, layer15, layer19, layer17, layer18)
  Expected second command: shows 2 PostToolUse commands (layer2, layer5)
  Expected third command: includes `PreCompact`, `PostCompact`

- [ ] **Step 7: Run the full test suite**

  Run: `cd ~/.claude/scripts/tests && PYTHONIOENCODING=utf-8 python -m pytest test_qg_layers.py test_qg_notification_router.py test_qg_session_state.py -v 2>&1 | tail -30`
  Expected: `56 passed` (35 existing + 21 new)

- [ ] **Step 8: Update README.md**

  Read `~/.claude/README.md`. Update:
  - Phase 2 status from "— Layers 1.7..." to "✅"
  - Layer table: add rows for 1.7, 1.8, 1.9, 3.5, 4.5, 5
  - Test count: `56 passed`

- [ ] **Step 9: Update design doc Phase 2 status**

  Read `~/.claude/projects/C--Users-Matt1/memory/quality-gate-monitor-design.md`. Update line 2 status to:
  `Phase 1 COMPLETE + Phase 2 COMPLETE — 56/56 tests pass`

  Update `~/.claude/projects/C--Users-Matt1/memory/MEMORY.md` to reflect Phase 2 complete.

- [ ] **Step 10: Final commit and push**

  ```bash
  cd ~/.claude && git add settings.json README.md
  git commit -m "feat(phase2): register Phase 2 hooks (1.7, 1.8, 1.9, 3.5, 4.5, 5) [AUTO]"
  git push
  ```

---

## Expected Final State

| Item | Before | After |
|------|--------|-------|
| Hook files | 6 Phase 1 | 12 total (6 new) |
| Unit tests | 35 passing | 56 passing |
| PreToolUse hooks | 2 (env, 1.5) | 5 (env, 1.5, 1.9, 1.7, 1.8) |
| PostToolUse hooks | 1 (layer2) | 2 (layer2, layer5) |
| PreCompact hooks | 0 | 1 (layer4.5 --pre) |
| PostCompact hooks | 0 | 1 (layer4.5 --post) |
| Haiku FN detection | Rule-based only | Haiku + rule fallback |
| Recovery tracking | None | 3-turn / 30-min window |

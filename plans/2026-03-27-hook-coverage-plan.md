# Hook System Coverage & Meta-Test Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close all coverage gaps in the hook system smoke-test suite: add tests for 3 fully-untested hooks, fill behavioral gaps in 6 partially-tested files, and add a meta-test harness that verifies the test runner itself counts correctly.

**Architecture:** All new tests are appended to `~/.claude/hooks/smoke-test.sh` as numbered sections following existing patterns. Each test section uses inline Python `-c` subprocesses piped to `grep -q 'token_ok'` to assert behavior. No new files are created; no existing tests are modified.

**Tech Stack:** Bash, Python 3.13 (inline `-c` blocks), `importlib.util` for module-level isolation, `tempfile` for state file isolation between tests.

---

## File Structure

**Single file modified:** `~/.claude/hooks/smoke-test.sh`

All tests append after the current final test section (section [81]) and before the `=== Results: ===` line.

**Files read (never modified) to understand behavior:**
- `~/.claude/hooks/error-dedup.py` — dedup logic, throttle, state structure
- `~/.claude/hooks/hook-health-feed.py` — log parsing, health JSON structure
- `~/.claude/hooks/todo-extractor.py` — transcript scan, TODO extraction
- `~/.claude/hooks/qg-session-recall.py` — snapshot read/delete flow
- `~/.claude/statusline.sh` — output format (structural test only)
- `~/.claude/scripts/qg-feedback.py` — cmd_fp/tp/miss, detect_sessions, write_feedback
- `~/.claude/scripts/quality-gate-analyst.py` — read_jsonl, compute_metrics, cluster_fp_patterns
- `~/.claude/hooks/quality-gate.py` — get_bash_results, get_failed_commands, _count_user_items
- `~/.claude/hooks/_hooks_shared.py` — _response_hash

---

## Task 1: Meta-Test Harness (Harness Self-Verification)

Verify that the `ok()`/`fail()` counter functions work correctly and that the `=== Results: ===` line is trustworthy.

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [82] near the top, before section [1])

- [ ] **Step 1: Write the meta-test section**

Find the line `echo "[1] Python syntax checks"` in smoke-test.sh and insert before it:

```bash
echo "[0] Meta-test: harness self-verification"
_meta_result=$(bash << 'METAEOF'
PASS=0; FAIL=0; TOTAL=0
ok()   { ((PASS++));  ((TOTAL++)); }
fail() { ((FAIL++));  ((TOTAL++)); }
echo "match" | grep -q "match" && ok "pass case" || fail "pass case"
echo "nope"  | grep -q "match" && ok "fail case" || fail "fail case"
echo "$PASS $FAIL $TOTAL"
METAEOF
)
[ "$_meta_result" = "1 1 2" ] && ok "harness: ok/fail counters work correctly" || fail "harness: BROKEN counters (got: $_meta_result)"
```

- [ ] **Step 2: Run and verify it passes**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A2 "\[0\]"
```
Expected: `PASS: harness: ok/fail counters work correctly`

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add harness self-verification meta-test [AUTO]"
```

---

## Task 2: error-dedup.py Tests

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [83] before `=== Results: ===`)

Key behaviors to test:
1. `normalize_error` strips paths, timestamps, line numbers
2. `error_hash` is deterministic and different for different errors
3. Dedup: 3rd occurrence triggers `alert.active = True`
4. Throttle: PostToolUse events within 5s of last state are skipped
5. Tier1 (PostToolUseFailure): fires on `error` field matching TIER1_RE
6. Tier2 (PostToolUse/Bash): fires when both TIER2_CONTEXT_RE and TIER2_ERROR_RE match
7. Unknown session_id resets state

- [ ] **Step 1: Write the test section**

Append to smoke-test.sh before `=== Results: ===`:

```bash
echo "[83] error-dedup.py"
# normalize_error strips paths and line numbers
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec); spec.loader.exec_module(ed)
result = ed.normalize_error('Error at line 42 in /tmp/foo.py: ENOENT /c/Users/Matt1/x.log')
assert 'line N' in result, f'line N not normalized: {result}'
assert 'PATH' in result, f'PATH not normalized: {result}'
assert '42' not in result, f'line number not removed: {result}'
print('norm_ok')
" 2>/dev/null | grep -q 'norm_ok' && ok "error-dedup: normalize_error strips paths+line numbers" || fail "error-dedup: normalize_error failed"

# error_hash is deterministic
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec); spec.loader.exec_module(ed)
h1 = ed.error_hash('Error: ENOENT /tmp/foo.txt at line 5')
h2 = ed.error_hash('Error: ENOENT /var/log/bar.txt at line 99')
h3 = ed.error_hash('TypeError: something else')
assert h1 == h2, f'same error class should hash same: {h1} vs {h2}'
assert h1 != h3, f'different errors should hash differently: {h1} vs {h3}'
assert len(h1) == 8, f'hash should be 8 chars: {h1}'
print('hash_ok')
" 2>/dev/null | grep -q 'hash_ok' && ok "error-dedup: error_hash deterministic and 8-char" || fail "error-dedup: error_hash failed"

# Dedup: 3rd occurrence triggers alert
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile, time
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec); spec.loader.exec_module(ed)
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    sid = 'test-session-123'
    state = ed.new_state(sid)
    h = ed.error_hash('Error: ENOENT something')
    # Simulate 2 prior occurrences
    state['errors'][h] = {'hash': h, 'canonical': 'Error: ENOENT something', 'count': 2,
        'first_seen_ts': int(time.time()), 'last_seen_ts': int(time.time()),
        'tool': 'Bash', 'dismissed': False}
    state['alert'] = {'active': False, 'hash': '', 'message': '', 'count': 0}
    ed.atomic_write(sf, state)
    # Feed 3rd occurrence via PostToolUseFailure
    import sys, io, json as _j
    payload = _j.dumps({'hook_event_name': 'PostToolUseFailure', 'session_id': sid,
        'tool_name': 'Bash', 'error': 'Error: ENOENT something important'})
    sys.stdin = io.StringIO(payload)
    ed.main()
    result = json.load(open(sf))
    assert result['alert']['active'] is True, f'alert not active: {result[\"alert\"]}'
    assert result['alert']['count'] == 3, f'count should be 3: {result[\"alert\"][\"count\"]}'
    print('dedup_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'dedup_ok' && ok "error-dedup: 3rd occurrence triggers alert" || fail "error-dedup: dedup alert not triggered"

# Throttle: PostToolUse within 5s is skipped (no state write)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile, time, sys, io
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec); spec.loader.exec_module(ed)
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    # Write state with ts=now (within throttle window)
    state = ed.new_state('sess1')
    state['ts'] = int(time.time())  # recent
    ed.atomic_write(sf, state)
    mtime_before = os.path.getmtime(sf)
    time.sleep(0.1)
    # PostToolUse within throttle window — should exit early without modifying state
    payload = json.dumps({'hook_event_name': 'PostToolUse', 'session_id': 'sess1',
        'tool_name': 'Bash', 'tool_response': 'Exit code 1\nError: something bad'})
    sys.stdin = io.StringIO(payload)
    ed.main()
    mtime_after = os.path.getmtime(sf)
    assert abs(mtime_after - mtime_before) < 0.05, f'state was modified during throttle window'
    print('throttle_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'throttle_ok' && ok "error-dedup: PostToolUse throttled within 5s" || fail "error-dedup: throttle not working"

# Tier2: PostToolUse/Bash fires when both context + error patterns match
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile, time, sys, io
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec); spec.loader.exec_module(ed)
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    # No recent state (forces past throttle window)
    payload = json.dumps({'hook_event_name': 'PostToolUse', 'session_id': 'sess2',
        'tool_name': 'Bash',
        'tool_response': 'Exit code 1\nTraceback (most recent call last):\n  File x.py line 10\nTypeError: bad input'})
    sys.stdin = io.StringIO(payload)
    ed.main()
    assert os.path.exists(sf), 'state file not written for tier2 match'
    state = json.load(open(sf))
    assert len(state['errors']) > 0, f'no errors recorded: {state}'
    print('tier2_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'tier2_ok' && ok "error-dedup: tier2 PostToolUse/Bash records matching error" || fail "error-dedup: tier2 not recording"

# New session resets state (different session_id)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile, time, sys, io
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec); spec.loader.exec_module(ed)
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    # State from old session with errors
    old_state = ed.new_state('old-session')
    old_state['errors']['abc'] = {'hash': 'abc', 'canonical': 'old error', 'count': 5,
        'first_seen_ts': 0, 'last_seen_ts': 0, 'tool': 'Bash', 'dismissed': False}
    old_state['ts'] = 0  # old enough to pass throttle
    ed.atomic_write(sf, old_state)
    payload = json.dumps({'hook_event_name': 'PostToolUseFailure', 'session_id': 'new-session',
        'tool_name': 'Bash', 'error': 'Error: ENOENT new error'})
    sys.stdin = io.StringIO(payload)
    ed.main()
    new_state = json.load(open(sf))
    assert new_state['session_id'] == 'new-session', f'session not reset: {new_state[\"session_id\"]}'
    assert 'abc' not in new_state['errors'], 'old errors not cleared on new session'
    print('session_reset_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'session_reset_ok' && ok "error-dedup: new session_id resets state" || fail "error-dedup: session reset failed"
```

- [ ] **Step 2: Run and verify all pass**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A20 "\[83\]"
```
Expected: 6 PASS lines, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add error-dedup.py behavioral tests [AUTO]"
```

---

## Task 3: hook-health-feed.py Tests

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [84])

Key behaviors to test:
1. `parse_hook_audit` parses `hook-audit.log` lines correctly
2. `parse_quality_gate` parses `quality-gate.log` PASS/BLOCK lines
3. `parse_task_classifier` parses `task-classifier.log` lines
4. `build_hook_entry` returns correct structure with `status`, `last_seen`, `error`
5. `main()` writes valid `hook-health.json` with expected top-level keys
6. Exits 0 always (even with no log files)

- [ ] **Step 1: Write the test section**

```bash
echo "[84] hook-health-feed.py"
# parse_hook_audit: parses standard audit log line
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec); spec.loader.exec_module(hhf)
# Feed a sample hook-audit log line
sample = '2026-03-27 15:00 | tool-failure-log | PostToolUse | session=abc | exit=0'
m = hhf.RE_HOOK_AUDIT.match(sample)
assert m is not None, f'RE_HOOK_AUDIT did not match: {repr(sample)}'
assert m.group(2) == 'tool-failure-log', f'wrong hook name: {m.group(2)}'
print('audit_parse_ok')
" 2>/dev/null | grep -q 'audit_parse_ok' && ok "hook-health-feed: parse_hook_audit matches standard line" || fail "hook-health-feed: parse_hook_audit regex failed"

# parse_quality_gate: parses PASS and BLOCK lines
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec); spec.loader.exec_module(hhf)
pass_line  = '2026-03-27 15:00:01 | PASS  | SIMPLE | llm-ok | tools=Bash | req=hello | hash=abc123'
block_line = '2026-03-27 15:00:02 | BLOCK | MODERATE | OVERCONFIDENCE: test | tools=- | req=foo | hash=xyz'
m1 = hhf.RE_QUALITY_GATE.match(pass_line)
m2 = hhf.RE_QUALITY_GATE.match(block_line)
assert m1 and m1.group(2) == 'PASS', f'PASS not parsed: {m1}'
assert m2 and m2.group(2) == 'BLOCK', f'BLOCK not parsed: {m2}'
print('qg_parse_ok')
" 2>/dev/null | grep -q 'qg_parse_ok' && ok "hook-health-feed: RE_QUALITY_GATE matches PASS and BLOCK" || fail "hook-health-feed: RE_QUALITY_GATE parse failed"

# main() writes hook-health.json with required keys and exits 0
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec); spec.loader.exec_module(hhf)
hf = tempfile.mktemp(suffix='.json')
hhf.HEALTH_FILE = hf
try:
    hhf.main()
    assert os.path.exists(hf), 'hook-health.json not written'
    data = json.load(open(hf))
    assert 'hooks' in data, f'no hooks key: {list(data.keys())}'
    assert 'generated_at' in data, f'no generated_at: {list(data.keys())}'
    assert isinstance(data['hooks'], dict), f'hooks not a dict: {type(data[\"hooks\"])}'
    print('health_main_ok')
finally:
    try: os.unlink(hf)
    except: pass
" 2>/dev/null | grep -q 'health_main_ok' && ok "hook-health-feed: main() writes valid hook-health.json" || fail "hook-health-feed: main() output invalid"

# Always exits 0 with no log files
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec); spec.loader.exec_module(hhf)
# Redirect all log files to nonexistent paths
for k in list(hhf.LOG_FILES.keys()):
    hhf.LOG_FILES[k] = '/nonexistent/path/that/does/not/exist.log'
hf = tempfile.mktemp(suffix='.json')
hhf.HEALTH_FILE = hf
try:
    hhf.main()  # should not raise
    print('health_nolog_ok')
finally:
    try: os.unlink(hf)
    except: pass
" 2>/dev/null | grep -q 'health_nolog_ok' && ok "hook-health-feed: exits 0 with no log files" || fail "hook-health-feed: crashed with no log files"

# build_hook_entry returns dict with status field
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec); spec.loader.exec_module(hhf)
entry = hhf.build_hook_entry('quality-gate', [], None)
assert isinstance(entry, dict), f'not a dict: {type(entry)}'
assert 'status' in entry, f'no status key: {entry}'
assert entry['status'] in ('ok', 'warn', 'error', 'unknown', 'stale'), f'bad status: {entry[\"status\"]}'
print('entry_ok')
" 2>/dev/null | grep -q 'entry_ok' && ok "hook-health-feed: build_hook_entry returns dict with valid status" || fail "hook-health-feed: build_hook_entry invalid"
```

- [ ] **Step 2: Run and verify all pass**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A15 "\[84\]"
```
Expected: 5 PASS lines, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add hook-health-feed.py behavioral tests [AUTO]"
```

---

## Task 4: todo-extractor.py Tests

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [85])

Key behaviors to test:
1. `normalize_text` strips whitespace consistently
2. `item_hash` is deterministic and returns 8 chars
3. `split_code_fences` separates code blocks from prose
4. `extract_sentence_for_match` returns surrounding sentence
5. `scan_transcript` extracts `TODO:` from code, high-conf from assistant text, skips low-conf without co-signal
6. `main()` writes `todo-feed.json` and exits 0

- [ ] **Step 1: Write the test section**

```bash
echo "[85] todo-extractor.py"
# normalize_text and item_hash
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec); spec.loader.exec_module(te)
n1 = te.normalize_text('  Hello   World  ')
n2 = te.normalize_text('Hello World')
assert n1 == n2, f'normalize not stripping whitespace: {repr(n1)} vs {repr(n2)}'
h = te.item_hash('some todo text')
assert len(h) == 8, f'hash not 8 chars: {repr(h)}'
assert h == te.item_hash('some todo text'), 'hash not deterministic'
assert h != te.item_hash('different todo'), 'different text should hash differently'
print('todo_hash_ok')
" 2>/dev/null | grep -q 'todo_hash_ok' && ok "todo-extractor: normalize_text + item_hash work correctly" || fail "todo-extractor: normalize/hash failed"

# split_code_fences separates code from prose
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec); spec.loader.exec_module(te)
text = 'Before code.\n\x60\x60\x60python\nx = 1  # TODO: fix this\n\x60\x60\x60\nAfter code.'
parts = te.split_code_fences(text)
assert isinstance(parts, list), f'not a list: {type(parts)}'
assert len(parts) >= 2, f'expected at least 2 parts: {parts}'
has_code = any(p.get('is_code') for p in parts if isinstance(p, dict))
has_prose = any(not p.get('is_code') for p in parts if isinstance(p, dict))
assert has_code, f'no code part found: {parts}'
assert has_prose, f'no prose part found: {parts}'
print('fence_ok')
" 2>/dev/null | grep -q 'fence_ok' && ok "todo-extractor: split_code_fences separates code from prose" || fail "todo-extractor: split_code_fences failed"

# scan_transcript extracts CODE_TODO from Write tool_use
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec); spec.loader.exec_module(te)
tf = tempfile.mktemp(suffix='.jsonl')
try:
    with open(tf, 'w') as f:
        # Write tool_use with TODO in content
        f.write(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Write', 'input': {
                'file_path': '/tmp/foo.py',
                'content': 'x = 1  # TODO: fix this hardcoded value\n'
            }}
        ]}}) + '\n')
    items = te.scan_transcript(tf)
    assert len(items) > 0, f'no TODO items extracted: {items}'
    texts = [i.get('text','') for i in items]
    assert any('fix this hardcoded value' in t for t in texts), f'TODO text not found: {texts}'
    print('scan_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'scan_ok' && ok "todo-extractor: scan_transcript extracts CODE_TODO from Write" || fail "todo-extractor: scan_transcript CODE_TODO extraction failed"

# scan_transcript extracts high-conf \"don't forget\" from assistant text
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec); spec.loader.exec_module(te)
tf = tempfile.mktemp(suffix='.jsonl')
try:
    with open(tf, 'w') as f:
        f.write(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'text', 'text': \"Don't forget to update the config file before deploying.\"}
        ]}}) + '\n')
    items = te.scan_transcript(tf)
    assert len(items) > 0, f'high-conf item not extracted: {items}'
    texts = [i.get('text','') for i in items]
    assert any('config' in t or 'forget' in t.lower() for t in texts), f'text not found: {texts}'
    print('highconf_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'highconf_ok' && ok "todo-extractor: scan_transcript extracts high-conf assistant signals" || fail "todo-extractor: high-conf signal not extracted"

# main() writes todo-feed.json and exits 0
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile, sys, io
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec); spec.loader.exec_module(te)
ff = tempfile.mktemp(suffix='.json')
tf = tempfile.mktemp(suffix='.jsonl')
te.FEED_FILE = ff
try:
    with open(tf, 'w') as f:
        f.write(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'text', 'text': \"Don't forget to run migrations before deploy.\"}
        ]}}) + '\n')
    payload = json.dumps({'transcript_path': tf, 'cwd': '/tmp'})
    sys.stdin = io.StringIO(payload)
    te.main()
    assert os.path.exists(ff), 'todo-feed.json not written'
    data = json.load(open(ff))
    assert 'items' in data, f'no items key: {list(data.keys())}'
    print('todo_main_ok')
finally:
    for p in [ff, tf]:
        try: os.unlink(p)
        except: pass
" 2>/dev/null | grep -q 'todo_main_ok' && ok "todo-extractor: main() writes todo-feed.json" || fail "todo-extractor: main() failed"
```

- [ ] **Step 2: Run and verify all pass**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A18 "\[85\]"
```
Expected: 5 PASS lines, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add todo-extractor.py behavioral tests [AUTO]"
```

---

## Task 5: qg-session-recall.py Behavioral Tests

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [86])

Key behaviors:
1. Snapshot present and fresh → prints JSON system message + deletes file
2. Snapshot older than 24h → deletes file, prints nothing
3. No snapshot → exits 0, no output

- [ ] **Step 1: Write the test section**

```bash
echo "[86] qg-session-recall.py"
# Fresh snapshot → system message emitted + file deleted
PYTHONIOENCODING=utf-8 python -c "
import subprocess, os, json, tempfile, time
hook = os.path.expanduser('~/.claude/hooks/qg-session-recall.py')
sf = tempfile.mktemp(suffix='.txt')
try:
    with open(sf, 'w') as f:
        f.write('BLOCK | OVERCONFIDENCE: test block from last session')
    import importlib.util
    spec = importlib.util.spec_from_file_location('qsr', hook)
    qsr = importlib.util.module_from_spec(spec)
    qsr.SNAPSHOT = sf
    # Capture output
    import sys, io
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        qsr_code = open(hook, encoding='utf-8').read()
        # Patch SNAPSHOT path in code and exec
        qsr_code2 = qsr_code.replace(
            \"SNAPSHOT = os.path.join(STATE_DIR, 'last-session-qg-failures.txt')\",
            f\"SNAPSHOT = {repr(sf)}\"
        )
        exec(compile(qsr_code2, hook, 'exec'), {'__name__': '__main__'})
    except SystemExit:
        pass
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    data = json.loads(output.strip())
    assert data.get('type') == 'system', f'wrong type: {data}'
    assert 'qg-recall' in data.get('message',''), f'header missing: {data}'
    assert not os.path.exists(sf), 'snapshot not deleted after read'
    print('recall_fresh_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'recall_fresh_ok' && ok "qg-session-recall: fresh snapshot emits system message + deletes" || fail "qg-session-recall: fresh snapshot behavior wrong"

# Stale snapshot (>24h) → deleted, no output
PYTHONIOENCODING=utf-8 python -c "
import os, sys, io, json, tempfile, time
hook = os.path.expanduser('~/.claude/hooks/qg-session-recall.py')
sf = tempfile.mktemp(suffix='.txt')
try:
    with open(sf, 'w') as f: f.write('old block summary')
    # Set mtime to 25 hours ago
    old_time = time.time() - (25 * 3600)
    os.utime(sf, (old_time, old_time))
    qsr_code = open(hook, encoding='utf-8').read().replace(
        \"SNAPSHOT = os.path.join(STATE_DIR, 'last-session-qg-failures.txt')\",
        f'SNAPSHOT = {repr(sf)}'
    )
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        exec(compile(qsr_code, hook, 'exec'), {'__name__': '__main__'})
    except SystemExit:
        pass
    output = sys.stdout.getvalue().strip()
    sys.stdout = old_stdout
    assert not os.path.exists(sf), 'stale snapshot should be deleted'
    assert output == '', f'stale snapshot should produce no output, got: {repr(output)}'
    print('recall_stale_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'recall_stale_ok' && ok "qg-session-recall: stale snapshot deleted silently" || fail "qg-session-recall: stale snapshot behavior wrong"

# No snapshot → exits 0, no output
PYTHONIOENCODING=utf-8 python -c "
import os, sys, io, tempfile
hook = os.path.expanduser('~/.claude/hooks/qg-session-recall.py')
nonexistent = tempfile.mktemp(suffix='.txt')  # guaranteed not to exist
qsr_code = open(hook, encoding='utf-8').read().replace(
    \"SNAPSHOT = os.path.join(STATE_DIR, 'last-session-qg-failures.txt')\",
    f'SNAPSHOT = {repr(nonexistent)}'
)
old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
    exec(compile(qsr_code, hook, 'exec'), {'__name__': '__main__'})
except SystemExit:
    pass
output = sys.stdout.getvalue().strip()
sys.stdout = old_stdout
assert output == '', f'no snapshot should produce no output, got: {repr(output)}'
print('recall_absent_ok')
" 2>/dev/null | grep -q 'recall_absent_ok' && ok "qg-session-recall: no snapshot exits cleanly" || fail "qg-session-recall: no-snapshot case failed"
```

- [ ] **Step 2: Run and verify all pass**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A12 "\[86\]"
```
Expected: 3 PASS lines, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add qg-session-recall.py behavioral tests [AUTO]"
```

---

## Task 6: qg-feedback.py Missing Function Tests

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [87])

Target untested functions: `write_feedback`, `read_last_override`, `detect_sessions`, `find_notable_patterns`, `cmd_failures_add`, `_detect_dominant_category`, `_detect_high_block_rate`, `_detect_short_input_rate`, `_detect_no_tool_dominance`, `_parse_milestones`.

(Note: `cmd_fp`, `cmd_tp`, `cmd_miss`, `cmd_report` all call external file paths or subprocess — test at integration level via CLI invocation with temp files.)

- [ ] **Step 1: Write the test section**

```bash
echo "[87] qg-feedback.py missing functions"
# write_feedback writes JSONL record
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec); spec.loader.exec_module(qgf)
ff = tempfile.mktemp(suffix='.jsonl')
qgf.FEEDBACK_PATH = ff
try:
    qgf.write_feedback({'type': 'fp', 'ts': '2026-01-01T00:00:00', 'test': True})
    lines = open(ff).readlines()
    assert len(lines) == 1, f'expected 1 line: {lines}'
    record = json.loads(lines[0])
    assert record['type'] == 'fp', f'wrong type: {record}'
    # Appends on second call
    qgf.write_feedback({'type': 'tp', 'ts': '2026-01-01T00:01:00', 'test': True})
    assert len(open(ff).readlines()) == 2, 'not appending'
    print('feedback_write_ok')
finally:
    try: os.unlink(ff)
    except: pass
" 2>/dev/null | grep -q 'feedback_write_ok' && ok "qg-feedback: write_feedback appends JSONL records" || fail "qg-feedback: write_feedback failed"

# read_last_override returns latest record or None
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec); spec.loader.exec_module(qgf)
of = tempfile.mktemp(suffix='.jsonl')
qgf.OVERRIDES_PATH = of
try:
    # No file → returns None
    result = qgf.read_last_override()
    assert result is None, f'should return None for missing file: {result}'
    # File with records → returns last
    with open(of, 'w') as f:
        f.write(json.dumps({'ts': '2026-01-01T00:00:00', 'source': 'main', 'auto_verdict': 'likely_fp'}) + '\n')
        f.write(json.dumps({'ts': '2026-01-02T00:00:00', 'source': 'main', 'auto_verdict': 'likely_tp'}) + '\n')
    result = qgf.read_last_override()
    assert result is not None, 'should return record'
    assert result.get('auto_verdict') == 'likely_tp', f'should return last: {result}'
    print('override_read_ok')
finally:
    try: os.unlink(of)
    except: pass
" 2>/dev/null | grep -q 'override_read_ok' && ok "qg-feedback: read_last_override returns latest or None" || fail "qg-feedback: read_last_override failed"

# detect_sessions groups entries by gap
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec); spec.loader.exec_module(qgf)
from datetime import datetime, timedelta
base = datetime(2026, 1, 1, 10, 0, 0)
# 3 entries close together, then a big gap, then 2 more
entries = [
    {'ts': base + timedelta(minutes=i), 'decision': 'PASS', 'req': 'test', 'tools': '-', 'hash': str(i), 'complexity': 'SIMPLE', 'reason': 'ok'}
    for i in [0, 5, 10, 60, 65]  # gap between index 2 and 3 is 50 min
]
sessions = qgf.detect_sessions(entries)
assert len(sessions) == 2, f'expected 2 sessions, got {len(sessions)}: {sessions}'
assert len(sessions[0]) == 3, f'session 1 should have 3 entries: {len(sessions[0])}'
assert len(sessions[1]) == 2, f'session 2 should have 2 entries: {len(sessions[1])}'
print('sessions_ok')
" 2>/dev/null | grep -q 'sessions_ok' && ok "qg-feedback: detect_sessions groups by gap correctly" || fail "qg-feedback: detect_sessions grouping wrong"

# _detect_high_block_rate returns finding when block rate >30%
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec); spec.loader.exec_module(qgf)
from datetime import datetime
base = datetime(2026, 1, 1, 10, 0, 0)
# 4 entries: 2 BLOCK, 2 PASS = 50% block rate
entries = [
    {'ts': base, 'decision': 'BLOCK', 'req': 'test', 'tools': '-', 'hash': '1', 'complexity': 'SIMPLE', 'reason': 'OVERCONFIDENCE: x'},
    {'ts': base, 'decision': 'BLOCK', 'req': 'test', 'tools': '-', 'hash': '2', 'complexity': 'SIMPLE', 'reason': 'OVERCONFIDENCE: y'},
    {'ts': base, 'decision': 'PASS',  'req': 'test', 'tools': '-', 'hash': '3', 'complexity': 'SIMPLE', 'reason': 'ok'},
    {'ts': base, 'decision': 'PASS',  'req': 'test', 'tools': '-', 'hash': '4', 'complexity': 'SIMPLE', 'reason': 'ok'},
]
result = qgf._detect_high_block_rate(entries)
assert result is not None, f'should detect high block rate: {result}'
assert '50' in str(result) or '2' in str(result), f'should mention rate in finding: {result}'
print('block_rate_ok')
" 2>/dev/null | grep -q 'block_rate_ok' && ok "qg-feedback: _detect_high_block_rate flags >30% rate" || fail "qg-feedback: _detect_high_block_rate failed"

# _detect_dominant_category returns category when one type dominates
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec); spec.loader.exec_module(qgf)
from datetime import datetime
base = datetime(2026, 1, 1, 10, 0, 0)
entries = [
    {'ts': base, 'decision': 'BLOCK', 'reason': 'OVERCONFIDENCE: test', 'req': 'x', 'tools': '-', 'hash': str(i), 'complexity': 'SIMPLE'}
    for i in range(4)
] + [{'ts': base, 'decision': 'BLOCK', 'reason': 'ASSUMPTION: test', 'req': 'x', 'tools': '-', 'hash': '99', 'complexity': 'SIMPLE'}]
result = qgf._detect_dominant_category(entries)
assert result is not None, f'should detect OVERCONFIDENCE dominance: {result}'
assert 'OVERCONFIDENCE' in str(result), f'should name the category: {result}'
print('dominant_ok')
" 2>/dev/null | grep -q 'dominant_ok' && ok "qg-feedback: _detect_dominant_category identifies dominant category" || fail "qg-feedback: _detect_dominant_category failed"
```

- [ ] **Step 2: Run and verify all pass**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A18 "\[87\]"
```
Expected: 5 PASS lines, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add qg-feedback.py missing function tests [AUTO]"
```

---

## Task 7: quality-gate-analyst.py Missing Function Tests

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [88])

Target: `read_jsonl`, `compute_metrics`, `cluster_fp_patterns`, `generate_candidate`, `write_report`

- [ ] **Step 1: Write the test section**

```bash
echo "[88] quality-gate-analyst.py missing functions"
# read_jsonl reads JSONL file into list of dicts
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec); spec.loader.exec_module(qga)
tf = tempfile.mktemp(suffix='.jsonl')
try:
    with open(tf, 'w') as f:
        f.write(json.dumps({'a': 1}) + '\n')
        f.write(json.dumps({'b': 2}) + '\n')
        f.write('not-json-line\n')  # should be skipped
    records = qga.read_jsonl(tf)
    assert len(records) == 2, f'expected 2 valid records (skipping bad line): {records}'
    assert records[0].get('a') == 1, f'wrong first record: {records[0]}'
    print('read_jsonl_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'read_jsonl_ok' && ok "quality-gate-analyst: read_jsonl skips bad lines" || fail "quality-gate-analyst: read_jsonl failed"

# compute_metrics returns dict with total/block_rate/categories
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec); spec.loader.exec_module(qga)
from datetime import datetime
base = datetime(2026, 1, 1, 10, 0, 0)
entries = [
    {'ts': base, 'decision': 'BLOCK', 'reason': 'OVERCONFIDENCE: x', 'req': 'a', 'tools': '-', 'hash': '1', 'complexity': 'SIMPLE'},
    {'ts': base, 'decision': 'PASS',  'reason': 'llm-ok',            'req': 'b', 'tools': 'Bash', 'hash': '2', 'complexity': 'MODERATE'},
    {'ts': base, 'decision': 'PASS',  'reason': 'llm-ok',            'req': 'c', 'tools': 'Bash', 'hash': '3', 'complexity': 'MODERATE'},
]
metrics = qga.compute_metrics(entries, [])
assert isinstance(metrics, dict), f'not a dict: {type(metrics)}'
assert metrics.get('total_evals', 0) >= 3, f'total_evals wrong: {metrics}'
assert 'block_rate' in metrics, f'no block_rate: {metrics}'
print('metrics_ok')
" 2>/dev/null | grep -q 'metrics_ok' && ok "quality-gate-analyst: compute_metrics returns expected structure" || fail "quality-gate-analyst: compute_metrics failed"

# cluster_fp_patterns returns list (even if empty)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec); spec.loader.exec_module(qga)
result = qga.cluster_fp_patterns([])
assert isinstance(result, list), f'should return list: {type(result)}'
# With actual FP patterns from overrides
from datetime import datetime
overrides = [
    {'ts': '2026-01-01T10:00:00', 'block_category': 'OVERCONFIDENCE', 'auto_verdict': 'likely_fp',
     'user_request': 'Are you sure?', 'block_reason': 'OVERCONFIDENCE: test', 'gap_sec': 5,
     'tools_before': [], 'tools_after': [], 'response_hash': 'abc'}
]
result2 = qga.cluster_fp_patterns(overrides)
assert isinstance(result2, list), f'should return list with data: {type(result2)}'
print('cluster_ok')
" 2>/dev/null | grep -q 'cluster_ok' && ok "quality-gate-analyst: cluster_fp_patterns returns list" || fail "quality-gate-analyst: cluster_fp_patterns failed"

# write_report writes output file
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec); spec.loader.exec_module(qga)
tf = tempfile.mktemp(suffix='.txt')
try:
    qga.write_report({'total_evals': 10, 'block_rate': 0.2, 'categories': {}}, [], [], tf)
    assert os.path.exists(tf), 'report file not written'
    content = open(tf).read()
    assert len(content) > 0, 'report file is empty'
    print('report_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'report_ok' && ok "quality-gate-analyst: write_report creates non-empty file" || fail "quality-gate-analyst: write_report failed"
```

- [ ] **Step 2: Run and verify all pass**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A15 "\[88\]"
```
Expected: 4 PASS lines, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add quality-gate-analyst.py missing function tests [AUTO]"
```

---

## Task 8: quality-gate.py Missing Function Tests

**Files:**
- Modify: `~/.claude/hooks/smoke-test.sh` (add section [89])

Target: `get_last_complexity`, `_get_last_turn_lines`, `get_bash_results`, `get_failed_commands`, `_count_user_items`, `_response_hash`

- [ ] **Step 1: Write the test section**

```bash
echo "[89] quality-gate.py + _hooks_shared.py missing functions"
# get_last_complexity reads classifier log
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
tf = tempfile.mktemp(suffix='.log')
qg.CLASSIFIER_LOG = tf
try:
    # No file → returns MODERATE
    result = qg.get_last_complexity()
    assert result == 'MODERATE', f'no file should return MODERATE: {result}'
    # File with DEEP entry
    with open(tf, 'w') as f:
        f.write('2026-03-27 12:00:00 | DEEP | sonnet | add feature\n')
    result2 = qg.get_last_complexity()
    assert result2 == 'DEEP', f'should return DEEP: {result2}'
    print('complexity_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'complexity_ok' && ok "quality-gate: get_last_complexity reads log correctly" || fail "quality-gate: get_last_complexity failed"

# _get_last_turn_lines returns assistant entries for last turn
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
tf = tempfile.mktemp(suffix='.jsonl')
try:
    with open(tf, 'w') as f:
        f.write(json.dumps({'type': 'user', 'message': {'content': [{'type': 'text', 'text': 'first msg'}]}}) + '\n')
        f.write(json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Bash', 'id': 't1', 'input': {'command': 'ls'}}]}}) + '\n')
        f.write(json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 't1', 'content': 'file.txt'}]}}) + '\n')
    turns = qg._get_last_turn_lines(tf)
    assert len(turns) >= 1, f'should find at least 1 assistant entry: {turns}'
    assert turns[0].get('type') == 'assistant', f'should be assistant type: {turns[0]}'
    print('turn_lines_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'turn_lines_ok' && ok "quality-gate: _get_last_turn_lines returns assistant entries" || fail "quality-gate: _get_last_turn_lines failed"

# get_bash_results returns tool result content for Bash calls
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
tf = tempfile.mktemp(suffix='.jsonl')
try:
    with open(tf, 'w') as f:
        f.write(json.dumps({'type': 'user', 'message': {'content': [{'type': 'text', 'text': 'run tests'}]}}) + '\n')
        f.write(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Bash', 'id': 'bash1', 'input': {'command': 'pytest'}},
        ]}}) + '\n')
        f.write(json.dumps({'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'bash1', 'content': '5 passed, 0 failed, 5 total'},
        ]}}) + '\n')
    results = qg.get_bash_results(tf)
    assert len(results) == 1, f'expected 1 result: {results}'
    assert '5 passed' in results[0], f'result text wrong: {results}'
    print('bash_results_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'bash_results_ok' && ok "quality-gate: get_bash_results extracts Bash tool results" || fail "quality-gate: get_bash_results failed"

# get_failed_commands detects is_error=True tool results
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
tf = tempfile.mktemp(suffix='.jsonl')
try:
    with open(tf, 'w') as f:
        f.write(json.dumps({'type': 'user', 'message': {'content': [{'type': 'text', 'text': 'fix it'}]}}) + '\n')
        f.write(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Bash', 'id': 'b1', 'input': {'command': 'bad_command'}},
        ]}}) + '\n')
        f.write(json.dumps({'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 'b1', 'content': 'command not found', 'is_error': True},
        ]}}) + '\n')
    failed = qg.get_failed_commands(tf)
    assert len(failed) == 1, f'expected 1 failure: {failed}'
    assert 'bad_command' in failed[0][0], f'command not in result: {failed[0]}'
    print('failed_cmds_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'failed_cmds_ok' && ok "quality-gate: get_failed_commands detects is_error=True" || fail "quality-gate: get_failed_commands failed"

# _count_user_items counts listed items
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
# Explicit number
assert qg._count_user_items('fix all 5 bugs') == 5, 'explicit number not parsed'
# Comma list
assert qg._count_user_items('fix: foo, bar, baz') >= 3, 'comma list not counted'
# Nothing
assert qg._count_user_items('hello world') == 0, 'no items should return 0'
print('count_ok')
" 2>/dev/null | grep -q 'count_ok' && ok "quality-gate: _count_user_items counts explicit + listed items" || fail "quality-gate: _count_user_items failed"

# _response_hash is deterministic and 8 chars
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('hs', os.path.expanduser('~/.claude/hooks/_hooks_shared.py'))
hs = importlib.util.module_from_spec(spec); spec.loader.exec_module(hs)
h1 = hs._response_hash('hello world')
h2 = hs._response_hash('hello world')
h3 = hs._response_hash('different text')
assert h1 == h2, f'hash not deterministic: {h1} vs {h2}'
assert h1 != h3, f'different input should differ: {h1} vs {h3}'
assert len(h1) == 8, f'hash should be 8 chars: {repr(h1)}'
print('hash_ok')
" 2>/dev/null | grep -q 'hash_ok' && ok "_hooks_shared: _response_hash is deterministic and 8-char" || fail "_hooks_shared: _response_hash failed"
```

- [ ] **Step 2: Run and verify all pass**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | grep -A22 "\[89\]"
```
Expected: 6 PASS lines, 0 FAIL

- [ ] **Step 3: Commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: add quality-gate + _hooks_shared missing function tests [AUTO]"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Run the full suite**

```bash
bash ~/.claude/hooks/smoke-test.sh 2>/dev/null | tail -10
```

Expected final line: `=== Results: 4XX passed, 0 failed, 4XX total ===` (exact count depends on any failures found and fixed during implementation)

- [ ] **Step 2: Confirm zero-coverage hooks now have tests**

```bash
PYTHONIOENCODING=utf-8 python -c "
import os
smoke = open(os.path.expanduser('~/.claude/hooks/smoke-test.sh'), encoding='utf-8').read()
for f in ['error-dedup.py', 'hook-health-feed.py', 'todo-extractor.py', 'qg-session-recall.py']:
    count = smoke.count(f)
    print(f'{f}: {count} refs')
"
```

Expected: all 4 previously-zero-coverage files now have >0 references.

- [ ] **Step 3: Confirm meta-test section exists**

```bash
grep -c "\[0\] Meta-test" ~/.claude/hooks/smoke-test.sh
```

Expected: `1`

- [ ] **Step 4: Update memory**

```bash
# Update quality-gate-calibration.md with new test count and coverage status
```

Edit `~/.claude/projects/C--Users-Matt1/memory/quality-gate-calibration.md` to note that all hooks now have coverage and the harness self-verification was added.

- [ ] **Step 5: Final commit**

```bash
git -C ~/.claude add hooks/smoke-test.sh
git -C ~/.claude commit -m "test: complete hook system coverage audit + meta-test harness [AUTO]"
```

---

## Notes for Implementer

**If a test fails after writing it:**
1. First re-read the hook source file to verify your understanding of the behavior
2. Check if the hook uses module-level globals (`STATE_FILE`, `LOG_PATH`) — patch these to temp files before calling functions
3. Some hooks call `sys.exit(0)` — wrap in try/except SystemExit
4. Some functions require `sys.stdin` to be patched with `io.StringIO(payload)` for main() calls

**On mock payload structure:**
- `PostToolUse`: `{'hook_event_name': 'PostToolUse', 'session_id': 'X', 'tool_name': 'Bash', 'tool_response': '...'}`
- `PostToolUseFailure`: `{'hook_event_name': 'PostToolUseFailure', 'session_id': 'X', 'tool_name': 'Bash', 'error': '...'}`
- `Stop`: `{'transcript_path': '/path/to/file.jsonl', 'stop_hook_active': False}`

**Token naming convention:** Each new test token must be unique across the entire smoke-test.sh. Check with `grep 'token_name' ~/.claude/hooks/smoke-test.sh` before using a token.

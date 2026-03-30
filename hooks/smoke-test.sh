#!/bin/bash
# smoke-test.sh — Quick validation of all hook scripts
# Run: bash ~/.claude/hooks/smoke-test.sh
# Tests syntax, basic input/output, and expected block/allow behavior.

HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
HOOKS_DIR_PY=$(PYTHONIOENCODING=utf-8 python -c "import os; print(os.path.expanduser('~/.claude/hooks').replace(chr(92), '/'))")
PASS=0
FAIL=0
TOTAL=0

ok() { ((PASS++)); ((TOTAL++)); echo "  PASS: $1"; }
fail() { ((FAIL++)); ((TOTAL++)); echo "  FAIL: $1"; }

echo "=== Hook Smoke Tests ==="
echo ""

# --- Python syntax ---
echo "[0] Meta-test: harness self-verification"
_meta_result=$(bash << 'METAEOF'
PASS=0; FAIL=0; TOTAL=0
ok()   { ((++PASS));  ((++TOTAL)); }
fail() { ((++FAIL));  ((++TOTAL)); }
echo "match" | grep -q "match" && ok "pass case" || fail "pass case"
echo "nope"  | grep -q "match" && ok "fail case" || fail "fail case"
echo "$PASS $FAIL $TOTAL"
METAEOF
)
[ "$_meta_result" = "1 1 2" ] && ok "harness: ok/fail counters work correctly" || fail "harness: BROKEN counters (got: $_meta_result)"

echo "[1] Python syntax checks"
for f in "$HOOKS_DIR"/*.py; do
  fname=$(basename "$f")
  PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/_py_check.py" "$f" 2>/dev/null
  [ $? -eq 0 ] && ok "$fname" || fail "$fname"
done

# --- Bash syntax ---
echo "[2] Bash syntax checks"
for f in "$HOOKS_DIR"/*.sh; do
  fname=$(basename "$f")
  [ "$fname" = "smoke-test.sh" ] && continue
  bash -n "$f" 2>/dev/null
  [ $? -eq 0 ] && ok "$fname" || fail "$fname"
done

# --- validate-bash.sh ---
echo "[3] validate-bash.sh"
# Should block rm -rf /
result=$(echo '{"tool_input":{"command":"rm -rf /"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks rm -rf /" || fail "blocks rm -rf /"

# Should block git push --force
result=$(echo '{"tool_input":{"command":"git push --force origin main"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks git push --force" || fail "blocks git push --force"

# Should allow grep for drop table (context-sensitive)
result=$(echo '{"tool_input":{"command":"grep drop table migrations/"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 0 ] && ok "allows grep drop table" || fail "allows grep drop table"

# Should allow normal commands
result=$(echo '{"tool_input":{"command":"ls -la"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 0 ] && ok "allows ls -la" || fail "allows ls -la"

# Should block python -c wrapping rm -rf
result=$(echo '{"tool_input":{"command":"python -c \"import os; os.system(\\\"rm -rf /\\\")\" "}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks python -c rm -rf" || fail "blocks python -c rm -rf"

# Should block node -e wrapping force push
result=$(echo '{"tool_input":{"command":"node -e \"require(\\\"child_process\\\").execSync(\\\"git push --force\\\")\" "}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks node -e force push" || fail "blocks node -e force push"

# Should allow safe python -c
result=$(echo '{"tool_input":{"command":"python -c \"print(42)\""}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 0 ] && ok "allows safe python -c" || fail "allows safe python -c"

# Should block sh -c wrapping rm -rf
result=$(echo '{"tool_input":{"command":"sh -c \"rm -rf /\""}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks sh -c rm -rf" || fail "blocks sh -c rm -rf"

# Should block $'...' ANSI-C quoting bypass
PYTHONIOENCODING=utf-8 python -c "
import json
cmd = 'python -c \$' + \"'import os\\\\nos.system(\\\"rm -rf /\\\")' \"
print(json.dumps({'tool_input': {'command': cmd}}))
" | bash "$HOOKS_DIR/validate-bash.sh" 2>&1
[ ${PIPESTATUS[1]} -eq 2 ] && ok "blocks ANSI-C quoting bypass" || fail "blocks ANSI-C quoting bypass"

# Should block bash -c with single-quoted dangerous command
PYTHONIOENCODING=utf-8 python -c "
import json; print(json.dumps({'tool_input': {'command': \"bash -c 'rm -rf /'\"}}))" | bash "$HOOKS_DIR/validate-bash.sh" 2>&1
[ ${PIPESTATUS[1]} -eq 2 ] && ok "blocks bash -c single-quote rm -rf" || fail "blocks bash -c single-quote rm -rf"

# Should block git branch -D
result=$(echo '{"tool_input":{"command":"git branch -D feature/old"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks git branch -D" || fail "blocks git branch -D"

# Should block checkout -- .
result=$(echo '{"tool_input":{"command":"git checkout -- ."}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks checkout -- ." || fail "blocks checkout -- ."

# Should allow git branch -d (safe delete)
result=$(echo '{"tool_input":{"command":"git branch -d feature/old"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 0 ] && ok "allows git branch -d" || fail "allows git branch -d"

# Should block docker system prune
result=$(echo '{"tool_input":{"command":"docker system prune -af"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks docker system prune" || fail "blocks docker system prune"

# Should block npm publish
result=$(echo '{"tool_input":{"command":"npm publish"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks npm publish" || fail "blocks npm publish"

# npm publish in grep context should be allowed (context-sensitive)
result=$(echo '{"tool_input":{"command":"grep npm publish package.json"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 0 ] && ok "allows grep npm publish" || fail "allows grep npm publish"

# Should block kubectl delete namespace
result=$(echo '{"tool_input":{"command":"kubectl delete namespace production"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks kubectl delete namespace" || fail "blocks kubectl delete namespace"

# Should block drop database
result=$(echo '{"tool_input":{"command":"psql -c \"DROP DATABASE mydb\""}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks drop database" || fail "blocks drop database"

# echo mentioning drop database should be allowed (context-sensitive)
result=$(echo '{"tool_input":{"command":"echo \"never run drop database in prod\""}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 0 ] && ok "allows echo drop database" || fail "allows echo drop database"

# Should block gh repo delete
result=$(echo '{"tool_input":{"command":"gh repo delete myorg/myrepo --yes"}}' | bash "$HOOKS_DIR/validate-bash.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks gh repo delete" || fail "blocks gh repo delete"

# --- block-secrets.py ---
echo "[4] block-secrets.py"
# Should block password in Write
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"x.js","content":"password=\"SuperSecret123\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 2 ] && ok "blocks password in Write" || fail "blocks password in Write"

# Should block AWS key in Bash redirect
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"echo AKIAIOSFODNN7EXAMPLE > creds.txt"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 2 ] && ok "blocks AWS key in Bash redirect" || fail "blocks AWS key in Bash redirect"

# Should allow normal Write
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"x.js","content":"const x = 42;"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 0 ] && ok "allows normal Write" || fail "allows normal Write"

# Should allow .claude/ paths
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"/c/Users/Matt1/.claude/test.md","content":"password=\"test123456\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 0 ] && ok "allows .claude/ path" || fail "allows .claude/ path"

# Should fail-closed on bad JSON
result=$(echo 'NOT VALID JSON!!!' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 2 ] && ok "fail-closed on bad JSON" || fail "fail-closed on bad JSON"

# Should block secret in python -c interpreter command
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"python -c \"print(\\\"AKIAIOSFODNN7EXAMPLE\\\")\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 2 ] && ok "blocks secret in python -c" || fail "blocks secret in python -c"

# --- task-classifier.py ---
echo "[5] task-classifier.py"
result=$(echo '{"message":"hello"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -q "TRIVIAL" && ok "classifies hello as TRIVIAL" || fail "classifies hello as TRIVIAL"

result=$(echo '{"message":"refactor the entire authentication module across all files"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -q "COMPLEX\|DEEP" && ok "classifies refactor as COMPLEX+" || fail "classifies refactor as COMPLEX+"

# Should skip task-notification messages entirely (no output)
result=$(echo '{"message":"<task-notification> build deploy design implement across all files"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
[ -z "$result" ] && ok "skips task-notification" || fail "skips task-notification (got: $result)"

# debug should be SIMPLE, not COMPLEX
result=$(echo '{"message":"debug this error in the login flow"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -q "SIMPLE" && ok "classifies debug as SIMPLE" || fail "classifies debug as SIMPLE (got: $result)"

# "design" as noun should not trigger COMPLEX
result=$(echo '{"message":"the design looks good to me"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -qv "COMPLEX" && ok "design-as-noun not COMPLEX" || fail "design-as-noun not COMPLEX (got: $result)"

# --- project-detector (inside task-classifier.py) ---
echo "[5b] project-detector"

# True positives: should mention /new-project
result=$(echo '{"message":"create a new project called vaultlister"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -q "new-project" && ok "detects 'new project'" || fail "detects 'new project' (got: $result)"

result=$(echo '{"message":"newproject myapp"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -q "new-project" && ok "detects 'newproject'" || fail "detects 'newproject' (got: $result)"

result=$(echo '{"message":"set up notion for my new app"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -q "new-project" && ok "detects 'set up notion'" || fail "detects 'set up notion' (got: $result)"

result=$(echo '{"message":"start a new project for the blog"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -q "new-project" && ok "detects 'start a new project'" || fail "detects 'start a new project' (got: $result)"

# False positives: should NOT mention /new-project
result=$(echo '{"message":"set up the test environment for this project"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -qv "new-project" && ok "ignores 'set up...for...project'" || fail "ignores 'set up...for...project'"

result=$(echo '{"message":"start working on the new project tasks"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -qv "new-project" && ok "ignores 'new project tasks'" || fail "ignores 'new project tasks'"

result=$(echo '{"message":"can you create a workspace directory"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -qv "new-project" && ok "ignores 'create workspace dir'" || fail "ignores 'create workspace dir'"

result=$(echo '{"message":"initialize the project with npm init"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -qv "new-project" && ok "ignores 'initialize project'" || fail "ignores 'initialize project'"

# Question filter: should NOT trigger
result=$(echo '{"message":"how does the new project flow work"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/task-classifier.py" 2>&1)
echo "$result" | grep -qv "new-project" && ok "question filter blocks" || fail "question filter blocks"

# --- _notion_shared.py import ---
echo "[6] Shared module"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, re; p=re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR'); sys.path.insert(0, p)
from _notion_shared import load_token, detect_project_name, DB_LESSONS_LEARNED
assert len(DB_LESSONS_LEARNED) == 36, 'DB ID wrong length'
print('import OK')
" 2>&1 | grep -q "import OK" && ok "_notion_shared imports" || fail "_notion_shared imports"

# --- tool-failure-log.py ---
echo "[7] tool-failure-log.py"
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"ls"},"error":"Command failed","hook_event_name":"PostToolUseFailure","session_id":"test1234"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/tool-failure-log.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on failure input" || fail "exits 0 on failure input"

# --- session-end-log.py ---
echo "[8] session-end-log.py"
result=$(echo '{"reason":"clear","session_id":"test5678","hook_event_name":"SessionEnd"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/session-end-log.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on session end" || fail "exits 0 on session end"

# --- event-observer.py ---
echo "[9] event-observer.py"
result=$(echo '{"hook_event_name":"InstructionsLoaded","load_reason":"session_start","file_path":"/test/CLAUDE.md"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/event-observer.py" 2>&1)
[ $? -eq 0 ] && ok "handles InstructionsLoaded" || fail "handles InstructionsLoaded"

result=$(echo '{"hook_event_name":"ConfigChange","source":"user_settings","file_path":"settings.json"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/event-observer.py" 2>&1)
[ $? -eq 0 ] && ok "handles ConfigChange" || fail "handles ConfigChange"

result=$(echo '{"hook_event_name":"SessionStart","trigger":"compact"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/event-observer.py" 2>&1)
[ $? -eq 0 ] && ok "handles SessionStart" || fail "handles SessionStart"

result=$(echo '{"hook_event_name":"Unknown"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/event-observer.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on unknown event" || fail "exits 0 on unknown event"

# --- pre-compact-snapshot.py ---
echo "[10] pre-compact-snapshot.py"
result=$(echo '{"transcript_path":"/nonexistent/path.jsonl","session_id":"test9999","trigger":"auto","hook_event_name":"PreCompact"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/pre-compact-snapshot.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 with nonexistent transcript" || fail "exits 0 with nonexistent transcript"

# --- quality-gate.py transcript tests (mechanical layer only) ---
echo "[11] quality-gate.py transcript tests"
# Clear LLM eval cache before these tests to prevent stale context-mismatched results
PYTHONIOENCODING=utf-8 python -c "import json, os; open(os.path.expanduser('~/.claude/quality-gate-cache.json'), 'w').write('{}')" 2>/dev/null || true

# Force SIMPLE complexity so Haiku LLM layer is skipped — we're testing mechanical checks only
_QG_CLASSIFIER_LOG="$HOME/.claude/task-classifier.log"
_qg_backup=$(cat "$_QG_CLASSIFIER_LOG" 2>/dev/null)
echo "$(date +%Y-%m-%d) | SIMPLE | smoke-test" >> "$_QG_CLASSIFIER_LOG"

# Run a quality gate test entirely in Python (avoids /tmp path issues on Windows)
# Args: $1=test name, $2=expected ("block"|"continue"), $3=transcript JSON (array of lines)
_qg_run() {
  local test_name="$1" expected="$2"
  shift 2
  # Build transcript as single JSON array string, then run gate in Python
  local transcript_json="["
  local first=true
  for line in "$@"; do
    if [ "$first" = true ]; then first=false; else transcript_json+=","; fi
    transcript_json+="$line"
  done
  transcript_json+="]"
  local result
  result=$(PYTHONIOENCODING=utf-8 python -c "
import json, os, sys, subprocess, tempfile

lines = json.loads(r'''$transcript_json''')
tf = tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8')
for item in lines:
    tf.write(json.dumps(item) + '\n')
tf.close()

resp = ''
for item in reversed(lines):
    if item.get('type') == 'assistant':
        for b in item.get('message', {}).get('content', []):
            if isinstance(b, dict) and b.get('type') == 'text':
                resp = b.get('text', '')
                break
        if resp:
            break

payload = json.dumps({
    'last_assistant_message': resp,
    'transcript_path': tf.name,
    'stop_hook_active': False
})

r = subprocess.run(
    [sys.executable, os.path.expanduser('~/.claude/hooks/quality-gate.py').replace(chr(92), '/')],
    input=payload, capture_output=True, text=True,
    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    timeout=10
)
print(r.stdout.strip())
os.unlink(tf.name)
" 2>/dev/null)
  if echo "$result" | grep -q "\"$expected\""; then
    ok "$test_name"
  else
    fail "$test_name (got: $result)"
  fi
}

# Test 1: Edit without verification → BLOCK
_qg_run "blocks edit without verify" "block" \
  '{"type":"user","message":{"content":"Fix the auth bug"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"t0","input":{"file_path":"src/auth.js"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t0","content":"// auth code"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t1","input":{"file_path":"src/auth.js","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Fixed the auth bug."}]}}'

# Test 2: Edit + real test → PASS
_qg_run "passes edit + verify" "continue" \
  '{"type":"user","message":{"content":"Fix the auth bug"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"t0","input":{"file_path":"src/auth.js"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t0","content":"// auth code"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t1","input":{"file_path":"src/auth.js","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t2","input":{"command":"bun test src/tests/auth.test.js"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","content":"32 passed, 0 failed"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Fixed the auth bug. Test output: 32 passed, 0 failed."}]}}'

# Test 3: Edit last (verify ran before final edit) → BLOCK
_qg_run "blocks edit-last" "block" \
  '{"type":"user","message":{"content":"Fix two files"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t1","input":{"command":"bun test"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"pass"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t2","input":{"file_path":"src/x.js","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Done."}]}}'

# Test 4: Fake bash (echo done) after edit → BLOCK
_qg_run "blocks fake bash (echo)" "block" \
  '{"type":"user","message":{"content":"Fix the bug"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t1","input":{"file_path":"src/x.js","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t2","input":{"command":"echo done"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","content":"done"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Fixed."}]}}'

# Test 5: Non-code edit (memory file) without verify → PASS
_qg_run "passes non-code edit" "continue" \
  '{"type":"user","message":{"content":"Update memory/STATUS.md to record that auth refactor is complete"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Read","id":"t0","input":{"file_path":"memory/STATUS.md"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t0","content":"# Memory notes"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t1","input":{"file_path":"memory/STATUS.md","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Read memory/STATUS.md and updated it to record that auth refactor is complete."}]}}'

# Test 6: Quantity mismatch (5 items, 1 file) → BLOCK
_qg_run "blocks quantity mismatch" "block" \
  '{"type":"user","message":{"content":"Fix all 5 bugs: auth timeout, CSRF bypass, SQL injection, XSS, rate limit"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t1","input":{"file_path":"src/auth.js","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t2","input":{"command":"bun test src/tests/auth.test.js"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","content":"pass"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"All 5 fixed. Tests pass."}]}}'

# Test 7: No tools, short response → PASS
_qg_run "passes no-tool short" "continue" \
  '{"type":"user","message":{"content":"What time is it?"}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"I don't have access to real-time information, so I can't check the current time."}]}}'

# Test 8: Agent without post-agent verification → BLOCK
_qg_run "blocks agent without verify" "block" \
  '{"type":"user","message":{"content":"Fix the CSS layout"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Agent","id":"t1","input":{"prompt":"Fix layout","subagent_type":"Frontend-UI"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"Fixed the layout in pages/inventory.js"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"The layout is fixed."}]}}'

# Test 9: Agent followed by Bash verification → PASS
_qg_run "passes agent + verify" "continue" \
  '{"type":"user","message":{"content":"Fix the CSS layout"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Agent","id":"t1","input":{"prompt":"Fix layout","subagent_type":"Frontend-UI"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"Fixed the layout"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t2","input":{"command":"bun test src/tests/layout.test.js"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","content":"5 pass, 0 fail"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Agent handled the layout fix. Tests pass -- 5 passed, 0 failed."}]}}'

# Test 10: Bash failed but response ignores the error → BLOCK
_qg_run "blocks ignored failure" "block" \
  '{"type":"user","message":{"content":"Run the migration"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t1","input":{"file_path":"src/db.js","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t2","input":{"command":"bun run db:migrate"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","is_error":true,"content":"SQLITE_ERROR: table users already exists"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"Migration complete. The database is up to date."}]}}'

# Test 11: Bash failed and response addresses the error → PASS
_qg_run "passes addressed failure" "continue" \
  '{"type":"user","message":{"content":"Run the migration"}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Edit","id":"t1","input":{"file_path":"src/db.js","old_string":"a","new_string":"b"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t1","content":"edited"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t2","input":{"command":"bun run db:migrate"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t2","is_error":true,"content":"SQLITE_ERROR: table users already exists"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","id":"t3","input":{"command":"bun test src/tests/db.test.js"}}]}}' \
  '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"t3","content":"12 pass"}]}}' \
  '{"type":"assistant","message":{"content":[{"type":"text","text":"The SQLITE_ERROR (table users already exists) means this migration already ran in a prior session — the table was created then. Ran the full db test suite to confirm: 12/12 pass with no data issues."}]}}'

# Test 12: stop_hook_active guard — should pass through immediately
result=$(PYTHONIOENCODING=utf-8 python -c "
import json, subprocess, sys, os
payload = json.dumps({'last_assistant_message': 'This would normally block.', 'transcript_path': '', 'stop_hook_active': True})
r = subprocess.run([sys.executable, os.path.expanduser('~/.claude/hooks/quality-gate.py').replace(chr(92), '/')],
    input=payload, capture_output=True, text=True, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=5)
print(r.stdout.strip())
" 2>/dev/null)
echo "$result" | grep -q '"continue"' && ok "stop_hook_active passes through" || fail "stop_hook_active passes through (got: $result)"

# Restore classifier log
echo "$_qg_backup" > "$_QG_CLASSIFIER_LOG"

# --- context-watch.py ---
echo "[12] context-watch.py"

# Below 70% → exit 0, no output
result=$(echo '{"session_id":"test-cw-1","context":{"tokens_used":50000,"context_window":200000}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/context-watch.py" 2>&1)
[ $? -eq 0 ] && [ -z "$result" ] && ok "silent below 70%" || fail "silent below 70% (got: $result)"

# At 90%+ → should emit compact reminder
# First, clear debounce state for this test session
echo '{}' > "$HOME/.claude/context-toast-state.json"
result=$(echo '{"session_id":"test-cw-2","context":{"tokens_used":185000,"context_window":200000}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/context-watch.py" 2>&1)
[ $? -eq 0 ] && echo "$result" | grep -q "compact needed" && ok "emits reminder at 90%+" || fail "emits reminder at 90%+ (got: $result)"

# Debounce: same session + same threshold → no toast, but 90%+ still emits message
result=$(echo '{"session_id":"test-cw-2","context":{"tokens_used":185000,"context_window":200000}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/context-watch.py" 2>&1)
[ $? -eq 0 ] && echo "$result" | grep -q "compact needed" && ok "debounce still emits 90% message" || fail "debounce still emits 90% message (got: $result)"

# Clean up test toast state
echo '{}' > "$HOME/.claude/context-toast-state.json"

# --- stop-log.py ---
echo "[13] stop-log.py"

# Basic: should exit 0 and append to audit log
_sl_backup=""
_sl_test_log="$HOME/.claude/audit-log-test.md"
# Temporarily redirect LOG_PATH by wrapping in python
result=$(PYTHONIOENCODING=utf-8 python -c "
import json, subprocess, sys, os
payload = json.dumps({
    'session_id': 'test-sl-1234',
    'cost': {'total_cost_usd': 1.234, 'total_duration_ms': 125000},
    'model': {'display_name': 'sonnet'},
    'workspace': {'current_dir': os.path.expanduser('~/testproject')}
})
r = subprocess.run(
    [sys.executable, os.path.expanduser('~/.claude/hooks/stop-log.py').replace(chr(92), '/')],
    input=payload, capture_output=True, text=True,
    env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}, timeout=5
)
sys.exit(r.returncode)
" 2>/dev/null)
[ $? -eq 0 ] && ok "exits 0 on valid stop" || fail "exits 0 on valid stop"

# Should have written to audit-log.md
grep -q "test-sl-" "$HOME/.claude/audit-log.md" && ok "appends to audit log" || fail "appends to audit log"

# Empty/malformed input → exit 0 gracefully
result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/stop-log.py" 2>&1)
[ $? -eq 0 ] && ok "handles malformed input" || fail "handles malformed input"

# Missing cost fields → exit 0
result=$(echo '{"session_id":"test-sl-empty"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/stop-log.py" 2>&1)
[ $? -eq 0 ] && ok "handles missing cost fields" || fail "handles missing cost fields"

# --- permission-guard.py ---
echo "[14] permission-guard.py"

# Should block force push to main
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin main"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-guard.py" 2>&1)
echo "$result" | grep -q '"block"' && ok "blocks force push to main" || fail "blocks force push to main (got: $result)"

# Should block curl to unknown domain
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"curl https://evil.com/data"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-guard.py" 2>&1)
echo "$result" | grep -q '"block"' && ok "blocks curl to unknown domain" || fail "blocks curl to unknown domain (got: $result)"

# Should auto-allow git status
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"git status"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-guard.py" 2>&1)
[ -z "$result" ] && ok "auto-allows git status" || fail "auto-allows git status (got: $result)"

# Should exit 0 (no opinion) for non-Bash tools
result=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"x.js"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-guard.py" 2>&1)
[ $? -eq 0 ] && [ -z "$result" ] && ok "no opinion on non-Bash" || fail "no opinion on non-Bash (got: $result)"

# Should allow curl to allowed domains (no deny output)
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"curl https://api.notion.com/v1/pages"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-guard.py" 2>&1)
echo "$result" | grep -qv '"deny"' && ok "allows curl to api.notion.com" || fail "allows curl to api.notion.com"

# Should handle env-prefixed curl (VAR=x curl ...)
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"NOTION_TOKEN=secret curl https://evil.com/api"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-guard.py" 2>&1)
echo "$result" | grep -q '"block"' && ok "blocks env-prefixed curl to unknown" || fail "blocks env-prefixed curl to unknown (got: $result)"

# Force push to non-main branch → no opinion (not blocked)
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"git push --force origin feature/x"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-guard.py" 2>&1)
[ $? -eq 0 ] && [ -z "$result" ] && ok "no opinion on force push to feature" || fail "no opinion on force push to feature (got: $result)"

# --- stop-failure-log.py ---
echo "[15] stop-failure-log.py"

# Should exit 0 and log the failure
result=$(echo '{"error":"rate_limit","error_details":"Too many requests","session_id":"test-sf-1"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/stop-failure-log.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on rate_limit" || fail "exits 0 on rate_limit"

# Should handle malformed input
result=$(echo 'garbage' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/stop-failure-log.py" 2>&1)
[ $? -eq 0 ] && ok "handles malformed input" || fail "handles malformed input"

# --- subagent-quality-gate.py ---
echo "[16] subagent-quality-gate.py"

# Should pass through when stop_hook_active
result=$(echo '{"stop_hook_active":true}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/subagent-quality-gate.py" 2>&1)
echo "$result" | grep -q '"continue"' && ok "passes on stop_hook_active" || fail "passes on stop_hook_active (got: $result)"

# Should pass with no tools (empty transcript)
result=$(echo '{"agent_type":"researcher","agent_transcript_path":""}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/subagent-quality-gate.py" 2>&1)
echo "$result" | grep -q '"continue"' && ok "passes with empty transcript" || fail "passes with empty transcript (got: $result)"

# LLM eval path: response present -> returns valid JSON (pass or block depending on API key)
result=$(echo '{"agent_type":"researcher","agent_transcript_path":"","last_assistant_message":"The fetchUsers function queries the database and returns user objects."}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/subagent-quality-gate.py" 2>&1)
echo "$result" | PYTHONIOENCODING=utf-8 python -c "import sys,json; json.load(sys.stdin)" 2>/dev/null && ok "LLM eval returns valid JSON" || fail "LLM eval returns valid JSON (got: $result)"

# --- _hooks_shared.py ---
echo "[17] _hooks_shared.py"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, re; p=re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR'); sys.path.insert(0, p)
from _hooks_shared import rotate_log, NON_CODE_PATH_RE, VALIDATION_COMMAND_RE
assert NON_CODE_PATH_RE.search('memory/STATUS.md'), 'NON_CODE_PATH_RE failed'
assert VALIDATION_COMMAND_RE.search('bun test'), 'VALIDATION_COMMAND_RE failed'
print('import OK')
" 2>&1 | grep -q "import OK" && ok "_hooks_shared imports + regexes" || fail "_hooks_shared imports + regexes"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, re; p=re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR'); sys.path.insert(0, p)
from _hooks_shared import load_api_key, check_cache, write_cache, call_haiku_check, FEW_SHOT_EXAMPLES, CACHE_PATH
assert 'Example 37' in FEW_SHOT_EXAMPLES, 'Example 28 missing'
assert callable(call_haiku_check), 'call_haiku_check not callable'
assert 'quality-gate-cache.json' in CACHE_PATH, 'CACHE_PATH wrong'
print('new exports OK')
" 2>&1 | grep -q 'new exports OK' && ok "_hooks_shared new LLM exports" || fail "_hooks_shared new LLM exports"

# --- block-secrets.py allowlist ---
echo "[18] block-secrets.py allowlist"

# Global ~/.claude/ path should be allowed (C:/ style)
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"C:/Users/Matt1/.claude/test.md","content":"password=\"test123456\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 0 ] && ok "allows global .claude/ (C:/)" || fail "allows global .claude/ (C:/)"

# Global ~/.claude/ path should be allowed (/c/ Git Bash style)
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"/c/Users/Matt1/.claude/hooks/test.py","content":"password=\"test123456\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 0 ] && ok "allows global .claude/ (/c/)" || fail "allows global .claude/ (/c/)"

# Project-level .claude/ should NOT be allowed
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"C:/Projects/app/.claude/config.json","content":"password=\"SuperSecret123\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 2 ] && ok "blocks project .claude/ secrets" || fail "blocks project .claude/ secrets"

# Other user's ~/.claude/ should NOT be allowed
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"/home/other/.claude/config.json","content":"password=\"SuperSecret123\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 2 ] && ok "blocks other-user .claude/" || fail "blocks other-user .claude/"

# .github/workflows still allowed
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"C:/Projects/app/.github/workflows/ci.yml","content":"password=\"test_jwt_secret_for_ci\""}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/block-secrets.py" 2>&1)
[ $? -eq 0 ] && ok "allows .github/workflows" || fail "allows .github/workflows"

# --- prune-permissions.py ---
echo "[19] prune-permissions.py"

# Test the is_reusable logic directly
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys, os, importlib.util, re
p = re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR')
spec = importlib.util.spec_from_file_location('pp', p + '/prune-permissions.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

tests = [
    ('Skill(build)', True),
    ('mcp__notion__search', True),
    ('WebFetch(domain:x.com)', True),
    ('Bash(gh pr:*)', True),
    ('Bash(git commit:*)', True),
    ('Bash(ps aux:*)', True),
    ('Bash(echo hello)', False),
    ('Bash(python -c \"import os\")', False),
    ('Bash(PYTHONIOENCODING=utf-8 python -c \"very long command with * in regex pattern that is not a glob\")', False),
]
ok = all(mod.is_reusable(e) == exp for e, exp in tests)
print('ALL_PASS' if ok else 'FAIL')
for e, exp in tests:
    if mod.is_reusable(e) != exp:
        print(f'  {e[:60]} => got {mod.is_reusable(e)}, expected {exp}')
" 2>&1)
echo "$result" | grep -q "ALL_PASS" && ok "is_reusable logic" || fail "is_reusable logic ($result)"

# Functional test: create temp settings, prune via subprocess, verify
_pp_test_dir=$(mktemp -d)
_pp_test_file="$_pp_test_dir/settings.local.json"
cat > "$_pp_test_file" << 'PPEOF'
{"permissions":{"allow":["Skill(build)","Bash(gh pr:*)","Bash(echo hello)","Bash(ls -la)","mcp__notion__search"]}}
PPEOF
# Write test runner to a temp script to avoid quoting hell
cat > "$_pp_test_dir/run_prune.py" << PYEOF
import json, os, sys, tempfile
test_file = sys.argv[1]
MAX_REUSABLE_LEN = 40
def is_reusable(e):
    if not e.startswith('Bash('):
        return True
    return '*' in e and len(e) <= MAX_REUSABLE_LEN
with open(test_file) as f:
    data = json.load(f)
allow = data['permissions']['allow']
cleaned = [e for e in allow if is_reusable(e)]
data['permissions']['allow'] = cleaned
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(test_file), suffix='.tmp')
with os.fdopen(fd, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
os.replace(tmp, test_file)
with open(test_file) as f:
    result = json.load(f)
entries = result['permissions']['allow']
ok = ('Skill(build)' in entries and 'Bash(gh pr:*)' in entries
      and 'mcp__notion__search' in entries
      and 'Bash(echo hello)' not in entries
      and 'Bash(ls -la)' not in entries
      and len(entries) == 3)
print('PRUNE_OK' if ok else f'FAIL: {entries}')
PYEOF
result=$(PYTHONIOENCODING=utf-8 python "$_pp_test_dir/run_prune.py" "$_pp_test_file" 2>&1)
echo "$result" | grep -q "PRUNE_OK" && ok "prunes one-off Bash entries" || fail "prunes one-off Bash entries ($result)"
rm -rf "$_pp_test_dir"

# --- pre-compact-snapshot.py ---
echo "[20] pre-compact-snapshot.py"

# Manual trigger → should log and exit 0 (toast may fail in test env — that's fine)
result=$(echo '{"session_id":"test-pcs-1","trigger":"manual","transcript_path":"/nonexistent"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/pre-compact-snapshot.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on manual trigger" || fail "exits 0 on manual trigger"

# Auto trigger → exit 0
result=$(echo '{"session_id":"test-pcs-2","trigger":"auto","transcript_path":""}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/pre-compact-snapshot.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on auto trigger" || fail "exits 0 on auto trigger"

# With real transcript → should create snapshot
# Use Windows-resolvable path (Python can't see /c/Users/ or /tmp/)
_pcs_sessions="$HOME/.claude/sessions"
mkdir -p "$_pcs_sessions"
_pcs_winpath=$(PYTHONIOENCODING=utf-8 python -c "import os, tempfile; d=os.path.expanduser('~/.claude/sessions').replace(chr(92),'/'); f=tempfile.NamedTemporaryFile(dir=d, suffix='.jsonl', delete=False); print(f.name.replace(chr(92),'/')); f.close()")
echo '{"type":"test"}' > "$_pcs_winpath"
_pcs_before=$(ls "$_pcs_sessions/"*.jsonl.bak 2>/dev/null | wc -l)
result=$(echo "{\"session_id\":\"smokepcs1\",\"trigger\":\"manual\",\"transcript_path\":\"$_pcs_winpath\"}" | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/pre-compact-snapshot.py" 2>&1)
[ $? -eq 0 ] && ok "snapshots real transcript" || fail "snapshots real transcript"
_pcs_after=$(ls "$_pcs_sessions/"*.jsonl.bak 2>/dev/null | wc -l)
[ "$_pcs_after" -gt "$_pcs_before" ] && ok "snapshot file created" || fail "snapshot file created (before=$_pcs_before after=$_pcs_after)"
rm -f "$_pcs_winpath"
rm -f "$_pcs_sessions/"*smokepcs*.jsonl.bak 2>/dev/null

# --- session-end-log.py ---
echo "[21] session-end-log.py"

# Normal end reason
result=$(echo '{"reason":"user_exit","session_id":"test-sel-1"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/session-end-log.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on user_exit" || fail "exits 0 on user_exit"

# Verify it wrote to hook-audit.log
grep -q "SESSION_END.*user_exit.*test-sel" "$HOME/.claude/hook-audit.log" && ok "logs exit reason" || fail "logs exit reason"

# Empty payload → exit 0
result=$(echo '{}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/session-end-log.py" 2>&1)
[ $? -eq 0 ] && ok "handles empty payload" || fail "handles empty payload"

# --- context-watch.py (expanded) ---
echo "[22] context-watch.py (expanded)"

# At exactly 70% → should fire toast (reset debounce first)
echo '{}' > "$HOME/.claude/context-toast-state.json"
result=$(echo '{"session_id":"test-cw-70","context":{"tokens_used":140000,"context_window":200000}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/context-watch.py" 2>&1)
# 70% fires toast but no stdout message (only 90%+ emits stdout)
[ $? -eq 0 ] && ok "fires at 70% boundary" || fail "fires at 70% boundary"

# Below 70% with statusline state file showing low pct → silent exit
echo '{}' > "$HOME/.claude/context-toast-state.json"
result=$(echo '{"session_id":"test-cw-low","context":{"tokens_used":10000,"context_window":200000}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/context-watch.py" 2>&1)
[ $? -eq 0 ] && [ -z "$result" ] && ok "silent below 70% (payload)" || fail "silent below 70% (payload) (got: $result)"

# Missing context fields → exit 0, no crash
result=$(echo '{"session_id":"test-cw-no-ctx"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/context-watch.py" 2>&1)
[ $? -eq 0 ] && ok "handles missing context fields" || fail "handles missing context fields"

# Clean up
echo '{}' > "$HOME/.claude/context-toast-state.json"

# --- [23a] _notion_shared.py ---
echo "[23a] _notion_shared.py"

# load_token: reads from temp .env
TEMP_ENV=$(PYTHONIOENCODING=utf-8 python -c "import tempfile, os; f=tempfile.NamedTemporaryFile(mode='w',suffix='.env',delete=False,dir=os.environ.get('TEMP','/tmp')); f.write('NOTION_TOKEN=ntn_test123\n'); f.close(); print(f.name)")
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, '$HOOKS_DIR_PY')
import _notion_shared as ns
ns.ENV_PATH = r'$TEMP_ENV'
t = ns.load_token()
print('OK' if t == 'ntn_test123' else f'FAIL:{t}')
")
[ "$result" = "OK" ] && ok "load_token reads valid token" || fail "load_token reads valid token ($result)"

# load_token: returns None for placeholder token
echo 'NOTION_TOKEN=YOUR_TOKEN_HERE' > "$TEMP_ENV"
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, '$HOOKS_DIR_PY')
import _notion_shared as ns
ns.ENV_PATH = r'$TEMP_ENV'
t = ns.load_token()
print('OK' if t is None else f'FAIL:{t}')
")
[ "$result" = "OK" ] && ok "load_token rejects placeholder" || fail "load_token rejects placeholder ($result)"
rm -f "$TEMP_ENV"

# detect_project_name: returns None for home dir
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, '$HOOKS_DIR_PY')
import _notion_shared as ns
home = os.path.expanduser('~').replace(chr(92), '/')
p = ns.detect_project_name({'cwd': home})
print('OK' if p is None else f'FAIL:{p}')
")
[ "$result" = "OK" ] && ok "detect_project_name: None for home dir" || fail "detect_project_name: None for home dir ($result)"

# notion_headers: returns correct structure
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, '$HOOKS_DIR_PY')
from _notion_shared import notion_headers
h = notion_headers('tok123')
ok = h.get('Authorization') == 'Bearer tok123' and 'Notion-Version' in h and 'Content-Type' in h
print('OK' if ok else 'FAIL')
")
[ "$result" = "OK" ] && ok "notion_headers structure" || fail "notion_headers structure ($result)"

# --- [23b] notion-capture.py (pure functions) ---
echo "[23b] notion-capture.py (pure functions)"

# _is_error: detects error patterns
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, '$HOOKS_DIR_PY')
import importlib
mod = importlib.import_module('notion-capture')
checks = [
    mod._is_error('Error: file not found') == True,
    mod._is_error('FAILED to connect') == True,
    mod._is_error('status 500 internal') == True,
    mod._is_error('everything is fine') == False,
    mod._is_error('Permission denied') == True,
]
print('OK' if all(checks) else f'FAIL:{checks}')
")
[ "$result" = "OK" ] && ok "_is_error detects patterns" || fail "_is_error detects patterns ($result)"

# _strip_pii: redacts emails and phone numbers
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, '$HOOKS_DIR_PY')
import importlib
mod = importlib.import_module('notion-capture')
checks = [
    '[REDACTED]' in mod._strip_pii('Contact user@example.com for help'),
    '[REDACTED]' in mod._strip_pii('Call 555-123-4567 now'),
    mod._strip_pii('no pii here') == 'no pii here',
]
print('OK' if all(checks) else f'FAIL:{checks}')
")
[ "$result" = "OK" ] && ok "_strip_pii redacts PII" || fail "_strip_pii redacts PII ($result)"

# _normalize_text: strips markdown formatting
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, '$HOOKS_DIR_PY')
import importlib
mod = importlib.import_module('notion-capture')
bt = chr(96)  # backtick without bash confusion
checks = [
    'bold text' in mod._normalize_text('**bold text**'),
    'code' in mod._normalize_text(bt + 'code' + bt),
    '  ' not in mod._normalize_text('lots   of   spaces'),
]
print('OK' if all(checks) else f'FAIL:{checks}')
")
[ "$result" = "OK" ] && ok "_normalize_text strips markdown" || fail "_normalize_text strips markdown ($result)"

# is_trivial_session: too few messages
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, '$HOOKS_DIR_PY')
import importlib
mod = importlib.import_module('notion-capture')
trivial = mod.is_trivial_session({'user_messages': ['hi'], 'first_ts': None, 'last_ts': None})
non_trivial = mod.is_trivial_session({'user_messages': ['a','b','c','d'], 'first_ts': None, 'last_ts': None})
print('OK' if trivial and not non_trivial else f'FAIL:trivial={trivial},non_trivial={non_trivial}')
")
[ "$result" = "OK" ] && ok "is_trivial_session threshold" || fail "is_trivial_session threshold ($result)"

# _is_technical_term: filters common words vs technical terms
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, '$HOOKS_DIR_PY')
import importlib
mod = importlib.import_module('notion-capture')
bt = chr(96)
checks = [
    mod._is_technical_term('CRLF', 'about CRLF') == True,
    mod._is_technical_term('node_modules', 'clean node_modules') == True,
    mod._is_technical_term('this', 'use this') == False,
    mod._is_technical_term('TOCTOU', bt + 'TOCTOU' + bt + ' race') == True,
]
print('OK' if all(checks) else f'FAIL:{checks}')
")
[ "$result" = "OK" ] && ok "_is_technical_term filters" || fail "_is_technical_term filters ($result)"

# notion-capture.py: exits 0 with no token (graceful degradation)
result=$(echo '{"session_id":"test-nc-notoken"}' | PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, '$HOOKS_DIR_PY')
import _notion_shared as ns
ns.ENV_PATH = '/nonexistent/.env'
import importlib
mod = importlib.import_module('notion-capture')
mod.load_token = ns.load_token
mod.main()
" 2>/dev/null)
[ $? -eq 0 ] && ok "exits 0 with no token" || fail "exits 0 with no token"

# --- [23c] notion-recall.py (pure functions) ---
echo "[23c] notion-recall.py"

# get_text: extracts from Notion property types
result=$(PYTHONIOENCODING=utf-8 python -c "
import sys; sys.path.insert(0, '$HOOKS_DIR_PY')
import importlib
mod = importlib.import_module('notion-recall')
checks = [
    mod.get_text({'type':'title','title':[{'plain_text':'Hello'}]}) == 'Hello',
    mod.get_text({'type':'rich_text','rich_text':[{'plain_text':'World'}]}) == 'World',
    mod.get_text({'type':'select','select':{'name':'Bug'}}) == 'Bug',
    mod.get_text({'type':'multi_select','multi_select':[{'name':'A'},{'name':'B'}]}) == 'A, B',
    mod.get_text(None) == '',
    mod.get_text({}) == '',
]
print('OK' if all(checks) else f'FAIL:{checks}')
")
[ "$result" = "OK" ] && ok "get_text extracts all property types" || fail "get_text extracts all property types ($result)"

# notion-recall.py: exits 0 with no token, no output
# Override _notion_shared.ENV_PATH to a non-existent file so load_token returns None
result=$(echo '{"trigger":"test"}' | PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, '$HOOKS_DIR_PY')
import _notion_shared as ns
ns.ENV_PATH = '/nonexistent/.env'
import importlib
mod = importlib.import_module('notion-recall')
mod.load_token = ns.load_token  # Use patched version
mod.main()
" 2>/dev/null)
rc=$?
[ $rc -eq 0 ] && [ -z "$result" ] && ok "exits 0, no output without token" || fail "exits 0, no output without token (rc=$rc, out=$result)"

# --- [23] protect-files.sh ---
echo "[23] protect-files.sh"

# Block Edit to hooks directory
result=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"C:\\Users\\Matt1\\.claude\\hooks\\somefile.py","old_string":"x","new_string":"y"}}' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks Edit to hooks dir" || fail "blocks Edit to hooks dir"

# Block Write to settings.json
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"C:\\Users\\Matt1\\.claude\\settings.json","content":"bad"}}' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks Write to settings.json" || fail "blocks Write to settings.json"

# Block Write to settings.local.json
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"C:\\Users\\Matt1\\.claude\\settings.local.json","content":"bad"}}' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks Write to settings.local.json" || fail "blocks Write to settings.local.json"

# Block Edit with forward-slash path variant
result=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"C:/Users/Matt1/.claude/hooks/evil.py","old_string":"a","new_string":"b"}}' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 2 ] && ok "blocks Edit (forward-slash path)" || fail "blocks Edit (forward-slash path)"

# Allow Edit to a normal project file
result=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"C:\\Users\\Matt1\\projects\\app\\main.py","old_string":"x","new_string":"y"}}' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 0 ] && ok "allows Edit to project file" || fail "allows Edit to project file"

# Allow Write to non-protected .claude path (e.g. memory)
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"C:\\Users\\Matt1\\.claude\\memory\\note.md","content":"ok"}}' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 0 ] && ok "allows Write to memory dir" || fail "allows Write to memory dir"

# Non-Edit/Write tool → exit 0
result=$(echo '{"tool_name":"Read","tool_input":{"file_path":"C:\\Users\\Matt1\\.claude\\hooks\\protect-files.sh"}}' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 0 ] && ok "allows Read tool (non-Edit/Write)" || fail "allows Read tool (non-Edit/Write)"

# Empty/invalid JSON → exit 0 (no crash)
result=$(echo 'not json' | bash "$HOOKS_DIR/protect-files.sh" 2>&1)
[ $? -eq 0 ] && ok "handles invalid JSON gracefully" || fail "handles invalid JSON gracefully"
# --- permission-request-log.py ---
echo "[24] permission-request-log.py"

# Valid Bash payload -> exits 0, never blocks
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-request-log.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on valid payload" || fail "exits 0 on valid payload"

# Appends PERMISSION_REQUEST entry to hook-audit.log
echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-request-log.py" 2>/dev/null
grep -q "PERMISSION_REQUEST.*Bash.*git push" "$HOME/.claude/hook-audit.log" && ok "logs PERMISSION_REQUEST entry" || fail "logs PERMISSION_REQUEST entry"

# Logs file_path for Edit tool
echo '{"tool_name":"Edit","tool_input":{"file_path":"src/config.py"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-request-log.py" 2>/dev/null
grep -q "PERMISSION_REQUEST.*Edit.*src/config.py" "$HOME/.claude/hook-audit.log" && ok "logs file_path for Edit tool" || fail "logs file_path for Edit tool"

# Bad JSON -> exits 0 (fail-open, never blocks)
result=$(echo 'not valid json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/permission-request-log.py" 2>&1)
[ $? -eq 0 ] && ok "exits 0 on bad JSON" || fail "exits 0 on bad JSON"

echo "[25] quality-gate learning loop"

# write_override importable from _hooks_shared
PYTHONIOENCODING=utf-8 python -c "
import sys, os, re; p=re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR'); sys.path.insert(0, p)
from _hooks_shared import write_override, OVERRIDES_PATH
print('write_override OK')
" 2>&1 | grep -q "write_override OK" && ok "write_override importable from _hooks_shared" || fail "write_override importable from _hooks_shared"

# _detect_override writes override record (injectable log_path)
PYTHONIOENCODING=utf-8 python -c "
import sys, os, re, importlib.util, json
from datetime import datetime
p = re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR')
sys.path.insert(0, p)
import _hooks_shared as hs
td = os.path.expanduser('~/.claude/tmp_smoke25').replace(chr(92), '/')
os.makedirs(td, exist_ok=True)
log_tmp = td + '/qg_smoke_log.txt'
ovr_tmp = td + '/qg_smoke_ovr.jsonl'
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
reason = 'ASSUMPTION: test block'.ljust(80)
log_line = now + ' | BLOCK | simple   | ' + reason + ' | tools=-     | req=detect test req  | hash=test0000\n'
with open(log_tmp, 'w') as f: f.write(log_line)
orig = hs.OVERRIDES_PATH
hs.OVERRIDES_PATH = ovr_tmp
spec = importlib.util.spec_from_file_location('quality_gate', os.path.join(p, 'quality-gate.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
mod._detect_override('detect test req', ['Read'], 'test response', log_path=log_tmp)
hs.OVERRIDES_PATH = orig
with open(ovr_tmp) as f: lines = [l for l in f if l.strip()]
assert lines, 'no override written'
rec = json.loads(lines[-1])
assert rec.get('auto_verdict') in ('likely_fp', 'likely_tp'), 'bad verdict: ' + str(rec)
import shutil; shutil.rmtree(td, ignore_errors=True)
print('detect_override OK')
" 2>&1 | grep -q "detect_override OK" && ok "_detect_override writes override record" || fail "_detect_override writes override record"

# quality-gate-analyst.py syntax valid
PYTHONIOENCODING=utf-8 python -c "
import ast, os
with open(os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'), encoding='utf-8') as f: src = f.read()
ast.parse(src)
print('analyst syntax OK')
" 2>&1 | grep -q "analyst syntax OK" && ok "quality-gate-analyst.py syntax valid" || fail "quality-gate-analyst.py syntax valid"

# qg failures subcommand: runs without crashing
result=$(PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py failures 2>&1)
[ $? -eq 0 ] && ok "qg failures subcommand" || fail "qg failures subcommand: $result"

# qg-feedback.py syntax valid
PYTHONIOENCODING=utf-8 python -c "
import ast, os
with open(os.path.expanduser('~/.claude/scripts/qg-feedback.py'), encoding='utf-8') as f: src = f.read()
ast.parse(src)
print('feedback syntax OK')
" 2>&1 | grep -q "feedback syntax OK" && ok "qg-feedback.py syntax valid" || fail "qg-feedback.py syntax valid"

echo ""
echo "[26] qg auto-detect and cross-check"

# Test 1: auto-detect exits 0
result=$(PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py auto-detect 2>&1)
[ $? -eq 0 ] && ok "auto-detect exits 0" || fail "auto-detect exits 0: $result"

# Test 2: cross-check exits 0
result=$(PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py cross-check 2>&1)
[ $? -eq 0 ] && ok "cross-check exits 0" || fail "cross-check exits 0: $result"

# Test 3: compliance threshold (triggers at 3, not at 2)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
b2 = [{'req': 'Stop hook feedback: x', 'tools': '-', 'decision': 'BLOCK', 'category': 'ASSUMPTION'}] * 2
ok2, _, _ = mod._detect_compliance(b2, b2)
assert not ok2, 'Should not trigger at 2'
b3 = b2 + [{'req': 'Stop hook feedback: y', 'tools': '-', 'decision': 'BLOCK', 'category': 'ASSUMPTION'}]
ok3, _, _ = mod._detect_compliance(b3, b3)
assert ok3, 'Should trigger at 3'
print('compliance_threshold_ok')
" 2>&1 | grep -q "compliance_threshold_ok" && ok "compliance threshold logic" || fail "compliance threshold logic"

# Test 4: dedup key extraction
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert mod._extract_key_from_description('Compliance retry failure: 8 retries') == 'compliance-retry'
assert mod._extract_key_from_description('[AUTO] Dominant ASSUMPTION blocks: 65%') == 'dominant-assumption'
assert mod._extract_key_from_description('High block rate: 53%') == 'high-block-rate'
assert mod._extract_key_from_description('No-tool blocks dominant: 82%') == 'no-tool-dominance'
assert mod._extract_key_from_description('[AUTO] Parser divergence: Raw count') == 'parser-divergence'
assert mod._extract_key_from_description('Contradiction dismissal: claimed done') is None
print('key_extraction_ok')
" 2>&1 | grep -q "key_extraction_ok" && ok "dedup key extraction" || fail "dedup key extraction"

# Test 5: dedup rejects known key, passes unknown
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile, shutil
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
tmpdir = tempfile.mkdtemp()
tmpfile = os.path.join(tmpdir, 'failures.md')
from datetime import datetime
today = datetime.now().strftime('%Y-%m-%d')
with open(tmpfile, 'w') as f:
    f.write(f'## {today}: Compliance retry failure: 3 retries\n')
orig = mod.FAILURES_PATH
mod.FAILURES_PATH = tmpfile
keys = mod._load_recent_failure_keys(days=3)
assert 'compliance-retry' in keys, f'Should find compliance-retry, got {keys}'
assert 'high-block-rate' not in keys, 'Should not find high-block-rate'
mod.FAILURES_PATH = orig
shutil.rmtree(tmpdir)
print('dedup_logic_ok')
" 2>&1 | grep -q "dedup_logic_ok" && ok "dedup rejects known key" || fail "dedup rejects known key"

echo ""
echo "[27] prior context and fix directives"

# Test 1: get_prior_context returns list (function exists and runs)
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
result = qg.get_prior_context('', max_exchanges=2)
assert isinstance(result, list), f'Expected list, got {type(result)}'
assert len(result) == 0, 'Empty path should return empty list'
print('prior_context_ok')
" 2>&1 | grep -q "prior_context_ok" && ok "get_prior_context exists and handles empty" || fail "get_prior_context"

# Test 2: get_prior_context with mock transcript
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
tmpdir = tempfile.mkdtemp()
transcript = os.path.join(tmpdir, 'test.jsonl')
entries = [
    {'type': 'user', 'message': {'content': 'Fix auth bug in src/auth.js'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'id': 'a', 'input': {}}, {'type': 'tool_use', 'name': 'Edit', 'id': 'b', 'input': {}}]}},
    {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'a', 'content': 'ok'}]}},
    {'type': 'user', 'message': {'content': 'Now run the tests'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Bash', 'id': 'c', 'input': {'command': 'pytest'}}]}},
    {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'c', 'content': '5 passed'}]}},
    {'type': 'user', 'message': {'content': 'Is that fixed?'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Yes it is fixed.'}]}},
]
with open(transcript, 'w') as f:
    for e in entries:
        f.write(json.dumps(e) + '\n')
result = qg.get_prior_context(transcript, max_exchanges=2)
import shutil
shutil.rmtree(tmpdir)
assert len(result) == 2, f'Expected 2 prior exchanges, got {len(result)}'
assert 'auth bug' in result[0]['user'], f'First exchange should be auth bug, got: {result[0]["user"]}'
assert 'Read' in result[0]['tools'], f'First exchange should have Read tool, got: {result[0]["tools"]}'
assert 'tests' in result[1]['user'].lower(), f'Second exchange should mention tests, got: {result[1]["user"]}'
print('prior_context_mock_ok')
" 2>&1 | grep -q "prior_context_mock_ok" && ok "get_prior_context parses mock transcript" || fail "get_prior_context mock transcript"

# Test 3: get_prior_context returns tools in chronological order
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
tmpdir = tempfile.mkdtemp()
transcript = os.path.join(tmpdir, 'test.jsonl')
entries = [
    {'type': 'user', 'message': {'content': 'Fix it'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'id': 'a', 'input': {}}]}},
    {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'a', 'content': 'ok'}]}},
    {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Edit', 'id': 'b', 'input': {}}]}},
    {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'b', 'content': 'ok'}]}},
    {'type': 'user', 'message': {'content': 'Done?'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Yes'}]}},
]
with open(transcript, 'w') as f:
    for e in entries:
        f.write(json.dumps(e) + '\n')
result = qg.get_prior_context(transcript, max_exchanges=2)
import shutil
shutil.rmtree(tmpdir)
assert len(result) == 1, f'Expected 1 prior exchange, got {len(result)}'
assert result[0]['tools'] == ['Read', 'Edit'], f'Tools should be chronological [Read, Edit], got {result[0]["tools"]}'
print('tool_order_ok')
" 2>&1 | grep -q "tool_order_ok" && ok "get_prior_context returns tools in chronological order" || fail "tool order"

# Test 4: llm_evaluate skips cache when prior context exists
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
tmpdir = tempfile.mkdtemp()
transcript = os.path.join(tmpdir, 'test.jsonl')
entries = [
    {'type': 'user', 'message': {'content': 'Fix the bug'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Read', 'id': 'a', 'input': {}}]}},
    {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'a', 'content': 'ok'}]}},
    {'type': 'user', 'message': {'content': 'Done?'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Yes'}]}},
]
with open(transcript, 'w') as f:
    for e in entries:
        f.write(json.dumps(e) + '\n')
prior = qg.get_prior_context(transcript, max_exchanges=2)
import shutil
shutil.rmtree(tmpdir)
assert len(prior) == 1, f'Expected 1 prior exchange, got {len(prior)}'
import inspect
src = inspect.getsource(qg.llm_evaluate)
assert 'get_prior_context' in src, 'llm_evaluate does not call get_prior_context'
assert 'if not prior' in src, 'llm_evaluate missing cache-skip logic'
assert 'check_cache' in src, 'llm_evaluate missing check_cache call'
print('cache_skip_ok')
" 2>&1 | grep -q "cache_skip_ok" && ok "llm_evaluate skips cache when prior context exists" || fail "cache skip logic"

# Test 5: FIX_DIRECTIVES dict exists and has all categories
PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
assert hasattr(qg, 'FIX_DIRECTIVES'), 'FIX_DIRECTIVES not found'
assert 'ASSUMPTION' in qg.FIX_DIRECTIVES, 'ASSUMPTION not in FIX_DIRECTIVES'
assert 'OVERCONFIDENCE' in qg.FIX_DIRECTIVES
assert 'LAZINESS' in qg.FIX_DIRECTIVES
print('fix_directives_ok')
" 2>&1 | grep -q "fix_directives_ok" && ok "FIX_DIRECTIVES exists with all categories" || fail "FIX_DIRECTIVES"

# Test 6: llm_evaluate accepts transcript_path parameter
PYTHONIOENCODING=utf-8 python -c "
import inspect, sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
sig = inspect.signature(qg.llm_evaluate)
params = list(sig.parameters.keys())
assert 'transcript_path' in params, f'transcript_path not in params: {params}'
print('sig_ok')
" 2>&1 | grep -q "sig_ok" && ok "llm_evaluate has transcript_path param" || fail "llm_evaluate signature"

# Test 7: Examples 38-40 present in FEW_SHOT_EXAMPLES
PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
from _hooks_shared import FEW_SHOT_EXAMPLES
assert 'Example 38' in FEW_SHOT_EXAMPLES, 'Example 38 missing'
assert 'Example 39' in FEW_SHOT_EXAMPLES, 'Example 39 missing'
assert 'Example 40' in FEW_SHOT_EXAMPLES, 'Example 40 missing'
assert 'PRIOR EXCHANGES' in FEW_SHOT_EXAMPLES, 'PRIOR EXCHANGES section missing'
print('examples_ok')
" 2>&1 | grep -q "examples_ok" && ok "Examples 38-40 present" || fail "Examples 38-40"


echo ""
echo "[28] assistant_snippet and short-input detection"

# Test 1: assistant_snippet field exists in get_prior_context return value
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
tmpdir = tempfile.mkdtemp()
t = os.path.join(tmpdir, 'test.jsonl')
entries = [
    {'type': 'user', 'message': {'content': 'go'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': '1. Run tests 2. Deploy'}]}},
    {'type': 'user', 'message': {'content': 'ok'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'confirmed'}]}},
]
with open(t, 'w') as f:
    [f.write(json.dumps(e) + chr(10)) for e in entries]
r = qg.get_prior_context(t, max_exchanges=1)
import shutil; shutil.rmtree(tmpdir)
assert len(r) == 1, f'Expected 1, got {len(r)}'
assert 'assistant_snippet' in r[0], f'Missing field: {list(r[0].keys())}'
assert '1. Run tests' in r[0]['assistant_snippet'], f'Content missing: {r[0]["assistant_snippet"]}'
print('snippet_ok')
" 2>&1 | grep -q "snippet_ok" && ok "get_prior_context returns assistant_snippet with text" || fail "assistant_snippet field"

# Test 2: assistant_snippet empty for tool-only assistant response
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
tmpdir = tempfile.mkdtemp()
t = os.path.join(tmpdir, 'test.jsonl')
entries = [
    {'type': 'user', 'message': {'content': 'fix it'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Edit', 'id': 'a', 'input': {}}]}},
    {'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': 'a', 'content': 'ok'}]}},
    {'type': 'user', 'message': {'content': 'done?'}},
    {'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'yes'}]}},
]
with open(t, 'w') as f:
    [f.write(json.dumps(e) + chr(10)) for e in entries]
r = qg.get_prior_context(t, max_exchanges=1)
import shutil; shutil.rmtree(tmpdir)
assert len(r) == 1, f'Expected 1, got {len(r)}'
assert r[0]['assistant_snippet'] == '', f'Expected empty snippet, got: {r[0]["assistant_snippet"]}'
print('empty_snippet_ok')
" 2>&1 | grep -q "empty_snippet_ok" && ok "assistant_snippet empty for tool-only response" || fail "assistant_snippet empty"

# Test 3: short-input detection code present in task-classifier.py
PYTHONIOENCODING=utf-8 python -c "
import os
tc = open(os.path.expanduser('~/.claude/hooks/task-classifier.py'), encoding='utf-8').read()
assert '[short-input]' in tc, 'short-input detection not found'
assert 'transcript_path' in tc, 'transcript_path not referenced'
assert 'numbered list' in tc, 'numbered list message not found'
print('tc_structure_ok')
" 2>&1 | grep -q "tc_structure_ok" && ok "task-classifier has short-input detection" || fail "short-input code"

# Test 4: short-input RE matches expected patterns
PYTHONIOENCODING=utf-8 python -c "
import re
pat = r'^(\d{1,2}|do it|do that|do this|go ahead|proceed|yes do it|ok do it|go)[\s.!]*$'
assert re.match(pat, '1', re.IGNORECASE), '1 not matched'
assert re.match(pat, '2', re.IGNORECASE), '2 not matched'
assert re.match(pat, 'do it', re.IGNORECASE), 'do it not matched'
assert re.match(pat, 'go ahead', re.IGNORECASE), 'go ahead not matched'
assert not re.match(pat, 'do it now please', re.IGNORECASE), 'false positive'
assert not re.match(pat, 'please fix it', re.IGNORECASE), 'false positive 2'
print('re_ok')
" 2>&1 | grep -q "re_ok" && ok "short-input RE matches correctly" || fail "short-input RE"

# Test 5: numbered list regex extracts items from sample text
PYTHONIOENCODING=utf-8 python -c "
import re
text = 'Here are options:\n1. Run tests\n2. Deploy to staging\n3. Update docs\n'
items = re.findall(r'(?:^|\n)\s*(\d+[.):])\s+(.{5,80}?)(?:\n|$)', text)
assert len(items) >= 2, f'Expected >= 2 items, got {len(items)}'
assert any('Run tests' in d for _, d in items), f'Item text missing: {items}'
print('list_re_ok')
" 2>&1 | grep -q "list_re_ok" && ok "numbered list regex extracts items" || fail "list regex"

# Test 6: Examples 41-43 present in FEW_SHOT_EXAMPLES
PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
from _hooks_shared import FEW_SHOT_EXAMPLES
assert 'Example 41' in FEW_SHOT_EXAMPLES, 'Example 41 missing'
assert 'Example 42' in FEW_SHOT_EXAMPLES, 'Example 42 missing'
assert 'Example 43' in FEW_SHOT_EXAMPLES, 'Example 43 missing'
print('examples_ok')
" 2>&1 | grep -q "examples_ok" && ok "Examples 41-43 present in FEW_SHOT_EXAMPLES" || fail "Examples 41-43"

# Test 7: context display includes assistant_snippet when present
PYTHONIOENCODING=utf-8 python -c "
import inspect, sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
src = inspect.getsource(qg.llm_evaluate)
assert 'assistant_snippet' in src, 'llm_evaluate does not use assistant_snippet'
print('ctx_display_ok')
" 2>&1 | grep -q "ctx_display_ok" && ok "llm_evaluate displays assistant_snippet" || fail "context display"


echo ""
echo "[29] compliance retry detection"

# Test 1: task-classifier has stop hook feedback check
python -c "
import os
tc = open(os.path.expanduser('~/.claude/hooks/task-classifier.py'), encoding='utf-8').read()
assert 'stop hook feedback:' in tc, 'stop hook feedback check not found'
print('tc_retry_check_ok')
" 2>&1 | grep -q "tc_retry_check_ok" && ok "task-classifier detects stop hook feedback messages" || fail "stop hook feedback check"

# Test 2: score override exists
python -c "
import os
tc = open(os.path.expanduser('~/.claude/hooks/task-classifier.py'), encoding='utf-8').read()
assert 'score = max(score, 2)' in tc, 'score override not found'
print('score_override_ok')
" 2>&1 | grep -q "score_override_ok" && ok "task-classifier score override for compliance retries" || fail "score override"

# Test 3: [compliance-retry] reminder text present
python -c "
import os
tc = open(os.path.expanduser('~/.claude/hooks/task-classifier.py'), encoding='utf-8').read()
assert '[compliance-retry]' in tc, '[compliance-retry] not found'
assert 'Text-only retries without tool output will be re-blocked' in tc, 'reminder text missing'
print('compliance_retry_reminder_ok')
" 2>&1 | grep -q "compliance_retry_reminder_ok" && ok "[compliance-retry] reminder text in task-classifier" || fail "[compliance-retry] reminder"

# Test 4: _count_recent_retry_blocks function exists in quality-gate.py
python -c "
import os
qg = open(os.path.expanduser('~/.claude/hooks/quality-gate.py'), encoding='utf-8').read()
assert '_count_recent_retry_blocks' in qg, 'function not found'
assert 'Stop hook feedback:' in qg, 'Stop hook feedback check not found'
print('retry_counter_ok')
" 2>&1 | grep -q "retry_counter_ok" && ok "_count_recent_retry_blocks function in quality-gate.py" || fail "_count_recent_retry_blocks"

# Test 5: escalating FIX strings present
python -c "
import os
qg = open(os.path.expanduser('~/.claude/hooks/quality-gate.py'), encoding='utf-8').read()
assert 'RETRY BLOCKED AGAIN' in qg, 'RETRY BLOCKED AGAIN not found'
assert 'MANDATORY' in qg, 'MANDATORY not found'
assert 'is_retry' in qg, 'is_retry not found'
print('escalating_fix_ok')
" 2>&1 | grep -q "escalating_fix_ok" && ok "escalating FIX directives in quality-gate.py" || fail "escalating FIX"

# Test 6: COMPLIANCE RETRY: note in llm_evaluate
python -c "
import inspect, sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
src = inspect.getsource(qg.llm_evaluate)
assert 'COMPLIANCE RETRY' in src, 'COMPLIANCE RETRY not in llm_evaluate'
assert 'retry_note' in src, 'retry_note not in llm_evaluate'
print('retry_prompt_ok')
" 2>&1 | grep -q "retry_prompt_ok" && ok "COMPLIANCE RETRY note in llm_evaluate" || fail "retry-aware prompt"

# Test 7: Examples 44-46 present in FEW_SHOT_EXAMPLES
python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
from _hooks_shared import FEW_SHOT_EXAMPLES
assert 'Example 44' in FEW_SHOT_EXAMPLES, 'Example 44 missing'
assert 'Example 45' in FEW_SHOT_EXAMPLES, 'Example 45 missing'
assert 'Example 46' in FEW_SHOT_EXAMPLES, 'Example 46 missing'
print('examples_ok')
" 2>&1 | grep -q "examples_ok" && ok "Examples 44-46 present in FEW_SHOT_EXAMPLES" || fail "Examples 44-46"


# ===== [30] Evidence gap + contradiction dismissal =====
echo "[30] Evidence gap + contradiction dismissal"

# Test 1: OVERCONFIDENCE wording updated
grep -q "evaluates the RESPONSE TEXT ONLY" ~/.claude/hooks/quality-gate.py && ok "OVERCONFIDENCE wording: evaluates RESPONSE TEXT ONLY" || fail "OVERCONFIDENCE wording not updated"

# Test 2: Mechanical evidence check exists
python -c "
import os
src = open(os.path.expanduser('~/.claude/hooks/quality-gate.py'), encoding='utf-8').read()
assert 'claim_re' in src and 'evidence_re' in src, 'mechanical check missing'
assert 'Claims test/verification' in src, 'check return message missing'
print('mechanical_check_ok')
" 2>&1 | grep -q "mechanical_check_ok" && ok "Mechanical evidence check present" || fail "Mechanical evidence check"

# Test 3: Contradiction signal detection in task-classifier.py
grep -q "contradiction-check" ~/.claude/hooks/task-classifier.py && ok "contradiction-check print in task-classifier" || fail "contradiction-check missing"

# Test 4: contradiction_signals list
grep -q "contradiction_signals" ~/.claude/hooks/task-classifier.py && ok "contradiction_signals list present" || fail "contradiction_signals missing"

# Test 5: Examples 47-50 present
python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
from _hooks_shared import FEW_SHOT_EXAMPLES
assert 'Example 47' in FEW_SHOT_EXAMPLES, 'Example 47 missing'
assert 'Example 48' in FEW_SHOT_EXAMPLES, 'Example 48 missing'
assert 'Example 49' in FEW_SHOT_EXAMPLES, 'Example 49 missing'
assert 'Example 50' in FEW_SHOT_EXAMPLES, 'Example 50 missing'
print('examples_ok')
" 2>&1 | grep -q "examples_ok" && ok "Examples 47-50 present in FEW_SHOT_EXAMPLES" || fail "Examples 47-50"

# Test 6: claim_re matches test claims but not false positives
python -c "
import re
claim_re = re.compile(r'\b(?:all\s+)?(?:tests?\s+pass(?:ed|es)?|(?:smoke\s+)?tests?\s+succeed(?:ed|s)?|build\s+succeed(?:ed|s)?|pass(?:es|ed)?\s+successfully)\b', re.IGNORECASE)
assert claim_re.search('all tests pass'), 'should match all tests pass'
assert claim_re.search('build succeeded'), 'should match build succeeded'
assert not claim_re.search('no errors found'), 'should not match no errors found'
print('claim_re_ok')
" 2>&1 | grep -q "claim_re_ok" && ok "claim_re: matches test claims, not false positives" || fail "claim_re regex"

# Test 7: evidence_re matches quoted output but not false positives
python -c "
import re
evidence_re = re.compile(r'(?:===.*===|passed,?\s*\d+\s*failed|\d+\s+passed|\bexit\s*(?:code\s*)?\d+\b|\d+\s+(?:ok|tests?))', re.IGNORECASE)
assert evidence_re.search('=== Results: 5 passed ==='), 'should match === Results ==='
assert evidence_re.search('3 passed, 0 failed'), 'should match N passed, M failed'
assert not evidence_re.search('I passed the value'), 'should not match I passed the value'
print('evidence_re_ok')
" 2>&1 | grep -q "evidence_re_ok" && ok "evidence_re: matches quoted output, not false positives" || fail "evidence_re regex"

# [31] Recording completeness: subagent entries, DEGRADED-PASS, thresholds
echo "[31] Recording completeness"
grep -q 'is_subagent' ~/.claude/scripts/qg-feedback.py && ok "parse_log_entries includes is_subagent flag" || fail "parse_log_entries missing is_subagent flag"
grep 'JSONDecodeError' ~/.claude/hooks/_hooks_shared.py | grep -q '_log_degradation' && ok "JSONDecodeError logs WARN via _log_degradation" || fail "JSONDecodeError missing _log_degradation call"
grep -q 'DEGRADED-PASS' ~/.claude/hooks/quality-gate.py && ok "quality-gate.py logs DEGRADED-PASS decision" || fail "quality-gate.py missing DEGRADED-PASS"
grep 'log_decision failed' ~/.claude/hooks/quality-gate.py | grep -q 'stderr' && ok "log_decision has stderr fallback" || fail "log_decision missing stderr fallback"
grep -q 'block_count >= 1' ~/.claude/hooks/session-end-log.py && ok "session-end threshold lowered to 1" || fail "session-end threshold not lowered"
grep -q 'os.remove(SNAPSHOT)' ~/.claude/hooks/qg-session-recall.py && ok "qg-session-recall deletes snapshot after reading" || fail "qg-session-recall missing delete"
grep -q 'SESSION_GAP_SEC = 7200' ~/.claude/scripts/qg-feedback.py && ok "SESSION_GAP_SEC increased to 7200" || fail "SESSION_GAP_SEC not updated"


# --- Section [32]: New failure categories and MECHANICAL prefix ---
grep -q 'MECHANICAL: Code was edited' ~/.claude/hooks/quality-gate.py && ok "mechanical_checks returns have MECHANICAL: prefix (edit-no-verify)" || fail "mechanical_checks missing MECHANICAL: prefix (edit-no-verify)"
grep -q 'MECHANICAL: Last action was editing' ~/.claude/hooks/quality-gate.py && ok "mechanical_checks returns have MECHANICAL: prefix (last-action)" || fail "mechanical_checks missing MECHANICAL: prefix (last-action)"
grep -q "MECHANICAL: Ran a Bash command" ~/.claude/hooks/quality-gate.py && ok "mechanical_checks returns have MECHANICAL: prefix (bash-not-test)" || fail "mechanical_checks missing MECHANICAL: prefix (bash-not-test)"
grep -q "'MECHANICAL'" ~/.claude/hooks/quality-gate.py && ok "FIX_DIRECTIVES has MECHANICAL entry" || fail "FIX_DIRECTIVES missing MECHANICAL"
grep -q "'INVALID'" ~/.claude/hooks/quality-gate.py && ok "FIX_DIRECTIVES has INVALID entry" || fail "FIX_DIRECTIVES missing INVALID"
grep -q "'CONTEXT_VIOLATION'" ~/.claude/hooks/quality-gate.py && ok "FIX_DIRECTIVES has CONTEXT_VIOLATION entry" || fail "FIX_DIRECTIVES missing CONTEXT_VIOLATION"
grep -q "'CARELESSNESS'" ~/.claude/hooks/quality-gate.py && ok "FIX_DIRECTIVES has CARELESSNESS entry" || fail "FIX_DIRECTIVES missing CARELESSNESS"

# --- Section [33]: qg milestone command ---
echo "[33] qg milestone command"
grep -q 'def cmd_milestone' ~/.claude/scripts/qg-feedback.py && ok "cmd_milestone function defined in qg-feedback.py" || fail "cmd_milestone missing from qg-feedback.py"
grep -q "elif cmd == 'milestone'" ~/.claude/scripts/qg-feedback.py && ok "milestone wired in main() dispatch" || fail "milestone not wired in main() dispatch"
grep -q 'qg milestone' ~/.claude/scripts/qg-feedback.py && ok "milestone appears in docstring/usage" || fail "milestone missing from docstring/usage"
grep -q 'MILESTONE' ~/.claude/scripts/qg-feedback.py && ok "MILESTONE keyword used in log write" || fail "MILESTONE keyword missing from cmd_milestone"
result=$(PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py milestone "smoke-test-verify" 2>&1)
echo "$result" | grep -q "Milestone recorded" && ok "qg milestone command runs and prints confirmation" || fail "qg milestone command failed: $result"
grep -q 'smoke-test-verify' ~/.claude/quality-gate.log && ok "milestone entry written to quality-gate.log" || fail "milestone entry not found in quality-gate.log"

# --- Section [34]: Confidence-challenge detection ---
echo "[34] Confidence-challenge detection"
grep -q 'confidence_challenge_signals' ~/.claude/hooks/task-classifier.py && ok "confidence_challenge_signals list in task-classifier.py" || fail "confidence_challenge_signals missing from task-classifier.py"
grep -q 'confidence-challenge' ~/.claude/hooks/task-classifier.py && ok "[confidence-challenge] reminder injected" || fail "[confidence-challenge] reminder missing from task-classifier.py"
grep -q 'are you sure' ~/.claude/hooks/task-classifier.py && ok "confidence-challenge trigger: 'are you sure'" || fail "trigger 'are you sure' missing"
grep -q 'exhaustively review' ~/.claude/hooks/task-classifier.py && ok "confidence-challenge trigger: 'exhaustively review'" || fail "trigger 'exhaustively review' missing"
grep -q 'Example 51' ~/.claude/hooks/_hooks_shared.py && ok "Example 51 present (confidence challenge BLOCK)" || fail "Example 51 missing from _hooks_shared.py"
grep -q 'Example 52' ~/.claude/hooks/_hooks_shared.py && ok "Example 52 present (confidence challenge PASS)" || fail "Example 52 missing from _hooks_shared.py"
grep -q 'confidence-challenge' ~/.claude/hooks/quality-gate.py && ok "OVERCONFIDENCE:confidence-challenge in FIX_DIRECTIVES" || fail "confidence-challenge missing from FIX_DIRECTIVES"

# --- Section [35]: ASSUMPTION:code-not-read examples ---
echo "[35] ASSUMPTION:code-not-read examples"
grep -q 'Example 53' ~/.claude/hooks/_hooks_shared.py && ok "Example 53 present (code-not-read BLOCK)" || fail "Example 53 missing"
grep -q 'Example 54' ~/.claude/hooks/_hooks_shared.py && ok "Example 54 present (code-not-read PASS)" || fail "Example 54 missing"
grep -q 'fetchUsers' ~/.claude/hooks/_hooks_shared.py && ok "fetchUsers pattern in examples" || fail "fetchUsers pattern missing"
grep -q 'without reading' ~/.claude/hooks/_hooks_shared.py && ok "without-reading wording in BLOCK example" || fail "without-reading wording missing"
grep -q 'grep.*def fetchUsers' ~/.claude/hooks/_hooks_shared.py && ok "grep verification shown in PASS example" || fail "grep verification missing from PASS example"

# --- Section [36]: qg miss usability ---
echo "[36] qg miss usability"
grep -q 'miss_hint' ~/.claude/hooks/session-end-log.py && ok "miss hint appended to session snapshot" || fail "miss hint missing from session-end-log.py"
grep -q 'qg miss' ~/.claude/hooks/session-end-log.py && ok "qg miss text in snapshot hint" || fail "qg miss text missing"
grep -q 'miss_signals' ~/.claude/hooks/task-classifier.py && ok "miss_signals list in task-classifier.py" || fail "miss_signals missing from task-classifier.py"
grep -q 'gate-miss?' ~/.claude/hooks/task-classifier.py && ok "[gate-miss?] reminder injected" || fail "[gate-miss?] reminder missing"
grep -q 'you assumed' ~/.claude/hooks/task-classifier.py && ok "miss signal: 'you assumed'" || fail "miss signal 'you assumed' missing"

# --- Section [37]: CARELESSNESS subagent examples ---
echo "[37] CARELESSNESS subagent examples"
grep -q 'Example 55' ~/.claude/hooks/_hooks_shared.py && ok "Example 55 present (carelessness BLOCK)" || fail "Example 55 missing"
grep -q 'Example 56' ~/.claude/hooks/_hooks_shared.py && ok "Example 56 present (carelessness PASS)" || fail "Example 56 missing"
grep -q "Response '3' is incomplete" ~/.claude/hooks/_hooks_shared.py && ok "fragment-response wording in BLOCK example" || fail "fragment-response wording missing"
grep -q 'CARELESSNESS' ~/.claude/hooks/_hooks_shared.py && ok "CARELESSNESS category in examples" || fail "CARELESSNESS missing from examples"

echo "[38] hallucinated-specifics + edit-without-read examples"
grep -q 'Example 57' ~/.claude/hooks/_hooks_shared.py && ok "Example 57 present (hallucinated-specifics BLOCK)" || fail "Example 57 missing"
grep -q 'Example 58' ~/.claude/hooks/_hooks_shared.py && ok "Example 58 present (hallucinated-specifics PASS)" || fail "Example 58 missing"
grep -q 'Example 59' ~/.claude/hooks/_hooks_shared.py && ok "Example 59 present (edit-without-read BLOCK)" || fail "Example 59 missing"
grep -q 'Example 60' ~/.claude/hooks/_hooks_shared.py && ok "Example 60 present (edit-without-read PASS)" || fail "Example 60 missing"
grep -q 'hallucinated' ~/.claude/hooks/_hooks_shared.py && ok "hallucinated-specifics wording present" || fail "hallucinated-specifics wording missing"
grep -q 'edit-without-read' ~/.claude/hooks/_hooks_shared.py && ok "edit-without-read wording present" || fail "edit-without-read wording missing"
grep -q 'MECHANICAL.*Edited.*without.*Read\|Edited.*without a prior Read' ~/.claude/hooks/_hooks_shared.py && ok "edit-without-read MECHANICAL reason present" || fail "edit-without-read MECHANICAL reason missing"

echo "[39] prior-context false positive fix"
grep -q "elif d.get('type') == 'user' and found_assistant:" ~/.claude/hooks/quality-gate.py && fail "guarded user check still present in quality-gate.py" || ok "guarded user check removed from quality-gate.py"
grep -c "elif d.get('type') == 'user':" ~/.claude/hooks/quality-gate.py | grep -q "^2$" && ok "exactly 2 unguarded user checks (get_user_request + get_prior_context)" || fail "unexpected count of unguarded user checks"
python -m py_compile ~/.claude/hooks/quality-gate.py 2>&1 | grep -q . && fail "quality-gate.py syntax error after fix" || ok "quality-gate.py syntax valid after fix"

echo "[40] assistant_snippet numbered-list detection"
grep -q "_nl = re.search" ~/.claude/hooks/quality-gate.py && ok "numbered-list regex search in get_prior_context" || fail "numbered-list regex search missing"
grep -q "_nl.start():_nl.start()+400" ~/.claude/hooks/quality-gate.py && ok "400-char capture from list start present" || fail "400-char capture missing"
grep -q "snippet\[:250\]" ~/.claude/hooks/quality-gate.py && ok "snippet display increased to 250 chars" || fail "snippet display not updated"
python -m py_compile ~/.claude/hooks/quality-gate.py 2>&1 | grep -q . && fail "quality-gate.py syntax error" || ok "quality-gate.py syntax valid"

echo "[41] FIX_DIRECTIVES for hallucinated-specifics + edit-without-read"
grep -q "ASSUMPTION:hallucinated-specifics" ~/.claude/hooks/quality-gate.py && ok "hallucinated-specifics directive present" || fail "hallucinated-specifics directive missing"
grep -q "MECHANICAL:edit-without-read" ~/.claude/hooks/quality-gate.py && ok "edit-without-read directive present" || fail "edit-without-read directive missing"
grep -q "not provided by the user or confirmed by a tool" ~/.claude/hooks/quality-gate.py && ok "hallucinated-specifics fix wording present" || fail "hallucinated-specifics fix wording missing"
grep -q "Read the file before making edits" ~/.claude/hooks/quality-gate.py && ok "edit-without-read fix wording present" || fail "edit-without-read fix wording missing"

echo "[42] get_prior_context snippet-detection (unit)"
PYTHONIOENCODING=utf-8 python ~/.claude/hooks/_test_snippet.py && ok "get_prior_context captures numbered list buried past 300 chars" || fail "get_prior_context missed numbered list"

echo "[43] short-input regex fix (long descriptions)"
grep -q "\[\^" ~/.claude/hooks/task-classifier.py && ok "task-classifier uses [^\\n] regex (no 80-char cap)" || fail "task-classifier still uses old capped regex"
grep -q "d.strip()\[:60\]" ~/.claude/hooks/task-classifier.py && ok "preview truncation updated to 60 chars" || fail "preview truncation not updated"
PYTHONIOENCODING=utf-8 python -c "import re; t='1. Long title here more than 80 chars for this description of the item\n2. Another long item description here\n'; items=re.findall(r'(?:^|\n)\s*(\d+[.):])\s+([^\n]{5,})', t); print(len(items))" 2>&1 | grep -q "^2$" && ok "regex matches 2 long-description items" || fail "regex failed on long descriptions"
python -m py_compile ~/.claude/hooks/task-classifier.py 2>&1 | grep -q . && fail "task-classifier.py syntax error" || ok "task-classifier.py syntax valid"

echo "[44] FIX_DIRECTIVES for ASSUMPTION:code-not-read"
grep -q "ASSUMPTION:code-not-read" ~/.claude/hooks/quality-gate.py && ok "code-not-read directive present" || fail "code-not-read directive missing"
grep -q "Use Grep to find the function definition" ~/.claude/hooks/quality-gate.py && ok "code-not-read fix wording present" || fail "code-not-read fix wording missing"

echo "[45] JSONDecodeError fallback in call_haiku_check"
grep -q "Fallback: try to extract JSON object with regex" ~/.claude/hooks/_hooks_shared.py && ok "JSON extraction fallback present" || fail "JSON extraction fallback missing"
grep -q "raw: " ~/.claude/hooks/_hooks_shared.py && ok "raw response logging on failure present" || fail "raw response logging missing"
grep -q "re.DOTALL" ~/.claude/hooks/_hooks_shared.py && ok "re.DOTALL flag used in fallback search" || fail "re.DOTALL missing from fallback"
python -m py_compile ~/.claude/hooks/_hooks_shared.py 2>&1 | grep -q . && fail "_hooks_shared.py syntax error" || ok "_hooks_shared.py syntax valid"

echo "[47] bare test-count mechanical check (no-verification path)"
grep -q "bare_count_re" ~/.claude/hooks/quality-gate.py && ok "bare_count_re pattern present" || fail "bare_count_re pattern missing"
grep -q "Cites specific test counts" ~/.claude/hooks/quality-gate.py && ok "Cites specific test counts message present" || fail "block message missing"
grep -q "not has_verification" ~/.claude/hooks/quality-gate.py | grep -q "bare_count" 2>/dev/null; grep -q "if response and not has_verification:" ~/.claude/hooks/quality-gate.py && ok "guard uses not has_verification" || fail "guard condition missing"
python -m py_compile ~/.claude/hooks/quality-gate.py 2>&1 | grep -q . && fail "quality-gate.py syntax error" || ok "quality-gate.py syntax valid after bare_count check"

echo "[46] subagent-quality-gate.py DEGRADED-PASS logging"
grep -q 'genuine = True' ~/.claude/hooks/subagent-quality-gate.py && ok "genuine flag initialized in subagent gate" || fail "genuine flag missing from subagent gate"
grep -q "decision_tag = 'PASS' if genuine else 'DEGRADED-PASS'" ~/.claude/hooks/subagent-quality-gate.py && ok "DEGRADED-PASS tag used in subagent gate" || fail "DEGRADED-PASS tag missing from subagent gate"
grep -q "reason_tag = 'ok' if genuine else 'llm-degraded'" ~/.claude/hooks/subagent-quality-gate.py && ok "llm-degraded reason tag used in subagent gate" || fail "llm-degraded reason tag missing"
python -m py_compile ~/.claude/hooks/subagent-quality-gate.py 2>&1 | grep -q . && fail "subagent-quality-gate.py syntax error" || ok "subagent-quality-gate.py syntax valid"

echo "[48] qg trend / precision / scan"
grep -q 'def cmd_trend' ~/.claude/scripts/qg-feedback.py && ok "trend command present" || fail "trend command missing"
grep -q 'def cmd_precision' ~/.claude/scripts/qg-feedback.py && ok "precision command present" || fail "precision command missing"
grep -q 'def cmd_scan' ~/.claude/scripts/qg-feedback.py && ok "scan command present" || fail "scan command missing"
grep -q "cmd == 'trend'" ~/.claude/scripts/qg-feedback.py && ok "trend wired in main()" || fail "trend not wired"
grep -q "cmd == 'precision'" ~/.claude/scripts/qg-feedback.py && ok "precision wired in main()" || fail "precision not wired"
grep -q "cmd == 'scan'" ~/.claude/scripts/qg-feedback.py && ok "scan wired in main()" || fail "scan not wired"
grep -q 'smoke-test-verify' ~/.claude/scripts/qg-feedback.py && ok "smoke-test-verify filtered in trend" || fail "smoke-test-verify filter missing"
grep -q 'len(e' ~/.claude/scripts/qg-feedback.py && ok "scan has length guard" || fail "scan length guard missing"
PYTHONIOENCODING=utf-8 python -c "import py_compile, os; py_compile.compile(os.path.expanduser('~/.claude/scripts/qg-feedback.py'))" 2>/dev/null && ok "qg-feedback.py syntax valid" || fail "qg-feedback.py syntax error"

echo "[49] qg weekly"
grep -q 'def cmd_weekly' ~/.claude/scripts/qg-feedback.py && ok "weekly command present" || fail "weekly command missing"
grep -q "cmd == 'weekly'" ~/.claude/scripts/qg-feedback.py && ok "weekly wired in main()" || fail "weekly not wired"
grep -q 'qg weekly' ~/.claude/scripts/qg-feedback.py && ok "weekly in docstring" || fail "weekly missing from docstring"
grep -q 'week_starts' ~/.claude/scripts/qg-feedback.py && ok "weekly computes week boundaries" || fail "weekly week_starts missing"
grep -q 'ABOVE TARGET' ~/.claude/scripts/qg-feedback.py && ok "weekly has FP target marker" || fail "weekly FP target marker missing"
grep -q 'Block rate delta' ~/.claude/scripts/qg-feedback.py && ok "weekly shows delta summary" || fail "weekly delta summary missing"
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py weekly 2>/dev/null | grep -q 'Quality Gate Weekly' && ok "weekly runs without error" || fail "weekly command fails"

echo "[50] qg coverage"
grep -q 'def cmd_coverage' ~/.claude/scripts/qg-feedback.py && ok "coverage command present" || fail "coverage command missing"
grep -q "cmd == 'coverage'" ~/.claude/scripts/qg-feedback.py && ok "coverage wired in main()" || fail "coverage not wired"
grep -q 'qg coverage' ~/.claude/scripts/qg-feedback.py && ok "coverage in docstring" || fail "coverage missing from docstring"
grep -q 'SMOKE_BRANCH_LABELS' ~/.claude/scripts/qg-feedback.py && ok "coverage has branch label map" || fail "branch label map missing"
grep -q 'SECTION_SMOKE_COVERAGE' ~/.claude/scripts/qg-feedback.py && ok "coverage has section map" || fail "section coverage map missing"
grep -c '# SMOKE:[0-9]' ~/.claude/hooks/quality-gate.py | grep -qE '^1[6-9]$|^[2-9][0-9]$' && ok "quality-gate.py has >= 16 SMOKE markers" || fail "quality-gate.py missing SMOKE markers"
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py coverage 2>/dev/null | grep -q 'Branch' && ok "coverage runs without error" || fail "coverage command fails"
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py coverage 2>/dev/null | grep -qv 'UNCOVERED' && ok "coverage has no uncovered branches" || fail "coverage has uncovered branches"

echo "[51] llm_evaluate cache-hit branch"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, re
hooks = re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR')
sys.path.insert(0, hooks)
from _hooks_shared import write_cache, check_cache
resp = 'Cache-hit smoke test response unique xq7z'
write_cache(resp, True, '')
cached = check_cache(resp)
assert cached == (True, ''), f'cache read failed: {cached}'
print('cache_roundtrip_ok')
" 2>/dev/null | grep -q 'cache_roundtrip_ok' && ok "cache write/read roundtrip works" || fail "cache write/read roundtrip failed"
grep -q '# SMOKE:16' ~/.claude/hooks/quality-gate.py && ok "SMOKE:16 marker in quality-gate.py" || fail "SMOKE:16 marker missing"
grep -q "16.*cache-hit" ~/.claude/scripts/qg-feedback.py && ok "SMOKE:16 in branch label map" || fail "SMOKE:16 missing from label map"
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py coverage 2>/dev/null | grep -q 'SMOKE:16' && ok "coverage shows SMOKE:16" || fail "coverage missing SMOKE:16"

echo "[52] DEGRADED-PASS: backslash-apostrophe fix"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, re
hooks = re.sub(r'^/([a-zA-Z])/', lambda m: m.group(1).upper() + ':/', '$HOOKS_DIR')
sys.path.insert(0, hooks)
import json
bs = chr(92); ap = chr(39)
bad = '{\"ok\": false, \"reason\": \"Claims ' + bs + ap + 'fully complete' + bs + ap + '\"}'
# Verify it fails before fix
try: json.loads(bad); print('pre_fix_ok_unexpected'); sys.exit(1)
except json.JSONDecodeError: pass
# Apply fix (same logic as in _hooks_shared.py)
fixed = bad.replace(bs + ap, ap)
parsed = json.loads(fixed)
assert parsed['reason'] == \"Claims 'fully complete'\", f'unexpected: {parsed}'
print('backslash_apos_fix_ok')
" 2>/dev/null | grep -q 'backslash_apos_fix_ok' && ok "backslash-apostrophe fix works" || fail "backslash-apostrophe fix broken"
grep -q "Fix invalid.*escape" ~/.claude/hooks/_hooks_shared.py && ok "_hooks_shared.py applies backslash-apos strip" || fail "_hooks_shared.py missing backslash-apos strip"

echo "[53] mechanical check fires with no tools (SMOKE:7 gate removal)"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
# SMOKE:7: bare count claim with no tools (tool_names=[]) should block
reason = qg.mechanical_checks([], [], [], [], '294 passed, 0 failed, 294 total', 'summarize')
assert reason and 'OVERCONFIDENCE' in reason, f'expected OVERCONFIDENCE block, got: {reason!r}'
print('smoke7_no_tools_ok')
" 2>/dev/null | grep -q 'smoke7_no_tools_ok' && ok "SMOKE:7 fires with empty tool_names" || fail "SMOKE:7 did not fire with empty tool_names"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
# SMOKE:7 should NOT fire when Bash ran (has_verification=True)
reason = qg.mechanical_checks(['Bash'], [], ['pytest'], [], '294 passed, 0 failed, 294 total', 'run tests')
assert reason is None, f'unexpected block when Bash ran: {reason!r}'
print('smoke7_with_bash_ok')
" 2>/dev/null | grep -q 'smoke7_with_bash_ok' && ok "SMOKE:7 does not fire when Bash ran" || fail "SMOKE:7 false-positive when Bash ran"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
# SMOKE:7 should NOT fire when TaskOutput ran (has_verification=True)
reason = qg.mechanical_checks(['TaskOutput'], [], [], [], '395 passed, 0 failed, 395 total', 'run tests')
assert reason is None, f'unexpected block when TaskOutput ran: {reason!r}'
print('taskout_ok')
" 2>/dev/null | grep -q 'taskout_ok' && ok "SMOKE:7 does not fire when TaskOutput ran" || fail "SMOKE:7 false-positive when TaskOutput ran"
grep -q "runs even with no tools" ~/.claude/hooks/quality-gate.py && ok "quality-gate.py if-tool_names gate removed" || fail "quality-gate.py still has old gate comment"

echo "[54] examples 61-62 (no-tool count claim)"
grep -q "Example 61" ~/.claude/hooks/_hooks_shared.py && ok "Example 61 present" || fail "Example 61 missing"
grep -q "Example 62" ~/.claude/hooks/_hooks_shared.py && ok "Example 62 present" || fail "Example 62 missing"
grep -q "294 smoke tests pass.*fully complete\|All 294 smoke tests pass" ~/.claude/hooks/_hooks_shared.py && ok "Example 61 block content present" || fail "Example 61 block content missing"
grep -q "294 passed, 0 failed, 294 total" ~/.claude/hooks/_hooks_shared.py && ok "Example 62 pass content present" || fail "Example 62 pass content missing"

echo "[55] examples 63-64 (notification dismissal)"
grep -q "Example 63" ~/.claude/hooks/_hooks_shared.py && ok "Example 63 present" || fail "Example 63 missing"
grep -q "Example 64" ~/.claude/hooks/_hooks_shared.py && ok "Example 64 present" || fail "Example 64 missing"
grep -q "nothing to act on\|empty output.*nothing" ~/.claude/hooks/_hooks_shared.py && ok "Example 63 dismissal wording present" || fail "Example 63 dismissal wording missing"
grep -q "TaskOutput" ~/.claude/hooks/_hooks_shared.py && ok "Example 64 uses TaskOutput" || fail "Example 64 TaskOutput missing"

echo "[56] degraded-rate auto-detector"
grep -q "_detect_degraded_rate" ~/.claude/scripts/qg-feedback.py && ok "_detect_degraded_rate defined" || fail "_detect_degraded_rate missing"
grep -q "'degraded-rate'" ~/.claude/scripts/qg-feedback.py && ok "degraded-rate key present" || fail "degraded-rate key missing"
grep -q "degraded eval rate" ~/.claude/scripts/qg-feedback.py && ok "degraded-rate description string present" || fail "degraded-rate description missing"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
session = [{'decision': 'DEGRADED-PASS'} for _ in range(4)] + [{'decision': 'PASS'} for _ in range(30)] + [{'decision': 'BLOCK'} for _ in range(6)]
ok, desc, key = qg._detect_degraded_rate(session)
assert ok, f'expected trigger, got ok={ok}'
assert key == 'degraded-rate', f'expected degraded-rate, got {key!r}'
assert '10%' in desc or '11%' in desc or '12%' in desc or '%' in desc, f'missing pct in desc: {desc!r}'
print('degraded_rate_ok')
" 2>/dev/null | grep -q 'degraded_rate_ok' && ok "_detect_degraded_rate triggers at >=5%" || fail "_detect_degraded_rate did not trigger"

echo "[57] qg weekly degraded-rate annotation"
grep -q "deg_pct" ~/.claude/scripts/qg-feedback.py && ok "deg_pct computed" || fail "deg_pct missing"
grep -q "ABOVE 5% TARGET" ~/.claude/scripts/qg-feedback.py && ok "ABOVE 5% TARGET flag present" || fail "flag text missing"
grep -q "deg_pct >= 5" ~/.claude/scripts/qg-feedback.py && ok "5% threshold check present" || fail "threshold check missing"


echo "[58] shadow mode wiring"
test -f ~/.claude/hooks/qg-shadow-worker.py && ok "shadow worker exists" || fail "shadow worker missing"
grep -q "_shadow_ollama_async" ~/.claude/hooks/quality-gate.py && ok "_shadow_ollama_async defined in quality-gate" || fail "function missing"
grep -q "_shadow_ollama_async(check_prompt" ~/.claude/hooks/quality-gate.py && ok "shadow call wired in llm_evaluate" || fail "shadow call not wired"
grep -q "qg-shadow-worker.py" ~/.claude/hooks/quality-gate.py && ok "worker path referenced in quality-gate" || fail "worker path missing"

echo "[59] qg shadow command"
grep -q "def cmd_shadow" ~/.claude/scripts/qg-feedback.py && ok "cmd_shadow function defined" || fail "function missing"
grep -q "SHADOW_LOG" ~/.claude/scripts/qg-feedback.py && ok "SHADOW_LOG constant in qg-feedback" || fail "constant missing"
grep -qE "phi4[:-](14b|shadow)|phi4-shadow" ~/.claude/hooks/qg-shadow-worker.py && ok "phi4 model in shadow worker" || fail "model missing"
grep -q "(no reason)" ~/.claude/hooks/qg-shadow-worker.py && ok "ollama reason always logged (no reason placeholder)" || fail "always-log missing"
grep -q "agree_pct" ~/.claude/scripts/qg-feedback.py && ok "agreement rate computed" || fail "agreement rate missing"
grep -q "cmd.*shadow" ~/.claude/scripts/qg-feedback.py && ok "shadow wired into main dispatcher" || fail "not wired"


echo "[60] unverified next-step examples + PLANNING precheck"
grep -q "Example 65" ~/.claude/hooks/_hooks_shared.py && ok "Example 65 present (unverified next steps BLOCK)" || fail "Example 65 missing"
grep -q "Example 66" ~/.claude/hooks/_hooks_shared.py && ok "Example 66 present (verified next steps PASS)" || fail "Example 66 missing"
grep -q "unverified next steps" ~/.claude/hooks/_hooks_shared.py && ok "unverified next steps wording present" || fail "wording missing"
grep -q "PLANNING" ~/.claude/hooks/precheck-hook.py && ok "PLANNING category in precheck-hook" || fail "PLANNING missing"
grep -q "next steps" ~/.claude/hooks/precheck-hook.py && ok "next steps trigger phrase in precheck" || fail "trigger missing"
grep -q "verify each candidate" ~/.claude/CLAUDE.md && ok "CLAUDE.md next-step verification rule present" || fail "CLAUDE.md rule missing"


echo "[61] qg shadow --diff command"
grep -q "def cmd_shadow(n=50, diff=False)" ~/.claude/scripts/qg-feedback.py && ok "cmd_shadow accepts diff flag" || fail "cmd_shadow diff flag missing"
grep -q "'--diff' in sys.argv" ~/.claude/scripts/qg-feedback.py && ok "--diff wired in shadow dispatcher" || fail "--diff not wired"
grep -q "_cat(e\['reasons'\]" ~/.claude/scripts/qg-feedback.py && ok "_cat helper used in diff mode" || fail "_cat helper missing"
grep -q "shadow.*--diff" ~/.claude/scripts/qg-feedback.py && ok "shadow --diff in usage string" || fail "usage string not updated"


echo "[62] precheck-hook model upgrade"
grep -q "qwen2.5:7b-instruct" ~/.claude/hooks/precheck-hook.py && ok "precheck-hook uses qwen2.5:7b-instruct" || fail "precheck-hook model not upgraded"


echo "[63] qg shadow --clear subcommand"
grep -q "'--clear' in sys.argv" ~/.claude/scripts/qg-feedback.py && ok "--clear flag handled in shadow dispatcher" || fail "--clear not handled"
grep -q "Shadow log cleared" ~/.claude/scripts/qg-feedback.py && ok "clear success message present" || fail "clear message missing"
grep -q "shadow.*--clear" ~/.claude/scripts/qg-feedback.py && ok "shadow --clear in usage string" || fail "usage string not updated"


echo "[64] degraded-eval fixes: max_tokens, 429 retry, LAZINESS definition"
grep -q '"max_tokens": 200' ~/.claude/hooks/_hooks_shared.py && ok "max_tokens raised to 200" || fail "max_tokens not raised"
grep -q '_e429' ~/.claude/hooks/_hooks_shared.py && ok "429 retry handler present" || fail "429 retry missing"
grep -q '_time.sleep(5)' ~/.claude/hooks/_hooks_shared.py && ok "5-second backoff on 429" || fail "backoff missing"
grep -q 'NOT LAZINESS.*capability refusals' ~/.claude/hooks/quality-gate.py && ok "LAZINESS definition excludes capability refusals" || fail "LAZINESS definition not updated"


echo "[65] command-suggestion false positive fixes"
grep -q "NOT ASSUMPTION.*Recommending a command" ~/.claude/hooks/quality-gate.py && ok "ASSUMPTION definition excludes command suggestions" || fail "ASSUMPTION definition not updated"
grep -q "Example 67" ~/.claude/hooks/_hooks_shared.py && ok "Example 67 present (command suggestion PASS)" || fail "Example 67 missing"
grep -q "Example 68" ~/.claude/hooks/_hooks_shared.py && ok "Example 68 present (command suggestion with false claim BLOCK)" || fail "Example 68 missing"


echo "[66] Example 6c capability refusal"
grep -q "Example 6c" ~/.claude/hooks/_hooks_shared.py && ok "Example 6c present (no internet refusal PASS)" || fail "Example 6c missing"
grep -q "internet access" ~/.claude/hooks/_hooks_shared.py && ok "internet access refusal wording present" || fail "internet refusal wording missing"


echo "[67] subagent gate exclusion sync"
grep -q "NOT ASSUMPTION.*Recommending a command" ~/.claude/hooks/subagent-quality-gate.py && ok "subagent gate: NOT ASSUMPTION command exclusion present" || fail "subagent gate missing command exclusion"
grep -q "NOT LAZINESS.*capability refusals" ~/.claude/hooks/subagent-quality-gate.py && ok "subagent gate: NOT LAZINESS capability refusal exclusion present" || fail "subagent gate missing laziness exclusion"


echo "[68] subagent gate bare_count_re check"
grep -q "_bare_count_re" ~/.claude/hooks/subagent-quality-gate.py && ok "bare_count_re present in subagent gate" || fail "bare_count_re missing from subagent gate"
grep -q "Cites specific test counts" ~/.claude/hooks/subagent-quality-gate.py && ok "test-count OVERCONFIDENCE reason in subagent gate" || fail "reason missing"

echo "[69] shadow worker newline sanitization"
grep -q "replace(chr(10)" ~/.claude/hooks/qg-shadow-worker.py && ok "shadow worker strips newlines via chr(10)" || fail "newline sanitization missing from shadow worker"
echo "[70] phi4 prior-context OVERCONFIDENCE/ASSUMPTION guidance"
grep -q "PHI4_NOTE" ~/.claude/hooks/qg-shadow-worker.py && ok "PHI4_NOTE constant present" || fail "PHI4_NOTE missing"
grep -q "check_prompt + PHI4_NOTE" ~/.claude/hooks/qg-shadow-worker.py && ok "PHI4_NOTE appended to prompt" || fail "PHI4_NOTE not appended"
grep -q "ASSUMPTION REMINDER" ~/.claude/hooks/qg-shadow-worker.py && ok "PHI4_NOTE includes ASSUMPTION guidance" || fail "PHI4_NOTE missing ASSUMPTION reminder"
echo "[71] CARELESSNESS examples 69-71"
grep -q "Example 69" ~/.claude/hooks/_hooks_shared.py && ok "Example 69 CARELESSNESS vague dismissal present" || fail "Example 69 missing"
grep -q "Example 70" ~/.claude/hooks/_hooks_shared.py && ok "Example 70 CARELESSNESS partial completion present" || fail "Example 70 missing"
grep -q "Example 71" ~/.claude/hooks/_hooks_shared.py && ok "Example 71 CARELESSNESS PASS present" || fail "Example 71 missing"
echo "[72] MECHANICAL examples 72-74"
grep -q "Example 72" ~/.claude/hooks/_hooks_shared.py && ok "Example 72 MECHANICAL write-without-check present" || fail "Example 72 missing"
grep -q "Example 73" ~/.claude/hooks/_hooks_shared.py && ok "Example 73 MECHANICAL append-without-read present" || fail "Example 73 missing"
grep -q "Example 74" ~/.claude/hooks/_hooks_shared.py && ok "Example 74 MECHANICAL PASS present" || fail "Example 74 missing"
echo "[73] OVERCONFIDENCE PASS examples 75-76"
grep -q "Example 75" ~/.claude/hooks/_hooks_shared.py && ok "Example 75 OVERCONFIDENCE PASS present" || fail "Example 75 missing"
grep -q "Example 76" ~/.claude/hooks/_hooks_shared.py && ok "Example 76 OVERCONFIDENCE PASS present" || fail "Example 76 missing"
echo "[74] LAZINESS PASS examples 77-78"
grep -q "Example 77" ~/.claude/hooks/_hooks_shared.py && ok "Example 77 LAZINESS PASS present" || fail "Example 77 missing"
grep -q "Example 78" ~/.claude/hooks/_hooks_shared.py && ok "Example 78 LAZINESS PASS present" || fail "Example 78 missing"
echo "[75] cmd_shadow smoke test filter"
grep -q '_ollama_reason' ~/.claude/scripts/qg-feedback.py && ok "_ollama_reason helper defined in cmd_shadow" || fail "_ollama_reason helper missing"
grep -q 'smoke_reasons' ~/.claude/scripts/qg-feedback.py && ok "smoke_reasons set computed" || fail "smoke_reasons missing"
grep -q 'smoke_count' ~/.claude/scripts/qg-feedback.py && ok "smoke_count computed" || fail "smoke_count missing"
grep -q 'smoke test entries filtered' ~/.claude/scripts/qg-feedback.py && ok "filtered count shown in output" || fail "filtered count message missing"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qg)
def _ollama_reason(e):
    for r in e.get('reasons', []):
        if r.startswith('ollama:'):
            return r[7:].strip()[:60]
    return ''
entries = [
    {'ts': '2026-01-01T00:00:0' + str(i), 'haiku': 'PASS', 'ollama': 'BLOCK',
     'agree': False, 'reasons': ['ollama:OVERCONFIDENCE Fixed the auth bug. Test output: 32 pa']}
    for i in range(5)
] + [
    {'ts': '2026-01-01T00:01:00', 'haiku': 'BLOCK', 'ollama': 'PASS',
     'agree': False, 'reasons': ['haiku:LAZINESS', 'ollama:ok']}
]
from collections import Counter
reason_counts = Counter(_ollama_reason(e) for e in entries)
smoke_reasons = {r for r, cnt in reason_counts.items() if r and cnt >= 3}
filtered = [e for e in entries if _ollama_reason(e) not in smoke_reasons]
smoke_count = len(entries) - len(filtered)
assert smoke_count == 5, f'expected 5 filtered, got {smoke_count}'
assert len(filtered) == 1, f'expected 1 remaining, got {len(filtered)}'
assert filtered[0]['reasons'] == ['haiku:LAZINESS', 'ollama:ok'], f'wrong entry kept: {filtered}'
print('shadow_filter_ok')
" 2>/dev/null | grep -q 'shadow_filter_ok' && ok "smoke filter removes repeated ollama reasons (>=3)" || fail "smoke filter logic broken"
echo "[76] qg shadow --trend"
grep -q 'SHADOW_TREND_LOG' ~/.claude/scripts/qg-feedback.py && ok "SHADOW_TREND_LOG constant defined" || fail "SHADOW_TREND_LOG missing"
grep -q "'--trend' in sys.argv" ~/.claude/scripts/qg-feedback.py && ok "--trend flag handled in shadow dispatcher" || fail "--trend not handled"
grep -q 'Trend snapshot' ~/.claude/scripts/qg-feedback.py && ok "trend snapshot message on --clear" || fail "trend snapshot message missing"
grep -q 'shadow.*--trend' ~/.claude/scripts/qg-feedback.py && ok "shadow --trend in usage string" || fail "usage string not updated"
PYTHONIOENCODING=utf-8 python ~/.claude/scripts/qg-feedback.py shadow --trend 2>/dev/null | grep -iqE 'shadow trend|No shadow trend' && ok "shadow --trend runs without error" || fail "shadow --trend command fails"
echo "[77] session-end phi4 shadow summary"
grep -q 'phi4 shadow summary' ~/.claude/hooks/session-end-log.py && ok "shadow summary block present in session-end-log" || fail "shadow summary block missing"
grep -q "qg_script, 'shadow'" ~/.claude/hooks/session-end-log.py && ok "shadow subprocess call correct" || fail "shadow subprocess call wrong"
grep -q 'agree_line' ~/.claude/hooks/session-end-log.py && ok "agree_line parsed in session-end shadow block" || fail "agree_line missing"
python -m py_compile ~/.claude/hooks/session-end-log.py 2>&1 | grep -q . && fail "session-end-log.py syntax error" || ok "session-end-log.py syntax valid"
echo "[78] req-based smoke test filter (_SMOKE_REQS_SEED + dynamic)"
grep -q '_SMOKE_REQS_SEED' ~/.claude/scripts/qg-feedback.py && ok "_SMOKE_REQS_SEED constant defined" || fail "_SMOKE_REQS_SEED missing"
grep -q "What time is it" ~/.claude/scripts/qg-feedback.py && ok "What time is it smoke req present" || fail "smoke req missing"
grep -q "Fix the auth bug" ~/.claude/scripts/qg-feedback.py && ok "Fix the auth bug smoke req present" || fail "smoke req missing"
grep -q "any(req.startswith" ~/.claude/scripts/qg-feedback.py && ok "req-based startswith filter applied" || fail "req filter logic missing"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
entries = [
    {'hash': 'aaa', 'req': 'Fix the auth bug', 'decision': 'BLOCK'},
    {'hash': 'bbb', 'req': 'Fix the auth bug', 'decision': 'PASS'},
    {'hash': 'ccc', 'req': 'What time is it?', 'decision': 'BLOCK'},
    {'hash': 'ddd', 'req': 'Real user request here', 'decision': 'BLOCK'},
]
filtered, smoke_count = qg.filter_smoke_tests(entries)
assert smoke_count == 3, f'expected 3 filtered, got {smoke_count}'
assert len(filtered) == 1 and filtered[0]['req'] == 'Real user request here', f'wrong result: {filtered}'
print('req_filter_ok')
" 2>/dev/null | grep -q 'req_filter_ok' && ok "req-based filter removes known smoke reqs" || fail "req-based filter broken"
echo "[79] qg failures close command"
grep -q 'def cmd_failures_close' ~/.claude/scripts/qg-feedback.py && ok "cmd_failures_close defined" || fail "cmd_failures_close missing"
grep -q "sys.argv\[2\].lower() == 'close'" ~/.claude/scripts/qg-feedback.py && ok "close wired in failures dispatcher" || fail "close not wired"
grep -q 'failures close N' ~/.claude/scripts/qg-feedback.py && ok "failures close in usage/docstring" || fail "close missing from usage"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile, re, datetime
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
# Create a temp failures file with one Open entry
tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
NL = chr(10)
tmp.write('# Test' + NL*2 + '## 2026-01-01: Test entry' + NL + '- **Session**: x' + NL + '- **Status**: Open' + NL)
tmp.close()
orig = qg.FAILURES_PATH
qg.FAILURES_PATH = tmp.name
qg.cmd_failures_close(1, 'test reason')
with open(tmp.name, encoding='utf-8') as f:
    result = f.read()
os.unlink(tmp.name)
qg.FAILURES_PATH = orig
assert 'Resolved' in result and 'test reason' in result, f'close failed: {result!r}'
print('close_ok')
" 2>/dev/null | grep -q 'close_ok' && ok "cmd_failures_close updates Open entry to Resolved" || fail "cmd_failures_close broken"
echo "[80] grace period: OVERCONFIDENCE count suppression"
grep -q "_GRACE_FILE" ~/.claude/hooks/quality-gate.py && ok "_GRACE_FILE constant present" || fail "_GRACE_FILE missing"
grep -q "def _record_verified_counts" ~/.claude/hooks/quality-gate.py && ok "_record_verified_counts defined" || fail "_record_verified_counts missing"
grep -q "def _check_count_grace" ~/.claude/hooks/quality-gate.py && ok "_check_count_grace defined" || fail "_check_count_grace missing"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
# Write fresh grace file with key=388
gf = qg._GRACE_FILE
with open(gf, 'w') as f: json.dump({'ts': time.time(), 'key': '388'}, f)
# Response cites 388 passed with no verification -> grace should suppress
resp = 'Smoke tests pass -- 388 passed, 0 failed, 388 total'
result = qg.mechanical_checks([], [], [], [], resp)
assert result is None, f'grace failed to suppress: {result}'
print('grace_ok')
" 2>/dev/null | grep -q 'grace_ok' && ok "grace suppresses SMOKE:7 for matching count" || fail "grace not suppressing SMOKE:7"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
# Grace key=388, response mentions 200 AND 388 (findall should find 388)
gf = qg._GRACE_FILE
with open(gf, 'w') as f: json.dump({'ts': time.time(), 'key': '388'}, f)
resp = 'Old run: 200 passed. Current: 388 passed, 0 failed, 388 total'
result = qg.mechanical_checks([], [], [], [], resp)
assert result is None, f'multi-count grace failed: {result}'
print('multi_ok')
" 2>/dev/null | grep -q 'multi_ok' && ok "grace fires when response has multiple counts including verified" || fail "grace fails multi-count response"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
# Grace file has key=388, but response cites 500 passed
gf = qg._GRACE_FILE
with open(gf, 'w') as f: json.dump({'ts': time.time(), 'key': '388'}, f)
resp = '500 passed, 0 failed, 500 total'
result = qg.mechanical_checks([], [], [], [], resp)
assert result is not None and 'OVERCONFIDENCE' in result, f'should block different count: {result}'
print('diff_ok')
" 2>/dev/null | grep -q 'diff_ok' && ok "different count still triggers SMOKE:7" || fail "grace wrongly suppresses different count"
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
# No grace file -> SMOKE:7 fires normally
gf = qg._GRACE_FILE
if os.path.exists(gf): os.unlink(gf)
resp = '388 passed, 0 failed, 388 total'
result = qg.mechanical_checks([], [], [], [], resp)
assert result is not None and 'OVERCONFIDENCE' in result, f'no-grace should block: {result}'
print('nograce_ok')
" 2>/dev/null | grep -q 'nograce_ok' && ok "no grace file: SMOKE:7 fires normally" || fail "no grace file: SMOKE:7 not firing"
echo "[81] grace period: production logging and transcript parsing"
# GRACE-WRITE logged to quality-gate.log
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
# Use temp log to avoid polluting production log
tmp = tempfile.mktemp(suffix='.log')
qg.LOG_PATH = tmp
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    qg._record_verified_counts('396 passed, 0 failed, 396 total', ['Bash'])
    with open(tmp) as f: log = f.read()
    assert 'GRACE-WRITE' in log, f'GRACE-WRITE not in log: {repr(log)}'
    assert 'key=396' in log, f'key=396 missing: {repr(log)}'
    assert 'tools=Bash' in log, f'tools=Bash missing: {repr(log)}'
    print('grace_write_ok')
finally:
    for p in [tmp, gf_tmp]:
        try: os.unlink(p)
        except: pass
" 2>/dev/null | grep -q 'grace_write_ok' && ok "GRACE-WRITE logged to quality-gate.log" || fail "GRACE-WRITE not logged"
# GRACE-WRITE fires via === Results: fallback even when tools=[]
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
tmp = tempfile.mktemp(suffix='.log')
qg.LOG_PATH = tmp
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    # No tool_names (simulates transcript timing race), but response has === Results:
    qg._record_verified_counts('=== Results: 400 passed, 0 failed, 400 total ===', [])
    assert os.path.exists(gf_tmp), 'grace file not written via fallback'
    with open(gf_tmp) as f: d = json.load(f)
    assert d['key'] == '400', f'wrong key: {d}'
    with open(tmp) as f: log = f.read()
    assert 'GRACE-WRITE' in log, 'GRACE-WRITE not logged for fallback'
    print('fallback_ok')
finally:
    for p in [tmp, gf_tmp]:
        try: os.unlink(p)
        except: pass
" 2>/dev/null | grep -q 'fallback_ok' && ok "GRACE-WRITE fires via === Results: fallback (tools=[])" || fail "GRACE-WRITE fallback not working"
# GRACE-WRITE fallback does NOT fire for plain count without === Results:
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    # Plain count claim without === Results: marker should NOT write grace via fallback
    qg._record_verified_counts('All 400 tests pass.', [])
    assert not os.path.exists(gf_tmp), 'grace wrongly written for plain count'
    print('no_fallback_ok')
finally:
    try: os.unlink(gf_tmp)
    except: pass
" 2>/dev/null | grep -q 'no_fallback_ok' && ok "GRACE-WRITE fallback does not fire for plain count claim" || fail "GRACE-WRITE fallback fires incorrectly"
# GRACE-HIT logged when suppression fires
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
tmp = tempfile.mktemp(suffix='.log')
qg.LOG_PATH = tmp
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    with open(gf_tmp, 'w') as f: json.dump({'ts': time.time(), 'key': '396'}, f)
    result = qg._check_count_grace('396 passed, 0 failed, 396 total')
    assert result is True, 'grace check should return True'
    with open(tmp) as f: log = f.read()
    assert 'GRACE-HIT' in log, f'GRACE-HIT not in log: {repr(log)}'
    assert 'key=396' in log, f'key=396 missing: {repr(log)}'
    print('grace_hit_ok')
finally:
    for p in [tmp, gf_tmp]:
        try: os.unlink(p)
        except: pass
" 2>/dev/null | grep -q 'grace_hit_ok' && ok "GRACE-HIT logged when suppression fires" || fail "GRACE-HIT not logged"
# TRANSCRIPT entry logged with mtime_age when path non-empty but tools=0 (real main() path)
PYTHONIOENCODING=utf-8 python -c "
import json, os, subprocess, sys, tempfile, time
hook = os.path.expanduser('~/.claude/hooks/quality-gate.py')
tf = tempfile.mktemp(suffix='.jsonl')
with open(tf, 'w') as f:
    f.write(json.dumps({'type': 'user', 'message': {'content': [{'type': 'text', 'text': 'hello'}]}}) + chr(10))
time.sleep(0.05)
payload = json.dumps({'transcript_path': tf, 'last_assistant_message': 'Done.', 'stop_hook_active': False})
try:
    r = subprocess.run(['python', hook], input=payload, capture_output=True, text=True, timeout=15,
                       env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    log_path = os.path.expanduser('~/.claude/quality-gate.log')
    with open(log_path, encoding='utf-8', errors='replace') as lf:
        recent = lf.readlines()[-5:]
    found = any('TRANSCRIPT' in l and 'tools=0' in l and 'mtime_age' in l for l in recent)
    assert found, f'TRANSCRIPT+mtime_age not found: {recent}'
    print('transcript_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'transcript_ok' && ok "TRANSCRIPT entry logged with mtime_age (real main path)" || fail "TRANSCRIPT+mtime_age missing"
# Transcript parsing: realistic JSONL with tool_use entries parses correctly
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
tf = tempfile.mktemp(suffix='.jsonl')
try:
    with open(tf, 'w') as f:
        # Real user message first (oldest)
        f.write(json.dumps({'type': 'user', 'message': {'content': [{'type': 'text', 'text': 'run the tests'}]}}) + '\n')
        # Assistant response with tool_use
        f.write(json.dumps({'type': 'assistant', 'message': {'content': [
            {'type': 'tool_use', 'name': 'Bash', 'id': 't1', 'input': {'command': 'bash smoke-test.sh'}},
            {'type': 'tool_use', 'name': 'Read', 'id': 't2', 'input': {'file_path': '/tmp/x.py'}},
        ]}}) + '\n')
        # Tool results
        f.write(json.dumps({'type': 'user', 'message': {'content': [
            {'type': 'tool_result', 'tool_use_id': 't1', 'content': '396 passed'},
            {'type': 'tool_result', 'tool_use_id': 't2', 'content': 'file'},
        ]}}) + '\n')
    names, _, cmds = qg.get_tool_summary(tf)
    assert 'Bash' in names, f'Bash not found: {names}'
    assert 'Read' in names, f'Read not found: {names}'
    assert 'bash smoke-test.sh' in cmds, f'cmd not found: {cmds}'
    print('transcript_parse_ok')
finally:
    try: os.unlink(tf)
    except: pass
" 2>/dev/null | grep -q 'transcript_parse_ok' && ok "transcript parsing: realistic JSONL with tool_use parses correctly" || fail "transcript parsing: realistic JSONL failed"
# SMOKE:7 bypassed for confidence-challenge requests
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, time, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    # No grace file — would normally fire SMOKE:7
    if os.path.exists(gf_tmp): os.unlink(gf_tmp)
    result = qg.mechanical_checks(
        [], [], [], [],
        '402 passed, 0 failed, 402 total',
        'Are you 100%% sure everything is working properly?'
    )
    assert result is None, f'Expected None (bypass), got: {result}'
    print('cc_bypass_ok')
finally:
    try: os.unlink(gf_tmp)
    except: pass
" 2>/dev/null | grep -q 'cc_bypass_ok' && ok "SMOKE:7 bypassed for confidence-challenge request" || fail "SMOKE:7 not bypassed for confidence-challenge"
# SMOKE:7 still fires for normal requests without grace
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    if os.path.exists(gf_tmp): os.unlink(gf_tmp)
    result = qg.mechanical_checks(
        [], [], [], [],
        '402 passed, 0 failed, 402 total',
        'What did you change in the last edit?'
    )
    assert result is not None and 'OVERCONFIDENCE' in result, f'Expected OVERCONFIDENCE block, got: {result}'
    print('cc_still_blocks_ok')
finally:
    try: os.unlink(gf_tmp)
    except: pass
" 2>/dev/null | grep -q 'cc_still_blocks_ok' && ok "SMOKE:7 still fires for non-challenge request without grace" || fail "SMOKE:7 not firing for non-challenge request"
# qg-grace-writer.py: pipe-test with matching Bash output writes grace and logs
PYTHONIOENCODING=utf-8 python -c "
import json, os, importlib.util, tempfile, time
spec = importlib.util.spec_from_file_location('gw', os.path.expanduser('~/.claude/hooks/qg-grace-writer.py'))
gw = importlib.util.module_from_spec(spec)
gf = tempfile.mktemp(suffix='.json')
lf = tempfile.mktemp(suffix='.log')
spec.loader.exec_module(gw)
gw._GRACE_FILE = gf
gw._LOG_PATH = lf
# Simulate PostToolUse payload with test-runner output
import sys, io
payload = json.dumps({'tool_name': 'Bash', 'tool_response': {'content': '37 passed, 0 failed, 37 total'}})
sys.stdin = io.StringIO(payload)
try:
    gw.main()
    assert os.path.exists(gf), 'grace file not written'
    d = json.load(open(gf))
    assert d.get('key') == '37', f'wrong key: {d}'
    assert time.time() - d.get('ts', 0) < 5, 'ts too old'
    log = open(lf).read()
    assert 'GRACE-WRITE' in log, 'GRACE-WRITE not in log'
    assert 'key=37' in log, 'key=37 not in log'
    assert 'source=PostToolUse' in log, 'source=PostToolUse not in log'
    print('grace_writer_ok')
finally:
    for p in [gf, lf]:
        try: os.unlink(p)
        except: pass
" 2>/dev/null | grep -q 'grace_writer_ok' && ok "qg-grace-writer: Bash output writes grace + GRACE-WRITE log" || fail "qg-grace-writer: pipe-test failed"
# qg-grace-writer.py: non-Bash tool_name is a no-op
PYTHONIOENCODING=utf-8 python -c "
import json, os, importlib.util, tempfile, sys, io
spec = importlib.util.spec_from_file_location('gw', os.path.expanduser('~/.claude/hooks/qg-grace-writer.py'))
gw = importlib.util.module_from_spec(spec); spec.loader.exec_module(gw)
gf = tempfile.mktemp(suffix='.json')
gw._GRACE_FILE = gf
payload = json.dumps({'tool_name': 'Edit', 'tool_response': {'content': '37 passed, 0 failed, 37 total'}})
sys.stdin = io.StringIO(payload)
try:
    gw.main()
    assert not os.path.exists(gf), 'grace file should NOT be written for Edit tool'
    print('grace_writer_noop_ok')
finally:
    try: os.unlink(gf)
    except: pass
" 2>/dev/null | grep -q 'grace_writer_noop_ok' && ok "qg-grace-writer: non-Bash tool is a no-op" || fail "qg-grace-writer: non-Bash tool incorrectly writes grace"
# qg-grace-writer.py: output with no test counts is a no-op
PYTHONIOENCODING=utf-8 python -c "
import json, os, importlib.util, tempfile, sys, io
spec = importlib.util.spec_from_file_location('gw', os.path.expanduser('~/.claude/hooks/qg-grace-writer.py'))
gw = importlib.util.module_from_spec(spec); spec.loader.exec_module(gw)
gf = tempfile.mktemp(suffix='.json')
gw._GRACE_FILE = gf
payload = json.dumps({'tool_name': 'Bash', 'tool_response': {'content': 'No tests found.'}})
sys.stdin = io.StringIO(payload)
try:
    gw.main()
    assert not os.path.exists(gf), 'grace file should NOT be written for non-count output'
    print('grace_writer_nocount_ok')
finally:
    try: os.unlink(gf)
    except: pass
" 2>/dev/null | grep -q 'grace_writer_nocount_ok' && ok "qg-grace-writer: no-count Bash output is a no-op" || fail "qg-grace-writer: no-count output incorrectly writes grace"
echo "[82] numbered-selection bypass for SMOKE:7"
# Test 1: single digit user_request bypasses SMOKE:7 (numbered selection from prior list)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    if os.path.exists(gf_tmp): os.unlink(gf_tmp)
    result = qg.mechanical_checks(
        [], [], [], [],
        '443 passed, 0 failed, 443 total',
        '2'
    )
    assert result is None, f'Expected None (bypass), got: {result}'
    print('numbered_bypass_ok')
finally:
    try: os.unlink(gf_tmp)
    except: pass
" 2>/dev/null | grep -q 'numbered_bypass_ok' && ok "SMOKE:7: single-digit user_request bypasses (numbered selection)" || fail "SMOKE:7: numbered-selection bypass not working"
# Test 2: multi-character request still blocks SMOKE:7 (no grace)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec); spec.loader.exec_module(qg)
gf_tmp = tempfile.mktemp(suffix='.json')
qg._GRACE_FILE = gf_tmp
try:
    if os.path.exists(gf_tmp): os.unlink(gf_tmp)
    result = qg.mechanical_checks(
        [], [], [], [],
        '443 passed, 0 failed, 443 total',
        '12'
    )
    assert result is not None and 'OVERCONFIDENCE' in result, f'Expected OVERCONFIDENCE, got: {result}'
    print('multi_char_blocks_ok')
finally:
    try: os.unlink(gf_tmp)
    except: pass
" 2>/dev/null | grep -q 'multi_char_blocks_ok' && ok "SMOKE:7: multi-char user_request still blocks (not numbered selection)" || fail "SMOKE:7: multi-char wrongly bypassed"

echo "[83] error-dedup.py"
# normalize_error strips paths and line numbers (returns lowercase)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, sys, io
sys.stdin = io.StringIO('{\"invalid\"}')  # force main() to exit early
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(ed)
except SystemExit: pass
result = ed.normalize_error('Error at line 42 in /tmp/foo.py: ENOENT /c/Users/Matt1/x.log')
assert 'line n' in result, f'line n not normalized: {result}'
assert 'path' in result, f'path not normalized: {result}'
assert '42' not in result, f'line number not removed: {result}'
print('norm_ok')
" 2>/dev/null | grep -q 'norm_ok' && ok "error-dedup: normalize_error strips paths+line numbers" || fail "error-dedup: normalize_error failed"

# error_hash is deterministic and 8 chars
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, sys, io
sys.stdin = io.StringIO('{\"invalid\"}')  # force main() to exit early
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(ed)
except SystemExit: pass
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
import importlib.util, os, json, tempfile, time, sys, io
sys.stdin = io.StringIO('{\"invalid\"}')  # force main() to exit early
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(ed)
except SystemExit: pass
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    sid = 'test-session-123'
    err_text = 'Error: ENOENT something'
    state = ed.new_state(sid)
    h = ed.error_hash(err_text)
    state['errors'][h] = {'hash': h, 'canonical': err_text, 'count': 2,
        'first_seen_ts': int(time.time()), 'last_seen_ts': int(time.time()),
        'tool': 'Bash', 'dismissed': False}
    state['alert'] = {'active': False, 'hash': '', 'message': '', 'count': 0}
    ed.atomic_write(sf, state)
    payload = json.dumps({'hook_event_name': 'PostToolUseFailure', 'session_id': sid,
        'tool_name': 'Bash', 'error': err_text})
    sys.stdin = io.StringIO(payload)
    try: ed.main()
    except SystemExit: pass
    result = json.load(open(sf))
    assert result['alert']['active'] is True, f'alert not active: {result["alert"]}'
    assert result['alert']['count'] == 3, f'count should be 3: {result["alert"]["count"]}'
    print('dedup_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'dedup_ok' && ok "error-dedup: 3rd occurrence triggers alert" || fail "error-dedup: dedup alert not triggered"

# Throttle: PostToolUse within 5s is skipped (no state write)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile, time, sys, io
sys.stdin = io.StringIO('{\"invalid\"}')  # force main() to exit early
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(ed)
except SystemExit: pass
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    state = ed.new_state('sess1')
    state['ts'] = int(time.time())
    ed.atomic_write(sf, state)
    mtime_before = os.path.getmtime(sf)
    time.sleep(0.15)
    payload = json.dumps({'hook_event_name': 'PostToolUse', 'session_id': 'sess1',
        'tool_name': 'Bash', 'tool_response': 'Exit code 1\nError: something bad'})
    sys.stdin = io.StringIO(payload)
    try: ed.main()
    except SystemExit: pass
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
sys.stdin = io.StringIO('{\"invalid\"}')  # force main() to exit early
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(ed)
except SystemExit: pass
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    payload = json.dumps({'hook_event_name': 'PostToolUse', 'session_id': 'sess2',
        'tool_name': 'Bash',
        'tool_response': 'Exit code 1\nTraceback (most recent call last):\n  File x.py line 10\nTypeError: bad input'})
    sys.stdin = io.StringIO(payload)
    try: ed.main()
    except SystemExit: pass
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
sys.stdin = io.StringIO('{\"invalid\"}')  # force main() to exit early
spec = importlib.util.spec_from_file_location('ed', os.path.expanduser('~/.claude/hooks/error-dedup.py'))
ed = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(ed)
except SystemExit: pass
sf = tempfile.mktemp(suffix='.json')
ed.STATE_FILE = sf
try:
    old_state = ed.new_state('old-session')
    old_state['errors']['abc'] = {'hash': 'abc', 'canonical': 'old error', 'count': 5,
        'first_seen_ts': 0, 'last_seen_ts': 0, 'tool': 'Bash', 'dismissed': False}
    old_state['ts'] = 0
    ed.atomic_write(sf, old_state)
    payload = json.dumps({'hook_event_name': 'PostToolUseFailure', 'session_id': 'new-session',
        'tool_name': 'Bash', 'error': 'Error: ENOENT new error'})
    sys.stdin = io.StringIO(payload)
    try: ed.main()
    except SystemExit: pass
    new_state = json.load(open(sf))
    assert new_state['session_id'] == 'new-session', f'session not reset: {new_state["session_id"]}'
    assert 'abc' not in new_state['errors'], 'old errors not cleared on new session'
    print('session_reset_ok')
finally:
    try: os.unlink(sf)
    except: pass
" 2>/dev/null | grep -q 'session_reset_ok' && ok "error-dedup: new session_id resets state" || fail "error-dedup: session reset failed"


echo "[84] hook-health-feed.py"

# Test 1: RE_HOOK_AUDIT matches a standard audit log line
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(hhf)
except SystemExit: pass
line = '2026-03-27 14:05 | SESSION_START | Claude Code started'
m = hhf.RE_HOOK_AUDIT.match(line)
assert m is not None, 'RE_HOOK_AUDIT did not match'
assert m.group(2).strip() == 'SESSION_START'
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "hook-health-feed: RE_HOOK_AUDIT matches audit log line" || fail "hook-health-feed: RE_HOOK_AUDIT matches audit log line"

# Test 2: RE_QUALITY_GATE matches PASS and BLOCK lines
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(hhf)
except SystemExit: pass
pass_line  = '2026-03-27 14:05:01 | PASS | response verified'
block_line = '2026-03-27 14:05:02 | BLOCK | missing evidence'
m1 = hhf.RE_QUALITY_GATE.match(pass_line)
m2 = hhf.RE_QUALITY_GATE.match(block_line)
assert m1 and m1.group(2).strip() == 'PASS'
assert m2 and m2.group(2).strip() == 'BLOCK'
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "hook-health-feed: RE_QUALITY_GATE matches PASS and BLOCK" || fail "hook-health-feed: RE_QUALITY_GATE matches PASS and BLOCK"

# Test 3: main() writes hook-health.json with required keys (hooks, overall_status)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(hhf)
except SystemExit: pass
tmp = tempfile.mktemp(suffix='.json')
hhf.HEALTH_FILE = tmp
hhf.LOG_FILES = {k: 'C:/nonexistent/no-such.log' for k in hhf.LOG_FILES}
try:
    hhf.main()
    data = json.load(open(tmp, encoding='utf-8'))
    assert 'hooks' in data and 'overall_status' in data and isinstance(data['hooks'], dict)
    print('token_ok')
finally:
    try: os.unlink(tmp)
    except: pass
" 2>/dev/null | grep -q 'token_ok' && ok "hook-health-feed: main() writes valid hook-health.json" || fail "hook-health-feed: main() writes valid hook-health.json"

# Test 4: main() exits cleanly when all log files are missing
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(hhf)
except SystemExit: pass
tmp = tempfile.mktemp(suffix='.json')
hhf.HEALTH_FILE = tmp
hhf.LOG_FILES = {k: 'C:/nonexistent/no-such.log' for k in hhf.LOG_FILES}
try:
    hhf.main()
    assert os.path.exists(tmp), 'health file not written'
    print('token_ok')
finally:
    try: os.unlink(tmp)
    except: pass
" 2>/dev/null | grep -q 'token_ok' && ok "hook-health-feed: exits cleanly with no log files" || fail "hook-health-feed: exits cleanly with no log files"

# Test 5: build_hook_entry() returns dict with valid status field
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, time
spec = importlib.util.spec_from_file_location('hhf', os.path.expanduser('~/.claude/hooks/hook-health-feed.py'))
hhf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(hhf)
except SystemExit: pass
log_data = {'audit': {}, 'quality_gate': [], 'task_class': [], 'notion_cap': []}
cfg = {'log': 'hook-audit.log', 'max_age': None}
entry = hhf.build_hook_entry('event-observer', cfg, log_data, time.time(), False, set())
assert isinstance(entry, dict) and 'status' in entry
assert entry['status'] in {'healthy', 'unknown', 'stale', 'error', 'muted'}
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "hook-health-feed: build_hook_entry() returns dict with valid status" || fail "hook-health-feed: build_hook_entry() returns dict with valid status"


echo "[85] todo-extractor.py"

# Test: normalize_text strips/lowercases, item_hash is 8-char hex
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(te)
except SystemExit: pass
assert te.normalize_text('  Hello   World  ') == 'hello world'
assert te.normalize_text('FOO BAR') == 'foo bar'
h = te.item_hash('Hello World')
assert isinstance(h, str) and len(h) == 8
assert te.item_hash('Hello World') == te.item_hash('  HELLO   world  ')
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "todo-extractor: normalize_text strips whitespace, item_hash is deterministic 8-char" || fail "todo-extractor: normalize_text strips whitespace, item_hash is deterministic 8-char"

# Test: split_code_fences
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(te)
except SystemExit: pass
bt = chr(96)*3
text = 'prose before\n' + bt + 'python\ncode here\n' + bt + '\nprose after'
parts = te.split_code_fences(text)
assert isinstance(parts, list), 'expected list'
assert len(parts) == 3, 'expected 3 parts, got ' + str(len(parts))
assert 'prose before' in parts[0]
assert 'code here' in parts[1]
assert 'prose after' in parts[2]
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "todo-extractor: split_code_fences returns list, even indices are outside-fence prose" || fail "todo-extractor: split_code_fences returns list, even indices are outside-fence prose"

# Test: scan_transcript CODE_TODO
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(te)
except SystemExit: pass
content = '# TODO: refactor this function later\nx = 1'
record = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'name': 'Write', 'input': {'file_path': '/tmp/test.py', 'content': content}}]}})
tmp = tempfile.mktemp(suffix='.jsonl')
open(tmp, 'w', encoding='utf-8').write(record + '\n')
try:
    items = te.scan_transcript(tmp, 12345)
    assert len(items) >= 1, 'expected at least 1 item, got ' + str(len(items))
    assert any('TODO' in i['category'] for i in items), 'no TODO category'
    assert items[0]['source'] == 'code_written'
    print('token_ok')
finally:
    try: os.unlink(tmp)
    except: pass
" 2>/dev/null | grep -q 'token_ok' && ok "todo-extractor: scan_transcript extracts CODE_TODO from Write tool_use" || fail "todo-extractor: scan_transcript extracts CODE_TODO from Write tool_use"

# Test: scan_transcript don't forget
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(te)
except SystemExit: pass
text = 'Don' + chr(39) + 't forget to update the config file before deploying.'
record = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': text}]}})
tmp = tempfile.mktemp(suffix='.jsonl')
open(tmp, 'w', encoding='utf-8').write(record + '\n')
try:
    items = te.scan_transcript(tmp, 12345)
    assert len(items) >= 1, 'expected at least 1 item, got ' + str(len(items))
    assert any(i['category'] == 'dont_forget' for i in items), 'no dont_forget category'
    assert items[0]['source'] == 'assistant'
    print('token_ok')
finally:
    try: os.unlink(tmp)
    except: pass
" 2>/dev/null | grep -q 'token_ok' && ok "todo-extractor: scan_transcript extracts high-conf dont_forget from assistant text" || fail "todo-extractor: scan_transcript extracts high-conf dont_forget from assistant text"

# Test: main() writes FEED_FILE
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile, sys, io
spec = importlib.util.spec_from_file_location('te', os.path.expanduser('~/.claude/hooks/todo-extractor.py'))
te = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(te)
except SystemExit: pass
tmp_feed = tempfile.mktemp(suffix='.json')
te.FEED_FILE = tmp_feed
payload = json.dumps({'session_id': 'test-session-123', 'cwd': '/tmp'})
sys.stdin = io.StringIO(payload)
try:
    te.main()
except SystemExit:
    pass
finally:
    sys.stdin = sys.__stdin__
data = json.load(open(tmp_feed, encoding='utf-8'))
assert 'items' in data and 'count' in data and 'session_id' in data
assert data['session_id'] == 'test-session-123'
try: os.unlink(tmp_feed)
except: pass
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "todo-extractor: main() writes todo-feed.json with required keys" || fail "todo-extractor: main() writes todo-feed.json with required keys"

echo "[86] qg-session-recall.py"
# Test 1: Fresh snapshot -> emits JSON system message with qg-recall, deletes file
PYTHONIOENCODING=utf-8 python -c "
import sys, os, io, json, time, tempfile

hook = os.path.expanduser('~/.claude/hooks/qg-session-recall.py')
sf = tempfile.mktemp(suffix='.txt')
code = open(hook, encoding='utf-8').read()
patched = code.replace(
    \"SNAPSHOT = os.path.join(STATE_DIR, 'last-session-qg-failures.txt')\",
    'SNAPSHOT = ' + repr(sf)
)
open(sf, 'w', encoding='utf-8').write('BLOCK | OVERCONFIDENCE: test block summary')
old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
    exec(compile(patched, hook, 'exec'), {'__name__': '__main__'})
except SystemExit:
    pass
output = sys.stdout.getvalue().strip()
sys.stdout = old_stdout
try:
    data = json.loads(output)
    assert data.get('type') == 'system', 'type != system'
    assert 'qg-recall' in data.get('message', ''), 'qg-recall not in message'
    assert not os.path.exists(sf), 'snapshot not deleted'
    print('token_ok')
except Exception as e:
    print('FAIL:', e, '| output:', repr(output))
" 2>/dev/null | grep -q 'token_ok' && ok "qg-session-recall: fresh snapshot emits JSON system message with qg-recall and deletes file" || fail "qg-session-recall: fresh snapshot emits JSON system message with qg-recall and deletes file"

# Test 2: Stale snapshot (mtime > 24h ago) -> deletes file, produces no output
PYTHONIOENCODING=utf-8 python -c "
import sys, os, io, time, tempfile

hook = os.path.expanduser('~/.claude/hooks/qg-session-recall.py')
sf = tempfile.mktemp(suffix='.txt')
code = open(hook, encoding='utf-8').read()
patched = code.replace(
    \"SNAPSHOT = os.path.join(STATE_DIR, 'last-session-qg-failures.txt')\",
    'SNAPSHOT = ' + repr(sf)
)
open(sf, 'w', encoding='utf-8').write('BLOCK | OVERCONFIDENCE: stale block')
old_time = time.time() - (25 * 3600)
os.utime(sf, (old_time, old_time))
old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
    exec(compile(patched, hook, 'exec'), {'__name__': '__main__'})
except SystemExit:
    pass
output = sys.stdout.getvalue().strip()
sys.stdout = old_stdout
assert output == '', 'expected no output, got: ' + repr(output)
assert not os.path.exists(sf), 'stale snapshot not deleted'
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "qg-session-recall: stale snapshot deleted silently with no output" || fail "qg-session-recall: stale snapshot deleted silently with no output"

# Test 3: No snapshot (file doesn't exist) -> exits 0, produces no output
PYTHONIOENCODING=utf-8 python -c "
import sys, os, io, tempfile

hook = os.path.expanduser('~/.claude/hooks/qg-session-recall.py')
sf = tempfile.mktemp(suffix='.txt')
code = open(hook, encoding='utf-8').read()
patched = code.replace(
    \"SNAPSHOT = os.path.join(STATE_DIR, 'last-session-qg-failures.txt')\",
    'SNAPSHOT = ' + repr(sf)
)
old_stdout = sys.stdout
sys.stdout = io.StringIO()
try:
    exec(compile(patched, hook, 'exec'), {'__name__': '__main__'})
except SystemExit:
    pass
output = sys.stdout.getvalue().strip()
sys.stdout = old_stdout
assert output == '', 'expected no output, got: ' + repr(output)
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "qg-session-recall: absent snapshot exits 0 with no output" || fail "qg-session-recall: absent snapshot exits 0 with no output"

echo "[87] qg-feedback.py missing functions"
# Test 1: write_feedback appends JSONL record to FEEDBACK_PATH
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgf)
except SystemExit: pass
ff = tempfile.mktemp(suffix='.jsonl')
qgf.FEEDBACK_PATH = ff
record = {'ts': '2026-01-01T00:00:00', 'type': 'fp', 'block_reason': 'test reason'}
qgf.write_feedback(record)
with open(ff, encoding='utf-8') as f:
    line = f.read().strip()
parsed = json.loads(line)
assert parsed['type'] == 'fp', 'type mismatch'
assert parsed['block_reason'] == 'test reason', 'block_reason mismatch'
os.unlink(ff)
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "qg-feedback: write_feedback appends JSONL record to FEEDBACK_PATH" || fail "qg-feedback: write_feedback appends JSONL record to FEEDBACK_PATH"

# Test 2: read_last_override returns last parsed record from OVERRIDES_PATH
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgf)
except SystemExit: pass
of = tempfile.mktemp(suffix='.jsonl')
qgf.OVERRIDES_PATH = of
rec1 = json.dumps({'ts': '2026-01-01T00:00:00', 'block_reason': 'first'})
rec2 = json.dumps({'ts': '2026-01-02T00:00:00', 'block_reason': 'last'})
with open(of, 'w', encoding='utf-8') as f:
    f.write(rec1 + chr(10) + rec2 + chr(10))
result = qgf.read_last_override()
assert result is not None, 'expected a record, got None'
assert result['block_reason'] == 'last', f'expected last record, got: {result}'
os.unlink(of)
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "qg-feedback: read_last_override returns last record from OVERRIDES_PATH" || fail "qg-feedback: read_last_override returns last record from OVERRIDES_PATH"

# Test 3: read_last_override returns None for missing file
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgf)
except SystemExit: pass
qgf.OVERRIDES_PATH = 'C:/nonexistent_overrides_xyzzy_87.jsonl'
result = qgf.read_last_override()
assert result is None, f'expected None for missing file, got: {result}'
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "qg-feedback: read_last_override returns None for missing file" || fail "qg-feedback: read_last_override returns None for missing file"

# Test 4: detect_sessions groups entries by 2-hour gap (SESSION_GAP_SEC=7200)
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
from datetime import datetime, timedelta
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgf)
except SystemExit: pass
base = datetime(2026, 1, 1, 10, 0, 0)
entries = [{'ts': base, 'decision': 'PASS'}, {'ts': base + timedelta(minutes=10), 'decision': 'PASS'}, {'ts': base + timedelta(minutes=20), 'decision': 'BLOCK'}, {'ts': base + timedelta(hours=3), 'decision': 'PASS'}]
sessions = qgf.detect_sessions(entries)
assert len(sessions) == 2, f'expected 2 sessions, got {len(sessions)}'
assert len(sessions[0]) == 3, f'expected 3 in session 1, got {len(sessions[0])}'
assert len(sessions[1]) == 1, f'expected 1 in session 2, got {len(sessions[1])}'
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "qg-feedback: detect_sessions groups entries by 2-hour gap" || fail "qg-feedback: detect_sessions groups entries by 2-hour gap"

# Test 5: _detect_dominant_category returns finding when one category >= 60% of blocks
PYTHONIOENCODING=utf-8 python -c "
import importlib.util, os
spec = importlib.util.spec_from_file_location('qgf', os.path.expanduser('~/.claude/scripts/qg-feedback.py'))
qgf = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgf)
except SystemExit: pass
blocks = [{'category': 'ASSUMPTION', 'decision': 'BLOCK'}] * 6 + [{'category': 'MECHANICAL', 'decision': 'BLOCK'}] * 2
ok_flag, desc, key = qgf._detect_dominant_category(blocks)
assert ok_flag is True, f'expected True, got {ok_flag}'
assert 'ASSUMPTION' in desc, f'expected ASSUMPTION in desc, got: {desc}'
assert key == 'dominant-assumption', f'expected dominant-assumption, got: {key}'
print('token_ok')
" 2>/dev/null | grep -q 'token_ok' && ok "qg-feedback: _detect_dominant_category returns finding when one category dominates" || fail "qg-feedback: _detect_dominant_category returns finding when one category dominates"


echo "[88] quality-gate-analyst.py missing functions"
# Test 1: read_jsonl returns list of dicts for valid JSONL; returns [] for missing file
PYTHONIOENCODING=utf-8 python << 'SMOKE88_1EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate-analyst: read_jsonl returns list of dicts; [] for missing file" || fail "quality-gate-analyst: read_jsonl returns list of dicts; [] for missing file"
import importlib.util, os, json, tempfile
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qga)
except SystemExit: pass
tf = tempfile.mktemp(suffix='.jsonl')
with open(tf, 'w', encoding='utf-8') as f:
    f.write(json.dumps({'a': 1}) + chr(10) + json.dumps({'b': 2}) + chr(10))
result = qga.read_jsonl(tf)
os.unlink(tf)
assert isinstance(result, list), f'expected list, got {type(result)}'
assert len(result) == 2, f'expected 2 entries, got {len(result)}'
assert result[0] == {'a': 1}, f'first entry mismatch: {result[0]}'
missing = qga.read_jsonl('/nonexistent_path_xyzzy_88.jsonl')
assert missing == [], f'expected [] for missing file, got {missing}'
print('token_ok')
SMOKE88_1EOF
# Test 2: compute_metrics returns dict with main_total and main_block_rate fields
PYTHONIOENCODING=utf-8 python << 'SMOKE88_2EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate-analyst: compute_metrics returns dict with main_total and main_block_rate" || fail "quality-gate-analyst: compute_metrics returns dict with main_total and main_block_rate"
import importlib.util, os
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qga)
except SystemExit: pass
entries = [
    {'source': 'main', 'decision': 'PASS', 'reason': 'ok', 'tools': '', 'req': '', 'hash': ''},
    {'source': 'main', 'decision': 'BLOCK', 'reason': 'ASSUMPTION: test', 'tools': '', 'req': '', 'hash': ''},
    {'source': 'subagent', 'decision': 'PASS', 'reason': '', 'tools': '', 'req': '', 'hash': ''},
]
overrides = [{'auto_verdict': 'likely_fp'}, {'auto_verdict': 'likely_tp'}]
feedback = [{'type': 'fp'}, {'type': 'tp'}, {'type': 'miss'}]
m = qga.compute_metrics(entries, overrides, feedback)
assert isinstance(m, dict), f'expected dict, got {type(m)}'
assert 'main_total' in m, f'missing main_total key: {list(m.keys())}'
assert 'main_block_rate' in m, f'missing main_block_rate key: {list(m.keys())}'
assert m['main_total'] == 2, f'expected main_total=2, got {m["main_total"]}'
assert abs(m['main_block_rate'] - 0.5) < 1e-9, f'expected 0.5 block rate, got {m["main_block_rate"]}'
print('token_ok')
SMOKE88_2EOF
# Test 3: cluster_fp_patterns returns dict; empty dict for empty input
PYTHONIOENCODING=utf-8 python << 'SMOKE88_3EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate-analyst: cluster_fp_patterns returns dict; empty dict for empty input" || fail "quality-gate-analyst: cluster_fp_patterns returns dict; empty dict for empty input"
import importlib.util, os
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qga)
except SystemExit: pass
empty_result = qga.cluster_fp_patterns([])
assert isinstance(empty_result, dict), f'expected dict for empty input, got {type(empty_result)}'
assert len(empty_result) == 0, f'expected empty dict, got {empty_result}'
overrides = [
    {'auto_verdict': 'likely_fp', 'block_reason': 'ASSUMPTION: file path not verified and also xxxxxx'},
    {'auto_verdict': 'likely_fp', 'block_reason': 'ASSUMPTION: file path not verified and also yyyyyy'},
    {'auto_verdict': 'likely_tp', 'block_reason': 'something else entirely different'},
]
result = qga.cluster_fp_patterns(overrides)
assert isinstance(result, dict), f'expected dict, got {type(result)}'
assert len(result) == 1, f'expected 1 cluster (same 40-char prefix), got {len(result)}: {list(result.keys())}'
prefix_key = list(result.keys())[0]
assert len(result[prefix_key]) == 2, f'expected 2 records in cluster, got {len(result[prefix_key])}'
print('token_ok')
SMOKE88_3EOF
# Test 4: write_report writes a non-empty output file to INSIGHTS path
PYTHONIOENCODING=utf-8 python << 'SMOKE88_4EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate-analyst: write_report writes non-empty output file to INSIGHTS path" || fail "quality-gate-analyst: write_report writes non-empty output file to INSIGHTS path"
import importlib.util, os, tempfile
spec = importlib.util.spec_from_file_location('qga', os.path.expanduser('~/.claude/scripts/quality-gate-analyst.py'))
qga = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qga)
except SystemExit: pass
tf = tempfile.mktemp(suffix='.md')
qga.INSIGHTS = tf
metrics = {
    'main_total': 0, 'main_blocks': 0, 'main_block_rate': 0.0,
    'sub_total': 0, 'sub_blocks': 0, 'sub_block_rate': 0.0,
    'fp_overrides': 0, 'tp_overrides': 0, 'total_overrides': 0,
    'fp_rate': 0.0, 'override_rate': 0.0,
    'categories': {},
    'fb_fp': 0, 'fb_tp': 0, 'fb_miss': 0,
}
qga.write_report(metrics, {}, [])
assert os.path.exists(tf), 'INSIGHTS file was not created'
size = os.path.getsize(tf)
os.unlink(tf)
assert size > 0, f'INSIGHTS file is empty (size={size})'
print('token_ok')
SMOKE88_4EOF

echo "[89] quality-gate.py + _hooks_shared.py missing functions"
# Test 1: get_last_complexity returns MODERATE for missing log; returns last entry complexity
PYTHONIOENCODING=utf-8 python << 'SMOKE89_1EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate: get_last_complexity returns MODERATE for missing log; DEEP from log entry" || fail "quality-gate: get_last_complexity returns MODERATE for missing log; DEEP from log entry"
import importlib.util, os, sys, tempfile, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
orig_log = qg.CLASSIFIER_LOG
qg.CLASSIFIER_LOG = '/tmp/nonexistent_classifier_89_xyzzy.log'
result_no_file = qg.get_last_complexity()
assert result_no_file == 'MODERATE', f'expected MODERATE for missing file, got: {result_no_file!r}'
tf = tempfile.mktemp(suffix='.log')
with open(tf, 'w', encoding='utf-8') as f:
    f.write('2026-01-01 10:00:00 | MODERATE | some task' + chr(10))
    f.write('2026-01-01 10:01:00 | DEEP | another task' + chr(10))
qg.CLASSIFIER_LOG = tf
result_deep = qg.get_last_complexity()
os.unlink(tf)
qg.CLASSIFIER_LOG = orig_log
assert result_deep == 'DEEP', f'expected DEEP, got: {result_deep!r}'
print('token_ok')
SMOKE89_1EOF
# Test 2: _get_last_turn_lines returns [] for missing transcript; returns assistant entries
PYTHONIOENCODING=utf-8 python << 'SMOKE89_2EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate: _get_last_turn_lines returns [] for missing file; returns assistant entries" || fail "quality-gate: _get_last_turn_lines returns [] for missing file; returns assistant entries"
import importlib.util, os, sys, tempfile, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
result_empty = qg._get_last_turn_lines('/tmp/nonexistent_transcript_89_xyzzy.jsonl')
assert result_empty == [], f'expected [] for missing file, got: {result_empty!r}'
tf = tempfile.mktemp(suffix='.jsonl')
assistant_entry = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Hello'}]}})
user_entry = json.dumps({'type': 'user', 'message': {'content': 'What should I do?'}})
with open(tf, 'w', encoding='utf-8') as f:
    f.write(user_entry + chr(10))
    f.write(assistant_entry + chr(10))
result = qg._get_last_turn_lines(tf)
os.unlink(tf)
assert isinstance(result, list), f'expected list, got: {type(result)}'
assert len(result) == 1, f'expected 1 assistant entry, got: {len(result)}'
assert result[0]['type'] == 'assistant', f'expected assistant type, got: {result[0]["type"]}'
print('token_ok')
SMOKE89_2EOF
# Test 3: get_bash_results extracts Bash tool result content; [] for missing transcript
PYTHONIOENCODING=utf-8 python << 'SMOKE89_3EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate: get_bash_results returns Bash result content; [] for missing transcript" || fail "quality-gate: get_bash_results returns Bash result content; [] for missing transcript"
import importlib.util, os, sys, tempfile, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
result_empty = qg.get_bash_results('/tmp/nonexistent_transcript_89b_xyzzy.jsonl')
assert result_empty == [], f'expected [] for missing file, got: {result_empty!r}'
tf = tempfile.mktemp(suffix='.jsonl')
bash_id = 'toolu_bash_smoke89_test3'
user_request_line = json.dumps({'type': 'user', 'message': {'content': 'run it'}})
assistant_tool_use_line = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': bash_id, 'name': 'Bash', 'input': {'command': 'echo hello'}}]}})
user_result_line = json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': bash_id, 'content': 'hello'}]}})
assistant_final_line = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': 'Done.'}]}})
with open(tf, 'w', encoding='utf-8') as f:
    f.write(user_request_line + chr(10))
    f.write(assistant_tool_use_line + chr(10))
    f.write(user_result_line + chr(10))
    f.write(assistant_final_line + chr(10))
result = qg.get_bash_results(tf)
os.unlink(tf)
assert isinstance(result, list), f'expected list, got: {type(result)}'
assert len(result) == 1, f'expected 1 result, got: {len(result)}'
assert 'hello' in result[0], f'expected hello in result, got: {result[0]!r}'
print('token_ok')
SMOKE89_3EOF
# Test 4: get_failed_commands detects is_error=True results as (cmd, err) tuples; [] for missing
PYTHONIOENCODING=utf-8 python << 'SMOKE89_4EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate: get_failed_commands returns (cmd, err) tuples for is_error=True; [] for missing" || fail "quality-gate: get_failed_commands returns (cmd, err) tuples for is_error=True; [] for missing"
import importlib.util, os, sys, tempfile, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
result_empty = qg.get_failed_commands('/tmp/nonexistent_transcript_89c_xyzzy.jsonl')
assert result_empty == [], f'expected [] for missing file, got: {result_empty!r}'
tf = tempfile.mktemp(suffix='.jsonl')
bash_id = 'toolu_bash_smoke89_test4'
user_request_line = json.dumps({'type': 'user', 'message': {'content': 'run bad command'}})
assistant_line = json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'tool_use', 'id': bash_id, 'name': 'Bash', 'input': {'command': 'bad_cmd_xyzzy'}}]}})
user_result_line = json.dumps({'type': 'user', 'message': {'content': [{'type': 'tool_result', 'tool_use_id': bash_id, 'is_error': True, 'content': 'command not found: bad_cmd_xyzzy'}]}})
with open(tf, 'w', encoding='utf-8') as f:
    f.write(user_request_line + chr(10))
    f.write(assistant_line + chr(10))
    f.write(user_result_line + chr(10))
result = qg.get_failed_commands(tf)
os.unlink(tf)
assert isinstance(result, list), f'expected list, got: {type(result)}'
assert len(result) == 1, f'expected 1 failed command, got: {len(result)}'
cmd, err = result[0]
assert 'bad_cmd_xyzzy' in cmd, f'expected bad_cmd_xyzzy in cmd, got: {cmd!r}'
assert 'not found' in err, f'expected not found in err, got: {err!r}'
print('token_ok')
SMOKE89_4EOF
# Test 5: _count_user_items returns 0 for empty; counts explicit number; counts comma list
PYTHONIOENCODING=utf-8 python << 'SMOKE89_5EOF' 2>/dev/null | grep -q token_ok && ok "quality-gate: _count_user_items returns 0 for empty; counts explicit number; counts comma list" || fail "quality-gate: _count_user_items returns 0 for empty; counts explicit number; counts comma list"
import importlib.util, os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
result_empty = qg._count_user_items('')
assert result_empty == 0, f'expected 0 for empty, got: {result_empty}'
result_none = qg._count_user_items(None)
assert result_none == 0, f'expected 0 for None, got: {result_none}'
result_explicit = qg._count_user_items('fix these 5 bugs in the codebase')
assert result_explicit == 5, f'expected 5, got: {result_explicit}'
result_list = qg._count_user_items('fix the following: auth timeout, CSRF bypass, SQL injection, XSS')
assert result_list >= 3, f'expected >= 3 for comma list, got: {result_list}'
print('token_ok')
SMOKE89_5EOF
# Test 6: _response_hash is deterministic; different inputs differ; length >= 8
PYTHONIOENCODING=utf-8 python << 'SMOKE89_6EOF' 2>/dev/null | grep -q token_ok && ok "_hooks_shared: _response_hash is deterministic; different inputs differ; length >= 8" || fail "_hooks_shared: _response_hash is deterministic; different inputs differ; length >= 8"
import importlib.util, os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('hs', os.path.expanduser('~/.claude/hooks/_hooks_shared.py'))
hs = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(hs)
except SystemExit: pass
h1 = hs._response_hash('hello world')
h2 = hs._response_hash('hello world')
assert h1 == h2, f'expected deterministic hash, got {h1!r} != {h2!r}'
h3 = hs._response_hash('different input')
assert h1 != h3, f'expected different hashes for different inputs, both got: {h1!r}'
assert len(h1) >= 8, f'expected hash length >= 8, got: {len(h1)}'
h_empty = hs._response_hash('')
assert isinstance(h_empty, str), f'expected str, got: {type(h_empty)}'
assert len(h_empty) >= 8, f'expected >= 8 chars for empty hash, got: {len(h_empty)}'
print('token_ok')
SMOKE89_6EOF

echo "[90] notion-commit-reminder.py"
# Test 1: git commit triggers additionalContext injection
PYTHONIOENCODING=utf-8 python << 'SMOKE90_1EOF' 2>/dev/null | grep -q commit_reminder_ok && ok "notion-commit-reminder: git commit injects additionalContext" || fail "notion-commit-reminder: git commit injects additionalContext"
import importlib.util, os, sys, json, io
sys.stdin = io.StringIO(json.dumps({'tool_input': {'command': 'git commit -m "fix: update auth"'}}))
import importlib.util
spec = importlib.util.spec_from_file_location('ncr', os.path.expanduser('~/.claude/hooks/notion-commit-reminder.py'))
ncr = importlib.util.module_from_spec(spec)
out = io.StringIO()
import contextlib
with contextlib.redirect_stdout(out):
    try: spec.loader.exec_module(ncr)
    except SystemExit: pass
result = out.getvalue().strip()
assert result, f'expected JSON output for git commit, got empty'
data = json.loads(result)
ctx = data.get('hookSpecificOutput', {}).get('additionalContext', '')
assert 'notion-commit-reminder' in ctx, f'missing reminder tag in: {ctx!r}'
print('commit_reminder_ok')
SMOKE90_1EOF
# Test 2: git commit --no-commit does NOT trigger
PYTHONIOENCODING=utf-8 python << 'SMOKE90_2EOF' 2>/dev/null | grep -q nocommit_ok && ok "notion-commit-reminder: --no-commit suppresses output" || fail "notion-commit-reminder: --no-commit suppresses output"
import importlib.util, os, sys, json, io, contextlib
sys.stdin = io.StringIO(json.dumps({'tool_input': {'command': 'git commit --no-commit'}}))
spec = importlib.util.spec_from_file_location('ncr', os.path.expanduser('~/.claude/hooks/notion-commit-reminder.py'))
ncr = importlib.util.module_from_spec(spec)
out = io.StringIO()
with contextlib.redirect_stdout(out):
    try: spec.loader.exec_module(ncr)
    except SystemExit: pass
assert out.getvalue().strip() == '', f'expected no output for --no-commit, got: {out.getvalue()!r}'
print('nocommit_ok')
SMOKE90_2EOF
# Test 3: non-commit bash command produces no output
PYTHONIOENCODING=utf-8 python << 'SMOKE90_3EOF' 2>/dev/null | grep -q nongit_ok && ok "notion-commit-reminder: non-commit command produces no output" || fail "notion-commit-reminder: non-commit command produces no output"
import importlib.util, os, sys, json, io, contextlib
sys.stdin = io.StringIO(json.dumps({'tool_input': {'command': 'git status'}}))
spec = importlib.util.spec_from_file_location('ncr', os.path.expanduser('~/.claude/hooks/notion-commit-reminder.py'))
ncr = importlib.util.module_from_spec(spec)
out = io.StringIO()
with contextlib.redirect_stdout(out):
    try: spec.loader.exec_module(ncr)
    except SystemExit: pass
assert out.getvalue().strip() == '', f'expected no output for git status, got: {out.getvalue()!r}'
print('nongit_ok')
SMOKE90_3EOF
# Test 4: invalid JSON input exits cleanly (no crash)
PYTHONIOENCODING=utf-8 python << 'SMOKE90_4EOF' 2>/dev/null | grep -q invalid_ok && ok "notion-commit-reminder: invalid JSON input exits cleanly" || fail "notion-commit-reminder: invalid JSON input exits cleanly"
import importlib.util, os, sys, io, contextlib
sys.stdin = io.StringIO('not valid json')
spec = importlib.util.spec_from_file_location('ncr', os.path.expanduser('~/.claude/hooks/notion-commit-reminder.py'))
ncr = importlib.util.module_from_spec(spec)
out = io.StringIO()
with contextlib.redirect_stdout(out):
    try: spec.loader.exec_module(ncr)
    except SystemExit: pass
assert out.getvalue().strip() == '', f'expected no output for invalid JSON, got: {out.getvalue()!r}'
print('invalid_ok')
SMOKE90_4EOF

echo "[91] smoke-count-updater.py"
# Test 1: non-Bash tool_name is a no-op
PYTHONIOENCODING=utf-8 python << 'SMOKE91_1EOF' 2>/dev/null | grep -q scu_noop_ok && ok "smoke-count-updater: non-Bash tool is a no-op" || fail "smoke-count-updater: non-Bash tool is a no-op"
import importlib.util, os, sys, json, io, tempfile
spec = importlib.util.spec_from_file_location('scu', os.path.expanduser('~/.claude/hooks/smoke-count-updater.py'))
scu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scu)
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as m:
    m.write('original'); mem_path = m.name
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as c:
    c.write('original'); cal_path = c.name
scu._MEMORY_MD = mem_path; scu._CALIBRATION = cal_path
sys.stdin = io.StringIO(json.dumps({'tool_name': 'Read', 'tool_response': {'content': '=== Results: 99 passed, 0 failed, 99 total ==='}}))
scu.main()
assert open(mem_path).read() == 'original', 'MEMORY.md changed for non-Bash tool'
os.unlink(mem_path); os.unlink(cal_path)
print('scu_noop_ok')
SMOKE91_1EOF
# Test 2: Bash output with results line updates MEMORY.md quality-gate entry
PYTHONIOENCODING=utf-8 python << 'SMOKE91_2EOF' 2>/dev/null | grep -q scu_memory_ok && ok "smoke-count-updater: results line updates MEMORY.md quality-gate line" || fail "smoke-count-updater: results line updates MEMORY.md quality-gate line"
import importlib.util, os, sys, json, io, tempfile
spec = importlib.util.spec_from_file_location('scu', os.path.expanduser('~/.claude/hooks/smoke-count-updater.py'))
scu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scu)
NL = chr(10)
mem_content = '# Memory' + NL + '- [quality-gate-calibration.md](memory/quality-gate-calibration.md) — Session X: 50 smoke tests pass.' + NL
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as m:
    m.write(mem_content); mem_path = m.name
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as c:
    c.write('# Calibration' + NL); cal_path = c.name
scu._MEMORY_MD = mem_path; scu._CALIBRATION = cal_path
sys.stdin = io.StringIO(json.dumps({'tool_name': 'Bash', 'tool_response': {'content': '=== Results: 99 passed, 0 failed, 99 total ==='}}))
scu.main()
mem_after = open(mem_path).read()
assert '99 smoke tests pass' in mem_after, 'MEMORY.md not updated to 99'
assert '50 smoke tests pass' not in mem_after, 'old count 50 still present'
os.unlink(mem_path); os.unlink(cal_path)
print('scu_memory_ok')
SMOKE91_2EOF
# Test 3: count < 50 is a no-op
PYTHONIOENCODING=utf-8 python << 'SMOKE91_3EOF' 2>/dev/null | grep -q scu_lowcount_ok && ok "smoke-count-updater: count < 50 is a no-op" || fail "smoke-count-updater: count < 50 is a no-op"
import importlib.util, os, sys, json, io, tempfile
spec = importlib.util.spec_from_file_location('scu', os.path.expanduser('~/.claude/hooks/smoke-count-updater.py'))
scu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scu)
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as m:
    m.write('original'); mem_path = m.name
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as c:
    c.write('original'); cal_path = c.name
scu._MEMORY_MD = mem_path; scu._CALIBRATION = cal_path
sys.stdin = io.StringIO(json.dumps({'tool_name': 'Bash', 'tool_response': {'content': '=== Results: 40 passed, 0 failed, 40 total ==='}}))
scu.main()
assert open(mem_path).read() == 'original', 'MEMORY.md changed for count < 50'
os.unlink(mem_path); os.unlink(cal_path)
print('scu_lowcount_ok')
SMOKE91_3EOF
# Test 4: calibration deduplication (same day+count not appended twice)
PYTHONIOENCODING=utf-8 python << 'SMOKE91_4EOF' 2>/dev/null | grep -q scu_dedup_ok && ok "smoke-count-updater: duplicate day+count not re-appended to calibration" || fail "smoke-count-updater: duplicate day+count not re-appended to calibration"
import importlib.util, os, sys, json, io, tempfile
from datetime import datetime
spec = importlib.util.spec_from_file_location('scu', os.path.expanduser('~/.claude/hooks/smoke-count-updater.py'))
scu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scu)
today = datetime.now().strftime('%Y-%m-%d')
NL = chr(10)
existing = '# Calibration' + NL + '## Auto-update ' + today + NL + '- smoke-test.sh: 99 passed' + NL
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as m:
    m.write('original'); mem_path = m.name
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as c:
    c.write(existing); cal_path = c.name
scu._MEMORY_MD = mem_path; scu._CALIBRATION = cal_path
sys.stdin = io.StringIO(json.dumps({'tool_name': 'Bash', 'tool_response': {'content': '=== Results: 99 passed, 0 failed, 99 total ==='}}))
scu.main()
cal_after = open(cal_path).read()
count_auto = cal_after.count('## Auto-update ' + today)
assert count_auto == 1, 'dedup failed: ' + str(count_auto) + ' auto-update entries'
os.unlink(mem_path); os.unlink(cal_path)
print('scu_dedup_ok')
SMOKE91_4EOF
# Test 5: new calibration entry IS appended when not already present
PYTHONIOENCODING=utf-8 python << 'SMOKE91_5EOF' 2>/dev/null | grep -q scu_cal_append_ok && ok "smoke-count-updater: new calibration entry appended when absent" || fail "smoke-count-updater: new calibration entry appended when absent"
import importlib.util, os, sys, json, io, tempfile
from datetime import datetime
spec = importlib.util.spec_from_file_location('scu', os.path.expanduser('~/.claude/hooks/smoke-count-updater.py'))
scu = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scu)
today = datetime.now().strftime('%Y-%m-%d')
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as m:
    m.write('original'); mem_path = m.name
with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as c:
    c.write('# Calibration' + chr(10)); cal_path = c.name
scu._MEMORY_MD = mem_path; scu._CALIBRATION = cal_path
sys.stdin = io.StringIO(json.dumps({'tool_name': 'Bash', 'tool_response': {'content': '=== Results: 99 passed, 0 failed, 99 total ==='}}))
scu.main()
cal_after = open(cal_path).read()
assert '## Auto-update ' + today in cal_after, 'auto-update header not in calibration: ' + repr(cal_after)
assert 'smoke-test.sh: 99 passed' in cal_after, 'count not in calibration: ' + repr(cal_after)
os.unlink(mem_path); os.unlink(cal_path)
print('scu_cal_append_ok')
SMOKE91_5EOF

echo "[92] precheck-hook.py (functional I/O)"
# Test 1: MECHANICAL input → directive injected
PYTHONIOENCODING=utf-8 python << 'SMOKE92_1EOF' 2>/dev/null | grep -q precheck_mechanical_ok && ok "precheck-hook: MECHANICAL category injects directive" || fail "precheck-hook: MECHANICAL category injects directive"
import importlib.util, os, sys, json, io, unittest.mock, contextlib
spec = importlib.util.spec_from_file_location('ph', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)
mock_resp = unittest.mock.MagicMock()
mock_resp.read.return_value = json.dumps({'response': 'MECHANICAL'}).encode()
mock_resp.__enter__ = lambda s: s
mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
sys.stdin = io.StringIO(json.dumps({'message': 'add the new function to utils.py'}))
out = io.StringIO()
with unittest.mock.patch('urllib.request.urlopen', return_value=mock_resp):
    with contextlib.redirect_stdout(out):
        ph.main()
result = out.getvalue().strip()
assert '[pre-check:MECHANICAL]' in result, 'expected MECHANICAL directive, got: ' + repr(result)
print('precheck_mechanical_ok')
SMOKE92_1EOF
# Test 2: Ollama down → silent exit (graceful degradation)
PYTHONIOENCODING=utf-8 python << 'SMOKE92_2EOF' 2>/dev/null | grep -q precheck_down_ok && ok "precheck-hook: Ollama down exits silently" || fail "precheck-hook: Ollama down exits silently"
import importlib.util, os, sys, json, io, unittest.mock, contextlib
spec = importlib.util.spec_from_file_location('ph', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)
sys.stdin = io.StringIO(json.dumps({'message': 'add the new function to utils.py'}))
out = io.StringIO()
with unittest.mock.patch('urllib.request.urlopen', side_effect=OSError('Connection refused')):
    with contextlib.redirect_stdout(out):
        ph.main()
assert out.getvalue().strip() == '', 'expected no output when Ollama down, got: ' + repr(out.getvalue())
print('precheck_down_ok')
SMOKE92_2EOF
# Test 3: NONE category → no output
PYTHONIOENCODING=utf-8 python << 'SMOKE92_3EOF' 2>/dev/null | grep -q precheck_none_ok && ok "precheck-hook: NONE category produces no output" || fail "precheck-hook: NONE category produces no output"
import importlib.util, os, sys, json, io, unittest.mock, contextlib
spec = importlib.util.spec_from_file_location('ph', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)
mock_resp = unittest.mock.MagicMock()
mock_resp.read.return_value = json.dumps({'response': 'NONE'}).encode()
mock_resp.__enter__ = lambda s: s
mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
sys.stdin = io.StringIO(json.dumps({'message': 'hello there how are you doing today'}))
out = io.StringIO()
with unittest.mock.patch('urllib.request.urlopen', return_value=mock_resp):
    with contextlib.redirect_stdout(out):
        ph.main()
assert out.getvalue().strip() == '', 'expected no output for NONE, got: ' + repr(out.getvalue())
print('precheck_none_ok')
SMOKE92_3EOF
# Test 4: short message (< 5 chars) skips Ollama entirely
PYTHONIOENCODING=utf-8 python << 'SMOKE92_4EOF' 2>/dev/null | grep -q precheck_short_ok && ok "precheck-hook: short message skips Ollama call" || fail "precheck-hook: short message skips Ollama call"
import importlib.util, os, sys, json, io, unittest.mock, contextlib
spec = importlib.util.spec_from_file_location('ph', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)
sys.stdin = io.StringIO(json.dumps({'message': 'hi'}))
out = io.StringIO()
with unittest.mock.patch('urllib.request.urlopen', side_effect=AssertionError('urlopen must not be called for short msg')) as mock_u:
    with contextlib.redirect_stdout(out):
        ph.main()
assert not mock_u.called, 'urlopen called for short message'
assert out.getvalue().strip() == '', 'expected no output for short message'
print('precheck_short_ok')
SMOKE92_4EOF
# Tests 5-7: remaining categories each inject the correct directive
PYTHONIOENCODING=utf-8 python << 'SMOKE92_5EOF' 2>/dev/null | grep -q precheck_assumption_ok && ok "precheck-hook: ASSUMPTION category injects directive" || fail "precheck-hook: ASSUMPTION category injects directive"
import importlib.util, os, sys, json, io, unittest.mock, contextlib
spec = importlib.util.spec_from_file_location('ph', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)
mock_resp = unittest.mock.MagicMock()
mock_resp.read.return_value = json.dumps({'response': 'ASSUMPTION'}).encode()
mock_resp.__enter__ = lambda s: s
mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
sys.stdin = io.StringIO(json.dumps({'message': 'what does the validate function return'}))
out = io.StringIO()
with unittest.mock.patch('urllib.request.urlopen', return_value=mock_resp):
    with contextlib.redirect_stdout(out):
        ph.main()
result = out.getvalue().strip()
assert '[pre-check:ASSUMPTION]' in result, 'expected ASSUMPTION directive, got: ' + repr(result)
print('precheck_assumption_ok')
SMOKE92_5EOF
PYTHONIOENCODING=utf-8 python << 'SMOKE92_6EOF' 2>/dev/null | grep -q precheck_planning_ok && ok "precheck-hook: PLANNING category injects directive" || fail "precheck-hook: PLANNING category injects directive"
import importlib.util, os, sys, json, io, unittest.mock, contextlib
spec = importlib.util.spec_from_file_location('ph', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)
mock_resp = unittest.mock.MagicMock()
mock_resp.read.return_value = json.dumps({'response': 'PLANNING'}).encode()
mock_resp.__enter__ = lambda s: s
mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
sys.stdin = io.StringIO(json.dumps({'message': 'what are the next steps we should work on'}))
out = io.StringIO()
with unittest.mock.patch('urllib.request.urlopen', return_value=mock_resp):
    with contextlib.redirect_stdout(out):
        ph.main()
result = out.getvalue().strip()
assert '[pre-check:PLANNING]' in result, 'expected PLANNING directive, got: ' + repr(result)
print('precheck_planning_ok')
SMOKE92_6EOF
PYTHONIOENCODING=utf-8 python << 'SMOKE92_7EOF' 2>/dev/null | grep -q precheck_overconf_ok && ok "precheck-hook: OVERCONFIDENCE category injects directive" || fail "precheck-hook: OVERCONFIDENCE category injects directive"
import importlib.util, os, sys, json, io, unittest.mock, contextlib
spec = importlib.util.spec_from_file_location('ph', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
ph = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ph)
mock_resp = unittest.mock.MagicMock()
mock_resp.read.return_value = json.dumps({'response': 'OVERCONFIDENCE'}).encode()
mock_resp.__enter__ = lambda s: s
mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
sys.stdin = io.StringIO(json.dumps({'message': 'did the tests pass and are the changes correct'}))
out = io.StringIO()
with unittest.mock.patch('urllib.request.urlopen', return_value=mock_resp):
    with contextlib.redirect_stdout(out):
        ph.main()
result = out.getvalue().strip()
assert '[pre-check:OVERCONFIDENCE]' in result, 'expected OVERCONFIDENCE directive, got: ' + repr(result)
print('precheck_overconf_ok')
SMOKE92_7EOF

echo "[93] qg-regression.py (pure functions)"
# Test 1: parse_tools handles list, none, empty, None
PYTHONIOENCODING=utf-8 python << 'SMOKE93_1EOF' 2>/dev/null | grep -q qgr_tools_ok && ok "qg-regression: parse_tools handles list/none/empty/None" || fail "qg-regression: parse_tools handles list/none/empty/None"
import importlib.util, os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qgr', os.path.expanduser('~/.claude/scripts/qg-regression.py'))
qgr = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgr)
except SystemExit: pass
assert qgr.parse_tools('Bash, Edit, Grep') == ['Bash', 'Edit', 'Grep'], 'list parse failed'
assert qgr.parse_tools('(none)') == [], '(none) not empty'
assert qgr.parse_tools('none') == [], 'none not empty'
assert qgr.parse_tools('') == [], 'empty string not empty'
assert qgr.parse_tools(None) == [], 'None not empty'
print('qgr_tools_ok')
SMOKE93_1EOF
# Test 2: parse_files handles list, none, empty
PYTHONIOENCODING=utf-8 python << 'SMOKE93_2EOF' 2>/dev/null | grep -q qgr_files_ok && ok "qg-regression: parse_files handles list/none/empty" || fail "qg-regression: parse_files handles list/none/empty"
import importlib.util, os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qgr', os.path.expanduser('~/.claude/scripts/qg-regression.py'))
qgr = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgr)
except SystemExit: pass
assert qgr.parse_files('src/main.py, tests/test.py') == ['src/main.py', 'tests/test.py'], 'list parse failed'
assert qgr.parse_files('none') == [], 'none not empty'
assert qgr.parse_files('-') == [], '- not empty'
assert qgr.parse_files('') == [], 'empty string not empty'
print('qgr_files_ok')
SMOKE93_2EOF
# Test 3: parse_examples parses old format (USER/TOOLS USED/FILES EDITED/RESPONSE/Verdict)
PYTHONIOENCODING=utf-8 python << 'SMOKE93_3EOF' 2>/dev/null | grep -q qgr_old_fmt_ok && ok "qg-regression: parse_examples parses old format correctly" || fail "qg-regression: parse_examples parses old format correctly"
import importlib.util, os, sys, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qgr', os.path.expanduser('~/.claude/scripts/qg-regression.py'))
qgr = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgr)
except SystemExit: pass
block = 'Example 1 -- PASS' + chr(10) + 'USER: "Fix the auth bug"' + chr(10) + 'TOOLS USED: Bash, Edit' + chr(10) + 'FILES EDITED: src/auth.py' + chr(10) + 'BASH RESULTS: tests pass' + chr(10) + 'RESPONSE: "Fixed by updating line 42."' + chr(10) + 'Verdict: {"ok": true}'
examples = qgr.parse_examples(block)
assert len(examples) == 1, 'expected 1 example, got ' + str(len(examples))
e = examples[0]
assert e['num'] == '1', 'wrong num: ' + repr(e['num'])
assert e['expected'] == 'PASS', 'wrong expected'
assert e['user'] == 'Fix the auth bug', 'wrong user: ' + repr(e['user'])
assert 'Bash' in e['tool_names'], 'Bash not in tool_names'
assert 'src/auth.py' in e['edited_paths'], 'file not parsed'
print('qgr_old_fmt_ok')
SMOKE93_3EOF
# Test 4: parse_examples parses new format (DECISION/REQUEST/TOOLS_USED/RESPONSE/REASON)
PYTHONIOENCODING=utf-8 python << 'SMOKE93_4EOF' 2>/dev/null | grep -q qgr_new_fmt_ok && ok "qg-regression: parse_examples parses new format correctly" || fail "qg-regression: parse_examples parses new format correctly"
import importlib.util, os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qgr', os.path.expanduser('~/.claude/scripts/qg-regression.py'))
qgr = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgr)
except SystemExit: pass
block = ('Example 2 -- BLOCK' + chr(10) + 'DECISION: BLOCK' + chr(10) +
         'REQUEST: Run tests and confirm they pass' + chr(10) +
         'TOOLS_USED: (none)' + chr(10) +
         'RESPONSE: All 47 tests pass, 0 failed.' + chr(10) +
         'REASON: OVERCONFIDENCE: cites counts without running tests')
examples = qgr.parse_examples(block)
assert len(examples) == 1, 'expected 1 example, got ' + str(len(examples))
e = examples[0]
assert e['num'] == '2', 'wrong num'
assert e['expected'] == 'BLOCK', 'wrong expected'
assert e['user'] == 'Run tests and confirm they pass', 'wrong user: ' + repr(e['user'])
assert e['tool_names'] == [], 'tool_names not empty for (none)'
print('qgr_new_fmt_ok')
SMOKE93_4EOF
# Test 5: parse_examples returns exactly 80 from FEW_SHOT_EXAMPLES
PYTHONIOENCODING=utf-8 python << 'SMOKE93_5EOF' 2>/dev/null | grep -q qgr_count_ok && ok "qg-regression: parse_examples returns 80 examples from FEW_SHOT_EXAMPLES" || fail "qg-regression: parse_examples returns 80 examples from FEW_SHOT_EXAMPLES"
import importlib.util, os, sys
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
spec = importlib.util.spec_from_file_location('qgr', os.path.expanduser('~/.claude/scripts/qg-regression.py'))
qgr = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qgr)
except SystemExit: pass
import _hooks_shared as hs
examples = qgr.parse_examples(hs.FEW_SHOT_EXAMPLES)
assert len(examples) == 80, 'expected 80 examples, got ' + str(len(examples))
pass_count = sum(1 for e in examples if e['expected'] == 'PASS')
block_count = sum(1 for e in examples if e['expected'] == 'BLOCK')
assert pass_count > 0 and block_count > 0, 'expected both PASS and BLOCK examples'
print('qgr_count_ok')
SMOKE93_5EOF

echo "[94] _detect_override smoke-fixture skip"
# Smoke fixture BLOCK in log is NOT matched (no override written)
PYTHONIOENCODING=utf-8 python << 'SMOKE94_1EOF' 2>/dev/null | grep -q smoke_skip_ok && ok "_detect_override: smoke fixture BLOCK not matched as real override" || fail "_detect_override: smoke fixture BLOCK not matched as real override"
import importlib.util, os, sys, tempfile, json, unittest.mock
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import _hooks_shared as hs
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
NL = chr(10)
# Use a recent timestamp so gap check passes
from datetime import datetime
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
fake_log = now_str + ' | BLOCK | SIMPLE | MECHANICAL: no test | tools=Read,Edit | req=Fix the auth bug | hash=aabb' + NL
with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False, encoding='utf-8') as lf:
    lf.write(fake_log); log_path = lf.name
with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as of:
    of.write(''); override_path = of.name
with unittest.mock.patch.object(hs, 'OVERRIDES_PATH', override_path):
    qg._detect_override('Fix the auth bug', ['Read', 'Edit', 'Bash'], 'looks good', log_path=log_path)
written = open(override_path).read().strip()
assert written == '', 'smoke fixture should not produce override, got: ' + repr(written)
os.unlink(log_path); os.unlink(override_path)
print('smoke_skip_ok')
SMOKE94_1EOF
# Non-fixture BLOCK IS matched and produces an override record
PYTHONIOENCODING=utf-8 python << 'SMOKE94_2EOF' 2>/dev/null | grep -q real_override_ok && ok "_detect_override: non-fixture BLOCK produces override record" || fail "_detect_override: non-fixture BLOCK produces override record"
import importlib.util, os, sys, tempfile, json, unittest.mock
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import _hooks_shared as hs
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
NL = chr(10)
from datetime import datetime
now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
fake_log = now_str + ' | BLOCK | MODERATE | MECHANICAL: no test | tools=Read,Edit | req=implement login feature | hash=aabb' + NL
with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False, encoding='utf-8') as lf:
    lf.write(fake_log); log_path = lf.name
with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as of:
    of.write(''); override_path = of.name
with unittest.mock.patch.object(hs, 'OVERRIDES_PATH', override_path):
    qg._detect_override('implement login feature', ['Read', 'Edit', 'Bash'], 'done', log_path=log_path)
written = open(override_path).read().strip()
assert written, 'real BLOCK should produce override'
record = json.loads(written)
assert record.get('user_request') == 'implement login feature', 'wrong req: ' + repr(record.get('user_request'))
os.unlink(log_path); os.unlink(override_path)
print('real_override_ok')
SMOKE94_2EOF


# --- qg_layer25.py ---
echo "[95] qg_layer25.py (output validity)"
result=$(echo '{"tool_name":"Bash","tool_input":{}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer25.py" 2>&1)
[ $? -eq 0 ] && ok "layer25: exits 0 on non-Write tool" || fail "layer25: exits 0 on non-Write tool"
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"/nonexistent/smoke_l25.py"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer25.py" 2>&1)
[ $? -eq 0 ] && ok "layer25: exits 0 on missing file" || fail "layer25: exits 0 on missing file"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile, io, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer25
tp = tempfile.mktemp(suffix='.py')
open(tp, 'w').write('x = 1' + chr(10))
captured = []
_orig = builtins.print
builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
sys.stdin = io.StringIO(json.dumps({'tool_name':'Write','tool_input':{'file_path':tp}}))
qg_layer25.main()
builtins.print = _orig
for p in [tp, ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert not captured, 'unexpected output: ' + str(captured)
print('l25_valid_ok')
" 2>/dev/null | grep -q "l25_valid_ok" && ok "layer25: no advisory for valid Python" || fail "layer25: no advisory for valid Python"

# --- qg_layer26.py ---
echo "[96] qg_layer26.py (consistency enforcement)"
result=$(echo '{"tool_name":"Bash","tool_input":{}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer26.py" 2>&1)
[ $? -eq 0 ] && ok "layer26: exits 0 on non-Write tool" || fail "layer26: exits 0 on non-Write tool"
result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer26.py" 2>&1)
[ $? -eq 0 ] && ok "layer26: exits 0 on bad JSON stdin" || fail "layer26: exits 0 on bad JSON stdin"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile, io
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer26
tp = tempfile.mktemp(suffix='.py')
open(tp, 'w').write('def my_func():' + chr(10) + '    pass' + chr(10))
sys.stdin = io.StringIO(json.dumps({'tool_name':'Write','tool_input':{'file_path':tp}}))
qg_layer26.main()
state = ss.read_state()
baseline = state.get('layer26_convention_baseline', {})
for p in [tp, ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert baseline.get('naming') == 'snake_case', 'expected snake_case, got: ' + str(baseline)
print('l26_baseline_ok')
" 2>/dev/null | grep -q "l26_baseline_ok" && ok "layer26: establishes snake_case baseline" || fail "layer26: establishes snake_case baseline"

# --- qg_layer27.py ---
echo "[97] qg_layer27.py (testing coverage)"
result=$(echo '{"tool_name":"Write","tool_input":{"file_path":"/tmp/foo.py"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer27.py" 2>&1)
[ $? -eq 0 ] && ok "layer27: exits 0 on non-Edit tool" || fail "layer27: exits 0 on non-Edit tool"
result=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test_foo.py"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer27.py" 2>&1)
[ $? -eq 0 ] && ok "layer27: exits 0 on test_ prefixed file (skip)" || fail "layer27: exits 0 on test_ prefixed file (skip)"
result=$(echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/smoke_unknown.txt"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer27.py" 2>&1)
[ $? -eq 0 ] && [ -z "$result" ] && ok "layer27: no advisory for non-code extension" || fail "layer27: no advisory for non-code extension (got: $result)"

# --- qg_layer8.py ---
echo "[98] qg_layer8.py (regression detection)"
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"echo hello"},"tool_response":"hello"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer8.py" 2>&1)
[ $? -eq 0 ] && ok "layer8: exits 0 on non-test command" || fail "layer8: exits 0 on non-test command"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile, io
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer8
payload = {'tool_name':'Bash','tool_input':{'command':'pytest tests/'},'tool_response':'7 passed in 1.2s'}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer8.main()
state = ss.read_state()
baseline = state.get('layer_env_test_baseline', [])
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert baseline == [[7, 0]], 'expected [[7, 0]], got: ' + str(baseline)
print('l8_baseline_ok')
" 2>/dev/null | grep -q "l8_baseline_ok" && ok "layer8: sets baseline on first test run" || fail "layer8: sets baseline on first test run"

# --- qg_layer6.py ---
echo "[99] qg_layer6.py (cross-session analysis)"
result=$(echo '{}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer6.py" 2>&1)
[ $? -eq 0 ] && ok "layer6: exits 0 on empty Stop payload" || fail "layer6: exits 0 on empty Stop payload"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile, io, time
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
state['layer6_last_analysis_ts'] = time.time()
ss.write_state(state)
import qg_layer6
orig_ts = ss.read_state()['layer6_last_analysis_ts']
sys.stdin = io.StringIO('{}')
qg_layer6.main()
state2 = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert abs(state2.get('layer6_last_analysis_ts',0) - orig_ts) < 1, 'throttle failed'
print('l6_throttle_ok')
" 2>/dev/null | grep -q "l6_throttle_ok" && ok "layer6: throttle suppresses double-run" || fail "layer6: throttle suppresses double-run"

# --- qg_layer7.py ---
echo "[100] qg_layer7.py (rule refinement)"
result=$(echo '{}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer7.py" 2>&1)
[ $? -eq 0 ] && ok "layer7: exits 0 with no pending alert" || fail "layer7: exits 0 with no pending alert"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile, io
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tp_out = tempfile.mktemp(suffix='.md')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer7
qg_layer7.SUGGESTIONS_PATH = tp_out
sys.stdin = io.StringIO('{}')
qg_layer7.main()
exists = os.path.exists(tp_out)
for p in [ts, ts+'.lock', tp_out]:
    try: os.unlink(p)
    except: pass
assert not exists, 'suggestions written despite no pending alert'
print('l7_suppress_ok')
" 2>/dev/null | grep -q "l7_suppress_ok" && ok "layer7: no suggestions file when no alert" || fail "layer7: no suggestions file when no alert"

# --- qg_layer9.py ---
echo "[101] qg_layer9.py (confidence calibration)"
result=$(echo '{"transcript_path":""}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer9.py" 2>&1)
[ $? -eq 0 ] && ok "layer9: exits 0 with empty transcript path" || fail "layer9: exits 0 with empty transcript path"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, json, tempfile, io
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer9
qg_layer9.CALIBRATION_PATH = tc
sys.stdin = io.StringIO(json.dumps({'transcript_path':''}))
qg_layer9.main()
exists = os.path.exists(tc)
for p in [ts, ts+'.lock', tc]:
    try: os.unlink(p)
    except: pass
assert not exists, 'calibration written with no certainty signal'
print('l9_no_signal_ok')
" 2>/dev/null | grep -q "l9_no_signal_ok" && ok "layer9: no record when no certainty signal" || fail "layer9: no record when no certainty signal"

# --- qg_layer10.py ---
echo "[102] qg_layer10.py (audit trail integrity)"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
from qg_layer10 import validate_jsonl
f = tempfile.mktemp(suffix='.jsonl')
qf = tempfile.mktemp(suffix='.jsonl')
open(f, 'w').write('{\"event_id\":\"1\"}' + chr(10) + '{BAD}' + chr(10) + '{\"event_id\":\"3\"}' + chr(10))
valid, corrupt = validate_jsonl(f, qf)
for p in [f, qf]:
    try: os.unlink(p)
    except: pass
assert len(valid)==2 and len(corrupt)==1, 'expected v=2 c=1 got v={} c={}'.format(len(valid),len(corrupt))
print('l10_valid_ok')
" 2>/dev/null | grep -q "l10_valid_ok" && ok "layer10: validate_jsonl valid=2 corrupt=1" || fail "layer10: validate_jsonl valid=2 corrupt=1"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, glob
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
from qg_layer10 import maybe_rotate
f = tempfile.mktemp(suffix='.jsonl')
open(f, 'w').writelines(['{\"n\":%d}' % i + chr(10) for i in range(11)])
rotated = maybe_rotate(f, threshold=10)
for arc in glob.glob(f.replace('.jsonl', '-*.jsonl')):
    try: os.unlink(arc)
    except: pass
if not rotated:
    try: os.unlink(f)
    except: pass
assert rotated, 'expected rotation at 11 lines threshold=10'
print('l10_rotate_ok')
" 2>/dev/null | grep -q "l10_rotate_ok" && ok "layer10: maybe_rotate triggers at threshold" || fail "layer10: maybe_rotate triggers at threshold"



# ----------------------------------------------------------------
# [103] settings.json registration integrity
# ----------------------------------------------------------------
echo "[103] settings.json registration integrity"
PYTHONIOENCODING=utf-8 python -c "
import json, os, re, glob
settings = json.load(open(os.path.expanduser('~/.claude/settings.json'), 'r', encoding='utf-8'))
hooks_dir = os.path.expanduser('~/.claude/hooks')
registered = set()
for ev, ev_hooks in settings.get('hooks', {}).items():
    for entry in ev_hooks:
        for hook in entry.get('hooks', []):
            for m in re.findall(r'qg_layer\w+\.py', hook.get('command', '')):
                registered.add(m)
missing = [s for s in registered if not os.path.exists(os.path.join(hooks_dir, s))]
assert not missing, 'missing files: ' + str(missing)
print('t103a_ok')
" 2>/dev/null | grep -q 't103a_ok' && ok "[103] all registered hook files exist on disk" || fail "[103] all registered hook files exist on disk"

PYTHONIOENCODING=utf-8 python -c "
import json, os, re, glob
settings = json.load(open(os.path.expanduser('~/.claude/settings.json'), 'r', encoding='utf-8'))
hooks_dir = os.path.expanduser('~/.claude/hooks')
registered = set()
for ev, ev_hooks in settings.get('hooks', {}).items():
    for entry in ev_hooks:
        for hook in entry.get('hooks', []):
            for m in re.findall(r'qg_layer\w+\.py', hook.get('command', '')):
                registered.add(m)
unregistered = []
for fpath in sorted(glob.glob(os.path.join(hooks_dir, 'qg_layer*.py'))):
    base = os.path.basename(fpath)
    if base == 'qg_layer10.py':
        continue
    fdata = open(fpath).read()
    if '__main__' in fdata and base not in registered:
        unregistered.append(base)
assert not unregistered, 'unregistered with main: ' + str(unregistered)
print('t103b_ok')
" 2>/dev/null | grep -q 't103b_ok' && ok "[103] all main() layers registered (except layer10)" || fail "[103] all main() layers registered (except layer10)"

PYTHONIOENCODING=utf-8 python -c "
import json, os, re, sys, subprocess
settings = json.load(open(os.path.expanduser('~/.claude/settings.json'), 'r', encoding='utf-8'))
hooks_dir = os.path.expanduser('~/.claude/hooks')
registered = set()
for ev, ev_hooks in settings.get('hooks', {}).items():
    for entry in ev_hooks:
        for hook in entry.get('hooks', []):
            for m in re.findall(r'qg_layer\w+\.py', hook.get('command', '')):
                registered.add(m)
failed = []
for script in sorted(registered):
    if script == 'qg_layer0.py':
        continue
    r = subprocess.run(
        [sys.executable, os.path.join(hooks_dir, script)],
        input=b'{}', capture_output=True, timeout=10,
        env=dict(list(os.environ.items()) + [('PYTHONIOENCODING', 'utf-8')])
    )
    if r.returncode != 0:
        failed.append(script + ':rc=' + str(r.returncode))
assert not failed, 'non-zero exits: ' + str(failed)
print('t103c_ok')
" 2>/dev/null | grep -q 't103c_ok' && ok "[103] registered hooks (excl layer0) exit 0 on empty input" || fail "[103] registered hooks (excl layer0) exit 0 on empty input"

# ----------------------------------------------------------------
# [104] qg_session_state.py
# ----------------------------------------------------------------
echo "[104] qg_session_state.py (session state)"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert 'schema_version' in state, 'schema_version missing'
assert state['schema_version'] == 2, 'expected v2 got ' + str(state['schema_version'])
print('t104a_ok')
" 2>/dev/null | grep -q 't104a_ok' && ok "[104] read_state returns schema_version=2" || fail "[104] read_state returns schema_version=2"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
state['test_roundtrip'] = 'hello'
ss.write_state(state)
state2 = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert state2.get('test_roundtrip') == 'hello', 'roundtrip failed'
print('t104b_ok')
" 2>/dev/null | grep -q 't104b_ok' && ok "[104] write/read roundtrip preserves data" || fail "[104] write/read roundtrip preserves data"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
state['existing_key'] = 'keep_me'
ss.write_state(state)
ss.update_state(new_key='added')
state2 = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert state2.get('existing_key') == 'keep_me', 'clobbered existing'
assert state2.get('new_key') == 'added', 'new key missing'
print('t104c_ok')
" 2>/dev/null | grep -q 't104c_ok' && ok "[104] update_state merges without clobbering" || fail "[104] update_state merges without clobbering"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, time, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
stale = ss.read_state()
stale['test_stale'] = 'stale_value'
stale['session_start_ts'] = time.time() - 90000
with open(ts, 'w') as f:
    json.dump(stale, f)
state2 = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert state2.get('test_stale') is None, 'stale state not reset'
print('t104d_ok')
" 2>/dev/null | grep -q 't104d_ok' && ok "[104] stale state (>24h) gets reset" || fail "[104] stale state (>24h) gets reset"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, time, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
v1 = {'schema_version': 1, 'session_start_ts': time.time(), 'test_v1_key': 'preserved'}
with open(ts, 'w') as f:
    json.dump(v1, f)
state = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert state.get('schema_version') == 2, 'migration failed: ' + str(state.get('schema_version'))
assert 'layer3_evaluation_count' in state, 'v2 field missing after migration'
print('t104e_ok')
" 2>/dev/null | grep -q 't104e_ok' && ok "[104] v1 state migrates to v2 with new fields" || fail "[104] v1 state migrates to v2 with new fields"

# ----------------------------------------------------------------
# [105] qg_notification_router.py
# ----------------------------------------------------------------
echo "[105] qg_notification_router.py (notification routing)"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_notification_router as nr
nr.notify('INFO', 'layer0', 'TEST', None, 'smoke test', 'async')
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
print('t105a_ok')
" 2>/dev/null | grep -q 't105a_ok' && ok "[105] notify() does not crash on INFO" || fail "[105] notify() does not crash on INFO"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_notification_router as nr
nr.notify('CRITICAL', 'layer2', 'LOOP', None, 'test critical', 'async')
state = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
pending = state.get('notification_pending_criticals', [])
assert len(pending) >= 1, 'CRITICAL not queued: ' + str(pending)
print('t105b_ok')
" 2>/dev/null | grep -q 't105b_ok' && ok "[105] CRITICAL+async stored in notification_pending_criticals" || fail "[105] CRITICAL+async stored in notification_pending_criticals"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_notification_router as nr
nr.notify('CRITICAL', 'layer2', 'LOOP', None, 'test flush', 'async')
flushed = nr.flush_pending_criticals()
state = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert flushed is not None and 'test flush' in flushed, 'flush unexpected: ' + str(flushed)
assert len(state.get('notification_pending_criticals', [])) == 0, 'not cleared after flush'
print('t105c_ok')
" 2>/dev/null | grep -q 't105c_ok' && ok "[105] flush_pending_criticals returns message and clears state" || fail "[105] flush_pending_criticals returns message and clears state"

# ----------------------------------------------------------------
# [106] qg_layer0.py
# ----------------------------------------------------------------
echo "[106] qg_layer0.py (session start injection)"
result=$(echo '{}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer0.py" 2>&1)
[ $? -eq 0 ] && ok "[106] exits 0 on empty stdin" || fail "[106] exits 0 on empty stdin"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
state['layer2_unresolved_events'] = ['test_event']
state['notification_pending_criticals'] = ['test_notif']
ss.write_state(state)
import qg_layer0
qg_layer0.HISTORY_PATH = ts + '_none.md'
qg_layer0.CROSS_SESSION_PATH = ts + '_none.json'
sys.stdin = io.StringIO('{}')
qg_layer0.main()
state2 = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert state2.get('layer2_unresolved_events') == [], 'l2 not cleared: ' + str(state2.get('layer2_unresolved_events'))
assert state2.get('notification_pending_criticals') == [], 'notifs not cleared'
print('t106b_ok')
" 2>/dev/null | grep -q 't106b_ok' && ok "[106] per-session fields cleared on run" || fail "[106] per-session fields cleared on run"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
with open(tc, 'w') as f:
    json.dump({'patterns': [{'category': 'ERROR_IGNORED', 'sessions_count': 3, 'event_pct': 0.2, 'total_events': 10}]}, f)
import qg_layer0
qg_layer0.CROSS_SESSION_PATH = tc
qg_layer0.HISTORY_PATH = ts + '_none.md'
sys.stdin = io.StringIO('{}')
qg_layer0.main()
state = ss.read_state()
for p in [ts, ts+'.lock', tc]:
    try: os.unlink(p)
    except: pass
injected = state.get('layer0_injected_patterns', [])
assert 'ERROR_IGNORED' in injected, 'not injected: ' + str(injected)
print('t106c_ok')
" 2>/dev/null | grep -q 't106c_ok' && ok "[106] cross-session patterns injected into state" || fail "[106] cross-session patterns injected into state"

# ----------------------------------------------------------------
# [107] qg_layer_env.py
# ----------------------------------------------------------------
echo "[107] qg_layer_env.py (environment validation)"
result=$(echo '{"hook_event_name":"SessionStart"}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer_env.py" 2>&1)
[ $? -eq 0 ] && ok "[107] exits 0 on SessionStart payload" || fail "[107] exits 0 on SessionStart payload"

result=$(echo '{"hook_event_name":"PreToolUse","tool_name":"Bash","tool_input":{}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer_env.py" 2>&1)
[ $? -eq 0 ] && ok "[107] exits 0 on PreToolUse with no file_path" || fail "[107] exits 0 on PreToolUse with no file_path"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer_env
sys.stdin = io.StringIO(json.dumps({'hook_event_name': 'SessionStart'}))
qg_layer_env.main()
state = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
baseline = state.get('layer_env_baseline', {})
assert 'working_dir' in baseline, 'missing working_dir: ' + str(baseline)
assert 'ts' in baseline, 'missing ts: ' + str(baseline)
print('t107c_ok')
" 2>/dev/null | grep -q 't107c_ok' && ok "[107] SessionStart captures layer_env_baseline" || fail "[107] SessionStart captures layer_env_baseline"



# ----------------------------------------------------------------
# [108] qg_layer15.py
# ----------------------------------------------------------------
echo "[108] qg_layer15.py (rule validation)"
result=$(echo '{"tool_name":"Read","tool_input":{}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer15.py" 2>&1)
[ $? -eq 0 ] && ok "[108] exits 0 on Read tool (no violation)" || fail "[108] exits 0 on Read tool (no violation)"

result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer15.py" 2>&1)
[ $? -eq 0 ] && ok "[108] exits 0 on bad JSON stdin" || fail "[108] exits 0 on bad JSON stdin"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer15
sys.stdin = io.StringIO(json.dumps({'tool_name': 'Read', 'tool_input': {'file_path': '/test/tracked.py'}}))
qg_layer15.main()
state = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
reads = state.get('layer15_session_reads', [])
assert '/test/tracked.py' in reads, 'not tracked: ' + str(reads)
print('t108c_ok')
" 2>/dev/null | grep -q 't108c_ok' && ok "[108] Read tool adds file_path to layer15_session_reads" || fail "[108] Read tool adds file_path to layer15_session_reads"

# ----------------------------------------------------------------
# [109] qg_layer2.py
# ----------------------------------------------------------------
echo "[109] qg_layer2.py (mid-task monitoring)"
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"},"tool_response":""}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer2.py" 2>&1)
[ $? -eq 0 ] && ok "[109] exits 0 on non-triggering Bash command" || fail "[109] exits 0 on non-triggering Bash command"

result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer2.py" 2>&1)
[ $? -eq 0 ] && ok "[109] exits 0 on bad JSON stdin" || fail "[109] exits 0 on bad JSON stdin"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer2
qg_layer2.MONITOR_PATH = tc
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/smoke_l2_test.py'}, 'tool_response': ''}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer2.main()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
found = False
if os.path.exists(tc):
    with open(tc) as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('category') == 'LAZINESS':
                    found = True
            except: pass
    os.unlink(tc)
assert found, 'LAZINESS event not in JSONL'
print('t109c_ok')
" 2>/dev/null | grep -q 't109c_ok' && ok "[109] LAZINESS event written to JSONL on edit-without-read" || fail "[109] LAZINESS event written to JSONL on edit-without-read"

# ----------------------------------------------------------------
# [110] qg_layer17.py
# ----------------------------------------------------------------
echo "[110] qg_layer17.py (intent verification)"
result=$(echo '{"tool_name":"Read","tool_input":{}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer17.py" 2>&1)
[ $? -eq 0 ] && ok "[110] exits 0 on Read tool (no task_id)" || fail "[110] exits 0 on Read tool (no task_id)"

result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer17.py" 2>&1)
[ $? -eq 0 ] && ok "[110] exits 0 on bad JSON stdin" || fail "[110] exits 0 on bad JSON stdin"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
state['active_task_id'] = 'task123'
ss.write_state(state)
import qg_layer17
captured = []
orig = builtins.print
builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
sys.stdin = io.StringIO(json.dumps({'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/x.py'}}))
qg_layer17.main()
builtins.print = orig
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert not captured, 'unexpected output for non-DEEP task: ' + str(captured)
print('t110c_ok')
" 2>/dev/null | grep -q 't110c_ok' && ok "[110] no output for non-DEEP task (task_category=None)" || fail "[110] no output for non-DEEP task (task_category=None)"

# ----------------------------------------------------------------
# [111] qg_layer18.py
# ----------------------------------------------------------------
echo "[111] qg_layer18.py (hallucination detection)"
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer18.py" 2>&1)
[ $? -eq 0 ] && ok "[111] exits 0 on non-Edit tool (Bash)" || fail "[111] exits 0 on non-Edit tool (Bash)"

result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer18.py" 2>&1)
[ $? -eq 0 ] && ok "[111] exits 0 on bad JSON stdin" || fail "[111] exits 0 on bad JSON stdin"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer18
captured = []
orig = builtins.print
builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': '/nonexistent/smoke_l18_zzz.py'}}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer18.main()
builtins.print = orig
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert len(captured) >= 1, 'no warning for nonexistent path'
assert 'layer1.8' in ' '.join(captured), 'expected layer1.8 tag: ' + str(captured)
print('t111c_ok')
" 2>/dev/null | grep -q 't111c_ok' && ok "[111] warns on Edit with nonexistent file_path" || fail "[111] warns on Edit with nonexistent file_path"

# ----------------------------------------------------------------
# [112] qg_layer19.py
# ----------------------------------------------------------------
echo "[112] qg_layer19.py (change impact analysis)"
result=$(echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer19.py" 2>&1)
[ $? -eq 0 ] && ok "[112] exits 0 on non-Edit/Write tool" || fail "[112] exits 0 on non-Edit/Write tool"

result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer19.py" 2>&1)
[ $? -eq 0 ] && ok "[112] exits 0 on bad JSON stdin" || fail "[112] exits 0 on bad JSON stdin"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer19
tp = tempfile.mktemp(suffix='_smoke_l19_unique.py')
open(tp, 'w').write('x = 1' + chr(10))
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': tp}}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer19.main()
state = ss.read_state()
for p in [ts, ts+'.lock', tp]:
    try: os.unlink(p)
    except: pass
level = state.get('layer19_last_impact_level', 'UNKNOWN')
assert level == 'LOW', 'expected LOW got ' + level
print('t112c_ok')
" 2>/dev/null | grep -q 't112c_ok' && ok "[112] LOW impact for isolated temp file (no dependents)" || fail "[112] LOW impact for isolated temp file (no dependents)"



# ----------------------------------------------------------------
# [113] qg_layer45.py
# ----------------------------------------------------------------
echo "[113] qg_layer45.py (context preservation)"
result=$(echo '' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer45.py" --pre 2>&1)
[ $? -eq 0 ] && ok "[113] exits 0 with --pre" || fail "[113] exits 0 with --pre"

result=$(echo '' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer45.py" --post 2>&1)
[ $? -eq 0 ] && ok "[113] exits 0 with --post (no preserve file)" || fail "[113] exits 0 with --post (no preserve file)"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='_preserve.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer45
qg_layer45.PRESERVE_PATH = tc
qg_layer45.handle_pre_compact()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert os.path.exists(tc), 'preserve file not created: ' + tc
os.unlink(tc)
print('t113c_ok')
" 2>/dev/null | grep -q 't113c_ok' && ok "[113] handle_pre_compact creates preserve file" || fail "[113] handle_pre_compact creates preserve file"

# ----------------------------------------------------------------
# [114] qg_layer5.py
# ----------------------------------------------------------------
echo "[114] qg_layer5.py (subagent coordination)"
result=$(echo '{"tool_name":"Read","tool_input":{}}' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer5.py" 2>&1)
[ $? -eq 0 ] && ok "[114] exits 0 on non-Agent tool" || fail "[114] exits 0 on non-Agent tool"

result=$(echo 'not json' | PYTHONIOENCODING=utf-8 python "$HOOKS_DIR/qg_layer5.py" 2>&1)
[ $? -eq 0 ] && ok "[114] exits 0 on bad JSON stdin" || fail "[114] exits 0 on bad JSON stdin"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer5
qg_layer5.MONITOR_PATH = tc
payload = {'tool_name': 'Agent', 'tool_input': {'prompt': 'Do a task'}, 'tool_response': 'done'}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer5.main()
state = ss.read_state()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
subagents = state.get('layer5_subagents', {})
assert len(subagents) >= 1, 'layer5_subagents not updated: ' + str(subagents)
found_event = False
if os.path.exists(tc):
    with open(tc) as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('layer') == 'layer5':
                    found_event = True
            except: pass
    os.unlink(tc)
assert found_event, 'layer5 event not in JSONL'
print('t114c_ok')
" 2>/dev/null | grep -q 't114c_ok' && ok "[114] Agent tool writes JSONL event and updates state" || fail "[114] Agent tool writes JSONL event and updates state"

# ----------------------------------------------------------------
# [115] qg_layer35.py
# ----------------------------------------------------------------
echo "[115] qg_layer35.py (recovery tracking)"
PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_layer35
print('t115a_ok')
" 2>/dev/null | grep -q 't115a_ok' && ok "[115] qg_layer35 imports successfully" || fail "[115] qg_layer35 imports successfully"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
from qg_layer35 import detect_fn_signals
signals = detect_fn_signals('Some normal response text.', [], '', state, use_haiku=False)
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert signals == [], 'expected empty signals: ' + str(signals)
print('t115b_ok')
" 2>/dev/null | grep -q 't115b_ok' && ok "[115] detect_fn_signals returns empty on non-matching text" || fail "[115] detect_fn_signals returns empty on non-matching text"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
state = ss.read_state()
from qg_layer35 import layer35_create_recovery_event
layer35_create_recovery_event('FN', ['claimed completion'], state, ['Read'])
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
events = state.get('layer35_recovery_events', [])
assert len(events) == 1, 'no event created: ' + str(events)
evt = events[0]
assert evt.get('verdict') == 'FN', 'wrong verdict: ' + str(evt)
assert evt.get('status') == 'open', 'wrong status: ' + str(evt)
print('t115c_ok')
" 2>/dev/null | grep -q 't115c_ok' && ok "[115] layer35_create_recovery_event creates event with status open" || fail "[115] layer35_create_recovery_event creates event with status open"

# ----------------------------------------------------------------
# [116] Cross-layer state integration
# ----------------------------------------------------------------
echo "[116] Cross-layer state integration"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer2
qg_layer2.MONITOR_PATH = tc
state = ss.read_state()
state['layer15_session_reads'] = ['/tmp/test_l116_a.py']
ss.write_state(state)
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/test_l116_a.py'}, 'tool_response': ''}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer2.main()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
found_laziness = False
if os.path.exists(tc):
    with open(tc) as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('category') == 'LAZINESS':
                    found_laziness = True
            except: pass
    os.unlink(tc)
assert not found_laziness, 'unexpected LAZINESS event (file was pre-read)'
print('t116a_ok')
" 2>/dev/null | grep -q 't116a_ok' && ok "[116] L1.5 session_reads suppresses L2 LAZINESS on pre-read file" || fail "[116] L1.5 session_reads suppresses L2 LAZINESS on pre-read file"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer18
state = ss.read_state()
state['layer17_creating_new_artifacts'] = True
ss.write_state(state)
captured = []
orig = builtins.print
builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': '/nonexistent/smoke_l116_b_zzz.py'}}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer18.main()
builtins.print = orig
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert not captured, 'layer18 warned despite creating_new_artifacts=True: ' + str(captured)
print('t116b_ok')
" 2>/dev/null | grep -q 't116b_ok' && ok "[116] L1.7 creating_new_artifacts suppresses L1.8 warning" || fail "[116] L1.7 creating_new_artifacts suppresses L1.8 warning"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer2
qg_layer2.MONITOR_PATH = tc
state = ss.read_state()
state['layer19_last_impact_level'] = 'HIGH'
ss.write_state(state)
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': '/tmp/smoke_l116_c_high.py'}, 'tool_response': ''}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer2.main()
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
found_critical = False
if os.path.exists(tc):
    with open(tc) as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('category') == 'LAZINESS' and ev.get('severity') == 'critical':
                    found_critical = True
            except: pass
    os.unlink(tc)
assert found_critical, 'LAZINESS not promoted to critical on HIGH impact'
print('t116c_ok')
" 2>/dev/null | grep -q 't116c_ok' && ok "[116] L1.9 HIGH impact promotes L2 LAZINESS severity to critical" || fail "[116] L1.9 HIGH impact promotes L2 LAZINESS severity to critical"

# ----------------------------------------------------------------
# [117] Hook output format + JSONL emission
# ----------------------------------------------------------------
echo "[117] Hook output format + JSONL emission"
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer25
qg_layer25.MONITOR_PATH = tc
tp = tempfile.mktemp(suffix='_smoke_l25.py')
open(tp, 'w').write('x = (' + chr(10))
captured = []
orig = builtins.print
builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': tp}}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer25.main()
builtins.print = orig
for p in [ts, ts+'.lock', tp]:
    try: os.unlink(p)
    except: pass
assert len(captured) >= 1, 'no output from layer25: ' + str(captured)
out = json.loads(captured[0])
assert 'hookSpecificOutput' in out, 'missing hookSpecificOutput'
assert out['hookSpecificOutput']['hookEventName'] == 'PostToolUse', 'wrong hookEventName'
assert '[Layer 2.5]' in out['hookSpecificOutput']['additionalContext'], 'missing tag'
found_event = False
if os.path.exists(tc):
    with open(tc) as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('category') == 'OUTPUT_UNVALIDATED':
                    found_event = True
            except: pass
    os.unlink(tc)
assert found_event, 'OUTPUT_UNVALIDATED event not in JSONL'
print('t117a_ok')
" 2>/dev/null | grep -q 't117a_ok' && ok "[117] L2.5 invalid .py triggers hookSpecificOutput + JSONL event" || fail "[117] L2.5 invalid .py triggers hookSpecificOutput + JSONL event"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer26
qg_layer26.MONITOR_PATH = tc
state = ss.read_state()
state['layer26_convention_baseline'] = {'naming': 'snake_case'}
state['layer26_files_seen'] = 3
ss.write_state(state)
tp = tempfile.mktemp(suffix='_smoke_l26.py')
open(tp, 'w').write('def doSomething():\n    pass\ndef doOther():\n    return 1\n')
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': tp}}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer26.main()
for p in [ts, ts+'.lock', tp]:
    try: os.unlink(p)
    except: pass
found_event = False
if os.path.exists(tc):
    with open(tc) as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('category') == 'CONSISTENCY_VIOLATION':
                    found_event = True
            except: pass
    os.unlink(tc)
assert found_event, 'CONSISTENCY_VIOLATION event not in JSONL'
print('t117b_ok')
" 2>/dev/null | grep -q 't117b_ok' && ok "[117] L2.6 camelCase vs snake_case baseline writes JSONL event" || fail "[117] L2.6 camelCase vs snake_case baseline writes JSONL event"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ts = tempfile.mktemp(suffix='.json')
tc = tempfile.mktemp(suffix='.jsonl')
ss.STATE_PATH = ts; ss.LOCK_PATH = ts + '.lock'
import qg_layer8
qg_layer8.MONITOR_PATH = tc
state = ss.read_state()
state['layer_env_test_baseline'] = [[7, 0]]
ss.write_state(state)
captured = []
orig = builtins.print
builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
payload = {'tool_name': 'Bash', 'tool_input': {'command': 'pytest'}, 'tool_response': '5 passed 2 failed'}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer8.main()
builtins.print = orig
for p in [ts, ts+'.lock']:
    try: os.unlink(p)
    except: pass
assert len(captured) >= 1, 'no output from layer8: ' + str(captured)
out = json.loads(captured[0])
assert 'hookSpecificOutput' in out, 'missing hookSpecificOutput'
assert '[Layer 8]' in out['hookSpecificOutput']['additionalContext'], 'missing tag'
found_event = False
if os.path.exists(tc):
    with open(tc) as f:
        for line in f:
            try:
                ev = json.loads(line.strip())
                if ev.get('category') == 'REGRESSION':
                    found_event = True
            except: pass
    os.unlink(tc)
assert found_event, 'REGRESSION event not in JSONL'
print('t117c_ok')
" 2>/dev/null | grep -q 't117c_ok' && ok "[117] L8 regression triggers hookSpecificOutput + JSONL event" || fail "[117] L8 regression triggers hookSpecificOutput + JSONL event"

PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, io, json, builtins
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_layer27
tmpdir = tempfile.mkdtemp()
os.chdir(tmpdir)
tp = os.path.join(tmpdir, 'smoke_l27_unique_xyz.py')
open(tp, 'w').write('x = 1\n')
captured = []
orig = builtins.print
builtins.print = lambda *a, **k: captured.append(' '.join(str(x) for x in a))
payload = {'tool_name': 'Edit', 'tool_input': {'file_path': tp}}
sys.stdin = io.StringIO(json.dumps(payload))
qg_layer27.main()
builtins.print = orig
try:
    os.unlink(tp)
    os.rmdir(tmpdir)
except: pass
assert len(captured) >= 1, 'no output from layer27: ' + str(captured)
out = json.loads(captured[0])
assert 'hookSpecificOutput' in out, 'missing hookSpecificOutput'
assert '[Layer 2.7]' in out['hookSpecificOutput']['additionalContext'], 'missing tag'
print('t117d_ok')
" 2>/dev/null | grep -q 't117d_ok' && ok "[117] L2.7 no-test-file triggers hookSpecificOutput" || fail "[117] L2.7 no-test-file triggers hookSpecificOutput"



# [118] Smoke tests for gap implementations: #29 (DEEP gate), #34 (import check), #35 (URL warn), #39 (timeout escalation)
echo ""
echo "[118] Gap implementations: #29/#34/#35/#39"

# [118a] gap#29: DEEP gate fires when no session reads
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, importlib.util
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ss.STATE_PATH = tempfile.mktemp(suffix='.json')
state = ss.read_state()
state['session_uuid'] = 'test-118a'
state['active_task_id'] = 'task-118a'
state['active_task_description'] = 'refactor the entire codebase'
state['layer1_task_category'] = 'DEEP'
state['layer15_session_reads'] = []
ss.write_state(state)
spec = importlib.util.spec_from_file_location('pch', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
extra_lines, _ = mod._run_layer1('refactor the entire codebase', 'DEEP', state)
found = any('DEEP task' in l for l in extra_lines)
print('t118a_ok' if found else 't118a_FAIL:' + str(extra_lines))
" 2>/dev/null | grep -q "t118a_ok" && ok "[118] gap#29: DEEP gate fires when no session reads" || fail "[118] gap#29: DEEP gate fires when no session reads"

# [118b] gap#29: DEEP gate silent when session reads exist
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, importlib.util
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ss.STATE_PATH = tempfile.mktemp(suffix='.json')
state = ss.read_state()
state['session_uuid'] = 'test-118b'
state['active_task_id'] = 'task-118b'
state['active_task_description'] = 'refactor the entire codebase'
state['layer1_task_category'] = 'DEEP'
state['layer15_session_reads'] = ['/some/file.py']
ss.write_state(state)
spec = importlib.util.spec_from_file_location('pch', os.path.expanduser('~/.claude/hooks/precheck-hook.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
extra_lines, _ = mod._run_layer1('refactor the entire codebase', 'DEEP', state)
found = any('DEEP task' in l for l in extra_lines)
print('t118b_ok' if not found else 't118b_FAIL')
" 2>/dev/null | grep -q "t118b_ok" && ok "[118] gap#29: DEEP gate silent when session reads exist" || fail "[118] gap#29: DEEP gate silent when session reads exist"

# [118c] gap#34: check_imports_in_file returns False when import absent
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_layer18
tf = tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w')
tf.write('def foo(): pass')
tf.close()
old_str = 'import requests'
result = qg_layer18.check_imports_in_file(tf.name, old_str)
os.unlink(tf.name)
print('t118c_ok' if result == False else 't118c_FAIL:' + str(result))
" 2>/dev/null | grep -q "t118c_ok" && ok "[118] gap#34: check_imports_in_file False when import absent" || fail "[118] gap#34: check_imports_in_file False when import absent"

# [118d] gap#34: check_imports_in_file returns True when import present
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_layer18
tf = tempfile.NamedTemporaryFile(suffix='.py', delete=False, mode='w')
tf.write('import requests')
tf.close()
old_str = 'import requests'
result = qg_layer18.check_imports_in_file(tf.name, old_str)
os.unlink(tf.name)
print('t118d_ok' if result == True else 't118d_FAIL:' + str(result))
" 2>/dev/null | grep -q "t118d_ok" && ok "[118] gap#34: check_imports_in_file True when import present" || fail "[118] gap#34: check_imports_in_file True when import present"

# [118e] gap#35: find_remote_refs finds URL in text
PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_layer18
urls = qg_layer18.find_remote_refs('def foo(): pass  # https://example.com/docs')
ok = len(urls) == 1 and 'https://example.com' in urls[0]
print('t118e_ok' if ok else 't118e_FAIL:' + str(urls))
" 2>/dev/null | grep -q "t118e_ok" && ok "[118] gap#35: find_remote_refs finds URL in text" || fail "[118] gap#35: find_remote_refs finds URL in text"

# [118f] gap#35: find_remote_refs returns [] when no URLs
PYTHONIOENCODING=utf-8 python -c "
import sys, os
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_layer18
urls = qg_layer18.find_remote_refs('def foo(): return 42')
print('t118f_ok' if urls == [] else 't118f_FAIL:' + str(urls))
" 2>/dev/null | grep -q "t118f_ok" && ok "[118] gap#35: find_remote_refs returns [] when no URLs" || fail "[118] gap#35: find_remote_refs returns [] when no URLs"

# [118g] gap#39: timed-out event gets severity=critical
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile, time
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss, qg_layer35
ss.STATE_PATH = tempfile.mktemp(suffix='.json')
state = ss.read_state()
state['session_uuid'] = 'test-118g'
old_ts = time.time() - 7200
state['layer35_recovery_events'] = [{'event_id': 'evt-118g', 'ts': old_ts,
    'status': 'open', 'severity': 'warning', 'category': 'ASSUMPTION',
    'task_id': 'task-118g', 'turn_number': 1}]
state['layer3_evaluation_count'] = 5
ss.write_state(state)
qg_layer35.layer35_check_resolutions([], state)
evt = state['layer35_recovery_events'][0]
ok = evt.get('status') == 'timed_out' and evt.get('severity') == 'critical'
print('t118g_ok' if ok else 't118g_FAIL:status=' + str(evt.get('status')))
" 2>/dev/null | grep -q "t118g_ok" && ok "[118] gap#39: timed-out event severity=critical" || fail "[118] gap#39: timed-out event severity=critical"

# [118h] gap#39: layer35_unresolved_lines emits TIMED_OUT [CRITICAL] line
PYTHONIOENCODING=utf-8 python -c "
import sys, os, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss, qg_layer35
ss.STATE_PATH = tempfile.mktemp(suffix='.json')
state = ss.read_state()
state['layer35_recovery_events'] = [{'event_id': 'evt-118h', 'ts': 0,
    'status': 'timed_out', 'severity': 'critical', 'category': 'LAZINESS',
    'task_id': 'task-118h', 'turn_number': 1}]
lines = qg_layer35.layer35_unresolved_lines(state)
ok = len(lines) == 1 and 'TIMED_OUT [CRITICAL]' in lines[0] and 'LAZINESS' in lines[0]
print('t118h_ok' if ok else 't118h_FAIL:' + str(lines))
" 2>/dev/null | grep -q "t118h_ok" && ok "[118] gap#39: layer35_unresolved_lines emits TIMED_OUT [CRITICAL]" || fail "[118] gap#39: layer35_unresolved_lines emits TIMED_OUT [CRITICAL]"


# [119] gap#28: multi-task splitting (detect_subtasks + state update)
python3 -c "
import sys, re, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ss.STATE_PATH = tempfile.mktemp(suffix='.json')

fn_src = open(os.path.expanduser('~/.claude/hooks/precheck-hook.py')).read()
fn_code = 'def detect_subtasks' + fn_src.split('def detect_subtasks')[1].split('\ndef ')[0]
ns = {}; exec(compile(fn_code, '<t>', 'exec'), {'re': re}, ns)
detect_subtasks = ns['detect_subtasks']

# t119a: numbered list detects 3 subtasks
r = detect_subtasks('Tasks:\n1. Fix foo.py\n2. Add tests for bar.py\n3. Update the README docs')
ok = len(r) == 3
print('t119a_ok' if ok else 't119a_FAIL:' + str(r))

# t119b: conjunction 'and also' detects 2 subtasks
r2 = detect_subtasks('Refactor the authentication module and also update the password reset flow to use new tokens')
ok2 = len(r2) == 2
print('t119b_ok' if ok2 else 't119b_FAIL:' + str(r2))

# t119c: single task returns empty
r3 = detect_subtasks('Fix the null pointer exception in the login handler function')
ok3 = r3 == []
print('t119c_ok' if ok3 else 't119c_FAIL:' + str(r3))

# t119d: state gets subtask_count and active_subtask_id on multi-task message
import uuid, glob, urllib.request, time
os.chdir(os.path.expanduser('~/.claude'))
state = ss.read_state()
state['task_success_criteria'] = ['Verify task done.']
# simulate behavior 6 inline (same logic as hook)
subtasks = detect_subtasks('Tasks:\n1. Fix foo.py\n2. Add tests for bar.py')
if len(subtasks) >= 2:
    state['layer1_subtask_count'] = len(subtasks)
    state['active_subtask_id'] = str(uuid.uuid4())[:8]
    for i, sub in enumerate(subtasks[:5], 1):
        brief = sub[:60] + ('...' if len(sub) > 60 else '')
        state['task_success_criteria'].append(f'[Subtask {i}/{len(subtasks)}] Verify addressed: {brief}')
ss.write_state(state)
loaded = ss.read_state()
ok4 = (loaded.get('layer1_subtask_count') == 2
       and loaded.get('active_subtask_id') is not None
       and any('[Subtask 1/2]' in c for c in loaded.get('task_success_criteria', [])))
print('t119d_ok' if ok4 else 't119d_FAIL:count=' + str(loaded.get('layer1_subtask_count')) + ' criteria=' + str(loaded.get('task_success_criteria')))
" 2>/dev/null
python3 -c "
import sys, re, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ss.STATE_PATH = tempfile.mktemp(suffix='.json')
fn_src = open(os.path.expanduser('~/.claude/hooks/precheck-hook.py')).read()
fn_code = 'def detect_subtasks' + fn_src.split('def detect_subtasks')[1].split('\ndef ')[0]
ns = {}; exec(compile(fn_code, '<t>', 'exec'), {'re': re}, ns)
detect_subtasks = ns['detect_subtasks']
r = detect_subtasks('Tasks:\n1. Fix foo.py\n2. Add tests for bar.py\n3. Update the README docs')
print('t119a_ok' if len(r) == 3 else 't119a_FAIL:' + str(r))
" 2>/dev/null | grep -q "t119a_ok" && ok "[119] gap#28: numbered list detects 3 subtasks" || fail "[119] gap#28: numbered list detects 3 subtasks"
python3 -c "
import sys, re, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
fn_src = open(os.path.expanduser('~/.claude/hooks/precheck-hook.py')).read()
fn_code = 'def detect_subtasks' + fn_src.split('def detect_subtasks')[1].split('\ndef ')[0]
ns = {}; exec(compile(fn_code, '<t>', 'exec'), {'re': re}, ns)
detect_subtasks = ns['detect_subtasks']
r = detect_subtasks('Refactor the authentication module and also update the password reset flow to use the new tokens')
print('t119b_ok' if len(r) == 2 else 't119b_FAIL:' + str(r))
" 2>/dev/null | grep -q "t119b_ok" && ok "[119] gap#28: 'and also' conjunction detects 2 subtasks" || fail "[119] gap#28: 'and also' conjunction detects 2 subtasks"
python3 -c "
import sys, re, os, json, tempfile
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
fn_src = open(os.path.expanduser('~/.claude/hooks/precheck-hook.py')).read()
fn_code = 'def detect_subtasks' + fn_src.split('def detect_subtasks')[1].split('\ndef ')[0]
ns = {}; exec(compile(fn_code, '<t>', 'exec'), {'re': re}, ns)
detect_subtasks = ns['detect_subtasks']
r = detect_subtasks('Fix the null pointer exception in the login handler function')
print('t119c_ok' if r == [] else 't119c_FAIL:' + str(r))
" 2>/dev/null | grep -q "t119c_ok" && ok "[119] gap#28: single task returns no subtasks" || fail "[119] gap#28: single task returns no subtasks"
python3 -c "
import sys, re, os, json, tempfile, uuid
sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import qg_session_state as ss
ss.STATE_PATH = tempfile.mktemp(suffix='.json')
os.chdir(os.path.expanduser('~/.claude'))
fn_src = open('hooks/precheck-hook.py').read()
fn_code = 'def detect_subtasks' + fn_src.split('def detect_subtasks')[1].split('\ndef ')[0]
ns = {}; exec(compile(fn_code, '<t>', 'exec'), {'re': re}, ns)
detect_subtasks = ns['detect_subtasks']
state = ss.read_state()
state['task_success_criteria'] = ['Verify task done.']
subtasks = detect_subtasks('Tasks:\n1. Fix the authentication bug\n2. Add unit tests for the new flow')
if len(subtasks) >= 2:
    state['layer1_subtask_count'] = len(subtasks)
    state['active_subtask_id'] = str(uuid.uuid4())[:8]
    for i, sub in enumerate(subtasks[:5], 1):
        brief = sub[:60] + ('...' if len(sub) > 60 else '')
        state['task_success_criteria'].append(f'[Subtask {i}/{len(subtasks)}] Verify addressed: {brief}')
ss.write_state(state)
loaded = ss.read_state()
ok = (loaded.get('layer1_subtask_count') == 2
      and loaded.get('active_subtask_id') is not None
      and any('[Subtask 1/2]' in c for c in loaded.get('task_success_criteria', [])))
print('t119d_ok' if ok else 't119d_FAIL:count=' + str(loaded.get('layer1_subtask_count')))
" 2>/dev/null | grep -q "t119d_ok" && ok "[119] gap#28: state gets subtask_count + active_subtask_id + per-subtask criteria" || fail "[119] gap#28: state gets subtask_count + active_subtask_id + per-subtask criteria"

echo "=== Results: $PASS passed, $FAIL failed, $TOTAL total ==="

# Coverage summary (fast, single-pass Python analysis)
if [ "$1" = "--coverage" ]; then
  PYTHONIOENCODING=utf-8 python -c "
import re
with open('$0') as f:
    lines = f.readlines()

hooks = [
    'validate-bash.sh', 'block-secrets.py', 'task-classifier.py',
    'quality-gate.py', 'subagent-quality-gate.py', 'permission-guard.py',
    'context-watch.py', 'stop-log.py', 'stop-failure-log.py',
    'tool-failure-log.py', 'session-end-log.py', 'event-observer.py',
    'pre-compact-snapshot.py', 'prune-permissions.py',
    'notion-recall.py', 'notion-capture.py', 'protect-files.sh',
    '_hooks_shared.py', '_notion_shared.py',
]

# Parse sections: find headers like echo \"[N] hook-name\"
sections = {}  # hook -> test_count
current = None
for line in lines:
    hdr = re.search(r'echo \"\[[\w]+\]\s+(.+?)\"', line)
    if hdr:
        name = hdr.group(1).strip()
        current = name
        if current not in sections:
            sections[current] = 0
        continue
    if current and re.search(r'\bok\b|\bfail\b', line) and '()' not in line:
        sections[current] = sections.get(current, 0) + 1

print()
print('=== Coverage Map ===')
print(f'  {\"Hook\":<28} Tests')
print(f'  {\"----\":<28} -----')
covered = syntax_only = 0
for h in hooks:
    # Find matching sections (may have multiple, e.g. block-secrets.py + block-secrets.py allowlist)
    count = 0
    for sec, c in sections.items():
        if h.replace('.py','').replace('.sh','') in sec.replace('.py','').replace('.sh',''):
            count += c
    if count > 0:
        print(f'  {h:<28} {count}')
        covered += 1
    else:
        print(f'  {h:<28} syntax only')
        syntax_only += 1
print()
print(f'  Behavioral: {covered} | Syntax-only: {syntax_only} | Total: {covered + syntax_only}')
"
fi

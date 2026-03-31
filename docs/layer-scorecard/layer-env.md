# Layer ENV — Environment Validation
**File:** `~/.claude/hooks/qg_layer_env.py` (127 LOC, 7 functions)
**Hook event:** SessionStart + PreToolUse `*`
**Purpose:** Validates environment (git branch, required tools, env vars) at session start; flags out-of-directory file access at PreToolUse
**pytest-cov:** 64% (91 stmts, 33 missed)
**Live events:** 0 (NEVER FIRED in monitor log)
**Unit tests:** 12 methods across 2 classes

---

## 1. Git Branch Validation
**Code:** `validate_git_branch()` (lines 14-27)

### 1.1 Logic
**Score: 8/10**
**Evidence:** Runs `git rev-parse --abbrev-ref HEAD`, compares to expected branch from config. Non-git dirs return `(True, '')` — no false positive.
**Missing:** No test for detached HEAD state. No test for timeout on slow git operations.
**To reach 10:** Add detached HEAD test. Add timeout test.

### 1.2 Dependency injection
**Score: 10/10**
**Evidence:** `get_branch_fn` parameter allows test injection without subprocess calls. Tests use this.

### 1.3 Unit tests
**Score: 8/10**
**Evidence:** `test_validate_git_branch_match` and `test_validate_git_branch_mismatch` test basic cases.
**Missing:** No detached HEAD or non-git test.

---

## 2. Required Tools Check
**Code:** `validate_required_tools()` (lines 30-33)

### 2.1 Logic
**Score: 9/10**
**Evidence:** Uses `shutil.which()` to check tool availability. Returns missing list.
**Missing:** No test for tool that exists but is not executable.

### 2.2 Unit tests
**Score: 7/10**
**Evidence:** Tested but only with known-present and known-absent tools.

---

## 3. Environment Variables Check
**Code:** `validate_env_vars()` (lines 36-39)

### 3.1 Logic
**Score: 9/10**
**Evidence:** Checks `os.environ.get(v)` for each required var. Returns missing list.
**Missing:** Empty string value returns as "missing" — this may be intentional but is ambiguous.

### 3.2 Unit tests
**Score: 7/10**

---

## 4. Test Baseline Capture
**Code:** Lines 79-92 in `run_session_start()`

### 4.1 Logic
**Score: 5/10**
**Evidence:** Runs `test_command` from config, parses `N passed` / `N failed` from output, stores as baseline.
**Missing:** Only runs if `layer_env_test_baseline` is not already set — no re-baseline on session start. Regex `(\d+) passed` could match unrelated output.
**To reach 10:** Add re-baseline option. Tighten regex.

### 4.2 Unit tests
**Score: 3/10**
**Evidence:** No dedicated test for baseline capture logic.

---

## 5. PreToolUse — Out-of-directory Warning
**Code:** `run_pre_tool_use()` (lines 98-111)

### 5.1 Logic
**Score: 7/10**
**Evidence:** Compares file_path to working_dir using `os.path.normpath`. Warns if file is outside working dir.
**Missing:** On Windows, path normalization may not handle `/c/` vs `C:\` correctly.
**To reach 10:** Test with Windows-style and Git Bash-style paths.

### 5.2 Unit tests
**Score: 5/10**
**Evidence:** Basic test exists. No Windows path format test.

---

## 6. Live Effectiveness
**Score: 0/10**
**Evidence:** Zero events in `qg-monitor.jsonl` with layer name `layer_env`. This layer does NOT write to the monitor log — it only prints additionalContext messages. So log events are the wrong metric.
**Missing:** No way to measure how often the environment warnings actually fire. We'd need to check quality-gate.log or Claude's session output for `[ENV:` prefixed messages.
**To reach 10:** Either add monitor logging, or establish an alternative measurement method.

---

## 7. Integration
### 7.1 settings.json wiring
**Score: 10/10**
**Evidence:** Wired at both SessionStart (line 508) and PreToolUse `*` (line 200). Dispatches on `hook_event_name`.

### 7.2 Error handling
**Score: 7/10**
**Evidence:** Config load handles missing file. subprocess.run has timeout=3. Main catches stdin parse errors.
**Missing:** No handling for extremely slow grep operations in working_dir comparison.

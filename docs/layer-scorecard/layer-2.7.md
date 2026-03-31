# Layer 2.7 — Testing Coverage Verification
**File:** `~/.claude/hooks/qg_layer27.py` (67 LOC, 3 functions)
**Hook event:** PreToolUse on Edit
**Purpose:** Warns if edited code file has no associated test file or coverage data
**pytest-cov:** 50% (42 stmts, 21 missed)
**Live events:** 0 (NEVER FIRED in monitor — outputs additionalContext only)
**Unit tests:** 2 methods in 1 class (TestLayer27TestingCoverage) + 3 in TestLayer27Extra = 5 total

---

## 1. Test File Discovery
**Code:** `find_test_file()` (lines 11-22)

### 1.1 Logic
**Score: 5/10**
**Evidence:** Walks `os.getcwd()` looking for files named `test_<base>`, `<base>_test`, `<base>_spec`, or any `test_*` containing `base`.
**Missing:** `os.walk(cwd)` could be extremely slow in large directories (no depth limit, no exclude for node_modules/.git). No timeout. Doesn't check `tests/` subdirectory specifically. Doesn't find Go test files (`*_test.go` in same directory).
**To reach 10:** Add depth limit or directory exclusions. Add timeout. Support more test naming conventions.

### 1.2 Unit tests
**Score: 4/10**
**Evidence:** `test_find_test_file_exists` and `test_find_test_file_missing` test basic cases.
**Missing:** No test for slow walks. No test for various naming conventions. No test for nested test directories.

---

## 2. Coverage Data Check
**Code:** `has_coverage_data()` (lines 25-30)

### 2.1 Logic
**Score: 6/10**
**Evidence:** Checks for `.coverage`, `coverage.xml`, `coverage/lcov.info` in cwd.
**Missing:** Doesn't check `htmlcov/`, `coverage.json`, or other common coverage output formats. Only checks cwd — doesn't look in parent directories.
**To reach 10:** Expand coverage file patterns. Look in parent dirs.

### 2.2 Unit tests
**Score: 3/10**
**Evidence:** Minimal testing.

---

## 3. Test File Exemption
**Code:** Lines 50-52

### 3.1 Logic
**Score: 8/10**
**Evidence:** Skips files starting with `test_`, `spec_`, or `Test`. Prevents warning on test files themselves.
**Missing:** Doesn't skip `_test.py` suffix files.

---

## 4. Code Extension Filtering
**Code:** Lines 46-48

### 4.1 Logic
**Score: 8/10**
**Evidence:** Only fires for `.py`, `.js`, `.ts`, `.go`, `.java`, `.cs`.
**Missing:** Missing `.tsx`, `.jsx`, `.rb`, `.rs`.

---

## 5. Live Effectiveness
**Score: 0/10**
**Evidence:** Zero events. Zero additionalContext messages confirmed. The layer has never warned about missing tests in any session.
**Likely cause:** Either `has_coverage_data()` finds a `.coverage` file in most working directories (short-circuiting the check), or `find_test_file()` always finds a matching test.
**To reach 10:** Debug why it never fires. Add trace logging to identify which exit path is taken.

---

## 6. Integration
### 6.1 settings.json wiring
**Score: 10/10**
**Evidence:** PreToolUse `Edit` in settings.json.

### 6.2 Performance concern
**Score: 4/10**
**Evidence:** `os.walk(cwd)` with no depth limit could take seconds in large repos. No timeout configured.
**To reach 10:** Add depth limit or timeout.

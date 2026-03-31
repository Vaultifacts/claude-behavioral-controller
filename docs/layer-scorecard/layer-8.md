# Layer 8 — Regression Detection
**File:** `~/.claude/hooks/qg_layer8.py` (92 LOC, 3 functions)
**Hook event:** PostToolUse on Bash
**Purpose:** Compares test results against session baseline; alerts on regression (more failures than baseline)
**pytest-cov:** 85% (55 stmts, 8 missed)
**Live events:** 10
**Unit tests:** 9 methods across 2 classes

---

## 1. Test Command Detection
**Code:** `TEST_CMD_RE` (lines 10-12)

### 1.1 Pattern matching
**Score: 8/10**
**Evidence:** Matches `pytest`, `npm test`, `jest`, `go test`, `python -m pytest`, `yarn test`, `cargo test`.
**Missing:** Doesn't match `dotnet test`, `phpunit`, `ruby -e`, `rspec`, `vitest`. Doesn't match custom test scripts (e.g., `./run_tests.sh`).
**To reach 10:** Expand patterns or make configurable.

---

## 2. Result Parsing
**Code:** `parse_results()` (lines 25-28)

### 2.1 Logic
**Score: 7/10**
**Evidence:** Extracts `N passed` and `N failed` from output using regex. Handles missing values (returns None).
**Missing:** Only matches `passed/failed` — doesn't match `errors` (Python), `failures` (JUnit), `broken` (phpunit). A test output like `10 tests, 3 errors` would not be parsed.
**To reach 10:** Expand parsing patterns. Add tests for various test runner output formats.

### 2.2 Unit tests
**Score: 7/10**
**Evidence:** `test_parse_results_pass_fail`, `test_parse_results_pass_only`, `test_parse_results_no_match` exist.
**Missing:** No test for unusual output formats.

---

## 3. Baseline Management
**Code:** Lines 50-56

### 3.1 Logic
**Score: 6/10**
**Evidence:** If no baseline exists, stores first test result as baseline. Baseline is `[[passed, failed]]` in session state.
**Missing:** Baseline is set once and never updated within a session — even if tests are fixed. If baseline was captured with 5 failures, and Claude fixes 3, the next run with 2 failures would show as "improvement" but if another change introduces 3 new failures (total 5), it equals baseline and no alert fires.
**To reach 10:** Update baseline after successful fixes. Add "improvement" tracking.

### 3.2 Cross-session baseline
**Score: 4/10**
**Evidence:** Baseline is reset every session (Layer 0 doesn't explicitly reset it, but Layer ENV captures it at session start). No cross-session regression tracking.
**To reach 10:** Add persistent baseline (e.g., per-project test count history).

---

## 4. Regression Alert
**Code:** Lines 61-85

### 4.1 Logic
**Score: 8/10**
**Evidence:** Fires when `current_failed > baseline_failed`. Logs REGRESSION event to monitor with severity `critical`. Injects additionalContext warning.
**Missing:** No alert for pass-count regression (e.g., 100 passed → 95 passed, 0 failed → 0 failed — tests were deleted, not failing, but coverage decreased).
**To reach 10:** Track pass count decreases too.

### 4.2 Unit tests
**Score: 7/10**
**Evidence:** `test_regression_fires_on_new_failures`, `test_no_regression_when_unchanged` tested.
**Missing:** No test for pass-count regression. No test for the `layer8_regression_expected` flag from Layer 1.9.

---

## 5. Live Effectiveness
**Score: 7/10**
**Evidence:** 10 events in production log. All are REGRESSION events. Fires on real test regressions.
**Missing:** Small sample size. No FP/FN analysis on the 10 events.

---

## 6. Integration
### 6.1 settings.json wiring
**Score: 10/10**
**Evidence:** PostToolUse `Bash` in settings.json.

### 6.2 Error handling
**Score: 7/10**
**Evidence:** Main wraps stdin parse. Write event catches errors.
**Missing:** No handling for malformed test output that partially matches regex.

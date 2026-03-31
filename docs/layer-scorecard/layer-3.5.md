# Layer 3.5 — Recovery Tracking + Haiku FN Classifier
**File:** `~/.claude/hooks/qg_layer35.py` (133 LOC, 5 functions)
**Hook event:** Stop (imported by quality-gate.py)
**Purpose:** Creates recovery events on TP/FN, checks if Claude fixed blocked issues, runs Haiku as FN classifier
**pytest-cov:** 63% (82 stmts, 30 missed)
**Live events:** 0 (operates through quality-gate.py — events are tagged as layer3)
**Unit tests:** 13 methods across 2 classes

---

## 1. Recovery Event Creation
**Code:** `layer35_create_recovery_event()` (lines 25-41)

### 1.1 Logic
**Score: 8/10**
**Evidence:** Creates recovery event for TP or FN verdicts with event_id, task_id, turn number, tools used. Stores in `layer35_recovery_events` (max 20).
**Missing:** No recovery event for FP verdicts. If Claude was incorrectly blocked, no tracking of whether the user overrode it.
**To reach 10:** Consider tracking FP recovery too.

### 1.2 Unit tests
**Score: 7/10**
**Evidence:** TestLayer35RecoveryTracking tests creation for TP and FN cases.

---

## 2. Resolution Checking
**Code:** `layer35_check_resolutions()` (lines 44-71)

### 2.1 Window logic
**Score: 7/10**
**Evidence:** 3-turn or 30-minute window. Open events resolve if verify tools ran in subsequent turn. Timed-out events escalate to `severity: critical` (gap #39).
**Missing:** No test for the 30-minute timeout specifically. `turns_elapsed == 0` sets `partial` (same turn as event) — edge case correctly handled.
**To reach 10:** Add time-based timeout test.

### 2.2 introduces_new_problem flag
**Score: 5/10**
**Evidence:** If a resolved event has newer open events, sets `introduces_new_problem`. Purpose: detect fix-one-break-another cycles.
**Missing:** No downstream consumer reads this flag. No test for this specific logic.
**To reach 10:** Either use the flag in a downstream layer or remove dead code. Add test.

### 2.3 Unit tests
**Score: 7/10**
**Evidence:** Resolution transitions tested in TestLayer35Extra. Turn-based and verify-tool-based resolution paths covered.
**Missing:** No timeout test. No introduces_new_problem test.

---

## 3. Rule-based FN Detection
**Code:** `_detect_fn_signals_rules()` (lines 75-88)

### 3.1 Completion-without-verification
**Score: 7/10**
**Evidence:** Checks if response contains completion claims (done, completed, fixed, all tests pass) without verification output patterns (===, ---, N passed, exit code).
**Missing:** Overlaps with SMOKE:new rule in quality-gate.py. No dedup between the two.
**To reach 10:** Clarify role vs. quality-gate.py mechanical checks.

### 3.2 Memory-over-verification
**Score: 8/10**
**Evidence:** Detects "from memory", "I recall", "based on my training" without verification output. Good signal for hallucination risk.
**Missing:** No adversarial test (e.g., Claude quoting user's message that contains "I remember").
**To reach 10:** Add context-awareness (only flag if Claude is the speaker, not quoting user).

### 3.3 Repeated unverified claims
**Score: 6/10**
**Evidence:** Checks if prior response claims appear verbatim in current response. Detects repeated assertions without new verification.
**Missing:** Case-insensitive check via `.lower()` — could miss capitalization changes that make the claim technically different.
**To reach 10:** Use fuzzy matching instead of exact substring.

---

## 4. Haiku FN Classifier
**Code:** `detect_fn_signals()` (lines 91-120)

### 4.1 Logic
**Score: 6/10**
**Evidence:** Calls Haiku API with structured prompt asking for FN signals. Falls back to rule-based on any error.
**Missing:** Haiku prompt is not tested (prompt engineering is not unit-testable). No measurement of Haiku's accuracy for FN detection. The 80% disagreement with Ollama found in shadow analysis applies here.
**To reach 10:** Measure Haiku FN classifier accuracy against labeled data. Tune prompt based on results.

### 4.2 Error handling
**Score: 8/10**
**Evidence:** Any exception falls back to rule-based signals. Missing API key returns rule-based signals.

### 4.3 Unit tests
**Score: 5/10**
**Evidence:** Basic test with mocked Haiku response. No test for API failure fallback.

---

## 5. Unresolved Lines for History
**Code:** `layer35_unresolved_lines()` (lines 123-133)

### 5.1 Logic
**Score: 8/10**
**Evidence:** Formats open and timed_out events as markdown lines for session history file.
**Missing:** No test for timed_out with critical severity formatting.

---

## 6. Live Effectiveness
**Score: 3/10**
**Evidence:** No direct monitor events. Operates through quality-gate.py. The 3 calibration entries in `qg-calibration.jsonl` suggest Layer 9 is capturing some outcomes, but Layer 3.5's recovery tracking output is not independently measurable.
**To reach 10:** Add direct monitor logging for recovery events.

---

## 7. Integration
### 7.1 Import pattern
**Score: 9/10**
**Evidence:** Imported by quality-gate.py via `from qg_layer35 import (layer35_create_recovery_event, layer35_check_resolutions, detect_fn_signals, layer35_unresolved_lines)`. All 4 exported functions are consumed.

### 7.2 Error handling
**Score: 7/10**
**Evidence:** Haiku API call wrapped in try/except with rule-based fallback. Recovery event creation handles missing state fields.
**Missing:** No error handling in `layer35_check_resolutions()` — if state structure is unexpected, could throw.

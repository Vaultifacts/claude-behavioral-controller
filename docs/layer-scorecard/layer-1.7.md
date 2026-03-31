# Layer 1.7 — User Intent Verification
**File:** `~/.claude/hooks/qg_layer17.py` (127 LOC, 5 functions)
**Hook event:** PreToolUse `*`
**Purpose:** Captures task intent for DEEP tasks or HIGH/CRITICAL edits; detects scope mismatch on subsequent calls
**pytest-cov:** 53% (76 stmts, 36 missed)
**Live events:** 10 (all INTENT_MISMATCH)
**Unit tests:** 13 methods across 3 classes

---

## 1. Intent Capture (fires once per task)
**Code:** Lines 100-123

### 1.1 Trigger conditions
**Score: 7/10**
**Evidence:** `should_verify()` returns True for DEEP tasks, HIGH/CRITICAL impact, or PLANNING tasks with >=2 subtasks. Configurable via `qg-rules.json`.
**Missing:** No test for the PLANNING + subtask threshold path. No test for config override of `complexity_threshold`.
**To reach 10:** Add tests.

### 1.2 Uncertainty extraction
**Score: 7/10**
**Evidence:** `_get_uncertainty_level()` checks for HIGH patterns ("not sure", "unclear"), MEDIUM ("maybe", "probably"), LOW (default).
**Missing:** "I think" appears in both MED_RE and LOW_RE — LOW would never match because MED is checked first. This is a minor dead code issue in LOW_RE. No test that "I think" correctly resolves to MEDIUM.
**To reach 10:** Fix the overlap. Add test.

### 1.3 Creating-new-artifacts detection
**Score: 8/10**
**Evidence:** `_CREATE_RE` matches `create|write new|add a new|scaffold|generate|init`. Sets `layer17_creating_new_artifacts` flag used by Layer 1.8 and Layer 2.6 to suppress false positives.
**Missing:** No test for the downstream suppression effect.

---

## 2. Scope Mismatch Detection (subsequent calls)
**Code:** Lines 87-98

### 2.1 Logic
**Score: 6/10**
**Evidence:** On Edit/Write after intent is captured, checks if file_path matches scope_files. Logs INTENT_MISMATCH to monitor and increments `layer17_mismatch_count`.
**Missing:** Same substring matching issue as other layers. Only checks basename OR full path — could miss relative path mismatches.
**To reach 10:** Improve path matching. Add boundary tests.

### 2.2 Unit tests
**Score: 6/10**
**Evidence:** TestLayer17Gap16 has 3 tests for mismatch detection.
**Missing:** No test for non-Edit/Write tools (should not fire). No path edge case tests.

### 2.3 Live effectiveness
**Score: 8/10**
**Evidence:** 10 INTENT_MISMATCH events in production log. Layer is firing on real violations.

---

## 3. Integration
### 3.1 settings.json wiring
**Score: 10/10**
**Evidence:** PreToolUse `*` in settings.json.

### 3.2 Error handling
**Score: 7/10**
**Evidence:** Handles missing config file. Main wraps stdin parse.
**Missing:** `_write_mismatch_event()` silently catches write errors (acceptable). No timeout on monitor file writes.

---

## 4. Live Effectiveness
**Score: 8/10**
**Evidence:** 10 INTENT_MISMATCH events in qg-monitor.jsonl. All from real sessions. Example: `2026-03-30T13:11:34 | layer17 | INTENT_MISMATCH`. Confirms the scope-mismatch detection fires on real violations.
**Missing:** No measurement of intent-capture quality or downstream impact on Claude's behavior.

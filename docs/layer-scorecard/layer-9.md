# Layer 9 — Confidence Calibration
**File:** `~/.claude/hooks/qg_layer9.py` (90 LOC, 3 functions)
**Hook event:** Stop
**Purpose:** Extracts stated certainty from response text; records actual outcome for calibration analysis
**pytest-cov:** 43% (63 stmts, 36 missed)
**Live events:** 0 (writes to qg-calibration.jsonl, not monitor log)
**Unit tests:** 10 methods across 2 classes

---

## 1. Certainty Extraction
**Code:** `extract_certainty()` (lines 19-26)

### 1.1 Logic
**Score: 7/10**
**Evidence:** THREE_RE patterns: HIGH ("I'm certain", "definitely", "guaranteed"), MEDIUM ("I believe", "should work", "likely"), LOW ("might", "possibly", "not sure").
**Missing:** "I think" appears in both MED_RE (`I think this will`) and LOW_RE (`I think`). MED is checked first and has higher specificity, so `"I think this will work"` → MEDIUM (correct), but bare `"I think"` → LOW (correct). However `"I think likely"` → MEDIUM (from MED_RE for "likely", not "I think this will"). The overlap is technically handled but confusing.
**To reach 10:** Clean up overlapping patterns. Add explicit tests for ambiguous phrases.

### 1.2 Unit tests
**Score: 7/10**
**Evidence:** TestLayer9ConfidenceCalibration tests HIGH, MEDIUM, LOW, and None cases.
**Missing:** No test for overlapping phrases.

---

## 2. Response Text Extraction
**Code:** `get_response_text()` (lines 29-48)

### 2.1 Logic
**Score: 5/10**
**Evidence:** Reads transcript JSONL, finds last assistant message, extracts text content.
**Missing:** Only reads last 100 lines of transcript. If assistant message is complex (multi-block content), it joins text blocks but may miss important context. No test for list-type content.
**To reach 10:** Add tests for complex content structures. Handle edge cases.

### 2.2 Unit tests
**Score: 3/10**
**Evidence:** Minimal testing of transcript parsing.

---

## 3. Calibration Recording
**Code:** Lines 63-86 in `main()`

### 3.1 Threshold gate
**Score: 7/10**
**Evidence:** Only records calibration data after `layer3_evaluation_count >= min_responses_before_recalibration` (default 5). Prevents recording before system has enough context.
**Missing:** No test for the threshold gate.

### 3.2 Outcome determination
**Score: 6/10**
**Evidence:** If `layer3_pending_fn_alert` is set, outcome is FN; otherwise TN. Does not record TP or FP outcomes.
**Missing:** Only tracks FN vs TN. TP (gate blocked correctly) and FP (gate blocked incorrectly) are not captured. This means calibration data is incomplete — it can only measure overconfidence when FN occurs, not when blocking was correct.
**To reach 10:** Record all four outcomes. Track TP and FP from quality-gate.py.

### 3.3 Output format
**Score: 8/10**
**Evidence:** Appends JSONL record with event_id, timestamp, session_uuid, certainty, outcome, task complexity.

---

## 4. Live Effectiveness
**Score: 2/10**
**Evidence:** Only 3 records in `qg-calibration.jsonl`. All show `stated_certainty: medium`, `actual_outcome: TN`. Insufficient data for any meaningful calibration analysis.
**To reach 10:** Need 100+ records across sessions. Investigate why so few records are being captured (likely the threshold gate is blocking most recordings, or certainty is rarely extracted).

---

## 5. Integration
### 5.1 settings.json wiring
**Score: 10/10**
**Evidence:** Stop hook in settings.json.

### 5.2 pytest-cov
**Score: 3/10**
**Evidence:** 43% coverage — much of main() and get_response_text() untested.
**To reach 10:** Add tests for main flow and transcript parsing.

# Layer 7 — Feedback and Rule Refinement
**File:** `~/.claude/hooks/qg_layer7.py` (114 LOC, 5 functions)
**Hook event:** Stop
**Purpose:** Generates rule suggestions from repeated FN patterns and cross-session data
**pytest-cov:** 23% (79 stmts, 61 missed)
**Live events:** 0 (writes to qg-rule-suggestions.md, no monitor events)
**Unit tests:** 7 methods across 2 classes

---

## 1. Feedback Loading
**Code:** `load_feedback()` (lines 14-28)

### 1.1 Logic
**Score: 7/10**
**Evidence:** Reads quality-gate-feedback.jsonl. Handles missing file and malformed lines.
**Missing:** No line count limit. No test for very large files.

---

## 2. Repeat FN Detection
**Code:** `find_repeat_fns()` (lines 31-37)

### 2.1 Logic
**Score: 7/10**
**Evidence:** Groups FN records by category. Returns categories with >=threshold occurrences (default 3).
**Missing:** No time window — counts all-time FNs regardless of when they occurred. Old fixed patterns still count.
**To reach 10:** Add recency weighting or time window.

### 2.2 Unit tests
**Score: 5/10**
**Evidence:** Basic test for repeat FN detection exists.
**Missing:** No test for threshold boundary. No test for empty feedback file.

---

## 3. Suggestion Generation
**Code:** `generate_suggestions()` (lines 40-73)

### 3.1 Logic
**Score: 6/10**
**Evidence:** Creates suggestions from repeat FNs and cross-session patterns. Deduplicates (cross-session only for categories not already in repeat FNs).
**Missing:** No priority ranking. No filtering of already-addressed suggestions. Suggestions are regenerated from scratch every time — no persistence of suggestion status.
**To reach 10:** Add suggestion persistence and status tracking.

### 3.2 Unit tests
**Score: 4/10**
**Evidence:** Minimal testing of suggestion generation.

---

## 4. Suggestion Output
**Code:** `write_suggestions()` (lines 76-89)

### 4.1 Logic
**Score: 7/10**
**Evidence:** Writes markdown file with status, category, reason, supporting count, timestamp.
**Missing:** Overwrites entire file every time. No merge with existing suggestions.

---

## 5. Main Trigger
**Code:** Lines 92-105

### 5.1 Logic
**Score: 5/10**
**Evidence:** Only runs if `layer3_pending_fn_alert` is set — meaning it only generates suggestions when a FN was detected this session.
**Missing:** This means the suggestion file is only updated on FN sessions. If there are cross-session patterns but no FN this session, suggestions are not updated. Seems like a design gap.
**To reach 10:** Run periodically regardless of FN alert (like Layer 6's time-based throttle).

---

## 6. Live Effectiveness
**Score: 2/10**
**Evidence:** No monitor events. `quality-gate-feedback.jsonl` has only 1 line (insufficient data for repeat FN detection). `qg-rule-suggestions.md` may not exist or may be empty.
**To reach 10:** Need more feedback data. Layer hasn't had enough input to produce meaningful suggestions yet.

---

## 7. Integration
### 7.1 settings.json wiring
**Score: 10/10**
**Evidence:** Stop hook in settings.json.

### 7.2 pytest-cov
**Score: 2/10**
**Evidence:** 23% coverage — lowest of all layers. Most of the code is never exercised by tests.
**To reach 10:** Write tests for suggestion generation, output formatting, and main trigger logic.

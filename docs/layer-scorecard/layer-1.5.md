# Layer 1.5 — PreToolUse Rule Validation
**File:** `~/.claude/hooks/qg_layer15.py` (133 LOC, 4 functions)
**Hook event:** PreToolUse `*`
**Purpose:** Warns or blocks based on rules; tracks reads; flushes queued CRITICALs; dedup within turn
**pytest-cov:** 82% (89 stmts, 16 missed — lines 19-20, 40, 63-64, 76-77, 84-88, 92, 112, 125, 133)
**Live events:** 0 (outputs additionalContext, not monitor events)
**Unit tests:** 15 methods across 3 classes

---

## 1. Rule: edit-without-read
**Code:** `evaluate_rules()` line 29-31

### 1.1 Detection logic
**Score: 8/10**
**Evidence:** Checks `tool_name == 'Edit' and fp and fp not in reads`. Same logic as Layer 2's LAZINESS but triggers a warning/block, not just a log event.
**Missing:** Same path normalization issue as Layer 2. Duplicate detection with Layer 2 — both fire on the same event.
**To reach 10:** Normalize paths. Clarify the role distinction (Layer 1.5 warns/blocks; Layer 2 logs).

### 1.2 Unit tests
**Score: 8/10**
**Evidence:** Tested in TestLayer15Rules and TestLayer15Extra.

---

## 2. Rule: bash-instead-of-tool
**Code:** Line 33-35

### 2.1 Detection logic
**Score: 7/10**
**Evidence:** `BASH_TOOL_RE` matches `grep|cat|find|head|tail|sed|awk` (broader than Layer 2's regex which lacks `sed|awk`).
**Missing:** Inconsistency with Layer 2's regex. Same false positive risk with word boundaries matching inside strings.
**To reach 10:** Align regexes between Layer 1.5 and Layer 2. Test for FPs.

---

## 3. Rule: write-outside-scope
**Code:** Lines 37-41

### 3.1 Detection logic
**Score: 6/10**
**Evidence:** Same substring match as Layer 2's SCOPE_CREEP. Same path issues.
**Missing:** Same limitations as Layer 2 section 5.

---

## 4. Read Tracking
**Code:** `handle_read_tracking()` (lines 46-55)

### 4.1 Logic
**Score: 9/10**
**Evidence:** Appends file_path to `layer15_session_reads` on every Read tool call. Deduplicates (only adds if not already present).
**Missing:** No path normalization. No cap on list size (could grow unbounded in long sessions).
**To reach 10:** Normalize paths. Add list size cap.

### 4.2 Unit tests
**Score: 7/10**
**Evidence:** Tested in TestLayer15Extra.

---

## 5. Critical Flush
**Code:** Lines 73-77

### 5.1 Logic
**Score: 6/10**
**Evidence:** Calls `router.flush_pending_criticals()`. If any pending criticals exist, injects them as additionalContext and returns early (skipping rule evaluation).
**Missing:** No test for the flush path. No test for what happens if flush returns empty string.
**To reach 10:** Add tests.

---

## 6. Override Token
**Code:** Lines 82-88

### 6.1 Logic
**Score: 5/10**
**Evidence:** If `layer15_override_pending` matches the current rule violation, skip the block. Consumed after use.
**Missing:** No test for override consumption. No test for override with wrong rule_id. No documentation on how overrides are set.
**To reach 10:** Add tests. Document override mechanism.

---

## 7. Repeat Violation Escalation
**Code:** Lines 103-113

### 7.1 Logic
**Score: 7/10**
**Evidence:** Counts violations per rule_id in `layer15_violation_counts`. At threshold (default 3), notifies CRITICAL via router.
**Missing:** No test for the threshold count. No test for the CRITICAL notification.
**To reach 10:** Add tests.

---

## 8. Impact-based Severity Promotion
**Code:** Lines 116-118

### 8.1 Logic
**Score: 6/10**
**Evidence:** If Layer 1.9 reports HIGH/CRITICAL impact and action is 'warn', promotes to 'block'.
**Missing:** No unit test for this promotion path.
**To reach 10:** Add test.

---

## 9. Gap 15: Warnings Ignored Count
**Code:** Lines 120-122

### 9.1 Logic
**Score: 7/10**
**Evidence:** Increments `layer15_warnings_ignored_count` for warn-level actions. Used by Layer 3 for confidence scoring.
**Missing:** No test verifying this counter is used downstream.

---

## 10. Integration
### 10.1 settings.json wiring
**Score: 10/10**
**Evidence:** PreToolUse `*` in settings.json.

### 10.2 Error handling
**Score: 8/10**
**Evidence:** Handles missing rules file, stdin parse errors.

---

## 11. Live Effectiveness
**Score: 4/10**
**Evidence:** Zero events in qg-monitor.jsonl (outputs additionalContext, not monitor events). We see `[monitor:INFO:layer1.5]` and `[monitor:WARN:layer1.5]` messages in Claude's context during sessions, confirming it fires. But effectiveness is unmeasurable from log data alone.
**To reach 10:** Add monitor event logging alongside additionalContext output. Or grep session transcripts for layer1.5 messages.

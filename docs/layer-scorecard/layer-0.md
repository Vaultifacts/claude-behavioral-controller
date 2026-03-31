# Layer 0 — Session Start Context Injection
**File:** `~/.claude/hooks/qg_layer0.py` (152 LOC, 4 functions)
**Hook event:** SessionStart
**Purpose:** Injects unresolved events + cross-session patterns from previous session, resets per-session state
**pytest-cov:** 54% (90 stmts, 41 missed)
**Live events:** 115
**Unit tests:** 7 methods in TestLayer0

---

## 1. Unresolved Event Injection
**Code:** `find_previous_session_unresolved()` (lines 19-39) + item 7 in main (lines 101-106)

### 1.1 History file parsing
**Score: 6/10**
**Evidence:** Reads `qg-session-history.md`, splits by `## Session` headers, finds current session UUID, extracts `- UNRESOLVED:` lines.
**Missing:** If history file doesn't exist, returns empty (correct). But no test for malformed history entries. Regex relies on exact format `- UNRESOLVED: ...`.
**To reach 10:** Add tests for malformed history. Test with multiple sessions in file.

### 1.2 UUID matching
**Score: 5/10**
**Evidence:** Matches `session_uuid: <uuid>` in the entry. But the function finds unresolved items *from the current UUID's entry* — this means it shows items from the CURRENT session, not the previous one. This may be a logic bug: it should show the PREVIOUS session's unresolved items.
**Missing:** Verify whether this correctly targets the previous session or the current one. The function name says "previous" but the logic matches `current_uuid`.
**To reach 10:** Verify and fix if needed. Add explicit test for previous-vs-current session behavior.

### 1.3 Unit tests
**Score: 5/10**
**Evidence:** TestLayer0 has 7 tests. `test_find_previous_session_unresolved_empty_path` and similar basic cases.
**Missing:** No test for multi-session history file. No test for UUID matching behavior.
**To reach 10:** Add comprehensive parsing tests.

### 1.4 Live effectiveness
**Score: 7/10**
**Evidence:** 115 events logged. We see `[monitor:Layer0] Cross-session patterns detected:` in session start output (confirmed in this session's system messages).
**Missing:** No verification that the injected patterns are accurate/useful. No measurement of whether Claude actually uses the injected context.

---

## 2. Cross-session Pattern Injection
**Code:** `load_cross_session_patterns()` (lines 42-51) + items 1-6 in main (lines 78-98)

### 2.1 Pattern loading
**Score: 7/10**
**Evidence:** Reads `qg-cross-session.json` written by Layer 6. Handles missing file and JSON errors gracefully.
**Missing:** No test for corrupt JSON. No test for empty patterns list.
**To reach 10:** Add edge case tests.

### 2.2 Character limit
**Score: 8/10**
**Evidence:** Configurable via `qg-rules.json` layer0.injection_max_chars (default 2000). Stops adding patterns when limit reached.
**Missing:** No unit test for the character limit truncation.
**To reach 10:** Add test.

### 2.3 Output formatting
**Score: 7/10**
**Evidence:** Formats as `  - CATEGORY (N sessions, N events)`. Limited to 10 patterns.
**Missing:** No test for the 10-pattern limit or formatting.

---

## 3. Recovery Pending Injection
**Code:** `load_recovery_pending()` (lines 56-71) + item 8 in main (lines 109-114)

### 3.1 Consume-once logic
**Score: 7/10**
**Evidence:** Reads `qg-recovery-pending.json`, checks `consumed` flag, sets it to True after reading.
**Missing:** Race condition if two sessions start simultaneously — both could read before either writes `consumed=True`.
**To reach 10:** Add file locking or atomic write. Test concurrent access.

### 3.2 Unit tests
**Score: 4/10**
**Evidence:** No dedicated test for `load_recovery_pending()` in the test file.
**To reach 10:** Add tests for: file missing, consumed=True, consumed=False, corrupt JSON.

---

## 4. State Reset
**Code:** Lines 117-149

### 4.1 Completeness of reset
**Score: 8/10**
**Evidence:** Resets 24 state keys to their defaults. Covers all layer prefixes (layer1, layer2, layer3, layer5, layer15, layer17, layer19, layer25, layer35).
**Missing:** Does not reset layer6, layer7, layer8, layer9, layer10, layer26, layer27, layer45 state keys. If any of these layers persist state, it could leak across sessions.
**To reach 10:** Audit all layers for persistent state keys and ensure all are reset.

### 4.2 Unit tests
**Score: 5/10**
**Evidence:** No test specifically validates that the reset clears all expected keys.
**To reach 10:** Add test that reads state after Layer 0 runs and verifies all expected keys are at defaults.

---

## 5. Integration
### 5.1 settings.json wiring
**Score: 10/10**
**Evidence:** Wired in SessionStart hook list in settings.json.

### 5.2 Error handling
**Score: 7/10**
**Evidence:** main() wraps stdin parse in try/except. Individual functions handle file-not-found.
**Missing:** If `ss.update_state()` fails, state reset is lost but session continues — could cause stale state leakage.

---

## 6. Live Effectiveness
**Score: 7/10**
**Evidence:** 115 events in qg-monitor.jsonl tagged `layer0`. Cross-session pattern injection confirmed working — this session shows `[monitor:Layer0] Cross-session patterns detected: INCORRECT_TOOL (6 sessions, 22 events)` at startup.
**Missing:** No measurement of whether injected context improves Claude's behavior. Unresolved event injection effectiveness unknown.

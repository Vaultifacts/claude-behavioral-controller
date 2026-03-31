# Layer 4.5 — Context Preservation (Compaction)
**File:** `~/.claude/hooks/qg_layer45.py` (108 LOC, 4 functions)
**Hook event:** PreCompact + PostCompact (manual and auto)
**Purpose:** Snapshots session state before context compaction; restores it after so monitoring survives /compact
**pytest-cov:** 83% (71 stmts, 12 missed)
**Live events:** 0 (outputs text messages, no monitor events)
**Unit tests:** 10 methods across 3 classes

---

## 1. PreCompact Snapshot
**Code:** `handle_pre_compact()` (lines 32-60)

### 1.1 State preservation
**Score: 8/10**
**Evidence:** Preserves 16 defined keys from PRESERVE_KEYS list plus dynamic keys from `qg-preservation-config.json`. Writes to `qg-context-preserve.json`.
**Missing:** 16 keys may not cover all important state. Layer 6, 7, 9, 10 state keys not preserved. No test that verifies all critical keys are in PRESERVE_KEYS.
**To reach 10:** Audit all layer state keys against PRESERVE_KEYS. Add test.

### 1.2 Dynamic key management (Gap #40)
**Score: 6/10**
**Evidence:** Reads `qg-preservation-config.json` for `always_preserve` and `skip_preserve` lists. Handles missing config gracefully.
**Missing:** No test for dynamic keys. No test for skip_preserve removing a key.

### 1.3 Resolved event pruning (Gap #41)
**Score: 8/10**
**Evidence:** Filters `layer2_unresolved_events` and `layer35_recovery_events` to only keep `status: open` events.
**Missing:** No test for pruning. What if status is missing from an event? (Would be included — `e.get('status') == 'open'` returns False, so it would be excluded. Could lose legitimate events without status.)
**To reach 10:** Handle missing status field. Add test.

### 1.4 Hash integrity
**Score: 7/10**
**Evidence:** Computes MD5 hash of first 5 preserved keys. Stored as `pre_compact_hash` for post-compact verification.
**Missing:** Only hashes 5 of 16 keys — remaining 11 could be corrupted without detection.
**To reach 10:** Hash all preserved keys.

---

## 2. PostCompact Restore
**Code:** `handle_post_compact()` (lines 63-96)

### 2.1 Hash verification
**Score: 6/10**
**Evidence:** Compares stored hash to recomputed hash. Prints warning on mismatch but proceeds anyway.
**Missing:** Mismatch only triggers a print message — doesn't block or escalate. If state is corrupted, monitoring continues with bad data.
**To reach 10:** Escalate hash mismatch to CRITICAL via notification router.

### 2.2 UUID mismatch handling
**Score: 7/10**
**Evidence:** If session UUID changed (new session, not a compact), only restores critical fields (unresolved events, recovery events, task description).
**Missing:** No test for UUID mismatch path.

### 2.3 Normal restore
**Score: 8/10**
**Evidence:** For same-session compact, restores all PRESERVE_KEYS where current state is empty/None.
**Missing:** If state has been partially updated between pre and post compact, restored values could overwrite newer data (though `not state.get(k)` check mitigates this for truthy values).

---

## 3. Live Effectiveness
**Score: 2/10**
**Evidence:** No monitor events. Output messages are visible in Claude's context but not logged. No measurement of how often compaction occurs or whether state is successfully preserved.
**To reach 10:** Add monitor logging. Track compaction events and restoration success rate.

---

## 4. Integration
### 4.1 settings.json wiring
**Score: 10/10**
**Evidence:** Wired for both PreCompact and PostCompact with `manual|auto` matchers. Uses `--pre` and `--post` CLI args.

### 4.2 Error handling
**Score: 7/10**
**Evidence:** File read/write wrapped in try/except. Missing preserve file in post-compact causes early return (no crash).
**Missing:** No notification on restore failure.

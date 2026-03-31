# Notification Router — Priority-based Event Delivery
**File:** `~/.claude/hooks/qg_notification_router.py` (125 LOC, 8 functions)
**Hook event:** N/A (imported by layers that need to send notifications)
**Purpose:** Routes CRITICAL/WARNING/INFO notifications with dedup, rate limiting, and queuing for cross-hook-context delivery
**pytest-cov:** 97% (76 stmts, 2 missed — lines 41-42)
**Unit tests:** 15 methods in TestNotificationRouter

---

## 1. Priority Routing
**Code:** `notify()` (lines 45-90)

### 1.1 INFO handling
**Score: 9/10**
**Evidence:** Writes to JSONL log and records delivery. No dedup (intentional — INFO is always logged).
**Missing:** No test for JSONL write failure path (lines 41-42 are the missed coverage).

### 1.2 WARNING handling
**Score: 8/10**
**Evidence:** Queued with status 'queued'. Delivered in batch at Stop time via `flush_warnings()`.
**Missing:** No test that confirms warnings are actually delivered at Stop time end-to-end.
**To reach 10:** Add integration test for Stop-time flush.

### 1.3 CRITICAL handling
**Score: 8/10**
**Evidence:** In pretooluse/posttooluse context: delivers immediately via additionalContext (max 3 per turn). In stop/sessionstart/async context: queues for next PreToolUse flush.
**Missing:** No test for the 3-per-turn limit. No test for cross-context queuing.
**To reach 10:** Add rate limit and cross-context tests.

---

## 2. Deduplication
**Code:** `_is_duplicate()` (lines 20-26)

### 2.1 Logic
**Score: 8/10**
**Evidence:** Dedup key is `layer:category:file_path`. 60-second window. Prevents duplicate notifications for the same issue within a minute.
**Missing:** No test for the 60-second window boundary. Same category from different layers would have different dedup keys (correct).

### 2.2 Unit tests
**Score: 8/10**
**Evidence:** Dedup tested in TestNotificationRouter.

---

## 3. Critical Flush
**Code:** `flush_pending_criticals()` (lines 93-105)

### 3.1 Logic
**Score: 8/10**
**Evidence:** Flushes up to 3 queued CRITICALs. Called by Layer 1.5 at PreToolUse entry. Removes flushed items from pending list.
**Missing:** No test for flushing more than 3 (should leave remainder for next flush).
**To reach 10:** Add test for partial flush.

---

## 4. Warning Flush
**Code:** `flush_warnings()` (lines 108-119)

### 4.1 Logic
**Score: 7/10**
**Evidence:** Collects all queued warnings and marks delivered. Returns formatted text.
**Missing:** No caller identified in the Stop hooks — `flush_warnings()` may never be called. If so, warnings accumulate forever.
**To reach 10:** Verify flush_warnings is called somewhere. If not, add the call.

---

## 5. Turn Counter Reset
**Code:** `reset_turn_counter()` (lines 122-124)

### 5.1 Logic
**Score: 9/10**
**Evidence:** Resets global `_turn_critical_count = 0`. Called by Layer 1.5 at the start of each PreToolUse.
**Missing:** Global variable means this only works within a single process invocation. Since each hook call is a separate process, the counter resets naturally. The global is effectively always 0 at the start of each hook call — which means the 3-per-turn limit may never actually trigger.
**To reach 10:** Verify whether the per-turn limit actually works across separate process invocations. If not, move the counter to session state.

---

## 6. Live Effectiveness
**Score: 7/10**
**Evidence:** Layer 1.5 and Layer 10 call `notify()`. Notification delivery records exist in session state. The router is actively used.
**Missing:** No measurement of how many notifications are delivered vs. dropped vs. queued.

---

## 7. Integration
### 7.1 Import pattern
**Score: 9/10**
**Evidence:** Imported by Layer 1.5 (`import qg_notification_router as router`) and Layer 10.
**Missing:** Not all layers that could benefit from notifications use the router (e.g., Layer 2 writes directly to monitor log instead of using notify()).

### 7.2 pytest-cov
**Score: 10/10**
**Evidence:** 97% coverage — highest of all files. Only 2 uncovered lines (JSONL write exception handler).

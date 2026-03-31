# Layer 5 — Subagent Coordination
**File:** `~/.claude/hooks/qg_layer5.py` (223 LOC, 7 functions)
**Hook event:** PreToolUse Agent + PostToolUse Agent
**Purpose:** Records dispatch/return events; tracks subagent-parent linkage; handoff files for state transfer
**pytest-cov:** 73% (106 stmts, 29 missed)
**Live events:** 101
**Unit tests:** 13 methods across 3 classes

---

## 1. Dispatch Tracking (PreToolUse)
**Code:** `process_predispatch()` (lines 98-142)

### 1.1 Event recording
**Score: 8/10**
**Evidence:** Creates `subagent_dispatch` event with unique subagent_id, parent_task_id, task description. Writes to monitor log.
**Missing:** No test for duplicate dispatch (same agent dispatched twice rapidly). UUID is random — no correlation with Claude's actual agent ID.
**To reach 10:** Explore whether Claude's agent tool provides an ID that could be used instead of random UUID.

### 1.2 Handoff file creation
**Score: 7/10**
**Evidence:** `_write_handoff()` creates `qg-subagent-<id>.json` with scope files, success criteria, unresolved events, impact level.
**Missing:** Only writes open unresolved events for the current task — other tasks' events are excluded. No encryption or access control on handoff file.
**To reach 10:** Verify that subagents actually read the handoff file (no evidence they do — this may be dead code if SubagentStart hook doesn't consume it).

### 1.3 Unit tests
**Score: 7/10**
**Evidence:** TestLayer5SubagentCoordination and TestLayer5HandoffFiles test dispatch and handoff creation.
**Missing:** No test for handoff consumption by subagent.

---

## 2. Return Tracking (PostToolUse)
**Code:** `process_and_record()` (lines 145-196)

### 2.1 Status detection
**Score: 6/10**
**Evidence:** Checks `tool_response` for "timeout", "timed out", "error:", "exception:" to determine `subagent_timeout` vs `subagent_complete`.
**Missing:** Simple keyword match could false-positive (response about fixing a timeout would trigger). No test for false positive scenarios.
**To reach 10:** Tighten pattern matching. Add negative tests.

### 2.2 ID correlation
**Score: 5/10**
**Evidence:** `_find_inflight_id()` looks up in-flight subagent by `parent_task_id`. If no match, generates a new UUID. This means dispatch and return events may have different IDs if task_id changed between dispatch and return.
**Missing:** Correlation depends on `active_task_id` being the same at dispatch and return time. If the task changes between dispatch and return (possible in long agent runs), correlation breaks.
**To reach 10:** Store dispatch IDs and match by timing rather than task_id alone.

### 2.3 Event merge
**Score: 7/10**
**Evidence:** `_merge_subagent_events()` reads handoff file, merges `subagent_events`, tags with `parent_task_id`, deletes file.
**Missing:** If handoff file was never written by subagent (which is likely — see 1.2), merge finds empty `subagent_events` and does nothing useful.

---

## 3. Timeout Handling
**Code:** Lines 63-77 in `_merge_subagent_events()`

### 3.1 Logic
**Score: 7/10**
**Evidence:** If handoff file doesn't exist at merge time, sets `timeout_marker` on the subagent entry. If file exists but is corrupt, also sets timeout_marker.
**Missing:** No escalation on timeout. No notification to user. Timeout marker is set but never consumed by any downstream layer.
**To reach 10:** Add timeout escalation. Consume the marker somewhere.

### 3.2 Unit tests
**Score: 7/10**
**Evidence:** TestLayer5HandoffFiles tests absent file = timeout_marker and successful merge + deletion.

---

## 4. Live Effectiveness
**Score: 8/10**
**Evidence:** 101 events in production log (all dispatch/return). Split roughly 50/50 between dispatch and return events.
**Missing:** No measurement of how many dispatches have matching returns. No measurement of timeout rate.
**To reach 10:** Add a report that correlates dispatch/return pairs and measures timeout rate.

---

## 5. Integration
### 5.1 settings.json wiring
**Score: 10/10**
**Evidence:** Wired at both PreToolUse `Agent` and PostToolUse `Agent` in settings.json.

### 5.2 Dispatch vs. return distinction
**Score: 8/10**
**Evidence:** Distinguishes by checking `"tool_response" not in payload` (PreToolUse has no response; PostToolUse does).
**Missing:** If payload format changes, this could break. No explicit `hook_event_name` check.

# Layer 6 — Cross-session Pattern Analysis
**File:** `~/.claude/hooks/qg_layer6.py` (105 LOC, 4 functions)
**Hook event:** Stop
**Purpose:** Analyzes monitor log for violation categories recurring across sessions; writes patterns to qg-cross-session.json for Layer 0 to inject
**pytest-cov:** 76% (82 stmts, 20 missed)
**Live events:** 0 (writes to qg-cross-session.json, not monitor log)
**Unit tests:** 10 methods across 2 classes

---

## 1. Monitor Event Loading
**Code:** `load_monitor_events()` (lines 14-28)

### 1.1 Logic
**Score: 8/10**
**Evidence:** Reads qg-monitor.jsonl line by line. Skips empty lines and invalid JSON.
**Missing:** No line count limit — reading entire file into memory could be slow for very large logs. No test for files with 10K+ lines.
**To reach 10:** Add line limit or streaming. Add large-file test.

---

## 2. Pattern Analysis
**Code:** `analyze_patterns()` (lines 31-61)

### 2.1 Windowing
**Score: 8/10**
**Evidence:** Analyzes last N sessions (default 10). Sessions sorted by earliest event timestamp.
**Missing:** No test for the window parameter. No test for sessions with overlapping timestamps.

### 2.2 Minimum thresholds
**Score: 7/10**
**Evidence:** Requires `min_sessions=3` and `min_pct=0.15` (15% of events). Both configurable.
**Missing:** No test for threshold edge cases (exactly at threshold).
**To reach 10:** Add boundary tests.

### 2.3 Project filtering
**Score: 6/10**
**Evidence:** Optional `project_dir` filter. But the filter logic `e.get("working_dir", project_dir) == project_dir` returns the default value as `project_dir` when key is missing — meaning events without working_dir ALWAYS match. This is likely a bug.
**To reach 10:** Fix the default value logic. Change to `e.get("working_dir") == project_dir`.

### 2.4 Unit tests
**Score: 7/10**
**Evidence:** TestLayer6CrossSessionAnalysis tests basic pattern detection. TestLayer6Extra tests edge cases.
**Missing:** No test for the project_dir filter bug.

---

## 3. Output Writing
**Code:** `run_analysis()` (lines 64-83)

### 3.1 Logic
**Score: 7/10**
**Evidence:** Writes `qg-cross-session.json` with patterns, timestamp, and session count. Only writes if patterns found or file doesn't exist.
**Missing:** No file locking. If two sessions end simultaneously, concurrent writes could corrupt the file.
**To reach 10:** Add file locking or atomic writes.

---

## 4. Throttling
**Code:** Lines 88-90 in `main()`

### 4.1 Logic
**Score: 8/10**
**Evidence:** Only runs analysis once per hour (`time.time() - last_ts < 3600`). Prevents excessive analysis on every Stop.
**Missing:** No test for throttle behavior.
**To reach 10:** Add test.

---

## 5. Live Effectiveness
**Score: 7/10**
**Evidence:** We can see `[monitor:Layer0] Cross-session patterns detected: INCORRECT_TOOL (6 sessions, 22 events), ERROR_IGNORED (6 sessions, 21 events), LOOP_DETECTED (4 sessions, 16 events)` in this session's startup — confirming Layer 6 successfully analyzed patterns and Layer 0 consumed them.
**Missing:** No measurement of whether the injected patterns actually improve Claude's behavior. No A/B comparison.

---

## 6. Integration
### 6.1 settings.json wiring
**Score: 10/10**
**Evidence:** Stop hook in settings.json.

### 6.2 Error handling
**Score: 7/10**
**Evidence:** Analysis wrapped in try/except in main(). Missing files handled.
**Missing:** If the analysis crashes, it silently fails — no error logging.

# Layer 10 — Audit Trail Integrity
**File:** `~/.claude/hooks/qg_layer10.py` (96 LOC, 3 functions)
**Hook event:** Stop (but throttled to once per 7 days)
**Purpose:** Validates JSONL files, quarantines corrupt lines, rotates at 10,000 lines
**pytest-cov:** 87% (71 stmts, 9 missed)
**Live events:** 0 (runs infrequently due to 7-day throttle)
**Unit tests:** 8 methods across 2 classes

---

## 1. JSONL Validation
**Code:** `validate_jsonl()` (lines 15-45)

### 1.1 Logic
**Score: 8/10**
**Evidence:** Reads every line, validates JSON parsing, checks for duplicate event_ids. Quarantines corrupt and duplicate lines to `qg-quarantine.jsonl`.
**Missing:** No validation of required fields (e.g., does each event have `ts`, `layer`, `category`?). Only checks JSON validity and ID uniqueness.
**To reach 10:** Add field validation. Add test for missing required fields.

### 1.2 Quarantine output
**Score: 8/10**
**Evidence:** Appends corrupt lines to quarantine file with timestamp, source path, and error detail. Non-destructive — original file is not modified during validation.
**Missing:** No quarantine file rotation. Quarantine could grow indefinitely.
**To reach 10:** Add quarantine rotation.

### 1.3 Unit tests
**Score: 8/10**
**Evidence:** Tests for valid JSON, invalid JSON, and duplicate IDs exist.
**Missing:** No test for very large files or performance.

---

## 2. Log Rotation
**Code:** `maybe_rotate()` (lines 48-57)

### 2.1 Logic
**Score: 7/10**
**Evidence:** Renames file to monthly archive (`qg-monitor-2026-03.jsonl`) when line count exceeds 10,000.
**Missing:** Uses `os.rename()` which can fail across filesystem boundaries. No graceful handling if archive already exists (would overwrite).
**To reach 10:** Use `shutil.move()`. Handle existing archive file. Add test for rotation.

### 2.2 Unit tests
**Score: 5/10**
**Evidence:** Basic rotation test exists. No test for existing archive file.

---

## 3. Throttle Guard
**Code:** Lines 61-70

### 3.1 Logic
**Score: 7/10**
**Evidence:** Only runs once per `integrity_check_interval_days` (default 7). Configurable.
**Missing:** No test for the throttle behavior. No manual override to force immediate check.
**To reach 10:** Add test. Document manual override via `qg integrity` CLI.

---

## 4. CRITICAL Notification
**Code:** Lines 83-85

### 4.1 Logic
**Score: 8/10**
**Evidence:** Notifies CRITICAL via notification router when corrupt lines are found.
**Missing:** No notification for rotation events. No notification for zero corrupt lines (confirmation of health).

---

## 5. Live Effectiveness
**Score: 4/10**
**Evidence:** No monitor events (by design — it doesn't log to the file it validates). Two quarantined lines exist from a previous integrity check. The 7-day throttle means it runs very rarely.
**Missing:** No way to confirm it's running unless you check `last_integrity_check_ts` in session state.
**To reach 10:** Add a lightweight "heartbeat" log entry confirming the check ran.

---

## 6. Integration
### 6.1 settings.json wiring
**Score: 10/10**
**Evidence:** Stop hook in settings.json.

### 6.2 Error handling
**Score: 7/10**
**Evidence:** Config load handles missing file. File operations use encoding='utf-8'. But `os.rename()` in rotation could throw on Windows if file is locked.
**To reach 10:** Handle file-lock errors.

# Layer 20 — System Health Dashboard
**File:** `~/.claude/hooks/qg_layer20.py` (299 LOC, 10 functions)
**Hook event:** SessionStart
**Purpose:** Validates monitoring system health: hook files exist, registrations match, state/monitor/quarantine files healthy, log sizes reasonable
**pytest-cov:** 79% (217 stmts, 46 missed)
**Live events:** 3
**Unit tests:** 25 methods in TestLayer20SystemHealth

---

## 1. Hook File Existence Check
**Code:** `check_hook_files()`, `_extract_hook_files()` (lines 61-88)

### 1.1 Logic
**Score: 9/10**
**Evidence:** Parses settings.json, extracts python/bash file paths via regex, verifies each exists. For .py files runs `compile()` to catch syntax errors.
**Missing:** Does not verify .sh files are executable.

### 1.2 Unit tests
**Score: 10/10**
**Evidence:** `test_hook_files_all_valid`, `test_hook_file_missing`, `test_hook_file_syntax_error`, `test_hook_file_bash_script`.

---

## 2. Registration Integrity
**Code:** `check_registration_integrity()` (lines 91-105)

### 2.1 Logic
**Score: 9/10**
**Evidence:** Finds `qg_layer*.py` in hooks dir, compares against settings.json. Excludes known library layers (layer10, layer35).
**Missing:** Library exclusion list is hardcoded. New library layers must be manually added to LIBRARY_LAYERS.

### 2.2 Unit tests
**Score: 10/10**
**Evidence:** `test_registration_integrity_clean`, `test_registration_unregistered_layer`, `test_registration_library_excluded`.

---

## 3. State File Health
**Code:** `check_state_health()` (lines 108-133)

### 3.1 Logic
**Score: 9/10**
**Evidence:** Checks existence, valid JSON, size < 50KB, has schema_version key.

### 3.2 Unit tests
**Score: 10/10**
**Evidence:** `test_state_valid`, `test_state_too_large`, `test_state_invalid_json`, `test_state_missing`, `test_state_no_schema_version`.

---

## 4. Monitor Log Health
**Code:** `check_monitor_health()` (lines 136-155)

### 4.1 Logic
**Score: 8/10**
**Evidence:** Checks existence, size < 5MB, counts lines.
**Missing:** No "no recent events" check. A monitor that has not logged in 24h still shows as healthy.
**To reach 10:** Add warning if last event is >24h old.

### 4.2 Unit tests
**Score: 9/10**
**Evidence:** `test_monitor_healthy`, `test_monitor_too_large`, `test_monitor_missing`.

---

## 5. Quarantine Log
**Code:** `check_quarantine()` (lines 158-174)

### 5.1 Logic
**Score: 8/10**
**Evidence:** Counts entries, warns if >20.
**Missing:** Does not track "new since last check" -- always reports total count.
**To reach 10:** Store last-seen count in session state and report delta.

### 5.2 Unit tests
**Score: 10/10**
**Evidence:** `test_quarantine_entries`, `test_quarantine_many`, `test_quarantine_empty`.

---

## 6. Layer Activity
**Code:** `check_layer_activity()` (lines 177-198)

### 6.1 Logic
**Score: 7/10**
**Evidence:** Scans last 200 lines of monitor log, extracts distinct layer values.
**Missing:** Does not compare against expected layer list. No "Layer X should be firing but is not" detection.
**To reach 10:** Maintain expected-active-layers list and report gaps.

### 6.2 Unit tests
**Score: 8/10**
**Evidence:** `test_layer_activity_all_active`, `test_layer_activity_gaps`.

---

## 7. Log Sizes
**Code:** `check_log_sizes()` (lines 201-213)

### 7.1 Logic
**Score: 9/10**
**Evidence:** Checks 4 key log files against 2MB limit. Simple and reliable.

### 7.2 Unit tests
**Score: 10/10**
**Evidence:** `test_log_sizes_normal`, `test_log_sizes_large`.

---

## 8. Integration
### 8.1 run_health_check()
**Score: 9/10**
**Evidence:** Orchestrates all 7 checks, computes overall status (ok/warning/critical), returns structured report.

### 8.2 settings.json wiring
**Score: 10/10**
**Evidence:** SessionStart registered.

### 8.3 Coverage gap
**Score: 7/10**
**Evidence:** 79% coverage. main() untested (lines 259-299). Integration tests use run_health_check() directly.
**To reach 10:** Add main() mock test with stdin payload.

---

## 9. Live Effectiveness
**Score: 6/10**
**Evidence:** 3 events in monitor log (just deployed). Need more sessions to validate.
**To reach 10:** After 10+ sessions, verify health checks are running and catching real issues.

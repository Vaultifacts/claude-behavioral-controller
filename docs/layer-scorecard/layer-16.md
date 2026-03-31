# Layer 16 — Rollback & Undo Capability
**File:** `~/.claude/hooks/qg_layer16.py` (173 LOC, 7 functions)
**Hook event:** PreToolUse on Edit/Write
**Purpose:** Captures file snapshots before edits, enables rollback to any of last 20 states
**pytest-cov:** 61% (119 stmts, 46 missed)
**Live events:** 7
**Unit tests:** 18 methods in TestLayer16RollbackUndo

---

## 1. Snapshot Capture
**Code:** `capture_snapshot()` (lines 29-53)

### 1.1 Logic
**Score: 9/10**
**Evidence:** Reads file content, writes to snapshot dir with timestamp+hash name. Skips empty files and files >512KB. Handles missing files gracefully.

### 1.2 Unit tests
**Score: 10/10**
**Evidence:** 6 tests: basic, content preserved, nonexistent, empty, large, no path.

---

## 2. Snapshot Restore
**Code:** `restore_snapshot()` (lines 73-84)

### 2.1 Logic
**Score: 9/10**
**Evidence:** Reads snapshot file, writes back to original path. Returns True/False.
**Missing:** No backup of current state before restore (could lose current version).

### 2.2 Unit tests
**Score: 9/10**
**Evidence:** 3 tests: basic restore, missing snapshot, empty meta.

---

## 3. Snapshot Pruning
**Code:** `prune_snapshots()` (lines 56-66)

### 3.1 Logic
**Score: 9/10**
**Evidence:** Keeps last 20 snapshots. Removes old snapshot files from disk.

### 3.2 Unit tests
**Score: 9/10**
**Evidence:** 2 tests: under limit, over limit with file cleanup verified.

---

## 4. File Lookup & Cleanup
**Code:** `get_snapshots_for_file()`, `cleanup_session_snapshots()` (lines 87-107)

### 4.1 Logic
**Score: 9/10**
**Evidence:** Path-normalized lookup. Cleanup removes only .snap files, preserves others.

### 4.2 Unit tests
**Score: 10/10**
**Evidence:** 5 tests: matches, none, cleanup removes, empty dir, nonexistent dir.

---

## 5. Integration
### 5.1 Coverage gap
**Score: 6/10**
**Evidence:** 61% coverage. main() untested (lines 119-169).
**To reach 10:** Add main() mock test with Edit/Write payload.

### 5.2 settings.json wiring
**Score: 10/10**
**Evidence:** PreToolUse Edit|Write registered.

---

## 6. Live Effectiveness
**Score: 7/10**
**Evidence:** 7 events — snapshots being captured. Restore functionality not yet exercised in production.

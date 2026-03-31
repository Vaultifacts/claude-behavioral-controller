# Layer 2.6 — Consistency Enforcement
**File:** `~/.claude/hooks/qg_layer26.py` (116 LOC, 4 functions)
**Hook event:** PostToolUse on Write/Edit
**Purpose:** Establishes convention baseline from first 3 files; warns on naming/import style deviation
**pytest-cov:** 86% (80 stmts, 11 missed)
**Live events:** 36
**Unit tests:** 9 methods across 2 classes

---

## 1. Convention Detection
**Code:** `detect_convention()` (lines 24-38)

### 1.1 Naming detection
**Score: 7/10**
**Evidence:** `SNAKE_RE` matches `def lower_case_name`, `CAMEL_RE` matches `def camelCaseName`. Mutually exclusive — if both found, neither is set.
**Missing:** Doesn't detect class naming conventions. Doesn't handle `_private_method` vs `public_method` distinction.
**To reach 10:** Add class naming detection. Add UPPER_CASE for constants.

### 1.2 Import style detection
**Score: 7/10**
**Evidence:** `IMPORT_DIRECT_RE` matches `import X`, `IMPORT_FROM_RE` matches `from X import`. Mutually exclusive.
**Missing:** Mixed imports in the same file result in neither being detected — no baseline established. Files with both `import os` and `from pathlib import Path` are silently skipped.
**To reach 10:** Handle mixed import files (e.g., flag the dominant style).

### 1.3 Unit tests
**Score: 8/10**
**Evidence:** Tested for snake_case, camelCase, direct imports, from imports.

---

## 2. Baseline Building
**Code:** Lines 79-86

### 2.1 Logic
**Score: 7/10**
**Evidence:** First 3 files establish the baseline. Only keys not already in baseline are set.
**Missing:** No test for files that don't contribute conventions (empty files, non-code files). Counter `files_seen` increments even for files with no detected convention.
**To reach 10:** Only increment counter when convention is detected. Add test for empty convention files.

### 2.2 Unit tests
**Score: 6/10**
**Evidence:** Basic baseline building tested.

---

## 3. Deviation Detection
**Code:** `check_deviation()` (lines 41-48) + lines 91-112

### 3.1 Logic
**Score: 8/10**
**Evidence:** Compares file convention to baseline for naming and imports. Lists all deviations.
**Missing:** No severity weighting (a naming deviation is treated same as import deviation).

### 3.2 New-artifact suppression
**Score: 9/10**
**Evidence:** Line 88: Skips deviation check if `layer17_creating_new_artifacts` is True.

### 3.3 Unit tests
**Score: 7/10**
**Evidence:** Deviation detection tested. Suppression not tested.

---

## 4. Monitor Event Logging
**Score: 8/10**
**Evidence:** Writes CONSISTENCY_VIOLATION events to qg-monitor.jsonl with detection signal describing the deviation.

---

## 5. Live Effectiveness
**Score: 9/10**
**Evidence:** 36 events in production log. Recent example: `imports: 'direct' vs baseline 'from'`. Fires consistently across sessions. Known to detect real style inconsistencies.
**Missing:** No FP analysis. Some of these may be false positives (e.g., mixed-import files are common in Python).

---

## 6. Integration
### 6.1 settings.json wiring
**Score: 10/10**
**Evidence:** PostToolUse `Write|Edit` in settings.json.

### 6.2 File type filtering
**Score: 9/10**
**Evidence:** Only processes `.py`, `.js`, `.ts` files. Skips non-existent files.

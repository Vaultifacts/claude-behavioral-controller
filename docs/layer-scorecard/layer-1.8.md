# Layer 1.8 — Hallucination Detection
**File:** `~/.claude/hooks/qg_layer18.py` (228 LOC, 6 functions)
**Hook event:** PreToolUse on Edit
**Purpose:** Detects hallucinated file paths, function names, imports, and URLs before edits land
**pytest-cov:** 64% (148 stmts, 54 missed)
**Live events:** 0 (outputs additionalContext, not monitor events)
**Unit tests:** 13 methods across 3 classes

---

## 1. Path Existence Check
**Code:** `check_path_exists()` (lines 21-26)

### 1.1 Logic
**Score: 9/10**
**Evidence:** `os.path.isfile()`. On exception returns True (avoids false positive). Only fires for Edit, not Write (correct — Write creates files).
**Missing:** No test for symlinks, permission errors, or very long paths.

---

## 2. Function/Class Existence Check
**Code:** `check_function_in_file()` (lines 29-47)

### 2.1 Logic
**Score: 6/10**
**Evidence:** Extracts `def name` and `class name` from old_string, verifies they exist in the file content via substring match.
**Missing:** Regex uses `(?:^|\s)def\s+(\w+)` — misses `def` preceded by punctuation (documented as known gap). Substring match `name in content` could match a variable with the same name as a function.
**To reach 10:** Use more precise matching (e.g., `re.search(r'def\s+' + name)`). Add adversarial test for variable-name collision.

### 2.2 Session dedup
**Score: 8/10**
**Evidence:** Lines 191-197: Tracks `layer18_session_checked` dict of `file_path::name` entries to avoid re-checking.
**Missing:** No test for dedup behavior. Dict could grow unbounded.

### 2.3 Unit tests
**Score: 6/10**
**Evidence:** TestLayer18HallucinationDetection has basic path and function tests. TestLayer18Gap17 has 3 tests for import and URL checks.
**Missing:** No adversarial test for false positives. No dedup test.

---

## 3. Import Existence Check (Gap #34)
**Code:** `check_imports_in_file()` (lines 50-67) + `check_packages_importable()` (lines 70-84)

### 3.1 File-level import check
**Score: 7/10**
**Evidence:** Extracts `import X` and `from X import` names from old_string, checks if the top-level module name exists in the file content.
**Missing:** Substring match could false-positive on comments or strings containing the module name.

### 3.2 System-level import check
**Score: 6/10**
**Evidence:** Uses `importlib.util.find_spec()` to verify packages are actually installed. Returns list of unimportable names.
**Missing:** `find_spec` may not work for namespace packages. No test for packages in virtual environments vs. system Python.

### 3.3 Unit tests
**Score: 5/10**
**Evidence:** TestLayer18Gap17 tests basic import checking. No adversarial tests.

---

## 4. URL/Remote Reference Check (Gap #35)
**Code:** `find_remote_refs()` (lines 14-18) + lines 163-174

### 4.1 Logic
**Score: 7/10**
**Evidence:** Finds `https?://` URLs in old_string and warns. Simple but effective for catching hallucinated URLs.
**Missing:** No verification of URL validity (could warn on legitimate URLs). No allowlist for known-good domains.
**To reach 10:** Add domain allowlist (e.g., github.com, docs.python.org). Add URL validation.

### 4.2 Unit tests
**Score: 6/10**
**Evidence:** Basic URL detection tested in TestLayer18Gap17.

---

## 5. New-artifact Suppression
**Code:** Lines 119-120

### 5.1 Logic
**Score: 8/10**
**Evidence:** If `layer17_creating_new_artifacts` is True (set by Layer 1.7), skip all hallucination checks. This prevents false positives when creating new files/functions.
**Missing:** No test for this suppression path.

---

## 6. Live Effectiveness
**Score: 2/10**
**Evidence:** Zero events in monitor log. Like Layer ENV, this layer outputs warnings via additionalContext but doesn't write to qg-monitor.jsonl. No independent measurement of how often it fires.
**To reach 10:** Add monitor logging. Or grep Claude session transcripts for `[monitor:WARN:layer1.8]` messages.

---

## 7. Integration
### 7.1 settings.json wiring
**Score: 9/10**
**Evidence:** PreToolUse `*` in settings.json (fires for all tools, but early-returns for non-Edit).
**Missing:** Could be optimized with matcher `Edit` instead of `*` to avoid unnecessary invocations.

### 7.2 Error handling
**Score: 8/10**
**Evidence:** All file reads wrapped in try/except with True fallback (no false positives on error). Config load handles missing file.

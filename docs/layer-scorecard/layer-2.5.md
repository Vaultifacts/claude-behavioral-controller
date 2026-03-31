# Layer 2.5 — Output Validity (Syntax Validation)
**File:** `~/.claude/hooks/qg_layer25.py` (120 LOC, 7 functions)
**Hook event:** PostToolUse on Write/Edit
**Purpose:** Validates file syntax (.py, .json, .yaml, .sh) after write/edit; logs OUTPUT_UNVALIDATED events
**pytest-cov:** 81% (68 stmts, 13 missed)
**Live events:** 1
**Unit tests:** 9 methods across 2 classes

---

## 1. Python Validation
**Code:** `_validate_python()` (lines 21-22)

### 1.1 Logic
**Score: 9/10**
**Evidence:** Uses `ast.parse(content)` — catches all syntax errors. Standard and reliable.
**Missing:** Doesn't detect runtime errors or type issues (not the layer's job).

### 1.2 Unit tests
**Score: 8/10**
**Evidence:** Tested with valid and invalid Python files.

---

## 2. JSON Validation
**Code:** `_validate_json()` (lines 24-25)

### 2.1 Logic
**Score: 10/10**
**Evidence:** `json.loads(content)` — definitive JSON validation.

### 2.2 Unit tests
**Score: 8/10**

---

## 3. YAML Validation
**Code:** `_validate_yaml()` (lines 27-34)

### 3.1 Logic
**Score: 6/10**
**Evidence:** Uses `yaml.safe_load()` but silently passes if yaml module isn't installed (`except ImportError: pass`).
**Missing:** If pyyaml isn't installed, YAML validation silently does nothing. No test for the ImportError path.
**To reach 10:** Log when yaml isn't available. Add test for ImportError path.

---

## 4. Shell Script Validation
**Code:** `_validate_sh()` (lines 37-42)

### 4.1 Logic
**Score: 7/10**
**Evidence:** Runs `bash -n /dev/stdin` with content piped in. 5-second timeout. Raises SyntaxError on non-zero exit.
**Missing:** Doesn't validate PowerShell scripts. Only checks syntax, not shebang correctness.
**To reach 10:** Consider adding PS1 validation on Windows.

### 4.2 Unit tests
**Score: 5/10**
**Evidence:** Basic test exists. No test for timeout.

---

## 5. File Size Limit
**Code:** Lines 62-64

### 5.1 Logic
**Score: 8/10**
**Evidence:** Skips files >100KB to avoid slow validation. Handles missing files gracefully.
**Missing:** No test for the size limit boundary.

---

## 6. Monitor Event Logging
**Code:** Lines 91-116

### 6.1 Logic
**Score: 8/10**
**Evidence:** Writes OUTPUT_UNVALIDATED event to qg-monitor.jsonl. Also appends to `layer2_unresolved_events` so Layer 2 can track resolution.
**Missing:** No dedup — same file written twice with same error creates two events.

### 6.2 AdditionalContext output
**Score: 8/10**
**Evidence:** Prints `[Layer 2.5] Syntax warning: <path> has invalid syntax` to alert Claude.

---

## 7. Live Effectiveness
**Score: 3/10**
**Evidence:** Only 1 event ever in the monitor log. Either syntax errors rarely happen (possible), or the validators are rarely triggered (need to check if Write/Edit tool calls for .py files actually reach this layer).
**To reach 10:** Verify the layer is being invoked. Add trace logging to confirm it runs.

---

## 8. Integration
### 8.1 settings.json wiring
**Score: 10/10**
**Evidence:** PostToolUse `Write|Edit` in settings.json.

### 8.2 Error handling
**Score: 8/10**
**Evidence:** Validator errors caught and returned as strings. File read errors caught. Silent on write failure.

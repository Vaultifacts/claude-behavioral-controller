# Layer 2.8 — Security Vulnerability Detection
**File:** `~/.claude/hooks/qg_layer28.py` (157 LOC, 5 functions)
**Hook event:** PostToolUse on Write/Edit
**Purpose:** Scans written/edited code for OWASP-category vulnerabilities (SQL injection, XSS, command injection, insecure crypto, deserialization)
**pytest-cov:** 63% (91 stmts, 34 missed)
**Live events:** 16
**Unit tests:** 18 methods in TestLayer28SecurityDetection

---

## 1. SQL Injection Detection
**Code:** `SQL_FSTRING_RE`, `SQL_CONCAT_RE`, `SQL_FORMAT_RE` (lines 36-38)

### 1.1 Logic
**Score: 9/10**
**Evidence:** Three regex patterns cover f-string, concatenation, and .format() injection in SQL. All validated against real examples.
**Missing:** No ORM-level injection detection (e.g., Django raw queries with string interpolation).

### 1.2 Unit tests
**Score: 9/10**
**Evidence:** `test_sql_injection_fstring`, `test_sql_parameterized_clean`, `test_sql_concat_detected` cover positive and negative cases.

---

## 2. Command Injection Detection
**Code:** `EVAL_RE`, `EXEC_RE`, `OS_SYSTEM_RE`, `SHELL_TRUE_RE` (lines 41-44)

### 2.1 Logic
**Score: 9/10**
**Evidence:** Detects `eval(variable)`, `exec(variable)`, `os.system()`, `subprocess(shell=True)`. Distinguishes literals from variables.
**Missing:** No detection of `__import__('os').system()` or indirect eval via `getattr`.

### 2.2 Unit tests
**Score: 9/10**
**Evidence:** `test_command_injection_eval_variable`, `test_eval_literal_clean`, `test_eval_in_test_file_relaxed`, `test_os_system_detected`, `test_shell_true_warning`.

---

## 3. XSS Detection
**Code:** `INNERHTML_RE`, `DANGEROUSLY_RE` (lines 47-48)

### 3.1 Logic
**Score: 8/10**
**Evidence:** Detects `.innerHTML = variable` and `dangerouslySetInnerHTML`. Literal assignments excluded.
**Missing:** No `document.write(variable)` or template literal injection detection.
**To reach 10:** Add `document.write` and backtick template patterns.

### 3.2 Unit tests
**Score: 9/10**
**Evidence:** `test_innerhtml_xss`, `test_innerhtml_literal_clean`, `test_dangerously_set_inner_html`.

---

## 4. Insecure Deserialization / Crypto
**Code:** `PICKLE_LOADS_RE`, `WEAK_HASH_RE` (lines 51-54)

### 4.1 Logic
**Score: 8/10**
**Evidence:** Detects `pickle.loads/load` and `hashlib.md5/sha1`.
**Missing:** No `yaml.load()` without SafeLoader or `marshal.loads()` detection.
**To reach 10:** Add yaml.load and marshal patterns.

### 4.2 Unit tests
**Score: 9/10**
**Evidence:** `test_pickle_loads_detected`, `test_weak_hash_detected`, `test_sha256_clean`.

---

## 5. False Positive Suppression
**Code:** `_is_test_file()`, `_skip_path()`, comment skipping (lines 24-32, 96-98)

### 5.1 Logic
**Score: 9/10**
**Evidence:** Test files get relaxed rules (eval/exec allowed). Comments skipped. node_modules/.git excluded. Non-code files skipped.

### 5.2 Unit tests
**Score: 9/10**
**Evidence:** `test_eval_in_test_file_relaxed`, `test_non_code_file_skipped`, `test_comment_skipped`, `test_clean_code_no_findings`.

---

## 6. Monitor Event Logging
**Code:** `_write_event()` + main() lines 131-152

### 6.1 Logic
**Score: 9/10**
**Evidence:** Writes SECURITY_VULNERABILITY events to qg-monitor.jsonl with vuln_type, severity, file_path, line number.

### 6.2 AdditionalContext output
**Score: 9/10**
**Evidence:** Outputs worst finding: `[Layer 2.8] SECURITY: {vuln_type} in {file} -- {detail}`.

---

## 7. Live Effectiveness
**Score: 8/10**
**Evidence:** 16 events in qg-monitor.jsonl. Actively catching security patterns across sessions.

---

## 8. Integration
### 8.1 settings.json wiring
**Score: 10/10**
**Evidence:** PostToolUse `Write|Edit` registered.

### 8.2 Coverage gap
**Score: 6/10**
**Evidence:** 63% coverage. main() and _write_event untested (lines 111-156). These are integration paths.
**To reach 10:** Add main() mock test with stdin payload, verify JSON output.

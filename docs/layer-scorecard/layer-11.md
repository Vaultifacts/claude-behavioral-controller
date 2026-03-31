# Layer 11 — Commit Quality Gate
**File:** `~/.claude/hooks/qg_layer11.py` (205 LOC, 10 functions)
**Hook event:** PreToolUse on Bash (git commit/push commands)
**Purpose:** Validates commit messages (conventional format), checks staged diffs for secrets, blocks dangerous files (.env/.pem/.key), detects force push
**pytest-cov:** 58% (124 stmts, 52 missed)
**Live events:** 8
**Unit tests:** 28 methods in TestLayer11CommitQualityGate

---

## 1. Commit Message Validation
**Code:** `check_commit_message()`, `CONVENTIONAL_RE` (lines 9-15, 76-84)

### 1.1 Logic
**Score: 9/10**
**Evidence:** Validates against conventional commit regex with [AUTO] prefix support, scope, breaking change indicator. Warns on >200 char messages.
**Missing:** No validation of commit body format (blank line after subject).

### 1.2 Unit tests
**Score: 10/10**
**Evidence:** 6 tests: valid, [AUTO], scope, nonconventional, long message, empty message.

---

## 2. Staged Secret Detection
**Code:** `check_staged_secrets()`, `SECRET_PATTERNS` (lines 17-30, 87-97)

### 2.1 Logic
**Score: 8/10**
**Evidence:** 8 regex patterns covering AWS keys, GitHub PATs, Slack tokens, private keys, passwords.
**Missing:** No SendGrid, no generic high-entropy string detection.

### 2.2 Unit tests
**Score: 9/10**
**Evidence:** AWS key, GitHub PAT, clean diff, empty diff tests.

---

## 3. Dangerous File Detection
**Code:** `check_staged_files()`, `DANGEROUS_FILES` (lines 32, 99-113)

### 3.1 Logic
**Score: 9/10**
**Evidence:** Blocks .env, .pem, .key, .pfx, .p12, credentials, .secret files.

### 3.2 Unit tests
**Score: 9/10**
**Evidence:** .env, .pem, normal files, empty list tests.

---

## 4. Push Safety
**Code:** `check_push()` (lines 115-120)

### 4.1 Logic
**Score: 7/10**
**Evidence:** Detects --force, --force-with-lease, -f flags.
**Missing:** No branch validation, no remote checking.
**To reach 10:** Verify target branch, check if local is ahead of remote.

---

## 5. Integration
### 5.1 Coverage gap
**Score: 6/10**
**Evidence:** 58% coverage. main() untested (lines 148-205). Multiline regex fix applied.
**To reach 10:** Add main() mock test.

### 5.2 settings.json wiring
**Score: 10/10**
**Evidence:** PreToolUse Bash registered.

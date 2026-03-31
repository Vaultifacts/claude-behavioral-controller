# Quality Gate Main — Stop Hook Evaluator
**File:** `~/.claude/hooks/quality-gate.py` (1243 LOC, 28 functions)
**Hook event:** Stop
**Purpose:** Two-layer evaluation: (1) Mechanical checks catch verifiable violations instantly; (2) Haiku LLM evaluates subjective quality. Blocks or passes each response.
**pytest-cov:** 9% (805 stmts, 733 missed — most code is in main flow untested by unit tests)
**Live decisions:** 602 total (443 PASS, 147 BLOCK, 12 DEGRADED-PASS)
**Smoke tests:** 575 pass, covering 16/16 mechanical branches
**Unit tests:** 9 methods across 4 classes (Layer 1 Pivot/Deep)

---

## CRITICAL NOTE
This is the most important file in the system and has the **worst pytest-cov score (9%)**. Smoke tests provide behavioral coverage but cannot verify internal logic paths the way unit tests can. The 1243 lines contain Layers 1, 3, and 4 — none of which have dedicated unit test classes.

---

## 1. Layer 1 — Mechanical Checks
**Code:** `mechanical_checks()` function

### 1.1 Code-edit-without-verification (SMOKE:2,3)
**Score: 8/10**
**Evidence:** Detects Edit/Write without subsequent Bash/Read verification. Smoke tests 2 and 3 cover this.
**Missing:** No unit test. Logic is complex with multiple conditions.

### 1.2 Bash-not-a-real-test (SMOKE:4)
**Score: 7/10**
**Evidence:** Detects Bash commands that look like tests but aren't (e.g., `echo test`). Smoke test 4 covers this.
**Missing:** No unit test. Pattern matching details not independently verified.

### 1.3 Failed-command-not-mentioned (SMOKE:5)
**Score: 7/10**
**Evidence:** Detects when a failed Bash command is not addressed in the response. Smoke test 5 covers.
**Missing:** No unit test.

### 1.4 OVERCONFIDENCE - claims without quoting (SMOKE:6,7)
**Score: 8/10**
**Evidence:** Two patterns: SMOKE:6 catches "all tests pass" without inline output. SMOKE:7 catches bare count claims ("265 passed") without verification output format.
**Missing:** No unit test. Complex regex patterns.

### 1.5 Quantity mismatch (SMOKE:8)
**Score: 6/10**
**Evidence:** Detects when count of items mentioned differs from files actually touched. Smoke test 8 covers.
**Missing:** No unit test. Limited to specific count patterns.

### 1.6 Agent-without-post-verify (SMOKE:14)
**Score: 7/10**
**Evidence:** Detects Agent dispatch without subsequent verification. Smoke test 14.
**Missing:** No unit test.

### 1.7 SMOKE:new — No-tools verifiable claim (commit 57851c9)
**Score: 7/10**
**Evidence:** Catches responses that claim verifiable outcomes without any tools running and no inline evidence. 2 smoke tests in section [121].
**Missing:** No unit test. Complex conditional chain (5 nested if statements with exclusions for confidence challenges, task notifications, and numeric inputs).
**To reach 10:** Add unit tests for each exclusion path.

### 1.8 Overall mechanical checks
**Score: 7/10**
**Evidence:** 16 branches, all smoke tested. But zero unit tests for any branch. Smoke tests exercise the function as a whole but don't isolate individual conditions.
**To reach 10:** Add unit tests for each mechanical check independently.

---

## 2. Layer 3 — Haiku LLM Evaluation
**Code:** `_layer3_run()` (lines ~1039-1110) + `llm_evaluate()` + Haiku prompt

### 2.1 Haiku prompt quality
**Score: 6/10**
**Evidence:** Prompt includes OVERCONFIDENCE definition with CRITICAL PATTERN clause (added commit 0ca0532). Defines TP/FP/FN/TN.
**Missing:** Haiku/Ollama shadow analysis showed 80% disagreement — Haiku was systematically under-detecting OVERCONFIDENCE before SMOKE:new. Post-fix measurement not yet done.
**To reach 10:** Run `qg shadow 10` after several sessions. Target <30% disagreement.

### 2.2 Response parsing
**Score: 5/10**
**Evidence:** Expects single JSON line from Haiku. Parses `ok`/`reason`/`genuine` fields.
**Missing:** No unit test for response parsing. No test for malformed Haiku responses. If Haiku returns multi-line or non-JSON, the parser may fail silently.
**To reach 10:** Add unit tests for parsing edge cases.

### 2.3 Cache hit path (SMOKE:16)
**Score: 7/10**
**Evidence:** Caches recent evaluation results by response hash. Smoke test 16 covers cache hit.
**Missing:** No unit test for cache. No test for cache expiry or size limit.

### 2.4 DEGRADED-PASS
**Score: 7/10**
**Evidence:** If Haiku API fails, returns DEGRADED-PASS instead of blocking. Smoke test 12 covers this.
**Missing:** No unit test. No measurement of how often DEGRADED-PASS occurs in production. Log shows 12 DEGRADED-PASS events — 2% of total.

### 2.5 Unit tests
**Score: 2/10**
**Evidence:** No dedicated unit tests for Layer 3 logic. Only tested through smoke tests.
**To reach 10:** Add unit tests for prompt construction, response parsing, cache, degraded path.

---

## 3. Layer 4 — Session Checkpoint
**Code:** `_layer4_checkpoint()` (lines ~1143-1238)

### 3.1 Logic
**Score: 4/10**
**Evidence:** Collects Layer 3 events, calculates FN pattern frequency, writes to session history. Notifies on repeated FN patterns.
**Missing:** No unit test. No smoke test specifically for Layer 4. It runs as part of the Stop hook but its behavior is not independently verified.
**To reach 10:** Add unit tests. Add a smoke test that verifies checkpoint output.

### 3.2 FN pattern detection
**Score: 3/10**
**Evidence:** Code exists but effectiveness is unknown. No measurement of whether it correctly identifies FN patterns.
**Missing:** No test, no live data, no measurement.

---

## 4. Compliance Retry
**Code:** Lines around SMOKE:10,11

### 4.1 Fix directive
**Score: 7/10**
**Evidence:** When blocking, provides specific instructions for Claude to fix the issue. Smoke test 10.

### 4.2 Mandatory escalation at retry >= 2
**Score: 7/10**
**Evidence:** After 2 failed retries, escalates. Smoke test 11.
**Missing:** No unit test.

---

## 5. Transcript Reading
**Code:** Early in main flow

### 5.1 Logic
**Score: 5/10**
**Evidence:** Reads Claude Code session transcript JSONL to extract response text, tool names, and user request. This is the foundation of all evaluation — if transcript reading fails, nothing works.
**Missing:** No unit test for transcript parsing. Relies on specific JSONL format that could change with Claude Code updates.
**To reach 10:** Add comprehensive transcript parsing tests. Add version detection.

---

## 6. Live Effectiveness
**Score: 8/10**
**Evidence:** 602 decisions (443 PASS, 147 BLOCK, 12 DEGRADED-PASS). 24% block rate. Actively working in production.
**Missing:** No FP/FN rate measurement from production data. The 147 blocks are assumed to be correct but not verified.
**To reach 10:** Sample and manually review 20+ blocks. Calculate FP rate.

---

## 7. Integration
### 7.1 settings.json wiring
**Score: 10/10**
**Evidence:** Stop hook in settings.json with statusMessage "Running quality gate..."

### 7.2 Error handling
**Score: 7/10**
**Evidence:** Haiku failure → DEGRADED-PASS. Transcript missing → early return. Various try/except blocks.
**Missing:** Some error paths are broad except clauses that could swallow unexpected errors.

### 7.3 pytest-cov
**Score: 1/10**
**Evidence:** 9% coverage. 733 of 805 statements never executed by tests. This is the single biggest coverage gap in the entire system.
**To reach 10:** Write unit tests for mechanical_checks(), _layer3_run(), _layer4_checkpoint(), llm_evaluate(), transcript parsing. This would be the highest-impact improvement to the entire scorecard.

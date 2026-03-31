# Precheck Hook — Request Classification + Layer 1 Session Management
**File:** `~/.claude/hooks/precheck-hook.py` (231 LOC, 4 functions) + `precheck_hook_ext.py` (helper)
**Hook event:** UserPromptSubmit
**Purpose:** Classifies user request via Ollama; injects pre-task directive; runs Layer 1 behaviors (task tracking, scope inference, subtask detection, pivot detection, success criteria)
**pytest-cov:** 51% (122 stmts, 60 missed)
**Live events:** 0 (outputs text lines, not monitor events)
**Unit tests:** 10 methods across 3 classes + 5 in TestDetectSubtasks + 2 in TestPrecheckHookGap28Integration = 17 total

---

## 1. Message Extraction
**Code:** `extract_message()` (lines 29-38)

### 1.1 Logic
**Score: 8/10**
**Evidence:** Handles string, dict (`content`/`text`), and list (text blocks) message formats. Returns empty string on unrecognized types.
**Missing:** No test for nested structures or None values within lists.
**To reach 10:** Add adversarial input tests.

### 1.2 Unit tests
**Score: 6/10**
**Evidence:** Basic tests exist. No test for list-type messages.

---

## 2. Ollama Classification
**Code:** Lines 184-201

### 2.1 Logic
**Score: 6/10**
**Evidence:** Sends request to local Ollama (`qwen2.5:7b-instruct`) with 3-second timeout. Parses first word of response as category.
**Missing:** If Ollama is not running, silently defaults to `NONE` — every prompt is unclassified. No logging of classification failures. No measurement of classification accuracy.
**To reach 10:** Add classification accuracy measurement. Log when Ollama is unavailable. Add fallback classification (rule-based).

### 2.2 DEEP override
**Score: 8/10**
**Evidence:** `detect_deep()` from ext module overrides Ollama classification. Ensures DEEP tasks are never missed by LLM misclassification.
**Missing:** No test for the override interaction.

### 2.3 Unit tests
**Score: 3/10**
**Evidence:** Classification logic is in main() which has no unit tests. Ollama call is not mockable without refactoring.
**To reach 10:** Extract classification into testable function. Add mock tests.

---

## 3. Subtask Detection (Gap #28)
**Code:** `detect_subtasks()` (lines 41-53)

### 3.1 Numbered list detection
**Score: 8/10**
**Evidence:** Regex `\d+[.)]\s+(.+)` matches `1. X` and `1) X` formats. Requires >=2 items.
**Missing:** No test for mixed numbering (`1. X` then `2) Y`). No test for indented lists.

### 3.2 Conjunction detection
**Score: 7/10**
**Evidence:** Splits on `and also|additionally|and then|furthermore`. Requires parts >15 chars.
**Missing:** Doesn't detect plain "and" conjunction (too common). Doesn't detect "as well as", "plus", "along with".
**To reach 10:** Consider expanding conjunction patterns. Add tests for edge cases.

### 3.3 Unit tests
**Score: 8/10**
**Evidence:** 5 tests in TestDetectSubtasks + 2 in TestPrecheckHookGap28Integration. Covers numbered lists, conjunctions, too-short parts.

---

## 4. Layer 1 Session Management
**Code:** `_run_layer1()` (lines 56-171)

### 4.1 FN alert delivery (Behavior 11)
**Score: 7/10**
**Evidence:** Delivers pending `layer3_pending_fn_alert` and clears it. Simple and correct.
**Missing:** No test for this specific behavior.

### 4.2 Scope creep clearing (Behavior 10)
**Score: 6/10**
**Evidence:** Approval keywords ("proceed", "that's fine", "go ahead", "continue", "ok") clear SCOPE_CREEP events.
**Missing:** "ok" would match any message containing "ok" as substring (e.g., "look at the token"). No word-boundary check. This is a false-positive risk.
**To reach 10:** Add word boundaries to keyword matching. Add test for false positive.

### 4.3 Pivot detection (Behavior 4+5)
**Score: 7/10**
**Evidence:** Uses Jaccard similarity (<0.3 threshold) between active task and new message. On pivot, resets task_id and scope.
**Missing:** No test for the 0.3 threshold boundary. No test for empty active description.
**To reach 10:** Add boundary tests.

### 4.4 Scope file inference (Behavior 2)
**Score: 6/10**
**Evidence:** Delegates to `infer_scope_files()` in ext module. Results stored in `layer1_scope_files`.
**Missing:** No test for the inference quality. If inference returns wrong files, all downstream scope-based checks are wrong.
**To reach 10:** Test inference with various real-world prompts.

### 4.5 Codebase scan (Behavior 3, Gap #30)
**Score: 6/10**
**Evidence:** Glob scan for DEEP/MECHANICAL tasks with 3-second deadline. Adds found files to scope.
**Missing:** No test for the glob scan. No test for timeout behavior. Scan could find irrelevant files with common names.
**To reach 10:** Add tests for scan accuracy and timeout.

### 4.6 Success criteria (Behavior 3)
**Score: 7/10**
**Evidence:** Category-specific criteria map with HIGH/CRITICAL impact additions. Stored in state.
**Missing:** Criteria are never evaluated — no downstream layer checks whether criteria were met.
**To reach 10:** Connect criteria to Layer 3/4 evaluation.

### 4.7 Multi-task splitting (Behavior 6)
**Score: 8/10**
**Evidence:** Sets `layer1_subtask_count`, `active_subtask_id`, appends per-subtask success criteria. Outputs `[monitor:layer1] Multi-task: N subtasks detected.`
**Missing:** No tracking of subtask completion within the session.

### 4.8 Turn counter reset (line 168)
**Score: 10/10**
**Evidence:** Resets `layer2_turn_event_count = 0` and `layer15_turn_warnings = []` on each new user prompt. **This is the fix for the Layer 2 rate limiter concern** — the counter IS reset per-turn, just from precheck-hook, not from Layer 2 itself.
**Adversarial:** Confirmed by reading the code directly. Layer 2's counter accumulates within a turn but resets here at the start of each new user prompt.

### 4.9 DEEP scope gate (Behavior 7)
**Score: 7/10**
**Evidence:** Warns if DEEP task starts with no prior reads.
**Missing:** No test.

---

## 5. Live Effectiveness
**Score: 5/10**
**Evidence:** We see precheck output in every session (`[pre-check:OVERCONFIDENCE]`, `[monitor:layer1] Multi-task:` etc). It runs on every prompt. But effectiveness of classification is unmeasured — no accuracy data for Ollama's categorization.
**To reach 10:** Add classification accuracy logging. Sample and manually review 50+ classifications.

---

## 6. Integration
### 6.1 settings.json wiring
**Score: 10/10**
**Evidence:** UserPromptSubmit hook with 5-second timeout.

### 6.2 Error handling
**Score: 7/10**
**Evidence:** Ollama failure → silent default to NONE. Layer 1 state update wrapped in try/except.
**Missing:** Silent failure means misclassification is invisible.

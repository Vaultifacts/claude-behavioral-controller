# Layer 12 — User Satisfaction Tracking
**File:** `~/.claude/hooks/qg_layer12.py` (160 LOC, 4 functions)
**Hook event:** UserPromptSubmit
**Purpose:** Classifies user messages as frustration/satisfaction/confusion/neutral signals about the previous response
**pytest-cov:** 58% (89 stmts, 37 missed)
**Live events:** 4
**Unit tests:** 22 methods in TestLayer12UserSatisfaction

---

## 1. Frustration Detection
**Code:** `FRUSTRATION_PATTERNS` (lines 23-28)

### 1.1 Logic
**Score: 8/10**
**Evidence:** 6 patterns: rejection, retry_request, correction, direct_negative, stop_command, repetition. Weighted scoring (-1 to -3).
**Missing:** No detection of emoji-based frustration, sarcasm, or implicit frustration ("fine, whatever").

### 1.2 Unit tests
**Score: 10/10**
**Evidence:** 5 frustration tests: wrong, try again, I said, that's not, undo.

---

## 2. Satisfaction Detection
**Code:** `SATISFACTION_PATTERNS` (lines 30-35)

### 2.1 Logic
**Score: 8/10**
**Evidence:** 5 patterns: gratitude, praise, approval, numbered_selection, affirmation.
**Missing:** No detection of task completion signals ("moving on to..."), emoji thumbs up.

### 2.2 Unit tests
**Score: 10/10**
**Evidence:** 5 satisfaction tests: thanks, perfect, lgtm, numbered, yes.

---

## 3. Confusion Detection
**Code:** `CONFUSION_PATTERNS` (lines 37-40)

### 3.1 Logic
**Score: 7/10**
**Evidence:** 3 patterns: confusion, clarity_request, question.
**Missing:** Rephrased questions (user asking same thing differently) not detected.

### 3.2 Unit tests
**Score: 9/10**
**Evidence:** 2 confusion tests: what, explain.

---

## 4. Mixed Signal Handling
**Score: 8/10**
**Evidence:** Weighted scoring system — frustration signals outweigh satisfaction when both present. Tested with mixed input.

---

## 5. Integration
### 5.1 Coverage gap
**Score: 6/10**
**Evidence:** 58% coverage. main() and session state tracking untested.
**To reach 10:** Add main() mock test with satisfaction history tracking.

### 5.2 settings.json wiring
**Score: 10/10**
**Evidence:** UserPromptSubmit registered.

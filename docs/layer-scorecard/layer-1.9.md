# Layer 1.9 — Change Impact Analysis
**File:** `~/.claude/hooks/qg_layer19.py` (124 LOC, 5 functions)
**Hook event:** PreToolUse on Edit/Write
**Purpose:** Counts dependents of the target file via grep; stores impact level (LOW/MEDIUM/HIGH/CRITICAL) in session state for other layers to use
**pytest-cov:** 70% (81 stmts, 24 missed)
**Live events:** 0 (outputs additionalContext for HIGH/CRITICAL only, no monitor events)
**Unit tests:** 11 methods across 2 classes

---

## 1. Dependent Counting
**Code:** `count_dependents()` (lines 24-47)

### 1.1 Grep logic
**Score: 6/10**
**Evidence:** Runs `grep -rl` with patterns `import.*stem`, `from.*stem.*import`, `require.*stem` for `.py`, `.js`, `.ts` files. 3-second timeout.
**Missing:** Regex `import.*stem` is very broad — matches `import something_stem_something`. Only searches `working_dir` — misses cross-project deps. Does not handle monorepo structures.
**To reach 10:** Tighten import regex (word boundary on stem). Consider caching results. Test with various project structures.

### 1.2 Timeout handling
**Score: 8/10**
**Evidence:** 3-second timeout on subprocess. On timeout, breaks and returns partial results.
**Missing:** No logging or notification when timeout occurs. User doesn't know results are partial.

### 1.3 Unit tests
**Score: 6/10**
**Evidence:** Tests mock grep results. `test_count_dependents_empty` and basic cases exist.
**Missing:** No test for timeout behavior. No test for the grep regex specifics.

---

## 2. Impact Level Computation
**Code:** `compute_impact_level()` (lines 50-61)

### 2.1 Logic
**Score: 9/10**
**Evidence:** `CORE_PATTERNS` regex → CRITICAL. `< low_threshold` → LOW. `< med_threshold` → MEDIUM. Else HIGH. Configurable thresholds via `qg-rules.json`.
**Missing:** No test for configurable thresholds.

### 2.2 Core file detection
**Score: 8/10**
**Evidence:** `CORE_PATTERNS` matches `utils|shared|common|base|core|config|settings|constants|helpers` with `.py|.js|.ts` extension.
**Missing:** Doesn't match `index.js`, `__init__.py`, or `main.py` which are often core files. No `.go` or other extensions.
**To reach 10:** Expand core patterns. Make configurable.

### 2.3 Unit tests
**Score: 8/10**
**Evidence:** Tested for CRITICAL (core pattern), LOW, MEDIUM, HIGH thresholds.

---

## 3. Impact Cache
**Code:** Lines 67-72

### 3.1 Logic
**Score: 8/10**
**Evidence:** Per-session 1-hour cache by file_path. Avoids repeated grep calls for the same file.
**Missing:** Cache is never invalidated if a new dependent is added during the session.

### 3.2 Unit tests
**Score: 6/10**
**Evidence:** Cache behavior tested in TestLayer19Extra.
**Missing:** No test for cache expiry.

---

## 4. Downstream Integration
### 4.1 layer8_regression_expected flag
**Score: 7/10**
**Evidence:** Line 91: Sets `layer8_regression_expected = True` on HIGH/CRITICAL impact. Layer 8 uses this to expect test failures.
**Missing:** No end-to-end test verifying this flag flows correctly to Layer 8.

### 4.2 Severity promotion in other layers
**Score: 7/10**
**Evidence:** `layer19_last_impact_level` is read by Layer 2 (severity promotion), Layer 1.5 (warn→block promotion), Layer 1.7 (trigger intent verification).
**Missing:** No integration test verifying the cross-layer flow.

---

## 5. Live Effectiveness
**Score: 3/10**
**Evidence:** No events in monitor log. Only fires additionalContext for HIGH/CRITICAL. If working_dir has no dependents (or grep is slow), nothing happens.
**To reach 10:** Add monitor logging for all impact assessments, not just HIGH/CRITICAL.

---

## 6. Integration
### 6.1 settings.json wiring
**Score: 9/10**
**Evidence:** PreToolUse `*` — but early-returns for non-Edit/Write. Could optimize with matcher.

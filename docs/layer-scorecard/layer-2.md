# Layer 2 — Mid-task Monitoring
**File:** `~/.claude/hooks/qg_layer2.py` (184 LOC, 4 functions)
**Hook event:** PostToolUse `*` (fires after every tool call)
**Purpose:** Detects 8 quality violation categories from observable tool patterns
**pytest-cov:** 93% (107 stmts, 8 missed — lines 20-21, 96-97, 108-109, 134, 184)
**Live events:** 1932 (87.6% of all monitor events)
**Unit tests:** 25 methods across 2 classes (TestLayer2Detection: 7, TestLayer2Extra: 18)

---

## Overall Score: derived from sections below
*See each section for individual scores. No single number — drill into sections to find weaknesses.*

---

## 1. LOOP_DETECTED
**Code:** `detect_loop()` (lines 24-32) + loop call in `main()` (lines 131-134)

### 1.1 Pattern matching — what tools/commands does it track?
**Score: 7/10**
**Evidence:** Matches on `(tool_name, target)` tuples where target is `file_path || pattern || command[:60]`. Covers Edit, Write, Bash, Read, Grep, Glob, Agent — any tool.
**Missing:** No distinction between similar but different commands (e.g., `grep foo` vs `grep bar` would be different targets, which is correct — but `Bash("pytest -q")` repeated 3x would trigger even if each run is intentional after fixes).
**To reach 10:** Add exemption for known-legitimate repeat commands (e.g., test re-runs after edits). Define which repeat patterns are legitimate vs. problematic.

### 1.2 Threshold logic (fires at N=3)
**Score: 6/10**
**Evidence:** Default threshold is 3 via `l2_rules.get('loop_same_tool_count', 3)`. Configurable via `qg-rules.json`.
**Missing:** No unit test verifies the threshold is read from config. No test for threshold=2 (should not fire) or threshold=4 (boundary). No evidence the default of 3 is optimal.
**To reach 10:** Add unit test for config-driven threshold. Add boundary tests at N-1 and N. Validate N=3 against real log data (what % of 3-repeat sequences are true loops vs. legitimate retries?).

### 1.3 Argument sensitivity (same cmd, different args)
**Score: 8/10**
**Evidence:** Target key uses `command[:60]` — two commands with different args but same first 60 chars would wrongly match. Two commands with same intent but different paths would not match (correct).
**Missing:** No test for the 60-char truncation edge case. No test for commands that differ only after char 60.
**To reach 10:** Add test for truncation boundary. Consider whether 60 chars is sufficient for real-world commands.

### 1.4 Empty target handling
**Score: 9/10**
**Evidence:** Line 26-27: `if not target: return None` — explicitly skips loop detection when target is empty. Unit test `test_loop_empty_target_skips` in TestLayer2Extra confirms this.
**Missing:** No adversarial test (e.g., target = whitespace only, target = `"0"`, target = `False`).
**To reach 10:** Add edge case tests for falsy but non-empty targets.

### 1.5 Reset behavior between tasks
**Score: 3/10**
**Evidence:** `turn_history` is persisted in session state (`layer2_turn_history`) and trimmed to last 20 entries (line 147). It is reset to `[]` only at session start by Layer 0 (line 130).
**Missing:** No reset when task changes. If task A causes 2 loops and task B causes 1 of the same tool/target, it fires incorrectly. No unit test for cross-task leakage. No unit test for the 20-entry trim.
**To reach 10:** Add task-boundary reset logic. Add unit test for cross-task non-leakage. Add unit test for history trimming.

### 1.6 Unit test coverage for LOOP_DETECTED
**Score: 6/10**
**Evidence:** `test_detect_loop_fires_at_threshold` and `test_detect_loop_below_threshold` exist in TestLayer2Detection. `test_loop_empty_target_skips` in TestLayer2Extra.
**Missing:** No test for configurable threshold. No test for history trimming at 20. No test for cross-task leakage. No boundary test at exactly N-1.
**To reach 10:** Add tests for all items listed above.

### 1.7 Live fire rate
**Score: 10/10**
**Evidence:** `grep -c LOOP_DETECTED ~/.claude/qg-monitor.jsonl` shows this fires regularly in production across multiple sessions. Latest example: `2026-03-30T15:24:10 | LOOP_DETECTED | Bash on 'cd /c/Users/Matt1/Vaultifacts && PYTHONIOENCODING=utf-8 pyth' called 3 times`.
**Adversarial:** Real production data confirms it catches actual loops.

---

## 2. ERROR_IGNORED
**Code:** Lines 54-60

### 2.1 Error pattern matching
**Score: 6/10**
**Evidence:** `ERROR_RE` matches: `error|exception|traceback|failed|exit code [1-9]|errno|not found|permission denied`. Case-insensitive.
**Missing:** Does not match `Error:` at start of line specifically. Matches `"not found"` which could appear in legitimate output (e.g., "resource not found — creating new one"). No test for false positive scenarios.
**To reach 10:** Add false-positive tests. Consider narrowing patterns to reduce FPs (e.g., only match "error" when preceded by severity indicators).

### 2.2 Lookback window
**Score: 7/10**
**Evidence:** Checks `prev_calls[-3:]` — last 3 tool calls. If ANY had an error in response, current non-read tool triggers ERROR_IGNORED.
**Missing:** No test for the 3-call window boundary (error 4 calls ago should not trigger). No test for exactly 3 calls ago.
**To reach 10:** Add boundary test for lookback window.

### 2.3 Tool exemptions
**Score: 8/10**
**Evidence:** Line 55: `tool_name not in ('Read', 'Glob', 'Grep')` — read-like tools are exempt. This is correct (reading after an error is investigating, not ignoring).
**Missing:** No test specifically validating the exemption list. Agent and Write are not exempt — is that correct? (Dispatching a subagent after an error could be legitimate.)
**To reach 10:** Add explicit test for each exempt and non-exempt tool. Consider whether Agent should be exempt.

### 2.4 False positive rate
**Score: 4/10**
**Evidence:** No measurement exists. The regex `not found` is known to match legitimate output. 21 ERROR_IGNORED events in recent sessions — unknown how many are true violations vs. false positives.
**Missing:** No FP analysis performed. No shadow/manual review of ERROR_IGNORED events.
**To reach 10:** Manually review 20+ ERROR_IGNORED events from the log. Calculate FP rate. Adjust regex if >10% FP.

### 2.5 Unit test coverage
**Score: 7/10**
**Evidence:** `test_error_ignored_detection` in TestLayer2Detection tests basic case. `test_error_ignored_reads_exempt` in TestLayer2Extra tests exemption. `test_error_in_old_history_still_detects` tests within window.
**Missing:** No test for lookback boundary. No test for false positive scenarios.
**To reach 10:** Add boundary and FP tests.

### 2.6 Live fire rate
**Score: 10/10**
**Evidence:** 21 events across 6 sessions in the log. Fires consistently in production.

---

## 3. LAZINESS (Edit without Read)
**Code:** Lines 43-47

### 3.1 Detection logic
**Score: 8/10**
**Evidence:** Checks `tool_name == 'Edit' and fp and fp not in reads`. `reads` comes from `layer15_session_reads` which Layer 1.5 populates when Read tool is used.
**Missing:** No path normalization — `C:\Users\Matt1\foo.py` and `/c/Users/Matt1/foo.py` would be treated as different files on Windows/Git Bash.
**To reach 10:** Normalize paths before comparison. Add test for path format mismatch.

### 3.2 Resolution tracking
**Score: 7/10**
**Evidence:** Lines 155-159: If a Read on the same `target_file` occurs later, LAZINESS events are marked `addressed`.
**Missing:** No test for the resolution transition. No test for partial resolution (read one file, not the other).
**To reach 10:** Add resolution transition tests.

### 3.3 Unit tests
**Score: 7/10**
**Evidence:** `test_laziness_edit_without_read` and `test_laziness_edit_after_read_ok` exist. Basic positive and negative cases covered.
**Missing:** No path normalization test. No resolution test.
**To reach 10:** Add the missing tests.

### 3.4 Live fire rate
**Score: 10/10**
**Evidence:** Multiple LAZINESS events in today's log across sessions.

---

## 4. INCORRECT_TOOL (Bash instead of dedicated tool)
**Code:** Lines 49-52

### 4.1 Detection logic
**Score: 7/10**
**Evidence:** `BASH_TOOL_RE` matches `grep|cat|find|head|tail` in Bash commands.
**Missing:** Does not match `rg` (ripgrep), `sed`, `awk` (Layer 1.5's regex does include `sed|awk` but Layer 2 doesn't). Regex has no word boundary after the match — could match `category` (contains `cat`). Wait — it does use `\b` on both sides. But `\bcat\b` would match the standalone word "cat" in comments or strings.
**To reach 10:** Ensure regex doesn't match inside quoted strings or comments. Align Layer 2 regex with Layer 1.5 regex. Add tests for `sed`, `awk`, `rg`.

### 4.2 Unit tests
**Score: 7/10**
**Evidence:** `test_incorrect_tool_bash_grep` tests basic case. `test_incorrect_tool_skips_non_bash` tests non-Bash.
**Missing:** No test for `cat`, `find`, `head`, `tail` individually. No false positive test.
**To reach 10:** Add tests for each matched command. Add FP test.

### 4.3 Live fire rate
**Score: 10/10**
**Evidence:** Frequent in production logs.

---

## 5. SCOPE_CREEP (Write/Edit outside scope)
**Code:** Lines 62-66

### 5.1 Detection logic
**Score: 6/10**
**Evidence:** Checks if `fp` doesn't match any of `layer1_scope_files` using `fp.endswith(s) or s in fp`. Only fires when scope is set (non-empty).
**Missing:** No path normalization. `s in fp` is substring match — `foo.py` would match `/bar/foo.py/baz` (unlikely but possible). No test for scope being empty (should not fire).
**To reach 10:** Use proper path comparison. Add edge case tests.

### 5.2 Unit tests
**Score: 5/10**
**Evidence:** Tested in TestLayer2Extra but no dedicated test for empty scope, path normalization, or substring false match.
**To reach 10:** Add dedicated tests.

### 5.3 Live fire rate
**Score: 2/10**
**Evidence:** No SCOPE_CREEP events found in the production log. Either the detection never triggers, or `layer1_scope_files` is never populated.
**To reach 10:** Investigate why it never fires. If scope is never set, this detection is dead code.

---

## 6. ASSUMPTION (Write without Read)
**Code:** Lines 68-72

### 6.1 Detection logic
**Score: 7/10**
**Evidence:** Similar to LAZINESS but for Write tool. Write to an unread file suggests blind overwrite.
**Missing:** Same path normalization issue as LAZINESS.
**To reach 10:** Normalize paths.

### 6.2 Unit tests
**Score: 6/10**
**Evidence:** Basic test exists. No path edge case tests.

### 6.3 Live fire rate
**Score: 8/10**
**Evidence:** 4 events in recent sessions.

---

## 7. INCOMPLETE_COVERAGE
**Code:** Lines 74-81

### 7.1 Detection logic
**Score: 5/10**
**Evidence:** Fires when same file edited 2+ times in last 5 turns while other scope files untouched. Requires scope to have >1 file.
**Missing:** Only checks if scope files were *targeted* in recent turns, not if they were *read*. A file could have been read 20 turns ago but not edited — that's not incomplete coverage.
**To reach 10:** Consider whether the logic correctly identifies incomplete coverage vs. focused editing.

### 7.2 Unit tests
**Score: 3/10**
**Evidence:** No dedicated test found for INCOMPLETE_COVERAGE.
**To reach 10:** Add positive and negative unit tests.

### 7.3 Live fire rate
**Score: 0/10**
**Evidence:** No INCOMPLETE_COVERAGE events in the production log.
**To reach 10:** Investigate if this ever fires. If not, it may be dead code.

---

## 8. OUTPUT_UNVALIDATED (consecutive edits, no validation)
**Code:** Lines 83-88

### 8.1 Detection logic
**Score: 6/10**
**Evidence:** Fires when 2+ consecutive Edit/Write calls with no Read/Bash between them. Checks `prev_calls[-3:]`.
**Missing:** This overlaps with Layer 2.5 (syntax validation) but detects a different thing (no validation step, not necessarily a syntax error). No dedup with Layer 2.5.
**To reach 10:** Clarify relationship with Layer 2.5. Add dedup or differentiation logic.

### 8.2 Unit tests
**Score: 5/10**
**Evidence:** Basic test exists for consecutive edits.
**Missing:** No test for the boundary (exactly 2 consecutive vs. 1).

### 8.3 Live fire rate
**Score: 3/10**
**Evidence:** Very few events — this detection rarely triggers in practice.

---

## 9. Integration
### 9.1 settings.json wiring
**Score: 10/10**
**Evidence:** Wired as PostToolUse `*` in settings.json line 311-317. Fires after every tool call. Matcher is `*` (universal).

### 9.2 Error handling
**Score: 8/10**
**Evidence:** `main()` wraps stdin parse in try/except (lines 94-97). `_write_event` silently catches write failures. No crash risk from malformed input.
**Missing:** If `ss.read_state()` or `ss.write_state()` fails, no fallback. Silent failure could mean events are lost.
**To reach 10:** Add fallback for state read/write failure.

### 9.3 Async/timeout configuration
**Score: 9/10**
**Evidence:** Not marked async in settings.json (correct — it needs to run synchronously to track state). No timeout set — relies on default.
**Missing:** Explicit timeout not set. If grep or file reads hang, the hook could block indefinitely.
**To reach 10:** Set an explicit timeout in settings.json.

---

## 10. Severity escalation via Layer 1.9
**Code:** Lines 123-128

### 10.1 Logic
**Score: 8/10**
**Evidence:** Promotes `info→warning` and `warning→critical` when Layer 1.9 reports HIGH/CRITICAL impact.
**Missing:** No test for the promotion path. What happens to events already at `critical`? (They stay at `critical` — promotion dict doesn't have a `critical` key, so `.get()` returns the existing value. Correct.)

### 10.2 Unit tests
**Score: 4/10**
**Evidence:** No dedicated test for severity promotion.
**To reach 10:** Add tests for each promotion path and the no-promotion case.

---

## 11. Rate limiting
**Code:** Lines 140-144

### 11.1 Logic
**Score: 7/10**
**Evidence:** Limits events per turn to `events_limit` (default 5 from config). Counter persists in state.
**Missing:** No test for rate limiting. No test for the counter reset between turns.
**To reach 10:** Add unit tests.

### 11.2 Counter reset
**Score: 8/10**
**Evidence:** `layer2_turn_event_count` is reset to 0 at session start (Layer 0 line 129) AND at each new user prompt (precheck-hook.py line 168: `state['layer2_turn_event_count'] = 0`). The counter IS per-turn, not per-session. The reset happens in the precheck hook, not in Layer 2 itself.
**Missing:** No unit test verifying the cross-file reset behavior.
**To reach 10:** Add integration test that confirms the full turn lifecycle: precheck resets → Layer 2 increments → precheck resets again.

---

## 12. Live Effectiveness
**Score: 10/10**
**Evidence:** 1932 events (87.6% of all monitor events). Fires across every session. Categories detected in production: LOOP_DETECTED, ERROR_IGNORED, LAZINESS, INCORRECT_TOOL, ASSUMPTION, OUTPUT_UNVALIDATED. Most active and effective layer in the system.
**Missing:** SCOPE_CREEP and INCOMPLETE_COVERAGE have zero events — possible dead code.

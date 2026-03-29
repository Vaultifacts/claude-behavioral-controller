# Quality Gate Monitor — Formal Specification
Date: 2026-03-28 | Status: Approved for implementation | Author: Matt1

---

## 1. Overview

The Quality Gate Monitor is a permanent, automated monitoring system layered on top of the existing Haiku quality gate. It operates in three phases of the Claude Code lifecycle: before work begins (prevention), during work (real-time detection), and after each response (classification and reporting). No manual labeling is required at any point.

The system is non-destructive: every component extends existing infrastructure rather than replacing it. The existing `quality-gate.py`, `precheck-hook.py`, and `qg-feedback.py` are extended in-place.

---

## 2. Goals

1. Classify every gate event into the correct confusion matrix bucket (TP / FP / FN / TN) automatically.
2. Detect errors, laziness, and assumptions mid-task — not only at response time.
3. Pre-emptively enforce good behavior before tool use begins.
4. Surface actionable patterns across sessions to drive continuous improvement.
5. Require zero manual labeling, zero separate daemon processes, and zero Haiku token spend beyond what already exists.

### Non-Goals

- Replacing or modifying the existing Haiku quality gate decision (pass/block).
- Real-time correction of Claude's behavior (the monitor observes and reports; enforcement is limited to the pre-task and pre-tool layers).
- Supporting multi-user or multi-machine deployments.

---

## 3. Confusion Matrix

| Label | Name | Meaning |
|---|---|---|
| TP | Failure Prevented | Gate blocked a genuinely bad response |
| FP | False Block | Gate blocked a good response (unnecessary block) |
| FN | Missed Failure | Gate passed a bad response (should have blocked) |
| TN | Compliant, No Block | Gate correctly passed a good response |

Classification is automatic (rules + Haiku). The existing Stop hook already calls Haiku for the pass/block decision; Layer 3 extends that same call with FN detection prompts at no additional API cost. The local Ollama model is NOT used for Layer 3 classification — only Haiku.

Layer 3 classification messages and their delivery mechanism:
- **TP**: Appended to the existing gate block message (Stop hook already returns `decision: block`; classification is added to that message text).
- **FP**: Appended to the existing gate block message.
- **FN**: Delivered via `additionalContext` injected into the next turn's prompt (since the gate passed, injection happens at the start of the following UserPromptSubmit).
- **TN**: Silent.

Message format: `[monitor] <label> — <brief reason>` (e.g., `[monitor] Missed Failure — claimed fix without re-reading file`)

---

## 4. Architecture Overview

```
SessionStart
  └── Layer 0 (session context injection)
  └── Layer ENV (environment validation)

UserPromptSubmit
  └── Layer 1 (pre-task enforcement, extended precheck-hook.py)

PreToolUse
  └── Layer ENV (mid-session re-validation, any tool with a file path)
  └── Layer 1.5 (tool validation rules)
  └── Layer 1.7 (user intent verification, PLANNING/DEEP tasks only)
  └── Layer 1.8 (hallucination detection)
  └── Layer 1.9 (change impact analysis)
  └── Layer 2.7 (testing coverage verification, Edit/Write only)
  └── Layer 5 (subagent dispatch preparation, Agent tool calls)

PostToolUse
  └── Layer 2 (mid-task monitoring, 8 categories)
  └── Layer 2.5 (output validity, Write/Edit only)
  └── Layer 2.6 (consistency enforcement, Write/Edit only)
  └── Layer 5 (subagent result merging, Agent tool calls)
  └── Layer 8 (regression detection, Bash test commands)

Stop (extended quality-gate.py)
  └── Layer 3 (post-response classification: TP/FP/FN/TN)
  └── Layer 3.5 (recovery tracking state update)
  └── Layer 4 (incremental session checkpoint)

Layer 4 trigger (async, on each Stop evaluation)
  └── Layer 6 (cross-session pattern analysis, if qg-monitor.jsonl has grown)
  └── Layer 7 (rule refinement suggestions, if repeat FN patterns detected)
  └── Layer 9 (confidence calibration, if ≥5 new responses since last run)
  └── Layer 10 (audit trail integrity, if >7 days since last check)

PreCompact / PostCompact
  └── Layer 4.5 (context preservation)

On-demand (qg commands)
  └── Layer 9 (also via qg analyze)
  └── Layer 10 (also via qg monitor / qg integrity)

Cross-cutting (all layers)
  └── Session State (qg-session-state.json)
  └── Notification Router (priority, dedup, delivery)
  └── Dashboard (qg monitor command)
```

---

## 5. Data Files

| File | Purpose | Owner |
|---|---|---|
| `~/.claude/qg-monitor.jsonl` | All classified events (all layers). Rotated at 10,000 lines → `qg-monitor-YYYY-MM.jsonl` | Layers 2, 3, 4, 5 |
| `~/.claude/qg-session-state.json` | Live cross-layer session state. Schema-versioned. 1MB cap. | All layers |
| `~/.claude/qg-session-history.md` | Layer 4 session summaries, last 30 sessions | Layer 4 |
| `~/.claude/qg-session-archive.md` | Older session summaries (pruned from history) | Layer 4 |
| `~/.claude/qg-cross-session.json` | Layer 6 pattern analysis output, read by Layer 0 | Layers 0, 6 |
| `~/.claude/qg-calibration.jsonl` | Layer 9 confidence calibration records | Layers 3, 9 |
| `~/.claude/qg-rules.json` | All tunable parameters for all layers (see Section 10). No code changes required to tune. | All configurable layers (read); Layer 7 (writes suggestions) |
| `~/.claude/qg-env.json` | Project environment expectations (Layer ENV) | Layer ENV |
| `~/.claude/qg-preservation-config.json` | Layer 4.5 explicit inclusion/exclusion list | Layer 4.5 |
| `~/.claude/qg-rule-suggestions.md` | Layer 7 pending rule suggestions with status | Layer 7 |
| `~/.claude/qg-quarantine.jsonl` | Layer 10 corrupt audit entries | Layer 10 |
| `~/.claude/qg-monitor-YYYY-MM.jsonl` | Rotated archive of `qg-monitor.jsonl` (one file per month) | Layer 10 |
| `~/.claude/qg-shadow-trend.log` | Existing shadow mode trend (unchanged) | Existing |

---

## 6. Cross-Cutting Components

### 6.1 Session State (`qg-session-state.json`)

Shared state file written and read by all layers within a session.

**Schema requirements:**
- `schema_version` field; migration function runs on load when version changes.
- `session_uuid` generated at session start; used for continuation detection in Layer 4.5.
- Each field tagged `turn_scoped` or `session_scoped`.
- Staleness rule: if file is >24 hours old with a non-matching session UUID, it is reset.
- Write locking: `.lock` file prevents concurrent writes. Reads are non-blocking.
- Size cap: 1MB; oldest `turn_scoped` data pruned first when cap is reached.
- Subagent namespace: `session_state.subagents[subagent_id]` — isolated per dispatched agent.

**Key fields (representative, not exhaustive):**
- `session_uuid`, `session_start_ts`, `active_task_id`, `active_subtask_id`
- `active_task_description` — raw text of the current active task (used by Layer 1 pivot detection)
- `task_success_criteria[]` — written by Layer 1, read by Layer 4
- `layer1_task_category` — MECHANICAL / ASSUMPTION / OVERCONFIDENCE / PLANNING / DEEP
- `layer1_scope_files[]` — files in scope for current task (Layer 1)
- `layer2_unresolved_events[]` — open mid-task events (Layer 2)
- `layer2_elevated_scrutiny` — boolean flag (set when 3+ criticals in one turn)
- `layer15_session_reads[]` — session-scope read tracking (Layer 1.5)
- `layer15_override_pending{}` — one-time override token set by Layer 3, consumed by Layer 1.5
- `layer19_impact_cache{}` — file → impact level cache (Layer 1.9)
- `layer35_recovery_events[]` — open recovery tracking entries (Layer 3.5)
- `layer25_syntax_failure` — set by Layer 2.5 when a written file fails syntax check; read by Layer 3 to raise FN probability; cleared after each Stop evaluation
- `layer3_pending_fn_alert` — FN message written by Stop hook (Layer 3); injected by Layer 1 (UserPromptSubmit) at start of next turn, then cleared
- `layer3_last_response_claims[]` — key factual claims extracted from previous response text; used by Layer 3 MEMORY_OVER_VERIFICATION detection each turn
- `layer_env_baseline{}` — environment state at session start
- `layer_env_test_baseline[]` — set of test names failing at session start (Layer ENV)
- `layer8_regression_expected` — boolean flag: HIGH/CRITICAL change made, regression check pending
- `last_integrity_check_ts` — timestamp of last Layer 10 run (for 7-day interval check)
- `notification_delivery[]` — router delivery tracking (delivered / queued / dropped per notification)
- `notification_pending_criticals[]` — CRITICALs queued by Stop-time or async layers for delivery at next PreToolUse

### 6.2 Notification Router

Central priority routing and deduplication for all layer notifications.

**Priority levels:** CRITICAL > WARNING > INFO

**Delivery channels:**
- CRITICAL → `additionalContext` injection at the earliest available hook:
  - If called from within PreToolUse or PostToolUse: injected immediately in that hook's response.
  - If called from Stop hook, Layer 4, or async-triggered layers (9, 10): written to a `notification_pending_criticals[]` queue in session state; delivered by the next PreToolUse invocation.
- WARNING → end-of-turn batch delivered via Stop hook's `additionalContext` (appended to block message if blocked; injected as pass-through context if passed)
- INFO → log only (`qg-monitor.jsonl`)

**Deduplication:** Same layer + category + file within 60 seconds = one notification.

**Rate limit:** Max 3 CRITICAL notifications per turn; excess queued to next turn.

**Delivery states:** `delivered`, `queued`, `dropped` — tracked in session state.

### 6.3 Dashboard (`qg monitor` command)

Unified read-only dashboard added to `qg-feedback.py` as a new subcommand.

**Displays:**
- Layer 2 events by category + severity (current session)
- Layer 3 TP/FP/FN/TN with confidence distribution (current session + all-time)
- Recovery rate: issued / resolved / timed-out
- Quality score + 5-session trend with direction (improving / degrading / stable)
- Subagent events with parent context
- Layer 9 calibration: stated confidence vs actual accuracy
- Pending rule suggestions count
- Audit trail status

Additional commands:
- `qg integrity` — Layer 10 quarantine report
- `qg analyze` — trigger Layer 6 cross-session pattern analysis + Layer 9 confidence calibration on demand
- `qg rules` — view pending rule suggestions
- `qg rules apply N` / `qg rules reject N "reason"` — Layer 7 approval UX

---

## 7. Layer Specifications

### Layer 0 — Session Start Context Injection

**Hook:** SessionStart

**Purpose:** Inject cross-session patterns as context at session start so Claude doesn't repeat known failure modes. This is a temporary safeguard that phases out as the system is tuned.

**Behavior:**
1. Reads `qg-cross-session.json` (output of Layer 6).
2. Identifies current task type from initial prompt context available at session start.
3. Injects patterns in priority order: most relevant to current task type first.
4. Caps injection size to avoid excessive context consumption (configurable in `qg-rules.json`).
5. Retires patterns absent from last 5 consecutive sessions.
6. Resolves contradictory patterns using recency + frequency weighting.
7. Reads the previous session's `qg-session-history.md` entry (identified by a non-matching `session_uuid`) and injects any `status: session_ended_unresolved` Layer 3.5 events as highest-priority context. **Phase degradation:** Layer 3.5 is Phase 2; in Phase 1 there will be no recovery events in session history to inject. This step is a no-op in Phase 1.

**Phase degradation (items 1–6):** `qg-cross-session.json` does not exist until Layer 6 is implemented (Phase 3). In Phases 1–2, items 1–6 are skipped silently. Item 7 runs independently of `qg-cross-session.json` using `qg-session-history.md` (available from Phase 1). If `qg-session-history.md` does not yet exist (first-ever session), item 7 is also a no-op.

**Effectiveness tracking:** Layer 3 outcomes for sessions with vs without injection.

### Layer ENV — Environment Validation

**Hook:** SessionStart (fires after Layer 0)

**Purpose:** Validate the working environment against project expectations and capture a baseline for Layer 8 (regression detection).

**Behavior:**
1. Reads `qg-env.json` for project-specific expected state.
2. Validates: git branch, working directory, required tools present, required env vars set.
3. Severity routing: minor mismatches → warn-and-continue; critical mismatches → halt with explanation.
4. Stores validated baseline in session state (`layer_env_baseline{}`).
5. Captures test baseline: runs the configured test command (from `qg-env.json`) and records the set of currently-failing tests as `layer_env_test_baseline[]` in session state. If no test command is configured, this step is skipped.
6. Re-validates on mid-session environment changes via the Layer ENV PreToolUse hook, which checks each incoming tool's file path prefix against `layer_env_baseline.working_dir`. If a mismatch is detected, re-runs validation item 2.
7. Supports non-git projects via explicit skip rules in `qg-env.json`.
8. Passes environment context to Layer 1.9 so impact thresholds can be calibrated. **Phase degradation:** Layer 1.9 is Phase 2; in Phase 1 this pass is a no-op.

**Baseline preserved through:** Layer 4.5 context preservation.

### Layer 1 — Pre-task Enforcement

**Hook:** UserPromptSubmit (extended `precheck-hook.py`)

**Purpose:** Classify the incoming task, write measurable success criteria, and enforce scope confirmation before work begins.

**Integration with existing precheck-hook.py:** The existing hook uses a 4-category Ollama classifier (MECHANICAL / ASSUMPTION / OVERCONFIDENCE / PLANNING). Layer 1 extends this by:
- Keeping the existing 4-category classifier and its DIRECTIVES injection unchanged.
- Adding a DEEP category detected via heuristics on the same prompt (e.g., message length >300 chars + multiple numbered steps + scope indicators like "redesign", "migrate", "refactor all"). DEEP classification runs after the existing Ollama call; if detected, it overrides the existing category.
- Adding the checklist, success criteria, pivot detection, and scope confirmation behaviors described below.

**Behavior:**
1. Classifies task into one of: MECHANICAL, ASSUMPTION, OVERCONFIDENCE, PLANNING, DEEP (see integration note above).
2. Generates task-specific checklist per category and writes to session state. Infers task scope from the request (file paths mentioned, module names, directory references) and writes `layer1_scope_files[]` to session state — used by Layer 2 SCOPE_CREEP detection. For DEEP tasks, scope is confirmed explicitly via behavior 7 before tools fire.
3. Writes measurable success criteria to session state — verified by Layer 4 in each session summary entry (Layer 4 writes after every Stop evaluation).
4. Detects pivot: Jaccard similarity score (tokenized keyword overlap) between new request and `active_task_description` in session state. If similarity < 0.3, the new request is classified as a pivot (new topic unrelated to active task). No Ollama call required. If no active task exists (first request of session), pivot detection is skipped.
5. Re-fires on detected mid-session pivot; updates `active_task_id`. After pivot detection (whether or not a pivot was detected), writes the current request text to `active_task_description` in session state (replacing the previous value), so subsequent pivot checks have a current baseline.
6. Multi-task splitting: if request contains multiple subtasks detected via numbered list pattern or explicit conjunctions ("and also", "then", "additionally"), each gets individual criteria; active_subtask_id tracked.
7. DEEP tasks require explicit scope confirmation (additionalContext injection) before any tools fire.
8. Codebase state scan bounded to 3 seconds (fast grep-based, not full AST).
9. HIGH/CRITICAL impact tasks (from Layer 1.9) get stricter success criteria. **Phase degradation:** When Layer 1.9 is not yet implemented (Phase 1), this step is skipped; all tasks get standard criteria.
10. Checks for pending SCOPE_CREEP events in `layer2_unresolved_events[]`. If the current request contains explicit approval keywords ("proceed", "that's fine", "go ahead", "continue", "ok") and a SCOPE_CREEP event is open, clears the SCOPE_CREEP event status to `addressed`. Also cleared if `active_task_id` changes (pivot detected in behavior 5).
11. At the start of every UserPromptSubmit invocation, reads `layer3_pending_fn_alert` from session state. If present, injects it as the highest-priority additionalContext message (before the standard DIRECTIVES block), then clears the field. This is the FN delivery mechanism: Layer 3 (Stop hook) writes the alert to session state; Layer 1 delivers it on the next user turn.

### Layer 1.5 — PreToolUse Validation

**Hook:** PreToolUse

**Purpose:** Warn or block on rule-defined tool use violations before the tool executes.

**Behavior:**
0. At entry, flushes `notification_pending_criticals[]` from session state: injects any queued CRITICAL notifications as `additionalContext` before running layer-specific logic. This makes Layer 1.5 the delivery point for CRITICALs queued by Stop-time or async layers (3, 4, 9, 10) that had no PreToolUse context at the time they were issued.
1. Evaluates incoming tool call against rules in `qg-rules.json`. No code changes required to add/modify rules.
2. Actions: `warn` (inject advisory via additionalContext) or `block` (return decision: block).
3. Session-scope read tracking: tracks which files have been Read this session (not turn-scope).
4. Deduplication: same warning suppressed within a single turn.
5. Repeat violation: 3rd occurrence of same violation in session → Notification Router CRITICAL alert.
6. Override mechanism: After a Layer 1.5 block, if Claude's response text contains the pattern `Override [rule_name]: <justification>`, the Stop hook (Layer 3) detects this, writes a one-time override token to session state (`layer15_override_pending: {rule_id, justification, ts}`). On the next PreToolUse invocation of the same rule, Layer 1.5 checks for a matching pending override — if present, the block is skipped for that tool call only, the justification is logged to session state, and the override token is cleared.
7. Warning-ignored events (warning issued but next tool fires without addressing it) written to session state for Layer 3 classification.
8. HIGH/CRITICAL impact edits (from Layer 1.9) escalate rule `warn` actions to `block`. **Phase degradation:** When Layer 1.9 is not yet implemented (Phase 1), this escalation is skipped; all rules use their configured action (`warn` or `block`) without modification.

**Rules stored in `qg-rules.json`:** examples include "Edit without prior Read", "Bash grep/cat instead of Grep/Read tools", "Write to file outside task scope".

**Interaction with Layer 2 LAZINESS:** Layer 1.5 fires pre-tool (before the Edit executes). If Layer 1.5 issues a `warn` and Claude proceeds anyway without addressing it, Layer 2 will additionally fire a LAZINESS event post-tool on the same Edit. If Layer 1.5 issues a `block` and it is not overridden, the Edit never executes so Layer 2 never fires. Both signals are intentional and serve different purposes: Layer 1.5 prevents, Layer 2 records.

### Layer 1.7 — User Intent Verification

**Hook:** PreToolUse (fires once per task for PLANNING/DEEP tasks)

**Purpose:** Verify understanding of intent for complex tasks before work begins, reducing scope mismatches.

**Behavior:**
1. Complexity threshold: configurable in `qg-rules.json` (default: DEEP tasks + multi-step PLANNING tasks where subtask count ≥ 2).
2. Fires once per task only — verified intent stored in session state; no re-verification on same task_id.
3. Clarification injected via `additionalContext` (not visible as Claude's response text).
4. Inherently ambiguous requests: logged with explicit `uncertainty: true` marker in session state; work proceeds without blocking.
5. Intent mismatch data written to session state as a cross-session signal for Layer 6 to consume. **Phase degradation:** Layer 6 is Phase 3; this data is stored in Phase 2 but not consumed until Phase 3.
6. Verified intent preserved through Layer 4.5 compaction.

### Layer 1.8 — Hallucination Detection

**Hook:** PreToolUse

**Purpose:** Detect references to non-existent files, functions, or packages before they cause downstream failures.

**Behavior:**
1. **File path hallucinations:** Filesystem existence check before any tool operates on a path.
   - Exception: Write/Create tools skip existence check (file doesn't exist yet by design).
   - If Layer 1.7 confirmed scope includes creating new artifacts: suppresses false-positive for those artifact paths.
2. **Function/method references:** Grep codebase on first use of any named function/method referenced in tool arguments (e.g., a function name in a Read or Edit target path, or in a Bash command). Per-session deduplication: each function name checked once per session (cached in session state) to avoid repeated scans. Only function names extractable from tool inputs are checked — not Claude's reasoning text.
3. **Package references:** Check against language-specific installed packages list before use (`pip list` for Python, `npm list` for Node). Detection is limited to package names that appear literally in tool inputs (e.g., import statements in Write/Edit content).
4. **Logical hallucinations:** Not detectable pre-tool; delegated to Layer 3 Haiku analysis.
5. **Remote references (URLs, external APIs):** Warn but do not block.

### Layer 1.9 — Change Impact Analysis

**Hook:** PreToolUse on Edit/Write

**Purpose:** Assess the blast radius of proposed edits before they execute, so downstream layers can calibrate severity.

**Behavior:**
1. Static dependency analysis: grep for all imports/requires of the target file.
2. Impact levels:
   - LOW: <5 dependent files
   - MEDIUM: 5–20 dependent files
   - HIGH: >20 dependent files
   - CRITICAL: core/shared infrastructure files (configurable list in `qg-rules.json`)
3. Results stored in session state (`layer19_impact_cache{}`), consumed by Layers 1.5, 2, 2.7, 3, 8.
4. Per-session file cache: avoids repeated scans of the same file.
5. Dynamic import limitation: if dynamic imports are detected, impact level flagged as "may be understated."
6. Thresholds (5, 20) configurable in `qg-rules.json`.
7. For HIGH or CRITICAL impact edits: writes `layer8_regression_expected = true` to session state, signaling to Layer 3 that a regression check should be performed before the session ends. **Phase degradation:** Layer 8 is Phase 3; in Phase 2, this flag is set but never consumed (Layer 3 ignores it when Layer 8 is not deployed).

### Layer 2 — Mid-task Monitoring

**Hook:** PostToolUse

**Purpose:** Detect quality violations in real time as tools are called, before the final response is generated. Detection is limited to what is observable from tool inputs and outputs — not Claude's response text (which is only available to the Stop hook / Layer 3).

**Rate limiting:** Max 5 events per turn; excess events are aggregated into a summary event.
**Elevated scrutiny:** 3+ CRITICAL events in one turn → `layer2_elevated_scrutiny = true` in session state (read by Layer 3).

**Event categories:**

| Category | Severity | Detection Signal |
|---|---|---|
| LAZINESS | warning | Edit tool call with no prior Read tool call on the same file this session (exception: Write tool creating a new file — no prior Read expected) |
| ASSUMPTION | warning | Hardcoded path/value in tool input without prior Glob/Grep confirming it exists |
| INCORRECT_TOOL | info | Bash command contains grep/cat/find/head/tail instead of using dedicated tools |
| ERROR_IGNORED | critical | Tool response contains non-zero exit code or failure text, but next tool call fires anyway |
| INCOMPLETE_COVERAGE | critical | Tool call count falls below minimum expected from Layer 1 session state success criteria |
| LOOP_DETECTED | critical | Same tool+target combination called 3+ times; or 5+ calls to same directory with no progress (configurable) |
| OUTPUT_UNVALIDATED | warning | Edit tool call followed immediately by another Edit with no Read in between; or test Bash call with no check of exit code |
| SCOPE_CREEP | warning | File outside Layer 1 `layer1_scope_files[]` is written; cleared when Layer 1 detects explicit user approval in a subsequent prompt (keywords: "proceed", "that's fine", "go ahead") or when task_id changes |

**Resolution tracking:** Each event tracked as `open / addressed / ignored` in session state.
**Resolution detection:** A tool call that directly addresses a flagged issue marks it as `addressed`.
**Change magnitude from Layer 1.9** incorporated into severity calculation (HIGH/CRITICAL impact raises severity one level). **Phase degradation:** When Layer 1.9 is not yet implemented (Phase 1), severity is calculated without impact level adjustment.

All events written to `qg-monitor.jsonl` with fields: `event_id` (UUID), `ts`, `session_uuid`, `working_dir`, `task_id`, `category`, `severity`, `detection_signal`. (The `working_dir` field is required for Layer 6 project isolation.)

### Layer 2.5 — Output Validity

**Hook:** PostToolUse on Write/Edit

**Purpose:** Syntax-check written files immediately after they are written.

**Validators by extension:**
- `.py` → `ast.parse()`
- `.json` → `json.loads()`
- `.yaml` / `.yml` → `yaml.safe_load()`
- `.sh` → `bash -n`
- `.html` → `html.parser`
- Unknown extensions → skipped with INFO log

**Behavior:**
- Files >100KB skipped for performance.
- Failure: advisory warn (does not block). Writes a `layer25_syntax_failure` flag to session state; Layer 3 reads this flag to raise FN probability. Also sends Notification Router WARNING. (Cannot feed Layer 2 directly — both fire PostToolUse; Layer 2 fires before Layer 2.5 for the same tool call.)

### Layer 2.6 — Consistency Enforcement

**Hook:** PostToolUse on Write/Edit

**Purpose:** Detect inconsistencies in naming conventions, import style, and error handling patterns across files written in the session.

**Behavior:**
1. Convention baseline: established from the first 3 files written in the session.
2. Tracks: naming convention (snake_case vs camelCase), import style (relative vs absolute), error handling pattern (try/except vs if/return).
3. Implementation: lightweight regex-based (not AST) for speed.
4. Intentional convention changes: suppressed if Layer 1.7 verified scope includes refactoring.
5. Cross-turn, session-scoped tracking.

### Layer 2.7 — Testing Coverage Verification

**Hook:** PreToolUse on Edit for code files

**Purpose:** Flag when code being edited has no test coverage.

**Behavior:**
1. Coverage data sources (checked in order): `.coverage` file (Python/pytest-cov), `coverage.xml` (Cobertura/JaCoCo), `lcov.info` (JavaScript/jest). Fallback: grep for a test file matching `test_<filename>` or `<filename>.test.*`.
2. Default threshold: warn if edited function has 0% coverage. Configurable in `qg-rules.json`.
3. No coverage data available: logged as `coverage: unknown`, not a violation.
4. HIGH/CRITICAL Layer 1.9 changes: stricter threshold applied (configurable).

### Layer 3 — Post-response Classification

**Hook:** Stop (integrated into `quality-gate.py`)

**Purpose:** Classify each completed response as TP, FP, FN, or TN using rules + Haiku content analysis. This is the core classification layer.

**Confidence algorithm:**
```
1. Base score:
   gate_blocked → base = 0.70
   gate_passed  → base = 0.75

2. Adjustments (additive):
   [only when gate_blocked]:
     block_category in {MECHANICAL, OVERCONFIDENCE}  → +0.15
     block_category in {PLANNING}                    → -0.10
   [all responses]:
     L2_unresolved_events > 0  → -0.10 per event (cap: -0.30)
     L2_critical_events > 0    → -0.15 per critical (cap: -0.30)
     ignored_warnings_count > 0 → -0.08 per warning (cap: -0.20)
     elevated_scrutiny_flag     → -0.20
     gap_sec < 2 with no tools_after edit verification → -0.15
     tools_after contains Read/Grep after Edit → +0.10

3. Clamp result to [0.01, 0.99]
```

**Confidence levels:** certain (≥0.85), probable (0.60–0.84), uncertain (<0.60)

**Verdict assignment:**
```
gate_blocked:
  certainty ≥ 0.60 → TP (Failure Prevented)
  certainty < 0.60 → FP (False Block)

gate_passed:
  Haiku FN prompt returns positive signal → FN (Missed Failure)
    certainty adjusted by response-text detections (LAZINESS text, MEMORY_OVER_VERIFICATION)
  Haiku FN prompt returns no signal → TN (Compliant, No Block)
    TN quality grade: high / standard / low (see below)
```

**TN quality grades:** high (verification tools used + criteria met), standard (clean pass), low (trivially clean with no tools)

**Haiku FN detection prompt extension:**
> "Does this response make claims about outcomes without quoting tool output? Does it skip verification the task required? Does it reference files or functions that were not confirmed to exist? Does it claim completion without demonstrating completion criteria?"

**Response-text detection (Stop hook only — not available to PostToolUse):**
- **LAZINESS (text):** Response claims work is "done" or "complete" without citing any verification tool output → FN signal.
- **MEMORY_OVER_VERIFICATION:** Response makes the same factual claim (file exists, function behaves X way) as the previous turn, with no verification tool call between the two turns → FN signal. After each Stop evaluation, Layer 3 extracts key factual claims from the response text and writes them to `layer3_last_response_claims[]` in session state for comparison on the next turn.

These signals augment the Layer 2 tool-observable detections, which cannot read response text.

**Additional behaviors:**
- **FN delivery:** When verdict = FN, Layer 3 writes the formatted FN message (`[monitor] Missed Failure — <reason>`) to `layer3_pending_fn_alert` in session state. Layer 1 (UserPromptSubmit) delivers this as additionalContext on the next user turn and clears the field. FN delivery cannot happen in the same turn (Stop hook cannot inject into the current turn's prompt after it has already been generated; it only influences the *next* turn via UserPromptSubmit).
- **WARNING flush:** At the end of each Stop evaluation, Layer 3 flushes all queued WARNING notifications from the Notification Router as a batch, appended to the block message text (if blocked) or injected as `additionalContext` (if passed). Subject to the 3-CRITICAL-per-turn rate limit (WARNINGs are not rate-limited).
- Multi-turn task correlation via `task_id` in session state.
- Cross-turn visibility: Layer 3 sees unresolved Layer 2 events from last 3 turns.
- Output Validity failures (Layer 2.5) raise FN probability via the `layer25_syntax_failure` flag in session state. Layer 3 clears this flag at the end of each Stop evaluation so it does not carry over to the next turn. **Phase degradation:** Not available until Phase 3; skipped in Phases 1–2.
- Consistency Enforcement violations (Layer 2.6) raise FP probability (gate may be responding to a style issue it mistook for a logic issue). **Phase degradation:** Not available until Phase 3; skipped in Phases 1–2.
- Repeat FN same pattern: escalates severity + feeds Layer 7 as high-priority signal. **Phase degradation:** Layer 7 is Phase 3; in Phases 1–2 this signal is written to session state but not consumed until Phase 3 is deployed.
- **Layer 1.5 override detection:** If the response text contains `Override [rule_name]: <justification>` and a Layer 1.5 block was issued this turn, Layer 3 writes `layer15_override_pending: {rule_id, justification, ts}` to session state. Layer 1.5 consumes and clears this token on the next PreToolUse invocation matching the same rule.
- Subagent events integrated with `parent_task_id`.
- Layer 3 extracts stated certainty from response text using Layer 9's phrase list (defined in Layer 9 spec). The raw certainty label is stored in the event. Layer 9's periodic analysis uses this stored data — Layer 9 does not run per-response.

**Event written to `qg-monitor.jsonl`** with fields: `event_id` (UUID), `ts`, `working_dir`, `session_uuid`, `task_id`, `parent_task_id` (optional — present only for events from subagent sessions merged by Layer 5), `verdict` (TP/FP/FN/TN), `confidence`, `confidence_level`, `stated_certainty` (high/medium/low/none), `block_reason`, `block_category`, `L2_events[]`, `tools_before[]`, `tools_after[]`, `gap_sec`, `response_hash`.

### Layer 3.5 — Recovery Tracking

**Hook:** Integrated into Stop evaluation (cross-turn state)

**Purpose:** Track whether flagged failures are corrected in subsequent turns within the same session.

**Turn definition:** One "turn" = one Stop hook evaluation (i.e., one completed response). Recovery is tracked by counting Stop hook invocations since the event was logged.

**Behavior:**
1. Recovery window: 3 turns or 30 minutes from event, whichever comes first.
2. State persisted to session state after each Stop evaluation.
3. Resolution criteria: specific tool call or verification directly addressing the flagged issue in a subsequent turn.
4. Partial recovery: tracked as `status: partial`.
5. Recovery-introduces-new-problem: a new same-category event in the same scope after resolution is flagged separately.
6. Unresolved at session end: passed to Layer 0 for injection into next session.
7. Timed-out unresolved: logged with elevated severity in Layer 4 session summary.

### Layer 4 — Session End Summary

**Hook:** Stop (a complete rolling summary is written to `qg-session-history.md` after EVERY Stop evaluation, not only at session end)

**Purpose:** Summarize session quality with trends, root cause clustering, and actionable recommendations.

**Session end detection:** Claude Code has no session-end hook. Layer 4 does not need to detect session end — it produces a complete, current summary after every Stop evaluation. Layer 0 at next session start reads the last entry in `qg-session-history.md` that does not match the current `session_uuid` as the previous session's summary.

**Quality score formula:**
```
score = (FN×3 + L2_critical×2 + FP×1) / (session_evals × complexity_factor)

complexity_factor = mean(category_weight for each eval in session)
where category_weight: MECHANICAL=1.0, ASSUMPTION=1.0,
                       OVERCONFIDENCE=1.2, PLANNING=1.3, DEEP=1.5
```
Lower score is better. `complexity_factor` normalizes so DEEP-task sessions don't unfairly score worse than MECHANICAL ones.

**Summary contents:**
- `session_uuid` header — written at the start of each summary entry so Layer 0 can identify the previous session's entry
- Quality score + comparison to previous 5 sessions with direction indicator (improving / degrading / stable)
- TP/FP/FN/TN counts with confidence distribution
- Root cause clusters by `(category, file_directory, task_id)` — grouped by count, sorted descending; recommendation per cluster is a templated string from a small set of pre-defined recommendations keyed by category (not generated by LLM)
- Recovery rate: issued / resolved / timed-out. **Phase degradation:** Recovery data not available until Layer 3.5 (Phase 2); shown as "N/A" in Phase 1.
- Layer 1 success criteria: met / partially met / unmet
- Unresolved Layer 3.5 events passed to Layer 0 with `status: session_ended_unresolved`

**Storage:** Written to `qg-session-history.md`. Pruning: 30 sessions retained; older entries moved to `qg-session-archive.md`.

**Crash resilience:** Final summary assembled from incremental checkpoints; partial summaries are valid.

**Triggers:** Layer 7 notified via Notification Router when summary is ready with repeat FN patterns.

### Layer 4.5 — Context Preservation

**Hook:** PreCompact + PostCompact

**Purpose:** Ensure cross-layer state survives context compaction without loss.

**Preserved items:**
- Full session state (`qg-session-state.json`)
- Unresolved Layer 3.5 recovery events
- Active task context (task_id, success criteria, scope files)
- Layer ENV baseline
- Layer 1.5 session-scope read tracking
- Layer 2 unresolved events

**Discarded items:**
- Resolved events
- Completed turn history
- Cached analysis results (Layer 1.9 impact cache — rebuilt on demand)

**Configuration:** `qg-preservation-config.json` with explicit inclusion/exclusion list.

**Post-compact validation:** Hash check on key preserved files to verify state integrity.

**Continuation detection:** Compacted session identified by session_uuid match. On mismatch: the PostCompact hook re-injects critical preserved state (active task context, unresolved Layer 3.5 events, ENV baseline, success criteria, unresolved Layer 2 events) directly via `additionalContext` in its return value — not via a SessionStart hook trigger, which would not fire at this point.

### Layer 5 — Subagent Coordination

**Hooks:** PreToolUse on Agent tool calls (dispatch) + PostToolUse on Agent tool calls (merge)

**Purpose:** Propagate session state to subagents and merge their monitoring events back to the parent session.

**Mechanism:** Two hooks fire per Agent tool call:
- **PreToolUse (dispatch):** fires before the subagent starts. Writes the state handoff file so the subagent's SessionStart hook can read it. The `subagent_id` is derived from the Agent tool call's parameters (task description hash, or explicit id if provided).
- **PostToolUse (merge):** fires after the subagent completes. Reads subagent results and merges them into the parent session.

For parallel subagents launched in the same turn, each fires its own PreToolUse then PostToolUse independently.

**Behavior:**
1. **Dispatch (PreToolUse):** Serialize task-relevant subset of session state (filtered by `task_id` and file scope), write to `~/.claude/qg-subagent-<subagent_id>.json`. The subagent's SessionStart hook reads this file (detected via file existence at a known path) to initialize its own monitoring context.
2. **Merge (PostToolUse):** Merge subagent events (from `~/.claude/qg-subagent-<subagent_id>.json` written by the subagent) into parent session state under `session_state.subagents[subagent_id]`, tagging each event with `parent_task_id`, and write to `qg-monitor.jsonl`.
3. Coverage thresholds and impact levels inherited from parent session (written to handoff file at dispatch).
4. Failure handling: if subagent's result file is absent or incomplete, write `subagent_timeout` marker in session state; Layer 4 notified.
5. Cleanup: handoff file deleted after successful merge.

### Layer 6 — Cross-session Pattern Analysis

**Phase degradation:** Layer 6 is Phase 3. In Phases 1–2, Layer 4 checks for the existence of the Layer 6 module before triggering it; if not present, the trigger is a no-op.

**Trigger:** Automatic at Layer 4 write (every Stop evaluation, since Layer 4 now writes after every Stop) + `qg analyze` command. Layer 6 is lightweight — it only reruns if `qg-monitor.jsonl` has grown since the last run (tracked by line count stored in `qg-cross-session.json`).

**Purpose:** Identify recurring failure patterns across sessions and produce structured output for Layer 0 injection.

**Pattern threshold:** A pattern qualifies if it appears in ≥3 of the last 10 sessions AND constitutes ≥15% of session events.

**Pattern retirement:** A qualified pattern is retired if absent from 3 consecutive sessions.

**Execution order:** When triggered by Layer 4, Layer 9 runs first (to update `qg-calibration.jsonl` with new responses), then Layer 6 runs (so it reads fresh calibration data in item 3 below).

**Behavior:**
1. Reads `qg-monitor.jsonl` filtered by `working_dir` field matching current working directory prefix (project isolation).
2. Clusters by `(category, file_directory, block_category)`.
3. Analyzes Layer 9 confidence calibration data (`qg-calibration.jsonl`) for model drift signals.
4. Writes structured output to `qg-cross-session.json` (consumed by Layer 0).
5. Statistical threshold configurable in `qg-rules.json`.

### Layer 7 — Feedback and Rule Refinement

**Phase degradation:** Layer 7 is Phase 3. In Phases 1–2, the Layer 4 notification trigger for Layer 7 is a no-op if the Layer 7 module is not present.

**Trigger:** Layer 3 repeat FN patterns + Layer 6 analysis output + `qg rules` command

**Purpose:** Propose concrete rule changes to `qg-rules.json` based on observed failure patterns.

**Behavior:**
1. Each suggestion: replay proposed rule against last 10 sessions to compute simulation result.
2. Suggestion format: rule text + simulation result (N events affected, estimated FN reduction) + supporting event data + plain-language "why" explanation.
3. Suggestions written to `qg-rule-suggestions.md` with status: `pending / applied / rejected`.
4. Notification: Notification Router WARNING alert + `qg-rule-suggestions.md` entry.
5. Approval UX: `qg rules apply N` / `qg rules reject N "reason"`.
6. Rule versioning: each rule in `qg-rules.json` carries `created_at`, `modified_at`, `version`, `last_simulation_result`.
7. Rollback: `qg-rules.json` versioned with timestamp history; prior version restorable.

### Layer 8 — Regression Detection

**Hook:** PostToolUse on Bash tool calls where the command matches a test pattern (e.g., contains `pytest`, `npm test`, `jest`, `go test`, `make test`)

**Purpose:** Detect new test failures introduced during the session.

**Behavior:**
1. Baseline: `layer_env_test_baseline[]` captured by Layer ENV at session start. If not present (no test command configured), Layer 8 exits silently.
2. Already-failing tests (present in baseline) excluded from delta — only newly-failing tests are counted.
3. Scope: compares against before-this-session baseline only.
4. HIGH/CRITICAL Layer 1.9 changes set `layer8_regression_expected = true` in session state (written by Layer 1.9). Layer 3 checks for this flag and raises FN probability if no regression check ran before the Stop hook fires. **Phase degradation:** Layer 8 is Phase 3; in Phase 2 (Layer 1.9 exists but Layer 8 does not), the flag is set by Layer 1.9 but never cleared. Layer 3 should only check this flag if Layer 8 is deployed — in Phase 2, Layer 3 ignores `layer8_regression_expected`.
5. When a test Bash command completes (Layer 8 fires PostToolUse), Layer 8 clears `layer8_regression_expected = false` in session state, indicating the regression check has been performed.
6. Test runner auto-detected from project config (`package.json`, `pytest.ini`, `Makefile`, `go.mod`, etc.) and stored in session state (`layer_env_baseline.test_command`). Not written to `qg-env.json` (that file is user-managed).
7. Non-test code changes in sessions with no test config: flagged in Layer 4 summary as "no regression detection available."

### Layer 9 — Confidence Calibration

**Phase degradation:** Layer 9 is Phase 3. In Phases 1–2, the Layer 4 trigger for Layer 9 is a no-op if the Layer 9 module is not present. Layer 3's `stated_certainty` field is written regardless — this data is stored now so Layer 9 can analyze it retroactively when Phase 3 is deployed.

**Trigger:** Via Layer 4 trigger (after each Stop evaluation) if ≥5 new responses have been classified since the last calibration run; also runs on demand via `qg analyze`. Configurable minimum threshold in `qg-rules.json` (default: 5).

**Purpose:** Track whether Claude's stated certainty correlates with actual accuracy.

**Stated certainty signals extracted from response text:**
- High: "I'm certain", "definitely", "I know", "this will work", "confirmed"
- Medium: "I believe", "should", "likely", "expect"
- Low: "might", "possibly", "I think", "probably"

**Ground truth:** Layer 3 classification outcome for the same response.

**Storage:** `qg-calibration.jsonl` tagged with `model_id` and `task_complexity`.

**Per-complexity normalization:** trivial / moderate / deep tracked separately to avoid conflating easy and hard tasks. Mapping from Layer 1 categories: MECHANICAL → trivial, ASSUMPTION → trivial, OVERCONFIDENCE → moderate, PLANNING → moderate, DEEP → deep.

**Staleness:** After 30 sessions without a calibration refresh, sends a Notification Router WARNING to prompt the user to run `qg analyze`.

**Layer 0 action:** If systematic overconfidence detected (high stated certainty + FN outcome ≥30% of responses in last 5 sessions), write a `calibration_reminder: true` flag to `qg-cross-session.json`. Layer 0 reads this at next session start and injects a calibration reminder into `additionalContext`.

**Cross-model comparison:** `model_id` tag enables comparison across model versions.

### Layer 10 — Audit Trail Integrity

**Trigger:** `qg monitor` invocation + if last integrity check timestamp in session state is >7 days ago (checked at Layer 4 write time)

**Purpose:** Detect and quarantine corrupt or inconsistent audit log entries.

**Checks:**
- All `qg-monitor.jsonl` lines parseable as valid JSON
- Session IDs consistent within a session's entries
- No duplicate `event_id` values (UUID field required for all events written to `qg-monitor.jsonl`)
- Timestamps monotonically increasing within each session
- File sizes within configured bounds

**Behavior:**
1. Corrupt lines: moved to `qg-quarantine.jsonl` with quarantine reason.
2. Alert: Notification Router CRITICAL on any integrity failure.
3. Rotation: `qg-monitor.jsonl` rotated at 10,000 lines → `qg-monitor-YYYY-MM.jsonl`.
4. `qg integrity` command: displays quarantine report with corrupt line counts and reasons.
5. After completing an integrity run, updates `last_integrity_check_ts` in session state to the current timestamp (used by Layer 4 to determine whether the 7-day interval has elapsed).

---

## 8. Implementation Phases

### Phase 1 — Functional Backbone
**Layers:** 0, ENV, 1, 1.5, 2, 3, 4 + Session State + Notification Router + Dashboard (`qg monitor` command)

This phase delivers the complete classify-detect-prevent lifecycle. After Phase 1, every session produces confusion matrix classifications, mid-task monitoring alerts, pre-task enforcement, and session summaries with quality scores.

### Phase 2 — Correctness and Recovery
**Layers:** 1.7, 1.8, 1.9, 3.5, 4.5, 5

This phase adds accuracy to Phase 1's skeleton: intent verification reduces scope mismatches, hallucination detection prevents phantom references, impact analysis calibrates severity, recovery tracking closes the loop on failures, context preservation survives compaction, and subagent coordination extends coverage to agent-dispatched work.

### Phase 3 — Self-Improvement and Intelligence
**Layers:** 2.5, 2.6, 2.7, 6, 7, 8, 9, 10

This phase adds the learning and integrity systems: syntax validation, consistency enforcement, coverage verification, cross-session pattern analysis, automated rule suggestions, regression detection, confidence calibration, and audit integrity.

---

## 9. Existing Infrastructure Integration

| Component | Action |
|---|---|
| `quality-gate.py` | Extended in-place for Layer 3 classification and Layer 4 checkpointing. Not replaced. |
| `precheck-hook.py` | Extended in-place for Layer 1 pre-task enforcement. Not replaced. |
| `validate-bash` | Unchanged. Complementary to Layer 1.5. |
| `block-secrets` | Unchanged. |
| `qg-feedback.py` | Extended with `qg monitor`, `qg analyze`, `qg integrity`, `qg rules` subcommands. |
| `quality-gate-feedback.jsonl` | Still used for confirmed fp/tp/miss labels. |
| `quality-gate-overrides.jsonl` | Still used as FP proxy signal. |
| `quality-gate.log` | Still the primary event log. |
| `qg-shadow-trend.log` | Unchanged. |

All new hooks (PostToolUse, PreToolUse for new layers, SessionStart layers) are added as new hook entries in `settings.json`. No existing hook entries are modified.

---

## 10. Configuration Reference (`qg-rules.json`)

All tunable parameters live in `qg-rules.json`. No code changes required to adjust behavior.

**Key configurable values:**
- Layer 0: injection context window cap (default: 2000 chars), pattern retirement threshold (default: 5 sessions)
- Layer 1: DEEP detection heuristics (message length threshold, scope indicator keywords), codebase scan time limit (default: 3s)
- Layer 1.5: rule definitions (warn vs block, category, condition), repeat violation threshold (default: 3)
- Layer 1.7: subtask count threshold for PLANNING tasks (default: 2)
- Layer 1.9: LOW/MEDIUM/HIGH thresholds (default: 5, 20); CRITICAL file list
- Layer 2: LOOP_DETECTED thresholds (default: 3 same tool+target, 5 same dir no progress); rate limit (default: 5/turn)
- Layer 2.7: coverage warn threshold (default: 0%); HIGH/CRITICAL stricter threshold
- Layer 4: session retention count (default: 30); quality score weights (default: FN×3, L2_critical×2, FP×1); category complexity weights
- Layer 6: pattern threshold (default: ≥3/10 sessions, ≥15%); retirement (default: 3 consecutive absent)
- Layer 8: test command, test runner timeout
- Layer 9: calibration staleness threshold (default: 30 sessions); minimum new responses before recalibration (default: 5)
- Layer 10: rotation threshold (default: 10,000 lines); integrity check interval (default: 7 days)

---

## 11. Testing Strategy

- **Smoke tests:** All new Python modules added to existing `~/.claude/scripts/qg-regression.py` battery.
- **Layer 3 extension:** New TP/FP/FN/TN classification examples added to `FEW_SHOT_EXAMPLES` in `_hooks_shared.py`.
- **Session state:** Unit tests for schema migration, staleness detection, and locking.
- **Notification Router:** Unit tests for deduplication, rate limiting, and delivery channel routing.
- **Layer 1:** Unit tests for DEEP heuristic classification (edge cases around message length and keyword detection) and Jaccard pivot detection (known similar/dissimilar prompt pairs).
- **Layer ENV:** Unit tests for each validation type (git branch mismatch, missing required tool, bad working dir).
- **Layer 2 detection:** Regression examples for each of the 8 event categories.
- **Layer 6 patterns:** Synthetic session history used to verify threshold logic.
- **Integration:** End-to-end session replay from `qg-monitor.jsonl` to verify Layer 4 summary assembly.

---

## 12. Open Questions (deferred to implementation)

1. **Haiku FN prompt validation:** Layer 3 extends the existing Haiku Stop hook call. Validate that the extended FN detection prompt (Section 7, Layer 3) produces accurate TP/FP/FN/TN verdicts against the existing 80-example test battery before deploying.
2. **Layer 0 injection format:** Determine whether cross-session patterns are injected as structured JSON in `additionalContext` or as natural language prose. Prose is more readable; JSON is more parseable by hooks.
3. **`qg-rules.json` initial rule set:** Define the v1 rule set for Layer 1.5 based on the most common MECHANICAL/ASSUMPTION violations observed in `quality-gate.log`.
4. **Layer ENV project config format:** Finalize `qg-env.json` schema to support both git and non-git projects cleanly.
5. **Layer 4 async trigger mechanism:** The architecture marks Layers 6, 7, 9, 10 as triggered "async" by Layer 4 after each Stop evaluation. Define the concrete mechanism: Python `subprocess.Popen` (no wait) is the likely approach, allowing Stop hook to return immediately. Confirm this does not cause file-lock conflicts on `qg-session-state.json` or `qg-monitor.jsonl` when the Stop hook and async processes access them concurrently.

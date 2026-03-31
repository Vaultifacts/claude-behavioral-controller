# Future Layers — Gaps the Current System Cannot Address
Created: 2026-03-31
Purpose: Catalog capabilities that no existing layer provides, even at 10/10. These are the missing pieces of the puzzle.

---

## How This Document Works

Each proposed layer describes:
- **The gap**: What can go wrong today that nothing catches
- **When it fires**: Which hook event
- **What it does**: Core behaviors
- **Value**: How much it would improve the system (CRITICAL / HIGH / MEDIUM / LOW)
- **Complexity**: How hard it is to build (HIGH / MEDIUM / LOW)
- **Dependencies**: What existing layers it needs or feeds
- **What 10/10 looks like**: The adversarial standard

Layers are numbered to fit the existing scheme (gaps between current numbers are intentional).

---

## Phase 4 — Correctness Deepening

### Layer 2.8 — Security Vulnerability Detection
**The gap:** Claude can write code with SQL injection, XSS, command injection, path traversal, hardcoded secrets, or insecure crypto — and nothing catches it. Layer 2.5 checks syntax, not security. Layer 1.8 checks hallucinations, not vulnerabilities.

**When it fires:** PostToolUse on Write/Edit (code files only)
**What it does:**
- Runs lightweight regex/AST pattern matching against OWASP Top 10 categories
- Detects: unsanitized user input in SQL/shell/HTML, hardcoded credentials, eval/exec on untrusted input, insecure deserialization, path traversal patterns, weak crypto (MD5/SHA1 for security), missing CSRF tokens, open redirects
- Severity: CRITICAL for injection/credential issues, WARNING for weaker patterns
- Feeds Layer 2 as a new category: `SECURITY_VULNERABILITY`
- Does NOT require external tools — pure static analysis via regex + Python AST

**Value:** CRITICAL — security vulnerabilities are the highest-consequence failure mode
**Complexity:** MEDIUM — pattern libraries exist (Semgrep rules, Bandit patterns); core is regex + AST visitors
**Dependencies:** Layer 2.5 (shares PostToolUse Write/Edit slot), Layer 1.9 (impact level for severity weighting)
**What 10/10 looks like:** Catches all OWASP Top 10 patterns with <5% false positive rate on real session data. Adversarial test: deliberately write vulnerable code in 20 categories and verify all are caught.

---

### Layer 2.9 — Semantic Correctness Verification
**The gap:** Claude can write code that parses, passes syntax checks, and looks correct — but doesn't actually do what was asked. Example: user asks to "sort descending" and Claude writes ascending sort. Layer 2.5 catches broken syntax. Nothing catches broken semantics.

**When it fires:** PostToolUse on Write/Edit + Stop (two phases)
**What it does:**
- Phase 1 (PostToolUse): Lightweight checks — function name matches described behavior, return type matches docstring, test assertions match expected direction
- Phase 2 (Stop): If task had success criteria (from Layer 1), compares response claims against what tools actually did. E.g., "I added error handling" → did any try/except or catch block actually appear in the edits?
- Detects: off-by-one in criteria (asked for 5, wrote 4), inverted logic, missing edge case handling when explicitly requested, wrong variable/column used

**Value:** HIGH — this is the gap between "code works" and "code does what you asked"
**Complexity:** HIGH — requires understanding intent, not just syntax. May need LLM assist for complex cases.
**Dependencies:** Layer 1 (success criteria), Layer 3 (feeds FN classification with semantic signals)
**What 10/10 looks like:** On a labeled dataset of 50 correct and 50 semantically-wrong-but-syntactically-valid responses, catches >80% of semantic failures with <10% false positives.

---

### Layer 11 — Commit Quality Gate
**The gap:** Claude can commit with wrong message format, include unintended files (`.env`, `node_modules`), commit broken code, or commit changes that don't match what was described. Nothing validates commits before they happen.

**When it fires:** PreToolUse on Bash (when command contains `git commit` or `git push`)
**What it does:**
- Validates commit message against conventional commit format
- Checks `git diff --cached` for: accidental secret inclusion, binary files, files >1MB, unrelated changes
- Verifies staged files match the task scope (from Layer 1)
- Checks that tests were run since last edit (from Layer 8 state)
- For `git push`: verifies branch name, remote, and that local is ahead of remote
- Can block with `decision: block` if critical issues found

**Value:** HIGH — commits are hard to undo once pushed; preventing bad commits is high-leverage
**Complexity:** LOW — mostly git commands + regex
**Dependencies:** Layer 1 (scope), Layer 8 (test state), Layer ENV (git branch validation)
**What 10/10 looks like:** No commit ever includes secrets, no push ever goes to wrong branch, commit messages always match conventional format. Tested with adversarial commit attempts.

---

## Phase 5 — Intelligence & Adaptation

### Layer 12 — User Satisfaction Tracking
**The gap:** The system measures its own behavior (TP/FP/FN/TN) but never measures whether the user is actually satisfied. A response can pass all quality checks and still be unhelpful, too verbose, or off-target. No layer tracks user sentiment.

**When it fires:** UserPromptSubmit (analyzes the user's NEW message as a signal about the PREVIOUS response)
**What it does:**
- Detects frustration signals: "no", "wrong", "that's not what I asked", "try again", "undo", repeated same request, "I said...", "you forgot..."
- Detects satisfaction signals: "thanks", "perfect", "great", moving on to next task
- Detects confusion signals: "what?", "I don't understand", "explain", rephrasing the same question
- Records satisfaction score per response, correlated with Layer 3 classification
- Feeds Layer 7: if user is consistently frustrated by a pattern, that's a rule refinement signal stronger than any FN detection

**Value:** HIGH — user satisfaction is the ultimate ground truth; all other metrics are proxies
**Complexity:** MEDIUM — sentiment detection is well-understood; the hard part is accurate signal extraction from terse messages
**Dependencies:** Layer 7 (feeds rule refinement), Layer 9 (improves calibration with ground truth)
**What 10/10 looks like:** On 100 labeled user messages, correctly classifies satisfaction/frustration/confusion >85% of the time. False satisfaction rate (user frustrated but classified as satisfied) <5%.

---

### Layer 13 — Knowledge Freshness Verification
**The gap:** Claude can reference outdated API syntax, deprecated functions, or removed features from its training data. Nothing verifies that the code Claude writes uses current library APIs. Layer 1.8 checks if functions exist in the file — not if they exist in the current version of a library.

**When it fires:** PreToolUse on Write/Edit (when code contains import statements for external packages)
**What it does:**
- Extracts imported package names and versions from the project's lock file (package-lock.json, Pipfile.lock, poetry.lock)
- For commonly-hallucinated APIs (detected via a maintained list), verifies against installed package's actual exports (`dir()` in Python, type definition files in TypeScript)
- Warns when Claude references a function/method that doesn't exist in the installed version
- Maintains a per-project cache of verified API surfaces

**Value:** MEDIUM — hallucinated APIs are a known Claude weakness but not the most common failure mode
**Complexity:** HIGH — requires parsing lock files, introspecting installed packages, maintaining API surface caches
**Dependencies:** Layer 1.8 (extends hallucination detection to external APIs), Layer ENV (package availability)
**What 10/10 looks like:** For the top 20 most-used packages in each project, 100% of API hallucinations are caught before they're written to files.

---

### Layer 14 — Response Efficiency Analysis
**The gap:** Claude can solve a task correctly but wastefully — using 15 tool calls when 3 would suffice, reading the same file 5 times, creating unnecessary abstractions, or writing 200 words when 20 would do. Nothing measures efficiency.

**When it fires:** Stop
**What it does:**
- Counts total tool calls this turn, compares to complexity class (TRIVIAL should be <5, MODERATE <15, etc.)
- Detects redundant reads: same file read multiple times without edits in between
- Detects unnecessary tool calls: Glob then Grep then Read when Grep alone would suffice
- Measures response length vs. task complexity — flags verbose responses on simple tasks
- Tracks efficiency trends across sessions (are we getting better or worse?)
- Does NOT block — purely advisory. Feeds Layer 7 as optimization signal.

**Value:** MEDIUM — efficiency matters for cost and user experience but isn't a correctness issue
**Complexity:** LOW — mostly counting and comparing against thresholds
**Dependencies:** Precheck (complexity classification), Layer 2 (tool call history)
**What 10/10 looks like:** Redundant reads reduced to <5% of total reads. Average tool calls per task within 1 standard deviation of optimal for each complexity class.

---

### Layer 15 — Memory & State Integrity
**The gap:** Claude has memory files (`MEMORY.md`, project-specific memories) that can become stale, contradictory, or wrong. If a memory file says "project uses React" but the project switched to Vue, Claude will operate on false assumptions. Nothing validates memory accuracy.

**When it fires:** SessionStart + PostToolUse on Write (for memory file writes)
**What it does:**
- At SessionStart: for each memory file referenced by MEMORY.md, checks if the claims are still verifiable (e.g., "project uses React" → does package.json contain react?)
- On memory file writes: validates that new memories don't contradict existing ones
- Flags stale memories: memories older than N days that haven't been re-verified
- Detects circular references and duplicate entries across memory files
- Outputs staleness report as context injection

**Value:** MEDIUM — stale memories lead to incorrect assumptions, but memory files are manually curated and relatively stable
**Complexity:** MEDIUM — parsing memory files is straightforward; verifying claims against code requires heuristics
**Dependencies:** Layer 0 (context injection), Layer ENV (project validation)
**What 10/10 looks like:** Every factual claim in memory files is re-verified monthly. No contradictions exist between memory files. Stale entries are flagged within 1 session of becoming stale.

---

### Layer 16 — Rollback & Undo Capability
**The gap:** When Claude makes a mistake (wrong edit, bad commit, broken file), the only recovery is manual fixing. No layer can automatically revert a change or propose a rollback. Layer 3.5 tracks recovery but doesn't perform it.

**When it fires:** PostToolUse on Edit/Write (records snapshots) + triggered by Layer 3 block or user "undo"
**What it does:**
- Records file state before every Edit/Write (lightweight diff snapshots, not full copies)
- On Layer 3 block: presents "rollback last N edits" option
- On user "undo" keyword: reverts the last edit to the affected file
- For git commits: `git revert HEAD` with proper message
- Snapshot retention: last 20 edits per session, pruned at session end
- Never auto-rolls-back — always proposes and waits for confirmation (or block triggers it)

**Value:** HIGH — fast recovery from mistakes saves significant user time
**Complexity:** MEDIUM — diff snapshots are straightforward; the UX of presenting rollback options is the hard part
**Dependencies:** Layer 3 (block triggers), Layer 4.5 (snapshot preservation through compaction)
**What 10/10 looks like:** Any edit from the last 20 can be perfectly reverted in under 2 seconds. No data loss from rollback. User can undo to any point in the session.

---

## Phase 6 — Self-Improvement

### Layer 17 — Adversarial Self-Testing
**The gap:** The system only catches problems it's been programmed to recognize. No layer proactively tries to find its own blind spots. The shadow analysis (Haiku vs. Ollama) is the closest thing, but it only runs on past data.

**When it fires:** Periodic (once per day or on `qg self-test` command)
**What it does:**
- Generates adversarial test prompts designed to trigger each detection category
- Runs them through the full hook pipeline in a sandbox
- Verifies each detection fires correctly
- Reports categories where detection failed (new blind spots)
- Generates new smoke test cases for any discovered gaps
- Tracks blind spot trends over time

**Value:** CRITICAL — this is how the system evolves beyond its original design
**Complexity:** HIGH — generating meaningful adversarial inputs and sandboxing the pipeline are both hard
**Dependencies:** All layers (tests every layer), smoke-test.sh (outputs new test cases)
**What 10/10 looks like:** Monthly adversarial sweeps find 0 regressions. Every new detection rule added in the past 30 days has been adversarially validated. Blind spot rate trending toward 0.

---

### Layer 18 — A/B Rule Testing
**The gap:** Layer 7 suggests rule changes, but there's no way to test whether a proposed rule is actually better than the current one without deploying it and waiting to see. No controlled comparison exists.

**When it fires:** On `qg rules test N` command
**What it does:**
- Takes a proposed rule from Layer 7 suggestions
- Replays last 30 sessions' transcripts through both current and proposed rule
- Compares: block rate, FP rate, FN rate, user satisfaction correlation
- Reports which rule performs better with statistical significance
- Can shadow-run a proposed rule for N sessions before full deployment

**Value:** MEDIUM — prevents bad rules from being deployed; enables data-driven rule evolution
**Complexity:** HIGH — session replay is complex; statistical comparison requires sufficient sample size
**Dependencies:** Layer 7 (rule suggestions), Layer 12 (user satisfaction data for correlation)
**What 10/10 looks like:** No rule change is deployed without A/B test showing improvement at p<0.05. Rule changes that would increase FP rate are caught before deployment 100% of the time.

---

### Layer 19 — Cross-Project Learning
**The gap:** Each project is monitored independently. If Claude makes the same mistake in Project A and Project B, no layer recognizes the pattern as a Claude-level weakness rather than a project-level one.

**When it fires:** SessionStart + periodic analysis
**What it does:**
- Aggregates patterns from Layer 6 across ALL projects (not just current working directory)
- Identifies Claude-level weaknesses: "Claude consistently ignores TypeErrors" vs "this project has unusual error patterns"
- Generates global rules that apply everywhere vs project-specific rules
- Tracks which projects benefit most from monitoring (prioritization signal)
- Identifies project-specific calibration needs (Claude behaves differently in Python vs TypeScript)

**Value:** MEDIUM — cross-project learning accelerates improvement but requires enough project diversity to be meaningful
**Complexity:** MEDIUM — extends Layer 6's analysis with project-aware grouping
**Dependencies:** Layer 6 (cross-session patterns), Layer 0 (global injection)
**What 10/10 looks like:** Global patterns detected within 3 sessions of appearing in a second project. Project-specific false rules (that would hurt other projects) never promoted to global.

---

### Layer 20 — System Health Dashboard
**The gap:** The scorecard we just built is a point-in-time snapshot. No layer continuously monitors the health of the monitoring system itself — are hooks timing out? Is the state file growing unbounded? Are any layers silently failing?

**When it fires:** SessionStart + `qg health` command
**What it does:**
- Checks all hook files exist and are syntactically valid
- Checks settings.json hook registrations match actual files
- Measures hook execution time (from stop-log timestamps)
- Checks state file size and age
- Checks monitor log growth rate (abnormal = possible stuck loop)
- Checks quarantine log for new entries
- Reports per-layer health: firing (yes/no), error rate, latency
- Auto-updates the scorecard's live effectiveness scores

**Value:** HIGH — a monitoring system that can fail silently is worse than no monitoring (false confidence)
**Complexity:** LOW — mostly file existence checks and timestamp math
**Dependencies:** Layer 10 (audit trail), all layers (checks their health)
**What 10/10 looks like:** Any layer failure is detected within 1 session. Hook timeout is alerted within 5 seconds. State file corruption is detected before it causes downstream issues.

---

## Summary: Priority Matrix

| Layer | Name | Value | Complexity | Priority |
|-------|------|-------|------------|----------|
| **2.8** | Security Vulnerability Detection | CRITICAL | MEDIUM | **1** |
| **20** | System Health Dashboard | HIGH | LOW | **2** |
| **11** | Commit Quality Gate | HIGH | LOW | **3** |
| **16** | Rollback & Undo | HIGH | MEDIUM | **4** |
| **12** | User Satisfaction Tracking | HIGH | MEDIUM | **5** |
| **17** | Adversarial Self-Testing | CRITICAL | HIGH | **6** |
| **2.9** | Semantic Correctness | HIGH | HIGH | **7** |
| **14** | Response Efficiency | MEDIUM | LOW | **8** |
| **15** | Memory & State Integrity | MEDIUM | MEDIUM | **9** |
| **19** | Cross-Project Learning | MEDIUM | MEDIUM | **10** |
| **18** | A/B Rule Testing | MEDIUM | HIGH | **11** |
| **13** | Knowledge Freshness | MEDIUM | HIGH | **12** |

**Recommended build order:** 2.8 → 20 → 11 → 16 → 12 → 17 (covers CRITICAL + all HIGH/LOW combos first)

---

## What These Would Add to the Puzzle

Current system answers: *"Did Claude follow the rules?"*

Missing pieces answer:
- **2.8**: *"Did Claude write safe code?"*
- **2.9**: *"Did Claude write correct code?"*
- **11**: *"Did Claude commit properly?"*
- **12**: *"Was the user actually happy?"*
- **13**: *"Is Claude using current knowledge?"*
- **14**: *"Was Claude efficient?"*
- **15**: *"Are Claude's memories accurate?"*
- **16**: *"Can we undo mistakes quickly?"*
- **17**: *"Can the system find its own blind spots?"*
- **18**: *"Can we prove a rule change is actually better?"*
- **19**: *"Does the system learn across all projects?"*
- **20**: *"Is the monitoring system itself healthy?"*

When all 32 layers (20 current + 12 proposed) are at 10/10, the system answers: *"Did Claude do the right thing, safely, efficiently, with the user's satisfaction confirmed, and can we prove it?"*

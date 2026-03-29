IMPORTANT: This project is architecture-complete for the single-model bot. Phase 1 of the ensemble layer is now being planned as an add-on, not a redesign.

---

# CURRENT TASK: Claude+GPT Integration Test

## Status
- OPENAI_API_KEY: confirmed set (164 chars)
- Sample app: /d/Temp/ensemble-test-sample (node server.js, port 3847)
- All ensemble files: syntax-validated, lifecycle working

## Steps
1. Run: `unset CLAUDECODE && bash ensemble-test-bot /d/Temp/ensemble-test-sample --models=claude,gpt --timeout=5m`
2. Inspect these 5 artifacts from the gpt/ session dir:
   - gpt/test-intents.json       — did GPT generate valid schema-compliant intents?
   - gpt/execution-results.json  — did intent-executor.js run them cleanly?
   - gpt/raw-report.md           — did GPT produce a normalizable bug report?
   - gpt/normalized.json         — did normalizer extract real findings?
   - merged.json                 — did Claude+GPT findings merge correctly?
3. Report what succeeded, what failed, and classify any failure as:
   - prompt/schema issue (fix gpt-system.md)
   - executor issue (fix intent-executor.js)
   - normalization issue (fix normalizer.js)
   - provider/API issue (fix runner-base.sh)
4. Make only targeted fixes based on real output — no speculative changes.

## No code changes until after first run.

---

# Phase 1 Implementation Plan — Multi-Model Ensemble QA System

**Revision 2** — Revised to address the independence problem. GPT/Codex now contribute independent test intents that are executed by the local harness, not just post-hoc analysis of Claude-collected evidence.

---

## Context

The Autonomous App Testing Bot (v2.0) is a stable, production-ready single-model testing agent. This plan adds an **ensemble orchestration layer** that runs multiple AI models (Claude, GPT, Codex) against the same target app independently, normalizes their reports, deduplicates findings, and produces one merged bug report with confidence scoring.

**Core principle:** The existing bot is untouched. The ensemble layer wraps it.

**Phase 1 scope:** Sequential execution, rule-based normalization, provider abstraction, partial failure tolerance, one merged markdown + JSON output.

**Independence model:** Each model independently decides *what* to test. Claude has full live execution. GPT/Codex independently generate test intents (routes, forms, endpoints, checks) based on app metadata, and the orchestrator executes those intents through existing scripts. This preserves meaningful model diversity at the planning layer.

---

## The Independence Problem (and Solution)

### Problem (identified in review)

The original plan had a single evidence-collection pass before model runs. GPT/Codex only analyzed Claude-shaped evidence. This made the ensemble a "one tester + two reviewers" system, not three independent testers.

### Solution: Test-Intent Architecture

Each model independently sees the same raw app metadata (package.json, README, route files, source code structure) and independently produces a **test intent list** — a structured set of what they want tested. The orchestrator then executes each model's intents through the existing scripts, producing model-specific evidence. Each model then analyzes its own evidence and produces its own bug report.

```
App metadata (read-only) ──┬──→ Claude: full autonomous session (unchanged)
                           ├──→ GPT:    generates test intents → orchestrator executes → GPT analyzes results
                           └──→ Codex:  generates test intents → orchestrator executes → Codex analyzes results
```

**Why this is meaningfully different:**
- GPT might request testing `/admin/settings` that Claude never visited
- Codex might request probing `/api/users` with 15 different malformed payloads that Claude only tried 3 of
- Each model's route discovery, form selection, and endpoint probing is shaped by its own reasoning
- The execution surface is bounded (existing scripts), but the test *planning* is independent

---

## Hard Requirements (locked before implementation)

These are non-negotiable constraints. Every file must respect them.

### HR-1: Intent Schema Must Remain Narrow and Deterministic
- Fixed allowed intent types only: `visit_routes`, `test_forms`, `probe_endpoints`, `check_a11y`, `check_security_headers`, `custom_curl`
- No arbitrary shell commands. No free-form execution primitives.
- No intent type may spawn processes, write files, or execute outside the HTTP/browser domain.
- Schema is versioned from day one: `"schemaVersion": "1"` in every `test-intents.json`. The executor rejects unknown schema versions.

### HR-2: Intent Executor Must Have Strict Guardrails
- **Localhost-only:** All URLs must resolve to `localhost`, `127.0.0.1`, or `[::1]`. Any other host is rejected.
- **No shell expansion/interpolation:** Intent fields are never passed through `eval`, backtick substitution, or `$()`. All values are treated as literal strings.
- **No arbitrary process spawning:** The executor only calls the existing scripts (`web-explorer.js`, `a11y-check.js`, `api-tester.sh`, `health-check.sh`, `port-detect.sh`) and `curl`. No other executables.
- **Capped intents per model:**
  - `visit_routes`: max 30
  - `probe_endpoints`: max 40
  - `test_forms`: max 10 form targets (each with max 5 actions)
  - `custom_curl`: max 20
  - `check_a11y`: max 10 URLs
  - `check_security_headers`: max 10 URLs
- **Capped payload sizes:** Request bodies in `probe_endpoints` and `custom_curl` are capped at 10,000 bytes. Larger payloads are truncated with a warning.
- **Capped runtime:** 30 seconds per individual intent execution. 10 minutes total per model's intent execution phase. Both enforced via timeout.
- **Approved HTTP methods only:** GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS. Others rejected.
- **Approved content types only:** `application/json`, `application/x-www-form-urlencoded`, `text/plain`, `multipart/form-data`. Others rejected.
- **No filesystem writes into the target app:** The executor writes only to its own model output directory under `runs/`.
- **Isolated per-model outputs:** Every artifact goes to `runs/{session-id}/{model}/`. No cross-model writes.

### HR-3: Intent Normalization Before Execution
- **Dedupe:** Duplicate intents (same method + path + body) are collapsed before execution.
- **Reject malformed:** Intents missing required fields (method, path) are skipped with a logged warning.
- **Coerce to canonical:** Paths are lowercased and stripped of trailing slashes. Methods are uppercased. Empty bodies become `null`.
- **Skip out-of-schema:** Any intent field or type not in the allowed schema is dropped with a warning. Unknown top-level keys in `test-intents.json` are ignored.
- **Log all normalization actions:** A `normalization-log.json` is written per model showing what was deduped, rejected, coerced, or skipped.

### HR-4: Preserve Current Repo
- 0 existing files modified unless absolutely necessary (currently: 0).
- The current Claude bot remains untouched and is the reference single-model runner.
- Sequential-only in Phase 1. No parallel execution.
- Rule-based normalizer is the default. No AI-assisted normalization dependency.
- Partial merged output is always produced if at least one model succeeds.

---

## 1. New Files to Add

```
Testing Bot/
├── ensemble-test-bot                  ← NEW: Main ensemble launcher (bash)
├── ensemble-test-bot.bat              ← NEW: Windows launcher for ensemble
├── ensemble-config.json               ← NEW: Ensemble-specific configuration
├── runners/
│   ├── runner-base.sh                 ← NEW: Shared runner logic (provider abstraction)
│   ├── claude-runner.sh               ← NEW: Claude-specific runner (wraps existing test-bot)
│   ├── openai-runner.sh               ← NEW: OpenAI-backed runner (GPT / Codex)
│   └── runner-utils.sh                ← NEW: Shared shell utilities for runners
├── prompts/
│   ├── claude-system.md               ← NEW: Claude ensemble prompt (pass-through to existing CLAUDE.md)
│   ├── gpt-system.md                  ← NEW: GPT-specific prompt (breadth/usability bias)
│   └── codex-system.md                ← NEW: Codex-specific prompt (edge-case/implementation bias)
├── merge/
│   ├── normalizer.js                  ← NEW: Rule-based report → canonical JSON converter
│   ├── deduplicator.js                ← NEW: Fingerprint-based finding merger
│   ├── report-generator.js            ← NEW: Merged JSON → final markdown report
│   ├── schema.json                    ← NEW: Canonical normalized finding schema (reference doc)
│   └── intent-executor.js             ← NEW: Executes model-generated test intents via existing scripts
└── (existing files remain untouched)
```

**Total new files: 14** (13 original + intent-executor.js)
**Modified existing files: 0**

---

## 2. Existing Files to Modify

**None in Phase 1.**

The existing bot (`test-bot`, `CLAUDE.md`, `scripts/*`, `.claude/settings.json`) remains completely untouched. The Claude runner delegates to the existing `test-bot` as-is. The intent executor calls the existing scripts (`web-explorer.js`, `a11y-check.js`, `api-tester.sh`) as subprocesses without modification.

---

## 3. Responsibilities of Each File

### `ensemble-test-bot` (bash, ~250 lines)
**Role:** Top-level orchestrator. The user's entry point for ensemble testing.
**Responsibilities:**
- Parse CLI flags: `--models=claude,gpt,codex` (default: all three), `--output=FILE`, `--timeout=DURATION`, `--browser=NAME`, target app path, optional focus string
- Generate a unique session ID (`YYYYMMDD-HHMMSS-APPNAME`)
- Create the session output directory structure under `runs/`
- **Collect app metadata** (read-only): package.json, README, directory listing, route-like files → `runs/{session-id}/app-metadata/`
- Invoke each enabled runner sequentially (see section 5 for full flow)
- For GPT/Codex: coordinate the intent-plan-execute-analyze cycle
- Wait for each runner to complete; capture exit code per model
- Invoke the normalizer on each raw report
- Invoke the deduplicator on all normalized JSONs
- Invoke the report generator to produce the final merged markdown + JSON
- Print cost summary (token counts / API costs if available)
- Handle partial failure: if one runner fails, continue with remaining models
- Exit with 0 if at least one model produced results; non-zero only if all failed

### `ensemble-test-bot.bat` (batch, ~60 lines)
**Role:** Windows launcher, mirrors existing `test-bot.bat` pattern.
**Responsibilities:** Convert Windows paths, delegate to `ensemble-test-bot` via bash.

### `ensemble-config.json` (~90 lines)
**Role:** Ensemble-specific defaults (does not replace `tester-config.json`).
**Contents:**
```json
{
  "models": {
    "claude": {
      "enabled": true,
      "runner": "runners/claude-runner.sh",
      "prompt": "prompts/claude-system.md",
      "provider": "claude-cli",
      "timeout": "45m",
      "cost_per_1k_input": 0.015,
      "cost_per_1k_output": 0.075
    },
    "gpt": {
      "enabled": true,
      "runner": "runners/openai-runner.sh",
      "prompt": "prompts/gpt-system.md",
      "provider": "openai-api",
      "model_id": "gpt-4o",
      "timeout": "30m",
      "cost_per_1k_input": 0.005,
      "cost_per_1k_output": 0.015
    },
    "codex": {
      "enabled": true,
      "runner": "runners/openai-runner.sh",
      "prompt": "prompts/codex-system.md",
      "provider": "openai-api",
      "model_id": "o3",
      "timeout": "30m",
      "cost_per_1k_input": 0.010,
      "cost_per_1k_output": 0.040
    }
  },
  "execution": {
    "mode": "sequential",
    "stop_on_failure": false
  },
  "intents": {
    "max_routes": 30,
    "max_api_endpoints": 40,
    "max_form_targets": 10,
    "max_custom_curl": 20,
    "_note": "Caps prevent models from generating unbounded test lists"
  },
  "merge": {
    "dedup_strategy": "fingerprint",
    "severity_voting": "highest-with-evidence",
    "confidence_threshold": {
      "high": 2,
      "medium": 1
    }
  }
}
```

### `runners/runner-base.sh` (~100 lines)
**Role:** Provider abstraction layer. Shared logic for all runners.
**Responsibilities:**
- Accept standardized arguments: `--target`, `--focus`, `--prompt`, `--output-dir`, `--timeout`, `--provider`, `--model-id`
- Create model-specific temp directory
- Validate prerequisites (is the provider CLI/API available?)
- Define the provider dispatch: `run_with_provider()`
  - `claude-cli`: delegates to `claude --print --dangerously-skip-permissions`
  - `openai-api`: delegates to OpenAI API via curl (or `openai` CLI if installed)
  - `local-cli`: extension point for future local models
- Capture raw output to `raw-report.md`
- Capture metadata (start time, end time, exit code, token count if available) to `meta.json`
- Return exit code

### `runners/claude-runner.sh` (~50 lines)
**Role:** Claude-specific runner. Wraps the existing `test-bot`.
**Responsibilities:**
- Source `runner-base.sh` for utilities
- Invoke `test-bot` with `--output=<model-output-dir>/raw-report.md`
- The existing `test-bot` handles all Claude interaction, prompt building, and report saving
- Capture exit code and timing metadata
- This is intentionally thin — the existing bot does the real work
- **Claude does NOT go through the intent cycle.** It retains full autonomous execution as-is. This is the reference tester.

### `runners/openai-runner.sh` (~180 lines)
**Role:** OpenAI-backed runner for GPT and Codex models. Implements the two-phase intent cycle.
**Responsibilities:**

**Phase A — Intent Generation (API call 1):**
- Source `runner-base.sh` for utilities
- Read the model-specific prompt from `prompts/<model>-system.md`
- Read app metadata from `runs/{session-id}/app-metadata/`
- Build the intent-generation prompt: "Given this app's structure, generate a structured JSON test intent list specifying exactly what you want tested."
- Call OpenAI API with system prompt + app metadata + intent request
- Parse response → save as `test-intents.json`
- Validate intents against caps in `ensemble-config.json` (truncate if over limit)

**Phase B — Intent Execution (local, no API):**
- Pass `test-intents.json` to `intent-executor.js`
- Intent executor runs the requested tests via existing scripts (see intent-executor.js below)
- Execution results saved to `execution-results.json`

**Phase C — Analysis (API call 2):**
- Build the analysis prompt: "Here are your requested test results. Analyze them and produce a structured bug report."
- Send system prompt + original app metadata + execution results to OpenAI API
- Parse response → save as `raw-report.md`
- Save token usage for both API calls to `meta.json`

**This two-call design preserves independence:** the model decides what to test (call 1), the harness executes it deterministically (local), and the model interprets its own results (call 2).

### `runners/runner-utils.sh` (~40 lines)
**Role:** Shared shell functions.
**Contents:** `log()`, `check_command()`, `safe_name()`, `elapsed_time()`, `json_escape()` — small utilities used across runners.

### `prompts/claude-system.md` (~50 lines)
**Role:** Claude ensemble prompt supplement.
**Content:** A thin wrapper that says "You are being run as part of an ensemble. Follow your existing CLAUDE.md instructions exactly. Output your standard bug report format." Essentially a pass-through — the existing CLAUDE.md does the heavy lifting.

### `prompts/gpt-system.md` (~250 lines)
**Role:** GPT-specific system prompt. Used for both intent generation and analysis phases.
**Bias:** Breadth, usability, cross-pattern recognition.
**Content (intent generation section):**
- Identity: "You are an autonomous app tester. You are a pure observer."
- Read-only invariant (same as CLAUDE.md)
- "You will receive the app's file structure, package.json, README, and key source files."
- "Your job: independently decide what to test. Output a JSON test intent list."
- Testing focus: "Prioritize broad coverage. Test every visible route. Check usability across pages. Look for inconsistent behavior, missing feedback, confusing errors."
- Intent schema (see section 5)

**Content (analysis section):**
- Bug report format (same schema as CLAUDE.md)
- "You will receive the execution results of your requested tests. Analyze them for bugs."
- "Report bugs you find. Do not invent bugs not supported by the evidence."

### `prompts/codex-system.md` (~250 lines)
**Role:** Codex-specific system prompt.
**Bias:** Edge cases, implementation-level failures, API/CLI depth.
**Content (intent generation section):**
- Same identity and invariant
- Testing focus: "Prioritize edge cases and implementation-level failures. Probe boundary conditions, type coercion issues, injection vectors, malformed inputs, API contract violations. Request unusual input combinations that developers rarely test."
- "Generate more API endpoint probes than web page visits. Focus on depth over breadth."

**Content (analysis section):**
- Same report format
- Same analysis instructions

### `merge/intent-executor.js` (~300 lines, Node.js) — **NEW in this revision**
**Role:** Executes model-generated test intents by calling existing scripts. The bridge between model planning and local execution.
**Responsibilities:**
- Read `test-intents.json` from a model's output directory
- Parse the structured intent list
- For each intent type, dispatch to the appropriate existing script:

| Intent Type | Executor Action |
|-------------|----------------|
| `visit_routes` | Run `web-explorer.js` with `--max-pages=N` targeting the specified routes. If specific routes are listed, visit them directly via Playwright `page.goto()` and capture console errors, network failures, page status. |
| `test_forms` | Run `web-explorer.js --forms` on the specified pages. If specific form actions are requested (e.g., "submit login with empty password"), execute them via targeted Playwright form interaction. |
| `probe_endpoints` | Run `api-tester.sh` with `--routes=FILE` where the routes file is generated from the intent list. Also execute any custom curl commands the model requested. |
| `check_a11y` | Run `a11y-check.js` on specified URLs. |
| `check_security_headers` | Run the security header curl check from `api-tester.sh` on specified URLs. |
| `custom_curl` | Execute specific curl commands from the intent list. **Sandboxed:** only GET/POST/PUT/PATCH/DELETE to localhost, no file writes, no shell expansion. |

- Collect all results into `execution-results.json`:
  ```json
  {
    "model": "gpt",
    "intents_requested": 24,
    "intents_executed": 22,
    "intents_skipped": 2,
    "skipped_reasons": ["custom_curl to non-localhost blocked", "route count exceeded cap"],
    "results": {
      "route_visits": [...],
      "form_tests": [...],
      "api_probes": [...],
      "a11y_findings": [...],
      "security_headers": [...],
      "custom_curl": [...]
    }
  }
  ```

- **Safety constraints:**
  - Only execute against localhost (or the target app's URL)
  - No file writes, no shell expansion in custom curl commands
  - Cap execution at config limits (max_routes, max_api_endpoints, etc.)
  - Log but skip any intent that violates constraints
  - The target app must be running (intent-executor does NOT start/stop the app — the orchestrator manages that)

### `merge/normalizer.js` (~250 lines, Node.js)
**Role:** Rule-based parser that converts raw markdown reports into canonical JSON.
**Responsibilities:**
- Read a raw markdown bug report (from any model)
- Parse using regex + structured patterns:
  - Extract bug blocks by matching `BUG #N` or `── HIGH/MEDIUM/LOW` headers
  - Extract title, severity, steps to reproduce, expected/actual, evidence
  - Extract summary counts (HIGH/MEDIUM/LOW)
  - Extract coverage notes
- Map each finding to the canonical schema (see section 4)
- Generate a fingerprint for each finding (see section 6)
- Output: `normalized.json` per model
- **Extension point:** Export a `normalize(rawText, modelName)` function. A future AI-assisted normalizer can call this first, then patch any findings it couldn't parse.
- Handle gracefully: missing fields get `null`, malformed sections get `"parse_error"` flag

### `merge/deduplicator.js` (~200 lines, Node.js)
**Role:** Merge normalized findings across models using fingerprint matching.
**Responsibilities:**
- Read all `normalized.json` files from the session
- Group findings by fingerprint similarity (exact match first, then fuzzy)
- For each group: pick canonical title, merge evidence, compute confidence, resolve severity
- Produce `merged.json` with deduplicated findings + provenance metadata
- Handle singleton findings (found by only one model) — include them with lower confidence

### `merge/report-generator.js` (~200 lines, Node.js)
**Role:** Convert `merged.json` into the final human-readable markdown report.
**Responsibilities:**
- Executive summary (total findings, consensus count, single-model count, highest-risk areas)
- Merged findings section (canonical title, severity, confidence, found-by, steps, evidence)
- Model-specific appendix (findings unique to each model)
- Coverage matrix (what each model actually requested and tested — now meaningful because each model's test surface is different)
- Cost summary (tokens used, estimated cost per model)
- Output: `merged-report.md` + `merged-report.json`

### `merge/schema.json` (~80 lines)
**Role:** Reference documentation for both the canonical finding schema and the test intent schema. Not programmatically enforced in Phase 1 — serves as the contract.

---

## 4. Canonical Normalized Schema

Each finding, regardless of source model, is normalized to this structure:

```json
{
  "id": "claude-003",
  "model": "claude",
  "title": "Login form submits with empty password",
  "severity": "HIGH",
  "surface": "web",
  "category": "validation",
  "target": "/login",
  "steps": [
    "Open /login",
    "Leave password field empty",
    "Click Sign In"
  ],
  "expected": "Form should show validation error and block submission",
  "actual": "Form submits and server returns 500 error",
  "evidence": [
    "Console error: POST /api/login returned 500",
    "No client-side required attribute on password input"
  ],
  "fingerprint": "web|validation|/login|empty-password-submit",
  "raw_text": "Original bug text from the model's report",
  "parse_confidence": "full",
  "metadata": {
    "page_url": "http://localhost:3000/login",
    "http_status": 500,
    "console_error": true
  }
}
```

**Test intent schema** (output of GPT/Codex intent generation):

```json
{
  "schemaVersion": "1",
  "model": "gpt",
  "app_name": "myapp",
  "generated_at": "2026-03-06T14:30:00Z",
  "intents": {
    "visit_routes": [
      "/", "/login", "/register", "/dashboard", "/admin",
      "/settings", "/profile", "/api/docs", "/404-test",
      "/admin/settings"
    ],
    "test_forms": [
      {
        "url": "/login",
        "actions": [
          "submit empty",
          "submit with invalid email format",
          "submit with valid email but empty password",
          "submit with SQL injection in email field"
        ]
      },
      {
        "url": "/register",
        "actions": [
          "submit empty",
          "submit with mismatched passwords",
          "submit with password shorter than minimum length"
        ]
      }
    ],
    "probe_endpoints": [
      {"method": "GET",    "path": "/api/users",          "label": "list users no auth"},
      {"method": "GET",    "path": "/api/users/1",        "label": "get user by id"},
      {"method": "GET",    "path": "/api/users/99999",    "label": "nonexistent user"},
      {"method": "POST",   "path": "/api/users",          "body": "{}",  "label": "create user empty body"},
      {"method": "DELETE", "path": "/api/users/1",         "label": "delete user no auth"},
      {"method": "GET",    "path": "/api/admin/config",    "label": "admin config no auth"},
      {"method": "POST",   "path": "/api/login",           "body": "{\"email\":\"' OR 1=1--\",\"password\":\"x\"}", "label": "SQL injection login"}
    ],
    "check_a11y": ["/", "/login", "/dashboard"],
    "check_security_headers": ["/", "/api/users"],
    "custom_curl": [
      {"method": "GET",  "url": "/robots.txt",             "label": "check robots.txt"},
      {"method": "GET",  "url": "/.env",                   "label": "check env file exposure"},
      {"method": "GET",  "url": "/api/graphql?query={__schema{types{name}}}", "label": "GraphQL introspection"}
    ]
  }
}
```

**Field definitions (finding schema):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | yes | `{model}-{NNN}` sequential per model |
| `model` | string | yes | `claude`, `gpt`, or `codex` |
| `title` | string | yes | Short descriptive title |
| `severity` | enum | yes | `HIGH`, `MEDIUM`, `LOW` |
| `surface` | enum | yes | `web`, `api`, `cli`, `electron`, `general` |
| `category` | enum | yes | `validation`, `a11y`, `network`, `security`, `crash`, `usability`, `performance`, `config` |
| `target` | string | yes | Route, endpoint, command, or page URL |
| `steps` | string[] | no | Ordered reproduction steps |
| `expected` | string | no | Expected behavior |
| `actual` | string | no | Actual behavior |
| `evidence` | string[] | no | Console errors, stack traces, status codes |
| `fingerprint` | string | yes | Dedup key (see section 6) |
| `raw_text` | string | yes | Original text from model report |
| `parse_confidence` | enum | yes | `full`, `partial`, `failed` |
| `metadata` | object | no | Freeform additional data |

**Merged finding schema** (output of deduplicator):

```json
{
  "merged_id": "M-001",
  "canonical_title": "Login form submits with empty password",
  "severity": "HIGH",
  "confidence": "high",
  "found_by": ["claude", "gpt"],
  "surface": "web",
  "category": "validation",
  "target": "/login",
  "steps": ["Open /login", "Leave password field empty", "Click Sign In"],
  "expected": "Form should show validation error",
  "actual": "Form submits, server returns 500",
  "evidence": [
    {"model": "claude", "text": "Console error: POST /api/login returned 500"},
    {"model": "gpt", "text": "No required attribute on password input, server error on empty submit"}
  ],
  "severity_votes": {"claude": "HIGH", "gpt": "HIGH"},
  "source_findings": ["claude-003", "gpt-007"],
  "fingerprint": "web|validation|/login|empty-password-submit"
}
```

---

## 5. Sequential Orchestration Flow

```
ensemble-test-bot /path/to/app "optional focus"
│
├── 1. SETUP
│   ├── Parse CLI args (--models, --output, --timeout, --browser)
│   ├── Validate target app directory exists
│   ├── Generate session ID: YYYYMMDD-HHMMSS-{safe-app-name}
│   ├── Create session directory: runs/{session-id}/
│   ├── Create per-model dirs: runs/{session-id}/{claude,gpt,codex}/
│   └── Print ensemble banner (models enabled, target, timeout)
│
├── 2. APP METADATA COLLECTION (read-only, no app launch)
│   ├── Read package.json, README.md, .env.example → runs/{session-id}/app-metadata/
│   ├── List directory structure (ls -R, capped depth) → app-metadata/tree.txt
│   ├── Read main entry point files (server.js, app.py, etc.) → app-metadata/sources/
│   ├── Extract route-like patterns from source (grep for '/api/', router.get, etc.) → app-metadata/routes-hint.txt
│   └── This metadata is given to ALL models for independent planning
│
├── 3. MODEL RUNS (sequential)
│   │
│   ├── 3a. CLAUDE RUN (full autonomous — unchanged)
│   │   ├── Invoke: bash runners/claude-runner.sh \
│   │   │     --target=/path/to/app \
│   │   │     --focus="optional focus" \
│   │   │     --output-dir=runs/{session-id}/claude/ \
│   │   │     --timeout=45m
│   │   ├── Claude runner delegates to existing test-bot
│   │   ├── test-bot launches app, explores, kills app, writes report
│   │   ├── Raw report → runs/{session-id}/claude/raw-report.md
│   │   ├── Metadata → runs/{session-id}/claude/meta.json
│   │   └── Log exit code; continue even if failed
│   │
│   ├── 3b. GPT RUN (intent-driven)
│   │   │
│   │   ├── PHASE A: Intent Generation (OpenAI API call 1)
│   │   │   ├── Send to GPT: system prompt + app metadata + "generate test intents"
│   │   │   ├── GPT returns structured JSON test intent list
│   │   │   └── Save → runs/{session-id}/gpt/test-intents.json
│   │   │
│   │   ├── PHASE B: Intent Execution (local, no API)
│   │   │   ├── Orchestrator starts the target app in background
│   │   │   ├── Waits for health check (health-check.sh)
│   │   │   ├── Invoke: node merge/intent-executor.js \
│   │   │   │     --intents=runs/{session-id}/gpt/test-intents.json \
│   │   │   │     --base-url=http://localhost:PORT \
│   │   │   │     --output=runs/{session-id}/gpt/execution-results.json \
│   │   │   │     --browser=chromium --headless=true
│   │   │   ├── Intent executor calls web-explorer.js, api-tester.sh, a11y-check.js as needed
│   │   │   ├── Results → runs/{session-id}/gpt/execution-results.json
│   │   │   └── Orchestrator kills the target app
│   │   │
│   │   └── PHASE C: Analysis (OpenAI API call 2)
│   │       ├── Send to GPT: system prompt + app metadata + execution results + "produce bug report"
│   │       ├── GPT analyzes ITS OWN execution results
│   │       ├── Raw report → runs/{session-id}/gpt/raw-report.md
│   │       └── Token usage → runs/{session-id}/gpt/meta.json
│   │
│   └── 3c. CODEX RUN (intent-driven, same structure as GPT)
│       ├── PHASE A: Intent Generation → runs/{session-id}/codex/test-intents.json
│       ├── PHASE B: Intent Execution (restart app) → runs/{session-id}/codex/execution-results.json
│       └── PHASE C: Analysis → runs/{session-id}/codex/raw-report.md
│
├── 4. NORMALIZATION
│   ├── For each model that produced a raw report:
│   │   └── node merge/normalizer.js runs/{session-id}/{model}/raw-report.md \
│   │         --model={model} \
│   │         --output=runs/{session-id}/{model}/normalized.json
│   └── Skip models that failed (no raw-report.md)
│
├── 5. DEDUPLICATION & MERGE
│   ├── node merge/deduplicator.js \
│   │     --input=runs/{session-id}/*/normalized.json \
│   │     --output=runs/{session-id}/merged.json
│   └── Produces merged findings with confidence scores
│
├── 6. REPORT GENERATION
│   ├── node merge/report-generator.js \
│   │     --input=runs/{session-id}/merged.json \
│   │     --meta=runs/{session-id}/*/meta.json \
│   │     --output=runs/{session-id}/merged-report.md
│   └── Also copies to reports/ with timestamp for consistency with existing bot
│
└── 7. OUTPUT
    ├── Print merged report to terminal
    ├── Print cost summary
    ├── Print: "Full session data: runs/{session-id}/"
    └── Exit 0 if any model succeeded; exit 1 if all failed
```

**Key difference from original plan:** The app is started and stopped for each intent-driven model (3b, 3c). This ensures clean state between model runs and avoids cross-contamination. Claude starts/stops the app itself (via test-bot). GPT and Codex have the orchestrator manage app lifecycle for their intent execution phase.

**App lifecycle summary:**
```
Claude run:  test-bot starts app → tests → test-bot kills app
GPT run:     orchestrator starts app → intent-executor tests → orchestrator kills app
Codex run:   orchestrator starts app → intent-executor tests → orchestrator kills app
```

---

## 6. Dedup / Fingerprint Strategy

### Fingerprint Construction

Each normalized finding gets a fingerprint built from four components:

```
{surface}|{category}|{normalized_target}|{trigger_condition}
```

**Component normalization rules:**

| Component | Normalization |
|-----------|--------------|
| `surface` | Lowercase enum: `web`, `api`, `cli`, `electron`, `general` |
| `category` | Lowercase enum: `validation`, `a11y`, `network`, `security`, `crash`, `usability`, `performance`, `config` |
| `normalized_target` | Strip query params, strip trailing slashes, lowercase. `/api/Login/` → `/api/login` |
| `trigger_condition` | Slugified summary of the triggering action: `empty-password-submit`, `missing-alt-text`, `no-rate-limiting`, `path-traversal-attempt` |

### Matching Algorithm

**Pass 1 — Exact fingerprint match:**
Findings with identical fingerprints are grouped immediately.

**Pass 2 — Fuzzy target match:**
If two findings share the same `surface|category` and their targets overlap (e.g., `/login` vs `/api/login`), compare `trigger_condition` using Levenshtein distance. If distance <= 3 (or one is a substring of the other), group them.

**Pass 3 — Singletons:**
Remaining unmatched findings are kept as-is with confidence based on evidence strength.

### Merge Rules Within a Group

| Field | Rule |
|-------|------|
| `canonical_title` | Pick the longest title (usually most descriptive) |
| `severity` | Highest severity if >=2 models agree; otherwise highest with a note |
| `confidence` | `"high"` if >=2 models, `"medium"` if 1 model with evidence, `"needs_review"` if 1 model with weak evidence |
| `steps` | Pick the most detailed steps (longest array) |
| `evidence` | Union all evidence, tagged by model |
| `found_by` | List of models that contributed |

---

## 7. Failure-Handling Behavior

### Runner Failures

| Scenario | Behavior |
|----------|----------|
| Runner exits non-zero | Log warning, record exit code in `meta.json`, continue to next model |
| Runner times out | Log timeout warning, save partial output if any, continue |
| Runner produces empty report | Log warning, skip normalization for this model, continue |
| API key missing (OpenAI) | Log error immediately, skip this model, continue |
| API rate limited | Retry once after 30s wait; if still failing, skip with warning |
| All models fail | Exit with code 1, produce a minimal report listing what failed and why |
| Intent generation succeeds but intent execution fails | Save intents for debugging, mark model as "partial-intent-only" in meta.json, skip analysis phase |
| Intent generation returns invalid JSON | Log parse error, skip this model, continue |
| App fails to start for intent execution | Log as HIGH finding ("app fails to start"), skip intent execution, continue to next model |

### Normalization Failures

| Scenario | Behavior |
|----------|----------|
| Parser can't extract any findings | Set `parse_confidence: "failed"` on the whole model output, include raw text in appendix |
| Parser extracts some findings but not all | Set per-finding `parse_confidence` to `"partial"` or `"full"`, include unparsed sections in appendix |
| Malformed JSON output | Catch, log, fall back to treating entire output as one `parse_confidence: "failed"` block |

### Merge Failures

| Scenario | Behavior |
|----------|----------|
| Only 1 model produced results | Produce report with no dedup needed, note "single-model only" in summary |
| 0 normalized files | Exit with error, produce failure report |
| Dedup creates bad groupings | Phase 1 accepts this risk; merged report includes raw per-model appendix for manual review |

### Partial Result Guarantee

The orchestrator always produces output if at least one model succeeded. The merged report clearly indicates which models participated:

```
Models: Claude ✅ (full autonomous)  |  GPT ✅ (intent-driven)  |  Codex ❌ (API timeout)
```

---

## 8. Phase 1 Output Structure

### Directory Layout

```
runs/
  20260306-142500-myapp/
    app-metadata/                      ← Read-only app context given to all models
      package.json
      readme.md
      tree.txt
      routes-hint.txt
      sources/
        server.js
        ...
    claude/
      raw-report.md                    ← Original Claude bug report (full autonomous)
      normalized.json                  ← Parsed into canonical schema
      meta.json                        ← Timing, exit code
    gpt/
      test-intents.json                ← GPT's independent test plan
      execution-results.json           ← Results of executing GPT's intents
      raw-report.md                    ← GPT's bug report based on its own results
      normalized.json
      meta.json                        ← Timing, tokens, cost (both API calls)
    codex/
      test-intents.json                ← Codex's independent test plan
      execution-results.json           ← Results of executing Codex's intents
      raw-report.md
      normalized.json
      meta.json
    merged.json                        ← Deduplicated canonical findings
    merged-report.md                   ← Final human-readable report
    session.json                       ← Session metadata (models, target, timing, costs)
```

### `session.json` Example

```json
{
  "session_id": "20260306-142500-myapp",
  "target": "/c/Users/Matt1/projects/myapp",
  "focus": "Test the login and checkout flow",
  "started": "2026-03-06T14:25:00-07:00",
  "finished": "2026-03-06T15:48:32-07:00",
  "duration_minutes": 83,
  "models": {
    "claude": {
      "status": "success",
      "mode": "full-autonomous",
      "exit_code": 0,
      "duration_minutes": 42,
      "findings_count": 8
    },
    "gpt": {
      "status": "success",
      "mode": "intent-driven",
      "exit_code": 0,
      "duration_minutes": 12,
      "intents_requested": 24,
      "intents_executed": 22,
      "findings_count": 7,
      "tokens_in": 18400,
      "tokens_out": 6200,
      "cost_usd": 0.19
    },
    "codex": {
      "status": "failed",
      "mode": "intent-driven",
      "exit_code": 1,
      "error": "API timeout during intent generation"
    }
  },
  "total_estimated_cost_usd": 1.34,
  "findings_summary": {
    "total_unique": 11,
    "consensus": 6,
    "single_model": 5,
    "high": 3,
    "medium": 5,
    "low": 3
  }
}
```

### Merged Report Format

```
===========================================================
  ENSEMBLE APP TESTING REPORT
  App: myapp
  Path: /c/Users/Matt1/projects/myapp
  Tested: 2026-03-06 14:25 MST
  Duration: 83 minutes (sequential)
  Models: Claude [full] | GPT [intent-driven] | Codex [failed]
  Tester: Ensemble Testing Bot v1 (Phase 1)
===========================================================

EXECUTIVE SUMMARY
-----------------------------------------------------------
Total unique findings: 11
  Consensus (2+ models):  6
  Single-model only:      5

By severity:
  HIGH:   3
  MEDIUM: 5
  LOW:    3

Estimated cost: $1.34 (Claude: $1.12, GPT: $0.19, Codex: $0.03 before failure)

Highest-risk areas: authentication, form validation

===========================================================
TESTING INDEPENDENCE SUMMARY
===========================================================
Each model independently decided what to test:

  Claude: Visited 12 pages, tested 4 forms, probed 28 API endpoints
  GPT:    Requested 18 routes, 6 form tests, 22 API probes, 3 custom curls
  Codex:  (failed before intent generation)

  Overlap: 8 routes tested by both Claude and GPT
  GPT-only: /admin/settings, /api/graphql, /.env (routes Claude did not visit)
  Claude-only: /about, /terms, /contact (routes GPT did not request)

===========================================================
CONSENSUS FINDINGS (found by 2+ models)
===========================================================

FINDING #1 -- HIGH -- Confidence: HIGH
Title: Login form submits with empty password
Found by: Claude, GPT
Surface: web | Category: validation

Steps to Reproduce:
  1. Open /login
  2. Leave password field empty
  3. Click Sign In

Expected: Form should show validation error
Actual:   Form submits and server returns 500

Evidence:
  [Claude] Console error: POST /api/login returned 500
  [GPT]    HTTP 500 on POST /api/login with empty password field

-----------------------------------------------------------

[...more findings...]

===========================================================
SINGLE-MODEL FINDINGS
===========================================================

FINDING #8 -- MEDIUM -- Confidence: MEDIUM
Title: .env file accessible via HTTP
Found by: GPT only (GPT independently requested /.env check)

Steps to Reproduce:
  1. curl http://localhost:3000/.env

Expected: 404 or 403
Actual:   200 with environment variables visible

Evidence:
  [GPT] GET /.env returned HTTP 200 with OPENAI_API_KEY visible

-----------------------------------------------------------

[...more findings...]

===========================================================
MODEL APPENDIX
===========================================================

-- Claude (42 min, 8 findings, full autonomous) --
  Full report: runs/20260306-142500-myapp/claude/raw-report.md

-- GPT (12 min, 7 findings, $0.19, intent-driven) --
  Test intents: runs/20260306-142500-myapp/gpt/test-intents.json
  Execution results: runs/20260306-142500-myapp/gpt/execution-results.json
  Full report: runs/20260306-142500-myapp/gpt/raw-report.md

-- Codex (failed -- API timeout) --
  No output produced.

===========================================================
COVERAGE MATRIX
===========================================================
  Area               Claude    GPT        Codex
  -----------------  --------  ---------  -----
  Routes visited       12        18         --
  Forms tested          4         6         --
  API endpoints        28        22         --
  A11y checks         yes       yes         --
  Security headers    yes       yes         --
  Auth flows          yes       yes         --
  Custom probes        --         3         --

  Note: Claude explored autonomously. GPT/Codex routes were
  independently chosen by each model based on app metadata.

===========================================================
```

---

## 9. Validation Plan

### Syntax Validation (automated, run after every edit)
- `bash -n ensemble-test-bot`
- `bash -n runners/runner-base.sh`
- `bash -n runners/claude-runner.sh`
- `bash -n runners/openai-runner.sh`
- `bash -n runners/runner-utils.sh`
- `node --check merge/normalizer.js`
- `node --check merge/deduplicator.js`
- `node --check merge/report-generator.js`
- `node --check merge/intent-executor.js`

### Unit Validation (manual, with sample data)
1. **Intent executor test:** Feed it a sample `test-intents.json` with 5 route visits + 3 API probes → verify it calls web-explorer.js and api-tester.sh correctly, produces valid `execution-results.json`
2. **Intent executor safety test:** Feed it an intent with a non-localhost URL → verify it is skipped with a logged warning
3. **Intent executor cap test:** Feed it 50 routes when config cap is 30 → verify only 30 are executed
4. **Normalizer test:** Feed it a sample Claude raw report → verify normalized.json matches schema
5. **Normalizer test:** Feed it a sample GPT raw report (slightly different format) → verify it still parses
6. **Normalizer test:** Feed it a malformed report → verify `parse_confidence: "failed"` behavior
7. **Deduplicator test:** Feed it 2 normalized.json files with overlapping findings → verify correct grouping
8. **Deduplicator test:** Feed it 1 normalized.json (single model) → verify passthrough
9. **Report generator test:** Feed it merged.json → verify markdown output matches expected format

### Integration Validation (end-to-end)
1. Run `ensemble-test-bot` against a known sample app with `--models=claude` (single model) → verify output matches existing bot quality
2. Run with `--models=claude,gpt` → verify intent generation, execution, analysis, normalization, merge, and final report
3. Run with `--models=claude,gpt,codex` where Codex API key is invalid → verify graceful failure and partial report
4. Compare Claude-only ensemble run vs direct `test-bot` run → verify no regression
5. Verify no files were created/modified in the target app directory
6. Inspect `test-intents.json` for GPT/Codex → verify they requested different routes/endpoints (demonstrating independence)

### Regression Validation
- Run existing `test-bot` directly (not through ensemble) → verify it still works identically
- Verify `.claude/settings.json` is unchanged
- Verify `CLAUDE.md` is unchanged
- Verify all files in `scripts/` are unchanged

---

## 10. Risks Intentionally Deferred to Phase 2

| Risk | Why Deferred | Phase 2 Mitigation |
|------|-------------|-------------------|
| **Parallel execution contention** | Stateful apps can't handle concurrent probing safely | Add `--parallel` flag with app-restart-per-model isolation |
| **AI-assisted normalization** | Rule-based is simpler and deterministic | Add optional `--ai-normalize` flag that uses Claude to fix parse failures |
| **Severity voting disagreements** | Phase 1 uses "highest-with-evidence" heuristic | Add weighted voting based on model track record |
| **Fingerprint false positives** | Fuzzy matching may over-merge distinct bugs | Add a verification pass that checks merged findings for logical consistency |
| **Coverage gap analysis** | Phase 1 shows what was tested per model, not what was missed | Add route enumeration + coverage diff to identify blind spots |
| **Token/cost optimization** | Phase 1 sends full app metadata to GPT/Codex | Add metadata summarization to reduce token count |
| **Adaptive retesting** | No follow-up runs based on findings | Add targeted retest of disputed/low-confidence findings |
| **Custom model support** | Only Claude + OpenAI in Phase 1 | Add `local-cli` provider for Ollama, llama.cpp, etc. |
| **Full GPT/Codex live execution** | GPT/Codex plan independently but execution is harness-mediated | Integrate with OpenAI tool-use or Codex sandbox for full autonomous execution |
| **Report format inconsistency** | GPT/Codex may not follow the exact report format | AI-assisted normalizer; or structured output (JSON mode) in API calls |
| **Historical comparison** | No run-over-run diff | Add `--compare=<previous-session>` to show new/fixed/persistent bugs |
| **Intent quality validation** | Models may generate nonsensical intents | Add intent sanity checker (valid HTTP methods, reasonable paths, no injection in labels) |
| **Form interaction depth** | Phase 1 form intents are limited to empty-submit + basic actions | Add richer form interaction DSL (fill field X with value Y, then click Z) |

---

## Summary

Phase 1 adds 14 new files and modifies 0 existing files. It produces a sequential ensemble run where each model independently decides what to test: Claude runs fully autonomously (unchanged), while GPT and Codex independently generate test intents based on app metadata, which are then executed locally through existing scripts. Each model analyzes its own execution results. Reports are normalized, deduplicated via fingerprinting, and merged into one final markdown + JSON report with confidence scoring.

The existing Claude bot is untouched. Partial failure is tolerated. Cost is visible. The test-intent architecture preserves meaningful model independence at the planning layer while keeping execution deterministic and safe through the existing script harness. The architecture cleanly supports Phase 2 additions (parallel mode, AI normalization, full model execution, coverage analysis) without redesign.

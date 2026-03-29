# Plan: Autonomous Agent Workflow Orchestrator — Project Setup

## Context
The user wants to scaffold a new Python project called "Autonomous Agent Workflow Orchestrator" at `C:\Users\Matt1\OneDrive\Desktop\Autonomous Agent Workflow Orchestrator`. This is a deterministic, file-based local control plane that:
- Analyzes a repository to produce a structured project snapshot
- Scores a YAML registry of specialized agents against that snapshot
- Activates/deactivates agents based on scoring rules and project signals
- Routes development tasks to the most appropriate active agent
- Maintains deterministic state, logs, and evidence files

**Runtime loop:** repo → snapshot → score agents → select active set → route tasks → log evidence → persist state

Templates to apply from `C:\Users\Matt1\OneDrive\Desktop\Universal Project Setup`:
- `claude-setup/` — full Claude Code config (adapted for Python)
- `scripts/` — selective; Node.js scripts inapplicable; create `scripts/audit.py` instead

---

## Final Directory Structure

```
Autonomous Agent Workflow Orchestrator/
├── .claude/
│   ├── CLAUDE.md                        # Adapted from claude-setup/CLAUDE.md
│   ├── settings.json                    # Adapted from claude-setup/settings.json
│   ├── hooks/
│   │   ├── validate-bash.sh             # Copied; blocks dangerous shell patterns
│   │   ├── protect-files.sh             # Copied; blocks writes to critical files
│   │   ├── post-commit.sh               # Adapted; logs to audit-log.md
│   │   └── session-init.sh              # Adapted; OpenClaw integration
│   ├── agents/
│   │   ├── Architect-Planner.md         # Adapted for orchestrator architecture
│   │   ├── Orchestration-Engine.md      # NEW: scoring/lifecycle/routing logic
│   │   ├── Repo-Analyzer.md             # NEW: snapshot building & signal detection
│   │   ├── Agent-Registry.md            # NEW: YAML registry management
│   │   ├── Testing.md                   # Adapted for Python/pytest
│   │   └── DevOps-Deployment.md         # Adapted (minimal — CLI-only MVP)
│   ├── rules/
│   │   ├── src/RULES.md                 # Adapted for Python conventions
│   │   └── tests/RULES.md               # Adapted for pytest conventions
│   └── skills/
│       ├── status/SKILL.md              # /status skill
│       ├── test/SKILL.md                # /test skill (pytest)
│       └── compare-project/SKILL.md     # /compare-project skill (copied as-is)
│
├── agent-runtime/                       # Core runtime package
│   ├── main.py                          # CLI entry point (argparse)
│   ├── models.py                        # Dataclasses: ProjectSnapshot, Agent, ScoredAgent, RoutingDecision
│   ├── registry_loader.py               # Load + validate agent-registry.yaml
│   ├── snapshot_builder.py              # Orchestrates snapshot construction pipeline
│   ├── snapshot_detectors.py            # Per-signal detectors (has_auth, has_docker, etc.)
│   ├── snapshot_normalizer.py           # Normalize raw detector output → canonical fields
│   ├── snapshot_validator.py            # Validate snapshot against project-snapshot-schema.yaml
│   ├── event_detector.py                # Detect change events between snapshots (new_auth, new_migration, etc.)
│   ├── score_engine.py                  # Score each agent against snapshot using agent-selection-rules.yaml
│   ├── dependency_resolver.py           # Resolve agent dependencies (agent A requires agent B)
│   ├── overlap_resolver.py              # Resolve agent ownership overlaps
│   ├── selector.py                      # Final active-set selection from scored + resolved agents
│   ├── lifecycle_manager.py             # Activate/deactivate agents; write state; emit lifecycle events
│   ├── task_router.py                   # Route task description to best active agent
│   ├── handoff_manager.py               # Manage agent handoffs and task continuity
│   ├── runtime_controller.py            # Orchestrates full cycle: snapshot → score → select → route
│   ├── queue_manager.py                 # Task queue: enqueue, dequeue, status
│   ├── policy_guard.py                  # Enforce policy rules before agent activation/routing
│   ├── audit_logger.py                  # Write structured JSONL evidence records
│   ├── state_store.py                   # Load/save JSON state files
│   ├── health_monitor.py                # Runtime health checks and diagnostics
│   ├── adapters/
│   │   ├── base.py                      # Abstract adapter interface
│   │   ├── claude_adapter.py            # Claude API adapter (stub)
│   │   └── codex_adapter.py             # Codex adapter (stub)
│   ├── executors/
│   │   ├── shell_executor.py            # Run shell commands deterministically
│   │   ├── git_executor.py              # Git operations (log, diff, status)
│   │   ├── test_executor.py             # Run pytest and capture results
│   │   └── file_executor.py             # File read/write/search operations
│   └── storage/                         # Runtime state — gitignored
│       ├── snapshots/                   # Snapshot JSON files (timestamped)
│       ├── runs/                        # Per-cycle run records
│       ├── logs/                        # JSONL audit/evidence logs
│       └── state/                       # Current active state (active-agents.json, etc.)
│
├── schemas/                             # YAML control-plane (authoritative definitions)
│   ├── project-snapshot-schema.yaml     # All fields snapshot_builder produces
│   ├── snapshot-builder-spec.yaml       # Which detectors run and in what order
│   ├── agent-registry.yaml              # All agent definitions (id, name, scope, keywords)
│   ├── agent-selection-rules.yaml       # Scoring rules: signals_required, signals_bonus, veto, thresholds
│   └── agent-lifecycle-runtime-spec.yaml # Lifecycle policies: activation, deactivation, handoff rules
│
├── scripts/
│   └── audit.py                         # Python security audit (secrets, eval/exec, os.system)
│
├── requirements.txt                     # PyYAML>=6.0
├── .env.example                         # OPENCLAW_WEBHOOK_URL= (optional)
├── .gitignore
├── STATUS.md                            # Session state tracker
└── audit-log.md                         # Auto-appended by post-commit hook
```

---

## Implementation Steps

### Step 1: Create project directory and initialize git
```bash
mkdir "C:\Users\Matt1\OneDrive\Desktop\Autonomous Agent Workflow Orchestrator"
cd "..."
git init
```

### Step 2: Apply claude-setup templates

**2a. Copy `.claude/` directory structure** from `Universal Project Setup/claude-setup/`

**2b. Adapt `.claude/CLAUDE.md`** — fill all `[PLACEHOLDER]` values:
- `[PROJECT_NAME]` → `Autonomous Agent Workflow Orchestrator`
- Stack: `Python 3.11+, PyYAML, argparse, standard library`
- Auth: `None (local CLI tool)`
- Database: `YAML control-plane + JSON flat-file state in agent-runtime/storage/`
- Deploy target: `Local CLI runtime`
- Key commands: `python agent-runtime/main.py snapshot|select|cycle|health|explain`
- Remove: frontend, browser-bot, CSRF sections
- Add sections: Runtime Loop, YAML Control-Plane, Agent Lifecycle, Scoring Engine

**2c. Adapt `.claude/settings.json`** — update memory file paths; keep hooks config as-is

**2d. Copy all 4 hooks** from `claude-setup/hooks/`; update any hardcoded paths to match this project

**2e. Write 6 project-specific Claude agents** (see agent table below)

**2f. Adapt rules** — replace Node.js/JS references with Python/pytest

**2g. Set up 3 skills**: `/status` (Python commands), `/test` (pytest), `/compare-project` (copy unchanged)

### Step 3: Write project-specific Claude agents

| File | Scope & Responsibilities |
|---|---|
| `Architect-Planner.md` | System architecture, YAML schema design, ADRs, module boundaries |
| `Orchestration-Engine.md` | score_engine, selector, lifecycle_manager, runtime_controller, policy_guard |
| `Repo-Analyzer.md` | snapshot_builder, snapshot_detectors, event_detector, normalizer, validator |
| `Agent-Registry.md` | registry_loader, schemas/*.yaml definitions, agent YAML authoring |
| `Testing.md` | pytest tests, snapshot fixtures, score engine unit tests, CLI integration tests |
| `DevOps-Deployment.md` | requirements.txt, .gitignore, CLI packaging, local environment setup |

### Step 4: Create YAML control-plane (5 schema files — real implementations)

**`schemas/project-snapshot-schema.yaml`**
```yaml
version: "1.0"
snapshot:
  schema_version: string        # "1.0"
  repo_path: string             # Absolute path to repo
  captured_at: string           # ISO 8601 timestamp
  snapshot_hash: string         # SHA256 of snapshot content

  identity:
    project_name: string
    primary_language: string    # python | javascript | typescript | go | rust | other
    languages: [string]
    frameworks: [string]        # e.g. [fastapi, react, pytest]
    package_managers: [string]  # e.g. [pip, npm, cargo]

  stage:
    value: string               # prototype | early | mvp | production | legacy
    confidence: float           # 0.0–1.0

  complexity:
    value: string               # low | medium | high | very_high
    file_count: int
    line_count: int
    module_count: int

  signals:
    has_auth: bool
    has_migrations: bool
    has_docker: bool
    has_ci: bool
    has_tests: bool
    has_makefile: bool
    has_config_files: bool
    has_external_api: bool
    has_user_data: bool
    has_multiple_languages: bool
    has_multiple_frameworks: bool
    has_background_jobs: bool
    high_complexity: bool       # derived: complexity.value in [high, very_high]

  risk_factors: [string]        # e.g. [no_tests, no_auth, hardcoded_secrets, no_ci]

  operational:
    last_commit_age_days: int
    open_file_count: int
    test_coverage_pct: float    # null if unknown
    has_uncommitted_changes: bool
```

---

**`schemas/snapshot-builder-spec.yaml`**
```yaml
version: "1.0"
pipeline:
  - step: language_detector
    module: snapshot_detectors
    function: detect_languages
    produces: [primary_language, languages, package_managers]
    enabled: true
    order: 1

  - step: framework_detector
    module: snapshot_detectors
    function: detect_frameworks
    produces: [frameworks]
    requires: [languages]
    enabled: true
    order: 2

  - step: signal_detector
    module: snapshot_detectors
    function: detect_signals
    produces: [has_auth, has_migrations, has_docker, has_ci, has_tests,
               has_makefile, has_config_files, has_external_api,
               has_user_data, has_background_jobs]
    enabled: true
    order: 3

  - step: complexity_estimator
    module: snapshot_detectors
    function: estimate_complexity
    produces: [complexity, file_count, line_count, module_count]
    enabled: true
    order: 4

  - step: stage_classifier
    module: snapshot_detectors
    function: classify_stage
    produces: [stage]
    requires: [complexity, has_tests, has_ci, has_docker]
    enabled: true
    order: 5

  - step: risk_scanner
    module: snapshot_detectors
    function: scan_risk_factors
    produces: [risk_factors]
    requires: [has_tests, has_ci, has_auth]
    enabled: true
    order: 6

  - step: operational_reader
    module: snapshot_detectors
    function: read_operational_signals
    produces: [last_commit_age_days, open_file_count, has_uncommitted_changes]
    enabled: true
    order: 7

  - step: normalizer
    module: snapshot_normalizer
    function: normalize
    produces: [high_complexity, has_multiple_languages, has_multiple_frameworks]
    requires: [complexity, languages, frameworks]
    enabled: true
    order: 8

  - step: validator
    module: snapshot_validator
    function: validate
    produces: []
    requires: [all]
    enabled: true
    order: 9
```

---

**`schemas/agent-registry.yaml`**
```yaml
version: "1.0"
agents:
  - id: architect_agent
    name: Architect & Planner
    description: Owns system architecture, schema design, module boundaries, and ADRs
    model: claude-sonnet-4-6
    priority: 1
    scope:
      owns: [docs/, schemas/, "*.md", "*.yaml"]
      reads: [agent-runtime/, .claude/]
      forbidden: [agent-runtime/storage/]
    keywords: [architecture, schema, design, structure, module, interface, boundary, adr, refactor, system]

  - id: orchestration_agent
    name: Orchestration Engine
    description: Owns scoring logic, lifecycle management, selector, policy guard, and runtime controller
    model: claude-sonnet-4-6
    priority: 2
    scope:
      owns: [agent-runtime/score_engine.py, agent-runtime/selector.py,
             agent-runtime/lifecycle_manager.py, agent-runtime/runtime_controller.py,
             agent-runtime/policy_guard.py]
      reads: [schemas/, agent-runtime/models.py]
      forbidden: [agent-runtime/storage/]
    keywords: [score, select, activate, deactivate, lifecycle, policy, orchestrate, cycle, rule, threshold]

  - id: repo_analyzer_agent
    name: Repo Analyzer
    description: Owns snapshot building, signal detection, normalization, and event detection
    model: claude-sonnet-4-6
    priority: 2
    scope:
      owns: [agent-runtime/snapshot_builder.py, agent-runtime/snapshot_detectors.py,
             agent-runtime/snapshot_normalizer.py, agent-runtime/snapshot_validator.py,
             agent-runtime/event_detector.py]
      reads: [schemas/project-snapshot-schema.yaml, schemas/snapshot-builder-spec.yaml]
      forbidden: [agent-runtime/storage/]
    keywords: [snapshot, detect, analyze, signal, repo, language, framework, complexity, risk, stage]

  - id: registry_agent
    name: Agent Registry Manager
    description: Owns YAML registry definitions, registry loader, and agent metadata
    model: claude-sonnet-4-6
    priority: 2
    scope:
      owns: [schemas/agent-registry.yaml, schemas/agent-selection-rules.yaml,
             agent-runtime/registry_loader.py]
      reads: [agent-runtime/models.py]
      forbidden: [agent-runtime/storage/]
    keywords: [registry, agent, definition, yaml, metadata, rule, keyword, scope]

  - id: routing_agent
    name: Task Router & Handoff Manager
    description: Owns task routing decisions, handoff management, and queue management
    model: claude-sonnet-4-6
    priority: 3
    scope:
      owns: [agent-runtime/task_router.py, agent-runtime/handoff_manager.py,
             agent-runtime/queue_manager.py]
      reads: [agent-runtime/models.py, agent-runtime/state_store.py]
      forbidden: [agent-runtime/storage/]
    keywords: [route, task, handoff, queue, dispatch, assign, routing, decision]

  - id: testing_agent
    name: Testing
    description: Owns pytest unit and integration tests for all runtime modules
    model: claude-sonnet-4-6
    priority: 4
    scope:
      owns: [tests/]
      reads: [agent-runtime/, schemas/]
      forbidden: [agent-runtime/storage/]
    keywords: [test, pytest, unit, integration, fixture, mock, coverage, assert]

  - id: security_agent
    name: Security & Auth Agent
    description: Owns security scanning, auth-related runtime logic, secrets detection, and hardening recommendations
    model: claude-sonnet-4-6
    priority: 3
    scope:
      owns: [scripts/audit.py]
      reads: [agent-runtime/, schemas/, .env.example]
      forbidden: [agent-runtime/storage/]
    keywords: [auth, jwt, password, secret, token, oauth, permission, credential, security, vulnerability, scan, hardening]

  - id: devops_agent
    name: DevOps & Deployment
    description: Owns requirements.txt, .gitignore, CLI packaging, and environment setup
    model: claude-haiku-4-5-20251001
    priority: 5
    scope:
      owns: [requirements.txt, .gitignore, .env.example, scripts/]
      reads: [agent-runtime/main.py]
      forbidden: [agent-runtime/storage/, schemas/]
    keywords: [install, package, deploy, environment, requirements, git, docker, ci]
```

---

**`schemas/agent-selection-rules.yaml`**
```yaml
version: "1.0"
scoring:
  signal_bonus_weight: 2.0
  keyword_weight: 1.0
  dependency_bonus: 0.5

rules:
  - agent_id: architect_agent
    signals_required: []
    signals_bonus: [has_multiple_languages, high_complexity, has_multiple_frameworks]
    signals_veto: []
    min_score: 0
    always_active: true
    rationale: "Always active — owns all structural decisions"

  - agent_id: orchestration_agent
    signals_required: []
    signals_bonus: [has_config_files, has_multiple_languages, high_complexity]
    signals_veto: []
    min_score: 0
    always_active: true
    rationale: "Always active — core runtime logic"

  - agent_id: repo_analyzer_agent
    signals_required: []
    signals_bonus: [has_multiple_languages, high_complexity, has_config_files]
    signals_veto: []
    min_score: 0
    always_active: true
    rationale: "Always active — drives the snapshot pipeline"

  - agent_id: registry_agent
    signals_required: []
    signals_bonus: [has_config_files]
    signals_veto: []
    min_score: 0
    always_active: true
    rationale: "Always active — owns YAML control-plane"

  - agent_id: routing_agent
    signals_required: []
    signals_bonus: [has_multiple_languages, high_complexity]
    signals_veto: []
    min_score: 0
    always_active: true
    rationale: "Always active — routes all tasks"

  - agent_id: testing_agent
    signals_required: []
    signals_bonus: [has_tests, high_complexity, has_ci]
    signals_veto: []
    min_score: 1
    always_active: false
    rationale: "Activate when tests exist or project is highly complex"

  - agent_id: security_agent
    signals_required: []
    signals_bonus: [has_auth, has_external_api, has_user_data]
    signals_veto: []
    min_score: 1
    always_active: false
    rationale: "Activate when auth, external APIs, or user data signals are detected"

  - agent_id: devops_agent
    signals_required: []
    signals_bonus: [has_docker, has_ci, has_makefile]
    signals_veto: []
    min_score: 1
    always_active: false
    rationale: "Activate when infrastructure signals detected"
```

---

**`schemas/agent-lifecycle-runtime-spec.yaml`**
```yaml
version: "1.0"

activation:
  min_score_to_activate: 1.0
  always_active_ids:
    - architect_agent
    - orchestration_agent
    - repo_analyzer_agent
    - registry_agent
    - routing_agent
  activation_log: agent-runtime/storage/logs/lifecycle.jsonl

deactivation:
  min_score_to_deactivate: 0.0   # score must reach 0 before deactivation is considered
  grace_cycles: 2                 # agent stays active 2 cycles after score drops below threshold
  never_deactivate_ids:
    - architect_agent
    - orchestration_agent
    - repo_analyzer_agent
    - registry_agent
    - routing_agent

handoff:
  strategy: explicit              # explicit | automatic
  require_summary: true
  summary_fields:
    - task_id
    - completed_steps
    - remaining_steps
    - context
    - receiving_agent_id
  handoff_log: agent-runtime/storage/logs/handoffs.jsonl

overlap_resolution:
  strategy: priority              # lower priority number wins
  tiebreak: agent_priority

state_persistence:
  active_agents_file: agent-runtime/storage/state/active-agents.json
  snapshot_dir: agent-runtime/storage/snapshots/
  runs_dir: agent-runtime/storage/runs/
  max_snapshots_retained: 50
  max_runs_retained: 100

events:
  reassess_triggers:
    - signal: has_auth
      appears: true
      activate: [security_agent]
    - signal: has_external_api
      appears: true
      activate: [security_agent]
    - signal: has_user_data
      appears: true
      activate: [security_agent]
    - signal: has_migrations
      appears: true
      activate: []
    - signal: has_docker
      appears: true
      activate: [devops_agent]
    - signal: has_ci
      appears: true
      activate: [devops_agent, testing_agent]
    - signal: has_tests
      appears: true
      activate: [testing_agent]
    - signal: high_complexity
      appears: true
      activate: [testing_agent]
```

### Step 5: Create `agent-runtime/` modules (22 Python files)

Key module responsibilities:
- `models.py` — all dataclasses; no logic
- `snapshot_builder.py` — calls detectors → normalizer → validator in sequence
- `snapshot_detectors.py` — walks repo, returns raw signal dict (has_auth, has_docker, has_migrations, etc.)
- `score_engine.py` — loads `agent-selection-rules.yaml`, computes float score per agent with reasoning
- `selector.py` — applies dependency_resolver + overlap_resolver, returns final `ActiveAgentSet`
- `lifecycle_manager.py` — diffs previous vs new active set, writes `storage/state/active-agents.json`, logs changes
- `task_router.py` — keyword + signal match between task string and active agents, returns `RoutingDecision`
- `runtime_controller.py` — full cycle method: `run_cycle(repo_path)` → snapshot → score → select → persist
- `main.py` — argparse with 5 subcommands:
  - `snapshot` — build + save snapshot for `--repo`
  - `select` — score + select active agents from last snapshot
  - `cycle` — full runtime loop (snapshot + select + persist)
  - `health` — show active agents, last snapshot summary, storage stats
  - `explain --agent <id>` — show scoring breakdown for a specific agent

### Step 6: Create supporting files

- `requirements.txt`: `PyYAML>=6.0`
- `.gitignore`: `agent-runtime/storage/`, `__pycache__/`, `*.pyc`, `.env`, `venv/`, `*.egg-info/`
- `.env.example`: `OPENCLAW_WEBHOOK_URL=`
- `STATUS.md`: stub
- `audit-log.md`: stub
- `scripts/audit.py`: scan `.py` files for hardcoded secrets patterns, `eval()`, `exec()`, `os.system()`
- `agent-runtime/storage/{snapshots,runs,logs,state}/.gitkeep`

---

## Files to Copy (Unchanged)
- `claude-setup/hooks/validate-bash.sh` → `.claude/hooks/validate-bash.sh`
- `claude-setup/hooks/protect-files.sh` → `.claude/hooks/protect-files.sh`
- `claude-setup/hooks/post-commit.sh` → `.claude/hooks/post-commit.sh`
- `claude-setup/hooks/session-init.sh` → `.claude/hooks/session-init.sh`
- `claude-setup/skills/compare-project/` → `.claude/skills/compare-project/`

## Files to Adapt (Replace Placeholders / Update Stack References)
- `claude-setup/CLAUDE.md` → `.claude/CLAUDE.md`
- `claude-setup/settings.json` → `.claude/settings.json`
- `claude-setup/rules/src/RULES.md` → `.claude/rules/src/RULES.md`
- `claude-setup/rules/tests/RULES.md` → `.claude/rules/tests/RULES.md`
- `claude-setup/skills/status/SKILL.md` → `.claude/skills/status/SKILL.md`
- `claude-setup/skills/test/SKILL.md` → `.claude/skills/test/SKILL.md`

## Files to Create New
- All 6 `.claude/agents/*.md`
- All `agent-runtime/*.py` (22 modules)
- All `agent-runtime/adapters/*.py` (3 files)
- All `agent-runtime/executors/*.py` (4 files)
- All `schemas/*.yaml` (5 files)
- `scripts/audit.py`
- `requirements.txt`, `.gitignore`, `.env.example`, `STATUS.md`, `audit-log.md`
- `agent-runtime/storage/**/.gitkeep` (4 directories)

---

## Verification

```bash
# 1. Structure check
find . -type f | sort

# 2. Python syntax check
python -m py_compile agent-runtime/main.py
python -m py_compile agent-runtime/models.py
# ... all modules

# 3. CLI help
python agent-runtime/main.py --help

# 4. Snapshot command (analyze this repo)
python agent-runtime/main.py snapshot --repo .

# 5. Select command (score + pick active agents)
python agent-runtime/main.py select

# 6. Full cycle
python agent-runtime/main.py cycle --repo .

# 7. Health check
python agent-runtime/main.py health

# 8. Explain a specific agent
python agent-runtime/main.py explain --agent security_agent
```

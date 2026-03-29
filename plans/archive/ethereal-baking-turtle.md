# Plan: Sequential Autonomous Execution — Items 1–4

## Context
User wants 4 items executed sequentially and autonomously:
1. Complete TASK-383 (OpenAPIHealthRoutes) through full pipeline
2. Close the last 1% AAWO coverage (15 uncovered lines in AAWO main.py)
3. New feature/task from the backlog
4. Commit the uncommitted CHANGELOG.md and metrics.jsonl

**Important ordering note:** Item 4 (commit dirty files) must happen *before* Item 1,
because TASK-383 will create new commits and we need a clean working tree first.
Execution order: 4 → 1 → 2 → 3.

---

## Item 4 (prerequisite): Commit Dirty Files
**Files:** `CHANGELOG.md` (staged, M), `solo_builder/metrics.jsonl` (unstaged, M)

Steps:
1. `git add CHANGELOG.md solo_builder/metrics.jsonl`
2. `git commit` — conventional commit: `chore: commit pending CHANGELOG and metrics updates`

---

## Item 1: TASK-383 — OpenAPIHealthRoutes
**Goal:** Add 11 new health endpoints to `tools/generate_openapi.py` OpenAPI spec.

### Research Phase
1. Read `tools/generate_openapi.py` — understand `build_spec()`, `_operation_id()`, existing route coverage
2. Identify the 11 health endpoints by reading:
   - `api/blueprints/health_detailed.py` — `/health/detailed`
   - `api/blueprints/core.py` — `/health`
   - All blueprints in `api/blueprints/` for any health-adjacent routes not yet in the spec
3. Overwrite `claude/HANDOFF_ARCHITECT.md` with TASK-383 research findings (replacing stale TASK-107 content)
4. Run `pwsh tools/research_extract.ps1`

### Architect Phase
5. Advance state: write `claude/HANDOFF_DEV.md` with:
   - List of exactly which 11 route entries to add
   - Schema for request/response bodies
   - `allowed_files.txt` update if needed
6. Run `pwsh tools/advance_state.ps1` (or equivalent) to move to `build` phase

### Dev Phase
7. Edit `tools/generate_openapi.py` — add the 11 health endpoint operations to `build_spec()`
8. Run `python tools/generate_openapi.py` to verify spec generates cleanly (no errors)

### Auditor Phase
9. Run `pwsh tools/audit_check.ps1` — must pass unittest-discover + prompt-regression
10. Commit: `feat: TASK-383 OpenAPIHealthRoutes — 11 health endpoints in generate_openapi.py`
11. Merge task branch to master (no-ff)

**Critical files:**
- `tools/generate_openapi.py` — main edit target
- `api/blueprints/health_detailed.py` — source of new routes
- `api/blueprints/core.py` — `/health` route
- `claude/HANDOFF_ARCHITECT.md` — research output
- `claude/STATE.json` — workflow state

---

## Item 2: AAWO 100% Coverage
**Goal:** Add tests to cover the 15 uncovered lines in AAWO `main.py`, reaching 100%.

AAWO main.py location: `C:\Users\Matt1\OneDrive\Desktop\Autonomous Agent Workflow Orchestrator\agent-runtime\main.py`

### Steps
1. Find existing AAWO test file for main.py — check `tests/test_main.py` or similar in the AAWO project
2. Run coverage to identify exact uncovered line numbers:
   `python -m pytest tests/ --cov=main --cov-report=term-missing -q` (from AAWO agent-runtime dir)
3. Identify which branches/lines are uncovered — likely candidates:
   - `if __name__ == "__main__": main()` guard
   - `cmd_select` output branches (outcome bias conditional)
   - `cmd_explain_all` terminal width fallback
   - Some `cmd_history` label branches
4. Add targeted unit tests — mock subprocess calls, import side effects, and sys.argv
5. Re-run coverage to confirm 100%
6. Commit in AAWO repo: `test: 100% coverage on main.py`

---

## Item 3: New Feature from Backlog
**Goal:** Pick the most impactful next task from TASK_QUEUE.md and implement it.

### Selection criteria
- TASK_QUEUE.md has tasks queued after TASK-383
- Prefer tasks that build on existing work with clear acceptance criteria
- Avoid tasks requiring external dependencies not yet installed

### Steps
1. Read `claude/TASK_QUEUE.md` — find the task immediately after TASK-383 (likely TASK-384 or similar)
2. Run `pwsh tools/start_task.ps1 -TaskId TASK-NNN -Goal "<goal>"` to initialize
3. Execute the standard RESEARCH → ARCHITECT → DEV → AUDITOR pipeline
4. Commit and merge to master

---

## Verification (end-to-end)
After all items complete:
- `python -m unittest discover` — all tests pass (1769+ tests, 0 failures)
- `git log --oneline -10` — shows 3–4 new commits on master
- AAWO coverage: `python -m pytest --cov=main` shows 100% for main.py
- `python tools/generate_openapi.py` — spec includes all health routes

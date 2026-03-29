# Plan: TASK-013 — Add claude/NEXT_ACTION.md Authoritative Action Contract

## Context

TASK-013 requests a single orchestrator-rendered `claude/NEXT_ACTION.md` file that gives agents one authoritative next-step contract, eliminating state inference from multiple files (TASK_QUEUE.md, TASK_ACTIVE.md, STATE.json, JOURNAL.md, orchestrator output text).

**Key finding from exploration:** The core feature is already implemented. `tools/claude_orchestrate.ps1` already writes `claude/NEXT_ACTION.md` (lines 180–227) using an inline template. `claude/AGENT_ENTRY.md` already references it at step #4. All role prompts already include it in Required reads.

All TASK-013 acceptance criteria are technically satisfied by the existing code. The one concrete deliverable still missing is `claude/templates/NEXT_ACTION_TEMPLATE.md` — the orchestrator checks for this file (lines 8, 212–214) but it doesn't exist; it silently falls back to the inline template. Creating it externalizes the template so it can be customized without touching the script.

The workflow state is `phase: triage`, `next_role: RESEARCH` for TASK-013. We need to advance it through all four role phases to formally close the task.

## Assumptions

- The project root is `C:/Users/Matt1/OneDrive/Desktop/Solo Builder/`
- `claude/templates/` directory does not yet exist
- `claude/prompts/` directory does not exist and is not required by acceptance criteria
- Verification is `pwsh tools/audit_check.ps1` which runs git-status, git-diff-stat, and optional unittest-discover
- No product code (`solo_builder/*`) is touched

## Files to Create or Modify

| File | Action | Reason |
|------|--------|--------|
| `claude/templates/NEXT_ACTION_TEMPLATE.md` | **Create** | Externalizes inline template; orchestrator already references this path |
| `claude/HANDOFF_ARCHITECT.md` | **Overwrite** | RESEARCH phase output (evidence + hypothesis for TASK-013) |
| `claude/HANDOFF_DEV.md` | **Overwrite** | ARCHITECT phase output (allowed files, acceptance criteria) |
| `claude/HANDOFF_AUDIT.md` | **Overwrite** | DEV phase output (implementation summary, verdict request) |
| `claude/STATE.json` | **Update** | Advance phase through triage → research → plan → build → verify → done |

Files NOT modified: `tools/claude_orchestrate.ps1`, `claude/AGENT_ENTRY.md`, `claude/CONTROL.md`, `claude/RULES.md`, any `solo_builder/*`.

## Implementation Steps

### Step 1 — Write HANDOFF_ARCHITECT.md (RESEARCH phase output)

Evidence:
- `claude_orchestrate.ps1` already writes `claude/NEXT_ACTION.md` (lines 180–227)
- `NEXT_ACTION.md` exists with correct content for TASK-013
- `AGENT_ENTRY.md` already lists `NEXT_ACTION.md` at read step #4
- `claude/templates/NEXT_ACTION_TEMPLATE.md` is referenced in the orchestrator (line 8) but missing — inline fallback is used

Hypothesis: All acceptance criteria are met except the external template file. Creating it is the only concrete DEV deliverable.

### Step 2 — Write HANDOFF_DEV.md (ARCHITECT phase output)

```
## Allowed changes
- claude/templates/NEXT_ACTION_TEMPLATE.md

## Files that must not be modified
- tools/claude_orchestrate.ps1
- solo_builder/*
- claude/STATE.json (except for phase advancement via orchestrator)

## Acceptance criteria
- claude/templates/NEXT_ACTION_TEMPLATE.md exists with correct {{PLACEHOLDER}} headings
- pwsh tools/claude_orchestrate.ps1 reads the external template (no error)
- claude/NEXT_ACTION.md content is unchanged from current output
- pwsh tools/audit_check.ps1 exits 0

## Verification commands
- pwsh tools/claude_orchestrate.ps1
- pwsh tools/audit_check.ps1
```

### Step 3 — Create claude/templates/NEXT_ACTION_TEMPLATE.md (DEV work)

Contents match the inline template in the orchestrator exactly, using the same `{{PLACEHOLDER}}` variables:

```markdown
# Next Action

## Task
{{TASK_ID}}

## Phase
{{PHASE}}

## Role
{{ROLE}}

## Status
{{STATUS}}

## Allowed operation
{{ALLOWED_OPERATION}}

## Required reads
{{REQUIRED_READS}}

## Required command
{{REQUIRED_COMMAND}}

## Commit expectation
{{COMMIT_EXPECTATION}}

## Rules
{{RULES}}
```

### Step 4 — Write HANDOFF_AUDIT.md and run audit_check.ps1 (AUDITOR work)

Run `pwsh tools/audit_check.ps1` and record result in HANDOFF_AUDIT.md.

### Step 5 — Advance STATE.json to done

Update phase to `done` and commit.

## Verification

```powershell
# Confirm template is read (no fallback)
pwsh tools/claude_orchestrate.ps1

# Confirm NEXT_ACTION.md output unchanged
Get-Content claude/NEXT_ACTION.md

# Confirm acceptance criteria pass
pwsh tools/audit_check.ps1

# Confirm no product files touched
git diff --stat
```

Expected: audit_check exits 0, git diff shows only `claude/templates/NEXT_ACTION_TEMPLATE.md` and handoff files.

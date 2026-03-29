# Agent & Agent Team Exhaustive Review — COMPLETE (2026-03-23)

## Status: ALL 7 RECOMMENDATIONS IMPLEMENTED

| Rec | Description | Status | How |
|-----|-------------|--------|-----|
| 1 | Pin models on 8 inherit agents | DONE | Plugin updates pinned all to sonnet |
| 2 | Downgrade 2 opus agents | DONE | pr-review-toolkit agents now sonnet |
| 3 | Wire debugger into fix-issue | DONE | fix-issue.md step 3 |
| 4 | Wire python-specialist (conditional) | DONE | fix-issue.md step 3, .py conditional |
| 5 | Add frontmatter to skill-creator agents | DONE | All 3 have name/model/description |
| 6 | Remove disabled code-simplifier | N/A | Never enabled; inert cache residue |
| 7 | Agent architecture memory file | DONE | memory/agent-architecture.md |

## Context

Matt has 27 agent definitions across 4 hand-crafted agents and 8 plugins (6 enabled, 2 disabled). These agents are organized into 4 distinct orchestration pipelines plus ad-hoc dispatch. The setup has grown organically through plugin installs, creating name collisions, model cost exposure, and underutilized agents that need attention.

---

## Full Inventory (27 agents)

### Hand-Crafted (`~/.claude/agents/`) — Always active

| # | Agent | Model | Tools | Background | Dispatched By |
|---|-------|-------|-------|------------|---------------|
| 1 | code-reviewer | sonnet-4-6 | Read,Grep,Glob,Bash | no | review-pr.md, code-review skill, post-edit hook |
| 2 | debugger | sonnet-4-6 | Read,Edit,Bash,Grep,Glob | no | **manual only** |
| 3 | python-specialist | haiku-4-5 | Read,Edit,Bash,Grep,Glob | no | **manual only** |
| 4 | researcher | haiku-4-5 | Read,Grep,Glob,Bash | yes | fix-issue.md, explain-code.md |

### feature-dev (ENABLED) — 3 agents

| # | Agent | Model | Color | Role |
|---|-------|-------|-------|------|
| 5 | code-explorer | sonnet | yellow | Traces execution paths |
| 6 | code-architect | sonnet | green | Designs feature architecture |
| 7 | **code-reviewer** | sonnet | red | Confidence-scored review (≥80) |

### hookify (ENABLED) — 1 agent

| # | Agent | Model | Color | Role |
|---|-------|-------|-------|------|
| 8 | conversation-analyzer | **inherit** | yellow | Finds behaviors to prevent with hooks |

### plugin-dev (ENABLED) — 3 agents

| # | Agent | Model | Color | Role |
|---|-------|-------|-------|------|
| 9 | agent-creator | sonnet | magenta | Creates new agent .md files |
| 10 | plugin-validator | **inherit** | yellow | Validates plugin structure |
| 11 | skill-reviewer | **inherit** | cyan | Reviews skill quality |

### pr-review-toolkit (ENABLED) — 6 agents

| # | Agent | Model | Color | Role |
|---|-------|-------|-------|------|
| 12 | **code-reviewer** | **opus** | green | Project guideline adherence |
| 13 | code-simplifier | **opus** | — | Simplifies code for clarity |
| 14 | comment-analyzer | **inherit** | green | Comment accuracy review |
| 15 | pr-test-analyzer | **inherit** | cyan | Test coverage analysis |
| 16 | silent-failure-hunter | **inherit** | yellow | Finds silent failures |
| 17 | type-design-analyzer | **inherit** | pink | Type design quality |

### skill-creator (ENABLED) — 3 agents

| # | Agent | Model | Frontmatter | Role |
|---|-------|-------|-------------|------|
| 18 | analyzer | **none** | **MISSING** | Post-hoc comparison analysis |
| 19 | comparator | **none** | **MISSING** | Blind output comparison |
| 20 | grader | **none** | **MISSING** | Expectation grading |

### superpowers (ENABLED) — 1 agent

| # | Agent | Model | Role |
|---|-------|-------|------|
| 21 | **code-reviewer** | **inherit** | Reviews against plan + coding standards |

### Disabled plugins (NOT enabled) — 6 agents

| # | Agent | Plugin | Model | Status |
|---|-------|--------|-------|--------|
| 22 | agent-sdk-verifier-py | agent-sdk-dev | sonnet | Disabled |
| 23 | agent-sdk-verifier-ts | agent-sdk-dev | sonnet | Disabled |
| 24 | code-simplifier | code-simplifier | opus | Disabled (duplicate of #13) |
| 25 | code-reviewer | coderabbit | unset | Disabled (requires external CLI) |
| 26 | skill-creator | sentry | unset | Disabled |
| 27 | skill-updater | sentry | unset | Disabled |

---

## Agent Teams / Orchestration Pipelines

### 1. feature-dev Pipeline (7 phases)
```
Phase 2: code-explorer x2-3 (parallel) → context gathering
Phase 4: code-architect x2-3 (parallel) → architecture design
Phase 6: code-reviewer x3 (parallel) → quality review
```
**Max agents per run: 9** | All sonnet

### 2. pr-review-toolkit (conditional dispatch)
```
Always:        code-reviewer (opus)
If tests:      pr-test-analyzer (inherit)
If comments:   comment-analyzer (inherit)
If errors:     silent-failure-hunter (inherit)
If types:      type-design-analyzer (inherit)
After review:  code-simplifier (opus)
```
**Max agents per run: 6** | 2 opus + 4 inherit

### 3. superpowers SDD Loop (sequential)
```
implementer → spec-reviewer (loop) → code-quality-reviewer → sdd-final-reviewer
```
**Agents per task: 4** | All inherit

### 4. superpowers Parallel Dispatch
```
N general-purpose agents for independent problems (all parallel)
```

---

## Assessment

### Strengths
- **Pipeline architecture is excellent** — parallel explorers → parallel architects → parallel reviewers is the right shape
- **pr-review-toolkit specialization** — 6 agents each doing one thing well beats one monolithic reviewer
- **researcher is perfectly positioned** — haiku, background, read-only, dispatched by 2 skills
- **Quality gate hook** catches unverified Agent tool calls (quality-gate.py)

### Critical Issues

#### Issue 1: 5× code-reviewer Name Collision
**Agents #1, #7, #12, #21, #25** all share the name `code-reviewer`. When Claude resolves agent names:
- Plugin agents are scoped to their plugin context (dispatched via plugin commands/skills)
- Global agents (`~/.claude/agents/`) are the fallback
- But skills like `review-pr.md` that call "code-reviewer" by name may resolve unpredictably

**Risk**: You think you're getting the opus pr-review-toolkit reviewer, but you might be getting your sonnet global one — or vice versa.

#### Issue 2: Uncontrolled Model Inheritance (8 agents)
Agents #8, #10, #11, #14, #15, #16, #17, #21 use `model: inherit`. In a DEEP task context (opus parent), ALL become opus simultaneously. A pr-review-toolkit run could spawn 4 opus agents + 2 explicit opus = **6 opus invocations** for a single PR review.

**Cost impact**: Opus is ~5× more expensive per token than sonnet. A 6-opus PR review costs ~$0.30-0.60 vs ~$0.06-0.12 with all-sonnet.

#### Issue 3: debugger and python-specialist Are Dead Weight
Both are well-written agents that **never fire automatically**. No hook, skill, or command dispatches them. On a Windows machine where Python encoding issues are documented and recurring, this is a gap.

#### Issue 4: Duplicate code-simplifier
Agent #13 (pr-review-toolkit, opus, enabled) and #24 (standalone plugin, opus, disabled) have **identical system prompts**. The disabled one is pure bloat.

#### Issue 5: skill-creator Sub-Agents Lack Frontmatter
Agents #18-20 (analyzer, comparator, grader) have no YAML frontmatter — no name, no model pin, no tools declaration. They work because the skill-creator workflow passes them as raw prompts, but they're fragile and non-standard.

### Minor Issues
- pr-review-toolkit's code-reviewer (#12) and code-simplifier (#13) at **opus** for routine pattern-matching tasks (guideline checking, clarity simplification) is overkill
- No observability — nothing monitors whether agents are performing well or degrading over time

---

## Recommendations (Ranked by Impact)

### Rec 1: Pin Explicit Models on All "inherit" Agents
**Impact: HIGH | Effort: LOW | Risk: NONE**

This is pure cost protection with zero functional change. Replace `model: inherit` with explicit pins:

| Agent | Current | Pin To | Rationale |
|-------|---------|--------|-----------|
| conversation-analyzer (#8) | inherit | sonnet | Pattern-matching task |
| plugin-validator (#10) | inherit | sonnet | Structure validation |
| skill-reviewer (#11) | inherit | sonnet | Quality assessment |
| comment-analyzer (#14) | inherit | sonnet | Comment checking |
| pr-test-analyzer (#15) | inherit | sonnet | Coverage analysis |
| silent-failure-hunter (#16) | inherit | sonnet | Error pattern detection |
| type-design-analyzer (#17) | inherit | sonnet | Type analysis |
| superpowers code-reviewer (#21) | inherit | sonnet | Plan alignment check |

**Files to modify**: 8 agent .md files in plugin cache directories

### Rec 2: Downgrade pr-review-toolkit's opus Agents to sonnet
**Impact: HIGH | Effort: LOW | Risk: LOW**

The code-reviewer (#12) does guideline compliance checking. The code-simplifier (#13) does clarity refactoring. Neither requires opus-level reasoning.

| Agent | Current | Change To |
|-------|---------|-----------|
| pr-review-toolkit code-reviewer | opus | sonnet |
| pr-review-toolkit code-simplifier | opus | sonnet |

**Files**: 2 agent .md files in pr-review-toolkit plugin

### Rec 3: Wire debugger into fix-issue.md
**Impact: MEDIUM | Effort: LOW | Risk: LOW**

`fix-issue.md` already dispatches `researcher` in step 2. Add debugger as step 2b:
```
2. Research: Use the researcher agent to find relevant files
2b. Debug: Use the debugger agent for root cause analysis on the found code
```

**File**: `~/.claude/skills/fix-issue.md`

### Rec 4: Wire python-specialist into fix-issue.md (conditional)
**Impact: MEDIUM | Effort: LOW | Risk: LOW**

Add a conditional in fix-issue.md:
```
2c. If the issue involves .py files, also dispatch the python-specialist agent
```

**File**: `~/.claude/skills/fix-issue.md`

### Rec 5: Add Frontmatter to skill-creator Sub-Agents
**Impact: LOW | Effort: LOW | Risk: NONE**

Add minimal frontmatter to analyzer.md, comparator.md, grader.md:
```yaml
---
name: analyzer  # (or comparator/grader)
model: sonnet
description: <current role description>
---
```

**Files**: 3 agent .md files in skill-creator plugin

### Rec 6: Remove Disabled Duplicate code-simplifier Plugin
**Impact: LOW | Effort: TRIVIAL | Risk: NONE**

The standalone `code-simplifier` plugin (#24) is disabled and identical to pr-review-toolkit's (#13). Remove it from installed plugins.

### Rec 7: Document the Name Collision Reality (no rename — these are plugin-managed)
**Impact: MEDIUM | Effort: LOW | Risk: NONE**

Since plugin agents are in the cache directory and managed by the plugin system, renaming them would be overwritten on plugin updates. Instead, document the collision in a memory file so future sessions understand which code-reviewer fires in which context:

- **Global `code-reviewer`** → fires from `review-pr.md` skill, `code-review` skill, and direct "use the code-reviewer agent" requests
- **feature-dev `code-reviewer`** → fires only within the feature-dev pipeline (scoped to plugin)
- **pr-review-toolkit `code-reviewer`** → fires only within review-pr pipeline (scoped to plugin)
- **superpowers `code-reviewer`** → fires only within SDD loop (scoped to plugin)

**File**: New memory file `~/.claude/projects/C--Users-Matt1/memory/agent-architecture.md`

---

## Proposed Ideal State

```
GLOBAL AGENTS (~/.claude/agents/)
  code-reviewer (sonnet) ─── post-edit hook, review-pr skill, code-review skill
  debugger (sonnet) ──────── fix-issue skill (NEW), manual
  python-specialist (haiku) ─ fix-issue skill conditional (NEW), manual
  researcher (haiku, bg) ──── fix-issue, explain-code

PIPELINES
  feature-dev:        explorer×3 → architect×3 → reviewer×3 (all sonnet)
  pr-review-toolkit:  6 agents, all pinned to sonnet (was 2 opus + 4 inherit)
  superpowers SDD:    implementer → spec-reviewer → quality-reviewer → final-reviewer (all sonnet)
  superpowers parallel: N general-purpose agents

COST PROFILE (per PR review, all 6 agents)
  Before: up to 6 opus = ~$0.30-0.60
  After:  6 sonnet     = ~$0.06-0.12
```

---

## Implementation Sequence

1. **Pin models on 8 inherit agents** (Rec 1) — no functional change, pure cost protection
2. **Downgrade 2 opus agents** (Rec 2) — test one PR review to confirm quality holds
3. **Wire debugger + python-specialist into fix-issue.md** (Recs 3-4) — test on a real issue
4. **Add frontmatter to 3 skill-creator agents** (Rec 5) — trivial
5. **Remove disabled code-simplifier plugin** (Rec 6) — trivial cleanup
6. **Create agent-architecture memory file** (Rec 7) — document the collision landscape

## Verification

- Run `/pr-review-toolkit:review-pr` on a real PR and confirm all 6 agents dispatch with sonnet
- Run `fix-issue` on a GitHub issue involving .py files — confirm debugger and python-specialist fire
- Check `~/.claude/audit-log.md` cost entries before and after to verify cost reduction

## Critical Files

- `~/.claude/agents/*.md` — 4 hand-crafted agents (no changes needed)
- `~/.claude/skills/fix-issue.md` — add debugger + python-specialist dispatch
- `~/.claude/plugins/cache/.../pr-review-toolkit/.../agents/*.md` — 6 agents to pin/downgrade
- `~/.claude/plugins/cache/.../superpowers/.../agents/code-reviewer.md` — pin to sonnet
- `~/.claude/plugins/cache/.../hookify/.../agents/conversation-analyzer.md` — pin to sonnet
- `~/.claude/plugins/cache/.../plugin-dev/.../agents/*.md` — 2 agents to pin
- `~/.claude/plugins/cache/.../skill-creator/.../agents/*.md` — 3 agents to add frontmatter

## Important Caveat

Plugin cache files (`~/.claude/plugins/cache/...`) may be overwritten on plugin updates. Model pin changes there are potentially ephemeral. Long-term solutions:
- Check if plugins support user-level overrides (e.g., a `.claude/agent-overrides/` directory)
- File feature requests for plugins to respect user model preferences
- Accept the maintenance cost of re-pinning after updates (low frequency)

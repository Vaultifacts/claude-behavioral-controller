# Plan: Idea Brainstormer Sub-Agent

## Context
The user wants to be able to prompt Claude to autonomously brainstorm app, automation, side project, and business ideas — on demand, with scoring and ranked output — using the same sub-agent pattern already established in the project.

This adds a new sub-agent (`claude-idea-brainstormer/`) alongside the existing 7, and registers it in `CLAUDE.md` (v2.7).

---

## Approved Idea Types (confirmed by user)
1. App / SaaS ideas
2. Automation / workflow ideas
3. Side project / indie maker ideas
4. Business / startup concepts

Any new types discovered during generation must be surfaced as proposals — NOT silently included.

---

## Files to Create

### `claude-idea-brainstormer/PROCESS.md`
The governing instruction file for the agent. Structure:

**Role block:**
- Purpose: divergent ideation engine — generates 20–30 ideas, scores them, returns ranked list with descriptions
- Trigger: `"brainstorm ideas"` (open-ended → asks 2 scoping questions first) OR `"brainstorm ideas for [X]"` (directed → skips to generation)
- Output: `Idea-Candidates.md`
- Non-negotiable: no code, no implementation — ideas only; stick to 4 approved types; surface new types as proposals

**Scoping questions (open-ended trigger only):**
1. What domain, persona, problem space, or theme should I focus on? (Leave blank = free-form across all domains)
2. Any constraints? (solo-buildable, no-code only, specific platform, specific budget tier, etc.)

**Scoring rubric (4 dimensions, 1–5 each, max 20):**
| Dimension | What it measures |
|-----------|-----------------|
| Market Pull | Proven demand — painkiller vs. vitamin; existing search/community signals |
| Buildability | Feasible V1 for solo maker / small team in ≤ 3 months |
| Revenue Clarity | Monetization model is obvious, proven, and early-revenue-possible |
| Novelty | Meaningfully differentiated from what already exists |

**Session protocol (6 steps):**
1. If no seed → ask 2 scoping questions; wait for response; then proceed. If seed provided → skip to Step 2.
2. Generate 20–30 ideas spanning all 4 approved types (aim for ≥ 3 per type; free-form can skew toward what's richest)
3. Score each idea on 4 dimensions (1–5); compute composite (sum out of 20)
4. Sort by composite score descending; ties broken by Market Pull
5. Write concept card per idea (see output format below)
6. Write to `Idea-Candidates.md` (append as a new session, not overwrite)

**Concept card format per idea:**
```
### [Rank]. [Idea Name] — [Score]/20
**Type:** [App/SaaS | Automation | Side Project | Business]
**In one sentence:** [Value proposition]
**Who it's for:** [Target user / persona]
**How it makes money:** [Revenue model]
**The core insight:** [Gap it fills or why it works]
**Biggest risk:** [Primary kill condition]
| Market Pull | Buildability | Revenue Clarity | Novelty |
|-------------|-------------|-----------------|---------|
| [1–5]       | [1–5]       | [1–5]           | [1–5]   |
```

**New type discovery protocol:**
- If generation naturally produces ideas that don't fit the 4 approved types, list them in a "Proposed New Idea Types" section at the end of the session — do NOT include them in the scored list without approval.

**Files table** (bottom of PROCESS.md)

---

### `claude-idea-brainstormer/Idea-Candidates.md`
Output template — status: NOT STARTED until first session.

Template structure:
- Header with project/session metadata
- Status line: `NOT STARTED — invoke with "brainstorm ideas" or "brainstorm ideas for [X]"`
- Session log format: each session is a new dated section, appended

---

## Files to Modify

### `CLAUDE.md` → v2.7
1. Add row to "Specialized Sub-Agents" table:
   - Agent: Idea Brainstormer
   - Directory: `./claude-idea-brainstormer/`
   - Trigger: `"brainstorm ideas"` or `"brainstorm ideas for [X]"`
   - Purpose: Generates 20–30 ideas (app, automation, side project, business), scores on 4 dimensions, returns ranked list with concept cards
2. Add trigger phrase to MEMORY.md
3. Bump Evolution Log to v2.7

### `MEMORY.md`
Add trigger phrase: `"brainstorm ideas"` / `"brainstorm ideas for [X]"` → `claude-idea-brainstormer/`

### `ai-academy-design/09-Iteration-Log.md`
Add entry for this pass (per standing rule: log all changes in same pass).

---

## Summary of New Files

| File | Purpose |
|------|---------|
| `claude-idea-brainstormer/PROCESS.md` | Agent governing rules, scoring rubric, session protocol |
| `claude-idea-brainstormer/Idea-Candidates.md` | Output template (populated per session) |

Total: 2 new files + updates to CLAUDE.md, MEMORY.md, 09-Iteration-Log.md.

---

## Verification
After implementation:
1. User can type `"brainstorm ideas"` → Claude asks 2 scoping questions → generates scored ranked list
2. User can type `"brainstorm ideas for solo founders who hate meetings"` → Claude skips to generation immediately
3. Output lands in `Idea-Candidates.md` as an appended session
4. New/unapproved idea types surface as proposals, not silent inclusions
5. CLAUDE.md Specialized Sub-Agents table includes the new row
6. 09-Iteration-Log.md has the new entry

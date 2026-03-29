# Remaining VaultLister Conflicts with Global Settings

## Context
After fixing the 4 root causes, a deeper review of the project's `.claude/` configuration reveals additional conflicts with the global settings optimized yesterday. These affect cost, correctness, and behavior.

---

## Issue 1: Stale consistency-manifest.json (HIGH — blocks commits)

The manifest tracks counts that hooks verify:
```json
{
  "deny_patterns": 38,
  "validate_bash_patterns": 36
}
```

Reality after our fixes:
- deny_patterns: 38 → **27** (we removed 10 redundant rules + the hook changes reduced it from original 37)
- validate_bash_patterns: **0** (we deleted `.claude/hooks/validate-bash.sh`)

The `.husky/pre-commit` hook runs consistency checks against this manifest. **Commits will fail** in vaultlister sessions until the manifest is updated.

**Fix:** Update `consistency-manifest.json` with correct counts.

---

## Issue 2: QA agents inherit `opusplan` model (MEDIUM — expensive)

6 QA agents have **no `model:` field** in their frontmatter:
- `qa-core-product.md`, `qa-data-systems.md`, `qa-environment-quality.md`
- `qa-infrastructure-delivery.md`, `qa-reliability.md`, `qa-security.md`

Without a model field, they inherit the global `model: "opusplan"` — using **Opus** in plan mode. These are QA audit agents that read code and report findings; Sonnet is more than sufficient.

Global agents (debugger, code-reviewer, researcher, python-specialist) all specify explicit models. The project's 8 specialized agents (Backend, Frontend-UI, etc.) all specify `model: sonnet`. Only the 6 QA agents are missing it.

**Fix:** Add `model: sonnet` to all 6 QA agent frontmatter blocks.

---

## Issue 3: Haiku agent missing `effort: low` (LOW — wasted tokens)

`NoCode-Workflow.md` uses `model: haiku` but no `effort: low`. With global `effortLevel: "high"`, this runs Haiku at max effort — wasted tokens for a no-code workflow agent.

Yesterday's session specifically noted: "Should add effort: low to both haiku agents to override the global setting." Global agents (researcher, python-specialist) already have `effort: low`.

**Fix:** Add `effort: low` to `NoCode-Workflow.md` frontmatter.

---

## Issue 4: CLAUDE.md compact instruction conflicts with global (LOW)

CLAUDE.md says:
> Run `/compact` at 70% context usage; `/clear` at 85%

But global settings have:
- `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE=90` — autocompact at 90%
- `context-watch` hook — notification at 70%, message to Claude at 90%
- Pre-compact snapshot hook fires automatically

The 70% instruction is unnecessarily early and conflicts with the global autocompact threshold. It wastes context by compacting prematurely.

**Fix:** Update the CLAUDE.md line to defer to global autocompact:
> Do not manually compact — global autocompact fires at 90%. Save findings to memory before compacting.

---

## Files Modified

| File | Action |
|------|--------|
| `.claude/consistency-manifest.json` | Update deny_patterns: 27, validate_bash_patterns: 0 |
| `.claude/agents/qa-core-product.md` | Add `model: sonnet` to frontmatter |
| `.claude/agents/qa-data-systems.md` | Add `model: sonnet` to frontmatter |
| `.claude/agents/qa-environment-quality.md` | Add `model: sonnet` to frontmatter |
| `.claude/agents/qa-infrastructure-delivery.md` | Add `model: sonnet` to frontmatter |
| `.claude/agents/qa-reliability.md` | Add `model: sonnet` to frontmatter |
| `.claude/agents/qa-security.md` | Add `model: sonnet` to frontmatter |
| `.claude/agents/NoCode-Workflow.md` | Add `effort: low` to frontmatter |
| `CLAUDE.md` | Update compact instruction (line ~181) |

## Verification
1. `python -c "import json; d=json.load(open('...')); print(d['deny_patterns'], d['validate_bash_patterns'])"` → expect 27, 0
2. `head -5` each QA agent → confirm `model: sonnet`
3. `head -6 NoCode-Workflow.md` → confirm `effort: low`
4. `grep -n compact CLAUDE.md` → confirm updated instruction

---
name: code-review
description: Use when the user explicitly asks to review code or audit a file — not after every edit, not for PRs, not for full project audits.
---

# Skill: Code Review

## Trigger
Use when the user **explicitly** asks to review code or audit a file. Do NOT auto-trigger after every edit — only fire when review is explicitly requested.

**Do NOT use this skill for:**
- PR review with a PR number → use `review-pr` (lightweight) or `pr-review-toolkit:review-pr` (deep)
- Full project audit → use `/audit`
- Post-edit automatic review → that's the `code-reviewer` agent, not this skill

## Behavior

1. **Read first** — always read the full file(s) before commenting. Never review code you haven't seen.

2. **Severity tiers**
   - `CRITICAL` — will cause bugs, data loss, security issues, or crashes
   - `WARNING` — likely to cause problems under real conditions
   - `INFO` — style, clarity, or minor improvement suggestions

3. **What to check**
   - Correctness: logic, edge cases, off-by-one, null/undefined handling
   - Security: injection, secrets in code, insecure defaults, missing auth checks
   - Performance: N+1 queries, unnecessary re-renders, unbounded loops
   - Maintainability: naming, dead code, commented-out stubs, magic numbers
   - Type safety: missing types, unsafe casts, implicit any (TypeScript)

4. **What NOT to do**
   - Do not refactor unless asked
   - Do not rewrite working code
   - Do not add comments or docstrings unless asked
   - Do not change formatting unless it causes a bug

## Output Format

```
## Review: <filename or PR title>

### CRITICAL
- `file.ts:42` — SQL query built via string concat; use parameterized queries

### WARNING
- `utils.py:18` — No timeout on external HTTP call; will hang indefinitely

### INFO
- `index.js:5` — `var` should be `const`; no reassignment occurs

**Verdict:** [Ready to merge | Needs fixes | Major issues]
```

## Related
- Agent: `code-reviewer` — for automated post-edit review
- Command: `/review` — user-invocable shortcut

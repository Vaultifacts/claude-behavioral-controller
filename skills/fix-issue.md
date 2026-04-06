---
name: fix-issue
description: Use when given a GitHub issue number to fix — researches, implements, tests, commits, and opens a PR end-to-end.
disable-model-invocation: true
---

Fix GitHub issue: $ARGUMENTS

Follow these steps:

1. **Read the issue**: `gh issue view $ARGUMENTS` to understand requirements and acceptance criteria
2. **Research**: Use the researcher agent to find all relevant files — search for keywords from the issue title
3. **Debug**: Dispatch the debugger agent to perform root cause analysis on the code identified by the researcher — do NOT reason about root cause inline. If the issue involves `.py` files, also dispatch the python-specialist agent for encoding/Windows-specific diagnosis. The issue reporter's proposed fix is a hypothesis, not a confirmed root cause.
4. **Plan**: Briefly explain what you'll change and why before touching any code
5. **Implement**: Make the minimal change needed to fix the issue — no scope creep
6. **Test**: Run the project's test command (check package.json scripts). If no tests exist, manually verify the fix
7. **Lint**: Run `npx eslint` or equivalent if available
8. **Commit**: `git add <specific files>` then `git commit -m "[AUTO] fix: <description>"`
   - Reference the issue: `Closes #$ARGUMENTS` in the commit body
9. **PR**: `gh pr create` with title matching issue title and body describing the fix

If any step fails, stop and report what went wrong rather than continuing.

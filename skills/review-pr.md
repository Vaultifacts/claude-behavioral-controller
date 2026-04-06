---
name: review-pr
description: Use when asked to review a pull request by PR number — lightweight single-pass. For deep multi-agent review, use pr-review-toolkit:review-pr instead.
disable-model-invocation: true
---

Review pull request: $ARGUMENTS

Follow these steps:

1. **Get the diff**: `gh pr diff $ARGUMENTS`
2. **Read PR description**: `gh pr view $ARGUMENTS` for context on what/why
3. **Analyze** using the code-reviewer agent — focus on:
   - Security vulnerabilities (injection, exposed secrets, unvalidated input)
   - Logic errors or edge cases not handled
   - Performance issues (N+1 queries, unnecessary loops)
   - Missing error handling
   - Test coverage for new logic
4. **Format review** as:
   ```
   ## Review of PR #$ARGUMENTS

   ### Critical Issues (must fix before merge)
   - [file:line] Issue description

   ### Suggestions (optional but recommended)
   - [file:line] Suggestion

   ### Overall
   [Approve/Request Changes/Comment] — [one sentence summary]
   ```
5. **Post review**: `gh pr review $ARGUMENTS --comment --body "..."`
   - Use `--approve` if no issues, `--request-changes` if critical issues found

If no PR number given, review the current branch's open PR.

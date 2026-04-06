---
name: hotfix
description: Use when a bug needs patching in production immediately — hotfix, emergency fix, patch without waiting for main, or cherry-pick to a release branch.
---

> **Iron rule**: Verify the root cause independently before writing any code. Do NOT implement a fix based on the reporter's diagnosis alone — verify by reading the relevant code path and all call sites yourself.

Hotfix for: $ARGUMENTS

## Step 1 — Identify the release to patch

```bash
git tag --sort=-version:refname | head -10
git log --oneline -5 origin/main origin/master 2>/dev/null
```

Determine:
- What is the current production version/tag? (e.g., `v2.3.1`)
- Is `main` deployable right now, or is there unreleased work on it?
- If main is clean → hotfix can branch from main. If not → branch from the release tag.

Ask if unclear: "Should I branch from `main` or from a specific release tag?"

## Step 2 — Create the hotfix branch

**From a tag (safest — exactly what's in prod):**
```bash
git fetch --tags
git checkout -b hotfix/v2.3.2 v2.3.1
```

**From main (if main == prod):**
```bash
git checkout -b hotfix/issue-description main
```

Branch naming: `hotfix/` prefix + short description (e.g., `hotfix/null-check-payment-handler`).

## Step 3 — Diagnose the bug

Use `superpowers:systematic-debugging` to find the root cause before writing any code.

The reporter's description is a starting point, not a conclusion. Before writing code: read the file at the reported line, trace the full call path, and confirm whether the same issue exists at other call sites. If the scope is larger than the reporter described, stop and escalate.

Constraints for a hotfix:
- Fix ONLY the reported issue — no refactoring, no "while I'm here" changes
- Change as few files as possible
- Prefer defensive additions (null checks, guards) over structural changes

## Step 4 — Implement the minimal fix

Make the change. Then verify the diff is scoped:
```bash
git diff
```

If the diff touches more than 2-3 files, reconsider — is the scope too broad for a hotfix?

## Step 5 — Test

Run the test suite scoped to the changed files:
```bash
# Run tests covering the changed path
```

If no tests exist for the fixed path, write one targeted test before committing — even one assertion is enough to prevent regression. 'Tests take too long' is not acceptable — an incorrect hotfix extends downtime. If the test suite is broken for unrelated reasons, see Abort criteria.

## Step 6 — State the rollback procedure

Before committing, write out the rollback:
```
Rollback: git revert <commit> && git push origin main
# or: git checkout v<previous-tag> && deploy
```

If you cannot state the rollback, do not proceed. A deployed fix that cannot be quickly reverted is worse than the original bug.

## Step 7 — Commit and tag

```bash
git add <specific-files>
git commit -m "[AUTO] fix: <description of the bug and fix>

Closes #<issue> (if applicable)
Hotfix for v<version>"

# Tag the hotfix release
git tag v2.3.2
```

Increment the patch version (semver: MAJOR.MINOR.**PATCH**).

## Step 8 — Merge back to main

A hotfix that isn't merged back to main will be lost in the next release:

```bash
git checkout main
git merge hotfix/v2.3.2 --no-ff -m "chore: merge hotfix v2.3.2 into main"
```

If there are conflicts merging back, resolve them carefully — main may have diverged.

## Step 9 — Push and deploy

```bash
git push origin main
git push origin v2.3.2  # push the tag
```

Then open a PR if required by the project's deployment process, or trigger the deploy directly.

## Step 10 — Report

```
## Hotfix Complete

**Version:** v2.3.2 (patched from v2.3.1)
**Branch:** hotfix/v2.3.2 (merged into main)
**Files changed:** [list]
**Fix:** [one-sentence description]
**Merged back to main:** yes / no (if no, explain why)
**Tag pushed:** yes / no
**Deploy triggered:** yes / no / manual
```

## Abort criteria

Stop and escalate if:
- The fix requires touching more than ~5 files
- The root cause is architectural (can't be fixed with a small patch)
- You can't reproduce the issue locally
- Tests are failing for unrelated reasons — don't deploy on a broken base

## Rationalizations

| Phrase | Why it fails |
|--------|-------------|
| "The bug is obvious" | Obvious to the reporter ≠ verified by you. Read the code path. |
| "We're losing $X/minute" | An incorrect fix doubles downtime. Diagnose first — it takes 2 minutes. |
| "Tests take too long" | Run targeted tests for the changed path. The full suite can run in CI. |
| "Just push it" | State the rollback before pushing. Takes 30 seconds. |
| "The fix is one line" | One-line fixes can have multiple callers. Check all call sites. |
| "I'll write tests after" | Tests written after deployment are not regression guards — they just document the current state. |

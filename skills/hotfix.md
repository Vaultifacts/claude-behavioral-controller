---
name: hotfix
description: Production hotfix workflow — branch from the release tag, apply a minimal fix, and fast-track to merge. Use when asked to "hotfix", "patch production", "emergency fix", "fix prod without waiting for main", or "cherry-pick to release". Distinct from normal feature development — this prioritizes speed and minimal blast radius over code elegance.
---

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

Run the test suite:
```bash
# Run tests relevant to the changed files only if possible
```

At minimum, run tests that cover the fixed path. If no tests exist for the fix, write one targeted test before committing.

## Step 6 — Commit and tag

```bash
git add <specific-files>
git commit -m "[AUTO] fix: <description of the bug and fix>

Closes #<issue> (if applicable)
Hotfix for v<version>"

# Tag the hotfix release
git tag v2.3.2
```

Increment the patch version (semver: MAJOR.MINOR.**PATCH**).

## Step 7 — Merge back to main

A hotfix that isn't merged back to main will be lost in the next release:

```bash
git checkout main
git merge hotfix/v2.3.2 --no-ff -m "chore: merge hotfix v2.3.2 into main"
```

If there are conflicts merging back, resolve them carefully — main may have diverged.

## Step 8 — Push and deploy

```bash
git push origin main
git push origin v2.3.2  # push the tag
```

Then open a PR if required by the project's deployment process, or trigger the deploy directly.

## Step 9 — Report

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

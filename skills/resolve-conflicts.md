---
name: resolve-conflicts
description: Resolve git merge or rebase conflicts. Use when encountering conflict markers (<<<<<<<, =======, >>>>>>>), when "git merge", "git rebase", or "git cherry-pick" leaves conflicts, or when asked to "fix conflicts", "resolve merge conflicts", or "help with rebase". Distinct from superpowers:using-git-worktrees (which sets up isolation before work begins).
---

Resolve git conflicts in: $ARGUMENTS (or current repo if no argument given)

## Step 1 — Assess the situation

```bash
git status
git log --oneline --mergebase HEAD MERGE_HEAD 2>/dev/null || git log --oneline -5
```

Identify:
- Are we mid-merge, mid-rebase, or mid-cherry-pick?
- How many files have conflicts?
- What branches/commits are involved?

## Step 2 — Understand the intent of each side

For each conflicted file, read the full conflict context:
```bash
git diff --diff-filter=U
```

For each conflict block:
- **Ours (HEAD)**: what the current branch intended
- **Theirs (MERGE_HEAD / incoming)**: what the other branch intended
- **Base**: what both diverged from (use `git show :1:<file>` for the common ancestor)

Do NOT resolve blindly. If the intent is unclear, read the commit messages:
```bash
git log --oneline HEAD..MERGE_HEAD 2>/dev/null
git log --oneline MERGE_HEAD..HEAD 2>/dev/null
```

## Step 3 — Resolve each conflict

For each conflict block, choose the resolution strategy:

| Strategy | When to use |
|----------|-------------|
| **Take ours** | Their change is superseded by ours; ours is correct |
| **Take theirs** | Our change is outdated; theirs is correct |
| **Merge both** | Both changes are additive and compatible |
| **Rewrite** | Neither side is right as-is; write a combined version |

Apply the resolution directly using the Edit tool — remove all conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`).

After editing each file:
```bash
git add <file>
```

## Step 4 — Verify resolution

After all conflicts are marked resolved:

```bash
# Check no conflict markers remain
grep -r "<<<<<<\|=======\|>>>>>>>" --include="*.ts" --include="*.js" --include="*.py" --include="*.rs" --include="*.go" . 2>/dev/null | grep -v ".git/"
```

Run the test suite if one exists — a conflict resolution that breaks tests is not done.

## Step 5 — Complete the operation

**If mid-merge:**
```bash
git merge --continue
```

**If mid-rebase:**
```bash
git rebase --continue
```

**If mid-cherry-pick:**
```bash
git cherry-pick --continue
```

## Step 6 — If a conflict is too ambiguous

Stop on that file. Show the user:
```
## Conflict requires your input
File: path/to/file.ts

**Our version (HEAD):**
[code block]

**Their version (incoming):**
[code block]

**Context:** [what each commit was trying to do]

Which should win, or how should they be combined?
```

Do not guess on ambiguous conflicts — wrong resolutions are worse than pausing.

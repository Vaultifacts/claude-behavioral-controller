# Investigation & Fix: GitHub Issue Automation & Kanban Board

## Context
User set up automated issue creation and a kanban board at `https://github.com/users/Vaultifacts/projects/1/views/2`, but sees no issues and an empty board.

---

## Finding 1: Automated Issue Creation — Working as Designed

Two automation workflows exist and are correctly configured:

- **`auto-create-issue-on-ci-failure.yml`** — Creates issues when CI workflow fails
- **`deploy.yml` → `notify-failure` job** — Creates issues when deploy fails

**Why no issues?** All recent CI and Deploy runs have succeeded. The auto-create workflow runs but skips (status: `skipped`) because the `if: conclusion == 'failure'` condition isn't met. The custom labels (`ci-failure`, `automated`, `deploy-failure`) don't exist yet, confirming the issue-creation step has never fired.

**Verdict: No action needed.** The automation works — it just hasn't had a failure to report.

---

## Finding 2: Empty Kanban Board — Missing Auto-Add Workflow

**Problem:** No automation exists to populate the GitHub Projects board. The issue-creation workflows create issues but don't add them to any project. Specifically:
- No `actions/add-to-project` in any workflow
- No `addProjectV2ItemById` GraphQL mutations
- No `gh project item-add` commands

---

## Implementation Plan

### Step 1: Create `ADD_TO_PROJECT_TOKEN` repository secret (manual — user)

The `actions/add-to-project` action requires a token with `project` write scope. The default `GITHUB_TOKEN` does NOT have this permission for user-level projects.

User must create a **classic PAT** (or fine-grained token) with these scopes:
- `project` (full access to user Projects v2)
- `repo` (already likely granted)

Then add it as a repository secret named `ADD_TO_PROJECT_TOKEN`:
1. Go to https://github.com/settings/tokens → Generate new token (classic)
2. Select scope: `project`
3. Copy the token
4. Go to https://github.com/Vaultifacts/VaultLister-3.0/settings/secrets/actions → New repository secret
5. Name: `ADD_TO_PROJECT_TOKEN`, Value: the token

### Step 2: Create `.github/workflows/add-to-project.yml`

**File:** `.github/workflows/add-to-project.yml`

```yaml
name: Add to Project Board

on:
  issues:
    types: [opened, reopened]
  pull_request:
    types: [opened, reopened]

jobs:
  add-to-project:
    name: Add to VaultLister Kanban
    runs-on: ubuntu-latest
    steps:
      - uses: actions/add-to-project@v1.0.2
        with:
          project-url: https://github.com/users/Vaultifacts/projects/1
          github-token: ${{ secrets.ADD_TO_PROJECT_TOKEN }}
```

This will:
- Auto-add every new or reopened issue to the project board
- Auto-add every new or reopened PR to the project board
- Items appear in the default "No Status" column; user can drag to appropriate columns

### Step 3: Backfill existing closed issues (optional)

The 2 existing closed issues (#7, #8) won't be auto-added since the workflow only triggers on `opened`/`reopened`. If you want them on the board, manually add them via the project UI.

---

## Verification

1. After creating the secret and workflow file, push to `master`
2. Create a test issue: `gh issue create --title "Test: project board automation" --body "Testing auto-add to project board" --label "automated"`
3. Check the project board at https://github.com/users/Vaultifacts/projects/1/views/2 — the test issue should appear within ~30 seconds
4. Check the workflow run: `gh run list --workflow="Add to Project Board" --limit 1`
5. Close the test issue after verification: `gh issue close <number>`

---

## Files Modified
- `.github/workflows/add-to-project.yml` — **NEW** (auto-add issues/PRs to project board)

## Manual Steps Required (User)
- Create PAT with `project` scope
- Add `ADD_TO_PROJECT_TOKEN` repository secret
- Optionally: `gh auth refresh -s read:project` to allow CLI project queries

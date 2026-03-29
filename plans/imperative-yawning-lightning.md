# Plan: Draft PR Disposition & GitHub Infrastructure Improvements

## Context

Four draft PRs were created by a Claude GitHub agent. After exhaustive review:
- **PR #18** and **PR #19** have real value but need fixes before merge
- **PR #20** and **PR #21** are pure documentation (audit reports at repo root) with no code changes — should be closed
- PR #21 contains verified, actionable findings that should be implemented as real code changes

This plan covers: fixing and merging the good PRs, closing the bad ones, and implementing the real infrastructure gaps identified by PR #21's audit.

### Prerequisites (before starting execution)
1. **Clean working tree** — verified: only `.walkthrough-active` untracked. OK to proceed.
2. **Start dev server** — `bun run dev:bg` required before any `git push` (pre-push hook runs unit tests if DATABASE_URL is set; blocks push if server not running on PORT).
3. **Commit trailers** — The `commit-msg` hook (`.husky/commit-msg`) BLOCKS `fix:` and `feat:` commits without both `Notion-Skip:` (or `Notion-Done:`) AND `Verified:` trailers. `ci:` type is exempt. Every local commit must include these.
4. **Pre-push Notion checks** — pre-push hook also validates Sprint Board drift and Notion-Done audit for all commits between remote HEAD and local HEAD.

### Verified Pinned SHAs (from ci.yml and deploy-staging.yml on master)
These are the canonical pinned references used throughout the repo:
- `actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2`
- `oven-sh/setup-bun@0c5077e51419868618aeaa5fe8019c62421857d6 # v2.2.0`
- `actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd # v8`
- `github/codeql-action/*@v4` — SHA to be looked up during execution (latest v4 tag commit)

---

## Phase 1: Close PRs #20 and #21

**Action:** Close both PRs with explanatory comments via `gh pr close`.

### PR #20 (`claude/audit-github-actions-workflows`)
- Close with comment: "Closing — this PR adds a 792-line audit report at the repo root with no code changes. The audit concluded no issues exist, which contradicts findings in PR #21. The workflow architecture observations are noted and will be addressed in targeted implementation PRs where needed."

### PR #21 (`claude/audit-github-configuration-settings`)
- Close with comment: "Closing — this PR adds a 1,566-line [WIP] audit document at the repo root with no applied fixes. The real findings (missing CodeQL workflow, staging URL exposure, no deploy failure notifications) are being implemented as actual code changes directly. See commits on master."

---

## Phase 2: Fix and Merge PR #19 (CI Failure Issue Workflow)

**Branch:** `claude/setup-issue-creation-workflow`
**File:** `.github/workflows/auto-create-issue-on-ci-failure.yml`

### Prep: Rebase onto master
```bash
git fetch origin
git checkout claude/setup-issue-creation-workflow
git rebase origin/master
```

### Fix 1: Add missing step ID (BUG — runtime failure)
The "Create failure issue" step (the one containing `github.rest.issues.create`) has NO `id:` field. The Summary step at the end references `steps.create-failure-issue.outputs.issue_url`, which will be `undefined` at runtime.

**Fix:** Add `id: create-failure-issue` to the "Create failure issue" step, immediately after the `- name: Create failure issue` line and before the `if:` line.

### Fix 2: Add labels to created issues
The `github.rest.issues.create()` call has no `labels` parameter. Add `labels: ['ci-failure', 'automated']` to the create call so issues are filterable and identifiable as automated.

### Fix 3: Pin and upgrade action references
The workflow uses `actions/github-script@v7` in 4 places. The repo standard (from `deploy-staging.yml`) is:
```
actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd # v8
```
Replace all 4 occurrences of `actions/github-script@v7` with the SHA-pinned v8 reference.

### Merge Strategy
```bash
# Local fix commit needs trailers (commit-msg hook enforces on fix: type)
git add .github/workflows/auto-create-issue-on-ci-failure.yml
git commit -m "fix: add step ID, labels, and pin actions in auto-issue workflow

Notion-Skip: GitHub infrastructure cleanup — no Sprint Board item
Verified: grep confirms id: create-failure-issue present, all github-script refs pinned to v8 SHA"

git push origin claude/setup-issue-creation-workflow --force-with-lease
gh pr ready 19
gh pr merge 19 --squash --subject "[AUTO] fix(ci): add step ID, labels, and pin actions in auto-issue workflow"
```
Note: The squash-merge commit is created on GitHub's server (not locally), so the local commit-msg hook does not apply to the final merge commit. The `--subject` flag sets the squash commit title.

---

## Phase 3: Fix and Merge PR #18 (New Agent Definitions)

**Branch:** `copilot/add-specialized-agents`
**Files:** 3 new agents + modifications to 4 existing agents + CLAUDE.md + CONTRIBUTING.md

### Prep: Rebase onto master (now includes PR #19)
```bash
git checkout copilot/add-specialized-agents
git rebase origin/master
```
If conflicts arise in `memory/MEMORY.md` (likely, since it's session-managed), resolve by taking master's version — we're removing PR #18's MEMORY.md changes anyway (Fix 4).

### Fix 1: AES-256-CBC to AES-256-GCM in Marketplace-Integration.md

**File:** `.claude/agents/Marketplace-Integration.md` (new file on PR branch)

Two occurrences — verified from `git show` of the branch:
- **Line 14:** `Credential encryption/decryption (AES-256-CBC, in partnership with Security-Auth)` → change `AES-256-CBC` to `AES-256-GCM`
- **Line 65:** `AES-256-CBC encrypt all OAuth tokens before SQLite storage` → change to `AES-256-GCM (authenticated encryption) encrypt all OAuth tokens before SQLite storage`

### Fix 2: Update existing agents for AES-256-GCM consistency

Fix stale CBC references that exist on both master and the PR branch. Making these changes on the PR branch means they merge cleanly:

**`.claude/agents/Backend.md` line 15:**
```
- OAuth tokens from marketplaces must be AES-256-CBC encrypted before SQLite storage
+ OAuth tokens from marketplaces must be AES-256-GCM (authenticated encryption) encrypted before SQLite storage
```

**`.claude/agents/Security-Auth.md` line 7** (inline in scope paragraph):
```
OAuth 2.0 marketplace tokens (AES-256-CBC encrypted)
→
OAuth 2.0 marketplace tokens (AES-256-GCM encrypted)
```

**`.claude/agents/qa-security.md` line 18:**
```
- OAuth token encryption (AES-256-CBC before SQLite storage)
+ OAuth token encryption (AES-256-GCM before SQLite storage)
```

### Fix 3: Resolve scope overlaps

The 3 new agents carve out territory from existing agents. Add explicit exclusion notes:

**`.claude/agents/Automations-AI.md`** — Add to scope paragraph after the existing scope description:
> "Excludes `src/shared/ai/listing-pipeline/` (owned by AI-Listing-Pipeline agent) and marketplace-specific Playwright bots in `src/shared/marketplaces/` (owned by Marketplace-Integration agent)."

**`.claude/agents/Backend.md`** — Add to scope paragraph after the existing scope description:
> "Excludes `src/backend/services/syncOrchestrator/` (owned by Data-Sync-Orchestrator agent), `src/backend/routes/oauth.js` and `src/backend/services/platformSync/index.js` (owned by Marketplace-Integration agent)."

### Fix 4: Remove memory/MEMORY.md changes

This file is session-managed and will cause merge conflicts with ongoing work. Revert:
```bash
git checkout origin/master -- memory/MEMORY.md
```

### Merge Strategy
```bash
# Stage only the specific files we modified
git add .claude/agents/Marketplace-Integration.md .claude/agents/Data-Sync-Orchestrator.md .claude/agents/AI-Listing-Pipeline.md
git add .claude/agents/Automations-AI.md .claude/agents/Backend.md .claude/agents/Security-Auth.md .claude/agents/qa-security.md
git add CLAUDE.md CONTRIBUTING.md
# Do NOT stage memory/MEMORY.md — it was reverted to master's version
git commit -m "fix: apply scope, encryption, and review fixes to agent definitions

Notion-Skip: GitHub infrastructure cleanup — no Sprint Board item
Verified: grep -r AES-256-CBC .claude/agents/ returns no results, scope exclusions present in Automations-AI.md and Backend.md"

git push origin copilot/add-specialized-agents --force-with-lease
gh pr ready 18
gh pr merge 18 --squash --subject "[AUTO] feat(agents): add 3 specialized agents with scope fixes and GCM correction"
```

**Note:** Verified that master's only commit ahead of the merge base (`1b819ff`) touches only `src/` and `scripts/` files — zero overlap with PR #18's files. Rebase will be clean.

---

## Phase 4: Implement PR #21's Real Findings on Master

These are genuine infrastructure gaps confirmed by the audit. Implement directly on master (single-developer workflow per CLAUDE.md).

### Prep: Return to master with merged PRs
```bash
git checkout master
git pull origin master  # Now includes squash-merged PRs #19 and #18
```

### 4A: Create CodeQL Workflow + Update Trivy (CRITICAL-001)

**New file:** `.github/workflows/codeql.yml`

Key decisions:
- Use `github/codeql-action` **v4** (not v3 as in the audit's YAML). Look up the current v4 tag SHA at execution time for pinning.
- Pin `actions/checkout` to `de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2` (repo standard)
- Trigger: push to main/master, PRs to main/master, weekly schedule (Monday 6 AM UTC)
- Language: `javascript` with `security-extended` query suite
- Permissions: `contents: read`, `security-events: write`, `actions: read`
- Timeout: 360 minutes (standard for CodeQL)

**Edit file:** `.github/workflows/trivy.yml` line 28
```
- uses: github/codeql-action/upload-sarif@v3
+ uses: github/codeql-action/upload-sarif@<v4-pinned-sha> # v4
```
This replaces the unpinned @v3 reference with a SHA-pinned v4 reference, consistent with the new codeql.yml.

**Close PR #13** (Dependabot codeql-action v3→v4 bump for trivy.yml) — superseded by our SHA-pinned update:
```bash
gh pr close 13 --comment "Superseded — trivy.yml updated to SHA-pinned v4 reference directly."
```

**Commit:** `[AUTO] ci: add CodeQL workflow and pin codeql-action to v4`

### 4B: Fix Staging URL Exposure (CRITICAL-003)

**Edit:** `.github/workflows/deploy-staging.yml`

**Verified:** Only one `environment_url` reference exists, at line 258 in the "Mark deployment success" step. The "Mark deployment failure" step (lines 262-273) does NOT include `environment_url`.

Line 258 currently reads:
```javascript
environment_url: 'http://${{ secrets.STAGING_HOST }}:3001',
```

This exposes the staging server's IP/hostname in the GitHub deployments UI. Fix by removing the field (safest — no staging domain exists yet):
```javascript
// Remove the entire environment_url line
```

**Trade-off:** Removing `environment_url` means GitHub's Deployments tab won't show a "View deployment" link for staging. This is acceptable — security (no secret exposure in GitHub UI) outweighs the convenience of a clickable link. If a staging domain is set up later, add it back as a static URL.

**Commit:** `[AUTO] fix(ci): remove staging host secret from deployment environment URL`

### 4C: Add Deploy Failure Notification (CRITICAL-004)

**Edit:** `.github/workflows/deploy.yml`

**Current state (verified):** Two jobs (`test` at lines 13-100, `deploy` at lines 102-116). No failure notification. Also uses unpinned actions:
- Line 44: `actions/checkout@v4` (should be `@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2`)
- Line 46: `oven-sh/setup-bun@v2` with `bun-version: latest` (should be `@0c5077e51419868618aeaa5fe8019c62421857d6 # v2.2.0` with `bun-version: '1.3.9'`)

**Changes:**
1. Pin existing `actions/checkout@v4` → SHA-pinned v6.0.2
2. Pin existing `oven-sh/setup-bun@v2` → SHA-pinned v2.2.0 with explicit bun version `1.3.9`
3. Add `notify-failure` job using GitHub issue creation (no external dependencies needed — SMTP and Slack are not yet configured):

```yaml
  notify-failure:
    name: Notify Deploy Failure
    runs-on: ubuntu-latest
    needs: [deploy]
    if: failure()
    permissions:
      issues: write
    steps:
      - uses: actions/github-script@ed597411d8f924073f98dfc5c65a23a2325f34cd # v8
        with:
          script: |
            const title = `[Deploy Failure] ${context.sha.substring(0, 7)} — Run #${context.runNumber}`;
            // Check for existing open issue first
            const issues = await github.rest.issues.listForRepo({
              owner: context.repo.owner,
              repo: context.repo.repo,
              state: 'open',
              labels: 'deploy-failure',
              per_page: 10
            });
            const existing = issues.data.find(i => i.title.startsWith('[Deploy Failure]'));
            if (existing) {
              core.notice(`Deploy failure detected, existing issue: ${existing.html_url}`);
              return;
            }
            const issue = await github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: title,
              body: `Production deploy failed.\n\n**Commit:** \`${context.sha}\`\n**Run:** ${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}\n\nPlease investigate and close this issue once resolved.`,
              labels: ['deploy-failure', 'automated']
            });
            core.notice(`Created deploy failure issue: ${issue.data.html_url}`);
```

Note: Added duplicate prevention (same pattern as PR #19) to avoid flooding issues on repeated failures.

**Commit:** `[AUTO] fix(ci): add deploy failure notification and pin actions in deploy.yml`

### 4D: Handle Remaining Dependabot PRs

| PR | Action | Reason |
|----|--------|--------|
| **#13** (codeql-action v3→v4) | **Close** | Superseded by our SHA-pinned v4 update to trivy.yml in Phase 4A |
| **#14** (actions/cache v4→v5) | **Review and merge if safe** | Independent dependency bump — check changelog for breaking changes |
| **#15** (sonarqube-scan-action v6→v7) | **Review and merge if safe** | Major version bump — check changelog for breaking changes before merging |

---

## Phase 5: Commit and Verify

### Commit Sequence (chronological order on master)
1. PR close operations (Phases 1, 4D) — no commits, just `gh pr close`
2. Squash-merge PR #19 — `[AUTO] fix(ci): add step ID, labels, and pin actions in auto-issue workflow`
3. Squash-merge PR #18 — `[AUTO] feat(agents): add 3 specialized agents with scope fixes and GCM correction`
4. Direct commit — `[AUTO] ci: add CodeQL workflow and pin codeql-action to v4`
5. Direct commit — `[AUTO] fix(ci): remove staging host secret from deployment environment URL`
6. Direct commit — `[AUTO] fix(ci): add deploy failure notification and pin actions in deploy.yml`

**Trailer requirements per commit type** (enforced by `.husky/commit-msg`):
- `ci:` type → **EXEMPT** from `Notion-Skip:` and `Verified:` trailers (line 19 of hook)
- `fix:`, `feat:` types → **BLOCKED** without both `Notion-Skip:` (or `Notion-Done:`) AND `Verified:` trailers

| # | Commit | Type | Trailers Needed |
|---|--------|------|-----------------|
| 1 | PR close operations | n/a | No commit |
| 2 | Squash-merge PR #19 | `fix` | Created on GitHub server — local hook does not apply |
| 3 | Squash-merge PR #18 | `feat` | Created on GitHub server — local hook does not apply |
| 4 | CodeQL + trivy pin | `ci` | **Exempt** |
| 5 | Staging URL fix | `fix` | `Notion-Skip:` + `Verified:` required |
| 6 | Deploy notification | `fix` | `Notion-Skip:` + `Verified:` required |

**Pre-push hook** (`.husky/pre-push`): Requires dev server on PORT if DATABASE_URL is set. Run `bun run dev:bg` before pushing to master. Syntax checks app.js + server.js from HEAD (we don't modify these). Checks Notion error log and Sprint Board drift.

### Verification Checklist
After all changes, run each of these and paste output:

```bash
# 1. Only Dependabot PRs #14 and #15 remain open
gh pr list --state open --json number,title,isDraft

# 2. codeql.yml exists (9 workflow files total)
ls .github/workflows/

# 3. All AES-256-CBC references eliminated from agents
grep -r "AES-256-CBC" .claude/agents/
# Expected: no output (exit code 1)

# 4. 17 agent files
ls .claude/agents/ | wc -l

# 5. Step ID bug fixed in PR #19's workflow
grep "id: create-failure-issue" .github/workflows/auto-create-issue-on-ci-failure.yml

# 6. Staging URL no longer exposes secret
grep "environment_url" .github/workflows/deploy-staging.yml
# Expected: no output (line removed)

# 7. Deploy failure notification exists
grep "notify-failure" .github/workflows/deploy.yml

# 8. All github-script refs are SHA-pinned v8
grep "github-script" .github/workflows/*.yml | grep -v "ed597411d8f924073f98dfc5c65a23a2325f34cd"
# Expected: no output (all pinned)

# 9. All checkout refs are SHA-pinned v6.0.2 (except any in PR templates)
grep "actions/checkout" .github/workflows/*.yml | grep -v "de0fac2e4500dabe0009e67214ff5f5447ce83dd"
# Expected: no output (all pinned)

# 10. trivy.yml uses v4 (not v3)
grep "codeql-action" .github/workflows/trivy.yml

# 11. Wait for CI to pass on master
gh run list --branch master --limit 3
```

---

## Files Modified (Complete Summary)

| File | Action | Phase |
|------|--------|-------|
| `.github/workflows/auto-create-issue-on-ci-failure.yml` | Add `id: create-failure-issue`, add labels, pin github-script to v8 SHA | 2 |
| `.claude/agents/Marketplace-Integration.md` | New file from PR; fix AES-256-CBC→GCM at lines 14, 65 | 3 |
| `.claude/agents/Data-Sync-Orchestrator.md` | New file from PR; accept as-is | 3 |
| `.claude/agents/AI-Listing-Pipeline.md` | New file from PR; accept as-is | 3 |
| `.claude/agents/Automations-AI.md` | Add scope exclusions for AI-Listing-Pipeline and Marketplace-Integration | 3 |
| `.claude/agents/Backend.md` | Add scope exclusions + fix AES-256-CBC→GCM at line 15 | 3 |
| `.claude/agents/Security-Auth.md` | Fix AES-256-CBC→GCM at line 7 | 3 |
| `.claude/agents/qa-security.md` | Fix AES-256-CBC→GCM at line 18 | 3 |
| `CLAUDE.md` | Accept agent count 14→17 + 3 new table rows from PR | 3 |
| `CONTRIBUTING.md` | Accept agent count 8→11 + 3 new table rows from PR | 3 |
| `.github/workflows/codeql.yml` | **New file** — CodeQL JavaScript analysis, v4, SHA-pinned | 4A |
| `.github/workflows/trivy.yml` | Pin codeql-action/upload-sarif from @v3 → SHA-pinned v4 | 4A |
| `.github/workflows/deploy-staging.yml` | Remove `environment_url` line 258 (staging host exposure) | 4B |
| `.github/workflows/deploy.yml` | Pin checkout+bun, add notify-failure job with issue creation | 4C |

**Total: 14 files (3 new, 11 modified)**

---

## Out of Scope (deferred with rationale)

| Item | Source | Why Deferred |
|------|--------|-------------|
| Rollback workflow | HIGH-003 | Audit's YAML uses `git log --grep` and force-push patterns that don't align with Railway's auto-deploy model. Needs architecture discussion first. |
| PostgreSQL composite action | HIGH-001 | Native `services:` blocks work correctly. Extracting to composite action is a nice-to-have refactor, not a gap. |
| Bun setup composite action | OPT-001 | Same — nice-to-have DRY cleanup, not blocking. |
| Branch protection | CRITICAL-002 | GitHub UI setting only, not a code change. Unverifiable from code — the audit admitted this. **User action:** Settings > Branches > Add rule for `master`. |
| Secret scanning | CRITICAL-005 | GitHub UI setting only. Unverifiable from code — audit admitted this. **User action:** Settings > Code security and analysis > Enable secret scanning. |
| E2E test re-enable | CRITICAL-006 | Separate concern from PR cleanup. Already tracked as known state. |
| Dependabot Docker | HIGH-006 | Nice-to-have addition to `dependabot.yml`. Can be done anytime. |

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| PR #18 rebase conflicts on CLAUDE.md or CONTRIBUTING.md | Resolve manually — accept PR's agent count changes on top of master's current content |
| PR #18 rebase conflicts on memory/MEMORY.md | Take master's version entirely (Fix 4 removes PR's changes) |
| CodeQL v4 SHA changes between plan and execution | Look up live SHA during execution via `gh api` |
| New CodeQL workflow triggers on first push and finds many alerts | Expected — JavaScript `security-extended` may surface existing issues. Not a blocker. |
| Deploy notification creates labels that don't exist | `github.rest.issues.create` with `labels` auto-creates them if the user has permission |

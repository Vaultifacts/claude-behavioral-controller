# Reopen Dismissed Alerts + Auto-Scanning + Dismissal Prevention

## Context
932 code scanning alerts were incorrectly bulk-dismissed as "false positive" by a previous Claude session at 06:04 UTC 2026-03-28. All 932 are Semgrep PRO findings, all dismissed with the same blanket comment. The correct behavior is: real issues that are fixed should close automatically when the scanner re-runs — dismissing them hides real vulnerabilities.

Additionally, the Semgrep workflow has a `paths:` filter that limits push triggers to only changes to the workflow file itself. CodeQL runs weekly via GitHub default setup (not on push). This means most code changes are NOT scanned in real time.

## Current Scanning State
| Tool | Trigger | Issue |
|------|---------|-------|
| Semgrep | push (but `paths:` filter = only workflow changes) + daily cron | **Broken** — normal pushes dont trigger |
| CodeQL | GitHub default setup, weekly | **Too infrequent** |
| Trivy | push + PR | OK |
| SonarCloud | push + PR | OK |

---

## Step 1: Reopen all 932 dismissed alerts

Use `gh api` in a paginated loop to set all dismissed alerts back to open:

```bash
page=1
count=0
while true; do
  numbers=$(gh api "repos/Vaultifacts/VaultLister-3.0/code-scanning/alerts?state=dismissed&per_page=100&page=$page" --jq '.[].number')
  if [ -z "$numbers" ]; then break; fi
  for n in $numbers; do
    gh api -X PATCH "repos/Vaultifacts/VaultLister-3.0/code-scanning/alerts/$n" -f state=open 2>/dev/null
    count=$((count + 1))
  done
  page=$((page + 1))
done
echo "Reopened $count alerts"
```

After reopening, trigger a rescan. The scanner will then automatically move genuinely-fixed alerts to "fixed" state, leaving only real issues as "open".

---

## Step 2: Fix scanning triggers for real-time updates

### 2a. Fix semgrep.yml — remove paths filter

**File:** `.github/workflows/semgrep.yml`

Problem: Lines 10-11 have a `paths:` filter that restricts push triggers to only `.github/workflows/semgrep.yml` changes. Normal code pushes to master do NOT trigger a scan.

Fix: Remove the `paths:` filter. Also remove `main` branch (default branch is `master`). Add `security-events: write` permission for SARIF upload.

```yaml
name: Semgrep

on:
  workflow_dispatch: {}
  pull_request: {}
  push:
    branches:
      - master
  schedule:
    - cron: "51 8 * * *"

jobs:
  semgrep:
    name: semgrep/ci
    runs-on: ubuntu-latest
    permissions:
      contents: read
      security-events: write
    env:
      SEMGREP_APP_TOKEN: ${{ secrets.SEMGREP_APP_TOKEN }}
    container:
      image: semgrep/semgrep
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd
      - name: Run Semgrep
        run: semgrep ci --exclude .github/workflows/sonarcloud.yml
```

### 2b. Add CodeQL workflow for push + PR triggers

**File:** `.github/workflows/codeql.yml` (NEW)

GitHub default setup only runs weekly. Adding a workflow file gives push + PR triggers. Uses same pinned action versions as existing workflows.

```yaml
name: CodeQL

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]
  schedule:
    - cron: "23 4 * * 1"

jobs:
  analyze:
    name: Analyze (${{ matrix.language }})
    runs-on: ubuntu-latest
    permissions:
      security-events: write
      contents: read
    strategy:
      fail-fast: false
      matrix:
        language: [javascript-typescript, python]
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd
      - name: Initialize CodeQL
        uses: github/codeql-action/init@c10b8064de6f491fea524254123dbe5e09572f13
        with:
          languages: ${{ matrix.language }}
      - name: Autobuild
        uses: github/codeql-action/autobuild@c10b8064de6f491fea524254123dbe5e09572f13
      - name: Perform CodeQL Analysis
        uses: github/codeql-action/analyze@c10b8064de6f491fea524254123dbe5e09572f13
        with:
          category: "/language:${{ matrix.language }}"
```

### Result after Step 2
| Tool | Trigger | Status |
|------|---------|--------|
| Semgrep | push + PR + daily cron | Fixed |
| CodeQL | push + PR + weekly cron | Fixed |
| Trivy | push + PR | Already OK |
| SonarCloud | push + PR | Already OK |

Every push to master triggers all 4 scanners. Alert statuses update automatically.

---

## Step 3: Prevent future bulk dismissals

### 3a. CLAUDE.md rule — explicit prohibition

Add to the "Things You Must NEVER Do" section in `CLAUDE.md`:
```
- Dismiss or close code scanning alerts via the GitHub API — alerts close automatically when fixed in code. Never use `gh api -X PATCH` on `code-scanning/alerts` with `state=dismissed`.
```

### 3b. Hook — block Claude from dismissing via API

Create `~/.claude/hooks/block-alert-dismiss.py` that reads the Bash command from stdin JSON, checks if it contains both `code-scanning/alerts` and `dismiss`, and returns a block decision if matched.

Register as a PreToolUse hook on `Bash` in `settings.local.json`.

---

## Step 4: Trigger rescan

After pushing Steps 2a/2b/3a, the push itself triggers Semgrep + CodeQL + Trivy + SonarCloud. The scanners will:
- Move genuinely-fixed alerts to "fixed"
- Keep real issues as "open"
- No manual intervention needed going forward

---

## Verification

1. `gh api "repos/.../code-scanning/alerts?state=dismissed" --jq length` returns **0**
2. Push the workflow changes to master
3. Check GitHub Actions — all 4 scanners (Semgrep, CodeQL, Trivy, SonarCloud) run
4. After scans complete: `gh api "repos/.../code-scanning/alerts?state=open" --jq length` shows real remaining issues
5. Fixed issues show as `state=fixed` (not dismissed)
6. Attempt to dismiss via Claude Bash tool — hook blocks it

## Files Modified
- `.github/workflows/semgrep.yml` — remove paths filter, add security-events write
- `.github/workflows/codeql.yml` — new file (push + PR + weekly triggers)
- `CLAUDE.md` — add "never dismiss code scanning alerts" rule
- `~/.claude/hooks/block-alert-dismiss.py` — new hook script
- Project `settings.local.json` — register the hook

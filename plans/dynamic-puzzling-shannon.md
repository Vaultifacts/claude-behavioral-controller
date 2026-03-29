# Fix Failed CI Checks on 5 Open Dependabot PRs — COMPLETED (commit 9a47fb7)

## Context

5 open Dependabot PRs (#12, #13, #14, #15, #16) all have failed CI checks. Investigation reveals **4 distinct root causes** — all are pre-existing issues on `master` (confirmed: latest 3 master CI runs also fail). The Dependabot PRs merely expose them. Fixing master unblocks all 5 PRs.

---

## PR Summary

| PR | Branch | Change | Failed (from `gh pr checks`) | Passed |
|----|--------|--------|-------------------------------|--------|
| #16 | `dependabot/npm_and_yarn/anthropic-ai/sdk-0.80.0` | Bump `@anthropic-ai/sdk` 0.39.0 → 0.80.0 | Lint, Unit Tests, Unit Tests (Guardian Gate), E2E Tests (Guardian), Security Scan, Accessibility Audit, Visual Tests (×3), Analysis, auto-merge (11 failures) | Docker Build, Dep Audit, Trivy, Semgrep |
| #15 | `dependabot/github_actions/SonarSource/sonarqube-scan-action-7` | Bump SonarSource action v6 → v7 | Lint, E2E Tests (Guardian), QA Guardian E2E Smoke, Analysis, auto-merge (5 failures) | Unit Tests, Security Scan, Accessibility, Visual Tests (×3), Docker Build, Dep Audit, Trivy, Semgrep |
| #14 | `dependabot/github_actions/actions/cache-5` | Bump actions/cache v4 → v5 | Lint, E2E Tests (Guardian), QA Guardian E2E Smoke, Analysis, auto-merge (5 failures) | (same as #15) |
| #13 | `dependabot/github_actions/github/codeql-action-4` | Bump codeql-action v3 → v4 | Lint, E2E Tests (Guardian), QA Guardian E2E Smoke, Analysis, auto-merge (5 failures) | (same as #15) |
| #12 | `dependabot/github_actions/appleboy/ssh-action-1.2.5` | Bump ssh-action 1.0.3 → 1.2.5 | (same as #16 — 11 failures) | (same as #16) |

---

## Root Cause 1: Lockfile out of sync with package.json

**Verified error (verbatim from CI):**
```
error: lockfile had changes, but lockfile is frozen
note: try re-running without --frozen-lockfile and commit the updated lockfile
```

**Root cause:** Commit `4cbb2a3` (Mar 23 — "chore: update settings, hooks, and config files") added `"dompurify": "^3.3.3"` to `package.json` dependencies and a new `test:coverage:lcov` script WITHOUT updating `bun.lock`. Every CI job runs `bun install --frozen-lockfile`, which rejects the install.

**Verified locally:** `bun install --frozen-lockfile` fails on current master with "8 packages resolved/downloaded/extracted".

**Affects:** PR #12 (all jobs fail), PR #16 (all jobs fail — also needs its own lockfile update for SDK bump). Also breaks master CI (Unit Tests, Security Scan, Accessibility Audit, Visual Tests all fail).

**Why PRs #13-15 are NOT affected by this:** They ran checks on Mar 23 09:44 UTC, ~12 hours BEFORE commit `4cbb2a3` was pushed (21:52 UTC). Their lockfile was still in sync at check time.

**Fix:**
1. Run `bun install` on master to regenerate `bun.lock`
2. Commit the updated lockfile
3. PR #16 additionally needs an on-branch `bun install` + commit (it bumps the SDK version in package.json)

---

## Root Cause 2: 5 JavaScript syntax errors in 2 handler files

**Verified:** Each file tested individually via `bun build --no-bundle`. Only these 2 files have real syntax errors. All other `src/**/*.js` files (including `core-bundle.js` and `widgets.js`) pass individually — the phantom errors attributed to them in combined xargs runs are cascading artifacts from bun's multi-file processing.

### File 1: `src/frontend/handlers/handlers-tools-tasks.js` — 3 errors

**Line 872** — Stray `)` before `<span>` in template literal:
```javascript
// CURRENT (broken):
...map(([sys, sz]) => `)<span class="badge" style="margin: 2px;">${sys}: ${sz}</span>`).join('')}
// FIX: delete the stray )
...map(([sys, sz]) => `<span class="badge" style="margin: 2px;">${sys}: ${sz}</span>`).join('')}
```

**Line 877** — Double `)` in CSS `var()` AND missing closing `)` for `sanitizeHTML(`:
```javascript
// CURRENT (broken):
...innerHTML = sanitizeHTML('<p style="color: var(--text-error));">Failed to get recommendation</p>';
// FIX: remove extra ), add closing )
...innerHTML = sanitizeHTML('<p style="color: var(--text-error);">Failed to get recommendation</p>');
```

**Line 1573** — Premature `)` closes `sanitizeHTML()` before concatenation completes:
```javascript
// CURRENT (broken — lines 1573-1577):
overlay.innerHTML = sanitizeHTML('<div class="celebration-content">' +)
    '<div class="celebration-icon">🎉</div>' +
    '<h2 ...>All Tasks Complete!</h2>' +
    '<p ...>Great job! You finished everything today.</p>' +
    '</div>';
// FIX: move ) from line 1573 to end of line 1577:
overlay.innerHTML = sanitizeHTML('<div class="celebration-content">' +
    '<div class="celebration-icon">🎉</div>' +
    '<h2 ...>All Tasks Complete!</h2>' +
    '<p ...>Great job! You finished everything today.</p>' +
    '</div>');
```

### File 2: `src/frontend/handlers/handlers-settings-account.js` — 2 errors

**Line 388** — Stray `)` in CSS padding value AND missing closing `)` for `sanitizeHTML(`:
```javascript
// CURRENT (broken):
resultsEl.innerHTML = sanitizeHTML('<div style="padding:12px 16px); color:var(--gray-500); font-size:13px;">No matching settings found</div>';
// FIX: remove ) from padding, add closing )
resultsEl.innerHTML = sanitizeHTML('<div style="padding:12px 16px; color:var(--gray-500); font-size:13px;">No matching settings found</div>');
```

**Line 1224** — Premature `)` closes `sanitizeHTML()` before concatenation:
```javascript
// CURRENT (broken — lines 1224-1225):
select.innerHTML = sanitizeHTML('<option value="">Select Service</option>' +)
    serviceTypes[carrier].map(s => `<option value="${s}">${s}</option>`).join('');
// FIX: move ) from line 1224 to end of line 1225:
select.innerHTML = sanitizeHTML('<option value="">Select Service</option>' +
    serviceTypes[carrier].map(s => `<option value="${s}">${s}</option>`).join(''));
```

**Affects:** PR #13, #14, #15 (Lint failure). Also fails on master CI.

---

## Root Cause 3: SonarCloud SONAR_TOKEN unavailable for Dependabot PRs

**Verified error (verbatim from CI, confirmed on both PR #13 with v6 and PR #15 with v7):**
```
ERROR Project not found. Please check the 'sonar.projectKey' and 'sonar.organization' properties,
the 'SONAR_TOKEN' environment variable, or contact the project administrator
```
```
Action failed: The process '/opt/hostedtoolcache/sonar-scanner-cli/.../bin/sonar-scanner' failed with exit code 3
```

**Root cause:** GitHub restricts repository secrets from Dependabot-triggered workflows. The `SONAR_TOKEN` secret is blank when `github.actor == 'dependabot[bot]'`, causing the scanner to fail.

**Affects:** PRs #13, #14, #15 directly (Analysis check fails at SonarCloud scan step). PRs #12, #16 also show Analysis failure, but that's from the lockfile drift (fails at `bun install` before reaching the scan step). After lockfile fix, PRs #12/#16 would also hit this SonarCloud issue on rerun.

**Not affected: Semgrep.** Despite using `SEMGREP_APP_TOKEN` from secrets, `semgrep/ci` **passes** on all 5 PRs (verified via `gh pr checks`). Semgrep likely handles missing tokens gracefully or uses Dependabot secrets configuration.

**Fix:** Add `if:` condition to the **SonarCloud scan step** (not the job) in `.github/workflows/sonarcloud.yml` at line 81. This keeps the Analysis job running (tests + coverage still execute) but skips only the scan step. The Analysis check still shows "pass" for Dependabot PRs, avoiding issues with required status checks:
```yaml
      - name: Analyze with SonarCloud
        if: github.actor != 'dependabot[bot]'
        uses: SonarSource/sonarqube-scan-action@v6
```
Why step-level (not job-level): A job-level `if:` would skip the entire job, causing the "Analysis" status check to not appear. If "Analysis" is a required check in branch protection, the PR would be stuck "pending" forever. Step-level skip keeps the job green.

---

## Root Cause 4: E2E `authedPage` fixture timeout (30000ms)

**Verified error (verbatim from CI, confirmed in both ci.yml and qa-guardian.yml runs):**
```
Test timeout of 30000ms exceeded while setting up "authedPage".
```

**All 11 tests** in `e2e/tests/qa-guardian.spec.js` fail identically.

### Deep-dive: Why the fixture exceeds 30s

The `authedPage` fixture in `e2e/fixtures/auth.js` performs **two full `page.goto()` navigations** (lines 79 and 87). Each `page.goto()` is a complete page reload — the browser discards the DOM and reloads all resources from scratch. This means the 1.4MB `core-bundle.js` (28,718 lines) is **fetched, gzipped, transferred, parsed, and executed twice**.

**Verified architecture (confirmed via source):**
- `src/frontend/index.html` (line 41): browser loads `<script src="/core-bundle.js" defer>` — this is the sole SPA bundle
- `src/backend/server.js` (line ~837): `serveStatic()` uses `gzipSync()` on every request in test/dev mode — no response caching
- `core-bundle.js` `initApp()` (lines 26817-27299): when authenticated, blocks up to **5 seconds** on `Promise.race([api.get('/inventory?limit=200'), api.get('/analytics/dashboard')], 5s_timeout)` before calling `router.init()` which renders the sidebar

**Worst-case CI timeline:**

| Step | Operation | Est. CI Time |
|------|-----------|-------------|
| 1 | `apiLogin()` — bcrypt(12) via `ensureTestDemoUser()` on first run | 1-3s |
| 2 | `page.goto(/#login)` — fetch+gzip+parse 1.4MB bundle, `initApp()` (no auth → login page) | 3-8s |
| 3 | `injectAuth()` — write to sessionStorage | ~10ms |
| 4 | **`page.goto(/#dashboard)` — SECOND full reload: re-fetch+re-gzip+re-parse 1.4MB bundle** | 3-8s |
| 5 | `initApp()` (authenticated) — blocks on API data calls | 0.5-5s |
| 6 | `waitForFunction('.sidebar', 15s)` — waits if sidebar hasn't rendered yet | 0-15s |
| 7 | Dismiss overlays | ~500ms |
| | **Total worst case** | **~34s** |

The default Playwright test timeout is **30000ms** (no override in `playwright.config.js`). On a slow GitHub Actions Ubuntu runner, the cumulative operations exceed this budget.

**Key sub-findings:**
- `ensureTestDemoUser()` (auth.js line 166): on first test run, calls `bcrypt.hash(password, 12)` — CPU-intensive, 1-3s on CI
- Double navigation is wasteful for a hash-based SPA: the second `goto()` discards the already-loaded SPA and reloads everything
- `waitForFunction('.sidebar').catch(() => {})` (line 117-118): the `.catch()` swallows the timeout silently — if the sidebar never appears, 15s is burned before continuing
- The sidebar only renders when `auth.isAuthenticated()` returns true AND `initApp()` completes its API data fetch (up to 5s timeout)

**Affects:** PR #13, #14, #15 (E2E Tests Guardian + QA Guardian E2E Smoke). Not visible on PR #12/#16 because those fail earlier at `bun install`.

**Pre-existing:** Confirmed failing on master's latest 3 CI runs too.

### Fix: Increase Playwright test timeout

Add `timeout: 60000` to the **top-level** config in `playwright.config.js` (after line 28 `fullyParallel: true,`):
```javascript
export default defineConfig({
    testDir: './e2e/tests',
    ...
    fullyParallel: true,
    timeout: 60000,  // Increase from default 30000ms — fixture needs ~34s worst-case on CI
    ...
});
```

**Note:** Line 68 already has `timeout: 60000` but that's inside the `webServer: { ... }` block — it controls how long Playwright waits for the dev server to start, NOT the per-test timeout. The per-test timeout is controlled by the top-level `timeout` property, which is currently absent (defaulting to 30000ms).

**Why this is sufficient:** The worst-case fixture time is ~34s. A 60s timeout gives 26s of headroom. No fixture code changes needed — the double navigation is inefficient but functionally correct (the second `page.goto()` triggers a full `initApp()` with authenticated state from sessionStorage, which pre-loads data the dashboard tests depend on).

**Why NOT optimize the fixture itself:** Eliminating the second `page.goto()` and replacing with `router.navigate('dashboard')` would save 3-13s, but it skips `initApp()`'s data pre-loading (`/inventory?limit=200` + `/analytics/dashboard`). Tests that expect dashboard stat cards or inventory data could fail. The timeout increase is a zero-risk fix that addresses the budget constraint without changing behavior.

**Confidence: HIGH.** Root cause is verified via complete source code trace (1.4MB bundle loaded twice, server gzips synchronously, `initApp()` blocks up to 5s on API calls). The 60s timeout provides ample margin for worst-case CI execution.

---

## Root Cause 5: Auto-merge failures (downstream — no direct fix needed)

The `Auto-merge Dependabot` workflow runs `gh pr checks --watch --fail-fast`, which exits non-zero when any other check fails. Self-resolves once root causes 1-4 are fixed.

## Additional workflows verified (NOT failing — confirmed via `gh pr checks`)

- **`semgrep.yml`** — Triggers on all PRs. Uses `SEMGREP_APP_TOKEN` from secrets, but `semgrep/ci` **passes** on all 5 Dependabot PRs (20-23s each). Token likely available via Dependabot secrets config or Semgrep handles missing tokens gracefully. **No fix needed.** ✓
- **`trivy.yml`** — Triggers on all PRs. Does NOT use repository secrets (only `GITHUB_TOKEN` for SARIF upload). **Passes** on all 5 PRs (20-26s each). ✓
- **`deploy.yml`** — Triggers only on `workflow_run` (after CI) on main/master, NOT on PRs. Not triggered. ✓
- **`deploy-staging.yml`** — Triggers only on push to `staging` branch. Not triggered. ✓

---

## Execution Order

All fixes go to **master first**, then PRs rebase:

1. **Fix syntax errors (Root Cause 2)** — 2 files, 5 edits. Zero risk.
   - `src/frontend/handlers/handlers-tools-tasks.js` (lines 872, 877, 1573)
   - `src/frontend/handlers/handlers-settings-account.js` (lines 388, 1224)

2. **Regenerate lockfile (Root Cause 1)** — `bun install` + commit updated `bun.lock`

3. **Skip SonarCloud for Dependabot (Root Cause 3)** — add `if:` condition in `.github/workflows/sonarcloud.yml`

4. **Fix E2E timeout (Root Cause 4)** — add `timeout: 60000` in `playwright.config.js`

5. **Commit all to master, push**

6. **PR #16 on-branch lockfile update** — checkout branch, merge master, `bun install`, commit, push

7. **Trigger Dependabot rebase** on PRs #12-15 via `@dependabot rebase` comments

---

## Verification

After pushing fixes to master:

1. `bun install --frozen-lockfile` — must succeed (lockfile in sync)
2. `find src -name "*.js" -not -path "*/node_modules/*" | xargs bun build --no-bundle --outdir /dev/null 2>&1 | grep -i "error"` — must return empty
3. `bun test src/tests/auth.test.js src/tests/security.test.js` — must pass
4. Push to master → monitor CI and QA Guardian workflows for green
5. Comment `@dependabot rebase` on PRs #12-15
6. Checkout PR #16 branch, merge master, `bun install`, push → monitor checks
7. All 5 PRs should have passing checks

---

## Files Modified

| File | Changes |
|------|---------|
| `src/frontend/handlers/handlers-tools-tasks.js` | L872: delete stray `)`. L877: fix `var(--text-error))` → `var(--text-error)` + add `)`. L1573+1577: move `)` |
| `src/frontend/handlers/handlers-settings-account.js` | L388: fix `16px)` → `16px` + add `)`. L1224+1225: move `)` |
| `bun.lock` | Regenerated via `bun install` |
| `.github/workflows/sonarcloud.yml` | Add `if: github.actor != 'dependabot[bot]'` to scan step at L81 (`- name: Analyze with SonarCloud`) |
| `playwright.config.js` | Add `timeout: 60000` to top-level config (after `fullyParallel: true`, line 28) |

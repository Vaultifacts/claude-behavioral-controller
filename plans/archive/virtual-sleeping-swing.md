# VaultLister 3.0 — Universal Reusability Audit
**Scope:** Every directory, every file. Identifies assets reusable in future projects of any domain.
**Coverage:** 8 agents × full codebase scan — src/, scripts/, chrome-extension/, mobile/, .claude/, .github/, .husky/, .openclaw/, e2e/, runbook/, public/, nginx/, config/, design/, data/, backups/

---

## Context

VaultLister 3.0 is a production-grade Bun.js + Vanilla JS SPA + SQLite platform built for reselling. While the business logic is marketplace-specific, approximately **65–70% of the codebase is domain-agnostic infrastructure** that could be extracted into a personal starter-kit for future projects. This plan catalogs every reusable asset across all 8 scan areas, assigns a tier, and lists what needs to change for reuse. A final section identifies patterns missing from this project but universally valuable.

---

## Extraction Strategy

**Recommended structure:**

```
~/dev/starter-kit/
  packages/                    # Extracted, self-contained units
    backend-middleware/        # csrf, rateLimiter, errorHandler, requestLogger, securityHeaders, cdn
    logger/                    # Structured logger (zero deps)
    utils-backend/             # dates, prices, strings, validation helpers
    utils-frontend/            # escapeHtml, formatters, DOM helpers, arrays
    state-store/               # Vanilla JS pub/sub state with localStorage
    spa-router/                # Hash-based lazy-loading SPA router
    api-client-web/            # JWT + CSRF + offline queue + retry (browser)
    api-client-mobile/         # Axios + JWT + AsyncStorage (React Native)
    api-client-extension/      # fetch + chrome.storage JWT (Chrome extension)
    websocket-client/          # Auto-reconnect + pub/sub + offline queue
    toast/                     # Accessible toast system
    sanitize/                  # XSS prevention + input validation
    ar-preview/                # WebXR camera overlay + fallback (no deps)
    sqlite-db/                 # WAL setup, migration runner, CRUD helpers
    notion-utils/              # Notion API client with retry + pagination
    env-loader/                # Minimal .env reader
  templates/                   # Full project templates (copy + customize)
    bun-fullstack/             # Dockerfile + nginx + CI + docker-compose + package.json
    chrome-extension/          # MV3 extension: manifest + sw + api + logger + popup
    react-native-app/          # Nav + authStore + api + ws + notifications
    pwa-shell/                 # sw.js + offline.html + manifest.json
    claude-project/            # .claude/ agents, hooks, rules, skills, settings, .mcp.json
    notion-workflow/           # session-start/end/transfer-approved + lib/notion.js
    openapi-ui/                # Swagger UI dark theme template
    runbook/                   # PowerShell runbook orchestration framework
```

---

## Full Asset Catalog

### KEY:  VH = Very High | H = High | M = Medium | L = Low reusability

---

### 1. BACKEND MIDDLEWARE  (`src/backend/middleware/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `csrf.js` | CSRF token generation + one-time Map-based validation, no deps | 1 | VH | None |
| `rateLimiter.js` | In-memory rate limiter, configurable presets (auth/mutation/expensive), breach detection, blocklist | 1 | VH | None |
| `errorHandler.js` | Custom error class hierarchy (AppError → ValidationError/NotFoundError/etc.), `catchAsync()` wrapper, consistent JSON format | 1 | VH | None |
| `requestLogger.js` | Request ID injection, timing, IP anonymization (GDPR), audit action constants, sensitive-field sanitization before log | 1 | VH | None |
| `securityHeaders.js` | Full CSP with nonce + strict-dynamic, HSTS preload, X-Frame-Options, Permissions-Policy, dev/prod split | 1 | VH | None |
| `cdn.js` | Asset versioning, per-type cache duration, immutable headers for hashed assets, Nginx config snippet | 1 | VH | None |
| `auth.js` | JWT generate/verify/refresh, `authenticateToken` middleware | 2 | H | Strip `checkTierPermission()` — subscription logic is VaultLister-specific |

---

### 2. BACKEND DATABASE  (`src/backend/db/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `database.js` (lines 63–120) | Migration runner: numbered SQL/JS files, idempotency tracking, ordering, error handling | 1 | VH | None — migration list is separate files |
| `database.js` (init) | SQLite WAL mode, PRAGMA tuning, prepared statement cache, generic CRUD helpers | 2 | H | Swap schema.sql and seed files |
| `connectionPool.js` | better-sqlite3 query profiler: slow-query detection, EXPLAIN logging, timing histograms, memory-capped pattern tracking | 1 | VH | None |
| `migrations/*.sql` (96 files) | All schema migrations | L | Domain-specific | Don't reuse content; reuse naming convention (`001_feature.sql`) |
| `seeds/*.js` | Demo data seeding pipeline | M | Architecture reusable | Swap data; keep seeding framework |

---

### 3. BACKEND SHARED UTILITIES  (`src/backend/shared/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `logger.js` | Structured logging, levels, JSON in prod, child logger factory, zero deps | 1 | VH | None |
| `utils.js` | UUID/short ID generation, date helpers (now/today/daysAgo), price formatting, slugify/pluralize | 1 | VH | None |
| `helpers.js` | Query param parsing, pagination metadata builder, safe JSON parse, field validation (required/length/range/enum/email/URL) | 1 | VH | None |

---

### 4. SHARED DOMAIN UTILITIES  (`src/shared/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `utils/sanitize.js` | `sanitizeHtml()` XSS prevention, `validateText()` parameterized bounds | 1 | VH | Remove `validateInventoryData()` — reseller-specific |
| `utils/ar-preview.js` | WebXR camera-based AR overlay + `SimpleAROverlay` fallback with drag/pinch; `takeSnapshot()` | 1 | VH | None — zero domain coupling |
| `utils/sustainability.js` | Environmental impact calculator: water/CO2/waste saved, equivalents (showers, car miles, trees) | 2 | H | Move `IMPACT_DATA` to config/DB; algorithm stays |
| `utils/blockchain.js` | SHA-256 item verification hashing, authenticity certificate chain | 2 | M | Bun crypto fallback needed for non-Bun envs |
| `automations/rate-limits.js` | Platform rate-limit constants + `jitteredDelay()` (±30% randomization) | 1 | VH | None — already generic; just add/remove platforms |
| `automations/poshmark-bot.js` (architecture) | Playwright bot: constructor → init → login → actions → cleanup + `humanType()` + `randomDelay()` | 2 | H | Keep architecture; swap selectors/endpoints per platform |
| `automations/automation-audit.log` (pattern) | JSON Lines audit trail: `{ts, platform, event, ...metadata}` | 1 | VH | None — pure logging pattern |
| `ai/listing-generator.js` | Template-based content generation: titles, descriptions, tags from rule dictionaries | 2 | VH | Move brand/category dictionaries to config; algorithm stays |
| `ai/image-analyzer.js` (quality check) | Image quality estimation: resolution, aspect ratio, file size, format validation | 2 | H | Move brand/category patterns to config |
| `ai/price-predictor.js` (algorithm) | Multi-factor pricing: brand tier × condition × seasonal × size multipliers | 2 | H | Move all price data to DB/config; keep algorithm |

---

### 5. FRONTEND CORE  (`src/frontend/core/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `store.js` | Observer-pattern state manager with localStorage/sessionStorage persistence, hydrate/persist/subscribe | 1 | VH | None |
| `toast.js` | Accessible toast system (aria-live, role=alert), auto-dismiss, undo action, max 5 concurrent | 1 | VH | None |
| `utils.js` | ~90% generic: `escapeHtml`, `formatCurrency`, date formatters, `groupBy`, `chunk`, `unique`, DOM helpers, feature detection | 1 | VH | Remove `formatCondition()` + `getPlatformName()` |
| `api.js` | JWT refresh chain, CSRF token, offline queue (IndexedDB), retry with backoff, loading state | 2 | VH | Parameterize `/api` base URL and auth endpoints |
| `router.js` | Hash-based SPA router, lazy chunk loading, auth guard, unsaved-changes detection | 2 | VH | Replace route map; keep routing engine |
| `auth.js` | Login/register forms, MFA prompt, lockout countdown timer, Web Speech API voice commands | 2 | H | Remove VaultLister endpoint URLs and form copy |

---

### 6. FRONTEND UI LAYER  (`src/frontend/ui/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `components.js` (~60% generic) | Stat cards, breadcrumbs, tooltips, loaders, skeletons, empty states, inline edit, progress rings | 2 | H | Remove platform badges (Poshmark/eBay/Mercari) |
| `widgets.js` (core parts) | Form validation engine, inline edit (EditInPlace), autocomplete, auto-save draft recovery, confetti celebration effects | 2 | M | Adapt global search to accept entity types via config |
| `modals.js` (engine only) | `modals.show()`, `modals.close()`, `modals.confirm()`, `modals.prompt()` core engine | 2 | M | Extract engine; discard workflow modals (add item, cross-list, etc.) |
| `main.css` (~80% generic) | CSS custom properties (color palette, spacing, type), dark mode, component styles, layout utilities | 2 | H | Remove platform color variables (Poshmark pink, eBay blue) |

---

### 7. FRONTEND SERVICES  (`src/frontend/services/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `websocketClient.js` | WS client: exponential backoff reconnect, pub/sub topics, offline message queue, auth token injection | 1 | VH | None — event type names are the only VaultLister part |

---

### 8. FRONTEND COMPONENTS  (`src/frontend/components/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `chatWidget.js` | Floating chat UI, message history, helpful/not-helpful rating, quick actions | 2 | H | Parameterize API endpoint; replace `eval()` with `Function()` |
| `photoEditor.js` | Canvas: rotate, flip, brightness, contrast, saturation, filters; Cloudinary optional | 2 | H | Make Cloudinary opt-in via config flag |

---

### 9. MOBILE APP — REACT NATIVE  (`mobile/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `src/services/api.js` | Axios + JWT interceptors, token refresh, AsyncStorage persistence | 1 | VH | Change endpoint paths; keep auth infrastructure |
| `src/services/websocket.js` | WS auto-reconnect, exponential backoff, message queue, event routing (native WS only) | 1 | VH | Remove event type strings; keep connection management |
| `src/services/notifications.js` | FCM integration, permission request, device token registration, Android channel setup | 1 | VH | Change API endpoint for token registration |
| `src/store/authStore.js` | Zustand auth store: login/register/logout, token persistence to AsyncStorage | 1 | VH | Replace API calls; keep store structure |
| `src/screens/LoginScreen.js` | Email/password form, show/hide toggle, OAuth placeholders, error handling | 2 | H | Remove VaultLister copy and brand colors |
| `src/App.js` | Tab + stack navigation, Firebase FCM init, auth check, WebSocket init | 2 | H | Swap screen imports; keep nav/init pattern |
| `package.json` | RN 0.73 + Navigation + Firebase + VisionCamera + Zustand + Axios | 1 | VH | Use as-is for similar RN projects |

---

### 10. CHROME EXTENSION  (`chrome-extension/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `manifest.json` | MV3: permissions, content scripts, background worker, popup | 1 | VH | Update `host_permissions` + API URL (3 lines) |
| `lib/api.js` | `fetch()` wrapper + chrome.storage JWT, 401 handling | 1 | VH | Change `API_BASE_URL` + method routes |
| `lib/logger.js` | Level-based chrome.storage debug toggle logger | 1 | VH | Change `LOG_PREFIX` (1 line) |
| `popup/popup.css` | Full popup styles, animations, dark color scheme | 1 | H | Swap brand colors (3 lines) |
| `popup/popup.html` | Login + dashboard UI: stats grid, quick action buttons | 2 | H | Update copy and branding |
| `background/service-worker.js` | Message routing, chrome alarms, notifications, badge updates | 2 | H | Abstract domain-specific handlers |
| `content/autofill.js` | Field-mapping + `setFieldValue()` + form fill modal — **extremely generic** | 2 | VH | Update field mappings for new platforms |
| `content/scraper.js` | Button injection, DOM scraping, message passing | 2 | M | Swap site selectors per target domain |
| `popup/popup.js` | State management, view switching, message passing | 2 | M | Refactor stat loading; keep state/view pattern |

---

### 11. PWA & WEB ASSETS  (`public/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `sw.js` | Service Worker: pre-cache app shell, network-first for APIs, cache-first for images/fonts, offline fallback | 1 | VH | Update PRECACHE_URLS, cache version, domain paths |
| `offline.html` | Styled offline fallback page, online/offline detector, auto-redirect on reconnect | 1 | VH | Replace copy only |
| `manifest.json` / `manifest.webmanifest` | PWA manifest: display mode, icons, shortcuts, theme, categories | 1 | VH | Update app name, colors, icons, shortcuts |
| `api-docs/index.html` | Swagger UI with custom dark theme (indigo + blue), method color coding | 1 | VH | Update brand colors + title |
| `axe-core.min.js` | Accessibility testing library (third-party) | 1 | VH | Use as-is |

---

### 12. DEVOPS & DEPLOYMENT  (root + `nginx/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `Dockerfile` | Multi-stage Bun build: builder → production slim, non-root user, health check | 1 | VH | Change image names; keep pattern |
| `docker-compose.yml` | App + Redis + Nginx + optional backup, profile-based optional services | 2 | H | Swap service names + ports |
| `nginx/nginx.conf` | SSL/TLS, rate limit zones, gzip, WebSocket upgrade, static asset caching, HSTS | 1 | VH | Change upstream name (`app:3000`) + SSL cert paths |
| `config/gate-thresholds.json` | Performance SLOs: startup, health latency, inventory latency — warn/fail tiers | 1 | VH | Tune values per app; keep structure |

---

### 13. CI/CD  (`.github/workflows/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `ci.yml` | Lint + unit + E2E (3-shard) + security scan + dep audit + Docker build + a11y + visual + known-failure baseline | 1 | H | Swap bun commands for your runner/framework |
| `qa-guardian.yml` | Nightly scheduled E2E run + flakiness tracking | 1 | H | Swap test command + schedule |
| `deploy.yml` | Docker build → ghcr.io push → staging/prod deploy stubs | 1 | H | Update image names + registry |

---

### 14. SCRIPTS & DEV TOOLS  (`scripts/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `lib/env.js` | Minimal .env reader: key=value, skips comments, respects pre-set vars | 1 | VH | None |
| `lib/notion.js` | Notion API client: rate-limit retry, pagination, full CRUD | 1 | VH | None |
| `kill-port.js` | Cross-platform port killer (Windows netstat/taskkill, Linux fuser) | 1 | VH | None |
| `server-manager.js` | Background HTTP process lifecycle: start/stop/restart/status/logs, PID file | 1 | VH | None |
| `backup.js` / `restore.js` | SQLite backup with WAL safety, gzip, retention rotation, integrity check | 1 | H | None |
| `security-audit.js` | Static code scan: hardcoded secrets, SQL injection, command injection, eval abuse | 1 | VH | Add patterns as needed |
| `accessibility-audit.js` | WCAG 2.2 AA compliance scan via axe-core + Playwright | 1 | VH | Swap routes |
| `session-start.js` | Project state recovery: Notion status check + health ping | 2 | H | Swap Notion page IDs + section names |
| `session-end.js` | CLI to capture completed work → Notion "Waiting for Approval" | 2 | H | Same Notion structure |
| `transfer-approved.js` | Move approved → completed in Notion with toggle preservation | 2 | H | Swap section names |
| `run-migrations.js` | Generic migration runner entry point | 1 | VH | None |
| `visual-test.js` | Playwright visual regression + a11y (140+ action types) | 2 | H | Swap route list |
| `load-test.js` | Multi-scenario load tester (baseline/stress/soak/spike), percentile math | 2 | H | Swap endpoint URLs + auth |
| `help.js` | Auto-generated categorized script help from script list | 1 | H | Swap script list |

---

### 15. CLAUDE CODE CONFIGURATION  (`.claude/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `settings.json` | Allow/deny permission model, hook bindings, memory file paths, statusline | 1 | VH | Swap critical file paths |
| `hooks/validate-bash.sh` | Pre-command safety gate: blocks dangerous bash patterns (pipe-to-bash, git add -A, rm -rf, force push) | 1 | VH | None |
| `hooks/protect-files.sh` | Blocks writes to configurable critical file list | 1 | H | Swap file list for your project |
| `hooks/post-commit.sh` | Appends to audit-log.md, sends OpenClaw event | 1 | VH | Swap webhook target |
| `hooks/session-init.sh` | Session lifecycle: read memory context, auto-stash, send events | 2 | H | Remove OpenClaw if not using bots |
| `hooks/notify-openclaw.sh` | Generic HTTP POST webhook with JSON payload, graceful no-op | 1 | VH | Update webhook URL in .env |
| `agents/*.md` (8 files) | Role-based scope boundaries: scope, invariants, model preference, deferred-to pattern | 1 | VH (pattern) | Swap roles + domain specifics per project |
| `rules/src/RULES.md` | Source code rules: naming, structure, security, modification discipline | 2 | H | Swap entity names + framework; keep security rules |
| `rules/tests/RULES.md` | Test rules: naming, scope, critical protocols (CSRF/IDOR/auth), failure protocol | 1 | VH | Swap test framework names |
| `skills/build/SKILL.md` | `/build` skill: lint → security test gate → bundle → validate → notify | 1 | VH | Swap build commands |
| `skills/deploy/SKILL.md` | `/deploy` skill: pre-checks → Docker build → push → health check → rollback | 1 | VH | Swap Docker targets |
| `skills/test/SKILL.md` | `/test` skill: routes to unit/auth/security/E2E/visual suites | 1 | VH | Swap test file paths |
| `skills/status/SKILL.md` | `/status` skill: git + server + tests + pending tasks + notify | 1 | H | Swap port + test command |
| `skills/design-sync/SKILL.md` | `/design-sync` skill: reads design docs, surfaces drift | 1 | VH | Swap design file paths |

---

### 16. GIT HOOKS  (`.husky/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `commit-msg` | Conventional commits format enforcement | 1 | VH | None — 100% generic |
| `pre-commit` | Secrets scan, auth infrastructure integrity checks, CSP validation | 2 | H | Parametrize critical file paths |
| `pre-push` | JS syntax check, regression gate against `.test-baseline` | 2 | H | Parametrize critical files; swap test runner |
| `post-commit` | Auto-logs to STATUS.md, Bot commit detection, Telegram alerts | 2 | M | Requires STATUS.md + webhook |

---

### 17. PROJECT COORDINATION  (`memory/`, `.openclaw/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `memory/STATUS.md` | CLI↔Bot coordination: In Progress, Pending Review, Next Tasks, Last Completed, Blockers, Messages | 1 | VH | Replace task entries; keep structure |
| `memory/MEMORY.md` | Auto-loaded project overview: commands, rules, entities, agent list | 2 | H | Swap project content; keep template structure |
| `.openclaw/config.json` | OpenClaw channel routing, webhook URLs, skills + workflow registry | 1 | VH | Rename project; update channel ID + URLs |
| `.openclaw/memory/schema.json` | JSON Schema for inter-session bot memory | 1 | VH | Add/remove fields per project |
| `.openclaw/memory/context.json` | Initial memory state template | 1 | VH | Swap task content |
| `.openclaw/skills/*.json` (ask/build/deploy/status) | OpenClaw skill definitions: trigger → Claude Code command | 1 | VH | Rename project reference |
| `.openclaw/workflows/*.json` (daily-heartbeat/on-build-complete) | Event-driven + cron notification workflows | 1 | VH | Adjust schedule and message |
| `.openclaw/hooks/on-message.sh` | Inbound message router → skill dispatcher | 2 | H | Add/remove command routes |

---

### 18. E2E TEST INFRASTRUCTURE  (`e2e/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `helpers/test-lock.js` | File-based concurrency lock with stale-lock override (30 min) | 1 | VH | None |
| `global-setup.js` | Acquire test lock before suite | 1 | VH | None |
| `global-teardown.js` | Release test lock after suite | 1 | VH | None |
| `helpers/wait-utils.js` | `waitForSpaRender`, `waitForTableRows`, `waitForUiSettle`, `waitForElement`, `waitForElementGone` | 1 | H | Remove `loginAndNavigate` hardcoding |
| `fixtures/auth.js` | API login → localStorage injection → authed Playwright page | 2 | H | Swap auth endpoint + localStorage key |
| `fixtures/test-data.js` | Test data factories, route map, CSS selectors | 2 | M | Replace VaultLister factories + selectors |
| `helpers/api-helpers.js` | `getAuthToken`, seed/cleanup helpers | 2 | M | Swap endpoint paths + data shapes |
| `.test-baseline` | Known-flaky test count tracker — prevents CI failures without hiding them | 1 | VH | None |
| `playwright.config.js` | Playwright config: sharded workers, device matrix, global setup/teardown, webServer auto-start | 1 | VH | Swap testDir + port |

---

### 19. GITHUB TEMPLATES  (`.github/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `ISSUE_TEMPLATE/bug_report.md` | Steps to reproduce, expected/actual, environment | 1 | VH | None |
| `ISSUE_TEMPLATE/feature_request.md` | Use case, proposed solution, alternatives | 1 | VH | None |
| `PULL_REQUEST_TEMPLATE.md` | Summary, test plan, breaking changes, DB changes, screenshots | 1 | VH | Rename "Database Changes" if no DB |

---

### 20. CONFIGURATION FILES  (root)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `bunfig.toml` | Bun test root directory config | 1 | VH | Change testRoot if needed |
| `.env.example` | Comprehensive env var reference organized by category | 2 | H | Remove marketplace OAuth vars; keep structure |
| `.mcp.json` | GitHub + filesystem + memory MCP server configuration | 1 | VH | Update token env var names |
| `AGENTS.md` | Governance rules: no runtime changes, no variant suffixes, minimum validation steps | 2 | H | Swap contract paths + file references |

---

### 21. RUNBOOK SYSTEM  (`runbook/`)

| File | What It Does | Tier | Reusability | Adapt? |
|------|-------------|------|------------|--------|
| `all.ps1` | PowerShell orchestrator: loads state → runs step sequence → generates checklist | 2 | H | Swap step names + order |
| `_bootstrap.ps1` | Repo root validation, error preferences setup | 1 | VH | Minimal (verify root detection) |
| `_state.ps1` | JSON-based step status persistence (load/save) | 1 | VH | None |
| `_helpers.ps1` | `Write-Evidence`, `Update-Dashboard`, `ConvertTo-PlainHashtable` | 2 | M | Parametrize hardcoded evidence paths |
| `_checklist.ps1` | Step freshness check (<48h), gate validation | 2 | M | Refactor hardcoded step names to registry |
| `steps/LINT_SYNTAX.ps1` | Run linter | 1 | VH | Swap CLI command |
| `steps/ENV_SANITY.ps1` | Validate required env vars | 2 | H | Swap var name list |
| `steps/MONITORING_EVIDENCE.ps1` | Hit /health, capture response | 2 | H | Parametrize URL |
| `steps/BACKUP_EVIDENCE.ps1` | Backup DB, log metadata | 2 | H | Abstract from SQLite |
| `steps/DEPLOYMENT_EVIDENCE.ps1` | Validate Docker image | 1 | H | Generic Docker |
| `steps/PERFORMANCE_EVIDENCE.ps1` | Run Lighthouse audit | 1 | VH | Generic |
| `steps/SMOKE_PLAYWRIGHT.ps1` | Run Playwright smoke tests | 1 | VH | Generic |

---

### 22. DOCUMENTATION TEMPLATES  (`claude-docs/`, `docs/`)

| Item | What It Does | Tier | Reusability |
|------|-------------|------|------------|
| `ARCHITECTURE.md` (format) | Tech stack table, folder structure, ADR list, runtime model, stable interfaces | 2 | H |
| `claude-docs/COMMAND_CHEATSHEET.md` | Decision tree + command reference | 2 | H |
| `claude-docs/docs/project-control/` | STATE_SNAPSHOT, PROJECT_ROADMAP, PROGRESS_ACCOUNTING, RISK_REGISTER templates | 1 | VH |
| Design folder structure (INDEX, Executive-Summary, Feature-Specs, Data-Model, Architecture) | Design-first project template | 1 | VH |

---

## Tier Summary

**Tier 1 — Copy-Paste Ready (220+ assets):** Works as-is, zero or 1-line adaptation.
Key examples: csrf.js, rateLimiter.js, errorHandler.js, logger.js, store.js, toast.js, websocketClient.js, ar-preview.js, rate-limits.js, sw.js, offline.html, nginx.conf, Dockerfile, ci.yml, validate-bash.sh, commit-msg hook, all agent SKILL.md files, GitHub templates, .openclaw templates, test-lock.js, global-setup/teardown, bunfig.toml, .mcp.json, STATUS.md, env.js, notion.js, kill-port.js, server-manager.js, migration runner.

**Tier 2 — Adapt Before Reuse (60+ assets):** 60–90% reusable, strip domain parts.
Key examples: api.js (web + mobile), router.js, auth.js, components.js, main.css, authStore.js (mobile), autofill.js (extension), docker-compose.yml, pre-commit hook, listing-generator.js, price-predictor.js, session-start/end, MEMORY.md.

**Tier 3 — Pattern / Architecture Only:** Not worth extracting as code; replicate the design.
- Route-based lazy chunk loading pattern (router.js architecture)
- Offline-first API client (IndexedDB queue pattern)
- CLI↔Bot coordination via STATUS.md + OpenClaw
- Known-failure baseline CI pattern
- Multi-stage Docker build with non-root user

**Not Reusable (domain-specific only):**
- All `src/backend/routes/` (inventory, listings, offers, automations)
- All `src/frontend/pages/` and `src/frontend/handlers/`
- `src/shared/automations/poshmark-bot.js` selectors/workflows
- All `src/backend/db/migrations/` content (96 SQL files)
- `config/settings.json` marketplace platform specs

---

## Recommended Additions (Not in This Project)

These are universally valuable patterns absent from VaultLister 3.0 that should be in any serious starter-kit:

| Pattern | Why Universal | Suggested Tool |
|---------|--------------|----------------|
| **Internationalization (i18n)** | Any user-facing app that may expand to other languages | `i18next` (web/RN), `react-i18next` |
| **Feature flags** | Safe progressive rollout without redeployment | Custom JSON config + env toggle; or `@unleash/client` |
| **Request body schema validation** | Prevent malformed data from ever hitting business logic | `zod` or `joi` in middleware |
| **Env var schema validation** | Fail fast on missing config at startup, not at runtime | `zod.parse(process.env)` in server startup |
| **Email service abstraction** | Any app that sends transactional emails | Abstraction layer over SMTP/SendGrid/Postmark |
| **Structured payment integration** | Any monetized product | Abstraction over Stripe; webhook handler template |
| **Job queue / background workers** | Deferred processing, retries, scheduling | `BullMQ` (Redis-backed); or Bun's built-in queuing |
| **Response caching** | Reduce DB load on expensive read endpoints | `Cache-Control` + ETag headers pattern |
| **OpenTelemetry tracing** | End-to-end request tracing across services | `@opentelemetry/sdk-node` |
| **Health check standard** | Kubernetes-style liveness + readiness probes | `/health/live` + `/health/ready` with JSON response |
| **API versioning strategy** | Prevent breaking changes for API consumers | `/api/v1/` prefix + deprecation header pattern |
| **Per-user rate limiting** | IP-based limiting misses shared IPs (offices/NATs) | Extend `rateLimiter.js` to key on `user_id` |
| **GDPR consent management** | Required for any EU-facing product | Consent banner + preference store pattern |
| **Cookie-based auth alternative** | HttpOnly cookies are more secure than localStorage tokens | Middleware flag: `authMode: 'cookie' | 'header'` |
| **Secrets rotation** | Critical env vars should rotate without redeployment | Vault / AWS Secrets Manager abstraction layer |
| **Dark launch / canary** | Progressive feature rollout to % of users | `featureFlag('new-feature', { rollout: 0.1 })` |
| **Outbound webhook delivery** | Allow integrations to subscribe to app events | Event queue → delivery + retry + signature |
| **Content delivery (image CDN)** | Direct file serving doesn't scale; images need CDN | Cloudflare Images / imgix integration pattern |
| **A/B testing infrastructure** | Data-driven product decisions | Variant assignment + event tracking pattern |
| **Mobile deep linking** | Universal Links (iOS) / App Links (Android) | Config file + server-side redirect handler |
| **Push notification segmentation** | FCM in place but no audience targeting | Device group / topic subscription pattern |
| **Database encryption at rest** | SQLite stores plaintext; sensitive apps need encryption | `better-sqlite3-sqlcipher` or WAL encryption |
| **Stale-while-revalidate API pattern** | Serve cached data immediately, refresh in background | Service Worker + Cache API or server-side SWR |

---

## Verification

When an asset is extracted to the starter-kit, verify reuse by:

1. Create a blank test project: `mkdir test-app && cd test-app && bun init`
2. Copy the target package in
3. Write a minimal integration test using only its public API
4. Confirm zero imports from VaultLister-specific paths (grep for `inventory`, `listing`, `platform`, `poshmark`)
5. For middleware: spin up a minimal Bun HTTP server; hit with a test client
6. For frontend packages: open in a browser with no backend — no console errors
7. For CI templates: run against a hello-world repo; all steps should pass
8. For Claude hooks: run a test session; hooks should fire and gracefully no-op if unconfigured

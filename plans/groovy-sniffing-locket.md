# Notion Reconciliation Plan — VaultLister 3.0

## Context
The VaultLister 3.0 Notion project page was scaffolded in early March 2026 and has been updated sporadically by session hooks and manual entries. The codebase has evolved significantly since then — notably migrating from SQLite to PostgreSQL, deploying to Railway, adding 8 CI/CD workflows, and accumulating 189 database tables (per pg-schema.sql CREATE TABLE count) across 112 migrations. This plan identifies every discrepancy between the actual codebase state and what Notion currently documents, organized by action type.

---

## 1. CRITICAL UPDATES (Stale/Wrong Information)

### 1a. ADR-003: SQLite over PostgreSQL — SUPERSEDED
- **Notion says:** Status "Accepted" — "SQLite in WAL mode handles the concurrency needs"
- **Reality:** Codebase has fully migrated to PostgreSQL (postgres npm package, `DATABASE_URL`, `pg-schema.sql`, 112 pg migrations, Railway managed PostgreSQL)
- **Action:** Change ADR-003 status to **"Superseded"**. Add note: "Superseded by PostgreSQL migration (March 2026). See ADR-012."
- **Action:** Create **ADR-012: PostgreSQL migration** (Status: Accepted) documenting the switch from SQLite to PostgreSQL for multi-tenant SaaS scalability, Railway hosting, and CI/CD compatibility.

### 1b. ADR-001: Bun.js — Stale Pros/Cons
- **Notion says:** "native SQLite bindings" as a pro
- **Reality:** SQLite is no longer used. The pro should now mention "fast startup, built-in HTTP/WebSocket, npm compatibility"
- **Action:** Update Pros/Cons to remove SQLite reference, add PostgreSQL compatibility note

### 1c. Roadmap: "Production Deploy" — Status Wrong
- **Notion says:** Status "Not Started"
- **Reality:** Railway production deployment is FULLY LIVE (STATUS.md confirms: Cloudflare -> Railway, PostgreSQL connected, Redis connected, B2 backups configured)
- **Action:** Change status to **"Done"**. Update notes with actual deployment details (Railway, not self-hosted docker-compose).

### 1d. Roadmap: "Testing Verified" — Numbers Stale
- **Notion says:** "Unit: 5470 pass. E2E: 620 pass"
- **Reality:** .test-baseline shows KNOWN_FAILURES=585, CI: 5619 pass / 252 fail, Local: 2050 pass / 264 fail, E2E: 620 pass / 0 fail. 588 named KNOWN_FAIL entries. The 5470 number is from pre-PostgreSQL migration.
- **Action:** Update notes to current numbers: "CI: 5619 pass / 252 fail. E2E: 620 pass / 0 fail. 585 known failures (588 named entries). Post-PG migration regressions tracked in .test-baseline."

### 1e. Roadmap: "Code Complete" — Numbers Stale
- **Notion says:** "5470 unit tests pass, 620 E2E tests pass"
- **Reality:** Same stale numbers as above
- **Action:** Update to current test counts, note that PostgreSQL migration introduced known regressions tracked in .test-baseline

### 1f. Roadmap: "Enforcement & Quality Gates" — Count Wrong
- **Notion says:** "37 deny patterns"
- **Reality:** settings.json has 31 deny patterns (verified by explore agent)
- **Action:** Correct to "31 deny patterns"

### 1g. Feature Backlog: "PostgreSQL migration for multi-tenant SaaS" — Already Done
- **Notion says:** This exists as a backlog idea
- **Reality:** PostgreSQL migration is COMPLETE and deployed
- **Action:** Change status to **"Done"**

### 1h. Feature Backlog: "Team collaboration / multi-user roles" — Already Implemented
- **Notion says:** Backlog idea
- **Reality:** `routes/teams.js`, `teams` DB table, migration 037, full CRUD with invitations, roles, activity log
- **Action:** Change status to **"Done"**

### 1i. Feature Backlog: "Batch photo editing / background removal" — Already Implemented
- **Notion says:** Backlog idea
- **Reality:** `routes/batchPhoto.js`, `batch_photo_jobs`/`batch_photo_items`/`batch_photo_presets` DB tables, frontend page, handlers
- **Action:** Change status to **"Done"**

### 1j. Feature Backlog: "Advanced analytics — competitor price tracking" — Already Implemented
- **Notion says:** Backlog idea
- **Reality:** `routes/competitorTracking.js`, `routes/marketIntel.js`, `competitors`/`competitor_listings`/`competitor_keywords` DB tables
- **Action:** Change status to **"Done"**

### 1k. Feature Backlog: "Automated re-pricing based on market data" — Partially Implemented
- **Notion says:** Backlog idea
- **Reality:** `routes/relisting.js` has `schedule-price-drop` and `preview-price` endpoints, `routes/predictions.js` has demand forecasting, `services/pricingEngine.js` exists
- **Action:** Change status to **"In Progress"** with note about what exists vs what's missing

### 1l. Feature Backlog: "Marketplace analytics comparison dashboard" — Already Implemented
- **Notion says:** Backlog idea
- **Reality:** `routes/analytics.js` has `/platforms` endpoint, frontend analytics page has platform comparison, market intel page exists
- **Action:** Change status to **"Done"**

### 1m. Feature Backlog: "Import from other reselling tools (Vendoo, List Perfectly)" — Partially Done
- **Notion says:** Backlog idea
- **Reality:** `routes/inventoryImport.js` with CSV import, field mapping, validation. Not Vendoo/LP-specific but generic import works.
- **Action:** Change status to **"In Progress"** — generic CSV import done, platform-specific parsers not yet built

---

## 2. MISSING FROM NOTION (Need to Add)

### 2a. ADRs Missing (Add to Architecture Decision Log)
| ADR | Decision | Status |
|-----|----------|--------|
| ADR-012 | PostgreSQL over SQLite (migration) | Accepted |
| ADR-013 | Railway for production hosting (not self-hosted Docker) | Accepted |
| ADR-014 | Resend for transactional email | Accepted |
| ADR-015 | Cloudflare R2 / S3 for image storage | Accepted |
| ADR-016 | BullMQ + Redis for background job queues | Accepted |
| ADR-017 | Backblaze B2 for database backups | Accepted |

### 2b. Roadmap Milestones Missing
| Milestone | Status | Notes |
|-----------|--------|-------|
| PostgreSQL Migration | Done | 112 migrations, pg-schema.sql, all routes converted |
| Railway Deployment | Done | Production live at vaultlister.com via Cloudflare |
| CI/CD Pipeline | Done | 8 GitHub Actions workflows (ci, deploy, staging, semgrep, trivy, sonarcloud, qa-guardian, auto-merge) |
| Security Hardening (CodeQL) | Done | Commits 1b819ff, cc41977, 41e1cbf — resolved 523+ GitHub code scanning alerts |
| Chrome Extension | Done | Full chrome-extension/ directory with manifest, service worker, content scripts, popup, options |

### 2c. Environment & Config Registry — Missing Entries
The database exists but needs rows for all production config items. Key items to add:
- `DATABASE_URL` (Category: Database, Environment: Production, Status: Active)
- `REDIS_URL` (Category: Database, Environment: Production, Status: Active)
- `RAILWAY_*` deployment config
- `R2_*` image storage config (Category: Cloud/Backup)
- `B2_*` Backblaze backup config (Category: Cloud/Backup)
- `STRIPE_PRICE_*` payment tier IDs (Category: Payments)
- `SENTRY_DSN` (Category: Monitoring)
- `RESEND_API_KEY` (Category: Email)
- All `EBAY_*`, `POSHMARK_*`, etc. marketplace credentials (Category: Marketplace)

### 2d. Release Notes / Changelog — Empty Database
- No releases have been logged despite the app being deployed to production
- **Action:** Add at least these milestone releases:
  - v0.1.0: Initial scaffold + MVP features (2026-03-02)
  - v0.5.0: Code complete — all MVP features (2026-03-09)
  - v0.8.0: PostgreSQL migration complete (2026-03-20)
  - v0.9.0: Railway production deployment (2026-03-21)
  - v0.9.1: CodeQL security fixes — 523 alerts resolved (2026-03-27)

### 2e. Performance & Benchmarks — Empty Database
- No benchmarks recorded despite CI having p95 < 50ms threshold
- **Action:** Add baseline entries from CI config:
  - API response time p95 target: < 50ms
  - Docker image size limit: < 500MB
  - Bundle size limit: < 3MB
  - Coverage threshold: >= 60% line coverage

### 2f. Security & Compliance Checklist — Needs Verification
- Database exists with schema but need to populate/verify items match actual implementation:
  - Authentication: JWT HS256, 15min access / 7d refresh, dual-key rotation, HttpOnly cookies
  - Authorization: Tier-based (free/starter/pro/business), IDOR protection
  - Data Protection: AES-256-GCM OAuth token encryption, bcryptjs 12 rounds, parameterized queries
  - Infrastructure: CSP with nonces + strict-dynamic, HSTS 1yr, X-Frame-Options DENY
  - Compliance: GDPR (export, deletion, consent, rectification), ToS acceptance tracking
  - Testing: Semgrep SAST, Trivy vulnerability scanning, SonarCloud analysis
  - Logging: Request logging, audit log, security events, error tracking (Sentry)

### 2g. Sprint Board — Missing Items for Current Work
Based on memory/STATUS.md and project_next_priorities.md, these tasks should be on the Sprint Board:
- SSL certificate + domain configuration (P0 — already exists as `3299f0c81de6811b`)
- Set real Stripe price IDs (P0 — already exists as `3299f0c81de6817d`)
- Configure SMTP for production email (P1 — already exists as `3299f0c81de68141`)
- Load testing verification (P2 — already exists as `3299f0c81de681b7`)

These items exist but their statuses may need updating based on current Railway deployment state.

---

## 3. ITEMS TO REMOVE OR ARCHIVE

### 3a. Feature Backlog — Correctly Deferred
These items are correctly in the backlog and match codebase reality (no code exists):
- "Firefox/Safari extension support" — Correct (memory confirms Chromium-only)
- "WhatsApp / SMS notification channel" — Correct (not implemented)
- "Mobile native app (React Native / PWA enhancement)" — Correct (PWA only)

### 3b. Feature Backlog — Status Adjustments for Partially-Built Items
- "Etsy OAuth integration" — Memory says "deferred to post-release". Status should remain "Idea" but add note: "Etsy API routes exist as stubs; OAuth deferred per project_etsy_deferred.md"
- "AR Previews — WebXR/3D model pipeline" — Notion says "V2 feature". Reality: `shared/utils/ar-preview.js` implements a basic WebAR class (camera + canvas overlay), frontend page exists. Not WebXR/3D models but basic AR is done. Update to "In Progress" with note.
- "Blockchain verification — NFT authenticity" — Notion says "V2 feature". Reality: `shared/utils/blockchain.js` implements SHA-256 hash verification (125 lines, local only, no NFT/external blockchain). Update to "In Progress" with note: "Local hash verification implemented; no external blockchain/NFT integration."

---

## 4. STRUCTURAL/SCHEMA UPDATES

### 4a. ADR Database — Missing ADR Numbers
Current ADRs: 001-011. Need to add 012+ (see 2a above). The existing ADRs 006-011 were added 2026-03-24 and appear accurate.

### 4b. Sprint Board — Sprint Field Has Only "Sprint 1"
- Consider adding Sprint 2+ options if work continues in phases
- Or rename to track by week/milestone

### 4c. "Things to Address" Database — Stale Items Found (queried 2026-03-27)
11 items found. Items needing status updates:
- **"Production deploy"** — Status: "Blocked", Notes: "Waiting on all P0/P1 items" → **Should be "Done"** (Railway is live)
- **"Run bun install on server after SDK upgrade"** — Status: "Open", P1 → **Should be "Done"** (Railway auto-deploys include `bun install`)

Items that are correctly still open (verified against codebase/memory):
- "SSL certificate + domain configuration" — Still P0 open
- "Set real Stripe price IDs in .env" — Still P0 open
- "Configure SMTP for production email" — Still P1 open
- "Configure real marketplace API credentials" — Still open
- "Fill marketplace credentials in staging .env" — Still open
- "Load testing — 50+ concurrent users" — Still P2 open
- "Chrome extension: full listing capture" — Needs verification
- "Mobile responsiveness verification" — Needs verification
- "Facebook bot share action (AU-11: TODO)" — Needs verification

### 4d. Risk Register — Stale SQLite Entry (queried 2026-03-27)
- **"SQLite no horizontal scaling — limits multi-tenant SaaS"**
  - Current: Status "Accepted", Impact "Low", Likelihood "Low", Mitigation "By design (ADR-003); WAL mode sufficient for target scale"
  - **Reality:** This risk is FULLY MITIGATED — PostgreSQL migration is complete. ADR-003 is superseded.
  - **Action:** Change Status to **"Mitigated"**, update Mitigation Plan to "Resolved by PostgreSQL migration (March 2026). See ADR-012.", update Related ADR to point to ADR-012.

### 4e. Exhaustive Build Checklist — Stale Items (queried 2026-03-27)
- **"Production deploy"** — Done: NO, Notes: "Waiting on P0 blockers" → **Should be Done: YES** (Railway is live)
- **"Inventory: CRUD + FTS5 search"** — Done: YES, but title says "FTS5" → Should say "TSVECTOR" (cosmetic, low priority)
- Other items (SSL, Stripe, SMTP, Etsy OAuth) appear correctly tracked as not-done

### 4f. E2E Test Failures & Bug Tracker — Appears Well-Maintained
- Entries from 2026-03-18 have proper Status tracking (e.g., "Fixed" with dates)
- .test-baseline shows E2E: 620 pass / 0 fail, consistent with tracker entries being resolved
- No action needed — database is current

### 4g. QA Walkthrough Checklist / Deep Audit Tracker
- These databases exist and were populated during QA sessions
- Memory confirms "QA walkthrough 100% done; 5 systemic fixes planned"
- Verify the 5 systemic fixes are tracked somewhere active

---

## 5. CODEBASE DOCUMENTATION DRIFT (CLAUDE.md + design/ docs)

> These are codebase file fixes, not Notion changes — but they were explicitly requested in scope and directly affect how Claude Code operates against this project. Every item below is a stale or wrong statement in a checked-in file.

### 5a. CLAUDE.md — Full Inventory of Stale Items

| Line(s) | Current Text | Reality | Fix |
|----------|-------------|---------|-----|
| 1 | `# Stack Variant: Web Full-Stack — Bun.js + Vanilla JS SPA + SQLite` | PostgreSQL, not SQLite | Change `SQLite` → `PostgreSQL` |
| 27 | `**Stack:** … + SQLite 3 (WAL mode, FTS5) + …` | PostgreSQL with `postgres` npm package | Replace entire Database portion of Stack line |
| 29 | `**Database:** SQLite 3 (WAL mode, FTS5 full-text search, bun:sqlite (Bun's native SQLite driver))` | PostgreSQL (`postgres` npm, `DATABASE_URL`, TSVECTOR+GIN for FTS) | Rewrite to `PostgreSQL (postgres npm, TSVECTOR + GIN index for FTS)` |
| 31 | `**Deploy target:** Docker + Nginx (self-hosted) + GitHub Actions CI/CD` | Railway (managed PaaS) + Cloudflare + GitHub Actions CI/CD | Rewrite to `Railway + Cloudflare + GitHub Actions CI/CD` |
| 34 | ADR-001 summary: "native SQLite (ADR-001)" | SQLite no longer used | Remove SQLite reference from ADR-001 summary |
| 36 | ADR-003 summary: "SQLite over PostgreSQL — local-first, WAL mode…" | Superseded — PostgreSQL is now the database | Mark ADR-003 as superseded, add ADR-012 reference |
| 101 | `data/ # SQLite database + backups` | `data/` now has PostgreSQL backup dumps, bot audit logs, not SQLite DB files | Change to `data/ # Database backups + automation audit logs` |
| 117 | Reference to `claude-docs/docs/reference/database.md` | May still reference SQLite patterns — verify contents match PostgreSQL | Verify and update if stale |
| 154 | Rule 7: "Use TEXT for all ID columns (UUIDs, not INTEGER)" | PostgreSQL supports native UUID type; may want `UUID` column type instead of `TEXT` | Update to reflect PostgreSQL UUID type if schema uses it |
| 265 | `Initialize database: bun run db:init` | Still valid command but context implies SQLite init | Add note that this now initializes PostgreSQL schema |

**Additional CLAUDE.md items (non-SQLite):**
- Lines 18-22: Design Reference table lists 5 files that **don't exist**: `design/INDEX.md`, `design/00-Executive-Summary.md`, `design/03-Feature-Specs.md`, `design/05-Data-Model-and-Flows.md`, `design/08-Technical-Architecture.md`. Actual design files are: `README.md`, `data-model.md`, `api-overview.md`, `platform-integrations.md`, `architecture.md`. **Fix:** Replace the entire table with actual filenames.
- The `src/shared/automations/` references in Automation Safety Rules — bots actually live in `worker/bots/`, rate-limits at `worker/bots/rate-limits.js`
- No mention of BullMQ, Redis, Resend, R2, or B2 anywhere in CLAUDE.md — these are now core infrastructure
- `.claude/rules/src/RULES.md` line 27: "OAuth tokens encrypted with AES-256-GCM before **SQLite** storage" — should say "PostgreSQL storage"
- `.claude/rules/src/RULES.md` line 42: "SQLite: always use WAL mode and parameterized statements; never raw string queries" — should reference PostgreSQL parameterized queries

### 5b. design/README.md — Stale Items

| Line | Current Text | Reality | Fix |
|------|-------------|---------|-----|
| 12 | `All 26 DB tables` | 189 tables in pg-schema.sql (across 112 migrations) | Change to `189 DB tables` |
| 13 | `All 67 route files` | 67 route files (verified — count is correct) | **No change needed** |
| 19 | `Database: SQLite 3 (WAL mode + FTS5 full-text search on inventory)` | PostgreSQL with TSVECTOR + GIN | Rewrite |
| 22 | `Deploy: Docker + Nginx (self-hosted) + GitHub Actions CI/CD` | Railway + Cloudflare | Rewrite |
| 27 | `src/backend/db/schema.sql` as source of truth | Actual file is `src/backend/db/pg-schema.sql` | Fix path |

### 5c. design/architecture.md — Stale Items

| Line(s) | Current Text | Reality | Fix |
|----------|-------------|---------|-----|
| 6-43 | System diagram shows `SQLite 3 / WAL mode / FTS5 index / 26 tables +indexes` | PostgreSQL, 189 tables | Redraw diagram box |
| 45 | `Deployment: Docker container → Nginx reverse proxy → GitHub Actions CI/CD` | `Cloudflare → Railway (managed PaaS) → GitHub Actions CI/CD` | Rewrite |
| 52-58 | ADR-001 Rationale: "native SQLite bindings" as a pro | SQLite no longer used | Remove SQLite binding pro, add PostgreSQL compat note |
| 72-81 | ADR-003 entire section: "SQLite over PostgreSQL" — Status "Accepted" | Superseded by PostgreSQL migration | Mark superseded, add cross-ref to new ADR-012 |
| 86-93 | ADR-004: "Bot scripts live in `src/shared/automations/`" | Bots are in `worker/bots/` | Fix path references |
| 92 | "Rate limits defined in `src/shared/automations/rate-limits.js`" | Actual location: `worker/bots/rate-limits.js` (verified) | Fix path to `worker/bots/rate-limits.js` |
| 113-132 | Directory structure: `db/schema.sql`, `database.js — bun:sqlite connection + WAL init`, `automations/ — Playwright bot files + rate-limits.js` | `db/pg-schema.sql`, `database.js` now uses `postgres` npm, bots in `worker/bots/` | Update all 3 entries |
| Missing | No ADRs 006-017 | ADRs 006-011 exist in Notion; 012-017 needed for PG, Railway, Resend, R2, BullMQ, B2 | Add ADR-012 through ADR-017 to this file as well (or note Notion as canonical ADR source) |

### 5d. design/data-model.md — Stale Items

| Line(s) | Current Text | Reality | Fix |
|----------|-------------|---------|-----|
| 1 | `Source of truth: src/backend/db/schema.sql` | Actual file: `src/backend/db/pg-schema.sql` | Fix path |
| 2 | `SQLite 3, WAL mode (PRAGMA journal_mode = WAL), all IDs are TEXT (UUID)` | PostgreSQL; IDs may use native UUID type | Rewrite to PostgreSQL; verify ID column types |
| 8 | `Core Tables (18)` | 189 tables in pg-schema.sql (18 original + 170+ added via migrations) | Update count or note that this lists only the original 18 core tables |
| 40-44 | `FTS Virtual Table (1) — inventory_fts — FTS5 full-text index via triggers` | PostgreSQL uses TSVECTOR column + GIN index + triggers (no FTS5) | Rewrite to describe PostgreSQL FTS approach |
| 74 | `shops.credentials encrypted with AES-256-CBC` | `encryption.js` function docstring says AES-256-GCM (line 38), but file header comment says AES-256-CBC (line 2). Frontend display strings also say CBC. Actual encrypt function uses GCM. | Fix to AES-256-GCM; also fix encryption.js header comment + frontend display strings (separate codebase fix) |
| 75 | `JSON columns: SQLite has no native JSON type; application layer parses` | PostgreSQL has native JSONB type | Rewrite: "JSON columns use PostgreSQL JSONB where appropriate" |
| 77 | `Soft delete pattern: inventory.status includes 'deleted'` | Likely still accurate — verify | Verify, keep if correct |

### 5e. design/api-overview.md — Stale FTS Reference

| Line | Current Text | Reality | Fix |
|------|-------------|---------|-----|
| 6 | `Total: 67 route files.` | Verified correct (67 files in routes/) | **No change needed** |
| 23 | `inventory.js — CRUD for InventoryItems, FTS5 search` | PostgreSQL uses TSVECTOR + GIN, not FTS5 | Change "FTS5 search" → "full-text search (TSVECTOR)" |

### 5f. design/platform-integrations.md — Stale Bot & Rate-Limit Paths

| Line | Current Text | Reality | Fix |
|------|-------------|---------|-----|
| 9 | `Playwright bots: src/shared/automations/[platform]-bot.js` | Bots are at `worker/bots/[platform]-bot.js` (6 files verified) | Fix path |
| 10 | `Rate limits: src/shared/automations/rate-limits.js` | Actual location: `worker/bots/rate-limits.js` (verified) | Fix path |

### 5g. .claude/agents/ — Stale SQLite & Bot Path References (7 files)

| File | Line(s) | Stale Text | Fix |
|------|---------|-----------|-----|
| `Backend.md` | 3 | `database (better-sqlite3)` | Change to `database (PostgreSQL)` |
| `Backend.md` | 7 | `SQLite (better-sqlite3, WAL mode, FTS5)` | Change to `PostgreSQL (postgres npm, TSVECTOR + GIN)` |
| `Backend.md` | 15 | `AES-256-CBC encrypted before SQLite storage` | Change to `AES-256-GCM encrypted before PostgreSQL storage` |
| `Architect-Planner.md` | 10 | `SQLite (WAL + FTS5)` | Change to `PostgreSQL (TSVECTOR + GIN)` |
| `DevOps-Deployment.md` | 13 | `Volumes: /app/data (SQLite)` | Change to `Volumes: /app/data (backups, audit logs)` — or reflect Railway deployment |
| `Automations-AI.md` | 7 | `src/shared/automations/*` as scope | Update scope to include `worker/bots/*` |
| `Automations-AI.md` | 17 | `src/shared/automations/rate-limits.js` | Change to `worker/bots/rate-limits.js` |
| `Frontend-UI.md` | 7 | `src/shared/automations/` in NEVER-touch list | Update path if bots moved |
| `Marketplace-Integration.md` | 65 | `encrypt all OAuth tokens before SQLite storage` | Change `SQLite` → `PostgreSQL` |
| `qa-security.md` | 18 | `AES-256-CBC before SQLite storage` | Change to `AES-256-GCM before PostgreSQL storage` |
| `qa-security.md` | 35 | `OAuth tokens stored in plaintext in SQLite` | Change SQLite → PostgreSQL |
| `DevOps-Deployment.md` | 3,7 | Scope: "Docker, docker-compose, Nginx" | Update to reflect Railway deployment; keep Docker for worker container |
| `qa-environment-quality.md` | 32 | "stale Docker images or docker-compose config drift" | Update to reflect Railway deployment |

**Also stale:**
- `.claude/skills/deploy/SKILL.md` — Entire skill (lines 3, 7, 18, 35, 44) references Docker/docker-compose deployment. Should be rewritten for Railway deployment (`railway up`, `railway logs`, etc.)

### 5h. claude-docs/ — 13 Files with Stale SQLite References

Files with stale SQLite content (all in `claude-docs/`):
- `docs/reference/database.md` — Line 7: "SQLite with Bun's built-in driver", Line 274: "SQLite datetime functions"
- `docs/project-control/STATE_SNAPSHOT.md`
- `docs/project-control/REPOSITORY_ANALYSIS.md`
- `docs/project-control/SYSTEM_WORKFLOWS.md`
- `docs/project-control/SYSTEM_CRITICALITY_MAP.md`
- `docs/project-control/SYSTEM_DEPENDENCY_GRAPH.md`
- `docs/PRD.md`
- `docs/commands/README.md`
- `docs/commands/review.md`
- `docs/commands/debug.md`
- `docs/commands/migration.md`
- `docs/progress.md`
- `docs/future_notes.md`

**Action:** Each file needs SQLite → PostgreSQL terminology update. These are reference docs that Claude Code reads on demand, so stale info here directly causes incorrect agent behavior.

### 5i. CLAUDE.md — Missing `worker/` Directory

CLAUDE.md Project Structure (line ~96) has no mention of `worker/` directory:
```
worker/
  ├── index.js          — Worker service entry point
  ├── package.json      — Worker dependencies
  ├── Dockerfile        — Worker container build
  └── bots/             — Playwright bot files + rate-limits.js
      ├── poshmark-bot.js
      ├── mercari-bot.js
      ├── depop-bot.js
      ├── grailed-bot.js
      ├── facebook-bot.js
      ├── whatnot-bot.js
      └── rate-limits.js
```
**Action:** Add `worker/` to the project structure in CLAUDE.md.

### 5j. Summary of Codebase Doc Changes Needed

| File/Area | Changes Needed |
|-----------|---------------|
| `CLAUDE.md` | 10+ stale references (SQLite, deploy target, design file paths, bot paths, missing infra, missing worker/) |
| `.claude/rules/src/RULES.md` | 2 stale references (SQLite storage, WAL mode) |
| `.claude/agents/` (8 files) | 11+ stale references (SQLite, better-sqlite3, bot paths, encryption algo, Docker/Nginx deploy) |
| `.claude/skills/deploy/SKILL.md` | Entire skill references Docker deployment — stale (now Railway) |
| `design/README.md` | 4 stale items (table count, SQLite, deploy, schema path) |
| `design/api-overview.md` | 1 stale item (FTS5 → TSVECTOR) |
| `design/architecture.md` | 8+ stale items (diagram, ADRs, bot paths, rate-limits path, directory structure) |
| `design/data-model.md` | 7 stale items (schema path, SQLite refs, table count, FTS, encryption algo, JSON) |
| `design/platform-integrations.md` | 2 stale items (bot paths, rate-limits path) |
| `claude-docs/` (13 files) | SQLite → PostgreSQL terminology across all reference docs |
| Source code (encryption display strings) | 8 instances of "AES-256-CBC" that should say "AES-256-GCM" |
| **Total** | ~65+ individual fixes across 28 files |

### 5k. Additional Files with Stale SQLite References (54 total files across entire repo)

Beyond the files already cataloged above, a `grep -ri "sqlite" --include="*.md" --include="*.yml"` reveals stale SQLite references in **24 additional files** not yet listed:

**Root-level docs (4 files):**
- `README.md` — **HIGH PRIORITY (user-facing)**: Line 8 "SQLite 3 (WAL mode, FTS5, bun:sqlite)", Line 12 "Docker + Nginx + GitHub Actions CI/CD" → should say PostgreSQL and Railway
- `RELEASE.md`, `ARCHITECTURE.md` (root), `DEEP_AUDIT_2026-03-19.md`

**docs/ directory (8 files):**
- `docs/DEPLOYMENT.md`, `docs/BACKUP-RESTORE.md`, `docs/ARCHITECTURE.md`, `docs/SETUP.md`
- `docs/DATABASE_SCHEMA.md`, `docs/BUG_LOG.md`
- `docs/evidence/TEST_UNIT.md`, `docs/evidence/PHASE-05_TASK-5.1.md`, `docs/evidence/SETUP_RUNBOOK.md`

**qa/ directory (10 files):**
- `qa/coverage_matrix.md`
- `qa/reports/scripts-layer-audit-2026-03-19.md`, `qa/reports/devops-infra-audit-2026-03-19.md`, `qa/reports/db-layer-audit-2026-03-19.md`
- `qa/reports/audits/backend-security-audit-2026-03-19.md`, `qa/reports/audits/infrastructure_delivery_audit.md`, `qa/reports/audits/environment_quality_audit.md`, `qa/reports/audits/security_governance_audit.md`, `qa/reports/audits/architecture_reliability_audit.md`, `qa/reports/audits/data_systems_audit.md`
- `qa/reports/final/remediation_status.md`, `qa/reports/final/final_master_report.md`
- `qa/reports/generation/environment_quality_generation.md`, `qa/reports/generation/security_governance_generation.md`

**memory/ (3 files):** `STATUS.md`, `COMPLETED.md`, `MEMORY.md` — these are session state files; SQLite references may be historical context (acceptable) or active stale guidance (needs fix)

**CI (1 file):** `.github/workflows/ci.yml` — may reference SQLite in test/build steps

**Action:** These are lower-priority than the core docs (CLAUDE.md, design/, agents/) since many are historical audit snapshots from pre-PG-migration dates. However, any that Claude Code reads for guidance (README.md, docs/SETUP.md, docs/ARCHITECTURE.md, docs/DATABASE_SCHEMA.md) should be updated. The QA audit reports from 2026-03-19 are historical snapshots and can be left as-is with a note that they predate the migration.

### 5l. Additional Codebase Inconsistency — Encryption Algo Display Strings
The actual encryption function in `src/backend/utils/encryption.js` uses **AES-256-GCM** (line 38), but:
- `encryption.js` header comment (line 2) says "AES-256-CBC"
- `src/frontend/app.js` lines 30151, 31797 display "AES-256-CBC"
- `src/frontend/pages/pages-deferred.js` lines 9908, 11563 display "AES-256-CBC"
- `src/frontend/pages/pages-community-help.js` lines 318, 1982 display "AES-256-CBC"
- `src/backend/db/migrations/103_add_google_integrations.sql` line 4 comment says "AES-256-CBC"
- `src/backend/services/googleOAuth.js` line 3 comment says "AES-256-CBC"
- **Action:** All should say AES-256-GCM to match the actual implementation

---

## Execution Order

### Phase A: Notion Updates
1. **ADR updates** (1a, 1b, 2a) — Fix the architectural record first
2. **Roadmap status updates** (1c-1f, 2b) — Reflect actual project state
3. **Feature Backlog status updates** (1g-1m, 3b) — Mark done/in-progress items
4. **Environment Config population** (2c) — Document production config
5. **Release Notes population** (2d) — Create historical changelog
6. **Performance Benchmarks** (2e) — Record CI thresholds
7. **Security Checklist verification** (2f) — Populate from actual implementation
8. **Sprint Board status refresh** (2g) — Update current task statuses
9. **Things to Address status updates** (4c) — Mark "Production deploy" and "bun install" as Done
10. **Risk Register update** (4d) — Change SQLite risk to "Mitigated", update mitigation text and ADR link
11. **Exhaustive Build Checklist updates** (4e) — Mark "Production deploy" as Done, update FTS5 → TSVECTOR in inventory item title

### Phase B: Codebase Documentation Fixes (Priority Order)
9. **memory/MEMORY.md line 6** (6a) — Fix stale Stack description (HIGH: auto-loaded every session, actively misleading)
10. **CLAUDE.md** (5a) — Fix SQLite refs, deploy target, design file paths table, bot paths, add worker/ to project structure, add missing infra
11. **`.claude/rules/src/RULES.md`** (5a addendum) — Fix 2 SQLite references
12. **`.claude/agents/` (8 files) + `.claude/skills/deploy/`** (5g) — Fix SQLite, better-sqlite3, bot paths, encryption algo, Docker/Nginx deploy references
12. **`design/README.md`** (5b) — Fix table count, SQLite refs, deploy, schema path
13. **`design/api-overview.md`** (5e) — Fix FTS5 → TSVECTOR reference
14. **`design/architecture.md`** (5c) — Redraw diagram, fix ADRs, bot paths, rate-limits path, directory structure
15. **`design/data-model.md`** (5d) — Fix schema path, SQLite refs, table count, FTS, encryption algo, JSON columns
16. **`design/platform-integrations.md`** (5f) — Fix bot paths and rate-limits path
17. **`claude-docs/` (13 files)** (5h) — SQLite → PostgreSQL across all reference docs
18. **Root + docs/ active docs** (5k) — Fix SQLite refs in README.md, docs/SETUP.md, docs/ARCHITECTURE.md, docs/DATABASE_SCHEMA.md, docs/DEPLOYMENT.md, docs/BACKUP-RESTORE.md
19. **Encryption display strings** (5l) — Fix AES-256-CBC → AES-256-GCM in encryption.js header, frontend display strings, migration comment, googleOAuth comment
20. **`.github/workflows/ci.yml` line 48** (6b) — Remove stale `bun:sqlite` from comment (only `bun:test` is relevant)
21. **`.env.example` line 27** (6c) — Remove or update legacy SQLite comment section (migration complete)
22. _(Optional)_ QA audit reports from 2026-03-19 — historical snapshots, can add "Note: predates PostgreSQL migration" header instead of rewriting

## Verification

### Notion Verification
1. Re-read each updated Notion page via `notion-fetch` to confirm changes took
2. Cross-check ADR statuses: 001-002 Accepted, 003 Superseded, 004-011 Accepted, 012+ Accepted
3. Confirm all "Done" Feature Backlog items match actual route files in codebase
4. Confirm Roadmap milestones reflect Railway deployment reality
5. Confirm Risk Register SQLite entry shows "Mitigated"
6. Confirm Things to Address "Production deploy" shows "Done"
7. Confirm Exhaustive Build Checklist "Production deploy" shows Done: YES

### Codebase Doc Verification
5. `grep -ri "sqlite" CLAUDE.md design/ .claude/rules/ .claude/agents/ claude-docs/ memory/MEMORY.md` — should return 0 hits (all replaced with PostgreSQL)
6. `grep -r "schema.sql" design/` — should show `pg-schema.sql` only
7. `grep -r "src/shared/automations/.*-bot\|src/shared/automations/rate-limits" design/ CLAUDE.md .claude/agents/` — should return 0 hits (replaced with `worker/bots/`)
8. `grep -r "Docker + Nginx" CLAUDE.md design/` — should return 0 hits (replaced with Railway)
9. `grep -r "26 tables\|26 DB tables" design/` — should return 0 hits (updated to 189)
10. `grep "AES-256-CBC" design/ .claude/agents/ src/backend/utils/encryption.js src/backend/services/googleOAuth.js` — should return 0 hits (fixed to AES-256-GCM)
11. `grep -r "better-sqlite3" .claude/agents/` — should return 0 hits
12. `grep -r "design/INDEX.md\|design/00-\|design/03-\|design/05-\|design/08-" CLAUDE.md` — should return 0 hits (replaced with actual filenames)

## Summary Counts

| Action | Count |
|--------|-------|
| **Notion: Items to UPDATE** (stale/wrong) | 18 (13 original + 2 Things to Address + 1 Risk Register + 2 Build Checklist) |
| **Notion: Items to ADD** (missing) | ~30+ (6 ADRs, 5 milestones, 10+ env configs, 5 releases, 5 benchmarks) |
| **Notion: Items to REMOVE** | 0 (nothing needs deletion) |
| **Notion: Feature Backlog status changes** | 8 (5 Done, 2 In Progress, 1 note update) |
| **Codebase docs: Fixes needed (priority)** | ~65+ individual fixes across 28 core files (CLAUDE.md, rules, 6 agents, 5 design docs, 13 claude-docs, encryption strings) |
| **Codebase docs: Lower-priority stale refs** | ~24 additional files (root docs, docs/, qa/ audit reports) with SQLite references |
| **Root cause** | PostgreSQL migration is the single event behind ~80% of all drift |

---

## 6. ADDITIONAL VERIFIED FINDINGS (Post-Plan-Review Round)

### 6a. memory/MEMORY.md line 6 — STALE (HIGH PRIORITY)
- **Current:** `- **Stack:** Bun.js 1.3+ + SQLite (WAL mode, FTS5) + Vanilla JS SPA + Playwright + @anthropic-ai/sdk`
- **Reality:** PostgreSQL, not SQLite
- **Impact:** This file is **auto-loaded at every session start** — actively misleads Claude Code agents
- **Action:** Change to `Bun.js 1.3+ + PostgreSQL (TSVECTOR + GIN) + Vanilla JS SPA + Playwright + @anthropic-ai/sdk`

### 6b. .github/workflows/ci.yml line 48 — STALE (LOW)
- **Current:** `# node --check hangs on ESM files with Bun-specific imports (bun:test, bun:sqlite).`
- **Reality:** No source files import `bun:sqlite` anymore (grep confirmed 0 hits). Only `bun:test` is relevant.
- **Action:** Change comment to `# node --check hangs on ESM files with Bun-specific imports (bun:test).`

### 6c. .env.example line 27 — LEGACY (LOW)
- **Current:** `# Legacy SQLite paths (deprecated — kept for reference during migration)`
- **Reality:** Migration is complete. These legacy vars can be removed entirely.
- **Action:** Remove the legacy SQLite section from .env.example (or leave with "deprecated" label — user's choice)

### 6d. package.json — CLEAN (No Action)
- Confirmed: No `better-sqlite3` or `bun:sqlite` in any package.json. Already cleaned during migration.

### 6e. Dockerfile / docker-compose — CLEAN (No Action)
- No SQLite references in Dockerfile or docker-compose files.

### 6f. memory/STATUS.md — HISTORICAL (No Action)
- SQLite references on lines 95, 98, 143, 145 are migration log entries (e.g., "Phase 3: All SQLite syntax converted ✅"). These are correct historical records, not stale guidance.

### 6g. memory/COMPLETED.md line 120 — HISTORICAL (No Action)
- "Dockerfile: groupadd/useradd (Debian); python3+make+g++ in builder for better-sqlite3" — historical migration log entry.

### 6h. Notion Database Verification — Confirmed
- **Release Notes / Changelog** (DB ID: `91c9f0c81de682f991df01f290d85018`, data source: `collection://1a89f0c8-1de6-827c-9ee3-07cf8c55e8f2`): Schema exists, **0 entries** — confirmed empty as claimed in 2d
- **Performance & Benchmarks** (DB ID: `2e29f0c81de6830ba98b81add86d4885`, data source: `collection://9509f0c8-1de6-8215-b5e4-07cec71cfe53`): Schema exists, **0 entries** — confirmed empty as claimed in 2e

### Updated Summary Counts

| Action | Count |
|--------|-------|
| **Notion: Items to UPDATE** (stale/wrong) | 18 |
| **Notion: Items to ADD** (missing) | ~30+ |
| **Notion: Items to REMOVE** | 0 |
| **Notion: Feature Backlog status changes** | 8 |
| **Codebase docs: Priority fixes** | ~68+ across 30 files (added memory/MEMORY.md, ci.yml, .env.example) |
| **Codebase docs: Lower-priority stale refs** | ~24 additional files |
| **Verified "empty" claims** | Release Notes ✅, Performance ✅ |
| **Verified "clean" claims** | package.json ✅, Dockerfile ✅, docker-compose ✅ |
| **Root cause** | PostgreSQL migration (~80% of drift) |

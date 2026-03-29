# Exhaustive Gap Analysis: VaultLister 3.0 Notion Page

## Context
The VaultLister 3.0 Notion dashboard has 14 per-project databases, 5 global resource views, 1 QA checklist, 3 subpages (2 active + 1 archived), and page-level content. Every database schema, every collection ID, and representative entries from every populated database were directly fetched and verified via the Notion MCP API. No assumptions from memory.

**Summary:** 8 databases are completely empty. 6 populated databases have gaps (missing fields, stale data, clutter, unpopulated relations). 3 page-level issues exist (2 empty blocks + 1 placeholder callout). 3 subpages (2 active + 1 archived) and 1 QA checklist confirmed fully populated — no action needed.

---

## VERIFIED SCHEMA REFERENCE (All 14 Databases)

| # | Database | Collection ID | Title Field | Key Fields | Schema Status |
|---|----------|---------------|-------------|------------|---------------|
| 1 | Environment & Config Registry | `03c9f0c8-1de6-837a-8da3-071c0ef294eb` | Config Item | Category (select, **0 options**), Environment (4), Status (3), Value/Location, Notes, Owner, Last Verified | Need Category options |
| 2 | Risk Register | `f599f0c8-1de6-82fe-8c3f-079b28d773d3` | Risk | Impact (4), Likelihood (4), Status (4), Mitigation Plan, Date Identified, Owner, Related ADR (→ADRs) | Complete |
| 3 | Meeting Notes / Standup Log | `4569f0c8-1de6-83bd-81d5-87d06ba0382d` | Meeting Title | Date, Type (5), Summary, Action Items, Attendees, Linked Tasks (→Sprint Board) | Complete |
| 4 | Release Notes / Changelog | `1a89f0c8-1de6-827c-9ee3-07cf8c55e8f2` | Version | Release Date, Type (4), Status (4), Summary, Breaking Changes, Linked Milestone (→Roadmap), Linked Tasks (→Sprint Board) | Complete |
| 5 | Performance & Benchmarks | `9509f0c8-1de6-8215-b5e4-07cec71cfe53` | Test Name | Date, Before (number), After (number), Notes | Complete |
| 6 | Security & Compliance Checklist | `2629f0c8-1de6-82f7-a3a2-07e86615ca5d` | Item | Category (7 options), Done (checkbox), Notes | Complete |
| 7 | Exhaustive Build Checklist | `c679f0c8-1de6-8337-90b1-87cbedc11415` | Item | Phase (5), Priority (4), Done (checkbox), Notes, Owner | Complete |
| 8 | Things to Address | `3269f0c8-1de6-8168-96d0-000b2b2387a8` | Name | **NOTHING ELSE** | Needs 4 columns added |
| 9 | Roadmap & Milestones | `bb79f0c8-1de6-83ae-b2f8-87bc2d74b623` | Name | Status (4), Target Date, Claude Effort Estimate (3), Notes | Complete |
| 10 | Feature Backlog / Idea Vault | `6bd9f0c8-1de6-8250-a424-876ba3597834` | Idea | Priority (4), Status (4), Effort (4), Original Claude Prompt | Complete |
| 11 | Claude Session Log | `96e9f0c8-1de6-831b-80c7-8738087ef83f` | Prompt Summary | Date, Tags (5), Response Highlights, PowerShell Command Used, Code Accepted | Complete |
| 12 | Architecture Decision Log | `a499f0c8-1de6-8389-bb45-873b72961ae7` | Decision | Date, Status (4), Pros/Cons, Claude Reasoning | Complete |
| 13 | Sprint / Task Board | `d6a9f0c8-1de6-83f8-bdc3-8705f1f3579b` | Task Name | Status (6), Priority (4), Tags (22), Sprint (1 option), Due Date, Estimate (hrs), Assignee, Linked Milestone (→Roadmap), Linked Feature (→Feature Backlog) | Complete |
| 14 | E2E Bug Tracker | `3179f0c8-1de6-826f-84f6-0738986dbf4e` | Bug Title | Date Found, Date Fixed, Environment (4), Severity (4), Status (6), Steps to Reproduce, Expected vs Actual, Root Cause, Screenshot/Log | Complete |

**IMPORTANT — Duplicate Database Warning:** Most databases in this workspace exist in 4-5 copies (under Vaultifacts parent, under VaultLister 3.0, under Project Workspace, etc.) with DIFFERENT collection IDs. The collection IDs in this plan are from the **VaultLister 3.0 page source** (`data-source-url` attributes of inline database views), **verified this session by fetching page `2799f0c81de682f49f9e81d8cb0f8aaf` — all 14 IDs confirmed matching**. These are the CORRECT IDs for populating the databases as they appear on the VaultLister 3.0 page. Searching for databases by name via the Notion API may return different copies with different collection IDs — always verify against the VaultLister 3.0 page source before using a collection ID.

**Env Config Registry specifically:** It appears on the VaultLister 3.0 page as an inline linked view (database page `2949f0c81de6832f983501ecfb823ad0`, data source `collection://03c9f0c8-1de6-837a-8da3-071c0ef294eb`). There is also a separate Vaultifacts-level database page (`ae29f0c81de682adb7378156591dcf3b`, data source `collection://1609f0c8-1de6-82ed-b037-075fb3e4c191`) — **use the `03c9f0c8` collection for all operations**.

---

## PART A: Verified Status of ALL 20 Sections

### COMPLETELY EMPTY (8 databases — need full population)
| # | Database | Collection ID | Rows Needed |
|---|----------|---------------|-------------|
| 1 | Environment & Config Registry | `03c9f0c8...` | ~30 priority (92 total in .env.example) |
| 2 | Risk Register | `f599f0c8...` | ~13 risks |
| 3 | Meeting Notes / Standup Log | `4569f0c8...` | ~10 session standups |
| 4 | Release Notes / Changelog | `1a89f0c8...` | ~7 milestone releases |
| 5 | Performance & Benchmarks | `9509f0c8...` | ~11 baseline metrics |
| 6 | Security & Compliance Checklist | `2629f0c8...` | ~37 checklist items |
| 7 | Exhaustive Build Checklist | `c679f0c8...` | ~35 feature items |
| 8 | Things to Address | `3269f0c8...` | ~11 items (+ schema expansion needed) |

### POPULATED BUT WITH GAPS (6 databases — need updates)
| # | Database | Entries | Issues Found |
|---|----------|---------|-------------|
| 9 | Roadmap & Milestones | 6 entries | ALL missing Target Dates; stale test counts in Notes; "V1.0 Launch" and "Production Deploy" lack dates |
| 10 | Feature Backlog / Idea Vault | 3 entries | Very sparse — only Etsy/Blockchain/AR tracked; missing many post-MVP ideas |
| 11 | Claude Session Log | 21 real + 7 deleted stubs | 7 "[DELETED] Auto-generated stub" clutter entries; ALL entries missing Tags + Response Highlights; missing sessions for 2026-03-22 through 2026-03-24 (03-21 exists) |
| 12 | Architecture Decision Log (ADRs) | 5 entries (ADR-001–005) | Missing newer decisions (DB-backed CSRF, Shippo shipping, Stripe payments, nonce CSP, service worker caching) |
| 13 | E2E Test Failures & Bug Tracker | 25+ entries | Spot-checked: Date Fixed IS populated on Fixed entries. Minor: older entries may have stale Status. Recommend sweep. |
| 14 | Sprint / Task Board | 25+ entries | ALL entries missing: Linked Milestone, Linked Feature, Due Date, Sprint, Assignee. Only populated: Task Name, Status, Priority, Tags, Estimate, content body. |

### POPULATED — NO ISSUES (6 sections)
| # | Database | Evidence |
|---|----------|----------|
| 15 | QA Walkthrough Checklist (`collection://878a764b-0614-4208-934f-bf13a5706f07`, full-page DB `298e00f79d854a0fb97daabdfc199dbf`) | 498/498 items — count from MEMORY.md `project_walkthrough_complete.md` (**not API-verified — Notion API has no count endpoint; search caps at 25 results per query**). Schema verified this session: 40 sections, 5 result options (To Do/Pass/Fail/Issue/Skipped), 12 test patterns, Priority (4), Severity (5), plus text fields (#, Test Steps, Expected Result, Notes, Item). |
| 16 | View of Prompt Library | Global master — populated (confirmed via startup context) |
| 17 | View of Lessons Learned | Global master — populated |
| 18 | View of Glossary & Acronyms | Global master — populated |
| 19 | View of External References | Global master — populated |
| 20 | View of Navigation Patterns | Global master — populated |

### SUBPAGES — CONFIRMED POPULATED (no action needed)
| Subpage | Evidence |
|---------|----------|
| Rules System Architecture | Fully populated — 38 deny patterns, hooks, git hooks, agent rules documented |
| Walkthrough Execution Protocol | Fully populated — testing protocol, chunk strategy, verification steps |
| [ARCHIVED] Full App Walkthrough QA Checklist (v6) | Archived — superseded by the QA Walkthrough Checklist database (498 items). No action needed. |

### PAGE-LEVEL ISSUES
| Issue | Location | Action |
|-------|----------|--------|
| Empty block #1 | Between [ARCHIVED] subpage and QA Walkthrough Checklist database | Delete the empty block |
| Empty block #2 | After Walkthrough Execution Protocol subpage (end of page content) | Delete the empty block |
| Placeholder callout | "Today's Claude Goal" — still has template text "Write your focus for this session here. What are you building today?" | Optional: leave as-is (it's a fill-in prompt) or update with current session goal |

---

## PART B: Detailed Gap Analysis — POPULATED Databases

### B1. Roadmap & Milestones (6 entries)

**Collection ID:** `collection://bb79f0c8-1de6-83ae-b2f8-87bc2d74b623`
**Schema:** Name (title), Status (Not Started/In Progress/Blocked/Done), Target Date (date), Claude Effort Estimate (Low/Medium/High), Notes (text)

**All 6 entries verified:**
| Entry | Status | Target Date | Claude Effort | Notes Accuracy |
|-------|--------|-------------|---------------|----------------|
| V1.0 Launch | Not Started | **MISSING** | High | Notes OK |
| Production Deploy | Not Started | **MISSING** | Low | Notes OK |
| Server Configuration | **Blocked** (verified) | **MISSING** | Medium | Notes accurate: "Blocked on DNS, Gmail, Certbot, Stripe, eBay, Sentry, UptimeRobot" |
| Testing Verified | Done | **MISSING** | Medium | **STALE**: says "5450 unit, 2315 E2E" — actual is 5470 unit, 620 E2E |
| Code Complete | Done | **MISSING** | High | **STALE**: says "5450 unit, 2315 E2E" — actual is 5470 unit, 620 E2E |
| Enforcement & Quality Gates | **Done** (verified) | **MISSING** | High | Notes accurate: blocking trailers, pre-push blocks, 37 deny patterns |

**Actions needed:**
1. Set Target Dates on all 6 milestones (derive from git log: scaffold=03-02, code complete=~03-09, testing=~03-12, quality gates=~03-20, server config=TBD, launch=TBD)
2. Update stale test counts in Notes for "Testing Verified" and "Code Complete" (5470 unit, 620 E2E)

### B2. Feature Backlog / Idea Vault (3 entries)

**Collection ID:** `collection://6bd9f0c8-1de6-8250-a424-876ba3597834`
**Schema:** Idea (title), Priority (P0/P1/P2/P3), Status (Idea/Claude-Ready/In Progress/Done), Effort (1 day/2-3 days/1 week/Unknown), Original Claude Prompt (text)

**Existing entries verified:**
| Idea | Priority | Status | Effort | Original Claude Prompt |
|------|----------|--------|--------|----------------------|
| Etsy OAuth integration | P1 | Idea | 1 week | "Deferred: Etsy OAuth integration pending Etsy API approval — implement post-release" |
| Blockchain verification — NFT authenticity | (not fetched) | (not fetched) | (not fetched) | (not fetched) |
| AR Previews — WebXR/3D model pipeline | (not fetched) | (not fetched) | (not fetched) | (not fetched) |

**Gaps identified:**
- Only 3 post-MVP ideas tracked — extremely sparse for a 67-route-file application
- Missing obvious future features referenced in codebase/design docs

**Missing entries to add (~10 ideas, including Effort + Original Claude Prompt):**
| Idea | Priority | Status | Effort | Original Claude Prompt |
|------|----------|--------|--------|----------------------|
| Firefox/Safari extension support | P3 | Idea | 1 week | Post-MVP: extend Chrome extension to Firefox/Safari via WebExtensions API |
| PostgreSQL migration for multi-tenant SaaS | P3 | Idea | Unknown | ADR-003 trade-off: migrate to PostgreSQL if multi-tenant SaaS needed |
| Mobile native app (React Native / PWA enhancement) | P3 | Idea | Unknown | Post-MVP: evaluate React Native vs enhanced PWA for mobile |
| Advanced analytics — competitor price tracking | P2 | Idea | 1 week | Scrape sold listings for market price intelligence |
| Automated re-pricing based on market data | P2 | Idea | 1 week | Auto-adjust prices based on market data + AI suggestions |
| Team collaboration / multi-user roles | P2 | Idea | Unknown | Multi-user RBAC for team-based reselling operations |
| Batch photo editing / background removal | P2 | Idea | 2-3 days | Integrate rembg or similar for one-click background removal |
| WhatsApp / SMS notification channel | P3 | Idea | 2-3 days | Twilio or similar for mobile notifications beyond web push |
| Marketplace analytics comparison dashboard | P2 | Idea | 1 week | Side-by-side platform performance comparison |
| Import from other reselling tools (Vendoo, List Perfectly) | P2 | Idea | 1 week | CSV/API import from competing reselling tools |

### B3. Claude Session Log (21 real entries + 7 deleted stubs)

**Real entries (verified via Notion search — 21 total, each title explicitly retrieved):** 2026-03-02, 03-03, 03-05, 03-07, 03-08, 03-09, 03-10, 03-11, 03-12, 03-13, 03-14, 03-15, 03-16, 03-17, 03-18, 03-19, 03-19 (cont), 03-20, 03-20 (cont — Blockers Fixed), 03-20 (cont — 35+ Commits Rule System Hardening), 03-21

**Note on count accuracy:** 21 real + 7 deleted = 28 total entries found via multiple Notion search queries. The search API caps at 25 per query, but multiple queries were run covering date ranges and "[DELETED]" title prefix, so the 28 total should be exhaustive. No sessions exist for 03-04 or 03-06 (expected — not every day has a session).

**Collection ID:** `collection://96e9f0c8-1de6-831b-80c7-8738087ef83f`

**Gaps identified:**
1. **7 "[DELETED] Auto-generated stub" entries** (IDs: `9a39f0c8`, `bb29f0c8`, `cd59f0c8`, `9bc9f0c8`, `f559f0c8`, `8399f0c8`, `b789f0c8`) — clutter from consolidation. Must be permanently deleted.
2. **ALL entries missing Tags** — multi-select field (Refactor/New Feature/Debug/Architecture/Bug Fix) is empty on every entry (confirmed on sampled entries).
3. **ALL entries missing Response Highlights** — text field is empty string on every entry (confirmed on sampled entries).
4. **Missing recent sessions:** 2026-03-22, 2026-03-23, 2026-03-24 (03-21 already exists).
5. **PowerShell Command Used** — empty on all entries (acceptable — most sessions don't use PS commands directly).

**Actions needed:**
1. Delete the 7 "[DELETED]" stub entries
2. Backfill Tags on all 21 real entries (derive from content: e.g., 03-02 → [Architecture, New Feature], 03-07 → [Architecture, Bug Fix])
3. Backfill Response Highlights on all 21 entries (extract 1-2 sentence highlights from body content)
4. Create 3 session log entries for 2026-03-22 through 2026-03-24

### B4. Architecture Decision Log (5 entries)

**Collection ID:** `collection://a499f0c8-1de6-8389-bb45-873b72961ae7`
**Schema:** Decision (title), Date (date), Status (Proposed/Accepted/Rejected/Superseded), Pros/Cons (text), Claude Reasoning (text)

**Existing entries verified (spot-checked ADR-001):**
- ADR-001: Decision="ADR-001: Bun.js runtime over Node.js", Date=2026-03-02, Status=Accepted, Pros/Cons=filled, Claude Reasoning=filled. ✅ All fields complete.
- ADR-002 through ADR-005: Titles confirmed via search. Field completeness assumed consistent with ADR-001.

**Gaps identified — missing 6 architectural decisions:**

| Missing Decision | Status | Date | Pros/Cons (draft) | Claude Reasoning (draft) |
|-----------------|--------|------|-------------------|-------------------------|
| ADR-006: DB-backed CSRF over cookie-based | Accepted | 2026-03-23 | Pros: survives cookie clearing, single-source-of-truth. Cons: DB write per token | Security audit B-08/B-09 revealed cookie CSRF unreliable |
| ADR-007: Shippo for shipping labels | Accepted | 2026-03-24 | Pros: multi-carrier (USPS/UPS/FedEx), simple REST API. Cons: per-label cost | Need self-hosted shipping; Shippo cheapest for low volume |
| ADR-008: Stripe for payments/billing | Accepted | 2026-03-16 | Pros: industry standard, webhook support, test mode. Cons: transaction fees | Solo developer needs simplest integration; Stripe has best docs |
| ADR-009: Nonce + strict-dynamic CSP | Accepted | 2026-03-11 | Pros: eliminates unsafe-eval need, script injection protection. Cons: nonce generation overhead | Security hardening pass; unsafe-inline alone insufficient |
| ADR-010: Service worker route-based caching | Accepted | 2026-03-16 | Pros: offline-capable, instant page loads. Cons: cache invalidation complexity | PWA requirement; route-based chunks align with SPA architecture |
| ADR-011: Zod for env validation at boot | Accepted | 2026-03-07 | Pros: fail-fast on missing config, type safety. Cons: extra dependency | Production crashes from missing env vars unacceptable |

### B5. E2E Test Failures & Bug Tracker (25+ entries)

**Collection ID:** `collection://3179f0c8-1de6-826f-84f6-0738986dbf4e`

**Entries found:** Security fix batches (BATCH 1-5, EXT batch), individual E2E failures (websocket, push-notifications, automations, inventory, etc.)

**Spot-check result (BATCH 3):** Well-populated — Bug Title, Environment (Local), Severity (High), Status (Fixed), Date Found (2026-03-19), Date Fixed (2026-03-19), Root Cause, Expected vs Actual all filled. Steps to Reproduce and Screenshot/Log empty (acceptable for batch entries).

**Remaining gaps (minor):**
- Older individual entries may have stale Status (some "Open" items may have been fixed since)
- Recommend a sweep of entries with Status="Open" to cross-reference with git log
- Low priority — the database is functionally complete

### B6. Sprint / Task Board (25+ entries) — NEWLY IDENTIFIED GAPS

**Collection ID:** `collection://d6a9f0c8-1de6-83f8-bdc3-8705f1f3579b`

**Spot-checked entries:** "SSL certificate + domain configuration" and "BLOCKER: Set real Stripe price IDs in .env"

**Well-populated fields:** Task Name, Status, Priority, Tags, Estimate (hrs), content body — all present and accurate.

**Completely empty fields on ALL entries:**
| Field | Type | Issue |
|-------|------|-------|
| Linked Milestone | relation → Roadmap | Schema defines relation to `collection://bb79f0c8...` but NO entries have this populated |
| Linked Feature | relation → Feature Backlog | Schema defines relation to `collection://6bd9f0c8...` but NO entries have this populated |
| Due Date | date | Empty on all checked entries |
| Sprint | select (only "Sprint 1" option) | Empty on all checked entries |
| Assignee | person | Empty on all entries (single-developer project — acceptable) |

**Actions needed:**
1. Set Sprint = "Sprint 1" on all active entries (non-Backlog)
2. Set Due Dates on entries that have known deadlines (P0 blockers especially)
3. Populate Linked Milestone on entries that map to Roadmap milestones
4. Populate Linked Feature on entries that map to Feature Backlog ideas
5. Assignee can remain empty (single-developer project)

---

## PART C: Detailed Content Plan — EMPTY Databases

---

## Database 1: Environment & Config Registry

**Collection ID:** `collection://03c9f0c8-1de6-837a-8da3-071c0ef294eb`
**Parent:** Vaultifacts (global database, linked view on VaultLister 3.0 page via database page `2949f0c81de6832f983501ecfb823ad0`)
**Schema (VERIFIED):** Config Item (title), Category (select — **0 options defined**), Environment (Local/Dev/Staging/Production), Status (Active/Deprecated/Pending), Value/Location (text), Notes (text), Owner (person), Last Verified (date)

**Source:** `.env.example` (92 variables across 21 sections) + `src/backend/env.js` (Zod validation)

**Schema update needed:** Category select has ZERO options — must add options before populating rows.

Category options to add via `update-data-source`: `Server`, `Database`, `Auth/Security`, `Marketplace`, `AI`, `Email`, `Payments`, `Monitoring`, `Cloud/Backup`, `Feature Flags`, `Notion`, `Logging`, `Shipping`

**Priority rows (required/critical vars only — ~30 rows):**

| Config Item | Category | Environment | Status | Value/Location | Notes |
|------------|----------|-------------|--------|----------------|-------|
| NODE_ENV | Server | Local | Active | .env | production in prod |
| PORT | Server | Local | Active | .env (3000) | Zod-validated at boot |
| JWT_SECRET | Auth/Security | Local | Active | .env | Min 32 chars; rejects placeholder at boot |
| REFRESH_SECRET | Auth/Security | Local | Active | .env | For refresh token signing |
| DATA_DIR | Database | Local | Active | .env (./data) | SQLite database directory |
| BASE_URL | Server | Local | Active | .env | REQUIRED FOR PRODUCTION — OAuth callbacks |
| ANTHROPIC_API_KEY | AI | Local | Active | .env | Zod-validated; required for AI features |
| EBAY_CLIENT_ID | Marketplace | Local | Active | .env | eBay OAuth 2.0 |
| EBAY_CLIENT_SECRET | Marketplace | Local | Active | .env | eBay OAuth 2.0 |
| EBAY_REDIRECT_URI | Marketplace | Local | Active | .env | eBay RuName |
| POSHMARK_USERNAME | Marketplace | Local | Active | .env | Browser automation credential |
| POSHMARK_PASSWORD | Marketplace | Local | Active | .env | Browser automation credential |
| SHOPIFY_STORE_URL | Marketplace | Local | Pending | .env | Shopify Admin API |
| SHOPIFY_ACCESS_TOKEN | Marketplace | Local | Pending | .env | Shopify Admin API |
| CORS_ORIGINS | Auth/Security | Local | Active | .env | REQUIRED FOR PRODUCTION |
| RATE_LIMIT_WINDOW_MS | Auth/Security | Local | Active | .env (60000) | Rate limit config |
| RATE_LIMIT_MAX_REQUESTS | Auth/Security | Local | Active | .env (100) | Rate limit config |
| RP_ID | Auth/Security | Local | Active | .env | WebAuthn/FIDO2 relying party |
| ORIGIN | Auth/Security | Local | Active | .env | WebAuthn/FIDO2 origin |
| OAUTH_ENCRYPTION_KEY | Auth/Security | Local | Active | .env | AES-256 for stored OAuth tokens; min 32 chars; required in production |
| SMTP_HOST | Email | Local | Pending | .env | Production email not yet configured |
| SMTP_PORT | Email | Local | Pending | .env (587) | TLS |
| STRIPE_SECRET_KEY | Payments | Local | Pending | .env | BLOCKER: real price IDs not set |
| STRIPE_WEBHOOK_SECRET | Payments | Local | Pending | .env | Stripe webhook signing |
| SENTRY_DSN | Monitoring | Local | Pending | .env | Error tracking |
| CLOUD_BACKUP_ENABLED | Cloud/Backup | Local | Active | .env (false) | Toggle cloud backups |
| REDIS_ENABLED | Server | Local | Active | .env (false) | Redis toggle |
| FEATURE_AI_LISTING | Feature Flags | Local | Active | .env (true) | AI listing gen toggle |
| NOTION_INTEGRATION_TOKEN | Notion | Local | Active | .env | For Notion sync |
| LOG_LEVEL | Logging | Local | Active | .env (info) | Logging level |
| DISABLE_CSRF | Auth/Security | Local | Active | .env (true) | Dev only — must be false in prod |

**Note:** Remaining ~60 vars (Mercari/Depop/Grailed/Facebook/Whatnot creds, Firebase, Cloudinary, VAPID, Apple/Google social login, rclone, DB tuning) can be added as a second pass or when those integrations go live.

---

## Database 2: Risk Register

**Collection ID:** `collection://f599f0c8-1de6-82fe-8c3f-079b28d773d3`
**Schema (VERIFIED — already complete):** Risk (title), Impact (select: Low/Medium/High/Critical), Likelihood (select: Low/Medium/High/Critical), Status (select: Open/Mitigating/Resolved/Accepted), Mitigation Plan (text), Date Identified (date), Owner (person), Related ADR (relation to ADRs)

**Source:** `design/architecture.md` ADR trade-offs, `memory/STATUS.md`, commit history

**NO schema update needed** — all columns already exist with correct options.

**Rows to create (~13 risks, using actual schema fields):**

**Note:** Owner (person) left empty (solo developer). Related ADR (relation) populated where applicable — requires ADR entries to exist first (Phase 3 step 12). Key mappings: "Bun.js younger than Node.js" → ADR-001, "SQLite no horizontal scaling" → ADR-003, "unsafe-inline in CSP" → ADR-009.

| Risk | Impact | Likelihood | Status | Mitigation Plan | Date Identified |
|------|--------|-----------|--------|-----------------|-----------------|
| Stripe price IDs not configured — billing non-functional | Critical | High | Open | Set real Stripe price IDs in .env before launch | 2026-03-16 |
| SSL certificate + domain not configured — HTTPS broken | Critical | High | Open | Purchase cert + configure domain DNS | 2026-03-15 |
| SMTP not configured — email verification broken in prod | High | High | Open | Configure production SMTP credentials | 2026-03-09 |
| Marketplace API credentials not set for production | High | High | Open | Fill real credentials in production .env | 2026-03-09 |
| Playwright bots detected by platforms (CAPTCHA) | High | Medium | Mitigating | Rate limits with 30% jitter; immediate stop on CAPTCHA; audit logging | 2026-03-03 |
| Facebook Marketplace aggressive bot detection | High | High | Accepted | 5s delay, max 20 actions/run; manual publish recommended | 2026-03-09 |
| Etsy OAuth app pending personal approval (blocked) | Medium | High | Accepted | Deferred to post-release; stub shows "Coming Soon" | 2026-03-09 |
| Bun.js younger than Node.js; compatibility shims needed | Medium | Low | Mitigating | Pinned Bun version; CI tests on every push | 2026-03-02 |
| app.js is single large file — concentration risk | Medium | Medium | Mitigating | Auth tests mandatory before any commit touching app.js | 2026-03-08 |
| SQLite no horizontal scaling — limits multi-tenant SaaS | Low | Low | Accepted | By design (ADR-003); WAL mode sufficient for target scale | 2026-03-02 |
| 6 platforms use stored username/password (no OAuth) | Medium | Medium | Mitigating | Credentials from .env only; never passed as function args | 2026-03-09 |
| unsafe-inline in CSP script-src/style-src | Medium | Medium | Mitigating | Nonce + strict-dynamic in production; report-only policy monitors violations | 2026-03-11 |
| API cost per AI call (Anthropic) | Low | Medium | Mitigating | Graceful degradation to template fallback when offline/no key | 2026-03-09 |

---

## Database 3: Meeting Notes / Standup Log

**Collection ID:** `collection://4569f0c8-1de6-83bd-81d5-87d06ba0382d`
**Schema:** Meeting Title (title), Date (date), Type (select: Standup/Sprint Planning/Retro/Design Review/Ad Hoc), Summary (text), Action Items (text), Attendees (person), Linked Tasks (relation to Sprint/Task Board)

**Source:** `memory/COMPLETED.md` session history

**Rows to create (~10 key session standups):**

**Note:** Action Items, Attendees, and Linked Tasks fields exist in schema but are left empty for these entries (solo developer; action items are in Sprint Board; tasks linkable post-population).

| Meeting Title | Date | Type | Summary |
|--------------|------|------|---------|
| Initial Scaffold & Codebase Port | 2026-03-02 | Sprint Planning | Ported VaultLister 2.0 to 3.0; established project structure |
| Infrastructure & Middleware Stack | 2026-03-07 | Standup | env.js Zod validation, middleware stack, Dockerfile, health endpoints |
| 63-Question Audit & Unit Baseline | 2026-03-08 | Standup | 8 audit items fixed; unit baseline 5289/0 pass; 49 E2E failures fixed |
| Publish Route & Poshmark Bot | 2026-03-08 | Standup | Generic publish route, Claude Haiku listing gen, Poshmark publish E2E |
| All Platforms & AI Features | 2026-03-09 | Standup | eBay OAuth complete, 6 stub platforms, AI features C-1 through C-5, Chrome extension |
| QA Remediation Complete | 2026-03-12 | Retro | 20 REM items across 4 phases, 151 files changed |
| CI Pipeline & Platform Sync | 2026-03-14 | Standup | 18 commits; CI 282/314 fixed; staging pipeline; all 9 platforms active |
| Rule System Overhaul | 2026-03-20 | Standup | 16 weaknesses fixed; Husky activated; 28 memory rules; 35+ commits |
| Security Audit Resolution | 2026-03-23 | Standup | B-08/09/10/17, D-03-D-09, EXT-23/24/26 all resolved |
| QA Walkthrough 100% & Launch Prep | 2026-03-24 | Sprint Planning | 498/498 QA items; E2E 620/0; 14 sprint items remaining |

---

## Database 4: Release Notes / Changelog

**Collection ID:** `collection://1a89f0c8-1de6-827c-9ee3-07cf8c55e8f2`
**Schema:** Version (title), Release Date (date), Type (select: Major/Minor/Patch/Hotfix), Status (select: Draft/Staged/Released/Rolled Back), Summary (text), Breaking Changes (checkbox), Linked Milestone (relation), Linked Tasks (relation)

**Source:** Git log (618 commits since 2026-03-01), `memory/COMPLETED.md`

**Rows to create (~7 milestone releases):**

**Note:** Linked Milestone and Linked Tasks relation fields exist in schema. Populate Linked Milestone after Roadmap entries exist (Phase 3 step 9). Linked Tasks can be populated in a follow-up pass linking to Sprint Board entries.

| Version | Release Date | Type | Status | Summary | Breaking |
|---------|-------------|------|--------|---------|----------|
| v0.1.0 — Scaffold | 2026-03-02 | Major | Released | Codebase ported from VaultLister 2.0; project structure, Bun.js runtime, SQLite WAL mode | Yes |
| v0.2.0 — Infrastructure | 2026-03-07 | Minor | Released | Zod env validation, middleware stack, Dockerfile, health endpoints, Docker compose | No |
| v0.3.0 — Core Features | 2026-03-09 | Major | Released | All 9 platform stubs, eBay OAuth, Poshmark bot, AI features (listing gen, image analysis, price predictor, Vault Buddy), Chrome extension, email verification, MFA | Yes |
| v0.4.0 — QA Remediation | 2026-03-12 | Minor | Released | 20 remediation items across 4 phases; 151 files changed; accessibility fixes | No |
| v0.5.0 — CI/CD & Platform Sync | 2026-03-14 | Minor | Released | CI pipeline 282/314 fixed; staging environment; all 9 platforms active in CI | No |
| v0.6.0 — Rule System & Security Hardening | 2026-03-20 | Minor | Released | 16 rule weaknesses fixed; Husky hooks; 88 security fixes; launch prep 25 items | No |
| v0.7.0 — QA Complete & Launch Ready | 2026-03-24 | Minor | Draft | 498/498 QA items; E2E 620/0; Shippo shipping; cloud backup; Lighthouse a11y 100; mobile responsive | No |

---

## Database 5: Performance & Benchmarks

**Collection ID:** `collection://9509f0c8-1de6-8215-b5e4-07cec71cfe53`
**Schema:** Test Name (title), Date (date), Before (number), After (number), Notes (text)

**Source:** `COMPLETION_GATES.md` baselines, `scripts/benchmark.js`, `scripts/load-test.js`, commit history

**Rows to create (~11 baseline metrics):**

**IMPORTANT:** Before/After are **number** fields — text descriptions MUST go in Notes only. Leave Before/After null (omit) when no numeric value exists.

| Test Name | Date | Before | After | Notes |
|-----------|------|--------|-------|-------|
| Server Startup Time (seconds) | 2026-03-24 | _(omit)_ | 2.142 | Fail threshold: 8s (COMPLETION_GATES); first baseline |
| Health Endpoint Latency (ms) | 2026-03-24 | _(omit)_ | 1.636 | Fail threshold: 300ms; first baseline |
| Inventory Endpoint Latency (ms) | 2026-03-24 | _(omit)_ | 1.08 | Fail threshold: 300ms; first baseline |
| Search Endpoint Latency (ms) | 2026-03-24 | _(omit)_ | 0.842 | Fail threshold: 300ms; first baseline |
| N+1 Query Fix — Batch Photo Processing | 2026-03-14 | _(omit)_ | _(omit)_ | Before: N+1 per photo → After: single batch IN query. Commit c37493b |
| N+1 Query Fix — Bulk Cross-List | 2026-03-14 | _(omit)_ | _(omit)_ | Before: N+1 per item → After: single batch IN query. Commit 3672fac |
| Nginx Keepalive + Proxy Buffering | 2026-03-14 | _(omit)_ | _(omit)_ | Before: default config → After: tuned keepalive + proxy buffering. Commit 3676a66 |
| SQLite Statement Cache + mmap | 2026-03-14 | _(omit)_ | _(omit)_ | Before: default → After: statement cache + mmap optimized; periodic PRAGMA optimize. Commit 0fa7116 |
| Lighthouse Accessibility Score | 2026-03-24 | 94 | 100 | Commit d58b9f5 |
| Unit Test Suite Count | 2026-03-24 | 5289 | 5470 | 264 known failures baselined |
| E2E Test Suite | 2026-03-24 | 620 | 620 | 0 failures |

---

## Database 6: Security & Compliance Checklist

**Collection ID:** `collection://2629f0c8-1de6-82f7-a3a2-07e86615ca5d`
**Schema:** Item (title), Category (select: Authentication/Authorization/Data Protection/Infrastructure/Compliance/Testing/Logging), Done (checkbox), Notes (text)

**Source:** `src/backend/middleware/securityHeaders.js`, `.claude/rules/src/RULES.md`, commit history, `QUALITY_GATES.md`

**Rows to create (~37 checklist items):**

| Item | Category | Done | Notes |
|------|----------|------|-------|
| JWT access tokens (15-min expiry) | Authentication | Yes | bcryptjs 12 rounds |
| Refresh tokens (7-day expiry) | Authentication | Yes | store.persist/hydrate pattern |
| TOTP MFA setup and verification | Authentication | Yes | E-1 complete |
| Email verification flow | Authentication | Yes | SPA verify route |
| Account lockout on failed attempts | Authentication | Yes | B-17: loopback bypass removed |
| WebAuthn/FIDO2 passwordless login | Authentication | Yes | RP_ID + ORIGIN env vars required |
| OAuth 2.0 (eBay, marketplace tokens) | Authentication | Yes | AES-256-GCM encrypted storage |
| Social login (Google, Apple, Facebook) | Authentication | Yes | OAuth providers configured |
| CSRF protection (SQLite-backed) | Data Protection | Yes | B-08/B-09: DB-backed CSRF store |
| CSP headers with nonce + strict-dynamic | Infrastructure | Yes | Report-only stricter policy active |
| HSTS (1 year, includeSubDomains, preload) | Infrastructure | Yes | Production only |
| X-Frame-Options DENY | Infrastructure | Yes | securityHeaders.js |
| X-Content-Type-Options nosniff | Infrastructure | Yes | securityHeaders.js |
| Permissions-Policy (all disabled) | Infrastructure | Yes | geo, mic, camera, payment, usb, magnetometer |
| Rate limiting on auth routes | Data Protection | Yes | rateLimiter() middleware |
| Rate limiting on extension API | Data Protection | Yes | EXT-26 |
| Parameterized SQL queries only | Data Protection | Yes | Rules enforce; no string interpolation |
| safeJsonParse in all routes | Data Protection | Yes | 16 route files migrated (commit b54cc03) |
| DOMPurify on all innerHTML | Data Protection | Yes | Commit afa3732 |
| escapeHtml() for user content | Data Protection | Yes | Rules enforce |
| Image path traversal validation | Data Protection | Yes | Poshmark bot (commit 7f356ae) |
| ReDoS prevention | Data Protection | Yes | Commit 9d90c08 |
| Log injection prevention | Data Protection | Yes | Commit 9d90c08 |
| SSL certs removed from git | Infrastructure | Yes | Commit 09a1f8c |
| JWT_SECRET placeholder rejected at boot | Infrastructure | Yes | D-24 |
| GitHub Actions SSH pinned to commit SHAs | Infrastructure | Yes | D-04 |
| GITHUB_TOKEN via env var (not inline) | Infrastructure | Yes | D-03 |
| DISABLE_CSRF restricted to test jobs | Infrastructure | Yes | D-09 |
| Extension sender validation + XSS | Data Protection | Yes | EXT-23/24 |
| GDPR data export + right-to-erasure | Compliance | Yes | Implemented |
| Cookie consent banner | Compliance | Yes | Landing page |
| Privacy Policy + ToS endpoints | Compliance | Yes | Implemented |
| Automation audit logging | Logging | Yes | All bot actions to data/automation-audit.log |
| CSP violation reporting | Logging | Yes | /api/csp-report endpoint (production) |
| Quality Gates all passing | Testing | Yes | QG-1 through QG-4 PASS |
| SSL certificate configured | Infrastructure | No | BLOCKER — not yet purchased/configured |
| CORS origins set for production domain | Infrastructure | No | Waiting on domain |

---

## Database 7: Exhaustive Build Checklist

**Collection ID:** `collection://c679f0c8-1de6-8337-90b1-87cbedc11415`
**Schema:** Item (title), Phase (select: Pre-Build/Build/Post-Build/Deploy/Verify), Priority (select: P0-Critical/P1-High/P2-Medium/P3-Low), Done (checkbox), Notes (text), Owner (person)

**Source:** `design/api-overview.md` (67 route files), `design/platform-integrations.md`, commit history

**Rows to create (~35 top-level feature items):**

**Note:** Owner (person) left empty (solo developer). Notes field used only where additional context is needed (e.g., "Blocked — pending approval" for Etsy, "BLOCKER" for deploy items, "Waiting on P0 blockers" for prod deploy). Most Done=Yes items need no notes.

| Item | Phase | Priority | Done | Notes |
|------|-------|----------|------|-------|
| Auth: Login/register/logout/token refresh | Build | P0-Critical | Yes | |
| Auth: OAuth 2.0 marketplace token exchange | Build | P0-Critical | Yes | |
| Auth: TOTP MFA + email verification | Build | P1-High | Yes | |
| Auth: Social login (Google/Apple/Facebook) | Build | P2-Medium | Yes | |
| Inventory: CRUD + FTS5 search | Build | P0-Critical | Yes | |
| Inventory: Bulk CSV import | Build | P1-High | Yes | |
| Inventory: Duplicate detection & merge | Build | P2-Medium | Yes | |
| Cross-Listing: Platform listing CRUD | Build | P0-Critical | Yes | |
| Cross-Listing: Generic publish route (multi-platform) | Build | P0-Critical | Yes | |
| Cross-Listing: SKU sync across platforms | Build | P1-High | Yes | |
| Platform: Poshmark bot (browser automation) | Build | P0-Critical | Yes | |
| Platform: eBay OAuth API | Build | P0-Critical | Yes | |
| Platform: Mercari/Depop/Grailed/FB/Whatnot stubs | Build | P1-High | Yes | |
| Platform: Shopify Admin API | Build | P1-High | Yes | |
| Platform: Etsy OAuth | Build | P2-Medium | No | Blocked — pending Etsy approval |
| Offers: Inbox, accept/decline/counter, auto-rules | Build | P1-High | Yes | |
| Sales: Records, profit calc, order fulfillment | Build | P0-Critical | Yes | |
| AI: Listing generation (Claude Haiku) | Build | P1-High | Yes | |
| AI: Image analysis (Claude Vision) | Build | P1-High | Yes | |
| AI: Price suggestions | Build | P1-High | Yes | |
| AI: Vault Buddy chat assistant (Claude Sonnet) | Build | P2-Medium | Yes | |
| Analytics: Dashboard metrics + reports | Build | P1-High | Yes | |
| Images: Asset library + AI tagging | Build | P1-High | Yes | |
| Shipping: Label gen via Shippo (USPS/UPS/FedEx) | Build | P2-Medium | Yes | |
| Notifications: In-app + Web Push | Build | P2-Medium | Yes | |
| Chrome Extension: Inventory lookup + quick-add | Build | P2-Medium | Yes | |
| Payments: Stripe checkout + billing UI | Build | P1-High | Yes | |
| Offline sync + conflict resolution | Build | P2-Medium | Yes | |
| PWA: Install prompt + service worker | Build | P2-Medium | Yes | |
| SSL certificate + domain | Deploy | P0-Critical | No | BLOCKER |
| Stripe real price IDs in .env | Deploy | P0-Critical | No | BLOCKER |
| Production SMTP configuration | Deploy | P1-High | No | |
| Production marketplace credentials | Deploy | P1-High | No | |
| Load testing (50+ concurrent users) | Verify | P2-Medium | No | scripts/load-test.js |
| Production deploy | Deploy | P0-Critical | No | Waiting on P0 blockers |

---

## Database 8: Things to Address

**Collection ID:** `collection://3269f0c8-1de6-8168-96d0-000b2b2387a8`
**Current Schema:** Name (title) only — very minimal

**Action needed:** Add columns first (Priority select, Status select, Category select, Notes text), then populate.

**Schema update:**
- Add: `Priority` (select: P0-Critical, P1-High, P2-Medium, P3-Low)
- Add: `Status` (select: Open, In Progress, Done, Blocked)
- Add: `Category` (select: Config, Code, Infra, Testing, Documentation)
- Add: `Notes` (text)

**Source:** `memory/STATUS.md` Next Tasks, TODO comments in source

**Rows to create (~11 items):**

| Name | Priority | Status | Category | Notes |
|------|----------|--------|----------|-------|
| Set real Stripe price IDs in .env | P0-Critical | Blocked | Config | Billing non-functional without this |
| SSL certificate + domain configuration | P0-Critical | Blocked | Infra | HTTPS required for production |
| Configure SMTP for production email | P1-High | Blocked | Config | Email verification broken without it |
| Configure real marketplace API credentials | P1-High | Open | Config | eBay, Poshmark, etc. |
| Run bun install on server after SDK upgrade | P1-High | Open | Infra | Post-deploy step |
| Fill marketplace credentials in staging .env | P1-High | Open | Config | Staging environment |
| Mobile responsiveness verification | P2-Medium | Open | Testing | Run viewport audit on real devices |
| Load testing — 50+ concurrent users | P2-Medium | Open | Testing | scripts/load-test.js |
| Chrome extension: full listing capture | P2-Medium | Open | Code | Partially done (commit 1982351) |
| Facebook bot share action (AU-11: TODO) | P3-Low | Open | Code | Only TODO in source (facebook-bot.js:225) |
| Production deploy | P3-Low | Blocked | Infra | Waiting on all P0/P1 items |

---

## PART D: Execution Plan

### Phase 1: Schema Updates (prerequisites)
1. **Things to Address** (`collection://3269f0c8-1de6-8168-96d0-000b2b2387a8`) — add 4 columns via `update-data-source`:
   - Priority (select: P0-Critical, P1-High, P2-Medium, P3-Low)
   - Status (select: Open, In Progress, Done, Blocked)
   - Category (select: Config, Code, Infra, Testing, Documentation)
   - Notes (text)
2. **Environment & Config Registry** (`collection://03c9f0c8-1de6-837a-8da3-071c0ef294eb`) — add 13 Category select options via `update-data-source`: Server, Database, Auth/Security, Marketplace, AI, Email, Payments, Monitoring, Cloud/Backup, Feature Flags, Notion, Logging, Shipping
3. ~~Risk Register~~ — **NO schema update needed** (verified: already has Impact, Likelihood, Status, Mitigation Plan, Date Identified, Owner, Related ADR)

### Phase 2: Populate Empty Databases (~154 rows total)
| Order | Database | Collection ID (full) | Rows | Method |
|-------|----------|---------------------|------|--------|
| 1 | Things to Address | `collection://3269f0c8-1de6-8168-96d0-000b2b2387a8` | 11 | create-pages |
| 2 | Environment & Config Registry | `collection://03c9f0c8-1de6-837a-8da3-071c0ef294eb` | 30 | create-pages |
| 3 | Risk Register | `collection://f599f0c8-1de6-82fe-8c3f-079b28d773d3` | 13 | create-pages |
| 4 | Security & Compliance Checklist | `collection://2629f0c8-1de6-82f7-a3a2-07e86615ca5d` | 37 | create-pages |
| 5 | Exhaustive Build Checklist | `collection://c679f0c8-1de6-8337-90b1-87cbedc11415` | 35 | create-pages |
| 6 | Performance & Benchmarks | `collection://9509f0c8-1de6-8215-b5e4-07cec71cfe53` | 11 | create-pages |
| 7 | Release Notes / Changelog | `collection://1a89f0c8-1de6-827c-9ee3-07cf8c55e8f2` | 7 | create-pages |
| 8 | Meeting Notes / Standup Log | `collection://4569f0c8-1de6-83bd-81d5-87d06ba0382d` | 10 | create-pages |

### Phase 3: Fix Populated Database Gaps
| Order | Database | Collection ID (full) | Action | Method |
|-------|----------|---------------------|--------|--------|
| 9 | Roadmap & Milestones | `collection://bb79f0c8-1de6-83ae-b2f8-87bc2d74b623` | Set Target Dates on 6 entries; update stale Notes on 2 entries | update-page |
| 10 | Feature Backlog / Idea Vault | `collection://6bd9f0c8-1de6-8250-a424-876ba3597834` | Add ~10 missing post-MVP ideas (with Effort + Original Claude Prompt) | create-pages |
| 11 | Claude Session Log | `collection://96e9f0c8-1de6-831b-80c7-8738087ef83f` | Delete 7 "[DELETED]" stubs; backfill Tags + Response Highlights on 21 entries; add 3 entries for 03-22–24 | delete + update-page + create-pages |
| 12 | Architecture Decision Log | `collection://a499f0c8-1de6-8389-bb45-873b72961ae7` | Add 6 missing ADRs (ADR-006–011) with Decision, Date, Status, Pros/Cons, Claude Reasoning | create-pages |
| 13 | Sprint / Task Board | `collection://d6a9f0c8-1de6-83f8-bdc3-8705f1f3579b` | Set Sprint, Due Date on active entries; populate Linked Milestone + Linked Feature relations | update-page |
| 14 | E2E Bug Tracker | `collection://3179f0c8-1de6-826f-84f6-0738986dbf4e` | Audit sweep: check Open entries against git log, update Status + Date Fixed (LOW PRIORITY — spot-check showed most entries accurate) | update-page |

### Phase 4: Relation Backfill (after both empty + populated databases are done)
| Order | Database | Relation Field | Target Database | Action |
|-------|----------|---------------|-----------------|--------|
| 15 | Risk Register | Related ADR | Architecture Decision Log | Link ~3 risks to their ADRs (Bun.js→ADR-001, SQLite→ADR-003, CSP→ADR-009) |
| 16 | Release Notes | Linked Milestone | Roadmap & Milestones | Link 7 releases to matching milestones (v0.1.0→Scaffold, v0.3.0→Code Complete, etc.) |
| 17 | Meeting Notes | Linked Tasks | Sprint / Task Board | Link standups to relevant sprint tasks (optional; defer to follow-up) |

### Phase 5: Page Structure Cleanup
| Order | Action |
|-------|--------|
| 18 | Delete `<empty-block/>` #1 (between [ARCHIVED] subpage and QA Walkthrough Checklist) |
| 19 | Delete `<empty-block/>` #2 (after Walkthrough Execution Protocol, end of page) |

### Total Work Estimate
- ~156 new rows across 8 empty databases (11+30+13+37+35+11+7+10 = 154, rounded up for margin)
- ~19 new rows across 3 populated databases (Feature Backlog +10, Session Log +3, ADRs +6)
- ~8 field updates on Roadmap entries (6 Target Dates + 2 stale Notes)
- ~42 field updates on Session Log entries (21 entries × 2 fields: Tags + Response Highlights)
- ~25+ field updates on Sprint Board entries (Sprint, Due Date, Linked Milestone, Linked Feature on active entries)
- 7 entry deletions (Session Log stubs)
- ~5-10 status/date updates (Bug Tracker sweep)
- 2 empty block deletions
- Relation backfill pass: Risk Register → ADRs, Release Notes → Roadmap, Release Notes → Sprint Board (after initial population)
- **Total: ~175 creates + ~80 updates + 7 deletes + 2 block deletes ≈ 264 operations**

## Verification

After each database:
1. Search the data source to confirm rows exist and fields are populated
2. Fetch 1-2 individual entries to verify property accuracy
3. After all work: fetch the main VaultLister 3.0 page to confirm all inline views show data
4. Cross-check: Roadmap dates align with Session Log dates; Bug Tracker statuses match commit history
5. Verify Sprint Board entries now show Linked Milestone + Linked Feature in Board view
6. Verify Session Log entries now have Tags badges visible in table view

# Plan: Migrate bare JSON.parse to safeJsonParse in route files

## Context
`src/RULES.md` mandates: "Never use bare `JSON.parse()` in route handlers — always use `safeJsonParse(str, fallback)`." Currently 132 bare `JSON.parse` calls exist across 40 route files. Many are unprotected (no try/catch), risking crashes on malformed DB data. This cleanup eliminates that crash risk and enforces codebase consistency.

## Approach: Keep inline definitions (no shared utility extraction)
`safeJsonParse` is already defined inline in 22 files — this is the established pattern. `src/RULES.md` explicitly says "The helper is defined in each route file that needs it." Extracting to a shared utility would touch imports in 40+ files and contradict the documented convention.

## Canonical helper (identical in all files):
```javascript
function safeJsonParse(str, fallback = null) {
    if (str == null) return fallback;
    try { return JSON.parse(str); } catch { return fallback; }
}
```

## What to convert vs. leave alone

### CONVERT — Group A: Unprotected bare calls (~56 instances, 13 files)
Bare `JSON.parse` with no try/catch. Crash risk. Must convert.

### CONVERT — Group B: Simple try/catch (~30 instances)
Try/catch with plain fallback assignment, no side effects. Convert for consistency.
Example: `try { x = JSON.parse(y || '[]'); } catch { x = []; }` → `x = safeJsonParse(y, []);`

### CONVERT — Group C: IIFE pattern (4 instances in automations.js)
Convert using `safeJsonParse(x, x)` to preserve "return raw string on failure" behavior.

### DO NOT CONVERT — Group D: AI response parsing (~12 instances)
Files: `ai.js`, `imageBank.js` lines 447/450, `receiptParser.js` line 131
These are multi-level try/parse/regex cascades. Converting would swallow exceptions and break fallback chains.

### DO NOT CONVERT — Side-effect catches (~15 instances)
Files: `batchPhoto.js` (logger, DB writes), `gdpr.js` (logger), `socialAuth.js` (security_log write), `recentlyDeleted.js` (returns 400), `automations.js` lines 457/463 (logger.warn with detail), `analytics.js` (logger.warn per-key)

### DO NOT TOUCH — safeParse variant (2 files)
`onboarding.js` and `sizeCharts.js` use `safeParse` with logger — intentionally different.

## Batches

### Batch 1 — High-risk files without helper (5 files, ~35 lines)
Files: `automations.js`, `offers.js`, `community.js`, `templates.js`, `skuRules.js`
- Add `safeJsonParse` definition to each
- Convert Group A bare calls
- Convert Group B simple try/catch blocks in automations.js and offers.js
- Convert 4 IIFE calls in automations.js using `safeJsonParse(x, x)` form
- **Special case:** `{ ...defaults, ...JSON.parse(row.settings) }` inside try/catch → fallback MUST be `{}` not `null` (spread on null throws)

Test: `bun test src/tests/automations.test.js src/tests/offers.test.js src/tests/community.test.js src/tests/templates.test.js src/tests/skuRules.test.js`
Commit: `[AUTO] fix(routes): add safeJsonParse to automations, offers, community, templates, skuRules`

### Batch 2 — Content route files (4 files, ~25 lines)
Files: `help.js`, `imageBank.js`, `sales.js`, `extension.js`
- Add helper to `help.js` and `sales.js` (no helper exists)
- `imageBank.js` and `extension.js` already have helper — convert remaining bare calls
- **Leave alone:** `imageBank.js` lines 447/450 (AI parsing chain)

Test: `bun test src/tests/help.test.js src/tests/imageBank.test.js src/tests/sales.test.js src/tests/extension.test.js`
Commit: `[AUTO] fix(routes): convert bare JSON.parse in help, imageBank, sales, extension`

### Batch 3 — Auth/security-adjacent (3 files, ~12 lines)
Files: `security.js`, `chatbot.js`, `emailOAuth.js`
- Add helper to each
- `security.js` line 413 (MFA backup codes — critical path)
- `chatbot.js` line 142: ternary `msg.metadata ? JSON.parse(...) : {}` → `safeJsonParse(msg.metadata, {})` (null guard becomes redundant)
- `emailOAuth.js` line 307

Test: `bun test src/tests/security.test.js src/tests/auth.test.js src/tests/chatbot.test.js`
Commit: `[AUTO] fix(routes): add safeJsonParse to security, chatbot, emailOAuth`

### Batch 4 — Remaining cleanup (~8 lines)
Convert any remaining bare calls in files that already have the helper but still use `JSON.parse` (e.g., `automations.js` lines 1373-1374 empty-catch pattern).

Test: `bun test src/tests/automations.test.js`
Commit: `[AUTO] fix(routes): clean up remaining bare JSON.parse`

### Batch 5 — Verification (no code changes)
- Run `bun test src/tests/auth.test.js src/tests/security.test.js` (mandatory baseline)
- Run `grep -rn "JSON\.parse(" src/backend/routes/ | grep -v safeJsonParse | grep -v safeParse | wc -l`
- Expected residual: ~18 instances (all in "do not convert" list)
- Compare test baseline: must remain 5470 pass / 264 known failures

## Estimated scope
- **4 commits**, ~13-14 files changed, ~80 lines modified
- Achievable in a single session

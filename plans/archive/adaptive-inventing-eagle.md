# Plan: Cross-Listing Automation — Fix Gaps & Make Production-Ready

## Context
Cross-listing is the highest business-value feature remaining. The infrastructure is ~80% built — all 9 publish bots work, backend routes exist for every platform, and per-platform frontend handlers follow a correct two-step draft+publish flow. However, the **Advanced Cross-List** modal path is broken (creates drafts but never publishes), there's dead code causing confusion, and batch publishes have no progress feedback. This plan fixes the 6 concrete gaps to make cross-listing production-ready.

---

## What Already Works
- **9 publish services**: eBay (Sell API), Etsy (REST API), Shopify (Admin API), Poshmark/Mercari/Depop/Grailed/Facebook/Whatnot (Playwright bots)
- **Per-platform Quick Publish**: `publishSelectedToEbay()` etc. — two-step draft+publish, all 9 functional
- **Publish to ALL**: `publishSelectedToAll()` — iterates all 9 platforms, results modal with retry button
- **Basic crosslist**: `submitCrosslist()` — creates drafts via `POST /crosslist` (by design, no auto-publish)
- **Backend routes**: `POST /:id/publish` generic dispatcher + 9 per-platform routes
- **WebSocket service**: Already has `listing.created`, `listing.updated` event types and `sendToUser()` pattern

---

## Gaps to Fix (6 items)

### Gap 1: Remove dead stub `submitAdvancedCrosslist` at line ~7314
**File:** `src/frontend/handlers/handlers-inventory-catalog.js`
- Line 7314 is a fake stub (client-side fake IDs, no API call)
- Line 7984 is the real handler (calls `/listings/batch`)
- **Fix:** Delete the stub at 7314. The real handler at 7984 already reads the correct camelCase field names from the active modal.

### Gap 2: Advanced crosslist must PUBLISH, not just create drafts
**File:** `src/frontend/handlers/handlers-inventory-catalog.js` ~line 7984
- Currently calls `POST /listings/batch` → creates `status: 'active'` records but never calls publish endpoints
- **Fix:** After batch creation, iterate the created listings and call `POST /listings/{id}/publish` (the generic dispatcher) for each. This reuses the existing publish infrastructure. Add the same results modal pattern from `publishSelectedToAll`.

### Gap 3: Add Mercari, Grailed, Etsy to advanced crosslist modal
**File:** `src/frontend/ui/modals.js` ~line 1853
- Currently only 6 platforms: poshmark, ebay, whatnot, depop, shopify, facebook
- **Fix:** Add mercari, grailed, etsy checkboxes + platform-specific field panels
- Mercari fields: condition, shipping_method
- Grailed fields: designer, category
- Etsy fields: who_made, when_made, is_supply (required by Etsy API)

### Gap 4: Remove old modal at line ~1088
**File:** `src/frontend/ui/modals.js`
- Line 1088 version uses old underscore field naming, only exists as dead code
- **Fix:** Delete the old modal function (lines ~1088-1285). The active modal at line 1853 is the one called by `startAdvancedCrosslist`.

### Gap 5: Add WebSocket progress events during batch publish
**Files:** `src/backend/routes/listings.js`, `src/backend/services/websocket.js`
- Currently no real-time feedback during multi-platform publishes
- **Fix:** In each platform-specific publish route handler, after successful publish, broadcast a `listing.published` event via `ws.sendToUser(userId, { type: 'listing.published', platform, listingId, status: 'success'|'error' })`. Add the event type to `MESSAGE_TYPES`.
- Frontend: listen for `listing.published` events to update a progress indicator. Simple approach — update a progress counter in the existing results modal.

### Gap 6: Add publish retry for individual failed platforms
**File:** `src/frontend/handlers/handlers-inventory-catalog.js`
- `publishSelectedToAll` already has a "Retry Failed Platforms" button but it retries ALL items again
- **Fix:** Track which specific listingId+platform combos failed. The retry button should only re-publish those specific failures, not redo the entire batch.

---

## Implementation Order

1. **Gap 1 + 4** — Delete dead code (stub handler + old modal) — cleanup first
2. **Gap 3** — Add missing platforms to modal — quick UI addition
3. **Gap 2** — Wire advanced crosslist to publish — core fix
4. **Gap 6** — Targeted retry logic — improves reliability
5. **Gap 5** — WebSocket progress — nice-to-have polish

---

## Key Files to Modify

| File | Changes |
|------|---------|
| `src/frontend/handlers/handlers-inventory-catalog.js` | Delete stub at ~7314; update `submitAdvancedCrosslist` at ~7984 to publish after batch create; improve retry logic in `showPublishAllResultsModal` |
| `src/frontend/ui/modals.js` | Delete old modal at ~1088; add mercari/grailed/etsy to modal at ~1853 |
| `src/backend/routes/listings.js` | Add `listing.published` WebSocket event in publish routes |
| `src/backend/services/websocket.js` | Add `listing.published` to MESSAGE_TYPES |

## Verification
1. Open Cross-Lister page → select items → click "Advanced Cross-List"
2. Verify all 9 platforms appear as checkboxes
3. Select platforms, fill fields, submit → verify drafts are created AND publish is triggered
4. Check WebSocket events fire during publish
5. Simulate a publish failure → verify retry button only retries the failed platform+item combos
6. Run `bun test src/tests/auth.test.js src/tests/security.test.js` before commit
7. Run relevant E2E tests: `npx playwright test e2e/tests/inventory.spec.js`

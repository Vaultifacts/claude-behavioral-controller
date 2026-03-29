# Fix 8 High-Severity QA Backlog Items

## Context
QA Walkthrough Checklist has 150 skipped items; 8 are High severity and actionable. Most code already exists — hidden widgets, orphaned modals, unwired utilities. This plan makes minimal targeted fixes to close all 8.

---

## Step 1: Enable 4 Fully-Implemented Dashboard Widgets (#50, #51, #55, #60)

**File:** `src/frontend/ui/widgets.js` (~line 1046-1069)

Change `visible: false` → `visible: true` and `collapsed: true` → `collapsed: false` for:
- `sales-forecast` (order 9)
- `conversion-funnel` (order 10)
- `ship-today` (order 14)
- `recent-items` (order 19)

**Note:** Existing users with localStorage state will keep their old settings (merge logic at line 1078 uses `{ ...def, ...savedWidget }`). This only affects new users/cleared cache. For QA verification, toggle via Customize Dashboard.

---

## Step 2: Fix Cash Flow Widget (#53) — 2 Code Fixes + Enable

### Fix A — Load purchases on dashboard
**File:** `src/frontend/handlers/handlers-core.js` line 1829

Add `handlers.loadPurchases()` to the `Promise.all` in `refreshDashboard()`:
```js
await Promise.all([
    handlers.loadInventory(),
    handlers.loadListings(),
    handlers.loadSales(),
    handlers.loadOffers(),
    handlers.loadOrders(),
    handlers.loadPurchases()  // <-- ADD for Cash Flow widget
]);
```

### Fix B — CSS class name mismatch
**File:** `src/frontend/ui/widgets.js` line 3263

Change `ticker-track` → `ticker-content` so the CSS `@keyframes tickerScroll` animation (defined on `.ticker-content` at main.css:15216) actually applies:
```js
// Before:
<div class="ticker-track">
// After:
<div class="ticker-content">
```

### Enable
**File:** `src/frontend/ui/widgets.js` — set `cash-flow` to `visible: true, collapsed: false`

---

## Step 3: Wire Duplicate Scanner Navigation (#218)

### 3a — Register route
**File:** `src/frontend/app.js` (near line 70196 where other tool routes are registered)

```js
router.register('duplicates', () => modals.duplicates());
```

### 3b — Add card to sidebar/tools navigation
**File:** `src/frontend/pages/pages-tools-tasks.js`

Find the Image Bank page or a suitable tools entry point. Add a "Duplicate Scanner" action button in the image-bank or inventory toolbar, OR add an entry in the sidebar nav for tools. The simplest approach: add the route registration (3a) so existing "View Duplicates" buttons in the cleanup suggestions modal (app.js:67440) actually work.

### 3c — Fix dead nav in settings cleanup
**File:** `src/frontend/app.js` line 67440 — already uses `router.navigate('duplicates')`, which will now work after 3a.

---

## Step 4: Add Expandable Rows to Pending Offers Table (#131)

**File:** `src/frontend/pages/pages-sales-orders.js` (~lines 245-341)

For each offer `<tr>`:
1. Add `class="expandable"` and a chevron click handler in the first cell:
   ```html
   <td><span class="expand-trigger" onclick="expandableTable.toggle(this.closest('tr'))">▶</span> <input type="checkbox" ...></td>
   ```
2. Insert a hidden detail row after each offer row:
   ```html
   <tr class="expand-content" style="display:none">
     <td colspan="10">
       <!-- item thumbnail, listing description, offer history -->
     </td>
   </tr>
   ```

Uses the existing `expandableTable.toggle()` utility (app.js:2895) and CSS styles (main.css:42061-42096). No new utilities needed.

**Data available in scope:** Each offer row already has access to `offer.item_title`, `offer.item_images`, `offer.listing_description` etc. from the offers API response.

---

## Step 5: Close Bulk Offer Actions As-Is (#129)

No code changes. Feature is fully implemented:
- Frontend: bulk accept/decline with confirmation dialogs, spinner, error tracking (`handlers-sales-orders.js:388-481`)
- Backend: individual accept/decline endpoints with TOCTOU protection (`offers.js:96-190`)
- UI: toolbar buttons disabled when no selection (`pages-sales-orders.js:182-187`)

Update Notion to "Pass" with note: "Client-side iteration approach — atomic bulk endpoint deferred as enhancement."

---

## Step 6: Rebuild + Verify

```bash
bun run dev:bundle
bun run dev:stop && bun run dev:bg
```

Verify:
1. Dashboard shows Sales Forecast (SVG chart), Conversion Funnel, Ship Today, Recent Items, Cash Flow (ticker scrolling with green/red items)
2. Tools → "View Duplicates" button opens Duplicate Scanner modal → "Scan Now" works
3. Offers page → pending offers have expand chevrons → click shows item details
4. Bulk accept/decline buttons still work

---

## Step 7: Update Notion + Commit

Update 8 QA items from "Skipped" → "Pass" via `notion-qa-audit.py`.

```bash
git add src/frontend/ui/widgets.js src/frontend/pages/pages-sales-orders.js \
       src/frontend/handlers/handlers-core.js src/frontend/app.js
git commit -m "fix(frontend): enable 5 dashboard widgets, wire duplicate scanner route, add offer expandable rows"
git push origin master
```

---

## Files Modified

| File | Changes |
|------|---------|
| `src/frontend/ui/widgets.js` | 5 widgets visible:true + ticker-track→ticker-content |
| `src/frontend/handlers/handlers-core.js` | Add loadPurchases() to refreshDashboard |
| `src/frontend/app.js` | Register 'duplicates' route |
| `src/frontend/pages/pages-sales-orders.js` | Expandable rows on pending offers table |

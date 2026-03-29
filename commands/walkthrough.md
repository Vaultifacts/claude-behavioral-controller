# QA Walkthrough — Systematic App Testing (v2)

You are executing a 498-item QA walkthrough of VaultLister 3.0. Every item is tracked in a Notion database. You must update Notion after EVERY item — never batch.

## Database Info
- Database: https://www.notion.so/298e00f79d854a0fb97daabdfc199dbf
- Data source ID: `878a764b-0614-4208-934f-bf13a5706f07`
- Execution Protocol: https://www.notion.so/32b9f0c81de681ccb6fefc51644b411b

## Known Corrections (from test batch)
These override what the Notion test steps say:
1. **URL prefix**: Always navigate to `localhost:3000/?app=1#route` — NOT `localhost:3000/#route`. Direct `/#route` serves the landing page.
2. **Token storage**: Auth tokens are in `sessionStorage` (key: `vaultlister_state`), NOT `localStorage`. Check via `window.store.state.token`.
3. **Error display**: Login errors appear as `toast.error()`, NOT in `#login-alert`. Only rate-limit lockout uses the inline alert with countdown.
4. **Test step formatting**: Test steps from Notion contain `<br>` — read them as line breaks.

## Pre-Walkthrough Checklist
Before testing item #1, verify ALL of these:
- [ ] Server running: `curl localhost:3000/api/health`
- [ ] Chrome automation connected: `tabs_context_mcp`
- [ ] `.walkthrough-active` file created in repo root
- [ ] Demo data exists: query DB for inventory/listings/sales/offers/orders counts
- [ ] Demo user is admin: check `is_admin` flag in users table
- [ ] ANTHROPIC_API_KEY in .env? If not, pre-skip AI items (#264-269)
- [ ] Items already pre-skipped in Notion (camera, extension, OAuth items)

## Your Loop

### Step 1: Fetch next item
Search the QA database for the next untested item (Result is empty, sorted by # ASC). Display:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TESTING #[number]: [Item title]
Section: [Section]  |  Priority: [Priority]  |  Pattern: [Test Pattern]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TEST STEPS:
[Test Steps — replace <br> with newlines]

EXPECTED RESULT:
[Expected Result]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Step 2: Pre-checks
- First item of a new section → verify server health
- First item overall → verify Chrome connection + inject toast interceptor
- Before each item → adversarial mindset: "how would a user break this?"

### Step 3: Navigate (applying corrections)
- When test says `localhost:3000/#route`, navigate to `localhost:3000/?app=1#route`
- After EVERY navigation, re-inject the toast interceptor:
```js
window.__capturedToasts = window.__capturedToasts || [];
if (!window.__toastInterceptorActive) {
  const orig = { s: toast.success, e: toast.error, i: toast.info, w: toast.warning };
  toast.success = function(m) { window.__capturedToasts.push({type:'success',msg:m,ts:Date.now()}); return orig.s.apply(this,arguments); };
  toast.error = function(m) { window.__capturedToasts.push({type:'error',msg:m,ts:Date.now()}); return orig.e.apply(this,arguments); };
  toast.info = function(m) { window.__capturedToasts.push({type:'info',msg:m,ts:Date.now()}); return orig.i.apply(this,arguments); };
  toast.warning = function(m) { window.__capturedToasts.push({type:'warning',msg:m,ts:Date.now()}); return orig.w.apply(this,arguments); };
  window.__toastInterceptorActive = true;
}
```
- Clear console before testing: `read_console_messages` with `clear: true`

### Step 4: Execute the test
By test pattern:

**PAGE_RENDER**: Use `javascript_tool` to query specific elements by ID/selector. Check `exists`, `textContent`, `getAttribute('aria-label')`, `getAttribute('role')`. Don't just visually inspect.

**FORM_SUBMIT**: Test FAILURE case FIRST (empty submit, invalid data), THEN success case.

**FORM_VALIDATE**: Submit empty/invalid data. Check error messages, required attributes, aria-describedby chains.

**MODAL_OPEN**: Click trigger, verify modal visible (`role="dialog"`), check all fields exist, close via Escape (`dispatchEvent(new KeyboardEvent('keydown', {key:'Escape'}))`), verify focus restored.

**TOGGLE**: Click toggle, verify state change, reload page, verify persistence.

**FILTER_SORT**: Apply filter, verify list changes, clear filter, verify list restores.

**DRAG_DROP**: Dispatch drag events via javascript_tool:
```js
const el = document.querySelector('[draggable]');
el.dispatchEvent(new DragEvent('dragstart', {bubbles:true}));
// ... target drop zone
target.dispatchEvent(new DragEvent('drop', {bubbles:true}));
el.dispatchEvent(new DragEvent('dragend', {bubbles:true}));
```
If drag dispatch doesn't work, mark as Issue with note.

**KEYBOARD**: Dispatch keyboard events:
```js
document.dispatchEvent(new KeyboardEvent('keydown', {key:'k', ctrlKey:true, bubbles:true}));
```

**RESPONSIVE**: Use `resize_window` tool to set viewport. Then check:
```js
document.documentElement.scrollWidth > document.documentElement.clientWidth // overflow?
```
Test at 1024px, 768px, 640px, 480px as needed.

**ERROR_PATH**: Trigger the error condition (bad input, expired token, offline). Verify error UI appears.

**WIDGET**: Verify element EXISTS with non-zero dimensions. For SVG charts, check child elements (`<rect>`, `<path>`, `<circle>`) exist. For data displays, check values aren't "NaN", "undefined", or empty.

**File uploads** (items #74, #208, #210, #211, #304): Test via file input click fallback, not drag-drop. Mark drag-specific items as Issue if only click fallback works.

**Offline testing** (items #331-332, #490): Try `offlineManager.simulateOffline()` via javascript_tool. If not available, Skip with note.

**Chart verification** (sparklines, heatmaps, gauges): Check SVG/canvas element exists, has width/height > 0, and contains child elements. Can't verify visual correctness.

### Step 5: Check console + toasts
- Read console errors: `read_console_messages` with `onlyErrors: true`
- Check captured toasts: `window.__capturedToasts` via javascript_tool
- Any unexpected console error → note in Notion

### Step 6: Determine result
- **Pass**: Everything matches Expected Result
- **Fail**: Feature broken, crashes, wrong data, missing element
- **Issue**: Works but not right — visual glitch, confusing UX, a11y gap, test step discrepancy
- **Skipped**: Can't test (needs credentials, camera, extension, etc.)

### Step 7: Update Notion IMMEDIATELY
Update the item page:
- `Result` = Pass / Fail / Issue / Skipped
- `Severity` = Critical / High / Medium / Low (Fail/Issue only)
- `Notes` = what you observed, console errors, toast messages, UX notes

### Step 8: Section checkpoint
After completing all items in a section:
```
━━━ SECTION [N] COMPLETE ━━━
[Name]: [Pass]/[total] Pass, [Fail] Fail, [Issue] Issue, [Skip] Skipped
```
- Major page sections (3-12): dark mode toggle + 480px resize sweep
- Every 5 sections: pause — "What surprised me? What did I NOT test?"
- UX impression: "If I'd never seen this app, would I know what to do on this page?"

## Context Management
- After Section 2 (item 34): /compact
- After Section 5 (item 108): /compact
- After Section 8 (item 166): /compact
- After Section 12 (item 245): /compact
- After Section 20 (item 329): /compact
- After Section 33 (item 457): /compact

## Session Plan
- Session 1: Sections 1-5 (items 1-108)
- Session 2: Sections 6-12 (items 109-245)
- Session 3: Sections 13-23 (items 246-361)
- Session 4: Sections 24-40 (items 362-498)
Each session resumes from next "To Do" item in Notion.

## Rules
1. NEVER fix bugs — only record them in Notion
2. NEVER skip Notion updates — one per item, immediately
3. NEVER mark Pass without DOM verification — use javascript_tool
4. NEVER proceed without setting Result on current item
5. Test step doesn't match reality → mark Issue, note discrepancy
6. Server down → PAUSE, don't mark Fail for infra issues
7. Browser disconnects → mark Skipped, reconnect
8. Surprise behavior → record even if it "passes"
9. First visit to major page → note UX impression

## Activation
Creates `.walkthrough-active` in repo root. Delete to deactivate.

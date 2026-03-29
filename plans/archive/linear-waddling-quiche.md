# Plan: Search/Filter Bar for Kanban Board

## Context
Cycle 3 of a Claude↔ChatGPT bridge build session. The board now has a v2 schema with labels and card colors. The next feature is a search/filter bar so users can quickly locate cards across columns. ChatGPT advised: keep filters in separate UI state (not persisted), highlight/dim rather than hide, debounce input, and filter by label with `.some()`.

## Approach

### UI State (not persisted)
Add a module-level `uiState` object:
```js
let uiState = { query: '', activeLabelIds: new Set() };
```
This is never written to localStorage — it resets on page load.

### HTML Changes (`index.html`)
Add a filter bar between `<h1>` and the add-column button in `#app-header`:
```html
<div id="filter-bar">
  <input id="search-input" type="text" placeholder="Search cards…" autocomplete="off" />
  <div id="label-filter-pills"></div>
  <button id="clear-filters" class="btn btn-ghost btn-sm hidden">✕ Clear</button>
</div>
```

### CSS Changes (`style.css`)
- `#filter-bar` — flex row, gap, align-center, wrappable
- `#search-input` — reuse `.modal-input` sizing, rounded, ~260px wide
- `#label-filter-pills` — flex row, flex-wrap, gap
- `.filter-pill` — small pill matching `.label-pill` style but smaller, toggleable
- `.card.dimmed` — `opacity: 0.18`, `pointer-events: none`
- `#clear-filters` — styled btn-ghost, hidden when no filter active

### JS Changes (`app.js`)

1. **`renderFilterBar()`** — called at end of `render()`. Builds label filter pills from `state.labelsById`. Pills are toggled active via `uiState.activeLabelIds`. Shows/hides `#clear-filters` button when filters are active.

2. **`matchesFilter(card)`** — pure function:
   ```js
   function matchesFilter(card) {
     const q = uiState.query.trim().toLowerCase();
     const textMatch = !q || card.text.toLowerCase().includes(q);
     const labelMatch = uiState.activeLabelIds.size === 0 ||
       card.labelIds.some(id => uiState.activeLabelIds.has(id));
     return textMatch && labelMatch;
   }
   ```

3. **`buildCard()` modification** — after building card element, add `.dimmed` if `!matchesFilter(card)`.

4. **Event listeners** (attached once on DOMContentLoaded):
   - Search input: debounced 200ms → update `uiState.query` → `render()`
   - Label pill click: toggle `uiState.activeLabelIds` → `render()`
   - Clear button: reset `uiState` → `render()`

5. **`renderFilterBar()` also handles**: when `labelsById` is empty, hide the pill section.

### What does NOT change
- `state` shape — no schema change, no v3 migration needed
- localStorage persistence logic — `uiState` is never saved
- DnD logic — `.dimmed` cards have `pointer-events: none`, they can't be dragged
- Modal logic — unaffected

## Files to Modify
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\index.html`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\style.css`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\app.js`

## Verification
1. Open `index.html` in browser
2. Type in search box → cards not matching dim in real time (debounced ~200ms)
3. Click a label pill in filter bar → only cards with that label remain visible
4. Combine text + label filter → both constraints applied
5. Click ✕ Clear → all cards return to full opacity
6. localStorage data unchanged after filtering (open DevTools → Application → Storage)

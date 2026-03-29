# Plan: Add Priority Levels to Kanban Board

## Context
Adding Low / Medium / High / Critical priority to cards, with a visual badge on each card, priority filtering in the filter bar, and optional sort-by-priority. ChatGPT suggested keeping a PRIORITY_ORDER map, treating priorities like label filters (Set in uiState), and never persisting derived flags.

## Critical Files
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\app.js`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\index.html`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\style.css`

---

## Implementation Plan

### 1. Data model (app.js)
- Bump schema to `version: 3`
- Add `priority: null` to new cards (`addCard()` at line 108)
- Add migration block: v2→v3 iterates all cards and sets `priority: null` if missing
- Add `PRIORITY_CONFIG` constant:
  ```js
  const PRIORITY_CONFIG = {
    low:      { label: 'Low',      color: '#6bcb77', order: 1 },
    medium:   { label: 'Medium',   color: '#f4c430', order: 2 },
    high:     { label: 'High',     color: '#ff8c42', order: 3 },
    critical: { label: 'Critical', color: '#e05c5c', order: 4 },
  };
  ```

### 2. uiState (app.js)
- Add `activePriorities: []` to the `uiState` object (line 180)
- Update `cardMatchesFilter()` to also check:
  ```js
  const priorityMatch = activePriorities.length === 0 ||
    (card.priority && activePriorities.includes(card.priority));
  return textMatch && labelMatch && priorityMatch;
  ```

### 3. Card rendering — priority badge (app.js `buildCard`)
- After the due-date badge, add a priority badge if `card.priority` is set:
  ```js
  if (card.priority) {
    const cfg = PRIORITY_CONFIG[card.priority];
    const badge = document.createElement('div');
    badge.className = 'priority-badge';
    badge.style.background = cfg.color + '30'; // ~19% opacity
    badge.style.color = cfg.color;
    badge.textContent = '▲ ' + cfg.label;
    el.appendChild(badge);
  }
  ```

### 4. Filter bar — priority pills (app.js + index.html)
- Add a `<div id="priority-filter-row">` row below the label-filter row in index.html
- Render toggleable priority pills (Low / Medium / High / Critical) similarly to label filter pills
- Toggle logic: add/remove from `uiState.activePriorities`, re-render all cards
- "× Clear" logic already clears everything; extend it to also reset `activePriorities`

### 5. Card-edit modal — priority selector (index.html + app.js)
- Add a new `<div class="form-section">` for Priority inside `#card-edit-extras`
- Render 5 buttons: None + the 4 priorities, styled as a segmented control
- Active selection highlighted with the priority color; stored in `modalContext.selectedPriority`
- `updateCard()` called with `priority: modalContext.selectedPriority`

### 6. CSS (style.css)
- `.priority-badge` — same pill shape as `.due-badge`, `pointer-events: none`
- `.priority-filter-pill` — same shape as label filter pills; active state uses the priority color as border/background tint
- `.priority-selector` — segmented row of buttons in modal; active button gets colored background

### 7. Verification
- Open `index.html` in browser; existing v2 cards auto-migrate (priority = null)
- Edit a card → Priority section shows 5 options; selecting one saves and shows badge on card
- Filter bar: clicking a priority pill dims non-matching cards
- Multiple priorities selected = OR logic (any match passes)
- "× Clear" resets text + labels + priorities

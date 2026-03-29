# Plan: Card Detail / Activity Log Sidebar

## Context
Add a slide-in sidebar panel that opens when a card is clicked (not on the edit/delete buttons). The sidebar shows full card details and a timestamped notes/activity log. Notes are stored immutably in `card.notes[]` and persisted to localStorage.

## Changes

### 1. Data Migration: v3 → v4 (app.js)
- Add `notes: []` to each card in `migrateV3toV4()`
- Bump `DATA_VERSION` from 3 → 4
- Note shape: `{ id: crypto.randomUUID(), text, createdAt: ISO string }`

### 2. UIState Extension (app.js)
```js
uiState.activeCardId = null;  // null = closed; cardId = open
```
No `sidebarOpen` bool needed — null check suffices.

### 3. New Functions (app.js)
- `openSidebar(cardId)` — sets uiState.activeCardId, calls render()
- `closeSidebar()` — sets null, calls render()
- `addNote(cardId, text)` — appends `{id, text, createdAt}` to card.notes, calls commit()
- `renderSidebar()` — called inside render(); builds sidebar content, auto-scrolls activity log

### 4. Card Click Guard (app.js buildCard)
```js
el.addEventListener('click', (e) => {
  if (isDragging) return;
  if (e.target.closest('.card-btn-row')) return;
  openSidebar(card.id);
});
```

### 5. Sidebar HTML (index.html)
Add `<aside id="card-sidebar">` after the modal overlay:
- Header: card title + × close button
- Details section: labels, due date badge, priority badge
- Activity log: scrollable list of timestamped notes (newest-last), auto-scroll on add
- Input area: `<textarea>` + "Add Note" button (Enter submits, Shift+Enter = newline)

### 6. Styles (style.css)
- `.card-sidebar` — fixed right panel, 320px wide, full height, z-index 500, slide-in via `transform: translateX(100%)` → `translateX(0)`
- `.sidebar-open` class on `<body>` or `#board-wrap` to shift board left (or just overlay)
- `.activity-item` — timestamp (muted, small) above note text
- `.sidebar-details` — mini-badges row mirroring card badges

## Critical Files
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\app.js`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\index.html`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\style.css`

## Verification
Open `index.html` in browser → click a card body → sidebar slides in from right with card title, labels/due/priority badges, empty activity log, and note input. Type a note, press Enter or click "Add Note" → note appears with timestamp, auto-scrolled into view. Reload page → notes persist. Click × or press Escape → sidebar closes.

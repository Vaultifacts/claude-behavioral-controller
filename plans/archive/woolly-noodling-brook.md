# Plan: Due-Date Quick Toggle Button on Cards

## Context
Cards with due dates show a badge (📅/⏰/⚠) but require opening the sidebar to clear or update the date. Adding a one-click "Done" button directly on the badge lets users dismiss overdue/due-soon cards instantly without interrupting their workflow.

## Approach
Add a small `✓` button inside the due-date badge on every card that has a due date. Clicking it clears `dueDate` (`updateCard(id, { dueDate: null })`), which removes the card from overdue tracking and re-renders the board.

## Files to modify
- **app.js** — `buildCard()` lines 1164–1173: add button element inside due badge with click handler
- **style.css** — add `.due-done-btn` styles (small inline button, hidden until badge hover)

## Implementation detail

### app.js — inside `buildCard()`, after badge textContent is set (after line 1172):
```js
const doneBtn = document.createElement('button');
doneBtn.className = 'due-done-btn';
doneBtn.textContent = '✓';
doneBtn.title = 'Mark done (clear due date)';
doneBtn.draggable = false;
doneBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  updateCard(card.id, { dueDate: null });
  renderBoard();
});
badge.appendChild(doneBtn);
```

### style.css — new rules:
```css
.due-badge { position: relative; display: inline-flex; align-items: center; gap: 4px; }
.due-done-btn {
  background: none; border: none; cursor: pointer; padding: 0 2px;
  font-size: 0.75rem; opacity: 0; transition: opacity 0.15s;
  color: inherit; line-height: 1;
}
.card:hover .due-done-btn,
.card:focus-within .due-done-btn { opacity: 1; }
```

## Verification
1. Open `index.html`
2. Add a card with a past due date → badge shows ⚠ overdue
3. Hover the card → `✓` button appears in the badge
4. Click `✓` → due date clears, badge disappears, stats bar updates
5. Reload → due date remains cleared (localStorage persisted)

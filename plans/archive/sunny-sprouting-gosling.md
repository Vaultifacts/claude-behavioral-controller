# Plan: Due-Date ✓ Done Button on Cards

## Context
The Kanban board has due-date badges on cards showing overdue/due-soon/normal states. Users need a one-click way to clear a card's due date directly from the board view, without opening the edit modal.

## Approach
Add a small `✓` button inside the due-date badge (hover-revealed). Clicking it sets `card.dueDate = null`, saves state, and re-renders — removing the badge and updating the stats bar overdue count instantly.

## Files to Modify

### `app.js` — `buildCard()` around line 1164
Current due-date block:
```js
const dueState = getDueState(card);
if (dueState) {
  const badge = document.createElement('div');
  badge.className = 'due-badge due-' + dueState;
  badge.draggable = false;
  const icon = dueState === 'overdue' ? '⚠ ' : (dueState === 'due-soon' ? '⏰ ' : '📅 ');
  badge.textContent = icon + formatDueDate(card.dueDate);
  el.appendChild(badge);
}
```

Change: wrap text in a `<span>`, append a `<button class="due-done-btn">✓</button>` inside the badge. Button click handler:
```js
doneBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  state.cardsById[card.id].dueDate = null;
  saveState();
  render();
});
```

### `style.css` — add `.due-done-btn` styles
```css
.due-badge { position: relative; }
.due-done-btn {
  opacity: 0;
  transition: opacity 0.15s;
  margin-left: 4px;
  padding: 0 3px;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.75rem;
  line-height: 1.4;
  background: rgba(255,255,255,0.25);
  color: inherit;
}
.card:hover .due-done-btn,
.card:focus-within .due-done-btn { opacity: 1; }
```

## Verification
1. Open `index.html`
2. Add a card with a past due date → badge shows ⚠ Overdue
3. Hover the card → ✓ button appears inside the badge
4. Click ✓ → badge disappears, stats-bar Overdue count decrements
5. Reload page → due date is gone (persisted to localStorage)

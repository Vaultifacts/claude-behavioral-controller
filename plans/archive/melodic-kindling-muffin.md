# Plan: Due-Date Quick Toggle (✓ Done Button)

## Context
Currently, users must open the card detail sidebar to clear a due date. The goal is to add a small checkmark button (✓) directly on the due-date badge that clears the date in one click, removing the card from overdue tracking and updating the board stats instantly. This speeds up day-to-day status updates.

## Approach

### 1. Add "Clear Due Date" Button to Card Badge (app.js ~1164)
Inside `buildCard()`, when rendering the due-date badge, append a small clickable button inside or adjacent to the badge:
```
<div class="due-badge due-{state}">
  📅 Mar 15, 2026
  <button class="due-clear-btn">✓</button>  <!-- NEW -->
</div>
```

**Implementation steps:**
- After creating the `badge` element (line 1169), create a `clearBtn` button element
- Set `clearBtn.className = 'due-clear-btn'`
- Add click handler that calls `updateCard(card.id, { dueDate: null })`
- Stop propagation to prevent card click from triggering
- Append button to badge

### 2. CSS for Hidden/Hover Reveal (style.css)
Add `.due-clear-btn` styling to hide by default and reveal on card hover:
```css
.due-clear-btn {
  opacity: 0;
  transition: opacity .15s;
  background: none;
  border: none;
  color: inherit;
  cursor: pointer;
  padding: 0 2px;
  font-size: 0.9em;
  line-height: 1;
}
.card:hover .due-clear-btn { opacity: 1; }
```

### 3. Event Handler Pattern (app.js ~1170)
Follow the existing pattern from `card-btn-row` buttons:
```javascript
clearBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  updateCard(card.id, { dueDate: null });
});
```

This triggers:
- `commit()` → persists to localStorage + re-renders
- `calculateStats()` re-runs automatically (board stats update)
- Badge disappears from the card
- Any card-position changes handled by `render()`

## Critical Files
- `app.js` (lines 1121-1300: buildCard function)
- `style.css` (lines 597-610: due-badge styles + new .due-clear-btn rules)

## Reusable Patterns Found
- **Hover-reveal pattern**: Card button row (`card-btn-row` / `.card:hover .card-btn-row`)
- **Event handler pattern**: `e.stopPropagation()` + `updateCard(cardId, {...})` (existing buttons at lines 1238-1271)
- **State mutation**: `updateCard()` at line 214 already handles `dueDate: null`
- **Auto-stats update**: `commit()` automatically calls `render()` which calls `calculateStats()`

## Testing Checklist
1. Open `index.html`
2. Add a card with a due date in the future
3. Hover the card — the ✓ button appears on the due-date badge
4. Click the ✓ button — the due-date badge disappears instantly
5. Check the stats bar — if this was the only overdue card, the overdue count decrements
6. Reload the page — the due date is gone (persisted to localStorage)
7. Keyboard: Tab to the due-date badge and try Space/Enter (should work if button is keyboard-accessible via natural tab order)

## Edge Cases Handled by Existing Code
- No due date? Button doesn't render (only in `if (dueState)` block)
- Card without stats bar? Stats still update in state/storage
- Multiple cards cleared rapidly? Debounced localStorage save handles it

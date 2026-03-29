# Implementation Plan: Bulk Action Bar Roving Tabindex & Focus Management

## Context
The Kanban board already has a roving tabindex system for the bulk action bar (keyboard navigation via arrows and Home/End). However, the current implementation traps Tab focus, preventing natural keyboard escape, and doesn't restore focus after clearing selection. This plan adds proper focus management:

1. **Allow Tab/Shift+Tab to exit** at boundaries (don't trap)
2. **Return focus after "Clear selection"** to a stable target (first card in DOM order)
3. **Keep arrow/Home/End navigation** within the bar (no change needed)

## Key Files to Modify
- `app.js` (lines 3437–3475): roving tabindex keydown handler in `renderBulkActionBar()`
- `app.js` (lines 3350–3362): "Clear" button click handler

## Implementation Strategy

### 1. Tab Focus Escape (lines 3437–3446)
**Current behavior**: Tab is prevented and wraps around within the bar.
**New behavior**:
- If Tab is pressed and the active control is the **last** focusable element, do NOT prevent default (let Tab escape naturally)
- If Shift+Tab is pressed and the active control is the **first** focusable element, do NOT prevent default (let Shift+Tab escape naturally)
- Otherwise, prevent default and move focus to the next/previous control within the bar

**Code change**:
```javascript
if (e.key === 'Tab') {
  const currentIndex = focusableEls.indexOf(document.activeElement);
  // Allow exit at boundaries
  if ((e.shiftKey && currentIndex === 0) || (!e.shiftKey && currentIndex === focusableEls.length - 1)) {
    return; // allow natural Tab exit
  }
  e.preventDefault();
  // ... rest of navigation logic
}
```

### 2. Focus After Clear Selection (lines 3350–3362)
**Current behavior**: "Clear" button removes selection but doesn't manage focus.
**New behavior**:
- After calling `clearSelection()` and `render()`, explicitly focus the first card in the board
- If no cards exist, focus the board container itself (`#board`)
- This prevents keyboard users from losing context when dismissing the bulk bar

**Code change**:
```javascript
clearBtn.addEventListener('click', () => {
  const bar = document.getElementById('bulk-action-bar');
  if (bar) {
    bar.classList.add('fading-out');
    bar.addEventListener('animationend', () => {
      clearSelection();
      render();
      // Return focus to first card or board after clear
      const firstCard = document.querySelector('.card');
      if (firstCard) {
        firstCard.focus();
      } else {
        document.getElementById('board')?.focus();
      }
    }, { once: true });
  } else {
    clearSelection();
    render();
    const firstCard = document.querySelector('.card');
    if (firstCard) {
      firstCard.focus();
    } else {
      document.getElementById('board')?.focus();
    }
  }
});
```

### 3. Arrow Key Navigation (lines 3447–3475)
**No changes needed** — arrow keys (←/→, Home/End) should remain trapped within the bar and wrap around. These are explicitly handled by roving tabindex rules.

## Verification Steps
1. Open `index.html` in browser
2. Select cards (Ctrl+click) to show bulk action bar
3. **Tab**: press Tab when focus is on last control (Delete button) — focus should escape to next page element (not wrap to "Clear")
4. **Shift+Tab**: press Shift+Tab when focus is on first control ("Clear") — focus should escape to previous page element (not wrap to Delete)
5. **Arrows**: press ← or → with focus on any control — focus should cycle within the bar
6. **Home/End**: focus should jump to first/last control in bar
7. **Clear button**: click "Clear" button — bulk bar fades and focus moves to the first card on the board
8. **Selection preservation**: Test that Alt+↑/↓ card reorder doesn't break bulk workflows (selection should survive reorder)

## Edge Cases Considered
- **Empty board after clear**: if all cards are archived, focus falls back to `#board`
- **Rapid Tab presses at boundary**: native browser Tab behavior takes over once we return from the handler
- **Animation timing**: focus is set after render completes, ensuring DOM is updated before focusing

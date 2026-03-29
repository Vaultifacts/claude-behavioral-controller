# Plan: Add Column Collapse/Expand Keyboard Shortcut (C Key)

## Context
The Kanban board already has column collapse/expand functionality with a visual button (▾), but there's no keyboard shortcut to toggle it. Users can collapse/expand columns by clicking the button in the column header, but keyboard-first users lack this binding. Adding the `C` key when focused on a column header's drag handle completes the keyboard interaction layer.

## Current State
- **Collapse state**: Already tracked in `uiState.collapsedCols` (Set of column IDs)
- **Visual toggle**: Collapse button (▾) with click handler that toggles state (app.js:797-806)
- **Keyboard handler**: Drag handle has existing keydown handler for Space/Enter/Escape/ArrowDown/ArrowLeft/ArrowRight (app.js:747-777)
- **Keyboard shortcuts overlay**: HTML table in index.html (lines 142-167) listing all bindings

## Implementation Plan

### 1. Add 'C' Key Handler to Drag Handle Keyboard Listener (app.js:747-777)
- Insert new condition after ArrowLeft/Right handler (after line 776)
- Check: `e.key.toLowerCase() === 'c' && !kbColDrag.active`
- Action: Prevent default, toggle `uiState.collapsedCols` for this column, call render() to update DOM
- Logic mirrors the button's click handler (app.js:799-806): add to set if not present, delete if present
- Announce the action via `ariaAnnounce()` for screen reader feedback

### 2. Update Keyboard Shortcuts Overlay (index.html:142-167)
- Add new row after the column header section:
  - Input: `<kbd>C</kbd> on column <kbd>⠿</kbd>`
  - Action: "Collapse / expand column"

### 3. Update Drag Handle Title/Aria-Label (app.js:736, 739)
- Current title: "Drag to reorder column (Space/Enter to grab, ← → to move, Esc to cancel)"
- Add `C` to the hint: "(Space/Enter to grab, ← → to move, C to collapse, Esc to cancel)"
- Aria-label already captures "Reorder column: {title}" — no change needed (collapse is secondary action)

## Files to Modify
1. **app.js** (lines 776-777, after ArrowLeft/Right handler)
   - Add C-key handler
   - Update dragHandle title (line 736)

2. **index.html** (lines 165-167, after column reorder section)
   - Add new keyboard shortcut row

## Testing
- Open app in browser
- Tab to a column drag handle (⠿)
- Press `C` to collapse — column should hide cards and add-card area, header stays visible
- Press `C` again to expand — cards should reappear
- Verify aria-announce message plays for screen readers
- Verify shortcuts overlay includes the new binding
- Test case-insensitivity: `c` and `C` both work
- Test that `C` doesn't work while column is grabbed (kbColDrag.active)

## Estimated Scope
- Add ~10 lines to app.js (keydown handler + toggle logic)
- Update 1 line for title hint
- Add 1 row to HTML shortcuts table
- **Risk**: Low — reuses existing collapse logic and follows established keyboard nav patterns

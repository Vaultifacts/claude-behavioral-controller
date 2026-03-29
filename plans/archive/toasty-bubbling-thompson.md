# Plan: Complete Keyboard Navigation for Kanban Board

## Context
The Kanban board has foundational keyboard navigation (arrow keys to move cards/columns, Space/Enter to grab), but lacks complete keyboard accessibility:
- **Focus indicators are subtle** — users can't easily see which card is focused during keyboard navigation
- **Card editing via keyboard is incomplete** — focused cards can't be opened for editing with a single keystroke
- **Tab navigation isn't optimized** — Tab should intelligently navigate through interactive elements (headers → cards → controls)

**Goal:** Make keyboard navigation first-class: strong focus indicators, Edit (Enter) from focused card, Tab-based element navigation, visual feedback for all keyboard states.

## Current State
From code exploration:
- ✅ Cards and columns have `tabIndex=0` (focusable)
- ✅ Keyboard grab/move/drop system exists (`kbDrag`, `kbColDrag` state)
- ✅ ARIA live announcements implemented
- ✅ Modal system for card editing (can add, edit, delete via modal)
- ✅ ? key opens keyboard shortcuts overlay
- ❌ **Focus indicators are weak** — `.card:focus` has browser default ring only
- ❌ **No Edit shortcut** — can grab card (Space), move it (arrows), but can't open modal to edit its properties
- ❌ **Tab navigation not optimized** — browser default Tab order; no smart sequencing

## Implementation Plan

### 1. **Improve Focus Indicators** (`style.css`)
Add strong visual feedback for keyboard focus:
- `.card:focus-visible` — 2px outline + background highlight (currently has subtle default)
- `.column-header:focus-visible` — outline + highlight for headers
- `.col-drag-handle:focus-visible` — prominent box-shadow + background change
- `.modal button:focus-visible`, `.modal input:focus-visible` — ensure modal controls are visible
- Add `outline-offset: 2px` to prevent outline from hiding content

**Why:** Users need to know which element is currently focused during keyboard navigation. Strong, colored focus indicators are WCAG AA requirement.

### 2. **Add "Edit Card" Keyboard Shortcut** (`app.js`)
When a card is focused, pressing **Enter** opens the card edit modal:
- Add handler to existing `document.keydown` listener for cards
- Detect if focused element is `.card` and key is `Enter`
- If card has focus and not already grabbed (`!kbDrag.active`), open modal in 'card-edit' mode
- Close modal with Escape (already works)

**Function location:** Add to the keyboard event handler section (~line 2195)
**Existing modal system:** `openModal('card-edit', colId, cardId)` already handles the UI

**Why:** Users can now keyboard-navigate to a card (arrow keys or Tab), press Enter to edit, modify title/description/dates/priority/labels, then Escape to close.

### 3. **Tab Navigation Ordering** (`index.html` + `app.js`)
Define logical Tab sequence:
- **First:** Search input (`#filter-search`)
- **Then:** Label filter pills (`.label-pill`) — make focusable (`tabIndex=0`)
- **Then:** Priority filter pills (`.priority-pill`) — make focusable (`tabIndex=0`)
- **Then:** Column headers in order (already `tabIndex=0`)
- **Then:** Cards within each column (already `tabIndex=0`, order determined by render)
- **Last:** Sidebar (if open), buttons (Add Column, etc.)

**Implementation:**
- In `buildCard()`: Ensure cards render with correct order (they do, via DOM order)
- In `buildColumn()`: Ensure column headers have `tabIndex=0` and are in order
- Update filter pills to have `tabIndex=0` (if not already)
- Verify no `tabIndex="-1"` breaks the sequence

**Why:** Predictable Tab order = users can navigate the entire board without mouse.

### 4. **Add Keyboard Hints to Focus State** (`style.css`)
Visual cues for what keyboard actions are available:
- When card is focused (not grabbed): show hint text "Press Enter to edit, Space to move" (via `::after` pseudo-element or tooltip)
- When column header is focused: show hint "Press Enter to reorder, or double-click to rename"
- Only show hints if keyboard is being used (check for mouse hover / touch)

**Why:** Discoverability — users see available actions without needing to know shortcuts.

### 5. **Ensure Modal Controls are Keyboard Accessible** (`app.js`)
Verify modal has proper keyboard handling:
- Tab through modal buttons (Save, Cancel, Delete)
- Escape closes modal (already works)
- Focus starts on first input when modal opens
- Focus returns to source card when modal closes

**Check existing code:** `openModal()` function (line 1126), modal event handlers
- Verify `#modal-input` and `#card-edit-textarea` receive focus on open
- Verify buttons have proper `tabIndex` or are `<button>` elements

### 6. **Update Keyboard Help Overlay** (`#kbd-overlay`)
Ensure the keyboard shortcuts display includes:
- Tab: Navigate elements
- Enter (on focused card): Edit card
- Arrow keys (on focused element): Move/reorder
- Space: Grab for drag
- Escape: Cancel/close
- ?: This help overlay

**Location:** The overlay already exists; just ensure text is comprehensive and updated.

---

## Critical Files to Modify
1. **`style.css`** — Add focus-visible styles, hint pseudo-elements
2. **`app.js`** — Add Enter handler for card edit, verify modal focus management, ensure label/priority filter pills are focusable
3. **`index.html`** — Ensure filter pills have `tabIndex=0`, verify semantic HTML for controls

---

## Testing Plan
1. **Focus Indicators:** Open board in browser, press Tab repeatedly → see strong focus outline on each element, clear which element is active
2. **Card Edit:** Tab to any card, press Enter → card edit modal opens; modify title; press Escape → modal closes, board shows updated card
3. **Tab Sequence:** Verify Tab cycles through: search → label filters → priority filters → column headers → cards (in order) → sidebar (if visible)
4. **Keyboard-only Navigation:** Complete workflow: Tab to card → Enter to edit → change priority/labels → Tab to + buttons → add new card via modal
5. **Screen Reader:** Test with NVDA or JAWS — ensure aria-live announcements fire for all keyboard actions

---

## Files & Functions to Preserve
- `kbDrag` state object (line 408) — card keyboard drag state
- `kbColDrag` state object (line 414) — column keyboard drag state
- `kbPickUp()`, `kbDrop()`, `kbCancel()` (lines 2195+) — existing card keyboard handlers
- `moveCard()`, `moveColumn()` (lines 257, 276) — core card/column movement
- `openModal()` (line 1126) — modal open function, reuse for edit
- `ariaAnnounce()` (line 1365) — accessibility announcements

---

## Verification
✅ All interactive elements (buttons, inputs, cards, headers) are focusable via Tab
✅ Focus indicators are visible (2px outline + color, WCAG AA compliant)
✅ Enter on focused card opens edit modal
✅ Escape closes modal and returns focus to card
✅ Arrow keys still move cards/columns as before
✅ Screen reader announces all state changes (existing aria-live)
✅ Keyboard shortcuts help is accurate and up-to-date

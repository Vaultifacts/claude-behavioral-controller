# Plan: Refine Long-Press Column Drag with Robust State Guards

## Context
The kanban board has a functional pointer/touch drag system with a 250ms long-press timer for column headers. The current implementation has a small gap: the timer can fire and activate drag even if the user moved beyond the 4px threshold early, then held still. Additionally, the `touchDrag.mode` guard exists but isn't actively enforced to prevent cross-type conflicts (column drag interfering with card drag).

## Refinements Required

### 1. **Enhance Timer Recheck Logic** (attachColumnTouchDrag, lines 1835–1849)
   - **Current**: Recheck only verifies pointer not released and no other drag active
   - **Issue**: If user moves > 4px then stops, timer can still fire and activate drag
   - **Fix**: Add movement threshold check in timer recheck:
     ```javascript
     if (Math.hypot(lp.curX - lp.startX, lp.curY - lp.startY) > 4) return;
     ```
   - **Why**: Ensures drag only activates if pointer is still within threshold at timer fire time
   - **Location**: Lines 1835–1849 in `attachColumnTouchDrag`

### 2. **Activate touchDrag.mode Guard**
   - **Current**: `mode` property exists in touchDrag state but is never checked
   - **Issue**: Column long-press could activate while card drag is in progress, or vice versa
   - **Fix**: In both `_startTouchDrag()` and the timer fire logic (line 1840), check:
     ```javascript
     if (touchDrag.mode && touchDrag.mode !== dragType) return;
     ```
   - **Why**: Prevents a column header long-press from interfering if user is dragging a card
   - **Location**: Before setting `lp.armed = true` (line 1838) in timer callback

### 3. **Add Wheel/Trackpad Scroll Cancellation**
   - **Current**: Board scroll event cancels timer, but not wheel events on trackpad
   - **Issue**: Slow trackpad scroll on hybrid devices might not trigger a scroll event until after timer fires
   - **Fix**: Add global wheel event listener in attachColumnTouchDrag to cancel timer:
     ```javascript
     document.addEventListener('wheel', () => { cancelLP(); }, { passive: true });
     ```
   - **Why**: Covers trackpad and wheel scroll, preventing accidental drag during scrolling
   - **Location**: Inside attachColumnTouchDrag, after board scroll handler (~line 1895)

### 4. **Ensure CSS Class Cleanup on Activation**
   - **Current**: `.col-longpress-ready` is removed when timer fires (line 1840)
   - **Verify**: The class removal happens before pointer capture and ghost creation
   - **Status**: Already correct; no change needed. Class is removed immediately when `lp.armed = true` is set

### 5. **Verify Movement Cancellation State Consistency**
   - **Current**: Movement > 4px cancels timer via `cancelLP()`
   - **Verify**: Ensure timer and movement cancellation don't race (both have access to same `lp` object)
   - **Status**: Already safe; `lp` is closure-local, no race conditions possible

## Files to Modify
- **`C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\app.js`**
  - Lines 1835–1849: Add movement threshold recheck in timer callback
  - Line 1838–1840: Add mode guard before setting `lp.armed = true`
  - Lines 1895–1899: Add wheel event listener to cancel timer

## Testing Strategy
1. **Timer recheck**: Hold header > 4px away, release, wait → verify drag does NOT activate (early cancel prevents timer)
2. **Timer recheck edge case**: Move slightly (< 4px), hold for 250ms → verify drag DOES activate (movement is within threshold)
3. **Mode guard**: Start dragging a card, then try to long-press a column header → verify column drag does not start (mode guard blocks it)
4. **Wheel cancel**: On trackpad, scroll slowly while holding column header → verify timer cancels and no drag starts
5. **CSS cleanup**: Observe that `.col-longpress-ready` class is removed before drag begins (use DevTools inspector)

## Verification
- Open index.html in browser
- Test each scenario above manually on touch device or Chrome DevTools touch emulation
- Check console for any errors during timer/movement/recheck logic
- Verify column header is visually responsive (class added/removed cleanly)

## Expected Outcome
Long-press column drag is now robust: timer only fires if pointer is still within 4px, mode guard prevents column/card conflicts, and wheel/trackpad scroll reliably cancels the timer. The UX is more reliable on mobile and hybrid input devices.

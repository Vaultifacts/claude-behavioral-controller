# DISCOVERY: Keyboard Column Reordering ALREADY IMPLEMENTED

## What I Found
Both the long-press timer AND keyboard column reordering are **fully implemented and working**:

### Already Complete:
1. **Long-press timer (250ms)** – Lines 1840–1957 in app.js (`attachColumnTouchDrag()`)
2. **Keyboard column reordering** – Lines 2114–2294 in app.js (`kbColPickUp/Drop/Cancel` + keydown handlers)
3. **Visual feedback for both** – Lines 1119–1128, 1148–1155 in style.css
4. **Column drag handle (⠿)** – Lines 726–758 in app.js (focusable, role=button, ARIA label, Space/Enter listener)

### Next Task
Since the requested features are done, recommend next high-impact improvements to ChatGPT.

**Candidates:**
- [ ] **Undo/Redo system** for card/column moves (user experience improvement)
- [ ] **Bulk operations** (multi-select cards, batch move/delete)
- [ ] **Search & filter cards** by title/label/priority/due date
- [ ] **Column WIP limits** with visual warnings (already has limit field, missing UI)
- [ ] **Card templates** (quick-create cards with preset fields)
- [ ] **Real-time collab** (multi-user sync via WebSocket)
- [ ] **Mobile optimizations** (responsive layout, touch card actions)

Ask ChatGPT which feature would be most valuable to build next.

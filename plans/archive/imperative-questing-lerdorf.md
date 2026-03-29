# Plan: Cycle Time / Flow Metrics

## Context
Kanban board needs card transition history to surface cycle time and per-column dwell time metrics. Cards currently have `createdAt` but no column-movement history. ChatGPT recommended storing `[{columnId, enteredAt, exitedAt}]` on each card, computing metrics at render time, and keeping `exitedAt: null` for cards still in a column.

## Files to Modify
- `app.js` — all changes here
- `index.html` — add metrics panel toggle button in stats bar

## Implementation Plan

### 1. State version bump → v9 + migration
- Bump `state.version` default to 9
- Migration in `migrateState()`: for each active card without `history`, infer current column from `col.cardIds` and initialize:
  ```js
  card.history = [{ columnId: currentColId, enteredAt: card.createdAt || new Date().toISOString(), exitedAt: null }]
  ```

### 2. Card creation
- In `addCard()`, initialize `history = [{ columnId: colId, enteredAt: new Date().toISOString(), exitedAt: null }]`

### 3. moveCard() — record transition
Before `commit()`:
```js
const now = new Date().toISOString();
// Find current column
const srcColId = Object.keys(state.columns).find(id => state.columns[id].cardIds.includes(cardId));
// Only record if actually changing column
if (srcColId !== destColId) {
  const card = state.cardsById[cardId];
  if (!card.history) card.history = [];
  // Close current open entry
  const open = card.history.findLast(e => e.exitedAt === null);
  if (open) open.exitedAt = now;
  // Open new entry
  card.history.push({ columnId: destColId, enteredAt: now, exitedAt: null });
}
```

### 4. Metrics computation (render-time, no persistence)
Add `calculateFlowMetrics()`:
- **Dwell time per column**: For closed entries (`exitedAt !== null`), compute `ms = exitedAt - enteredAt`. Average across all cards per column.
- **Current WIP age**: For open entry (`exitedAt === null`) on active cards, compute `age = Date.now() - enteredAt`. Find oldest card per non-done column.
- **Cycle time**: For completed cards (last history entry is the "done" column):
  - "First work column" = column at index 1 (second column, after backlog)
  - "Done column" = last column (`state.columnIds[state.columnIds.length - 1]`)
  - `cycleTime = enteredAt(done) - enteredAt(firstWorkCol)` for the same card
  - Average across last 10 completed cards

### 5. Stats bar display
Append to existing `renderStats()`:
- Show `Avg Cycle` stat (e.g., "2.4d") if ≥1 completed card
- Show `WIP Age` stat (oldest card age, e.g., "5d") if any active non-done cards
- Add a "Metrics" toggle button (`⊞ Metrics`) that shows/hides a detail panel

### 6. Metrics detail panel
A collapsible `<div id="metrics-panel">` below the stats bar:
- Table: Column Name | Avg Dwell | Cards Completed | Oldest Active
- Rendered by `renderMetricsPanel()`, called from `render()`
- Toggle state stored in `uiState.metricsOpen` (in-memory only, not persisted)

### 7. Helper: formatDuration(ms)
Returns human-readable string: `< 1h`, `Xh`, `X.Xd`, `X.Xw`

## Verification
1. Create cards in first column, drag to middle, drag to done column
2. Check localStorage — `card.history` should have 3 entries, last has `exitedAt: null`
3. Open metrics panel — avg cycle time and dwell should reflect actual moves
4. Reload page — history should persist, metrics panel should recalculate correctly
5. Test with cards that have no history (migration path)

# Cycle 5: Stats Dashboard + Bulk Operations

## Context
The app has full selection UI (per-card checkboxes, select-all, bulk delete) but only one bulk action (DELETE_MULTIPLE). This cycle adds a stats dashboard for visibility into counter metrics and two new bulk operations (BULK_ARCHIVE, BULK_SET_CATEGORY) with clean undo/redo support.

## Feature 1: Stats Utility + Dashboard

### New file: `src/lib/stats.ts`
- `getCounterStats(counters: Counter[]): CounterStats | null`
- Returns null for empty array (zero-state guard, no NaN)
- Computes: totalCount, sumOfValues, average, min, max, byCategory breakdown
- Normalizes empty/missing category → "Uncategorized"
- Sorts category breakdowns alphabetically

### New file: `src/components/StatsDashboard.tsx`
- Props: `{ counters: Counter[] }` (pass activeCounters)
- Collapsible section (starts collapsed), summary always visible
- `useMemo(() => getCounterStats(counters), [counters])`
- Summary line with `aria-live="polite"`: count, sum, avg
- Expanded view: all metrics + per-category breakdown (only when 2+ categories)

### New file: `src/styles/stats.css`
- Styling for `.stats-dashboard`, `.stats-toggle`, `.stats-details`, `.stats-row`, `.stats-categories`

### Modify: `src/App.tsx`
- Import StatsDashboard, render between sort/filter bar and counter grid

## Feature 2: Bulk Operations

### Modify: `src/lib/types.ts`
Add to CounterAction union:
- `{ type: 'BULK_ARCHIVE'; ids: string[] }`
- `{ type: 'BULK_SET_CATEGORY'; ids: string[]; category: string }`

### Modify: `src/lib/reducer.ts`
- `BULK_ARCHIVE`: empty-ids guard → return state; sets `archived: true` on all matched IDs
- `BULK_SET_CATEGORY`: empty-ids guard → return state; trims category, empty → undefined

### Modify: `src/hooks/useAnnouncingDispatch.ts`
- Add announcement cases for both new actions

### Modify: `src/hooks/useAppHandlers.ts`
- Add `handleBulkArchive()` and `handleBulkSetCategory(category)` handlers
- Both: guard on empty selection, dispatch, clear selection, show toast with undo hint

### Modify: `src/App.tsx`
- Add "Archive Selected (N)" button and category `<select>` dropdown next to "Delete Selected" in footer

### Modify: `src/styles/footer.css`
- Styles for `.btn-bulk-archive` and `.bulk-category-select`

## Feature 3: Tests

### New: `src/lib/__tests__/stats.test.ts`
- null for empty, correct metrics, zero-value, single counter, category normalization, multiple categories

### Modify: `src/lib/__tests__/reducer.test.ts`
- BULK_ARCHIVE: archives targeted, no-op on empty ids, ignores unknown ids
- BULK_SET_CATEGORY: sets category, trims, empty clears, no-op on empty ids
- History: bulk archive + undo restores, bulk set category + undo restores

### New: `src/components/__tests__/StatsDashboard.test.tsx`
- No render when empty, summary values, expand/collapse, category breakdown

### New: `e2e/bulk-operations.spec.ts`
- Select → bulk archive → verify archived → undo → verify restored → redo → verify archived again

## Implementation Order
1. `src/lib/stats.ts` + tests
2. `src/lib/types.ts` (add action types)
3. `src/lib/reducer.ts` + reducer tests
4. `src/hooks/useAnnouncingDispatch.ts`
5. `src/hooks/useAppHandlers.ts`
6. `src/components/StatsDashboard.tsx` + `src/styles/stats.css`
7. `src/App.tsx` (integrate dashboard + bulk buttons)
8. `src/styles/footer.css`
9. Component tests + E2E test

## Verification
- `npm test` — all unit tests pass including new stats, reducer, and component tests
- Manual: create counters with categories, verify stats dashboard shows correct metrics
- Manual: select counters → archive selected → undo → redo
- E2E: `npx playwright test e2e/bulk-operations.spec.ts`

# Cycle 2 Plan: Sorting, Bulk Duplicate, Debounced Announcements

## Context
Cycle 1 added notes, single duplicate, and Ctrl+N quick-add. This cycle implements the agreed plan: `updatedAt`-based sorting, bulk duplicate with upfront ID generation, and debounced announcements for DUPLICATE/SET_NOTES. DnD is already disabled when sorting is active (App.tsx:117).

## Feature 1: "Sort: Recently Updated" option

**Files to modify:**
- `src/hooks/useAppHandlers.ts` — add `'updated'` to `SortKey` union, add sort case in `displayCounters` useMemo
- `src/App.tsx` — add `<option value="updated">Sort: Recently updated</option>` to sort select

**Implementation:**
- Add `'updated'` to `SortKey` type (line 18)
- Add sort branch: `if (sortKey === 'updated') return b.updatedAt.localeCompare(a.updatedAt)` (most recent first, with `createdAt` tiebreaker)
- Add option element to sort `<select>` in App.tsx

**Reducer `updatedAt` audit — already consistent:**
- `touch()` helper (reducer.ts:13-15) stamps `updatedAt` on all mutations: INCREMENT, DECREMENT, RESET_ONE, RESET_ALL, SET_STEP, SET_COLOR, ARCHIVE, SET_CATEGORY, RENAME_COUNTER, SET_VALUE, BULK_ARCHIVE, BULK_SET_CATEGORY, SET_MAX_VALUE, RENAME_CATEGORY, DELETE_CATEGORY, SET_NOTES
- MOVE_COUNTER intentionally does NOT touch `updatedAt` (reorder ≠ mutation) — correct per plan
- ADD and DUPLICATE set `updatedAt` in the constructor — correct
- DELETE/DELETE_MULTIPLE remove counters — no `updatedAt` needed

## Feature 2: Bulk Duplicate with upfront ID generation

**Files to modify:**
- `src/lib/types.ts` — add `BULK_DUPLICATE` action type
- `src/lib/reducer.ts` — add `BULK_DUPLICATE` case
- `src/hooks/useAppHandlers.ts` — add `handleBulkDuplicate` handler
- `src/hooks/useAnnouncingDispatch.ts` — add announcement for `BULK_DUPLICATE`
- `src/components/BulkActionBar.tsx` — add Duplicate button
- `src/App.tsx` — wire `onBulkDuplicate` prop

**Implementation:**
- Action type: `{ type: 'BULK_DUPLICATE'; ids: string[]; newIds: string[] }` — IDs generated before dispatch
- Reducer: for each id in `ids`, find source counter, create clone with corresponding `newIds[i]`, insert after source. Process in reverse index order to maintain correct insertion positions.
- Handler in `useAppHandlers`: generate `newIds` via `createId()` before dispatching, clear selection after
- BulkActionBar: add "Duplicate" button between Archive and Set Category

## Feature 3: Debounced announcements for SET_NOTES and DUPLICATE

**Files to modify:**
- `src/hooks/useAnnouncingDispatch.ts` — add debounce logic for SET_NOTES and DUPLICATE

**Implementation:**
- Add a `useRef` timer for collapsing rapid SET_NOTES and DUPLICATE announcements (same 200ms pattern as category cycling in useAppHandlers.ts:216-224)
- For SET_NOTES: debounce with 300ms delay (typing produces many rapid dispatches)
- For DUPLICATE: debounce with 200ms delay (bulk duplicate fires multiple single dispatches — but actually with BULK_DUPLICATE it's a single dispatch, so this is mainly for rapid manual duplicates)
- Use `clearTimeout` before each `setTimeout` to collapse

## Tests

**File to modify:** `src/lib/__tests__/reducer.test.ts`

Add tests for:
- `BULK_DUPLICATE`: duplicates multiple counters, generates unique IDs, inserts after sources, no-op for empty ids, preserves fields on clones
- Reducer invariant: every mutating action updates `updatedAt` (as suggested by ChatGPT)

**File to modify:** `src/hooks/__tests__/useAnnouncingDispatch.test.ts`
- Add test for `BULK_DUPLICATE` announcement

## Verification
1. `npm test` — all tests pass
2. `npx tsc --noEmit` — no type errors
3. Manual: sort by "Recently updated", increment a counter, verify it moves to top
4. Manual: select multiple counters, click Duplicate, verify clones appear
5. Manual: rapid notes editing doesn't spam screen reader

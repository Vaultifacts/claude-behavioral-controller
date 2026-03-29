# Cycle 3 Plan: Hydration State Machine + Write Queue + createInitialState

## Context
CounterProvider currently hydrates synchronously via `useReducer` lazy init. This blocks async adapters (IndexedDB, REST backends). We need to model hydration as a state machine (`loading → ready → error`), queue writes until ready, and extract a `createInitialState` utility.

## Changes (3 features)

### 1. Extract `createInitialState()` utility
**File:** `src/lib/reducer.ts`
- Convert `initialState` constant into a `createInitialState()` function that returns `{ counters: [], categories: [], version: CURRENT_VERSION }`
- Keep `initialState` as a re-export (`export const initialState = createInitialState()`) for backward compat
- Update `InMemoryAdapter` to use `createInitialState()` instead of spreading `initialState`

### 2. Make `StorageAdapter.load()` async-capable + Hydration State Machine
**File:** `src/lib/storageAdapter.ts`
- Change interface: `load(): AppState | Promise<AppState>`
- Both existing adapters keep returning `AppState` synchronously (no breaking change)
- Add `AsyncInMemoryAdapter` for testing the async path (load returns a Promise)

**File:** `src/contexts/CounterContext.tsx`
- Add `HydrationStatus = 'loading' | 'ready' | 'error'` type
- Expose `hydrationStatus` in `CounterStateValue`
- Replace lazy `useReducer` init with empty-state init + `useEffect` that calls `Promise.resolve(adapter.load())`:
  - On mount: set status `loading`, init reducer with `createInitialState()`
  - On resolve: dispatch `REPLACE_COUNTERS` with loaded data, set status `ready`
  - On reject: set status `error`, keep `createInitialState()` as fallback
- Guard against StrictMode double-mount with a cleanup/cancel pattern (ignore stale results via `cancelled` flag)
- `hydratedRef` logic stays but is now set to `true` only after the `REPLACE_COUNTERS` from hydration fires

### 3. Write Queue (overwrite strategy)
**File:** `src/contexts/CounterContext.tsx`
- In the persistence `useEffect`, check `hydrationStatus !== 'ready'` → store latest snapshot in a `pendingWriteRef` instead of calling `debouncedSave`
- On transition to `ready`, flush `pendingWriteRef` once (latest snapshot wins)
- After `ready`, writes flow through `debouncedSave` as before

### 4. Tests
**File:** `src/lib/__tests__/storageAdapter.test.ts`
- Add `AsyncInMemoryAdapter` tests (load returns Promise, round-trip)

**File:** `src/hooks/__tests__/useCounters.test.ts`
- Add hydration status tests: starts `loading`, transitions to `ready`
- Add write-queue test: dispatches during `loading` don't trigger adapter.save(); after `ready` they do
- Add error-path test: adapter.load() rejects → status becomes `error`, state falls back to `createInitialState()`
- Add StrictMode double-mount safety test

**File:** `src/__tests__/test-utils.tsx`
- No changes needed (already passes adapter through)

## Key Files
- `src/lib/reducer.ts` — add `createInitialState()`
- `src/lib/storageAdapter.ts` — widen `load()` return type, add `AsyncInMemoryAdapter`
- `src/contexts/CounterContext.tsx` — hydration state machine + write queue
- `src/hooks/__tests__/useCounters.test.ts` — hydration tests
- `src/lib/__tests__/storageAdapter.test.ts` — async adapter tests

## Verification
1. `npm test` — all existing 1100+ tests pass
2. `npx tsc --noEmit` — no type errors
3. New tests cover: hydration lifecycle, write queue blocking, error fallback, StrictMode safety

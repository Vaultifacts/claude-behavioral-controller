# Plan: Add Hidden "Done" Archive Column

## Context
The Kanban board has grown feature-complete with drag-and-drop, local storage, statistics, card details, and quick-toggle due dates.

**Note on existing archive**: The board already has an archive system (separate panel below board, with individual "📦" archive buttons on cards).

**This plan proposes**: Converting the existing archive approach into a regular "Done" column that behaves like any other column—accepted via drag-drop, toggled visible/hidden in the filter bar, respecting WIP limits. This keeps the board cleaner (no separate archive panel) and makes archival a first-class column operation, consistent with the column-based mental model.

## Goal
- Implement a special "Done" column that is **hidden by default**
- Users can move any card to the Done column (same as regular columns)
- Add a **"Show Archive"** toggle button in the filter bar to reveal/hide the Done column
- Archive state persists to localStorage so the toggle state is remembered
- The Done column behaves like any other column: accepts drag-drop, respects WIP limits if set, shows card count in stats

## Data Model Changes

**State v8 migration** (in `migrateV7toV8()`):
- Add `archiveColumnId: string` — ID of the reserved "Done" column (e.g., `'__archive__'`)
- Add `archiveVisible: boolean` — toggle for showing/hiding Done column (default: `false`)
- The Done column is stored in `columns[archiveColumnId]` like any other, not separate
- Initialize archive column in `defaultState()` with title "Done" and `limit: null`

**Why this approach**:
- Reuses existing column infrastructure (no special-case rendering or drag-drop logic)
- The "Done" column is just another column, marked by its ID
- Toggle state (`archiveVisible`) is a simple boolean, persisted in state

## Implementation Steps

### 1. Update `defaultState()` (lines 34–54)
- Add `archiveColumnId: '__archive__'` and `archiveVisible: false`
- Initialize `state.columns['__archive__'] = { id: '__archive__', title: 'Done', cardIds: [], limit: null }`
- Add `'__archive__'` to the end of `columnIds` array

### 2. Create migration `migrateV7toV8()` (after `migrateV6toV7()`)
- Ensure old v7 state without archive gets initialized with the new fields
- Set `archiveColumnId: '__archive__'` and `archiveVisible: false` on old states
- Create the archive column in the columns map

### 3. Update `loadState()` (lines 106–154)
- Increment version check from `>= 7` to `>= 8`
- Call `migrateV7toV8()` if state.version < 8

### 4. Add toggle function (new function, around line 380)
```javascript
function toggleArchiveVisible() {
  state.archiveVisible = !state.archiveVisible;
  commit();
}
```

### 5. Update `render()` to conditionally show the archive column
- In the column rendering loop (lines 947–949), skip the archive column if `!state.archiveVisible && colId === state.archiveColumnId`
- This hides the Done column from the board view when `archiveVisible === false`

### 6. Add "Show Archive" toggle button to the filter bar
- File: `index.html`, find the filter section (search for `filter-bar`)
- Add a new button element: `<button id="toggle-archive" class="btn-small">📦 Show Archive</button>`
- Update the button text dynamically in `renderFilterPills()` to show "📦 Show Archive" or "📦 Hide Archive" based on `state.archiveVisible`

### 7. Attach click listener to the toggle button
- In the event listeners section (bottom of `app.js`), add:
  ```javascript
  document.getElementById('toggle-archive').addEventListener('click', toggleArchiveVisible);
  ```

### 8. Update stats calculation
- The `calculateStats()` function (around line 1751) should **exclude** the archive column from total card count or clearly label them separately
- Option: Show a separate "Archived: N" badge in the stats bar when `state.archiveVisible === true`

### 9. Update `renderFilterPills()` (around line 1900)
- Update the toggle button text to reflect current state:
  - If `state.archiveVisible`: "📦 Hide Archive"
  - If `!state.archiveVisible`: "📦 Show Archive"

## Critical Files
- **app.js** (main mutations, render, migration logic)
  - `defaultState()` — add archiveColumnId, archiveVisible, initialize Done column
  - `migrateV7toV8()` — new migration function
  - `loadState()` — update version check
  - `toggleArchiveVisible()` — new function
  - `render()` — conditionally render archive column
  - `renderFilterPills()` — update toggle button text
  - Event listeners section — attach click handler

- **index.html**
  - Filter bar — add toggle button

## Existing Patterns to Reuse
- State versioning pattern (lines 56–104) — follow `migrateVxtoVy()` naming convention
- Column rendering loop in `render()` (lines 947–949) — add conditional for archive visibility
- Filter bar rendering pattern from `renderFilterPills()` — add similar toggle button logic
- `commit()` pattern for state mutations (line 397–402)

## Testing / Verification
1. Open `index.html` in browser, verify board loads with 3 regular columns (To Do, In Progress, Done) + 1 hidden Done archive
2. Click "📦 Show Archive" button in filter bar — archive column should appear at the end
3. Drag a card to the Done column — card should move normally, stats updated
4. Click "📦 Hide Archive" — Done column disappears, cards remain in archive
5. Reload the page — toggle state should persist (page loads with archive shown/hidden as before)
6. Verify WIP limits still work on the Done column if one is set
7. Verify card count in stats includes/excludes archive cards as designed

## Edge Cases
- **First load**: Archive column is hidden and populated with sample archived cards (optional for demo)
- **Dragging from done back to active**: Works normally (just another column)
- **Stats with archive hidden**: Don't count Done cards if column is hidden (or show "Archived: N" separately)
- **Keyboard nav (if implemented)**: May need to skip archive column when cycling through columns if it's hidden

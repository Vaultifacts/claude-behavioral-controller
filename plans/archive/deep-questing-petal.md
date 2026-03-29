# Plan: Add Card Archive/Completed Column Feature

## Context
The Kanban board already has archive infrastructure (`archivedCardIds` array, `archiveCard()`, `restoreCard()` functions). Currently, archived cards are removed from view but can't be accessed. This feature adds a hidden "Archive" column that displays archived cards, toggles visibility, and allows restoration—keeping the active board clean while preserving completed work.

## Implementation Approach

### 1. UI State Enhancement
**File: `app.js` (uiState object)**
- Add `showArchive: boolean` flag to track archive column visibility
- Store in uiState (not persisted to localStorage by design—archive column starts hidden)

### 2. Archive Column Rendering
**File: `app.js` (render function)**
- After rendering regular columns (line 858-861), check `uiState.showArchive`
- If true and archived cards exist, build and append a special "Archive" column
- The archive column is built like a regular column but:
  - Uses a fake/virtual column ID: `'__archive__'`
  - Contains cards from `state.archivedCardIds` instead of regular column cardIds
  - Marked as read-only (no drag-in/drag-out, no delete of column)
  - Uses visual styling to distinguish it (grayed out background, different text)

### 3. Header Toggle Button
**File: `index.html` (header)**
- Add toggle button next to "Add Column" button: `<button id="toggle-archive-btn" class="btn btn-ghost">📦 Archive (N)</button>`
- Button text shows count of archived cards

**File: `app.js` (event handlers)**
- Click handler toggles `uiState.showArchive` and calls `render()`
- Update button text to show archive count

### 4. Card Actions in Archive Column
**File: `app.js` (buildCard function)**
- When rendering cards in archive column, add a "Restore" button instead of delete
- Clicking restore calls `restoreCard(cardId)` → saves → renders
- Archive cards can't be dragged or edited (read-only view)

### 5. Card Detail Sidebar Access
**File: `app.js` (renderSidebar)**
- When a card in archive is opened, show "Restore" button in the sidebar instead of archive/delete options
- Allow editing due date, priority, color, etc. for context

### 6. Styling
**File: `style.css`**
- Add `.column.archive-column` selector:
  - Background: lighter/desaturated (e.g., `background: rgba(128, 128, 128, 0.05)`)
  - Title text: grayed out/muted
  - Header styling: no drag handle, no WIP limit button
  - Cards: slightly desaturated, read-only appearance
- Ensure responsive collapse/expand works with archive

## Critical Files to Modify
1. **app.js**: uiState, render(), buildColumn() logic for archive, event handlers
2. **index.html**: add toggle button in header
3. **style.css**: archive column styling

## Key Existing Functions to Reuse
- `buildColumn()` (line 917) — can be reused/adapted for archive column
- `buildCard()` (line 1173) — can add conditional restore button
- `archiveCard()` (line 229) — already exists, no changes needed
- `restoreCard()` (line 240) — already exists, no changes needed
- `render()` (line 846) — add archive column rendering after regular columns

## Verification
1. Open index.html
2. Click toggle archive button — archive column should appear/hide
3. Archive a card (from card delete menu or sidebar) → card moves to archive column
4. Click restore on archived card → card returns to first column
5. Archive column count badge updates correctly
6. Archive column is collapsible and searchable like regular columns
7. Archived cards can't be dragged or moved between columns
8. Verify localStorage persistence: reload page, archive visibility persists to next session if toggled

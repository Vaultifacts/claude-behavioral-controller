# Kanban Board — Implementation Cycle 1

## Context
Empty directory. Building a complete Kanban board app from scratch:
- **Stack**: Vite + React 18 + TypeScript + Tailwind CSS v3 + @dnd-kit + Zustand + clsx + tailwind-merge
- **Data**: Local-first, localStorage persistence with schema versioning
- **Auth/Backend**: None

## Build Order
1. Scaffold Vite project + install deps + configure Tailwind
2. Types → Storage → Seed → Migrations → Store → Selectors
3. UI primitives (Button, Input, Modal)
4. Board components (Board, Column, Card, AddForms, CardDetailModal)
5. DnD layer (KanbanDndContext wrapping everything)
6. Wire App.tsx

## File Structure
```
src/
  lib/utils/cn.ts
  lib/storage/persistence.ts
  features/board/
    types/index.ts
    store/seedBoard.ts
    store/boardMigrations.ts
    store/boardStore.ts
    store/boardSelectors.ts
    components/Board.tsx
    components/BoardColumn.tsx
    components/BoardCard.tsx
    components/AddColumnForm.tsx
    components/AddCardForm.tsx
    components/CardDetailModal.tsx
    dnd/KanbanDndContext.tsx
    dnd/types.ts
  components/ui/Button.tsx
  components/ui/Input.tsx
  components/ui/Modal.tsx
  App.tsx
  main.tsx
```

## Entity Types
```typescript
Board { id, title, columnIds, createdAt, updatedAt }
Column { id, boardId, title, cardIds, createdAt, updatedAt }
Card { id, columnId, title, description?, createdAt, updatedAt }
PersistedBoardState { version: 1, boardId, boards, columns, cards }
```

## Store Actions
updateBoard, addColumn, updateColumn, deleteColumn, moveColumn,
addCard, updateCard, deleteCard, moveCard, resetBoard, exportBoard, importBoard, _restoreState

## DnD Rules
- Drag types: `card` | `column` (set on useSortable data)
- onDragStart: snapshot state + set activeId
- onDragOver: cross-column card moves (real-time visual feedback)
- onDragEnd: same-column card reorder + column reorder
- onDragCancel: restore snapshot
- Collision: closestCorners
- Pointer-only (v1)

## Deletion Rules
- deleteColumn: cascades to all child cards
- deleteCard: removes from column.cardIds
- No orphan entities enforced via store actions

## Persistence
- Key: `kanban-board-v1`
- Fallback: seed board on parse/hydration failure
- Persisted shape: PersistedBoardState (no UI state)
- Migration function: pure, version-gated

## UI
- Dark theme (slate-900 bg, slate-800 columns, slate-700 cards)
- Horizontal scrolling column layout
- Inline title editing for columns and board
- Card detail modal for title + description
- DragOverlay for ghost card/column during drag

## Verification
- `npm run dev` launches app with seeded board
- Drag cards between columns
- Add/edit/delete cards and columns
- Refresh page → board persists

# Plan: Kanban Board — React + TS + Vite + Tailwind + @dnd-kit + Zustand

## Context
Building a local-first Kanban board app from scratch in a new directory.
No backend, no auth, no database — localStorage is the persistence layer.
Advisor input (ChatGPT) confirmed the stack and recommended feature-first structure,
isolated DnD layer, versioned localStorage schema, and action-first Zustand stores.

---

## Stack
- **Vite** (React + TypeScript template)
- **Tailwind CSS v3** (PostCSS plugin)
- **@dnd-kit/core + @dnd-kit/sortable + @dnd-kit/utilities**
- **Zustand** (with persist middleware)
- **clsx** (class utility)
- **uuid** (id generation)

---

## Folder Structure

```
create-a-kanban-board/
├── public/
├── src/
│   ├── app/
│   │   └── providers/        # App-level React context wrappers (DndContext, etc.)
│   ├── features/
│   │   ├── board/
│   │   │   ├── components/   # Board, Column, Card components
│   │   │   ├── hooks/        # useBoard, useColumn, useCard
│   │   │   ├── store/        # boardStore.ts (Zustand)
│   │   │   └── types/        # Board, Column, Card interfaces
│   │   └── dnd/
│   │       ├── hooks/        # useDndSensors, useDragState
│   │       └── utils/        # collision strategy, drag helpers
│   ├── lib/
│   │   ├── storage/          # localStorage adapter + schema versioning
│   │   └── utils/            # cn(), generateId()
│   ├── components/
│   │   └── ui/               # Button, Input, Modal, Badge (reusable primitives)
│   ├── types/                # Shared global types
│   └── main.tsx
├── index.html
├── tailwind.config.ts
├── vite.config.ts
└── tsconfig.json
```

---

## Data Model

```ts
interface Card {
  id: string;
  title: string;
  description?: string;
  createdAt: number;
  updatedAt: number;
}

interface Column {
  id: string;
  title: string;
  cardIds: string[];     // ordered list — defines card sort order
}

interface Board {
  id: string;
  title: string;
  columnIds: string[];   // ordered list — defines column order
}

interface AppState {
  boards: Record<string, Board>;
  columns: Record<string, Column>;
  cards: Record<string, Card>;
  activeBoardId: string | null;
  schemaVersion: number;       // for migration support
}
```

Normalized shape: boards/columns/cards each keyed by id. Order tracked via `columnIds`/`cardIds` arrays.

---

## Zustand Store Design

**File**: `src/features/board/store/boardStore.ts`

```ts
// Actions (all pure, no async):
addBoard(title: string)
deleteBoard(id: string)
addColumn(boardId: string, title: string)
deleteColumn(boardId: string, columnId: string)
moveColumn(boardId: string, fromIndex: number, toIndex: number)
addCard(columnId: string, title: string)
deleteCard(columnId: string, cardId: string)
moveCard(sourceColId: string, destColId: string, cardId: string, toIndex: number)
updateCard(cardId: string, patch: Partial<Card>)
```

Persistence: `persist` middleware with `name: 'kanban-v1'` — wraps full state slice.
Schema version baked in as `schemaVersion: 1` — migration hook reads version on load.

---

## DnD Design

**Drag types**: `CARD` | `COLUMN`
**Collision**: `closestCorners` for cards within columns; `rectIntersection` for columns
**Sensors**: `useSensor(PointerSensor, { activationConstraint: { distance: 5 } })`
**Active drag state**: tracked in local React state (not Zustand) — only committed on `onDragEnd`
**Overlay**: `DragOverlay` renders a ghost copy of dragged item

No DnD state leaks into boardStore — store only receives final `moveCard`/`moveColumn` calls.

---

## Persistence Subsystem

**File**: `src/lib/storage/index.ts`
- Zustand `persist` middleware handles read/write automatically
- `storageVersion: 1` baked into persisted state
- `onRehydrateStorage` callback: if `schemaVersion` mismatch, run migration or reset to defaults
- Safe default: if localStorage is corrupt/empty, seed with one default board ("My Board") + 3 columns (To Do / In Progress / Done)

---

## UI Components to Build

### Primitives (`src/components/ui/`)
- `Button` — variant: primary/ghost/danger
- `Input` — controlled, with onEnter callback
- `Modal` — portal-based, for card detail view
- `Badge` — for card metadata

### Feature Components (`src/features/board/components/`)
- `BoardView` — renders active board (list of columns)
- `ColumnContainer` — droppable column + sortable cards
- `CardItem` — draggable card with title, click → modal
- `CardDetailModal` — title + description edit
- `AddColumnButton` — inline add column
- `AddCardButton` — inline add card per column
- `BoardSidebar` — board switcher (list of boards + add board)

---

## Build Order

1. **Scaffold**: `npm create vite@latest` → install deps → Tailwind setup
2. **Types + data model** (`src/features/board/types/`)
3. **Storage layer** (`src/lib/storage/`) + defaults seed
4. **Zustand store** (`src/features/board/store/boardStore.ts`)
5. **UI primitives** (`src/components/ui/`)
6. **Board/Column/Card components** (static, no DnD)
7. **DnD layer** — wrap with DndContext, add sensors, overlay, drag handlers
8. **CardDetailModal** — click card → edit title/description
9. **BoardSidebar** — multi-board support
10. **Polish** — keyboard accessibility, empty states, transitions

---

## Verification

- `npm run dev` — app loads, shows default board with 3 columns
- Add/edit/delete cards and columns — state persists on page reload
- Drag card between columns — order updates correctly
- Drag column — reorder works
- Open DevTools → Application → localStorage → `kanban-v1` key is populated
- Clear localStorage → app reseeds with default board (no crash)

---

## Files to Create (net-new, no existing code)

All files are new — this is a greenfield project in:
`C:\Users\Matt1\OneDrive\Desktop\create-a-kanban-board\`

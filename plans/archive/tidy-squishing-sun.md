# Plan: Card Labels/Tags + Color Picker

## Context
The Kanban board currently stores cards as `{ id, text }`. We're adding visual categorization via per-card color accents and reusable labels/tags, as advised by ChatGPT. These features require extending the data model, adding a card-edit modal mode, updating card rendering, and migrating localStorage from `kanban_v1` → `kanban_v2`.

## Files to Modify
- `app.js` — data model, mutations, modal logic, card rendering
- `index.html` — modal HTML (add color + label fields)
- `style.css` — card color indicator, label badges, color swatch grid

---

## Implementation Plan

### 1. Data Model Extension (`app.js`)

**Default state additions:**
```js
labelsById: {},   // { [id]: { id, name, color } }
```

**Card shape:** `{ id, text, color: null, labelIds: [] }`

**Storage migration:** On load, if data has key `kanban_v1`, migrate it:
- Copy to `kanban_v2` key
- Add `color: null, labelIds: []` to every existing card
- Add `labelsById: {}` if missing

### 2. New Mutations (`app.js`)

- `updateCard(cardId, { text, color, labelIds })` — partial update, calls `commit()`
- `addLabel(name, color)` — adds to `labelsById`, returns new ID
- `deleteLabel(labelId)` — removes from `labelsById` + strips from all cards
- `toggleCardLabel(cardId, labelId)` — add/remove label from card

### 3. Modal Extension (`app.js` + `index.html`)

Extend `modalContext` with `mode: 'card-edit'` and `cardId`.

**Card-edit modal content (injected into existing modal):**
- Text `<input>` (prefilled)
- Color section: 8 preset swatches (circle buttons) + native `<input type="color">` for custom
- Labels section: existing labels as pill-checkboxes + inline "New label" mini-form (name + color swatch)

`openCardEdit(cardId)` → sets `modalContext = { mode: 'card-edit', cardId }`, renders form into modal body, shows overlay.

`confirmModal()` reads all fields and calls `updateCard()`.

### 4. Card Rendering Update (`app.js` — `buildCard()`)

- If `card.color`: add `style="border-left: 4px solid <color>"` to card div
- If `card.labelIds.length`: append a `<div class="card-labels">` with `<span class="label-badge">` per label
- Add pencil edit button (hidden until hover, like delete button)

### 5. CSS Additions (`style.css`)

```css
/* Color swatch grid */
.color-swatches { display: flex; gap: 6px; flex-wrap: wrap; margin: 8px 0; }
.swatch { width: 22px; height: 22px; border-radius: 50%; cursor: pointer; border: 2px solid transparent; }
.swatch.selected { border-color: var(--text); }

/* Label badges on cards */
.card-labels { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 6px; }
.label-badge { font-size: 0.7rem; padding: 1px 7px; border-radius: 20px; color: #fff; }

/* Card edit button */
.card-edit { /* same pattern as .card-delete */ }

/* Card color accent */
.card[style*="border-left"] { padding-left: 10px; }
```

### 6. Preset Colors
8 swatches: red `#e05c5c`, orange `#e08c5c`, yellow `#d4b84a`, green `#4caf7d`, teal `#4aa8c0`, blue `#5c6ef8`, purple `#9c6ef8`, pink `#e05ca8`

### 7. LocalStorage Migration

```js
function loadState() {
  // Try kanban_v2 first
  let raw = localStorage.getItem('kanban_v2');
  if (!raw) {
    // Migrate from kanban_v1
    raw = localStorage.getItem('kanban_v1');
    if (raw) {
      const old = JSON.parse(raw);
      Object.values(old.cardsById || {}).forEach(c => {
        c.color = c.color ?? null;
        c.labelIds = c.labelIds ?? [];
      });
      old.labelsById = old.labelsById ?? {};
      localStorage.setItem('kanban_v2', JSON.stringify(old));
    }
  }
  return raw ? JSON.parse(raw) : defaultState();
}
```

---

## Verification
1. Open `index.html` in browser — existing board renders normally
2. Hover a card — pencil edit button appears
3. Click pencil — card-edit modal opens with text, color swatches, labels section
4. Pick a color swatch → card gets left border accent
5. Use native color picker → custom color applied
6. Add a new label (name + color) → appears as badge on card
7. Reload page → all colors and labels persisted via `kanban_v2` localStorage key
8. Cards with `kanban_v1` data auto-migrate on first load with no data loss

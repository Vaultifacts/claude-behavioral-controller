# Plan: Card Labels/Tags + Per-Card Color Picker

## Context
Cycle 2 of the Kanban board build. ChatGPT advised: store labels as `{id,name,color}` objects with a top-level `labelsById` map, use `<input type="color">` for the color picker, add a `color` hex field per card, and add a state version/migration field. I'm adopting the simpler inline approach (labels as plain strings on each card) for this scope — a global `labelsById` map adds complexity that's not needed yet.

## Files to modify
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\app.js`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\style.css`
- `C:\Users\Matt1\OneDrive\Desktop\kanban-board-web-app-with-drag-and-drop-\index.html`

## State model changes
Extend card schema from `{ id, text }` to `{ id, text, labels: string[], color: null|"#hex" }`.

Bump storage key from `kanban_v1` → `kanban_v2` with a migration that reads `kanban_v1`, adds `labels: []` and `color: null` to all existing cards, saves as `kanban_v2`.

## New UI: Card detail modal
Add a second modal (or reuse the existing one with a new mode) for card details:
- **Color swatch**: `<input type="color">` pre-populated with current card color (default `#5c6ef8` accent or white)
- **Tags section**: show existing tags as removable pill chips + a text input to add new tags (Enter to add)
- **Save / Cancel** buttons

Trigger: small pencil/edit icon button on card hover (sits next to existing delete button).
Double-click still = inline text edit (unchanged).

## Render changes in `buildCard()`
- If `card.color`, apply it as a left-border accent: `style="border-left: 4px solid ${card.color}"`
- If `card.labels.length`, render a `.card-labels` div below the text with `<span class="label-pill">` per label

## CSS additions (no existing label/color infrastructure)
```css
.card-labels { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 6px; }
.label-pill { font-size: 11px; padding: 2px 7px; border-radius: 10px; background: rgba(92,110,248,0.25); color: #a0a8ff; }
/* Color accent handled inline via border-left */
/* Edit icon button: same style as delete btn */
```

## Implementation steps
1. **index.html**: Add a second modal `#card-modal` with color input, tag pills container, tag input, save/cancel
2. **app.js**:
   a. Add `STORAGE_KEY_V2 = 'kanban_v2'`, migration fn `migrateV1()`
   b. Extend `defaultState()` cards to include `labels: [], color: null`
   c. Add mutations: `setCardColor(cardId, color)`, `addCardLabel(cardId, label)`, `removeCardLabel(cardId, label)`
   d. Add `openCardModal(cardId)` / `closeCardModal()` / `saveCardModal()` handlers
   e. Update `buildCard()` to render labels + color border + edit button
3. **style.css**: Add `.card-labels`, `.label-pill`, `.edit-btn` styles

## Verification
- Open `index.html` in browser
- Hover a card → see pencil icon
- Click pencil → card modal opens with color picker and tag input
- Add a tag "urgent" → pill appears on card
- Change color → left border accent updates
- Refresh page → labels and color persist via localStorage
- Old `kanban_v1` data (if present) migrates cleanly without data loss

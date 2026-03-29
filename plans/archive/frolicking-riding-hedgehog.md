# Plan: Add Due-Date Quick Toggle Button to Cards

## Context
The user wants to add a quick-toggle button visible on cards with due dates, allowing one-click updates to mark cards as overdue or done without opening the edit modal or sidebar. This speeds up day-to-day workflow.

## Current State
- Due dates are stored as ISO strings (YYYY-MM-DD) in `card.dueDate`
- `getDueState(card)` returns 'overdue' | 'due-soon' | 'normal' | null
- Cards display a due-date badge showing the date and status icon (📅, ⏰, ⚠)
- Edit button appears on cards in `.card-btn-row` on hover
- Sidebar shows move-to-column dropdown and notes section

## Implementation Approach

### Option A: Toggle Button with Cycling States
Add a quick-toggle button to `.card-btn-row` that cycles through states:
- Normal/due-soon → **Mark Overdue** (set dueDate to yesterday)
- Overdue → **Mark Done** (set dueDate to today or clear it)
- Repeat

### Option B: Popover Menu
Add a button with a small popover showing quick actions:
- "Mark Overdue" (yesterday)
- "Mark Done Today" (today)
- "Clear Due Date"

## Need Clarification
Before implementing, please clarify the exact behavior you want:

1. **What should "Mark Overdue" do?**
   - Set dueDate to yesterday?
   - Set to a past date?

2. **What should "Mark Done Today" do?**
   - Set dueDate to today?
   - Clear the due date entirely?
   - Move the card to a "Done" column?

3. **Button behavior?**
   - Single toggle cycling through states?
   - Popover menu with multiple options?
   - Smart button showing the next action (e.g., if overdue, show "Mark Done")?

4. **Visual placement?**
   - Next to the edit button in card-btn-row?
   - On the due-date badge itself?

Once confirmed, I'll implement:
- Add a new button/icon to card rendering
- Add event listener to update dueDate via updateCard()
- Add CSS styling for the button
- Update keyboard shortcuts table if needed

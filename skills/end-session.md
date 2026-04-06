---
name: end-session
description: Use when ending a session without running /compact — saves state and writes a resume pointer for next session.
---

Save session state before closing. Work through steps in order.

## Steps 1–6 — Save state

Follow steps 1–6 from the `pre-compact` skill exactly:
1. Active task state → memory
2. Pending items → memory
3. Session learnings (the *why*) → memory
4. User feedback/corrections → feedback memory
5. Plan file path → memory
6. Update MEMORY.md index

## Step 7 — Write resume pointer

Write or update a memory file with a single sentence:
> "Resume from: [the one most important next action for next session]"

This is the first thing the `new-session` skill will surface. Keep it to one action — not a list.

## Step 8 — Confirm and close

State a brief summary of what was saved, e.g.:
> "Session saved. Saved: [active task], [1 learning], [1 feedback item]. Resume from: [X]."

Do NOT ask the user questions about committing, pushing, or next steps. State what was saved and stop.

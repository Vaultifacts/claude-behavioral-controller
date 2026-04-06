---
name: pre-compact
description: Use when about to run /compact, or when context usage is high and compaction is imminent.
---

Save session state before compacting. Work through each step below in order. Do not run /compact until all applicable steps are complete.

## Step 1 — Active task state

Is there an active task in this session (something in-progress, mid-implementation, or mid-debug)?

- If yes: write or update a memory file capturing the current step and the immediate next action needed.
- If no: skip.

## Step 2 — Pending items

Are there any items explicitly deferred, flagged, or noted as "do next"?

- If yes: write or update a memory file listing them.
- If no: skip.

## Step 3 — Session learnings

Were any of the following discovered or decided this session?
- Non-obvious decisions or tradeoffs in code changed (the *why*, not the *what* — git has the what)
- Errors or bugs with root cause identified
- Approaches tried and rejected
- Non-obvious facts about the codebase or system

- If yes: write or update a memory file. Be specific — vague summaries decay fast.
- If no: skip.

## Step 4 — User feedback

Did the user correct my approach, validate an unusual choice, or give explicit guidance this session?

- If yes: write or update a feedback memory file. Format: rule first, then **Why:** (reason given), then **How to apply:** (when it kicks in).
- If no: skip.

## Step 5 — Plan file

Is there an active plan file in use this session?

- If yes: ensure its path is recorded in memory (existing file or new entry).
- If no: skip.

## Step 6 — Update MEMORY.md

Review `~/.claude/projects/C--Users-Matt1/memory/MEMORY.md`:
- Add pointers for any new memory files written above
- Update descriptions for any existing entries that changed this session
- Flag (but do not delete) any entries that appear stale — deletion requires user confirmation
- Count the lines — if approaching 200, alert the user: entries past line 200 are silently truncated

## Step 7 — Confirm

State a brief summary of what was saved, e.g.:
> "Pre-compact save complete. Saved: [active task step], [2 learnings], [1 feedback item]. Ready to /compact."

If nothing needed saving, state: "Pre-compact check complete — nothing to save. Ready to /compact."

---

**Memory file location**: `~/.claude/projects/C--Users-Matt1/memory/`
**Format**: Use frontmatter with `name`, `description`, `type` (user/feedback/project/reference), then content body.

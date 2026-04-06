---
name: new-session
description: Use when a new session has just started, before responding to the user's first message.
---

Orient for this session before doing anything else. Work through steps in order.

## Step 1 — Check QG failures

Read `~/.claude/last-session-qg-failures.txt`.

If it exists: surface the failures to the user before continuing.
If it doesn't exist: skip.

## Step 2 — Read MEMORY.md

Read `~/.claude/projects/C--Users-Matt1/memory/MEMORY.md`.

If it doesn't exist: skip to Step 4.

Identify any active task, pending items, or plan file recorded.

## Step 3 — Read active context files

If MEMORY.md points to any of the following: read them.
- Active task file
- Pending items file
- Resume pointer file (written by `end-session` — look for entries containing "Resume from:")

If no entry exists, or the file doesn't exist: skip.

## Step 4 — State session context

State what you know before responding to the user's first message, e.g.:
> "Session ready. Active task: [X]. Next action: [Y]. Pending: [Z]."

If nothing was found:
> "Session ready. No prior context found — ready for your first task."

Do NOT ask the user "what are you working on?" — state what you found and proceed. The user will redirect if needed.

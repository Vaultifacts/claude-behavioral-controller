---
name: post-compact
description: Use when /compact has just completed.
---

Restore session context after compaction. Work through steps in order before continuing any work.

## Step 1 — Read MEMORY.md

Read `~/.claude/projects/C--Users-Matt1/memory/MEMORY.md`.

If it doesn't exist: skip to Step 6 and report no state was saved.

Identify pointers to:
- Active task state file
- Pending items file
- Session learnings or feedback files
- Plan file path

## Step 2 — Read active task file

If MEMORY.md points to an active task memory file: read it.
If no entry exists, or the file doesn't exist: skip.

## Step 3 — Read pending items file

If MEMORY.md points to a pending items memory file: read it.
If no entry exists, or the file doesn't exist: skip.

## Step 4 — Read session learnings and feedback files

If MEMORY.md points to any session learnings or feedback memory files: read them.
If no entries exist: skip.
If a referenced file doesn't exist: skip it and continue.

## Step 5 — Read plan file

If a plan file path is recorded in memory: read that file.
If no path is recorded, or the file doesn't exist: skip.
Do NOT guess or invent a path — only read it if explicitly recorded in memory.

## Step 6 — State resumed context

State what you understand before proceeding, e.g.:
> "Context restored. Active task: [X]. Next action: [Y]. Pending: [Z]."

If nothing was saved pre-compact:
> "Context restored. No session state was saved before compaction — please redirect me."

Do NOT ask the user a question. State what you know and proceed. The user will redirect if anything is wrong.

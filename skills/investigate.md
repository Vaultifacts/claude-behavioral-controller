---
name: investigate
description: Use when asked to fix a bug, before touching any code — read, trace, and identify root cause first.
---

Investigate before implementing. Do NOT write or modify code until Step 5 is complete.

## Step 1 — Locate the relevant code

Use Grep and Glob to find the affected code. Do NOT guess paths.

- Search for the route, function name, or symptom keyword
- Read the handler/function in full once found

If nothing is found: stop and tell the user exactly what you searched for and ask them to point you to the right file. Do NOT proceed to Step 2.

## Step 2 — Trace the execution path

From the entry point, follow the code to where the bug likely occurs:

- Trace through function calls to the data layer
- Read each function that touches the affected logic
- Stop when you reach the probable failure point

## Step 3 — Identify the failure point

Look for common root causes:
- Missing guard for edge case input (null, empty, missing param)
- Logic that behaves differently when a condition is absent vs. present
- Query or data fetch that produces wrong results under specific conditions
- Duplicate execution or incorrect branching

## Step 4 — Confirm with a second read

Re-read the specific lines around the failure point. Verify the hypothesis holds.
Quote the exact lines as evidence.

## Step 5 — State root cause

State the finding before doing anything else:
> "Root cause: [what is wrong] at [file:line]. Evidence: [quoted code]. Recommended fix: [approach, not implementation]."

Do NOT ask permission to start. Do NOT implement yet. Hand off to `fix-issue` or proceed directly only after this statement is made.

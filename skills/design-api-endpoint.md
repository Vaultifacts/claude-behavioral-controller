---
name: design-api-endpoint
description: Use when asked to add, modify, or implement an API endpoint — before writing any handler code.
---

Design the contract before implementing. Do NOT write handler code until Step 4 is complete.

## Step 1 — Check existing conventions

Read one or two existing route handlers in the codebase:
- Response envelope shape (e.g., `{ success, data }` vs `{ result }` vs bare object)
- Validation library in use (Zod, Joi, express-validator, etc.)
- Error response format for 400/404/500
- How auth middleware is applied

If no existing routes exist: define conventions now, before Step 2.

## Step 2 — Define the contract

State all of these before writing any code:

- **Route:** `METHOD /path`
- **Auth:** required / optional / none — and which middleware
- **Request body:** each field, its type, and whether it's required
- **Success response:** HTTP status + response shape
- **Error cases:**
  - 400: validation — which fields, what format
  - 401/403: auth — when triggered
  - 404: not found — which resource
  - Business logic errors (conflict, out of stock, etc.) — enumerate them

If field names, types, or business rules are unknown: ask the user before proceeding. Do NOT invent a plausible shape and proceed.

## Step 3 — Verify against existing patterns

Confirm the contract from Step 2 matches the conventions from Step 1:
- Response envelope consistent
- Error format consistent
- Auth pattern consistent

If anything conflicts: state the discrepancy and ask the user which pattern to follow.

## Step 4 — State the contract

Before writing any code, output the complete contract:
> "Contract for `[METHOD /path]`: body — [fields]. Success: [shape]. Errors: [cases]. Auth: [requirement]. Matches existing conventions: [yes / no — detail]."

Then write the handler.

## Time pressure does not skip this

"Quick", "just add it", "demo in 20 minutes", "nothing fancy" — these mean execute Steps 1–3 faster, not skip them. An endpoint with the wrong response shape or missing auth breaks a demo worse than a 2-minute contract step.

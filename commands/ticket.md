# /ticket — Create a Development Ticket
# Converts a description or current task into a structured ticket.
# Usage: /ticket [description]

Convert $ARGUMENTS into a well-structured development ticket.

Output the following sections:

## Title
One concise line (imperative verb, under 60 chars)

## Context
Why this work is needed. What problem it solves.

## Acceptance Criteria
- [ ] Specific, testable conditions (use checkboxes)
- [ ] Each criterion is independently verifiable

## Technical Notes
- Relevant files, functions, or systems to touch
- Known constraints or dependencies
- Suggested implementation approach (if obvious)

## Out of Scope
Explicitly list what this ticket does NOT cover.

## Labels
Suggest: `bug` | `feature` | `chore` | `docs` | `perf` | `security`

Keep it concise. Avoid padding. Use the information provided — do not invent requirements.

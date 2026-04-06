---
name: delete-code
description: Use when deleting, removing, or commenting out code, functions, modules, files, exported symbols, or database columns — before making any deletion.
---

Audit all references before deleting anything. Do NOT delete until Step 3 (reference audit) is complete.

## Step 1 — Identify exactly what is being deleted

Record all of the following before proceeding. Read the actual file — no inference.

- **Function/method**: exact name, file path, line number
- **Module/file**: full path
- **Exported symbol**: name + every file that re-exports it
- **Database column**: table name, column name, current data type, nullability
- **Config/env key**: key name, every config file and `.env.example` it appears in

## Step 2 — Classify the deletion type

| Type | Risk | Examples |
|------|------|---------|
| Internal function | Low | Private function used only within one file |
| Exported symbol | Medium | Function imported by other project files |
| Public API / library export | High | Function used by external consumers |
| Serialized identifier | Maximum | DB column name, JSON key, env var name, log field |

Serialized identifiers require a migration plan, not a delete — see Step 4.

State the classification before Step 3:

> "Type: internal function — Low risk. Not exported, no cross-file references expected."

## Step 3 — Audit all references (three passes)

**Pass 1 — Static references:**

```bash
grep -r "functionName\|ClassName\|columnName" --include="*.ts" --include="*.js" --include="*.py" --include="*.go" --include="*.rb" . 2>/dev/null | grep -v ".git/"
```

Every hit must be resolved before deleting. "Resolved" means the caller is being deleted in the same atomic commit, or updated to not use the target.

**Pass 2 — Dynamic references:**

```bash
grep -r '"functionName"\|'"'functionName'" . 2>/dev/null | grep -v ".git/"
```

Check for: `require('moduleName')`, `getattr(obj, 'methodName')`, eval(), plugin systems, template strings, `Object.keys()` enumeration, factory functions that construct names from strings.

**Pass 3 — External references (Medium risk and above):**

- Database columns: grep migration files, ORM model definitions, raw query strings
- Env vars: grep config files, `docker-compose.yml`, `.env.example`, CI config, documentation
- JSON keys: grep serializers, API response formatters, test fixtures, seed data
- Exported symbols: check barrel files (`index.ts`, `__init__.py`)

If ANY reference is found that will not be deleted atomically with the target: **STOP.** Remove or update the caller first, then delete the target in a follow-up commit.

## Step 4 — Handle serialized identifiers

A database column, env var, or external API key cannot be deleted in a single commit.

**Database column** — use the `database-migration` skill. Always expand/contract:
1. Remove all app code reads/writes of the column; deploy
2. Drop the column in a separate migration after confirming no reads or writes remain

**Environment variable** — three steps:
1. Remove all code references; deploy the updated app
2. Remove from the secrets manager / hosting platform config
3. Remove from `.env.example` and documentation

**API response key** — deprecate first:
1. Keep returning the key but stop consuming it; add a deprecation notice
2. Confirm all consumers have updated
3. Remove the key from the response

Never delete a serialized identifier without completing the full sequence. Single-commit deletion is always wrong.

## Step 5 — Delete and run tests

Delete only after Step 3 is complete and all callers are resolved.

Do not batch multiple deletions in the same commit. One deletion per commit — a failing test after five deletions is an archaeology problem; after one it is a two-minute fix.

Run the full test suite immediately after:

```bash
npm test
# or pytest / cargo test / go test ./...
```

A failing test means a reference was missed. Revert, find it via Step 3, resolve, retry.

## Step 6 — Verify no dynamic references remain

After tests pass:

- Re-run the Pass 2 grep from Step 3
- Check git history: `git log --all -S "identifier" --oneline`
- Search README, API docs, changelogs, and inline comments
- Check test fixtures and seed data
- Check CI config, `Dockerfile`, `docker-compose.yml`

If any surface a remaining reference, update it before closing the task.

After Step 6, output this block:

```
## Deletion Summary
- Deleted: [name] ([type]) at [file:line]
- Static refs found: [N] — all resolved
- Dynamic refs found: [N] — all resolved
- Tests: [N passed]
- Serialized identifier: [yes — migration required / no]
```

## Pressure cases

- `"It's obviously dead code"` — Grep it. "Obvious" misses dynamic references. Step 3 is not optional.
- `"The linter says it's unused"` — Linters do not grep string-based dynamic calls, configs, or test fixtures.
- `"Clean up a few other things while you're at it"` — One deletion at a time. Batch deletions make it impossible to attribute a failing test.
- `"I'll comment it out temporarily"` — Commented-out code never gets permanently deleted. Delete it properly or leave it.
- `"It's a private function"` — Private visibility does not prevent string-based reflection or plugin lookup by name.

## Rationalizations

| Phrase | Why it fails |
|--------|-------------|
| "The IDE says no usages" | IDEs miss string-based dynamic references, external configs, and test fixtures. Run Step 3. |
| "I know nothing calls this" | Grep it. You will find callers. |
| "It's a private method" | Private visibility does not prevent string-based reflection or config references. |
| "Deleting a DB column is easy" | DB column deletion is always multi-step expand/contract. Never a simple drop. |
| "Tests will catch it" | Only if the callers have tests. Step 3 finds what tests do not cover. |
| "I'll batch delete unused code" | One deletion at a time. A failing test after five deletions is a debugging session. |

---
name: database-migration
description: Use when writing, planning, or reviewing a database schema migration — adding columns, dropping columns, renaming columns, changing types, adding NOT NULL constraints, or any other ALTER TABLE / DROP TABLE operation.
---

Do NOT write any migration file until Step 3 (reference audit) is complete. Never drop or rename a column in a single migration deploy — always use expand/contract.

## Step 1 — Classify the migration

Two classes:

- **Additive/Safe**: add a nullable column, add a column with a default value, create a new table, add an index. These are safe to deploy before the application code that uses them.
- **Expand/Contract Required**: drop a column, rename a column, change a column's type, tighten a constraint (nullable → NOT NULL), change a column's default to a breaking value, drop a table. These ALWAYS require the multi-phase expand/contract pattern and CANNOT be done in a single migration.

State the class explicitly: "Classification: [Additive/Safe | Expand/Contract Required] — [one-sentence reason]."

## Step 2 — State the exact before/after

Write:

```
Table: [table name]
Column: [column name]
Before: [current type, nullable/not null, default value, indexed: yes/no]
After:  [target state, or "DROPPED"]
Data impact: [none / rows will be updated / rows will be NULL / data will be permanently lost]
```

If data will be permanently lost, state: "Data loss: irreversible. Confirm a backup exists before proceeding." Do not proceed if the user cannot confirm backup availability for a destructive migration on a table with production data.

## Step 3 — Reference audit (GATE)

Before writing any migration, search for all code, config, and test references to the column or table being changed.

```bash
# For a column name
grep -r "column_name\|\"column_name\"" --include="*.ts" --include="*.js" --include="*.py" --include="*.rb" --include="*.go" --include="*.sql" . 2>/dev/null | grep -v ".git/" | grep -v "node_modules/"

# Also check migration history files
grep -r "column_name" --include="*.js" --include="*.ts" --include="*.rb" db/ migrations/ knex/ . 2>/dev/null | grep -v ".git/"

# Check seeds and fixtures
grep -r "column_name" --include="*.json" --include="*.yml" --include="*.yaml" --include="*.sql" . 2>/dev/null | grep -v ".git/"
```

Record every hit. If any hit represents active code that reads or writes the column:
- For **Additive/Safe**: this is informational. The new column does not break existing code.
- For **Expand/Contract Required**: the app code referencing the column MUST be removed or updated before the destructive migration phase runs. Do not write the drop migration until the code references are resolved.

State: "References found: [N — list files:lines or 'none found']"

## Step 4 — Determine deploy order

State the correct deploy order explicitly for this migration type:

| Migration type | Deploy order |
|----------------|-------------|
| Add nullable column | Migration first, then code deploy |
| Add column with default | Migration first, then code deploy |
| Drop column | Code deploy first (remove all reads/writes), then migration |
| Rename column | Expand/contract multi-phase (see Step 5) |
| Change column type | Expand/contract multi-phase (see Step 5) |
| Add NOT NULL constraint | Backfill first, then migration (see Step 5) |
| Drop table | Code deploy first (remove all references), then migration |

State: "Deploy order: [migration first / code first / multi-phase — see Step 5]"

## Step 5 — Expand/Contract Plan (required for Expand/Contract class)

Never skip this for drop/rename/type-change/NOT NULL operations.

**Drop a column:**
Phase 1 (code deploy): Remove all application code that reads or writes the column. Deploy. Verify in production that no queries touch the column for at least one full traffic cycle (monitor query logs if possible).
Phase 2 (migration): Drop the column in a separate migration. This migration runs after Phase 1 has been deployed and verified.

**Rename a column:**
Phase 1 (migration): Add the new column name alongside the old one. Write a backfill: `UPDATE table SET new_col = old_col WHERE new_col IS NULL`.
Phase 2 (code deploy): Update all application code to read/write the new column name. Keep writing to old column if possible during transition.
Phase 3 (migration): Drop the old column after Phase 2 has been deployed and verified.

**Change column type:**
Phase 1 (migration): Add a new column with the target type alongside the old one. Backfill values with type conversion.
Phase 2 (code deploy): Update all application code to use the new column.
Phase 3 (migration): Drop the old column.

**Add NOT NULL constraint to existing column:**
Phase 1 (migration): Backfill all NULLs: `UPDATE table SET column = <default> WHERE column IS NULL`. Add a NOT NULL constraint with a default value in the same transaction.
Note: For large tables (>100K rows), the backfill should be batched. State the estimated row count before proceeding.

For each phase, state: "Phase N migration: [exact SQL or ORM call] — deploy after: [Phase N-1 verified / immediately]"

## Step 6 — Write the migration

Write the actual migration file with both `up` and `down` functions. Requirements:
- `down` must reverse `up` exactly. If `down` cannot reverse `up` (e.g., dropped data is unrecoverable), state: "down: schema-reversible only — data lost in up cannot be recovered."
- For multi-phase migrations: write only the current phase's migration. Label the file: `YYYYMMDDHHMMSS_phase1_[description].js`
- Index creation on large tables: use `CONCURRENTLY` (PostgreSQL) or the equivalent non-blocking form to avoid table locks.

## Step 7 — State the rollback procedure

Before the migration runs in production:

```
Rollback procedure: [knex migrate:rollback / rails db:rollback / exact command]
Effect: [what state the schema returns to]
Data recovery: [not needed / backup restore required / not possible]
```

If rollback would cause data loss or application errors, state that explicitly before the migration runs.

## Step 8 — Test the migration locally

Run:

```bash
# Run up
knex migrate:latest  # or: rails db:migrate / python manage.py migrate / goose up
# Verify schema
# Run down
knex migrate:rollback  # or equivalent
# Verify schema reverted
# Run up again (idempotency check)
knex migrate:latest
```

Confirm: up/down/up succeeds without errors before running in staging or production.

## Summary output block

After migration is written and tested:

```
## Migration Summary
- Table: [name]
- Change: [description]
- Classification: [Additive/Safe | Expand/Contract Required]
- References found: [N — list or "none"]
- Deploy order: [migration first / code first / phase N of M]
- Data impact: [none / backfilled / permanently lost]
- Rollback: [command + effect]
- Local test: [up/down/up passed / failed]
- Expand/contract phases remaining: [N of M / complete]
```

## Rationalizations that don't apply

| Phrase | Why it fails |
|--------|-------------|
| "The column is dead code, just drop it" | Dead code that isn't verified by Step 3 has hidden references. Run the audit first. |
| "It's a simple rename — one migration is fine" | A single-migration rename causes a deploy window where the old column is gone but app code still references it. Use expand/contract. |
| "I'll write the migration first and check references after" | Step 3 is a precondition, not a follow-up. References found after writing the migration require rewriting it. |
| "The backfill is just a few rows" | Row count estimates are often wrong. Check the actual count before deciding on batching. |
| "down migrations never get used" | They do get used during rollbacks, failed deployments, and local dev resets. Write them correctly. |
| "I'll add NOT NULL without a backfill — nulls are invalid anyway" | Existing null rows will cause the constraint to fail on large tables. Backfill first. |
| "It's a test database, data loss is fine" | Migrations are written once and run in production. Write them production-safe from the start. |
| "We can do the second phase next sprint" | Phase 2 of expand/contract is a tracking item, not an optional follow-up. Create the ticket before this PR merges. |

---
name: database-migration
description: Use when writing, reviewing, or running database migrations — adding/dropping columns or tables, renaming, indexing, type changes, or any schema evolution task.
---

Classify before writing. Do NOT write migration code until Step 3 (risk classification) is complete.

## Step 1 — Identify migration tool

Detect the tool from project files. Look for these markers in order:

- `prisma/schema.prisma` → Prisma Migrate
- `db/migrate/*.rb` → Rails Active Record
- `knexfile.js` or `knexfile.ts` → Knex
- `flyway.conf` or `V*.sql` in a migrations folder → Flyway
- `db/changelog/` or `liquibase.properties` → Liquibase
- Raw `.sql` files with no framework markers → bare SQL

If no marker is found, ask the user which tool is in use. Do not infer from the ORM or framework alone.

## Step 2 — Read the current schema

Read the actual migration or schema file. Never infer column names, types, or constraints from model names, variable names, or memory.

- **Prisma**: read `prisma/schema.prisma`
- **Rails**: read the latest `db/schema.rb` or the most recent migration file in `db/migrate/`
- **Knex**: read the most recent migration file
- **Flyway/Liquibase**: read the current versioned SQL file
- **Raw SQL**: read the table definition (`\d tablename` in psql, `SHOW CREATE TABLE` in MySQL)

Confirm: exact column names, current data types, nullability, existing indexes, and foreign key constraints. If any of these is unknown, stop and read further before proceeding.

## Step 3 — Classify risk

Assign both axes before doing anything else.

### Lock risk

| Class | Meaning | Examples |
|-------|---------|---------|
| A | No lock or near-instant | `CREATE INDEX CONCURRENTLY`, `ADD COLUMN NULL` (no default), adding a new table |
| B | Brief lock, sub-second | `ADD COLUMN NOT NULL DEFAULT <value>` on PG 11+ (metadata-only), most `ALGORITHM=INPLACE` ops on MySQL |
| C | Full table lock | `RENAME COLUMN`, type change, `DROP COLUMN`, `DROP TABLE`, any operation not explicitly listed as A or B |

When in doubt, classify C. Lock class B is only correct if you can cite the specific database version and feature (e.g., "PG 11+ fast default").

### Rollback class

| Class | Meaning | Examples |
|-------|---------|---------|
| A | Fully reversible, no data risk | Add nullable column, add index, add new table |
| B | Reversible but with data risk | Backfill then add NOT NULL; down migration can drop the constraint but backfilled rows remain |
| C | Irreversible | `DROP COLUMN`, `DROP TABLE`, destructive type cast that loses precision or format |

State both classifications explicitly before Step 4:

> "Lock risk: B — PG 11+ fast default. Rollback class: A — new nullable column, drop in down migration."

## Step 4 — Choose deployment sequence

Use the classification from Step 3 to pick the deployment pattern:

| Lock | Rollback | Pattern |
|------|----------|---------|
| A | A | Single migration, any deploy order |
| B | A or B | Migrate-then-deploy for additive; deploy-then-migrate if app tolerates missing column briefly |
| C | A or B | Expand/contract: separate PRs for (1) add new structure, (2) migrate app code, (3) remove old structure |
| Any | C | Expand/contract required. Document all phases before writing any SQL. Label this Phase 1/N and state the remaining phases. |

For expand/contract, write out all phases even if only one is being implemented today:

```
Phase 1 — Add new_column (nullable). Deploy app reading both columns.
Phase 2 — Backfill new_column. Add NOT NULL constraint.
Phase 3 — Remove old_column after app no longer references it.
```

## Step 5 — Write the migration

Use the correct pattern for the detected database and tool.

**PostgreSQL**
- New index on a live table: `CREATE INDEX CONCURRENTLY idx_name ON table(col);` — never a plain `CREATE INDEX`
- Add NOT NULL with default (PG 11+): `ADD COLUMN col type NOT NULL DEFAULT value` is safe (metadata-only). On PG 10 or below, add nullable, backfill, then add constraint.
- Add check constraint without locking: `ADD CONSTRAINT ... NOT VALID;` then `VALIDATE CONSTRAINT ...;` in a separate transaction.
- Column rename: always expand/contract (Lock C, Rollback C).

**MySQL**
- Prefer `ALTER TABLE ... ALGORITHM=INPLACE, LOCK=NONE` where supported (adding columns, most index ops).
- For tables >1M rows or where `LOCK=NONE` is not supported: use `pt-online-schema-change` or `gh-ost`. State this in a comment at the top of the migration.
- Renaming: `RENAME COLUMN` is supported in MySQL 8.0+; still Rollback C — use expand/contract.

**SQLite**
- No `ALTER TABLE DROP COLUMN` (before SQLite 3.35) and no `RENAME COLUMN` (before 3.25). Default pattern: create new table, copy data, drop old table, rename new table.
- Always check the SQLite version before using ALTER shortcuts.

**Prisma**
- Run `prisma migrate dev` in development (generates and applies). Run `prisma migrate deploy` in CI/production (applies only).
- Shadow database is required for `migrate dev` — confirm `shadowDatabaseUrl` is set if not using the default.
- For multi-step migrations, create separate migration files using `prisma migrate dev --name phase-1-add-col`.

**Rails**
- Use the `change` method when the migration is fully reversible (adds table, adds column, adds index).
- Use explicit `up` / `down` methods when the migration is Rollback B or C.
- Call `reversible!` explicitly in the `down` method for irreversible migrations so the error is visible rather than silent.

**Knex**
- Use `table.specificType('col', 'citext')` or equivalent for DB-native types not in the Knex type map.
- Always return the promise chain from `exports.up` and `exports.down`.

## Step 6 — Write the down migration

Write the rollback path now, not later.

- **Rollback A**: write the exact inverse SQL or `down` method. If the up adds a column, the down drops it.
- **Rollback B**: write the reversal and add a comment documenting the data risk: `-- Down migration removes the NOT NULL constraint; backfilled data in new_col remains.`
- **Rollback C**: write the backup command that must be run before the up migration is applied:

```sql
-- ROLLBACK CLASS C: this migration is irreversible.
-- Before running: pg_dump -t tablename dbname > tablename_backup_$(date +%Y%m%d).sql
-- Down migration: not possible after data is dropped.
```

For Rails, call `reversible!` explicitly so the error is visible rather than silent.

## Step 7 — Verify app code sync

Before finalizing, check all three directions:

1. **New column referenced too early**: does app code read or write the new column before this migration runs? If deploy order is deploy-first, the column must not be required by the app until after the migration.
2. **Dropped column still referenced**: search the codebase for the column name being dropped. Every reference must be removed before or in the same deploy.
3. **Renamed column**: both the old name and the new name must be audited. Old name must be gone from app code in Phase 3 of expand/contract; new name must be present by Phase 2.

If a sync issue is found, state it and do not proceed until the app code change and migration change are coordinated.

## Step 8 — Output checklist block

After all steps are complete, output this block verbatim with values filled in:

```
## Migration Checklist
- [ ] Lock risk: [A/B/C] — [reason]
- [ ] Rollback class: [A/B/C] — [reason]
- [ ] Deployment order: [migrate-first / deploy-first / multi-step phases N]
- [ ] Down migration: [SQL written / backup command written / irreversible — noted]
- [ ] App code sync: [verified clean / issue found — description]
```

Do not abbreviate or skip lines. If any item is unknown, mark it `[ ] — UNRESOLVED` and state what information is needed.

## Shortcuts that don't apply

| Phrase | Why it doesn't apply |
|--------|----------------------|
| "It's just adding a column" | `NOT NULL` without a default is a full table lock on PG 10 and below. Classify first, write second. |
| "I'll handle the down migration later" | Write it in Step 6, not later. Later means never, or writing it under incident pressure. |
| "I know what the schema looks like" | Model names lie. A column named `user_id` may be `bigint`, `uuid`, or `varchar`. Read the actual schema file. |
| "We can just roll back the deploy" | Rolling back the app does not undo a `DROP COLUMN`. The data is gone. Classify C before you write the statement. |
| "expand/contract is overkill for a rename" | Rename is Lock C, Rollback C. Expand/contract is not optional — it is the only safe pattern. |
| "We can re-run the migration if it fails" | A partially applied Rollback C migration leaves the database in an unknown state. Backup first, always. |

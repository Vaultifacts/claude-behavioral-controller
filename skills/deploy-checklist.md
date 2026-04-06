---
name: deploy-checklist
description: Use when deploying to production or staging, pushing code to a live environment, cutting a release, or executing a hotfix deployment.
---

Complete all gates before executing the deploy. Do NOT run the deploy command until Step 10 (rollback procedure) is written out in full.

## Step 1 — Confirm authorization

State before anything else:
- Who authorized this deployment (name or role — not "I assumed it was fine")
- Target environment (prod / staging / preview)
- Source branch or tag being deployed

If any of these are unknown or ambiguous: STOP. Do not proceed.

## Step 2 — Confirm target environment

Explicitly state which environment is the target. Prod and staging are not interchangeable.

- If the user said "deploy" with no qualifier, ask: "Deploy to prod or staging?"
- If the current context suggests staging but the command targets prod: pause and confirm
- Document the environment in every status update going forward

## Step 3 — Check branch or tag

```bash
git log --oneline -5
git tag --sort=-version:refname | head -5
git status
```

- For prod: prefer a tagged release over a branch tip
- State the commit SHA that will be deployed
- If HEAD has uncommitted changes: STOP. A dirty working tree must never be deployed

## Step 4 — Run tests

Execute the full test suite. Do NOT skip.

If CI is running tests in parallel: wait for green. Do not deploy while CI is in-progress or red. "CI will probably pass" is not green.

If tests fail: STOP. Fix the failures or escalate to the user.

## Step 5 — Verify build

A passing test suite does not prove the build is clean. Run the build explicitly:

```bash
npm run build       # Node
cargo build --release  # Rust
go build ./...      # Go
```

If deploying a Docker image: verify CI finished building the new image and did NOT serve a cached layer from the previous commit. "Image is up to date" in deploy output means old code is running.

If the build fails: STOP.

## Step 6 — Audit environment variables

Diff env var references between the last production tag and HEAD:

```bash
git diff [last-prod-tag]..HEAD -- . | grep -E 'process\.env\.|os\.environ|getenv|ENV\['
```

For every new reference found:
1. Identify the variable name
2. Verify it exists in the production secrets manager or `.env.production`
3. Confirm the value is not a staging placeholder

If any new env var reference is unverified in production secrets: **deploy blocker. STOP.**

"I know it's set" is not verification. Open the secrets manager and confirm it.

## Step 7 — Check migrations

Diff migrations between last prod tag and HEAD:

```bash
git diff [last-prod-tag]..HEAD -- migrations/ db/ schema/
```

For each migration found:

| Migration type | Safe order | Required action |
|----------------|-----------|-----------------|
| Additive (new nullable column, new table, new index) | Migrate BEFORE deploy | Run migration, then deploy |
| Rename or drop with compatibility shim | Multi-step required | Deploy shim first → migrate → deploy removal |
| Destructive (DROP column, DROP table) | Backup BEFORE migrate | Backup mandatory; write the backup command now |

For destructive migrations, write the backup command before proceeding:
```
Backup: pg_dump -t [table] [db] > backup-[table]-$(date +%Y%m%d).sql
```

Do not deploy a destructive migration without a timestamped backup you can restore from.

## Step 8 — Review the changelog

```bash
git log [last-prod-tag]..HEAD --oneline
```

Read every commit. Flag anything unexpected: commits from unrelated branches, large ambiguous commit messages ("misc fixes", "updates"), changes touching unrelated files.

If you see unexpected commits: pause and confirm with the user before continuing.

## Step 9 — Check feature flags

If any new code is behind a feature flag, confirm the flag is set correctly in prod config before the deploy lands.

If feature flags cannot be verified: note it explicitly and get confirmation from the user.

## Step 10 — Write out rollback procedure

Do not write "rollback is available." Write the actual procedure now, before the deploy runs. Fill in every line:

```
## Rollback procedure

- Revert: `git revert [commit SHA]` or `git checkout [last-prod-tag]` + redeploy
- Migration rollback: [down migration SQL command] OR [not reversible — backup at path/to/backup-file.sql]
- Env var rollback: [none required] OR [remove VAR_NAME from secrets manager]
- Feature flag rollback: [none] OR [set FLAG_NAME=false in prod config]
- Deploy command to execute rollback: [exact command]
- ETA to complete rollback: ~[N] minutes
```

If you cannot fill in every line: the deploy is not ready. STOP and resolve the gaps first.

## Step 11 — Notify stakeholders

For a prod deploy, confirm who needs to know before the deploy starts: on-call engineer, product owner, support team (if user-facing behavior changes). Send the notification now, not after.

Format:
```
Deploying [version/description] to prod at [time].
Changes: [git log summary or link]
Rollback ETA: ~[N] minutes if needed.
Point of contact: [name]
```

## Step 12 — Execute deploy

Run the deploy command and document exactly what was run. Do not use an abbreviated or improvised variant unless you have verified it is equivalent.

## Step 13 — Post-deploy health check

Within 5 minutes of deploy completion:

```bash
curl -f https://[your-domain]/health && echo "OK" || echo "FAILED"
```

Must return HTTP 200. Also check:
- No crash loops in workers or daemons
- No new ERROR-level log entries in the first 2 minutes
- Error rate not elevated above pre-deploy baseline

If any check fails: execute the rollback procedure from Step 10 immediately. Do not wait to diagnose first.

## Step 14 — Confirm or rollback

**If all health checks pass:**
```
Deploy complete.
Version: [tag/commit]
Environment: [prod/staging]
Health check: passed
Time: [timestamp]
```
Notify stakeholders.

**If any health check fails:** Execute rollback from Step 10 immediately. Roll back first, diagnose after. Notify stakeholders of the rollback.

## Gates that don't have exceptions

| Phrase | Why it doesn't apply |
|--------|----------------------|
| "It's just a config change" | Env var audit (Step 6) still applies. Config changes cause production outages. |
| "CI is green" | Wait for CI to finish and go green. In-progress CI is not green. |
| "I know the env vars are right" | Verify against the secrets manager. Knowledge is not verification. |
| "Rollback is obvious" | Write it out. Obvious things get forgotten during incidents. |
| "We can roll back if needed" | "We can" is not a written procedure. Write Step 10 first. |
| "Skip the health check, it'll be fine" | 5-minute health check prevents 2am pages. Step 13 is mandatory. |
| "Just a one-line change" | One-line changes cause prod incidents. All 14 steps apply. |

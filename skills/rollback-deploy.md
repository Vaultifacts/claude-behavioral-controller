---
name: rollback-deploy
description: Use when rolling back a production deployment — bad deploy, elevated error rate after deploy, or any situation requiring reversion to a previous version.
---

Do NOT execute any rollback command until Step 3 (DB migration compatibility) is verified and Step 4 (stakeholder notification) is sent. A rollback that breaks the DB layer extends the incident.

## Step 1 — Confirm rollback is the right fix

Before touching anything, answer:
1. Is the error rate actually caused by the new deploy? Check the error timeline: did errors start exactly at deploy time, or were they present before?
2. Is the error from the application code, or from a config/infra change in the same deploy? (Config rollback ≠ code rollback — they have different procedures.)
3. Is the target version (`vN-1`) actually known-good? Check git log or release notes — confirm it does not have its own known incident or unfixed bug.

If the answer to #1 is "errors predate the deploy," rollback is the wrong fix. Stop and diagnose.
If the target version has a known issue, state it before proceeding — do not silently roll back to a broken version.

State: "Rollback confirmed: [yes — errors started at deploy time / no — investigate further]. Target version: [tag/SHA — confirmed safe / has known issue: describe]."

## Step 2 — Identify what was in the deploy

Read the diff or release notes for the version being rolled back. Specifically identify:
- Were any database migrations included?
- Were any environment variable changes included?
- Were any infrastructure changes included (new queues, new S3 buckets, new IAM policies)?

These non-code changes may NOT be reversible by a code rollback, and some actively break the previous version if left in place.

State: "Deploy contained: [code only / code + DB migrations / code + env vars / code + infra changes]. Non-reversible changes: [list or 'none']."

## Step 3 — Check DB migration compatibility (GATE if migrations present)

If the deploy included database migrations, answer before executing any rollback:

1. Were any `NOT NULL` constraints added without a default value? If yes, the previous application version will fail on any write to that table. You must add a default or drop the constraint before rolling back the code.
2. Were any columns removed? The previous version may reference them. Check if removal was preceded by a code deploy that removed the references.
3. Were any column types changed? The previous version may send the old type.

```sql
-- Check new columns added in this deploy for nullability
SELECT column_name, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = '<affected_table>'
  AND column_name IN ('<new_column_1>', '<new_column_2>');
```

If any migration is incompatible with the previous code version: fix the schema issue first. Do not roll back the code until the schema is safe for both versions.

Iron rule lifts here — Step 3 is complete when all migration compatibility questions are answered.

## Step 4 — Notify stakeholders BEFORE executing

Send the rollback notification before the first `aws`/`kubectl`/`heroku` command runs:

```
Rolling back [service] from [current version] to [target version].
Reason: [one sentence — elevated errors since deploy at HH:MM]
ETA to stable: [estimate]
Will update when complete.
```

Notification is not optional. A rollback that stakeholders don't know about causes parallel incident investigation that wastes time and can conflict with the rollback itself.

## Step 5 — Execute the rollback

Use the platform-appropriate command. Examples:

**AWS ECS:**
```bash
aws ecs update-service \
  --cluster <cluster> \
  --service <service> \
  --task-definition <family>:<previous_revision> \
  --region <region>

# Wait for stability
aws ecs wait services-stable --cluster <cluster> --services <service> --region <region>
```

**Kubernetes:**
```bash
kubectl rollout undo deployment/<name> -n <namespace>
kubectl rollout status deployment/<name> -n <namespace>
```

**Heroku:**
```bash
heroku releases:rollback v<N> --app <app-name>
```

**Docker Compose / single server:**
```bash
docker pull <image>:<previous-tag>
docker-compose up -d  # with previous image tag in compose file
```

During rollout: monitor deployment health. Do not proceed to Step 6 until all instances are running the previous version.

## Step 6 — Verify rollback succeeded

Do not declare the rollback complete until all four pass:

1. **Error rate** — confirm returned to pre-incident baseline. Quote before/after numbers.
2. **Health endpoint** — `curl -f https://<domain>/health` returns 200.
3. **Auth path** — if the incident involved auth (as it often does), test with a real token.
4. **Deployment version** — confirm the running version is actually the target, not a mixed fleet.

```
## Rollback Verification
- Error rate: [before X% → after Y%] ✓ / ✗
- Health endpoint: 200 ✓ / ✗
- Affected path smoke test: ✓ / ✗
- All instances on target version: ✓ / ✗
```

If any check fails: the rollback did not fully work. Do not declare resolved. Return to Step 3 (likely a schema issue) or escalate.

## Step 7 — Post-rollback monitoring window

Do not declare the incident resolved immediately after Step 6. Hold for a defined window:
- Error spike lasting < 5 minutes: hold 15 minutes after rollback stabilizes
- Error spike lasting 5–30 minutes: hold 30 minutes
- Error spike lasting > 30 minutes (potential data corruption): hold 1 hour and check for data integrity issues

During the window: watch error rate trend. If errors resurface, the problem was not the deploy.

## Step 8 — Document and plan re-deploy

After the window passes:

```
## Rollback Summary
- Service: [name]
- Rolled back from: [version / SHA]
- Rolled back to: [version / SHA]
- Root cause: [one sentence — confirmed or suspected]
- DB migrations left in place: [yes — [list columns] / no]
- Post-rollback monitoring: [N minutes — clean / resurged]
- Re-deploy plan: [fix description / not yet determined]
- Ticket created: [URL or "no"]
```

Do NOT delete or deregister the bad task definition / release. Preserve it for root cause analysis.

---

## Rationalizations table

| Phrase | Why it fails |
|--------|-------------|
| "Just roll it back, we can check the DB after" | A NOT NULL column without a default will break writes in the previous version. Check first. |
| "It was working 30 minutes ago, just revert" | Check what else changed in the deploy: env vars, migrations, infra. Code rollback only fixes code changes. |
| "I'll tell the team once it's stable" | Parallel investigation from uninformed engineers wastes time and can conflict with your rollback. Notify first. |
| "The monitor went green, we're done" | Green monitor ≠ rollback complete. Run the four verification checks. Monitors can lag. |
| "Let's keep the rollback going even though the DB check failed" | A DB-incompatible rollback adds a second failure on top of the first. Fix the schema, then rollback. |
| "I'll document the root cause next sprint" | Root cause is most accurate within 2 hours of the incident. Document now or it won't happen. |
| "We can drop the new DB columns now that we rolled back" | Column drops are destructive and irreversible. Leave them — they are dead weight until the fix is ready. |
| "The error started right after the deploy so it must be the deploy" | Correlation is strong evidence but not proof. Confirm the target version is clean before executing. |

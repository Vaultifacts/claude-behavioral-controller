---
name: incident-response
description: Use when responding to a live production incident — system down, critical error spike, data loss event, security breach, or any situation requiring structured triage, containment, fix, verification, stakeholder communication, and post-mortem.
---

> **Iron rule 1**: Do NOT attempt any fix — no code change, no rollback, no restart, no config change — until Step 3 (impact scope) is complete.

> **Iron rule 2**: Do NOT close this incident until Step 9 (post-mortem document) is written and linked.

Incident: $ARGUMENTS

If $ARGUMENTS is empty, ask: 'What is the observed symptom and affected service?' Do not proceed without it.

---

## Step 1 — Declare the incident

Before any investigation begins, state the following:

```
## Incident Declared
- Incident commander: [name or "me"]
- Time declared: [HH:MM timezone]
- Affected service(s): [names]
- Observed symptom: [one sentence]
- Incident channel/ticket: [URL or "none — create one now"]
```

If 'Incident commander' is unknown, name yourself as acting incident commander and flag that a human should assume the role. Do NOT proceed without a named owner.

---

## Step 2 — Classify severity (P0–P3)

Assign exactly one severity level. If two levels seem applicable, choose the higher one. Do not negotiate severity downward to avoid paging someone.

| Level | Name | Criteria | Communication cadence |
|-------|------|----------|-----------------------|
| P0 | Critical | Total service outage; data loss in progress; security breach with active exfiltration; payment processing down | Every 15 min internal; immediate external |
| P1 | High | Major feature unavailable for >10% of users; severe performance degradation (>5x baseline); partial data corruption confirmed | Every 30 min internal; within 1 hr external |
| P2 | Medium | Single non-critical feature broken; elevated error rate (<10% users affected); no data loss | Hourly internal; external if user-facing and noticeable |
| P3 | Low | Minor degradation; cosmetic bug; workaround available; no active user impact | Internal only; no external required |

State the severity: 'This is P[N] because [specific criterion from the table applies].' If no criterion matches, ask the user rather than guess.

---

## Step 3 — Assess impact scope (GATE for Iron Rule 1)

Answer all five questions before moving to Step 4. Leave no item as 'unknown' without stating what you will do to find out.

1. **What is broken?** — specific service, endpoint, job, or feature. Not "the app." Name the component.
2. **Who is affected?** — all users / subset (by region, plan tier, cohort). Quantify if possible.
3. **Since when?** — first error timestamp from logs, not "a while." Run: `grep -i "error\|exception\|500" <log> | head -5` or equivalent.
4. **Is it getting worse, stable, or recovering?** — check error rate graph or log volume over time.
5. **Is there any data loss or corruption?** — yes / no / unknown. If unknown, state what check would determine this and run it.

Do not proceed to Step 4 until all five answers are written. Estimates are acceptable; blanks are not.

Iron rule 1 lifts here — Step 3 is complete when all five answers are recorded.

---

## Step 4 — Containment decision

Choose the containment strategy now. Execute containment before writing any fix code.

| Situation | Preferred containment | When NOT to use |
|-----------|----------------------|-----------------|
| Bad deploy caused the incident | Rollback to previous version | When previous version also has the bug, or rollback causes data migration issues |
| Feature introduced the regression | Disable feature flag | When no feature flag exists |
| Traffic/load is the cause | Rate limit, shed load, scale horizontally | When it's not a load problem |
| Third-party dependency failing | Circuit break / degrade gracefully / serve cached response | When dependency is central and degrading means data loss |
| Data corruption in progress | Put affected resource into read-only mode; halt writes | When corruption is already complete |
| Security breach (active) | Revoke credentials/tokens, isolate affected service, block attacker IP | After isolation: do not touch evidence |
| Cannot identify cause yet | Rollback to last known-good state as precaution | When rollback itself is risky (schema migration in the deploy) |

```
## Containment Plan
- Strategy chosen: [rollback / feature flag / rate limit / circuit break / read-only / credential revoke / other]
- Action: [exact command or steps]
- Expected effect: [what changes once this is done]
- Rollback of containment: [how to undo this containment if it makes things worse]
- Executed at: [timestamp]
```

State the rollback of containment before you execute containment. If you cannot state how to undo the containment step, that step is itself a risk.

---

## Step 5 — Fix

Invoke the `hotfix` skill for the technical repair. Do not write fix code directly in this incident response. The hotfix skill enforces: independent root cause verification, minimal diff scope, test requirement, rollback statement, and merge-back discipline.

While the fix is being developed, continue this skill at Step 6 (communications).

If the fix is not a code change (config, DNS, database statement, infrastructure):

```
## Fix Applied
- Type: [config / database / dns / infrastructure / code]
- Change: [exact change made]
- Applied by: [name]
- Applied at: [timestamp]
- Verified by: [how you confirmed it took effect]
```

---

## Step 6 — Internal status communication

Send the following update immediately after containment is executed. Repeat on the cadence defined in Step 2.

```
## Incident Update — [HH:MM timezone]

**Status:** [Investigating / Contained / Fixing / Monitoring / Resolved]
**Severity:** P[N]
**Affected:** [service and user population]
**What we know:** [1-3 sentences — facts only, no speculation]
**What we don't know yet:** [specific open questions]
**Current action:** [what is actively being done right now]
**Next update:** [time]
**Incident commander:** [name]
```

Do not omit the 'What we don't know yet' field. Admitting uncertainty prevents stakeholders from acting on false information. If everything is known, write 'Nothing — situation fully understood.' Never leave this field blank.

---

## Step 7 — External customer-facing communication (P0/P1 user-facing)

For P0 and P1 user-facing incidents: draft external communication now. For P2 and P3: optional. When skipping: state 'Skipping external communication because [reason].'

```
## [Service Name] — [Brief Title]

**Status:** Investigating / We have identified / We have resolved
**Posted:** [HH:MM timezone]

We are [currently investigating / aware of] an issue affecting [feature/service].

**Impact:** [What users are experiencing — be specific.]

**What we are doing:** [One sentence. Honest. No promises.]

**Next update:** [time, or "when resolved"]

We apologize for the disruption.
```

Constraints:
- Do NOT include internal details, root cause guesses, or technical stack information
- Do NOT promise a resolution time unless already resolved
- Do NOT use "may be experiencing" if impact is confirmed — be direct

---

## Step 8 — Verify resolution

Do not declare the incident resolved until all four checks pass.

1. **Error rate** — confirm returned to pre-incident baseline. Show before/after numbers.
2. **Service health endpoint** — `curl -f https://[domain]/health && echo OK`. Must return 200.
3. **Affected user flow** — manually verify the specific user action that was failing. Log the result.
4. **No new error classes** — check logs: `grep -i "error\|exception" <log> | tail -20`. Compare to pre-incident baseline.

```
## Resolution Verification
- Error rate: [before X% → after Y%] ✓ / ✗
- Health endpoint: [HTTP 200] ✓ / ✗
- User flow verified: [description of manual check] ✓ / ✗
- No new errors: [confirmed clean / found: description] ✓ / ✗
- Resolved at: [HH:MM timezone]
```

If any check fails: do not close the incident. Return to Step 4 or Step 5. Do NOT move status to 'Resolved' until all four checks pass.

---

## Step 9 — Post-mortem (GATE for Iron Rule 2)

Write the post-mortem before closing the incident ticket. 'We'll do this next week' is how recurring incidents happen. The post-mortem is a gate, not a follow-up.

Iron rule 2 lifts here — Step 9 is complete when the post-mortem document is written and linked to the incident ticket.

```
# Post-Mortem: [Incident title]
Date: [YYYY-MM-DD]
Severity: P[N]
Duration: [start time] → [resolution time] = [total minutes/hours]
Incident commander: [name]
Participants: [names]
Status: [Draft / Final]

---

## Summary
[2-4 sentences. What happened, who was affected, how long, how it was resolved.]

---

## Timeline
All times in [timezone].

| Time | Event |
|------|-------|
| HH:MM | [First alert / user report / detection] |
| HH:MM | [Incident declared] |
| HH:MM | [Initial diagnosis conclusion] |
| HH:MM | [Containment action taken] |
| HH:MM | [Fix applied] |
| HH:MM | [Resolution verified] |
| HH:MM | [Incident closed] |

---

## Root Cause
[One paragraph. Technical root cause only. "Human error" is always an intermediate cause — find the system condition or process gap that made the error possible.]

---

## 5 Whys
1. Why did [symptom] occur? → Because [cause 1]
2. Why did [cause 1] occur? → Because [cause 2]
3. Why did [cause 2] occur? → Because [cause 3]
4. Why did [cause 3] occur? → Because [cause 4]
5. Why did [cause 4] occur? → Because [root cause — a system or process gap]

[The final why must be a process, system, or architecture gap — not a person's mistake.]

---

## What Went Well
-
-

---

## What Went Poorly
-
-

---

## Action Items

| # | Item | Owner | Due date | Priority |
|---|------|-------|----------|----------|
| 1 | [Prevention item tied to root cause] | [name] | [date] | P[N] |
| 2 | [Detection/alerting improvement] | [name] | [date] | P[N] |
| 3 | [Process or runbook improvement] | [name] | [date] | P[N] |

[Minimum: one action item addressing the root cause.]

---

## Links
- Incident ticket: [URL]
- Monitoring/alert that fired: [URL]
- Deploy that caused it (if applicable): [URL]
- Hotfix PR: [URL]
```

Required fields — the post-mortem is incomplete if any are missing:
- Timeline with at least 5 entries
- Root cause statement that goes below 'human error'
- 5 Whys analysis
- At least one action item with a named owner and due date

An action item without an owner is not an action item. An action item without a due date will not be done.

---

## Step 10 — Close the incident

Close the incident only when all boxes are checked:

```
## Incident Closure Checklist
- [ ] Resolution verified (all 4 checks in Step 8 passed)
- [ ] Post-mortem written and linked (Step 9 gate passed)
- [ ] Final internal status update sent ("Resolved" status)
- [ ] Final external update sent (if applicable)
- [ ] Action items entered into tracking system with owners and due dates
- [ ] Incident ticket updated to "Resolved" with resolution timestamp
```

---

## Abort / Escalate Criteria

Stop and escalate to human leadership immediately if:
- The incident is P0 and has not been assigned a human incident commander within 15 minutes
- The root cause is not understood after 30 minutes of investigation
- The fix requires production database surgery with no available DBA
- Any indication of active security exfiltration — stop the technical response and involve security/legal
- Two consecutive containment attempts have failed and the situation is worsening

---

## Rationalizations That Will Extend the Incident

| Phrase | Why it fails |
|--------|-------------|
| "We know what's wrong, let's just fix it" | Scope assessment comes before the fix. An unscoped fix can mask the symptom while the root cause keeps running. |
| "We'll do the post-mortem next week" | Next week means never. The timeline is accurate now; it degrades rapidly. Write it before closing. |
| "It's obviously a P0, no need to classify" | Severity drives communication cadence and escalation path. 'Obviously P0' without writing it means stakeholders get P0 impact with P2 communication. |
| "We don't need to tell customers, it was brief" | For P0/P1 user-facing incidents, external communication is not optional. Brief outages still erode trust. |
| "The monitor went green, we're resolved" | Green monitor is one of four resolution checks. Run all four. Monitors can lag or have flawed thresholds. |
| "Action items can wait until the post-mortem is polished" | Action items with owners and due dates are required for the post-mortem to be complete. |
| "We already know the root cause, no need for 5 Whys" | 5 Whys finds the systemic gap behind the root cause. 'We know the root cause' usually means 'we know the proximate cause.' |
| "I'll handle communication once things stabilize" | Communication happens concurrently with investigation. Stability is not a prerequisite for stakeholder updates. |
| "The rollback fixed it, so we don't need hotfix discipline" | If rollback was your fix, document it in Step 5. If a code fix is still needed, hotfix discipline applies then. |
| "Scope assessment takes too long during a P0" | The five questions in Step 3 take under 5 minutes. A fix applied to the wrong scope extends the incident. |
| "We'll figure out containment as we go" | Containment must be chosen and documented before the fix begins. |
| "The incident is over once the fix is deployed" | The incident is over when Step 10's closure checklist is complete — not when the deploy finishes. |

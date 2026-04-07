---
name: api-contract-change
description: Use when modifying an existing API contract — REST endpoint, function/method signature, GraphQL schema, event payload, message queue schema, or webhook shape — where existing consumers may be affected.
---

Enumerate all consumers before classifying the change. Do NOT implement a breaking change until Step 5 (user confirmation) is complete.

API contract change: $ARGUMENTS

## Step 1 — Identify the contract element

Read the actual definition. Record:
- For REST endpoints: HTTP method, URL path, request body shape (every field, type, required/optional), response body shape, all status codes, headers/query params callers depend on
- For function/method signatures: exact name, all parameters (name, type, default, position), return type
- For GraphQL: type/query/mutation/subscription definition, all fields and nullability
- For event/message queue payloads: schema version if present, every field, types, required vs optional
- For webhook payloads: every field emitted, shape version, event type discriminator

Read the file — do NOT reconstruct the contract from usage patterns or memory. Use Glob or Grep to locate the definition file if the path is not known.

## Step 2 — State the proposed change precisely

Write out the exact before/after:
```
Before: [exact current signature / shape]
After:  [exact proposed signature / shape]
Change type: [field rename / field removal / type change / enum value change / parameter added / parameter removed / parameter made required / status code change / response shape restructure]
```
If the change is not yet fully defined, ask for the target value before proceeding. Do not invent a plausible name.

## Step 3 — Classify: additive/safe vs. breaking

Assign one of these classes using the table below. State the class explicitly before Step 4.

| Change | Class |
|--------|-------|
| Add an optional field to a response body (existing fields unchanged) | Safe/Additive |
| Add an optional parameter with a default value to a function | Safe/Additive |
| Add a new endpoint alongside existing endpoints | Safe/Additive |
| Add a new optional query parameter to a REST endpoint | Safe/Additive |
| Add a new enum value to a type | Potentially Breaking |
| Rename a field in a request body | Breaking |
| Rename a field in a response body | Breaking |
| Rename a function or method | Breaking |
| Remove a field from a request body | Breaking |
| Remove a field from a response body | Breaking |
| Remove an endpoint entirely | Breaking |
| Change a field's type (e.g., string → integer, nullable → required) | Breaking |
| Change a parameter from optional to required | Breaking |
| Remove a parameter's default value | Breaking |
| Change an HTTP status code on a known path | Breaking |
| Reorder positional function parameters | Breaking |
| Change a GraphQL field from nullable to non-null | Breaking |
| Change a GraphQL field from non-null to nullable | Potentially Breaking |
| Change a message queue event type discriminator value | Breaking |
| Change a webhook field name or remove a webhook field | Breaking |

Classification rule for ambiguous cases: When in doubt, classify as Breaking.

Required output before Step 4: "Classification: [Safe/Additive | Potentially Breaking | Breaking] — [one-sentence reason]."

If this change requires a database schema change, also invoke the `database-migration` skill.

## Step 4 — Enumerate all consumers

Search exhaustively. A consumer is any code, config, test, or external system that calls this API, reads this response, or depends on this contract shape.

**Pass 1 — Internal code references:**
```bash
# REST endpoint
grep -r '"/api/path"' --include="*.ts" --include="*.js" --include="*.py" --include="*.rb" --include="*.go" . 2>/dev/null | grep -v ".git/"
# Function/method
grep -r "functionName\b" --include="*.ts" --include="*.js" --include="*.py" --include="*.go" --include="*.rb" . 2>/dev/null | grep -v ".git/"
# GraphQL
grep -r "fieldName" --include="*.graphql" --include="*.gql" --include="*.ts" --include="*.js" . 2>/dev/null | grep -v ".git/"
```

**Pass 2 — Test files:**
```bash
grep -r "fieldName\|endpointPath\|functionName" --include="*.test.*" --include="*.spec.*" --include="*_test.*" --include="test_*.py" . 2>/dev/null | grep -v ".git/"
```

**Pass 3 — Configuration, CI, and infrastructure:**
```bash
grep -r "fieldName\|/api/path" --include="*.yml" --include="*.yaml" --include="*.json" . 2>/dev/null | grep -v ".git/" | grep -v "node_modules"
```

**Pass 4 — External and cross-service consumers:**
Is this API documented in a README, CHANGELOG, or docs folder? Is there a client SDK generated from this API? Does any other service or repo call this API? Ask the user: "Are there external services, mobile apps, third-party integrations, or other repositories that call this endpoint/function?"

Required output before Step 5:
```
Internal code: [list files:lines or "none found"]
Test files: [list files:lines or "none found"]
Config/CI: [list files:lines or "none found"]
External consumers: [confirmed none / user input required]
```
If external consumers cannot be confirmed as absent, treat as "unknown — assume present" and proceed with the full migration plan.

## Step 5 — Get user confirmation (breaking changes only)

For Safe/Additive: "Classification: Safe/Additive. No migration required. Proceeding to implement."

For Breaking or Potentially Breaking — do NOT write any code yet. Output this block:
```
## Breaking Change Summary
- Change: [exact before/after from Step 2]
- Classification: [Breaking / Potentially Breaking]
- Reason: [one sentence]
- Consumers found: [N internal, N tests, N config, external unknown/confirmed]
- Migration strategy required: [see Step 6 options]

Proposed migration: [one of the four strategies from Step 6, with brief rationale]

Confirm to proceed? (yes / change strategy / cancel)
```
Do NOT assume confirmation. A response of "yes go ahead" to an earlier message is not confirmation of this specific block.

## Step 6 — Choose a migration strategy

**Strategy A: Coordinated Update (all consumers in one commit/deploy)**
Use when: all consumers are internal to the same codebase, consumer list is complete and finite, all consumers can be updated atomically in the same PR, no external consumers.
How: update the contract definition, update every consumer from Step 4, run full test suite, commit as one atomic PR.
Do not use when: any consumer is external, undiscovered, or in a separate deployment.

**Strategy B: Deprecation Period**
Use when: external consumers exist that cannot be updated atomically, API is public or semi-public, transition window of days/weeks is acceptable.
How: (1) keep old contract fully functional, (2) add new contract alongside it, (3) mark old contract deprecated (docs, `Deprecation: true` header, code comments), (4) set deprecation deadline (minimum: one sprint for internal; one version bump for public), (5) communicate to all known consumers, (6) after deadline and no traffic, remove old contract. The removal step must be tracked — create a follow-up ticket immediately.

**Strategy C: API Versioning**
Use when: breaking change affects a stable versioned API, multiple consumers at different version levels must coexist, change is significant enough to warrant a new version.
How: (1) create new versioned route or schema (`/v2/resource`, `@deprecated` GraphQL field, schema version bump), (2) keep v1 fully functional, (3) migrate internal consumers to v2, (4) document v1→v2 migration for external consumers, (5) sunset v1 on defined timeline with communication.

**Strategy D: Compatibility Shim**
Use when: breaking rename or type change must land quickly, backward compatibility at runtime is preferred, shim will be temporary.
How: (1) implement new contract, (2) add shim that accepts old shape and transforms to new, (3) log when old path is hit to track remaining consumers, (4) set removal date, (5) track shim removal as follow-up item.

Required output: "Migration strategy: [A/B/C/D] — [name]. Rationale: [one sentence]. Phases: [list if multi-phase]."

## Step 7 — Implement

For Strategy A: Implement the contract change and update every consumer from Step 4. If any consumer found during implementation was not in the Step 4 list, STOP, add it to the consumer list, and assess whether the strategy still applies.

For all other strategies: Implement only the specific phase agreed in Step 6. Do not update consumers not part of this phase. Label the deprecation or version boundary clearly in code comments.

After implementation: run the full test suite. A failing test means a consumer was missed in Step 4.

## Step 8 — Output the change summary

```
## API Contract Change Summary
- Contract element: [function name / endpoint / schema]
- Change: [exact before → after]
- Classification: [Safe/Additive / Potentially Breaking / Breaking]
- Consumers found: [N] — [list or "see Step 4 output"]
- Migration strategy: [A/B/C/D — name]
- External consumers confirmed absent: [yes / no — user confirmed / unknown]
- Phase implemented: [1 of N / complete]
- Follow-up required: [yes — [ticket/issue created] / no]
- Tests: [N passed / failures: describe]
```
Do not abbreviate or skip fields. If follow-up is required, it must appear in this block.

---

## Rationalizations — Why Common Shortcuts Fail

| Phrase | Why it fails |
|--------|-------------|
| "It's an internal API — nobody external uses it" | "Internal" describes access control, not consumer scope. Internal APIs are called by other services, background jobs, test harnesses, and CLI tools. Run Step 4 before claiming scope. |
| "I'll just rename it everywhere with a global find-and-replace" | Find-and-replace misses string-based calls, generated clients, external services, test fixtures, and any consumer not in this repository. |
| "The parameter has a default so callers won't notice" | Callers that explicitly pass the old value or rely on the old default behavior will break. |
| "It's a minor type change" | No type change is minor at a contract boundary. Changing string → number, nullable → required, or array → object breaks every consumer that handles the old type. |
| "We can do this in a quick follow-up PR" | A follow-up PR that fixes broken consumers is a production incident window, not a follow-up. |
| "I know all the callers — it's just this one place" | The last time someone said this, they were wrong. Step 4 takes two minutes. Run it. |
| "It's already broken so we can change it freely" | A broken API may still have consumers handling the error gracefully. Enumerate them in Step 4 before assuming the change is safe. |
| "The tests will catch any missed consumers" | Tests only cover what was written. Undocumented callers, external services, and integration paths have no tests. |
| "We'll add the migration plan later" | Step 5 requires the migration strategy before Step 7 begins. There is no code written before the plan is confirmed. |
| "Adding a new enum value is safe" | Consumers that exhaustively switch/match on the enum will hit an unhandled case. This is Potentially Breaking. |
| "This is just a refactor, not an API change" | If the function signature, field name, return type, or HTTP contract changes, it is an API change. Intent doesn't change the blast radius. |
| "The old field will still be there temporarily" | 'Temporarily' without a deadline is permanent. Step 6 requires a removal date and follow-up tracking for any shim or deprecated path. |
| "The user said to just do it" | 'Just do it' applies to implementation, not to skipping consumer enumeration. Enumerate the consumers first — that is the agent's job. |
| "It's a POST body field, not a response field — callers control it" | Callers that send the renamed/removed field will get silent null or a 400 error. Both request and response shapes are part of the contract. |
| "No external consumers are registered" | 'Registered' is not the same as 'none exist.' Mobile apps, third-party tools, and scrapers don't register. |

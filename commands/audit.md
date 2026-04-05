# /audit — Exhaustive Codebase Audit

Run a comprehensive, multi-pass audit of the current project. Discovers the tech stack automatically, maps all source files, and systematically assesses every layer for bugs, gaps, inconsistencies, and improvements.

## Arguments
- `$ARGUMENTS` — Optional: specific area to audit (e.g., "security", "ui", "state management", "rust", "python"). If omitted, audits everything.

## Instructions

### Step 0: Determine scope

**If `$ARGUMENTS` is empty:** Full audit, 2 passes. Tell the user:
> Running full codebase audit (2 passes). For a medium project (~50-100 files) this takes 15-45 minutes.

**If `$ARGUMENTS` is a specific area**, map it to files:

| Argument | Focus files |
|----------|------------|
| `security` | config files, commands/, handlers/, services/, CSP, auth, .env |
| `ui` | components/, views/, shell/, *.module.css, accessibility |
| `state` | stores/, reducers/, context/, bridge, selectors |
| `backend` / `rust` / `python` / `go` | server-side source, services, DB ops, commands |
| `data` / `db` | migrations, schema, ORM models, persistence layer |
| `config` / `build` | package.json, tsconfig, vite.config, CI/CD, turbo.json |
| `types` / `domain` | shared types, interfaces, schemas, guards |
| `tests` | test files, fixtures, coverage config |
| `performance` | hot paths, render loops, DB queries, caching |
| `docs` | README, CLAUDE.md, architecture docs, inline comments |
| `api` | routes, controllers, middleware, OpenAPI spec |

For unrecognized arguments, use both Grep (search file contents for the keyword) and Glob (search file names) to find relevant files, then audit those.

### Step 1: Discover the project

**Read config files** (use Read tool, not shell commands):
- package.json / Cargo.toml / pyproject.toml / go.mod / pom.xml → language & framework
- Check for: monorepo (turbo.json, pnpm-workspace.yaml, lerna.json), frontend (React, Vue, Svelte, Angular), backend (Tauri, Electron, Express, FastAPI, Actix, Gin), database, build tools
- Check for: .env.example, Dockerfile, .github/workflows/, docs/ directory, ADRs
- **Read the project's CLAUDE.md** (if it exists) for coding conventions, forbidden patterns, and project-specific rules that should inform the audit

**List ALL source files** using Glob tool:
```
Glob: **/*.{ts,tsx,rs,py,go,js,jsx,vue,svelte,css,scss}
```

**Exclude from audit** (skip these even if found):
- `node_modules/`, `dist/`, `target/`, `build/`, `.next/`
- Lock files (`package-lock.json`, `pnpm-lock.yaml`, `Cargo.lock`)
- Generated files, minified bundles, source maps
- Files over 2000 lines (likely generated — note them but don't read fully)

**Create a tracking file** at `.claude-audit-progress.md` in the project root (add to .gitignore if one exists):
```markdown
# Audit Progress
## Assessed
(populated from Glob results as files are read)
## Remaining
(populated from Glob results — files not yet read)
## Findings count
CRITICAL: 0 | HIGH: 0 | MEDIUM: 0 | LOW: 0 | INFO: 0
```

Update this file after each agent completes. Read it first on subsequent passes to recover state after compaction.

### Step 2: Map the architecture

Read entry points to understand structure. Common entry points by language:
- **TS/JS**: main.tsx, App.tsx, index.ts, server.ts, app.ts
- **Rust**: main.rs, lib.rs
- **Python**: main.py, app.py, manage.py, __main__.py
- **Go**: main.go, cmd/*/main.go

Identify these layers (not all will exist in every project):

| Layer | Examples |
|-------|---------|
| **UI** | components, views, pages, templates |
| **State** | stores, reducers, context, signals, Zustand, Redux, Pinia |
| **Business Logic** | services, domain models, state machines, validators |
| **Data** | DB ops, ORM models, migrations, repositories, API clients |
| **IPC/Transport** | API routes, WebSocket, Tauri commands, gRPC, message queues |
| **Config/Build** | bundler, CI/CD, TypeScript/ESLint/Prettier config |
| **Assets** | images, fonts, static files, sprites |
| **Types/Schema** | shared types, interfaces, Protobuf, OpenAPI schemas |
| **Tests** | test files, fixtures, utilities, mocks |
| **Docs** | README, architecture docs, inline docs |

### Step 3: Audit by layer

Launch 2-3 Explore agents in parallel (use `model: "sonnet"` for depth; respects any model override in CLAUDE.md). Give each agent:
1. **Exact file paths** to read (not vague descriptions)
2. **The specific checklist items** to evaluate from the relevant section below
3. **Instructions to use IDs**: `CAT1 [SEVERITY] Title` — where CAT is a short category prefix (SEC for Security, UI for UI, SVC for Services, CFG for Config, etc.) and number is sequential within the category

Split agents by grouping layers **that have files** (skip empty categories):
- Agent 1: UI + State + Accessibility (if frontend exists)
- Agent 2: Business Logic + Data + IPC
- Agent 3: Security + Config + Types + Tests + Docs

For smaller projects (<30 files) or single-package projects, use 1 agent.
For monorepos, consider one agent per package/app.

#### Universal Checklist (all projects)

**Security:**
- Secrets in source code (.env committed, API keys hardcoded)
- Input sanitization (injection vectors: shell, SQL, XSS, path traversal)
- TOCTOU race conditions on file/path operations
- Authentication/authorization gaps
- Dependency vulnerabilities (outdated packages with known CVEs)

**Error Handling:**
- Silent error swallowing (catch blocks that only console.log)
- Missing error boundaries / global error handlers
- Crash-on-corrupt-data (no graceful degradation)
- Unhandled promise rejections / panics

**Data Integrity:**
- Schema drift between layers (frontend types vs backend vs DB)
- Silent data loss (truncation, caps with no warning)
- Missing validations on create/update operations
- Race conditions on concurrent writes

**Performance:**
- Unnecessary re-renders / redraws
- Unbounded growth (arrays, maps, listeners never cleaned up)
- Missing pagination / virtualization for large lists
- Expensive operations on hot paths (every frame, every keystroke)

**Documentation:**
- README accuracy (does it match what the code actually does?)
- Stale comments referencing old architecture
- Missing setup / prerequisites instructions

**Testing:**
- Coverage gaps per layer
- Stale fixtures / test utilities using wrong types
- Missing CI/CD pipeline

**Logging / Observability:**
- Missing structured logging on error paths
- No request/event tracing or correlation IDs
- Console.log left in production code paths
- No health check endpoint (if applicable)

#### Language-Specific Checklists

**TypeScript / JavaScript:**
- useEffect dependency arrays (missing deps, stale closures)
- Optimistic updates without rollback on failure
- Type assertions (`as any`, `as unknown`) hiding real issues
- Duplicated constants across files (colors, magic numbers)
- Event listeners not cleaned up on unmount
- CSS: hardcoded values, z-index conflicts, global selector leaks

**Rust:**
- `unwrap()` / `expect()` on fallible operations in non-test code
- Mutex poisoning risk (panic inside lock guard)
- Missing `Drop` implementations for owned resources
- Unsafe blocks without safety comments
- Error types: using `String` instead of typed errors
- Serialization: serde field names matching frontend expectations

**Python:**
- Missing type hints on public functions
- Bare `except:` clauses swallowing all errors
- Mutable default arguments
- File handles not using context managers
- Missing `__init__.py` in packages
- Async/sync boundary issues

**Go:**
- Unchecked errors (err not checked after function call)
- Goroutine leaks (no cancellation context)
- Race conditions (shared state without mutex)
- Missing `defer` for cleanup

**C# / .NET:** (if applicable)
- Undisposed IDisposable resources
- async void methods (should be async Task)
- Missing null checks on nullable reference types
- EF Core: N+1 queries, missing .AsNoTracking()

**Java / Kotlin:** (if applicable)
- Unclosed resources (streams, connections)
- Missing null safety annotations
- Thread safety issues with shared mutable state
- Missing @Override annotations

#### UI-Specific Checklist (if frontend exists)

- Accessibility: ARIA attributes, labels, keyboard nav, focus management
- Missing loading / error / empty states
- Missing selected / hover / focus visual feedback
- Hardcoded strings (i18n readiness)
- Responsive layout issues
- Color-only indicators (colorblind accessibility)
- Modal focus traps and escape handling

#### IPC-Specific Checklist (if client-server exists)

- Type mismatches between sender and receiver
- Missing reconnection / retry logic
- Silent message drops
- No startup handshake / ready signal
- Event payload not validated against current context (e.g., wrong workspace)

#### Database-Specific Checklist (if DB exists)

- N+1 query patterns
- Missing indexes on frequently queried columns
- Unparameterized queries (SQL injection risk)
- Connection pool exhaustion under load
- Missing migrations / no migration system
- No foreign key enforcement
- No backup/export mechanism

#### API-Specific Checklist (if REST/GraphQL exists)

- Missing rate limiting
- No pagination on list endpoints
- Inconsistent error response format
- Missing OpenAPI / GraphQL schema documentation
- No request validation middleware
- Missing CORS configuration
- No versioning strategy

### Step 4: Cross-cutting assessment

After agents return, **deduplicate findings** — agents running in parallel may report the same issue independently. Merge duplicates, keeping the more detailed description. Renumber IDs sequentially within each category after merging.

Then check interactions inline (not as a separate agent):
- **View lifecycle**: does switching views preserve state? Does unmount clean up?
- **Entity lifecycle**: create → use → update → delete — end-to-end correctness
- **Error propagation**: do errors in layer N surface correctly in layer N+1?
- **Project lifecycle**: open → work → close → reopen (if applicable)
- **Performance at scale**: what happens with 10x the current data?

### Step 5: Compile results

For each issue, format as:
```
**ID [SEVERITY] Title** — Description. File:line. Impact. Fix: resolution.
```

**Worked example:**
```
**SEC1 [CRITICAL] Shell injection via unsanitized model argument** — spawn('claude', [..., '--model', model], { shell: true }) passes the model string directly to cmd.exe. A model value like "mock & calc.exe" executes calc.exe. File: apps/sidecar/src/adapters/claude-code.ts:108. Impact: arbitrary command execution. Fix: validate model against allowlist in Rust command before storing, or remove shell:true from spawn.
```

**Severity guide:**
| Severity | Criteria | Examples |
|----------|----------|---------|
| CRITICAL | Data loss, security vulnerability, or crash | Shell injection, DB corruption on startup, silent data deletion |
| HIGH | Feature is broken or produces wrong results | State machine can't reach valid states, stuck entities, broken lifecycle |
| MEDIUM | UX issue, inconsistency, or correctness risk | Missing validation, duplicated code, accessibility gap, type drift |
| LOW | Polish, minor inconsistency, or tech debt | Stale comments, magic numbers, missing tests, cosmetic CSS |
| INFO | Observation, architecture note, or future risk | Dead code, deprecated patterns, latent race condition |

Group by category. End with:
1. **Severity breakdown** — one line: `CRITICAL: X | HIGH: Y | MEDIUM: Z | LOW: W | INFO: V | Total: N`
2. **Summary table** — all items with ID, severity, title
3. **Top 5 recommended fixes** — highest impact items to address first
4. **Updated tracking file** — update `.claude-audit-progress.md` with assessed files and severity counts

### Step 6: Output

1. Write results to `audit-results.md` in the project root
2. Print the summary table and top 5 to the console

### Step 7: Repeat (if requested)

On subsequent passes:
1. Read the tracking list to see what's already been assessed
2. Focus on:
   - Files not yet read (REMAINING list)
   - Interactions between layers already assessed
   - Edge cases in flows identified in previous passes
3. Check existing findings for duplicates before adding new ones
4. Append new findings to the same audit results file

Stop when:
- The requested number of passes is complete (default: 2), OR
- A full pass yields zero new CRITICAL or HIGH items, OR
- The user says stop

## Scope control

If `$ARGUMENTS` specifies an area:
- Map which files/layers correspond to that area using the table in Step 0
- Read entry points for context but don't audit unrelated layers
- Still check cross-cutting concerns that touch the specified area
- Default to 1 pass for scoped audits

If `$ARGUMENTS` is empty:
- Audit everything
- Default to 2 passes

## Context management

- If context usage exceeds 70%, **first update `.claude-audit-progress.md`** with all findings so far, then tell the user: "Context is getting full. Run `/compact` and then say 'continue audit' to resume."
- After compaction, re-read `.claude-audit-progress.md` and the audit results file to recover state
- The tracking file is the primary checkpoint that survives compaction — always update it BEFORE suggesting compact

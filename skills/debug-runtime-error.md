---
name: debug-runtime-error
description: Use when given a stack trace, exception message, crash log, or runtime error output and asked to find the cause — before any fix is proposed or code is changed.
---

Read and parse the full error artifact BEFORE looking at any code. Do NOT propose a fix until Step 10 (root cause statement) is complete.

## Step 1 — Read the full error artifact

Paste or quote the ENTIRE stack trace, exception chain, or crash log. Do not summarize. Do not truncate.

If the user provided a partial trace, stop and ask:

> "Please provide the full output — including all `Caused by:`, `During handling of`, or chained exception blocks. Truncated traces hide the real cause."

Do not proceed to Step 2 until the complete artifact is available.

## Step 2 — Parse the structure

Identify each of the following from the artifact:

- **Exception type** — the class or error code (e.g., `TypeError`, `NullPointerException`, `ECONNREFUSED`)
- **Exception message** — the human-readable string attached to the type
- **Whether this is a chain** — does the trace contain `Caused by:`, `During handling of the above exception`, or a `.cause` property?
- **Call stack frames** — list them top to bottom; note file paths and line numbers

Do not skip this step because you "recognize the error." Parsing is structured extraction, not pattern matching.

## Step 3 — Find the innermost cause

For exception chains, work inward until there are no more nested causes:

- **Python:** find the last `During handling of the above exception` or `The above exception was the direct cause`
- **Java / Kotlin:** find the deepest `Caused by:` block
- **JavaScript / TypeScript:** find the root error in a `.cause` chain, or the first error thrown in a promise rejection chain
- **Go:** find the innermost wrapped error in an `errors.Is` / `errors.As` chain

The outermost exception is the symptom. The innermost exception is the cause. All analysis from this point forward is about the innermost exception.

## Step 4 — Identify the user-code frame

Separate user code from framework and library frames:

- **User code:** file paths inside the project directory — not `node_modules/`, `site-packages/`, `.gradle/`, `$JAVA_HOME`, or runtime library paths
- Find the **deepest** stack frame that points to user code (the frame closest to the error origin that is still project code)
- That frame provides the file path and line number for Step 7

If **no user-code frame exists** in the entire trace, do not read code. Hand off:

> "No user-code frame found. This may be a framework or environment issue. I'll investigate [exception type + message] as a configuration or dependency problem next."

## Step 5 — Classify the error type

Use the exception type and message from Step 2:

| Type | Signals | Common Cause |
|------|---------|--------------|
| Null / Undefined | `NullPointerException`, `TypeError: Cannot read properties of undefined`, `AttributeError: 'NoneType'` | Missing guard, uninitialized field, wrong key name |
| Type mismatch | `TypeError`, `ClassCastException`, `cannot convert`, `expected X got Y` | Wrong data shape, API contract change |
| Network / Timeout | `ECONNREFUSED`, `ETIMEDOUT`, `ConnectionResetError`, `socket hang up` | Service down, wrong host/port, firewall |
| Database | `OperationalError`, `QueryFailedError`, `relation does not exist` | Migration not run, wrong connection string, pool exhausted |
| Memory | `OutOfMemoryError`, `MemoryError`, process killed (exit 137) | Leak, large dataset in memory |
| Permission | `EACCES`, `PermissionDenied`, `403 Forbidden` | Missing file permission, wrong IAM role |
| Environment / Config | `KeyError` on env var name, `ConfigError`, missing required field | Missing env var, wrong config file loaded |
| Import / Init | `ModuleNotFoundError`, `Cannot find module`, `ClassNotFoundException` | Missing dependency, wrong path, not installed |

Record the classification. It governs the order of investigation in Steps 6 and 7.

## Step 6 — Check environment and config first

For certain error types, code reading is premature until the environment is verified:

- **Environment / Config:** read `.env`, config files, and the environment's variable list BEFORE opening any source file
- **Database:** verify the connection string and confirm migrations have run (`prisma migrate status`, `rails db:migrate:status`, etc.) BEFORE reading query code
- **Network / Timeout:** verify the target service is reachable (`curl`, `ping`, `nslookup`) BEFORE reading network code
- **Import / Init:** verify the package is installed (`pip show <package>`, `npm ls <package>`) BEFORE reading module code

For all other types: proceed directly to Step 7.

Code reading comes AFTER environment verification for the four types above. The fix may be a missing env var, not a code change.

## Step 7 — Read the user-code frame

Using the file path and line number from Step 4:

1. Open the source file at exactly that path. Do not guess; do not open a file with a similar name.
2. Read the full function or method body that contains the identified line.
3. Understand what value the code expects at that point, what it is actually receiving, and what operation is being attempted.

## Step 8 — Trace the bad value backward

From the line in Step 7, follow the bad value up through user-code frames:

- Where was the value set or returned before it arrived at this line?
- Which caller passed it in?
- Continue tracing upward through each user-code frame until you reach the origin of the bad value
- Identify precisely where the assumption broke (e.g., "expected a string but the API returns `null` when the field is absent")

Stop tracing when you reach a frame outside user code. The origin is the last user-code frame in the backward trace.

## Step 9 — Verify with a code quote

Before stating root cause, quote the specific line or lines that are wrong:

```
[file:line] — [what the code does at this line]
[why this is the problem given the bad value]
```

Example:
```
[src/utils/formatters.ts:34] — accesses `user.address.city` directly
[user.address is undefined when the shipping address was never collected]
```

Do not state root cause without this quote. No quote = stating assumption as fact.

## Step 10 — State root cause

Write this block before proposing any fix:

```
Root cause: [what is wrong] at [file:line]. [Why the code produces this error given the value it received.] [What condition or change caused the bad value to appear.]
```

Then, and only then:
- If the fix is a single targeted change in one file: propose it inline
- If the fix requires changes across multiple files or should be tracked: hand off to `fix-issue`

## Handoffs

**No user-code frame found** → investigation mode:
> "No user-code frame found. This may be a framework or environment issue. I'll investigate [exception type and message] as a configuration or dependency problem next."

**Root cause found, multi-file fix needed** → hand off to fix-issue:
> "Root cause identified. The fix touches [N] files. Handing off to fix-issue."

## Shortcuts that skip steps

| Phrase | Why it fails |
|--------|-------------|
| "I can tell from the error message what's wrong" | The message is the symptom. The trace contains the cause. Read it. |
| "Let me check the code first" | Environment check comes BEFORE code reading for env/config and database errors. Follow the classification. |
| "I'll just add a null check" | A null check at the wrong location adds a second bug. State root cause first. |
| "The fix is obvious" | Write the root cause statement before proposing any fix. Obvious fixes skip verification. |
| "quick" / "just tell me the fix" | Read the full artifact. Truncated analysis produces wrong fixes. |
| "I've seen this error pattern before" | Pattern recognition skips root cause verification. Read this trace, in this file, at this line. |
| "No need to quote the line" | No quote = no verification = assumption stated as fact. The quote is the evidence. |

---
name: handle-documentation
description: Use when adding, updating, or auditing documentation in a codebase. Invoke whenever the user says "add docs", "document this", "write JSDoc", "add docstrings", "update the README", "our docs are out of date", "add comments to this", "document the API", "generate documentation", or asks to improve code documentation in any form. Also invoke when documentation is requested as part of a larger task — docs deserve the same rigor as code. Use this before writing any documentation to ensure it will be accurate, maintainable, and not create future technical debt.
---

# Handle Documentation

## Overview

Documentation written without reading the code becomes wrong the moment the code changes. Documentation written after the fact describes what you remember, not what the code does.

**Core principle:** Documentation is a contract. Inaccurate docs are worse than no docs — they mislead confidently.

## The Four Phases

### Phase 1: Find What Needs Documenting

Don't guess — discover.

1. **Identify the target scope**
   - A single function? A module? A public API? The whole codebase?
   - What doc format is expected? (JSDoc, Python docstrings, Markdown, OpenAPI, README)
   - Is there an existing doc style in this project? Find one documented function/class and match it exactly.

2. **Find undocumented code systematically**
   - For functions/methods: grep for `function `, `def `, `const.*=>`, `class ` and check which lack doc comments
   - For public APIs: check what's exported vs. what has docs
   - For README gaps: what does the project do, how do you install it, how do you run it, how do you test it, how do you contribute — is each answered?

3. **Check for stale docs**
   - Find existing comments that reference function signatures, parameter names, or behaviors
   - Verify each one still matches the current code — stale docs are the primary documentation debt
   - If a docstring describes `@param userId string` but the function now takes `@param user User`, that's a bug

4. **Prioritize**
   - Public APIs and exported symbols: highest priority (callers depend on them)
   - Complex logic with non-obvious behavior: high priority (future readers need explanation)
   - Simple getters/setters and obvious wrappers: low priority (don't document the obvious)

### Phase 2: Read Before Writing

**Never write documentation without reading the actual code.**

For each symbol you're documenting:

1. **Read the full implementation** — not just the signature
   - What does it actually do vs. what its name implies?
   - Are there edge cases not obvious from the name?
   - Does it have side effects beyond the return value?
   - What happens on error? Does it throw, return null, return a Result type?

2. **Read the callers** — find 2-3 call sites
   - How is it actually used in practice?
   - What assumptions do callers make about the return value?
   - Are there usage patterns the docs should mention or warn against?

3. **Read the tests** — they document expected behavior
   - Tests reveal edge cases the implementation handles silently
   - If a test covers `null` input handling, the docs should mention it
   - Contradictions between tests and docs are bugs

### Phase 3: Write Accurate Documentation

**Match the style already in the codebase.** Consistency matters more than your preferred format.

**What good docs contain:**

| Element | Include when |
|---------|-------------|
| **Purpose** (what + why) | Always — one sentence describing what this does and why it exists |
| **Parameters** | When parameter names or types aren't self-evident |
| **Return value** | When the return shape isn't obvious from the type |
| **Side effects** | Always if present (mutates state, fires events, writes to disk) |
| **Throws/errors** | When the function can fail and what it throws |
| **Edge cases** | When behavior is non-obvious for null, empty, boundary values |
| **Examples** | For public APIs, complex signatures, or non-obvious usage |

**What good docs don't contain:**

- Restatements of the code: `// increments counter by 1` above `counter++`
- Lies about the implementation: don't document what you wish it did
- Tense that will age badly: avoid "currently", "as of v2", "TODO: document this"
- The author's internal reasoning that doesn't help the reader

**The accuracy test:** After writing a docstring, read only the docstring — not the code. Could someone correctly use this function from the docs alone? Would they be surprised by any behavior?

### Phase 4: Verify Documentation

Don't declare docs done without verification.

1. **Cross-check signatures**
   - Every `@param` name matches the actual parameter name
   - Every `@param` type matches the actual type
   - `@returns` describes the actual return value, not the intended one

2. **Test the examples**
   - If you wrote example code in the docs, run it or trace it manually
   - An example that doesn't work is worse than no example

3. **Check for staleness traps**
   - Did you document any behavior that's controlled by a config or flag? Note the dependency.
   - Did you describe any external service behavior? It can change independently.
   - Did you use specific version numbers or dates? They decay.

4. **README completeness check** (if updating README)
   - Clone the repo mentally from scratch: can you follow the README to a working state?
   - Are the commands in the README copy-pasteable and correct right now?
   - Does the README reflect the current project structure, not a historical one?

## Red Flags — STOP and Verify

- Writing docs before reading the implementation
- Copying parameter descriptions from similar functions without checking they match
- Documenting what you intend the code to do rather than what it does
- "I'll update the docs after I change the code" (the update never happens)
- Adding a doc comment that just restates the function name in sentence form

## Quick Reference

| Phase | Key Activity | Gate |
|-------|-------------|------|
| **1. Find** | Locate undocumented code, check for stale docs, prioritize | Target list with priority order |
| **2. Read** | Implementation + callers + tests before writing anything | Understand before documenting |
| **3. Write** | Match existing style, accurate, no restatements | Accuracy test: usable from docs alone? |
| **4. Verify** | Cross-check signatures, test examples, check for staleness | Every @param matches, examples work |

## Related Skills

- **superpowers:refactor-code** — If the code needs changing before it can be documented clearly
- **superpowers:codebase-quickmap** — For understanding a codebase before documenting it
- **superpowers:verification-before-completion** — Final gate before declaring docs done

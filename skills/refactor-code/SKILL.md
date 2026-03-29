---
name: refactor-code
description: Use when refactoring, modernizing, cleaning up, restructuring, or simplifying existing code — before touching a single line. Invoke this skill whenever the user says "refactor", "clean up", "modernize", "restructure", "simplify this", "decouple", "extract", "migrate to", or describes making code better without changing what it does. Also invoke when the user says "this code is a mess" or "rewrite this properly". Use this before any refactoring work, even if it seems small — small refactors are where silent regressions hide.
---

# Refactor Code

## Overview

Refactoring without a safety net introduces bugs that are harder to debug than the original mess. The code looked bad — now it's broken and looks different.

**Core principle:** Behavior must be provably identical before and after. Style changes are cheap; regressions are expensive.

**Violating the letter of this process is violating the spirit of refactoring.**

## The Iron Law

```
NO REFACTORING WITHOUT VERIFIED TEST COVERAGE FIRST
```

If you can't demonstrate the behavior is preserved, you haven't refactored — you've rewritten.

## When to Use

**Always:**
- Modernizing syntax or language features
- Extracting functions or modules
- Renaming for clarity
- Reducing duplication
- Decoupling components
- Performance-neutral restructuring

**Use this ESPECIALLY when:**
- "It's a small cleanup" (small = high confidence = skipping the process)
- Removing code that "looks unused"
- Migrating from one pattern to another
- Touching code with no existing tests

**Don't skip when:**
- You're confident nothing could break (confidence is not coverage)
- The tests are slow (slow tests are still tests)
- The scope seems tiny (regressions happen at the boundary)

## The Four Phases

Complete each phase before proceeding.

### Phase 1: Scope the Refactor

Before writing a single character of new code, understand what you're touching and what depends on it.

1. **Identify the target and gate on behavior preservation**
   - What code is being refactored? Files, modules, functions?
   - What is the stated goal? (modernize, simplify, decouple, extract, rename)
   - Write one sentence: "I am refactoring X to achieve Y"
   - **Answer explicitly: will the externally observable behavior be identical before and after?**
     - If yes → proceed as a refactor
     - If no, or uncertain → **STOP.** This is a feature change, not a refactor. Surface the behavioral difference to the user before touching any code. Track it separately from the refactor.
   - Watch for: layout changes, ARIA role changes, URL structure changes, event emission changes, error message changes, prop interface changes — these are behavior, not style

2. **Map references and dependencies**
   - What calls this code? (callers, importers, consumers)
   - What does this code call? (dependencies it relies on)
   - Are there indirect users — configs, serialized state, external APIs?
   - Use `grep`, language server "find references", or IDE tooling — don't rely on memory

3. **Assess blast radius**
   - How many files touch this code?
   - Are there callers outside this repo (published APIs, consumers you can't control)?
   - Is there serialized state (database columns, JSON keys, env var names) tied to identifiers?
   - Blast radius determines required caution level:
     - **Private internal function**: lower caution, easier rollback
     - **Public API / exported symbol**: high caution, backward compatibility required
     - **Serialized identifiers**: maximum caution, migration plan needed

4. **Plan the increments**
   - Break the refactor into atomic steps, each independently testable
   - Resist the urge to "clean everything up while I'm here" — scope creep is how regressions hide

### Phase 2: Verify Test Coverage Before Touching Anything

You need a green baseline to return to. If it doesn't exist, create it first.

1. **Run the existing test suite**
   - All relevant tests should pass before you change anything
   - If tests fail *before* your changes, stop — you've inherited broken state, not a refactoring task

2. **Assess coverage of the target code**
   - Do the tests exercise the specific behavior of what you're refactoring?
   - Tests that exist but don't cover your target provide false confidence
   - Check: would a test fail if you deleted the function body? If not, the coverage is cosmetic

3. **Write missing coverage before proceeding**
   - Characterization tests are acceptable: write tests that document current behavior (even if behavior is wrong)
   - Use the `superpowers:test-driven-development` skill for writing good failing tests
   - Your goal: a green test suite that will *actually fail* if behavior changes

4. **Commit the green baseline**
   - Commit the tests as a separate commit before any refactoring begins
   - Label it clearly: `test: characterize behavior before refactor of X`
   - This commit is your rollback point if anything goes wrong

### Phase 3: Apply Changes in Atomic Increments

Refactor in the smallest steps that are independently verifiable.

1. **One transformation at a time**
   - Extract one function. Rename one variable. Move one module.
   - Do not combine multiple semantic changes in a single step
   - The smaller the step, the easier it is to identify what broke when tests fail

2. **Run tests after every step**
   - Not at the end — after each individual change
   - A failing test immediately after a single change points directly to the cause
   - A failing test after 20 combined changes requires archaeology

3. **Check backward compatibility at the blast radius boundary**
   - If callers outside your refactor scope exist: do they still work without changes?
   - If you're renaming a public symbol: add a deprecation alias rather than a hard rename
   - If you're changing a function signature: update all callers atomically in the same commit

4. **Commit each atomic step**
   - Small, passing commits create a bisectable history
   - Format: `refactor: extract validateEmail() from submitForm()`
   - If you can't describe the commit in one line, the step is too large

5. **Stop if tests break and you don't know why**
   - Do not continue refactoring when tests are red
   - Do not "fix the test to match the new behavior" unless the test was wrong
   - Revert the last step, understand why it failed, try a different approach
   - If you can't keep tests green, the refactor plan needs revision

### Phase 4: Verify Behavior Equivalence

"Tests pass" is necessary but not sufficient. Verify that nothing regressed at the boundaries.

1. **Confirm the original stated goal was achieved**
   - You said you were refactoring X to achieve Y — is Y achieved?
   - Don't accept "roughly similar" — the refactor succeeded or it didn't

2. **Check boundary behavior**
   - Run integration tests or end-to-end tests if available
   - Manually exercise the primary user-facing flows that touch the refactored code
   - Pay attention to edge cases: empty inputs, error paths, concurrent usage

3. **Verify no silent behavioral changes**
   - Watch for: changed exception types, changed return value shapes, changed log output, changed side effects
   - These don't always break tests but do break callers
   - Compare before/after behavior at the API boundary, not just internally

4. **Check for performance changes**
   - Refactors that change algorithmic complexity can slow production unexpectedly
   - If the refactor touches a hot path, benchmark before and after

5. **Review the diff with fresh eyes**
   - Read the final diff as if reviewing someone else's PR
   - Does each change make sense? Is there anything you didn't intend to change?
   - Accidental whitespace changes, re-ordered imports, or subtle logic changes hide in large diffs

## Red Flags — STOP and Return to Phase 1

If you catch yourself thinking:

- "Tests don't cover this but I know what it does"
- "I'll add tests after the refactor to verify it works"
- "Just renaming — can't break anything"
- "The tests are slow, I'll run them at the end"
- "I'll clean up a few other things while I'm here"
- "The old behavior was wrong anyway, this is better"
- "I'll check backward compatibility after merging"
- Combining refactor + feature in the same commit
- Editing test assertions to match new behavior instead of reverting code
- Proceeding with "migrate layout/structure" without answering whether external behavior is identical

**These all mean: STOP. Return to Phase 1 or Phase 2.**

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "I know this code, I don't need tests" | Knowledge decays. New code has new behavior. Tests are proof, not comfort. |
| "It's just a rename" | Renames break serialization, reflection, external configs, log parsers, documentation. |
| "Tests after the refactor verify the same thing" | Tests after pass by definition — you wrote the code they're testing. Tests before catch regressions. |
| "The old behavior was wrong, new is correct" | That's a feature change, not a refactor. Track it separately. |
| "Backward compat can break — callers should update" | True for major versions. Surprise breakage in minor changes destroys trust. |
| "I'll clean everything up at once" | Scope creep. Each "while I'm here" multiplies blast radius. |
| "No one calls this code" | `grep` it. You'll find callers. |
| "The tests pass, I'm done" | Tests pass ≠ behavior preserved. Check boundaries. |

## Quick Reference

| Phase | Key Activity | Gate to Pass |
|-------|-------------|--------------|
| **1. Scope** | Map refs, assess blast radius, plan increments | One-sentence goal + reference list |
| **2. Coverage** | Run tests, assess coverage, add missing tests, commit green baseline | Green suite that would fail if code deleted |
| **3. Apply** | One transformation at a time, test after each step, commit atomically | All tests green at every step |
| **4. Verify** | Confirm goal achieved, check boundaries, review diff | Behavior provably identical |

## Refactor Goals Reference

When the user names a goal, apply these specific checks:

| Goal | Extra Checks |
|------|-------------|
| **Modernize syntax** | New syntax must have the same runtime semantics (e.g., `var` → `const/let` scoping) |
| **Extract function** | Verify extracted function handles all code paths the original did |
| **Decouple / DI** | Verify all injection points are covered; circular dependencies don't move, they hide |
| **Rename** | Check serialized state, configs, log parsers, external documentation |
| **Reduce duplication** | Shared abstraction must handle all cases it replaces — test each original call site |
| **Migrate pattern** | Run both old and new in parallel during migration; remove old only after new is verified |

## Related Skills

- **superpowers:test-driven-development** — Writing coverage before refactoring (Phase 2)
- **superpowers:systematic-debugging** — When refactor breaks something and you need root cause
- **superpowers:verification-before-completion** — Final gate before declaring the refactor done

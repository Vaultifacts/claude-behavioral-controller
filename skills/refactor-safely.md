---
name: refactor-safely
description: Use when refactoring, restructuring, renaming, simplifying, or cleaning up existing code — before touching a single line.
---

**Iron rule:** Do NOT write any refactored code until Step 3 (characterization tests) is complete. A refactor that changes behavior is a bug, not a cleanup.

---

## Step 1 — Read and document current behavior

Before touching any code, read the target function/module and record:

- What does it do? One sentence of observable behavior per public function.
- What are its inputs and outputs?
- What are the edge cases? Look for: conditional branches, boundary values, null/undefined inputs, error paths, and any comments that describe non-obvious behavior.
- What are the callers? Grep for all call sites — the refactor must not change the public interface.

Record every branch and edge case. Do not rely on the function's name or comments to infer behavior — read the code.

If any behavior is unclear from reading (e.g., "this comment says handled elsewhere — what does that mean?"), ask before proceeding.

---

## Step 2 — Identify what "clean" means for this specific request

Refactoring requests are often underspecified. Before writing code, answer:

- What specific problem is being addressed? (long function / duplication / unclear naming / complex conditionals)
- What is the minimum change that addresses it?
- What is explicitly NOT being asked for? (new abstractions, architecture changes, behavior changes)

State: "Scope of refactor: [specific changes]. Out of scope: [list of things that would be tempting but are not asked for]."

If the request is vague ("make it cleaner"), ask: "Are you looking to: (a) simplify the control flow, (b) extract named constants, (c) reduce duplication, or (d) something else?"

---

## Step 3 — Write characterization tests (GATE)

Before refactoring, write tests that capture current behavior — including any bugs. These tests define "behavior preserved."

- Write one test per branch and per edge case identified in Step 1
- Include boundary values: the exact values where behavior changes (e.g., quantity === 10, quantity === 9, quantity === 50, quantity === 49)
- Do NOT write tests that assert what the code should do — write tests that assert what it currently does. If the current behavior is wrong, that is a separate task. Refactoring and bug-fixing are separate commits.
- Run the tests before refactoring. They must all pass before proceeding.

State: "Characterization tests written: [N tests covering N branches]. All pass before refactor: yes."

If the codebase has no test infrastructure, state that explicitly and ask: "There is no test framework set up. Should I add tests anyway or proceed without them?" Do not silently skip.

---

## Step 4 — Implement the refactor

Apply only the changes identified in Step 2.

Enforcement rules:

1. **No behavior changes.** If the refactored code produces a different output for any input combination, it is not a refactor — it is a bug.
2. **No new features or fixes.** If you notice a bug during refactoring, note it and surface it to the user after the refactor is complete — do not fix it now. Mixing bug fixes with refactoring makes both harder to review.
3. **No scope creep.** Do not refactor adjacent code that was not in scope. Do not rename symbols that were not in scope. Do not restructure the module layout unless that was explicitly requested.
4. **No removing comments unless they are demonstrably wrong.** Comments that explain intent, cross-cutting concerns, or non-obvious behavior must be preserved or rewritten — not silently deleted.
5. **No new abstractions beyond what was asked.** A helper function is a new abstraction. A lookup table is a new abstraction. A shared constant is a new abstraction. These are fine if they are the specific thing being requested; they are out of scope if they were not.

---

## Step 5 — Run characterization tests

Run the same tests from Step 3.

- All tests must pass. If any fail, the refactor changed behavior — revert and fix.
- If a test fails: do not fix the test to match the new code. Fix the code to match the test. The test is the specification.

State: "[N tests pass / N-M tests fail — list failing cases]"

---

## Step 6 — Output the refactor summary

```
## Refactor Summary
- Target: [function/module name]
- Problem addressed: [specific issue from Step 2]
- Changes made: [bullet list of actual changes]
- Out of scope (not changed): [what was intentionally left alone]
- Characterization tests: [N written / N pass]
- Behavior changes: none / [describe if any — this is a red flag]
- Bugs noticed (not fixed): [list with locations — handle separately]
- Comments preserved: yes / no — [if no, explain]
```

---

## Rationalizations that fail

| Phrase | Why it fails |
|--------|-------------|
| "I'll just clean up a few other things while I'm here" | Scope creep makes the diff impossible to review. Refactoring and other changes belong in separate commits. |
| "The behavior is obviously the same" | "Obviously" is not a test. Characterization tests are. Write them first. |
| "There are no tests, so I'll skip that step" | No tests means no way to verify behavior is preserved. This is exactly when characterization tests are most important, not least. |
| "I fixed a bug while refactoring — it's better now" | It is also unreviewed, untracked, and mixed into a refactoring diff. Surface the bug separately. |
| "The comment was outdated/wrong — I removed it" | Comments can be updated; they should not be silently deleted. If a comment is wrong, note that in the refactor summary. |
| "I introduced a helper — it makes the code cleaner" | A new helper is a new abstraction. If it wasn't in the scope stated in Step 2, it is scope creep. |
| "The original code was clearly wrong here" | A refactor that 'corrects' behavior is a bug fix. Track it separately. |
| "I ran the tests and they pass" | Tests written after refactoring confirm what the code does, not that behavior was preserved. Write characterization tests before refactoring. |
| "The boundary values are obvious from the code" | Boundary values are where behavior changes. They are the exact cases that silent refactoring bugs affect. Test them explicitly. |

---
name: add-feature
description: Use when asked to add a new feature, implement a user story, build new functionality, or extend an existing capability — before writing any implementation code.
---

Do NOT write any implementation code until Step 4 (implementation contract) is complete.

Add feature: $ARGUMENTS

## Step 1 — Read existing patterns

Before writing anything, read the codebase to understand how similar features are built.

- Find one or two existing features that are closest in shape to what's being added
- Read the actual source files — do not infer patterns from file names or memory
- Identify: file organization, naming conventions, how state is managed, how the feature is wired into the application entry point
- Identify: which existing file or module this feature belongs in vs. whether a new file is warranted

If you cannot find any analogous feature in the codebase, state that explicitly before proceeding. Do not invent a pattern.

## Step 2 — Establish acceptance criteria

State the criteria that will determine when this feature is complete before writing any code.

- What does the feature do? One sentence of observable behavior.
- What are the inputs and outputs (or user actions and resulting states)?
- What are the edge cases that must be handled: empty state, missing data, concurrent use, invalid input?
- What does success look like in a test?

If any of these is ambiguous or absent, ask the user before proceeding. Do NOT invent acceptance criteria and proceed as if they were confirmed.

Acceptance criteria written here become the direct basis for Step 6 tests. Write them with enough precision that a test can be derived from each one.

## Step 3 — Extend vs. new file decision

Based on Step 1, decide explicitly: should this feature extend an existing file or create a new one?

- If an existing file handles the same concern (same domain, same layer, same module), extend it — do not create a new file
- If no existing file is the right home, state why a new file is necessary and what it will be named
- New file names must match the naming convention observed in Step 1

State the decision as: "Extending [file path]" or "Creating [file path] because [reason]." Do not proceed without stating this explicitly.

## Step 4 — Implementation contract

Before writing any implementation code, state the full contract for this feature:

> "Feature contract for [feature name]: Entry point — [function/component/route name]. Accepts — [inputs or props]. Returns or produces — [outputs or side effects]. Edge cases handled — [list from Step 2]. Lives in — [file path from Step 3]. Acceptance criteria satisfied — [list from Step 2]. Pattern matches — [file from Step 1]: yes."

If any part of this contract cannot be filled in without guessing, stop and resolve the gap before writing code.

This is the gate. Do NOT write implementation code before this statement is complete.

## Step 5 — Implement

Write the implementation according to the contract from Step 4.

Enforcement rules:

1. **No scope creep.** Implement only what the contract in Step 4 specifies. Do not add related improvements, cleanups, or enhancements that were not in the acceptance criteria.
2. **No "while I'm here" changes.** Do not refactor, rename, or restructure surrounding code. If you notice something worth fixing, note it in a comment or surface it to the user after this feature is complete — do not act on it now.
3. **No new abstractions unless specified.** Do not introduce helper utilities, base classes, shared hooks, or reusable modules that were not in the contract. If a new abstraction seems necessary, stop and ask — it may belong in a separate task.
4. **No adding error handling, comments, or docstrings beyond what is asked.** Follow the minimal-changes principle: fix what's asked, nothing more.
5. **No deviating from the pattern identified in Step 1.** If the implementation requires a different pattern than observed in the codebase, stop and surface the conflict — do not silently choose a different approach.

## Step 6 — Write tests

Tests are not optional. Each acceptance criterion from Step 2 must have at least one corresponding test.

- Map each criterion to a test case explicitly: "Criterion: [criterion text] → Test: [test description]"
- Include: happy path, edge cases from Step 2, and at least one failure/invalid-input case
- Match the exact test style, file naming convention, and import patterns observed in the codebase — do not introduce a new testing pattern
- Place tests in the correct location per project conventions
- Run the tests and confirm they pass before reporting completion

If generating tests is complex or the test surface is large, invoke the `generate-tests` skill with the acceptance criteria from Step 2 as input.

Do not skip or defer this step. A feature without tests is not complete.

## Step 7 — Verify

Confirm the feature is complete by checking every item in this list.

Output this block verbatim with values filled in:

```
## Feature Completion Checklist
- [ ] Existing patterns read: [file(s) read in Step 1]
- [ ] Acceptance criteria confirmed: [source — user-provided / inferred and confirmed]
- [ ] Extend vs. new decision stated: [extending <path> / created <path> — reason]
- [ ] Implementation contract completed before code written: [yes / no — if no, explain]
- [ ] Scope limited to contract: [yes / no — if no, list what was added outside contract]
- [ ] Tests written: [yes / no — if no, explain]
- [ ] Each acceptance criterion has a test: [yes — list / no — list gaps]
- [ ] Tests pass: [yes / no — if no, list failures]
- [ ] No unintended changes to surrounding code: [yes / no — if no, describe]
```

Do not abbreviate or skip lines. If any item is "no", state what is needed to resolve it before considering the feature done.

## Rationalizations

| Phrase | Why it fails |
|--------|-------------|
| "I know this codebase, I don't need to read the patterns" | Pattern knowledge decays and is often wrong for new areas of the codebase. Reading takes 30 seconds; undoing the wrong pattern takes hours. |
| "The acceptance criteria are obvious from the ticket title" | Ticket titles omit edge cases. Edge cases are where bugs ship. Write them out explicitly or ask. |
| "I'll add a new file — it keeps things clean" | A new file when an existing one is the right home fragments the codebase. Read Step 1 before deciding. |
| "I'll write the contract after — it's just documentation" | The contract is a gate, not documentation. Writing it after means you already guessed at a shape and implemented it. |
| "Just a quick addition — no need for a full contract" | Quick additions with no contract are how inconsistent APIs and wrong response shapes get shipped. The contract takes 2 minutes. |
| "I'll clean up a few things while I'm here" | Scope creep multiplies blast radius. Each unplanned change is an untested change. Surface it; handle it separately. |
| "Tests can wait — let's get the feature working first" | Tests written after passing implementation test what the code does, not what it should do. Write tests against the acceptance criteria, not the output. |
| "Edge cases are unlikely for this feature" | Edge cases are where bugs ship and where security vulnerabilities hide. They are the most important cases to test. |
| "This abstraction will be useful later" | YAGNI. An abstraction introduced speculatively adds complexity now and maintenance burden forever. If it's not in the contract, it's out of scope. |
| "The pattern I know from other projects is better" | The right pattern for this codebase is the one already in use. Introducing a foreign pattern creates inconsistency. Read Step 1 first. |

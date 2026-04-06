---
name: generate-tests
description: Use when asked to write tests, add test coverage, or generate a test file for a function or module. Not for planning TDD cycles or running existing tests.
---

**Iron rule**: Understand intended behavior before writing tests. Do NOT write assertions based solely on what the current implementation returns — test what the function SHOULD do.

Generate tests for: $ARGUMENTS

Follow these steps:

## Step 1 — Understand the target
- Read the file/function to understand its purpose — the function name, JSDoc/docstring, and calling context
- Find the specification: PR description, ticket, README section, or inline docs that states intended behavior
- If no spec exists and the function has edge cases with non-obvious expected results (e.g., negative values, overflow, empty input), ask before writing tests: *"What should `fn(x)` return for [edge case]?"*
- Do NOT infer expected behavior for edge cases solely from the implementation — the implementation may be buggy

2. **Study existing tests**:
   - Find existing test files (look for `*.test.ts`, `*.spec.ts`, `__tests__/`)
   - Match the exact testing style, import patterns, and describe/it structure

3. **Plan test cases** for each function:
   - Happy path (normal inputs → expected outputs)
   - Edge cases (empty, null, zero, max values)
   - Error cases (invalid input, network failure, missing data)
   - Boundary conditions
   - For each edge case with a non-obvious expected result: confirm the intended behavior before writing the assertion. Write `// TODO: confirm intended behavior` rather than asserting what the code currently returns.

4. **Write tests**:
   - Place in same directory with `.test.ts` suffix (or match existing convention)
   - Use mocks for external dependencies (API calls, DB, filesystem)
   - Each test: one clear assertion, descriptive name

5. **Run tests**: Execute the test command and fix any failures

6. **Report**: List each test case and its status (pass/fail)

Target coverage: all exported functions, minimum 3 test cases each.

## Shortcuts that don't apply

| Phrase | Why it fails |
|--------|-------------|
| "Just test what the function does" | A test that asserts buggy behavior passes forever and never catches the bug. |
| "The implementation is the spec" | If the implementation had a bug, you wouldn't know — you'd write a test documenting it. |
| "I'll ask for the spec later" | Write a TODO comment on the ambiguous assertion. Do not write a passing assertion for unknown intended behavior. |
| "Edge cases are unlikely" | Edge cases are where bugs live. They are the most important tests. |

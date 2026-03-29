---
name: generate-tests
description: Generate comprehensive tests for a file or function. Analyzes existing test patterns in the project and writes matching-style tests with good coverage.
---

Generate tests for: $ARGUMENTS

Follow these steps:

1. **Understand the target**:
   - Read the file/function specified: `$ARGUMENTS`
   - Identify all exported functions, their inputs, outputs, and edge cases

2. **Study existing tests**:
   - Find existing test files (look for `*.test.ts`, `*.spec.ts`, `__tests__/`)
   - Match the exact testing style, import patterns, and describe/it structure

3. **Plan test cases** for each function:
   - Happy path (normal inputs → expected outputs)
   - Edge cases (empty, null, zero, max values)
   - Error cases (invalid input, network failure, missing data)
   - Boundary conditions

4. **Write tests**:
   - Place in same directory with `.test.ts` suffix (or match existing convention)
   - Use mocks for external dependencies (API calls, DB, filesystem)
   - Each test: one clear assertion, descriptive name

5. **Run tests**: Execute the test command and fix any failures

6. **Report**: List each test case and its status (pass/fail)

Target coverage: all exported functions, minimum 3 test cases each.

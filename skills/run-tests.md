---
name: run-tests
description: Use when tests are failing, after writing code that needs verification, or when asked to make tests pass or get tests green. Not for writing new tests (use generate-tests) or TDD planning.
---

Run the test suite and fix any failures for: $ARGUMENTS

## Step 1 — Detect the test command

Check in this order:
1. `package.json` → `scripts.test` (Node/TS projects)
2. `pytest` / `python -m pytest` (Python projects — check for `pytest.ini`, `pyproject.toml`, or `setup.cfg`)
3. `cargo test` (Rust — check for `Cargo.toml`)
4. `go test ./...` (Go — check for `go.mod`)
5. `dotnet test` (.NET — check for `*.csproj`)

If `$ARGUMENTS` specifies a file or test name, scope the command to that target only.

## Step 2 — Run the tests

Execute the test command. Capture full output including:
- Number of tests run / passed / failed / skipped
- Full error messages and stack traces for each failure
- File:line references

Set `PYTHONIOENCODING=utf-8` for Python. Use `--no-coverage` or equivalent to skip coverage reports unless they're already fast.

## Step 3 — If all pass

Report: `✓ All tests passing ([N] tests)`. Done.

## Step 4 — Triage failures

For each failing test, determine the failure type:

| Type | Signal | Action |
|------|--------|--------|
| **Implementation bug** | Test logic is correct, code is wrong | Fix the implementation |
| **Test is stale** | Test references old API/signature | Update the test |
| **Missing mock/fixture** | Import error, missing dependency | Add mock or setup |
| **Environment issue** | DB not running, env var missing | Report to user, do not fix |
| **Flaky test** | Non-deterministic (timing, network) | Note it, skip for now |

Do not fix tests just to silence them — if a test is catching a real bug, fix the bug.

## Step 5 — Fix failures (max 3 iterations)

For each failure:
1. Read the failing test to understand what it expects
2. Read the implementation it's testing
3. Make the minimal fix (implementation or test, per Step 4 triage)
4. Do not touch passing tests

After fixing, re-run the test suite. Repeat up to 3 times total.

If still failing after 3 iterations: stop, report what's failing and why, and ask the user how to proceed. Do not loop indefinitely.

## Step 6 — Report

```
## Test Results

**Before:** [N passed / M failed]
**After:**  [N passed / 0 failed]

### Fixed
- `test_foo` — [what was wrong and what was changed]
- `test_bar` — [what was wrong and what was changed]

### Still failing (if any)
- `test_baz` — [root cause, why not auto-fixed]

### Skipped (flaky/environment)
- `test_env_check` — [reason]
```

---
name: performance-fix
description: Use when a performance bottleneck has been identified and you are about to apply a fix — before touching any code. Not for profiling or finding bottlenecks (use perf-profile for that).
---

Measure before touching code. Do NOT apply any optimization until Step 2 (baseline measurement) is recorded.

## Step 1 — Confirm the bottleneck is measured

There must be a number: ms, KB, req/s, query time, bundle size — something concrete. "Feels slow" is not a bottleneck. "The code looks like O(n²)" is not a measurement.

If there is no measured value, do not proceed. Go back to `perf-profile` and produce one.

## Step 2 — Record the baseline

Write it down before touching any code:

```
Baseline: [value] ([tool used], [dataset size / load level / environment])
```

Example: `Baseline: 1,840ms (Lighthouse cold load, prod dataset, staging env)`

This is the number you will compare against in Step 7. Without it, you cannot claim the fix worked — only that the code changed.

## Step 3 — Identify ONE change

The single smallest change that could address this specific bottleneck. Not a list of improvements. One.

If multiple optimizations are obvious, pick the highest-impact one and write the rest down as deferred. They are not part of this fix.

## Step 4 — Assess regression risk

Before writing any code, answer these:

- What does this code path do besides the hot operation being optimized?
- Are there callers that depend on exact execution order, timing, or side effects?
- Does the optimization trade memory for speed (or vice versa) in a way that affects other constraints?
- Is this on a path with error handling or fallback logic that could be silently skipped?

If any answer raises a concern, note it explicitly before proceeding.

## Step 5 — Apply the single change

Minimal diff. No cleanup, no "while I'm here" refactoring, no additional optimizations in the same commit.

After writing the change, review the diff. If it touches more than the targeted operation, cut the scope.

## Step 6 — Re-measure using identical conditions

Same tool, same dataset size, same environment as Step 2. Apples-to-apples.

If conditions have changed (different machine, dataset, load), note the change and explain why the comparison is still valid — or re-establish the baseline under the new conditions first.

## Step 7 — Compare

- Did the metric improve? By how much?
- If improvement is less than 10%, it may be within measurement noise — re-run to confirm
- If it regressed: revert immediately. Do not attempt a second fix on top of a regression.

Do NOT state a performance improvement without a measured before/after delta. "Should be faster" and "obviously faster" are not results.

## Step 8 — Run the test suite

Full test suite, not just the tests for the changed code. Performance fixes break logic in non-obvious ways: memoization that caches incorrect results, batch operations that skip edge cases, ordering assumptions that resolve differently under the new implementation.

If tests fail: revert the change and return to Step 3 with the failure as a constraint.

After Step 8, output this block:

```
## Performance Fix Summary
- Bottleneck: [what was slow, file:line]
- Baseline: [value] ([tool], [conditions])
- Fix applied: [one-sentence description]
- After: [value] ([same tool, same conditions])
- Delta: [+/- X%]
- Regression check: [N tests passed]
```

## Shortcuts that don't apply

| Phrase | Why it fails |
|--------|-------------|
| "It's obviously faster" | Obvious optimizations sometimes regress. The Step 2 baseline is what proves it. |
| "I'll optimize a few things at once" | One change at a time. You cannot isolate what helped or what broke with multiple changes in flight. |
| "The demo is in 10 minutes" | One change, measured. An unmeasured fix can regress the demo worse than the original slowness. |
| "The profile is enough proof" | Profile shows potential. Step 7 measurement confirms actual improvement. |
| "Tests pass so I'm done" | That satisfies Step 8 only. Did you record the before/after delta in Step 7? |
| "The optimization is safe, no need to test" | Performance fixes change execution order, caching, and side effects. Run the suite. |
| "I don't need a baseline, the fix is clear" | No baseline means no proof. A claimed improvement without measurement is an assumption. |
| "Let me also fix these other slow paths while I'm here" | Defer them. One change at a time. |

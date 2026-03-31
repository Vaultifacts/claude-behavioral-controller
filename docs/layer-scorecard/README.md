# Quality Gate Layer Scorecard — Standards & Framework
Created: 2026-03-30 | Owner: Matt1

## Purpose

This scorecard is the single source of truth for the health, completeness, correctness, and effectiveness of every layer in the Quality Gate Monitor system. Every score is backed by verifiable evidence. No assumptions. No guesses. No "it probably works."

## Philosophy

A score of 10/10 does not mean "we did everything we thought to do." It means "we tried to break it and couldn't, we measured it and it performs, and we can prove it with evidence." The bar is set by what would be required for the system to be truly bulletproof — not by what we've accomplished so far.

---

## Hierarchy

```
System (Quality Gate Monitor)
  Layer (e.g., Layer 2 — Mid-task Monitoring)
    Section (e.g., LOOP_DETECTED)
      Category (e.g., Threshold Logic)
        Sub-category (e.g., Unit test for reset behavior)
          ... (as deep as needed)
```

Every node in this tree that can be meaningfully evaluated gets its own score. Parent scores are calculated from their children — never assigned directly. If a parent shows 7/10, you can drill down to find exactly which children are dragging it down.

---

## Score Calculation

**Leaf nodes** (the deepest level for any branch) are scored 0–10 directly with evidence.

**Parent nodes** are the **weighted average** of their children, rounded to 1 decimal place. Weights default to equal unless explicitly noted. A parent score is never manually assigned — it always derives from its children.

**Layer overall score** = average of its top-level sections.

---

## Scoring Rubric (applies to all leaf nodes)

| Score | Meaning | Evidence required |
|-------|---------|-------------------|
| 10 | Bulletproof — verified correct, adversarially tested, no conceivable failure | Test name + adversarial case + live data |
| 9 | Verified correct, tested, one minor edge case untested | Test name + evidence of what's missing |
| 8 | All critical paths tested, some edge cases untested | Test names covering critical paths |
| 7 | Main behavior tested, notable gaps in edge cases | Test name + list of untested edges |
| 6 | Partially tested, critical paths covered but not thoroughly | Test name + gap description |
| 5 | Implemented and appears to work, but testing is shallow | Implementation evidence + gap description |
| 4 | Implemented but barely tested or test quality is poor | Implementation exists, tests weak |
| 3 | Implemented but untested — correctness is assumed | Code exists, no verification |
| 2 | Partially implemented or tests exist but don't pass | Specific gap description |
| 1 | Stub, placeholder, or fundamentally broken | What exists and what's wrong |
| 0 | Does not exist / never fires / no evidence of function | Absence confirmed |

---

## What 10/10 Actually Requires (per dimension)

### Implementation
- Every behavior described in the docstring/spec is implemented
- Every edge case that can be reasoned about is handled
- Deliberate attempts to break it have failed
- Code has been read and verified, not just assumed from test results

### Unit Tests
- `pytest-cov` reports 100% branch coverage on the layer file
- Tests exist for adversarial inputs (designed to slip past detection)
- Tests exist for boundary conditions (off-by-one, empty input, malformed data)
- Tests verify both positive cases (should detect) and negative cases (should not detect)
- Each test is correct (tests what it claims to test, assertions are meaningful)

### Smoke Tests
- Every behavioral outcome (block/pass/log/skip/warn) has a dedicated smoke test
- At least one adversarial case per detection rule
- Smoke tests exercise the full hook pipeline, not just the function

### Live Effectiveness
- Minimum 30 days of log data with the layer active
- Layer fires on real violations in production (not just synthetic/test events)
- False negative rate measured and below 5% (via shadow analysis or manual review)
- False positive rate measured and below 10%
- Events from multiple distinct sessions confirm consistent behavior

### Known Gaps
- A formal gap analysis has been performed (not just "we haven't found problems")
- Every identified gap is either: fixed, or documented with explicit acceptance rationale
- Adversarial thinking applied: "what could slip past this?" answered and tested
- No open "unknown unknowns" — the boundaries of what the layer can and cannot detect are documented

### Integration
- Confirmed wired in settings.json at the correct event with correct matcher
- Timeout value is appropriate (not too short to complete, not so long it blocks)
- async flag is correct for the layer's role (blocking layers are sync, logging layers are async)
- Failure mode tested: what happens when the script crashes? Does it block Claude or fail silently?
- No conflicting hooks that could interfere with this layer's operation

---

## Justification Format (mandatory for scores under 10)

```
Score: 6/10
Evidence: [specific test name, grep output, log count, or code reference]
Missing: [specific thing that is not covered]
To reach 10: [concrete action — not "improve tests" but "add test for empty input case in TestX"]
```

For scores of 10:
```
Score: 10/10
Evidence: [proof — test name, pytest-cov line, log grep, adversarial test name]
Adversarial: [what was tried to break it and why it didn't break]
```

---

## File Structure

```
layer-scorecard/
  README.md              <- this file (standards, locked in)
  INDEX.md               <- all layers at a glance, derived scores only
  layer-0.md             <- full scorecard for Layer 0
  layer-env.md           <- full scorecard for Layer ENV
  layer-1.md             <- full scorecard for Layer 1 (in quality-gate.py)
  layer-1.5.md           <- etc.
  ...
  quality-gate-main.md   <- the Stop hook evaluator (quality-gate.py overall)
  precheck.md            <- precheck-hook.py
```

---

## How to Update

1. Read the layer file
2. Read the corresponding test classes
3. Run `pytest-cov` for that specific file
4. Grep the live log for that layer's events
5. Score each leaf node with evidence
6. Let parent scores calculate automatically
7. Update INDEX.md with new top-level scores

Never update a score without re-verifying the evidence. Stale scores are worse than no scores.

---

## Baseline Data (collected 2026-03-30)

### pytest-cov branch coverage (from test_qg_layers.py)
| File | Stmts | Miss | Coverage |
|------|-------|------|----------|
| quality-gate.py | 805 | 733 | **9%** |
| precheck-hook.py | 122 | 60 | **51%** |
| qg_layer0.py | 90 | 41 | **54%** |
| qg_layer2.py | 107 | 8 | **93%** |
| qg_layer5.py | 106 | 29 | **73%** |
| qg_layer6.py | 82 | 20 | **76%** |
| qg_layer7.py | 79 | 61 | **23%** |
| qg_layer8.py | 55 | 8 | **85%** |
| qg_layer9.py | 63 | 36 | **43%** |
| qg_layer10.py | 71 | 9 | **87%** |
| qg_layer15.py | 89 | 16 | **82%** |
| qg_layer17.py | 76 | 36 | **53%** |
| qg_layer18.py | 148 | 54 | **64%** |
| qg_layer19.py | 81 | 24 | **70%** |
| qg_layer25.py | 68 | 13 | **81%** |
| qg_layer26.py | 80 | 11 | **86%** |
| qg_layer27.py | 42 | 21 | **50%** |
| qg_layer35.py | 82 | 30 | **63%** |
| qg_layer45.py | 71 | 12 | **83%** |
| qg_layer_env.py | 91 | 33 | **64%** |

### Live events (qg-monitor.jsonl, 2204 total events)
| Layer | Events | Note |
|-------|--------|------|
| layer0 | 115 | Session start context |
| layer2 | 1932 | 87.6% of all events |
| layer5 | 101 | Subagent coordination |
| layer8 | 10 | Regression detection |
| layer17 | 10 | Intent verification |
| layer25 | 1 | Output validation |
| layer26 | 36 | Consistency |
| All others | 0 | **Never fired in production** |

### Quality Gate Stop hook (quality-gate.log, 602 decisions)
| Decision | Count |
|----------|-------|
| PASS | 443 |
| BLOCK | 147 |
| DEGRADED-PASS | 12 |

### Unit tests per layer
| Layer | Test classes | Test methods |
|-------|-------------|--------------|
| Layer 0 | 1 | 7 |
| Layer ENV | 2 | 12 |
| Layer 1 (Pivot+Deep) | 4 | 9 |
| Layer 1.5 | 3 | 15 |
| Layer 1.7 | 3 | 13 |
| Layer 1.8 | 3 | 13 |
| Layer 1.9 | 2 | 11 |
| Layer 2 | 2 | 25 |
| Layer 2.5 | 2 | 9 |
| Layer 2.6 | 2 | 9 |
| Layer 2.7 | 1 | 2 |
| Layer 3.5 | 2 | 13 |
| Layer 4.5 | 3 | 10 |
| Layer 5 | 3 | 13 |
| Layer 6 | 2 | 10 |
| Layer 7 | 2 | 7 |
| Layer 8 | 2 | 9 |
| Layer 9 | 2 | 10 |
| Layer 10 | 2 | 8 |
| Precheck | 3 | 10 |
| Session State | 1 | 14 |
| Notification Router | 1 | 15 |

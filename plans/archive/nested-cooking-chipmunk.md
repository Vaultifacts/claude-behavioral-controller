# Plan: Test 102 — Completeness Score Extremes Freeze

## Status
Test 101 (Multi-input Duplicate Count Freeze) is already implemented and passing.
Current suite: **101 tests green**.

## Context

Continuing spec-freeze hardening of the Autonomous Architecture Auditor.
`completeness_score` is a `[0, 1]` float in `summary`. Tests 87–93 froze int/float
equivalence, negative zero, and version bumps — but the boundary values `0.0` and `1.0`
for `completeness_score` have never been frozen. This test freezes whether the extremes
(`0.0` vs `1.0`) produce DISTINCT keys and hashes, confirming that this scalar is fully
content-sensitive at the boundaries of its declared range.

## File to Modify

- `C:\Users\Matt1\OneDrive\Desktop\Autonomous-Architecture-Auditor\validation.py`

## Design

Two reports identical except `summary["completeness_score"]`:
- `report_zero`: `completeness_score = 0.0`
- `report_one`:  `completeness_score = 1.0`

**Vacuity guards:**
- `report_zero != report_one` (Python inequality)
- `json.dumps` differ (serialization confirmation)
- `0.0 != 1.0` and `1.0 - 0.0 == 1.0` (numeric distinctness)

**Execution:** Standard two-variant, two-build-each pattern.

**Assertions (two branches, freeze whichever applies):**
- Case A) one variant fails: deterministic failure freeze (same exc type).
- Case B) both succeed:
  - Within-variant determinism for each (`project_key`, `run_key`, `output_hash?`, `structural_signature?`).
  - Cross-variant self-consistent freeze (if equal assert equal, if distinct assert distinct).

## Implementation

### 1. Add function immediately above `run_all_validations`

Function name: `run_completeness_score_extremes_freeze_test`
`tempfile` prefix: `"cs_extremes_test_"`

Report template (only `completeness_score` varies):
```python
{
    "schema_version": "1.0.0",
    "engine_metadata": {"engine_version": "1.0.0"},
    "summary": {
        "overall_health_score": 72.0,
        "risk_score": 4.5,
        "completeness_score": <0.0 or 1.0>,
        "critical_issues": 0,
        "major_issues": 1,
        "minor_issues": 2,
        "strengths_count": 3,
        "gaps_count": 3,
        "recommendation_summary": "ok",
    },
    "execution_roadmap": [],
    "scenario_simulation": [],
}
```

Vacuity guards:
```python
reports_differ  = (report_zero != report_one)
json_differ     = (json.dumps(report_zero, ...) != json.dumps(report_one, ...))
numeric_differ  = (0.0 != 1.0) and (1.0 - 0.0 == 1.0)
setup_ok = reports_differ and json_differ and numeric_differ
```

Extraction helper (identical to neighboring tests):
```python
def _build_and_extract(path, report):
    pf = build_portfolio([(path, report)])
    assert len(pf["portfolio_inputs"]) == 1
    e = pf["portfolio_inputs"][0]
    return (e["project_key"], e["run_key"],
            pf.get("output_hash"), pf.get("structural_signature"))
```

Standard two-build-each execution and Case A / Case B branching — matching the
pattern of `run_execution_roadmap_step_content_freeze_test` (Test 96) exactly.

Verbose output labels: `"completeness_score=0.0 variant"`, `"completeness_score=1.0 variant"`.

### 2. Register in `run_all_validations` after Test 101 block

```python
    # Test 102: Completeness score extremes freeze (0.0 vs 1.0)
    print("Test 102: Completeness Score Extremes Freeze (0.0 vs 1.0)")
    passed, details = run_completeness_score_extremes_freeze_test(verbose=verbose)
    if not passed:
        all_passed = False
        print(f"  FAILED: {details}")
    print()
```

## Verification

```
PYTHONIOENCODING=utf-8 python validation.py
```

Expected: `ALL VALIDATION TESTS PASSED` (102 tests green).

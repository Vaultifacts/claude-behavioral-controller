# Layer 17 -- Adversarial Self-Testing
**File:** qg_layer17_adv.py (154 LOC) | **Hook:** SessionStart (daily) | **Cov:** 0%* | **Events:** 1 | **Tests:** 0*

*This layer IS the test runner. It tests other layers directly.

## 1. Test Suites (7/10)
4 suites testing Layers 2.8, 11, 12, 29 with 16 adversarial cases. Missing: suites for Layers 13-20.

## 2. Scheduling (9/10)
Runs once per day (86400s interval).

## 3. Reporting (8/10)
Pass/fail/skip per suite, blind spot identification, JSON output.

## 4. Effectiveness (5/10)
1 event. Needs daily runs to validate.

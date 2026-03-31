# Layer 18 -- A/B Rule Testing
**File:** qg_layer18_ab.py (182 LOC) | **Hook:** SessionStart + CLI | **Cov:** 66% | **Events:** 1 | **Tests:** 12

## 1. Rule Evaluation (7/10)
Counts fire/suppress by severity. Simplified model -- metadata comparison, not actual re-evaluation.

## 2. Comparison (7/10)
Delta-based recommendation. No statistical significance testing.

## 3. CLI Mode (8/10)
Accepts proposed_rules.json, outputs comparison JSON.

## 4. Coverage Gap (6/10)
66% -- main() hook mode untested.

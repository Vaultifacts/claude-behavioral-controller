# Layer 2.9 -- Semantic Correctness Verification
**File:** qg_layer29.py (175 LOC) | **Hook:** Stop | **Cov:** 44% | **Events:** 0 | **Tests:** 30

## 1. Claim-Action Matching (8/10)
6 claim patterns (error handling, type hints, logging, tests, validation, docstrings). Missing: refactoring/optimization claims.

## 2. Direction Checking (7/10)
3 patterns (descending, ascending, case-insensitive). Missing: newest-first, alphabetical.

## 3. Count Verification (7/10)
Extracts N tests/functions claims, counts actual. Tolerates off-by-1. Missing: endpoint/class counting.

## 4. Coverage Gap (4/10)
44% -- transcript parsing and main() untested.

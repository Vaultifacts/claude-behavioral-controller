# Layer 15m -- Memory and State Integrity
**File:** qg_layer15_mem.py (172 LOC) | **Hook:** SessionStart | **Cov:** 67% | **Events:** 0 | **Tests:** 14

## 1. Reference Checking (8/10)
Parses MEMORY.md links, resolves paths, verifies existence.

## 2. Staleness Detection (9/10)
14-day threshold on file mtime. Reports age.

## 3. Size and Duplicates (8/10)
100KB limit. Duplicate heading detection across files.

## 4. Coverage Gap (6/10)
67% -- main() untested.

# Layer 19 -- Cross-Project Learning
**File:** qg_layer19_cross.py (189 LOC) | **Hook:** SessionStart | **Cov:** 74% | **Events:** 5 | **Tests:** 17

## 1. Project Grouping (9/10)
Normalizes working_dir to project name. Groups events by project.

## 2. Cross-Project Patterns (8/10)
Finds categories in 2+ projects with 3+ events. No project-size weighting.

## 3. Project-Specific Patterns (8/10)
Finds categories unique to one project.

## 4. Coverage Gap (7/10)
74% -- main() untested but core functions well tested.

## 5. Effectiveness (6/10)
5 events. Actively detecting patterns across 5 projects.

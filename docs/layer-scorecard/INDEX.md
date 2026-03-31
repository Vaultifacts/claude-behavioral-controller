# Quality Gate Layer Scorecard — Index
Last updated: 2026-03-30
Standards: [README.md](README.md)

---

## System-Level Summary

| Metric | Baseline (2026-03-30) | Current (2026-03-30) | Change |
|--------|----------------------|---------------------|--------|
| Total unit tests | 402 | **455** | +53 |
| Total smoke tests | 583 | **585** | +2 |
| Total live events | 2,885 | **~3,600** | +715 |
| quality-gate.py coverage | **83%** | 83% | — |
| Layers with monitor events | 15 of 20 | **16 of 23** | +1 new layer |
| Bugs fixed (cumulative) | 2 | 2 | — |
| Layers deployed | 20 | **23** | +3 (2.8, 20, 11) |

---

## New This Session

### Layer 2.8 — Security Vulnerability Detection (DEPLOYED)
- `qg_layer28.py` (157 LOC) — PostToolUse on Write/Edit
- 18 unit tests, 63% coverage, 16 live events
- Scorecard: [layer-2.8.md](layer-2.8.md)

### Layer 20 — System Health Dashboard (DEPLOYED)
- `qg_layer20.py` (299 LOC) — SessionStart
- 25 unit tests, 79% coverage, 3 live events
- Scorecard: [layer-20.md](layer-20.md)

### Layer 11 — Commit Quality Gate (DEPLOYED)
- `qg_layer11.py` (205 LOC) — PreToolUse on Bash (git commit/push)
- 28 unit tests, validates conventional commits, blocks secrets/dangerous files
- Scorecard: pending

---

## Layer Scores at a Glance

| Layer | File | pytest-cov | Live Events | Tests | Top Weakness |
|-------|------|-----------|-------------|-------|-------------|
| [Layer 0](layer-0.md) | qg_layer0.py | 54% | 169 | 7 | UUID matching may target wrong session |
| [Layer ENV](layer-env.md) | qg_layer_env.py | 59% | logging | 12 | Test baseline capture untested |
| [Layer 1/3/4](quality-gate-main.md) | quality-gate.py | **83%** | 0* | **101** | Remaining 17%: edge branches in transcript parsing |
| [Layer 1.5](layer-1.5.md) | qg_layer15.py | 82% | 93 | 15 | Override token untested |
| [Layer 1.7](layer-1.7.md) | qg_layer17.py | 54% | 10 | 13 | Uncertainty regex overlap |
| [Layer 1.8](layer-1.8.md) | qg_layer18.py | 64% | 36 | 13 | Function check uses substring match (FP risk) |
| [Layer 1.9](layer-1.9.md) | qg_layer19.py | 63% | 34 | 11 | grep regex too broad for import matching |
| [Layer 2](layer-2.md) | qg_layer2.py | **93%** | **2131** | **25** | Path normalization added |
| [Layer 2.5](layer-2.5.md) | qg_layer25.py | 81% | 2 | 9 | YAML validation silently skipped if pyyaml missing |
| [Layer 2.6](layer-2.6.md) | qg_layer26.py | 86% | 36 | 9 | Mixed-import files produce no baseline |
| [Layer 2.7](layer-2.7.md) | qg_layer27.py | **92%** | 12 | **17** | os.walk no depth limit |
| [Layer **2.8**](layer-2.8.md) | qg_layer28.py | 63% | **16** | **18** | **NEW** — main() untested |
| [Layer 3.5](layer-3.5.md) | qg_layer35.py | 64% | 55 | 13 | introduces_new_problem now consumed |
| [Layer 4.5](layer-4.5.md) | qg_layer45.py | 83% | 134 | 10 | Hash only covers 5/16 preserved keys |
| [Layer 5](layer-5.md) | qg_layer5.py | 73% | 111 | 13 | ID correlation breaks if task_id changes mid-agent |
| [Layer 6](layer-6.md) | qg_layer6.py | 76% | 0** | 10 | Filter bug fixed |
| [Layer 7](layer-7.md) | qg_layer7.py | **84%** | 3 | **21** | Needs more feedback data |
| [Layer 8](layer-8.md) | qg_layer8.py | 85% | 10 | 9 | Baseline never updates within session |
| [Layer 9](layer-9.md) | qg_layer9.py | **85%** | logging | **22** | Insufficient calibration data |
| [Layer 10](layer-10.md) | qg_layer10.py | 89% | 0 | 8 | 7-day throttle means it rarely runs |
| [Layer **11**](pending) | qg_layer11.py | new | **0** | **28** | **NEW** — just deployed |
| [Layer **20**](layer-20.md) | qg_layer20.py | 79% | **3** | **25** | **NEW** — needs more sessions |
| [Precheck](precheck.md) | precheck-hook.py | 49% | 49 | 17 | Ollama classification accuracy unmeasured |
| [Session State](session-state.md) | qg_session_state.py | 87% | N/A | 14 | Atomic writes now implemented |
| [Notification Router](notification-router.md) | qg_notification_router.py | **97%** | N/A | 15 | Per-turn counter now uses session state |

`*` = operates through quality-gate.py; decisions logged in quality-gate.log
`**` = writes to qg-cross-session.json; confirmed working via Layer 0 output

---

## Critical Findings — Status Update

### Previously Resolved
1. ~~quality-gate.py has 9% test coverage~~ → **83%**
2. ~~13 of 20 layers never logged monitor events~~ → **16 of 23 now visible**
3. ~~Layer 7 has 23% coverage~~ → **84%**
4. ~~Layer 2 rate limiter bug~~ → **RESOLVED** (precheck resets it)
5. ~~Path normalization issues~~ → **RESOLVED** (3 layers patched)
6. ~~Layer 6 filter bug~~ → **RESOLVED**
7. ~~Dead code candidates~~ → **MOSTLY RESOLVED** (SCOPE_CREEP/INCOMPLETE_COVERAGE confirmed live)
8. ~~introduces_new_problem not consumed~~ → **RESOLVED** (consumed in _compute_confidence)
9. ~~Non-atomic session state writes~~ → **RESOLVED** (temp file + os.replace)
10. ~~Notification router per-turn counter~~ → **RESOLVED** (moved to session state)

---

## Remaining Priority Improvements

1. **Layer 11 scorecard** — create `layer-11.md` with coverage data after more sessions
2. **Layer 2.8 main() tests** — coverage 63%, main() path untested
3. **Layer 20 main() tests** — coverage 79%, main() path untested
4. **Improve Layer 1.7 coverage** (54%) — among lowest
5. **Improve precheck coverage** (49%) — lowest overall
6. **Tune Haiku OVERCONFIDENCE prompt** — 76% of shadow disagreements
7. **Measure precheck Ollama accuracy** — need 50+ labeled classifications

---

## Future Layers

See **[FUTURE-LAYERS.md](FUTURE-LAYERS.md)** for remaining proposed layers:

| Layer | Name | Value | Complexity | Status |
|-------|------|-------|------------|--------|
| ~~2.8~~ | ~~Security Vulnerability Detection~~ | ~~CRITICAL~~ | ~~MEDIUM~~ | **DEPLOYED** |
| 2.9 | Semantic Correctness Verification | HIGH | HIGH | planned |
| ~~11~~ | ~~Commit Quality Gate~~ | ~~HIGH~~ | ~~LOW~~ | **DEPLOYED** |
| 12 | User Satisfaction Tracking | HIGH | MEDIUM | planned |
| 13 | Knowledge Freshness Verification | MEDIUM | HIGH | planned |
| 14 | Response Efficiency Analysis | MEDIUM | LOW | planned |
| 15 | Memory & State Integrity | MEDIUM | MEDIUM | planned |
| 16 | Rollback & Undo Capability | HIGH | MEDIUM | planned |
| 17 | Adversarial Self-Testing | CRITICAL | HIGH | planned |
| 18 | A/B Rule Testing | MEDIUM | HIGH | planned |
| 19 | Cross-Project Learning | MEDIUM | MEDIUM | planned |
| ~~20~~ | ~~System Health Dashboard~~ | ~~HIGH~~ | ~~LOW~~ | **DEPLOYED** |

**Next build priority:** 16 (Rollback) → 12 (Satisfaction) → 14 (Efficiency) → 17 (Adversarial)

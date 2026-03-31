# Quality Gate Layer Scorecard — Index
Last updated: 2026-03-30
Standards: [README.md](README.md)

---

## System-Level Summary

| Metric | Baseline (start of session) | Current | Change |
|--------|---------------------------|---------|--------|
| Total unit tests | 402 | **512** | +110 |
| Total smoke tests | 583 | **588** | +5 |
| quality-gate.py coverage | 83% | 83% | — |
| Layers deployed | 20 | **27** | +7 new layers |
| Layers with monitor events | 15 of 20 | **19 of 27** | +4 |
| Bugs fixed (cumulative) | 2 | **3** (+Layer 11 multiline fix) | +1 |

---

## New Layers This Session (7 built)

| Layer | File | LOC | Hook Event | Tests | Cov | Events |
|-------|------|-----|-----------|-------|-----|--------|
| [2.8](layer-2.8.md) | qg_layer28.py | 157 | PostToolUse Write/Edit | 18 | 63% | 16 |
| [11](layer-11.md) | qg_layer11.py | 205 | PreToolUse Bash | 28 | 58% | 8 |
| [12](layer-12.md) | qg_layer12.py | 160 | UserPromptSubmit | 22 | 58% | 4 |
| [14](layer-14.md) | qg_layer14.py | 160 | Stop | 17 | 37% | 0 |
| [16](layer-16.md) | qg_layer16.py | 173 | PreToolUse Edit/Write | 18 | 61% | 7 |
| [20](layer-20.md) | qg_layer20.py | 299 | SessionStart | 25 | 79% | 3 |

Layer 2.8 was built in a prior session; Layers 11, 12, 14, 16, 20 built this session.

---

## Layer Scores at a Glance

| Layer | File | pytest-cov | Live Events | Tests | Top Weakness |
|-------|------|-----------|-------------|-------|-------------|
| [Layer 0](layer-0.md) | qg_layer0.py | 54% | 169 | 7 | UUID matching may target wrong session |
| [Layer ENV](layer-env.md) | qg_layer_env.py | 59% | logging | 12 | Test baseline capture untested |
| [Layer 1/3/4](quality-gate-main.md) | quality-gate.py | **83%** | 0* | **101** | Remaining 17%: edge branches |
| [Layer 1.5](layer-1.5.md) | qg_layer15.py | 82% | 93 | 15 | Override token untested |
| [Layer 1.7](layer-1.7.md) | qg_layer17.py | 54% | 10 | 13 | Uncertainty regex overlap |
| [Layer 1.8](layer-1.8.md) | qg_layer18.py | 64% | 36 | 13 | Substring match FP risk |
| [Layer 1.9](layer-1.9.md) | qg_layer19.py | 63% | 34 | 11 | grep regex too broad |
| [Layer 2](layer-2.md) | qg_layer2.py | **93%** | **2131** | **25** | — |
| [Layer 2.5](layer-2.5.md) | qg_layer25.py | 81% | 2 | 9 | YAML skipped if pyyaml missing |
| [Layer 2.6](layer-2.6.md) | qg_layer26.py | 86% | 36 | 9 | Mixed-import no baseline |
| [Layer 2.7](layer-2.7.md) | qg_layer27.py | **92%** | 12 | **17** | os.walk no depth limit |
| [Layer 2.8](layer-2.8.md) | qg_layer28.py | 63% | 16 | 18 | main() untested |
| [Layer 3.5](layer-3.5.md) | qg_layer35.py | 64% | 55 | 13 | — |
| [Layer 4.5](layer-4.5.md) | qg_layer45.py | 83% | 134 | 10 | Hash covers 5/16 keys |
| [Layer 5](layer-5.md) | qg_layer5.py | 73% | 111 | 13 | ID correlation breaks mid-agent |
| [Layer 6](layer-6.md) | qg_layer6.py | 76% | 0** | 10 | — |
| [Layer 7](layer-7.md) | qg_layer7.py | **84%** | 3 | **21** | Needs more feedback data |
| [Layer 8](layer-8.md) | qg_layer8.py | 85% | 10 | 9 | Baseline never updates in session |
| [Layer 9](layer-9.md) | qg_layer9.py | **85%** | logging | **22** | Calibration data insufficient |
| [Layer 10](layer-10.md) | qg_layer10.py | 89% | 0 | 8 | 7-day throttle |
| [Layer 11](layer-11.md) | qg_layer11.py | 58% | 8 | 28 | Push branch validation missing |
| [Layer 12](layer-12.md) | qg_layer12.py | 58% | 4 | 22 | Sarcasm/emoji undetected |
| [Layer 14](layer-14.md) | qg_layer14.py | 37% | 0 | 17 | Transcript parsing untested |
| [Layer 16](layer-16.md) | qg_layer16.py | 61% | 7 | 18 | main() untested |
| [Layer 20](layer-20.md) | qg_layer20.py | 79% | 3 | 25 | main() untested |
| [Precheck](precheck.md) | precheck-hook.py | 49% | 49 | 17 | Ollama accuracy unmeasured |
| [Session State](session-state.md) | qg_session_state.py | 87% | N/A | 14 | — |
| [Notification Router](notification-router.md) | qg_notification_router.py | **97%** | N/A | 15 | — |

`*` = operates through quality-gate.py; decisions logged in quality-gate.log
`**` = writes to qg-cross-session.json; confirmed working via Layer 0 output

---

## Previously Resolved Issues
1. ~~quality-gate.py 9% coverage~~ → **83%**
2. ~~13/20 layers no monitor events~~ → **19/27 visible**
3. ~~Layer 7 23% coverage~~ → **84%**
4. ~~Layer 2 rate limiter bug~~ → **RESOLVED**
5. ~~Path normalization~~ → **RESOLVED** (3 layers)
6. ~~Layer 6 filter bug~~ → **RESOLVED**
7. ~~Dead code candidates~~ → **RESOLVED**
8. ~~introduces_new_problem~~ → **RESOLVED**
9. ~~Non-atomic state writes~~ → **RESOLVED**
10. ~~Notification router counter~~ → **RESOLVED**
11. ~~Layer 11 multiline commit regex~~ → **RESOLVED**

---

## Remaining Priority Improvements

1. **Layer 14 coverage** (37%) — lowest of all layers, transcript parsing needs tests
2. **Precheck coverage** (49%) — second lowest
3. **Layer 1.7 coverage** (54%) — third lowest
4. **main() tests** for new layers (2.8, 11, 12, 14, 16, 20) — all ~60% coverage
5. **Tune Haiku OVERCONFIDENCE prompt** — 76% of shadow disagreements
6. **Measure precheck Ollama accuracy** — need 50+ labeled classifications

---

## Future Layers

See **[FUTURE-LAYERS.md](FUTURE-LAYERS.md)** — 5 of 12 remaining:

| Layer | Name | Value | Complexity | Status |
|-------|------|-------|------------|--------|
| ~~2.8~~ | ~~Security Vulnerability Detection~~ | — | — | **DEPLOYED** |
| 2.9 | Semantic Correctness Verification | HIGH | HIGH | planned |
| ~~11~~ | ~~Commit Quality Gate~~ | — | — | **DEPLOYED** |
| ~~12~~ | ~~User Satisfaction Tracking~~ | — | — | **DEPLOYED** |
| 13 | Knowledge Freshness Verification | MEDIUM | HIGH | planned |
| ~~14~~ | ~~Response Efficiency Analysis~~ | — | — | **DEPLOYED** |
| 15 | Memory & State Integrity | MEDIUM | MEDIUM | planned |
| ~~16~~ | ~~Rollback & Undo Capability~~ | — | — | **DEPLOYED** |
| 17 | Adversarial Self-Testing | CRITICAL | HIGH | planned |
| 18 | A/B Rule Testing | MEDIUM | HIGH | planned |
| 19 | Cross-Project Learning | MEDIUM | MEDIUM | planned |
| ~~20~~ | ~~System Health Dashboard~~ | — | — | **DEPLOYED** |

**Next build priority:** 2.9 (Semantic) → 17 (Adversarial) → 19 (Cross-Project) → 15 (Memory) → 13 (Freshness) → 18 (A/B)

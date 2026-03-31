# Quality Gate Layer Scorecard — Index
Last updated: 2026-03-30
Standards: [README.md](README.md)

---

## System-Level Summary

| Metric | Start of Session | End of Session | Change |
|--------|-----------------|----------------|--------|
| Layers deployed | 20 | **33** | **+13** |
| Unit tests | 402 | **590** | +188 |
| Smoke tests | 583 | **594** | +11 |
| quality-gate.py coverage | 83% | 83% | — |
| Future layers remaining | 12 | **0** | ALL DEPLOYED |
| Bugs fixed (cumulative) | 2 | 3 | +1 |

---

## New Layers This Session (12 built + 1 fix)

| Layer | File | LOC | Hook Event | Tests | Cov | Events |
|-------|------|-----|-----------|-------|-----|--------|
| [2.8](layer-2.8.md) | qg_layer28.py | 157 | PostToolUse Write/Edit | 18 | 63% | 16 |
| [2.9](pending) | qg_layer29.py | 175 | Stop | 30 | 44% | 0 |
| [11](layer-11.md) | qg_layer11.py | 205 | PreToolUse Bash | 28 | 58% | 8 |
| [12](layer-12.md) | qg_layer12.py | 160 | UserPromptSubmit | 22 | 58% | 21 |
| [13](pending) | qg_layer13.py | 164 | PostToolUse Write/Edit | 15 | 59% | 0 |
| [14](layer-14.md) | qg_layer14.py | 160 | Stop | 17 | 37% | 0 |
| [15m](pending) | qg_layer15_mem.py | 172 | SessionStart | 14 | 67% | 0 |
| [16](layer-16.md) | qg_layer16.py | 173 | PreToolUse Edit/Write | 18 | 61% | 17 |
| [17](pending) | qg_layer17_adv.py | 154 | SessionStart (daily) | 0* | 0%* | 1 |
| [18](pending) | qg_layer18_ab.py | 182 | SessionStart + CLI | 12 | 66% | 1 |
| [19](pending) | qg_layer19_cross.py | 189 | SessionStart | 17 | 74% | 5 |
| [20](layer-20.md) | qg_layer20.py | 299 | SessionStart | 25 | 79% | 16 |

`*` Layer 17 IS the test runner — it tests other layers' detection functions directly. 0% unit test coverage because it's tested by running it.

---

## All Layers at a Glance (33 total)

| Layer | File | Cov | Events | Tests | Top Weakness |
|-------|------|-----|--------|-------|-------------|
| [0](layer-0.md) | qg_layer0.py | 54% | 169 | 7 | UUID matching |
| [ENV](layer-env.md) | qg_layer_env.py | 59% | yes | 12 | Baseline untested |
| [1/3/4](quality-gate-main.md) | quality-gate.py | **83%** | 0* | **101** | Edge branches |
| [1.5](layer-1.5.md) | qg_layer15.py | 82% | 93 | 15 | Override untested |
| [1.7](layer-1.7.md) | qg_layer17.py | 54% | 10 | 13 | Regex overlap |
| [1.8](layer-1.8.md) | qg_layer18.py | 64% | 36 | 13 | Substring FP |
| [1.9](layer-1.9.md) | qg_layer19.py | 63% | 34 | 11 | Broad regex |
| [2](layer-2.md) | qg_layer2.py | **93%** | **2131** | **25** | — |
| [2.5](layer-2.5.md) | qg_layer25.py | 81% | 2 | 9 | YAML skip |
| [2.6](layer-2.6.md) | qg_layer26.py | 86% | 36 | 9 | Mixed-import |
| [2.7](layer-2.7.md) | qg_layer27.py | **92%** | 12 | **17** | Depth limit |
| [2.8](layer-2.8.md) | qg_layer28.py | 63% | 16 | 18 | main() untested |
| **2.9** | qg_layer29.py | 44% | 0 | 30 | Transcript parsing |
| [3.5](layer-3.5.md) | qg_layer35.py | 64% | 55 | 13 | — |
| [4.5](layer-4.5.md) | qg_layer45.py | 83% | 134 | 10 | Hash 5/16 keys |
| [5](layer-5.md) | qg_layer5.py | 73% | 111 | 13 | ID mid-agent |
| [6](layer-6.md) | qg_layer6.py | 76% | 0** | 10 | — |
| [7](layer-7.md) | qg_layer7.py | **84%** | 3 | **21** | Feedback data |
| [8](layer-8.md) | qg_layer8.py | 85% | 10 | 9 | Baseline static |
| [9](layer-9.md) | qg_layer9.py | **85%** | yes | **22** | Calibration |
| [10](layer-10.md) | qg_layer10.py | 89% | 0 | 8 | 7-day throttle |
| [**11**](layer-11.md) | qg_layer11.py | 58% | 8 | 28 | Push validation |
| [**12**](layer-12.md) | qg_layer12.py | 58% | 21 | 22 | Sarcasm/emoji |
| **13** | qg_layer13.py | 59% | 0 | 15 | Cache bloat |
| [**14**](layer-14.md) | qg_layer14.py | 37% | 0 | 17 | Transcript parse |
| **15m** | qg_layer15_mem.py | 67% | 0 | 14 | Claim verify |
| [**16**](layer-16.md) | qg_layer16.py | 61% | 17 | 18 | main() untested |
| **17** | qg_layer17_adv.py | 0% | 1 | 0* | Self-tests only |
| **18** | qg_layer18_ab.py | 66% | 1 | 12 | Shadow mode |
| **19** | qg_layer19_cross.py | 74% | 5 | 17 | Min threshold |
| [**20**](layer-20.md) | qg_layer20.py | 79% | 16 | 25 | main() untested |
| [Precheck](precheck.md) | precheck-hook.py | 49% | 49 | 17 | Ollama accuracy |
| [State](session-state.md) | qg_session_state.py | 87% | N/A | 14 | — |
| [Router](notification-router.md) | qg_notification_router.py | **97%** | N/A | 15 | — |

`*` quality-gate.py logs to quality-gate.log | `**` writes to qg-cross-session.json
**Bold** = new this session

---

## Previously Resolved Issues (11)
1. ~~quality-gate.py 9% coverage~~ → **83%**
2. ~~13/20 layers no monitor events~~ → **visible**
3. ~~Layer 7 23% coverage~~ → **84%**
4. ~~Layer 2 rate limiter bug~~ → **RESOLVED**
5. ~~Path normalization~~ → **RESOLVED**
6. ~~Layer 6 filter bug~~ → **RESOLVED**
7. ~~Dead code candidates~~ → **RESOLVED**
8. ~~introduces_new_problem~~ → **RESOLVED**
9. ~~Non-atomic state writes~~ → **RESOLVED**
10. ~~Notification router counter~~ → **RESOLVED**
11. ~~Layer 11 multiline commit regex~~ → **RESOLVED**

---

## Remaining Priority Improvements

1. **Layer 14 coverage** (37%) — lowest, transcript parsing needs tests
2. **Layer 2.9 coverage** (44%) — transcript parsing untested
3. **Precheck coverage** (49%) — third lowest
4. **Layer 1.7 coverage** (54%) — fourth lowest
5. **main() tests** for 8 new layers — most at ~60% coverage
6. **Tune Haiku OVERCONFIDENCE prompt** — 76% of shadow disagreements
7. **Create scorecards** for Layers 2.9, 13, 15m, 17, 18, 19

---

## Future Layers — ALL DEPLOYED

All 12 layers from **[FUTURE-LAYERS.md](FUTURE-LAYERS.md)** are now deployed:

| Layer | Name | Status |
|-------|------|--------|
| 2.8 | Security Vulnerability Detection | **DEPLOYED** |
| 2.9 | Semantic Correctness Verification | **DEPLOYED** |
| 11 | Commit Quality Gate | **DEPLOYED** |
| 12 | User Satisfaction Tracking | **DEPLOYED** |
| 13 | Knowledge Freshness Verification | **DEPLOYED** |
| 14 | Response Efficiency Analysis | **DEPLOYED** |
| 15 | Memory & State Integrity | **DEPLOYED** |
| 16 | Rollback & Undo Capability | **DEPLOYED** |
| 17 | Adversarial Self-Testing | **DEPLOYED** |
| 18 | A/B Rule Testing | **DEPLOYED** |
| 19 | Cross-Project Learning | **DEPLOYED** |
| 20 | System Health Dashboard | **DEPLOYED** |

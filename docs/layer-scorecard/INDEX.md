# Quality Gate Layer Scorecard — Index
Last updated: 2026-03-31
Standards: [README.md](README.md)

---

## System-Level Summary

| Metric | Before (2026-03-30) | After (2026-03-31) | Change |
|--------|--------------------|--------------------|--------|
| Total unit tests | 253 | **359** | +106 |
| Total smoke tests | 575 | **576** | +1 |
| Total live events | 2,204 | **2,885** | +681 |
| Overall pytest-cov | **26%** | **~45%** (estimated) | +19% |
| quality-gate.py coverage | **9%** | **83%** | +74% |
| Layer 7 coverage | **23%** | **84%** | +61% |
| Quality gate decisions | 602 | **627** (420 PASS, 198 BLOCK, 9 DEGRADED-PASS) | +25 |
| Layers with monitor events | 7 of 20 | **15 of 20** | +8 layers visible |
| Bugs fixed | 0 | **2** (Layer 6 filter, path normalization) | |

---

## Changes This Session

### Completed (items 1-5 from prior priority list)
1. ~~Write unit tests for quality-gate.py~~ **DONE** — 92 new tests, coverage 9% → 83%
2. ~~Fix Layer 6 filter bug~~ **DONE** — `e.get("working_dir", project_dir)` → `e.get("working_dir")`
3. ~~Add monitor logging to invisible layers~~ **DONE** — 10 layers patched (ENV, 1.5, 1.8, 1.9, 2.7, 3.5, 4.5, 7, 9, precheck)
4. ~~Add path normalization~~ **DONE** — `_norm_path()` added to Layers 2, 1.5, 1.7
5. ~~Write tests for Layer 7~~ **DONE** — 14 new tests, coverage 23% → 84%

---

## Layer Scores at a Glance

| Layer | File | pytest-cov | Live Events | Tests | Top Weakness |
|-------|------|-----------|-------------|-------|-------------|
| [Layer 0](layer-0.md) | qg_layer0.py | 54% | 169 | 7 | UUID matching may target wrong session |
| [Layer ENV](layer-env.md) | qg_layer_env.py | 59% | **now logging** | 12 | Test baseline capture untested |
| [Layer 1/3/4](quality-gate-main.md) | quality-gate.py | **83%** | 0* | **101** | Remaining 17%: edge branches in transcript parsing |
| [Layer 1.5](layer-1.5.md) | qg_layer15.py | 82% | **93** | 15 | Override token untested; critical flush untested |
| [Layer 1.7](layer-1.7.md) | qg_layer17.py | 54% | 10 | 13 | Path normalization added; uncertainty regex overlap remains |
| [Layer 1.8](layer-1.8.md) | qg_layer18.py | 64% | **36** | 13 | Function check uses substring match (FP risk) |
| [Layer 1.9](layer-1.9.md) | qg_layer19.py | 63% | **34** | 11 | grep regex too broad for import matching |
| [Layer 2](layer-2.md) | qg_layer2.py | **93%** | **2131** | **25** | Path normalization added; SCOPE_CREEP/INCOMPLETE_COVERAGE dead? |
| [Layer 2.5](layer-2.5.md) | qg_layer25.py | 81% | 2 | 9 | YAML validation silently skipped if pyyaml missing |
| [Layer 2.6](layer-2.6.md) | qg_layer26.py | 86% | 36 | 9 | Mixed-import files produce no baseline |
| [Layer 2.7](layer-2.7.md) | qg_layer27.py | 45% | **12** | 5 | os.walk no depth limit; now fires (was thought dead) |
| [Layer 3.5](layer-3.5.md) | qg_layer35.py | 64% | **55** | 13 | introduces_new_problem flag never consumed |
| [Layer 4.5](layer-4.5.md) | qg_layer45.py | 83% | **134** | 10 | Hash only covers 5/16 preserved keys |
| [Layer 5](layer-5.md) | qg_layer5.py | 73% | 111 | 13 | ID correlation breaks if task_id changes mid-agent |
| [Layer 6](layer-6.md) | qg_layer6.py | 76% | 0** | 10 | ~~filter bug~~ **FIXED** |
| [Layer 7](layer-7.md) | qg_layer7.py | **84%** | **3** | **21** | ~~23% coverage~~ **FIXED**; needs more feedback data |
| [Layer 8](layer-8.md) | qg_layer8.py | 85% | 10 | 9 | Baseline never updates within session |
| [Layer 9](layer-9.md) | qg_layer9.py | 41% | **now logging** | 10 | Insufficient calibration data; coverage still low |
| [Layer 10](layer-10.md) | qg_layer10.py | 89% | 0 | 8 | 7-day throttle means it rarely runs |
| [Precheck](precheck.md) | precheck-hook.py | 49% | **49** | 17 | Ollama classification accuracy unmeasured |
| [Session State](session-state.md) | qg_session_state.py | 87% | N/A | 14 | Silent lock failure; no atomic writes |
| [Notification Router](notification-router.md) | qg_notification_router.py | **97%** | N/A | 15 | Per-turn counter resets each process (may not limit) |
| [Verify Reminder](verify-reminder.md) | verify-reminder.py | N/A | new | 1 | Untested: whether Claude follows the reminder reliably |

`*` = operates through quality-gate.py; decisions logged in quality-gate.log (627 total)
`**` = writes to qg-cross-session.json; confirmed working via Layer 0 output

---

## Critical Findings — Status Update

### 1. ~~quality-gate.py has 9% test coverage~~ RESOLVED
Coverage now **83%** with 92 new unit tests across 8 test classes covering mechanical checks, transcript parsing, LLM evaluation (mocked), Layer 3 classification (mocked), Layer 4 checkpoint, main() orchestration, and override detection.

### 2. ~~13 of 20 layers have never logged a monitor event~~ MOSTLY RESOLVED
10 layers patched with `_write_event()` calls. Now **15 of 20 layers** have monitor events. Remaining 5 without direct monitor events: Layer ENV (fires only on env warnings — rare), Layer 6 (writes to separate file), Layer 9 (now logging but needs more sessions to accumulate), Layer 10 (7-day throttle), and quality-gate.py itself (logs to quality-gate.log).

### 3. ~~Layer 7 has 23% coverage~~ RESOLVED
Coverage now **84%** with 14 new tests covering `load_feedback`, `generate_suggestions`, `write_suggestions`, and `main()`.

### 4. ~~Layer 2's rate limiter may be a bug~~ RESOLVED (prior session)

### 5. ~~Multiple layers have path normalization issues~~ RESOLVED
`_norm_path()` added to Layers 2, 1.5, and 1.7. All path comparisons now normalize `C:\` and `C:/` to canonical form.

### 6. ~~Layer 6 has a filter bug~~ RESOLVED
Changed `e.get("working_dir", project_dir)` to `e.get("working_dir")`.

### 7. ~~Dead code candidates~~ MOSTLY RESOLVED
- **SCOPE_CREEP — NOT DEAD.** 31 events in monitor log since March 28. Fires when edits land outside `layer1_scope_files`. Was always logging via Layer 2 — the original scorecard search missed them.
- **INCOMPLETE_COVERAGE — NOT DEAD.** 1 event confirmed. Rare but functional.
- **Layer 2.7 — NOT DEAD.** 12 events after monitor logging was added.
- `introduces_new_problem` flag in Layer 3.5 — still not consumed downstream (only remaining dead code candidate)

---

## Remaining Priority Improvements

1. **Consume `introduces_new_problem` flag** — or remove from Layer 3.5 (only dead code left)
2. **Add atomic writes to session state** — temp file + rename to prevent corruption on crash
3. **Verify notification router per-turn limit** — global counter resets each process invocation
4. **Improve Layer 9 coverage** (41%) — second-lowest after Layer 2.7
5. **Improve Layer 2.7 coverage** (45%) — lowest overall
6. **Run `qg shadow 10`** — measure post-tuning Haiku/Ollama agreement
7. **Measure precheck Ollama classification accuracy** — sample 50+ classifications
8. **Consume `introduces_new_problem` flag** — or remove dead code from Layer 3.5

---

## Future Layers

See **[FUTURE-LAYERS.md](FUTURE-LAYERS.md)** for 12 proposed new layers covering gaps no existing layer can address:

| Layer | Name | Value | Complexity |
|-------|------|-------|------------|
| 2.8 | Security Vulnerability Detection | CRITICAL | MEDIUM |
| 2.9 | Semantic Correctness Verification | HIGH | HIGH |
| 11 | Commit Quality Gate | HIGH | LOW |
| 12 | User Satisfaction Tracking | HIGH | MEDIUM |
| 13 | Knowledge Freshness Verification | MEDIUM | HIGH |
| 14 | Response Efficiency Analysis | MEDIUM | LOW |
| 15 | Memory & State Integrity | MEDIUM | MEDIUM |
| 16 | Rollback & Undo Capability | HIGH | MEDIUM |
| 17 | Adversarial Self-Testing | CRITICAL | HIGH |
| 18 | A/B Rule Testing | MEDIUM | HIGH |
| 19 | Cross-Project Learning | MEDIUM | MEDIUM |
| 20 | System Health Dashboard | HIGH | LOW |

**Recommended build order:** 2.8 → 20 → 11 → 16 → 12 → 17

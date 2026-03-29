# Claude Behavioral Controller

A real-time quality monitoring and behavioral enforcement system for [Claude Code](https://claude.ai/code), implemented as a layered hook stack.

## What It Does

Every Claude Code session is monitored by a stack of Python hooks that fire at key lifecycle events. The system classifies every response as **TP** (failure prevented), **FP** (incorrect block), **FN** (missed failure), or **TN** (correctly passed), tracks violations mid-task, and maintains a rolling session history.

The goal: catch laziness, assumptions, incorrect tool use, and unverified claims *before* they make it into the final response.

## Architecture

```
SessionStart
  └── Layer 0      (qg_layer0.py)       — inject previous session's unresolved items; reset per-session state
  └── Layer ENV    (qg_layer_env.py)    — validate git branch, required tools, env vars

UserPromptSubmit
  └── Layer 1      (precheck-hook.py)   — classify task (MECHANICAL/ASSUMPTION/OVERCONFIDENCE/PLANNING/DEEP);
                                          generate session UUID; detect task pivots; inject directives

PreToolUse (every tool)
  └── Layer ENV    (qg_layer_env.py)    — re-validate if file path is outside working directory
  └── Layer 1.5    (qg_layer15.py)      — rule validation: edit-without-read, bash-instead-of-tool,
                                          write-outside-scope; flush queued CRITICAL notifications
  └── Layer 1.9    (qg_layer19.py)      — change impact analysis; dependency count → impact level
  └── Layer 1.7    (qg_layer17.py)      — user intent verification for COMPLEX/DEEP tasks
  └── Layer 1.8    (qg_layer18.py)      — hallucination detection: file path + function ref checks
  └── Layer 2.7    (qg_layer27.py)      — testing coverage: warn when editing code without corresponding tests

PostToolUse (every tool)
  └── Layer 2      (qg_layer2.py)       — detect LAZINESS, INCORRECT_TOOL, ERROR_IGNORED,
                                          SCOPE_CREEP, LOOP_DETECTED
  └── Layer 2.5    (qg_layer25.py)      — output validity: syntax check written files (JSON, Python, YAML)
  └── Layer 2.6    (qg_layer26.py)      — consistency enforcement: naming convention drift detection
  └── Layer 5      (qg_layer5.py)       — subagent coordination: track dispatch/return, merge events
  └── Layer 8      (qg_layer8.py)       — regression detection: track test pass/fail counts across runs

PreCompact / PostCompact
  └── Layer 4.5    (qg_layer45.py)      — context preservation: save/restore session state through compaction

Stop (every response)
  └── Layer 3/4    (quality-gate.py)    — classify TP/FP/FN/TN; write session history checkpoint
  └── Layer 3.5    (qg_layer35.py)      — recovery tracking: cross-turn resolution of unresolved events
  └── Layer 6      (qg_layer6.py)       — cross-session pattern analysis: recurring violation trends
  └── Layer 7      (qg_layer7.py)       — rule refinement: suggest rule changes from FP/FN patterns
  └── Layer 9      (qg_layer9.py)       — confidence calibration: track certainty vs actual outcomes
```

## Layer Details

| Layer | Hook Event | File | Purpose |
|-------|-----------|------|---------|
| 0 | SessionStart | `qg_layer0.py` | Inject previous unresolved items; reset cross-session state |
| ENV | SessionStart + PreToolUse | `qg_layer_env.py` | Environment validation |
| 1 | UserPromptSubmit | `precheck-hook.py` | Task classification, UUID generation, scope inference |
| 1.5 | PreToolUse | `qg_layer15.py` | Rule-based PreToolUse validation |
| 1.7 | PreToolUse | `qg_layer17.py` | User intent verification for COMPLEX/DEEP tasks |
| 1.8 | PreToolUse | `qg_layer18.py` | Hallucination detection: file path + function ref existence checks |
| 1.9 | PreToolUse | `qg_layer19.py` | Change impact analysis: dependency count → impact level |
| 2 | PostToolUse | `qg_layer2.py` | Mid-task violation detection |
| 3 | Stop | `quality-gate.py` | TP/FP/FN/TN classification |
| 3.5 | Stop | `qg_layer35.py` | Recovery tracking: cross-turn resolution of unresolved events |
| 4 | Stop | `quality-gate.py` | Incremental session history checkpoint |
| 4.5 | PreCompact + PostCompact | `qg_layer45.py` | Context preservation through compaction |
| 2.5 | PostToolUse (Write\|Edit) | `qg_layer25.py` | Output validity: syntax check written files |
| 2.6 | PostToolUse (Write\|Edit) | `qg_layer26.py` | Consistency enforcement: naming convention drift |
| 2.7 | PreToolUse (Edit) | `qg_layer27.py` | Testing coverage: warn on code edits without tests |
| 5 | PostToolUse (Agent) | `qg_layer5.py` | Subagent coordination: dispatch/return tracking, event merge |
| 6 | Stop | `qg_layer6.py` | Cross-session pattern analysis: recurring violations |
| 7 | Stop | `qg_layer7.py` | Rule refinement: suggest rule changes from FP/FN |
| 8 | PostToolUse (Bash) | `qg_layer8.py` | Regression detection: test pass/fail tracking |
| 9 | Stop | `qg_layer9.py` | Confidence calibration: certainty vs outcomes |
| 10 | — (library) | `qg_layer10.py` | Audit trail integrity: JSONL validation and rotation |

**Supporting modules:**
- `qg_session_state.py` — cross-layer session state (file-locked JSON)
- `qg_notification_router.py` — priority notification routing (CRITICAL → immediate, WARNING → end-of-turn)
- `precheck_hook_ext.py` — testable helpers for Layer 1 (Jaccard similarity, scope inference)

## Layer 2 Violation Categories

| Category | Severity | Detection Signal |
|----------|----------|-----------------|
| LAZINESS | warning | Edit without prior Read |
| INCORRECT_TOOL | info | Bash grep/cat/find instead of dedicated tools |
| ERROR_IGNORED | critical | Error in prior tool output, next tool fires anyway |
| SCOPE_CREEP | warning | Files outside Layer 1 task scope touched |
| LOOP_DETECTED | critical | Same tool + target called 3+ times |

## Configuration

All tunable parameters live in `qg-rules.json` — no code changes required:

```json
{
  "layer1":  { "deep_min_length": 300, "deep_scope_keywords": [...] },
  "layer15": { "repeat_violation_threshold": 3 },
  "layer2":  { "events_per_turn_limit": 5, "loop_same_tool_count": 3 },
  "layer4":  { "session_retention_count": 30 }
}
```

## Data Files

| File | Purpose |
|------|---------|
| `~/.claude/qg-session-state.json` | Live cross-layer session state |
| `~/.claude/qg-monitor.jsonl` | All classified events (all layers) |
| `~/.claude/qg-session-history.md` | Rolling session summaries (last 30) |
| `~/.claude/qg-rules.json` | Configurable rules |

## Dashboard

```bash
qg monitor     # unified dashboard: L2 events, L3 TP/FP/FN/TN, session summary
qg integrity   # audit trail integrity check
qg analyze     # cross-session pattern analysis (Phase 3)
qg rules       # view pending rule suggestions (Phase 3)
```

## Tests

```bash
cd ~/.claude/scripts/tests
python -m pytest test_qg_layers.py test_qg_notification_router.py test_qg_session_state.py -v
# 71 passed
```

## Implementation Phases

- **Phase 1** ✅ — Layers 0, ENV, 1, 1.5, 2, 3, 4 + Session State + Notification Router + Dashboard
- **Phase 2** ✅ — Layers 1.7 (intent verification), 1.8 (hallucination detection), 1.9 (change impact), 3.5 (recovery tracking), 4.5 (context preservation), 5 (subagent coordination)
- **Phase 3** ✅ — Layers 2.5 (output validity), 2.6 (consistency enforcement), 2.7 (testing coverage), 6 (cross-session patterns), 7 (rule refinement), 8 (regression detection), 9 (confidence calibration), 10 (audit integrity)

## Platform

Windows 10 + Python 3.13. Hook commands use `python` directly; paths are absolute Windows paths (`C:/Users/...`). The hooks run inside Claude Code's Git Bash environment.

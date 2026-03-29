# Credible Validation + Anti-Laziness System

## Context

Three layers of the problem:
1. **Specific patterns** (solved): quality-gate catches missing verification, unverified edits, absolutist claims, compact without save
2. **Fake verification** (in progress): Check 2c validates Bash commands are real tests, not `echo hello`
3. **Subjective laziness** (unsolved): shallow reviews, skipped edge cases, assumptions instead of tests, citing docs from memory instead of fetching them

Layers 1-2 are deterministic. Layer 3 requires judgment — only an LLM can evaluate thoroughness.

## Part 1: Absolutist fix + credible validation (deterministic)

*(Same as previously reviewed — taxonomy reclassification + VALIDATION_COMMAND_RE)*

### Change 1: Reclassify phrases

**ABSOLUTIST_PHRASES** — reduce to `["100% sure", "100% confident"]`

**COMPLETION_PHRASES** — add `"nothing to improve"`, `"nothing to fix"` (only these two — `"nothing left to *"` already caught by `"nothing left"`)

Remove from ABSOLUTIST: `"nothing left to improve"`, `"nothing to improve"`, `"nothing left to fix"`, `"nothing to fix"`, `"nothing at all"`, `"absolutely nothing"`

### Change 2: Add Check 2c (Bash content validation)

New helper `get_recent_bash_commands(transcript_path)` + `VALIDATION_COMMAND_RE` regex (tested 24/24).

Check 2c fires when edits were made + Bash was used + Check 2b passed. Verifies at least one Bash command matches validation patterns.

## Part 2: Anti-laziness enforcement (LLM-based)

### Design: `prompt` type Stop hook

A `prompt` hook on the Stop event uses Haiku to evaluate whether the response is thorough. This is the ONLY mechanism that can catch subjective laziness.

```json
{
  "type": "prompt",
  "prompt": "Evaluate the assistant's response for thoroughness. If stop_hook_active is true in the input, respond {\"ok\": true} unless the response is clearly evasive. For TRIVIAL interactions (greetings, yes/no, simple facts, single-line answers to simple questions), respond {\"ok\": true}. For substantive responses, flag laziness if you see ANY of: (1) Response mentions multiple items/files/steps but doesn't address them individually (2) Claims about code correctness without showing test output or command results (3) 'Looks fine' or 'No issues' without listing what was specifically checked (4) Making claims about documentation, APIs, or behavior using phrases like 'per the docs' without quoting the source or showing a URL (5) Skipping items in a multi-item review or assessment (6) Giving a conclusion without showing the work that led to it. If lazy, respond {\"ok\": false, \"reason\": \"what was skipped or done poorly\"}. If thorough, respond {\"ok\": true}."
}
```

**Key design decisions:**
- No `model` field — uses default (Haiku, cheapest/fastest)
- `stop_hook_active: true` handling — auto-passes on retry to prevent infinite loops, unless response is clearly evasive
- Items reframed to be detectable from response text alone (prompt hook only sees `last_assistant_message`, not tool calls)
- Removed "short answer to complex question" — Haiku can't see the user's question, only the response. Replaced with "mentions complexity but doesn't address it"
- Removed "not fetched docs this session" — Haiku can't see tool call history. Replaced with "claims about docs without showing source"

**Key behaviors**:
- `ok: false` → Claude Code blocks the stop and feeds `reason` to Claude as next instruction
- `ok: true` → stop proceeds
- TRIVIAL interactions auto-pass (the prompt instructs Haiku to skip them)
- Uses Haiku (cheapest, fastest model) — ~$0.001 per call, ~1s latency

### Placement

Add as an ADDITIONAL Stop hook entry alongside quality-gate.py. Both fire in parallel on every Stop. quality-gate handles deterministic checks; the prompt hook handles subjective evaluation.

```json
"Stop": [
  { "hooks": [
    { "type": "command", "command": "python .../stop-log.py", "async": true },
    { "type": "command", "command": "python .../notion-capture.py", "async": true }
  ]},
  { "hooks": [
    { "type": "command", "command": "python .../quality-gate.py" }
  ]},
  { "hooks": [
    {
      "type": "prompt",
      "prompt": "...",
      "model": "haiku"
    }
  ]}
]
```

### Cost analysis

- Haiku cost per call: ~$0.001 (25 input tokens/M at $0.25, ~4K tokens per evaluation)
- Calls per session: ~5-20 (one per Claude response)
- Cost per session: ~$0.005-0.020
- Monthly (10 sessions/day): ~$1.50-6.00

Negligible compared to Opus/Sonnet costs for the main conversation.

### Tuning the prompt

Calibrated to avoid false positives:
- **TRIVIAL auto-pass**: greetings, yes/no, simple facts → ok:true
- **Retry auto-pass**: `stop_hook_active: true` → ok:true (unless evasive)
- **6 laziness signals**: all detectable from response text alone (no tool call visibility needed)
- **Severity**: blocks are soft — Claude retries with the `reason` as guidance, and the retry auto-passes via stop_hook_active

### Interaction with quality-gate.py

Both hooks fire on Stop in parallel. If BOTH block, Claude gets two blocking reasons and must address both.

On retry (`stop_hook_active: true`):
- quality-gate.py: guard passes immediately (existing behavior)
- prompt hook: instructed to auto-pass on `stop_hook_active: true` (in the prompt text), unless response is clearly evasive

This prevents infinite loops while still catching truly lazy retries.

### What the prompt hook CAN'T see

The prompt hook receives `last_assistant_message` (text only) — NOT tool calls or transcript. So:
- **CAN catch**: superficial text, unsupported claims, skipped items, conclusions without work
- **CAN'T catch**: fake Bash verification (`echo hello`), not reading files, skipped tool calls
- **Complementary**: quality-gate.py Check 2c handles tool-level laziness; prompt hook handles text-level laziness

## Implementation

### Change 1: Reclassify phrases in quality-gate.py
### Change 2: Add Check 2c + helpers in quality-gate.py
### Change 3: Add prompt-type Stop hook in settings.json

## Verification

### Deterministic checks (via temp script)
1. Edit + `echo hello` → Check 2c blocks
2. Edit + `bash smoke-test.sh` → Check 2c passes
3. "nothing at all" in conversation → no false positive
4. "100% sure" → still blocks
5. All previous 10 quality-gate tests still pass

### Prompt hook (manual observation)
6. Give a complex question, answer shallowly → should block
7. Give a complex question, answer thoroughly → should pass
8. Say "hi" → should pass (trivial)
9. Smoke test: 38/38

## Critical Files

| File | Action |
|------|--------|
| `~/.claude/hooks/quality-gate.py` | **Modify** — phrase reclassification + Check 2c |
| `~/.claude/settings.json` | **Modify** — add prompt-type Stop hook |

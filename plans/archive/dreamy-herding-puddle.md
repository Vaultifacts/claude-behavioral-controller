# Plan: Automatic Effort Level Assessment

## Context

Currently, Claude Code defaults to `claude-sonnet-4-6` for all tasks, and model selection (haiku for simple, opus for hard reasoning) is done manually. The goal is to make Claude automatically assess task complexity on every prompt and switch to the appropriate effort level — without user intervention.

### Key Constraint
**The main session model is fixed at startup** — it cannot be changed mid-conversation. However, there are two high-value places where automatic selection *can* happen:

1. **Subagent spawning** (Agent tool) — Claude can pick `haiku`, `sonnet`, or `opus` dynamically per subtask
2. **UserPromptSubmit hook** — fires before Claude processes each message, can inject a complexity tag that Claude acts on

The effective result: every spawned agent uses the right model automatically, and Claude self-adjusts reasoning depth and effort for the main session accordingly.

---

## Implementation Plan

### Step 1 — Create `task-classifier.py` hook

**File:** `C:\Users\Matt1\.claude\hooks\task-classifier.py`

Heuristic classifier (no API calls) that fires on every user message. It outputs a single injected line that appears in Claude's context before it responds.

**Classification tiers:**

| Tier | Label | Main session behavior | Agent model |
|------|-------|----------------------|-------------|
| 0 | `TRIVIAL` | Minimal reasoning, skip agents | haiku |
| 1 | `SIMPLE` | Light reasoning | haiku |
| 2 | `MODERATE` | Normal reasoning (default) | sonnet |
| 3 | `COMPLEX` | Thorough, multi-step | sonnet |
| 4 | `DEEP` | Maximum reasoning, slow OK | opus |

**Heuristic signals (keyword/pattern matching on the prompt):**
- TRIVIAL: "what is", "list", "show me", single word questions, very short (< 15 words)
- SIMPLE: file reads, quick edits, small searches, "rename", "add comment"
- COMPLEX: "refactor", "migrate", "debug", "why is", multi-file mentions, "design"
- DEEP: "architect", "algorithm", "prove", "analyze all", "optimize performance", "security audit", "explain how X works at a deep level"
- Default: MODERATE

**Output format** (printed to stdout, injected as system context by Claude Code):
```
[task-classifier] Complexity: MODERATE → use sonnet for agents; normal reasoning depth
```

### Step 2 — Register the hook in `settings.json`

Add a `UserPromptSubmit` hook entry:
```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python C:/Users/Matt1/.claude/hooks/task-classifier.py"
          }
        ]
      }
    ]
  }
}
```

### Step 3 — Add decision rules to `~/.claude/CLAUDE.md`

Add a new section `## Effort Level (Auto)` that instructs Claude to:

1. Read the `[task-classifier]` tag injected at the top of each turn
2. Apply the matching behavior:
   - **TRIVIAL/SIMPLE** → respond directly without agents; if agent needed, use `model: "haiku"`
   - **MODERATE** → default behavior; use `model: "sonnet"` for agents
   - **COMPLEX** → be thorough, use multiple agents if needed; use `model: "sonnet"`
   - **DEEP** → maximum reasoning depth; use `model: "opus"` for all agents; think before acting
3. If no tag present, default to MODERATE

Also update the backup list in `stop-log.py` to include `task-classifier.py`.

---

## Files to Modify

| File | Change |
|------|--------|
| `~/.claude/hooks/task-classifier.py` | **Create** — heuristic classifier hook |
| `~/.claude/settings.json` | **Add** `UserPromptSubmit` hook entry |
| `~/.claude/CLAUDE.md` | **Add** `## Effort Level (Auto)` section |
| `~/.claude/hooks/stop-log.py` | **Add** `task-classifier.py` to backup list |

---

## Verification

1. Start a new Claude Code session
2. Ask a trivial question (e.g., "what day is it") — observe `[task-classifier] Complexity: TRIVIAL` in the hook output
3. Ask a complex task (e.g., "refactor the auth system") — observe `COMPLEX` tag
4. Ask Claude to do a task that uses the Agent tool — verify the spawned agent uses the correct model
5. Check `~/.claude/audit-log.md` after session end to confirm `task-classifier.py` was backed up

# Plan: Integration Setup (Items 1–18)

## Context
Setting up all project integrations for Cupid v3.5. Adding MCP servers, LSP, GitHub Actions CI/CD,
headless supervisor, plugin manifest, global Claude settings, and Agent Teams experimental mode.
Last updated: 2026-02-23 MST

## Pre-flight checks
- `.github/` — does NOT exist → will be created
- `.claude/settings.local.json` — exists, needs `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` added to env
- `~/.claude/CLAUDE.md` — already exists with exact requested content → SKIP (no action)
- `docs/prd.md` — needs `enable-mcp-live-test: true` (currently false) per Item 11

## Files to Create (8 new)
1. `.mcp.json`
2. `.lsp.json`
3. `.github/workflows/claude-review.yml`
4. `.github/workflows/claude-scheduled.yml`
5. `.claude/scripts/supervisor.sh`
6. `.claude-plugin/plugin.json`
7. `~/.claude/settings.json`
8. `~/.claude/keybindings.json`

## Files to Update (2 existing)
9. `.claude/settings.local.json` — add `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` to env section
10. `docs/prd.md` — flip `enable-mcp-live-test: false` → `true`

---

## Integration 1: `.mcp.json` (project root)

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"],
      "capabilities": ["vision"]
    },
    "notion": {
      "command": "npx",
      "args": ["@notionhq/notion-mcp-server"],
      "env": {
        "NOTION_API_KEY": "${NOTION_API_KEY}"
      }
    }
  }
}
```

---

## Integration 2: `.lsp.json` (project root)

```json
{
  "python": {
    "command": "pyright-langserver",
    "args": ["--stdio"],
    "extensionToLanguage": { ".py": "python" }
  },
  "typescript": {
    "command": "typescript-language-server",
    "args": ["--stdio"],
    "extensionToLanguage": { ".ts": "typescript", ".tsx": "typescriptreact", ".js": "javascript", ".jsx": "javascriptreact" }
  }
}
```

---

## Integration 3: `.github/workflows/claude-review.yml`

```yaml
name: Claude Code Review
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]

jobs:
  claude-review:
    if: |
      contains(github.event.comment.body, '@claude') &&
      (github.event_name == 'pull_request_review_comment' || github.event.issue.pull_request)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          claude_args: "--max-turns 10"
```

---

## Integration 4: `.github/workflows/claude-scheduled.yml`

```yaml
name: Claude Scheduled Maintenance
on:
  schedule:
    - cron: "0 6 * * *"   # Daily 6am UTC: health + audit rotation
    - cron: "0 6 * * 1"   # Weekly Monday: prune + dep check
  workflow_dispatch:        # Manual trigger
jobs:
  claude-maintenance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          claude_args: >-
            --allowedTools "Read,Write,Edit,Bash,Grep,Glob"
            --max-turns 20
            --output-format json
          prompt: |
            Run scheduled maintenance:
            1. /health-dashboard all
            2. If Monday: /prune-archives all and check outdated deps
            3. Append summary to docs/audit-log.md
            4. If any RED flags: create GitHub issue with findings
```

---

## Integration 5: `.claude/scripts/supervisor.sh`

```bash
#!/usr/bin/env bash
# .claude/scripts/supervisor.sh – Headless supervisor for Claude Code
# Usage: bash .claude/scripts/supervisor.sh [session-id]

SESSION_ID="${1:-}"
POLL_INTERVAL=300  # 5 minutes
MAX_FAILURES=3
FAILURE_COUNT=0
COST_BUDGET="${CLAUDE_COST_BUDGET:-5.00}"  # Default $5 budget

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a docs/audit-log.md; }

log "Supervisor started (PID: $)"

while true; do
  HEALTH=$(claude -p "Run /health-dashboard all" --output-format json ${SESSION_ID:+--resume $SESSION_ID} 2>/dev/null)

  if echo "$HEALTH" | grep -qiE 'FAIL|STUCK|CATASTROPHIC'; then
    FAILURE_COUNT=$((FAILURE_COUNT + 1))
    log "ALERT: Health check failed ($FAILURE_COUNT/$MAX_FAILURES)"

    if [ $FAILURE_COUNT -ge $MAX_FAILURES ]; then
      log "CRITICAL: Max failures reached – stopping supervisor"
      claude -p "Save all state to scratchpad and commit" --output-format json ${SESSION_ID:+--resume $SESSION_ID} 2>/dev/null
      log "Session state saved. Supervisor exiting."
      exit 1
    fi
  else
    FAILURE_COUNT=0
    log "Health check passed"
  fi

  # Cost budget enforcement (Item 20)
  COST_OUT=$(claude -p "Output JSON only: {\"cost\": <session_usd_float>}" --output-format json 2>/dev/null || echo '{}')
  CUR_COST=$(echo "$COST_OUT" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('cost', d.get('result', '0')))" 2>/dev/null || echo "0")
  log "Session cost estimate: \$CUR_COST (budget: \$COST_BUDGET)"

  if python3 -c "import sys; sys.exit(0 if float('${CUR_COST:-0}') < float('$COST_BUDGET') else 1)" 2>/dev/null; then
    :  # within budget
  else
    log "BUDGET EXCEEDED: cost \$CUR_COST >= \$COST_BUDGET – pausing supervisor"
    claude -p "Save state – cost budget exceeded" --output-format json ${SESSION_ID:+--resume $SESSION_ID} 2>/dev/null
    exit 2
  fi

  sleep $POLL_INTERVAL
done
```

---

## Integration 6: `.claude-plugin/plugin.json`

```json
{
  "name": "claude-workflow-v3",
  "version": "3.4.0",
  "description": "Full autonomous Claude Code workflow v3.4 with testing, safety, self-improvement, and cost controls",
  "skills": [
    ".claude/skills/context-reset/SKILL.md",
    ".claude/skills/update-prd/SKILL.md",
    ".claude/skills/evolve-system/SKILL.md",
    ".claude/skills/toggle-autonomy/SKILL.md",
    ".claude/skills/self-suggest-improvements/SKILL.md",
    ".claude/skills/rollback-to-milestone/SKILL.md",
    ".claude/skills/health-dashboard/SKILL.md",
    ".claude/skills/generate-docs/SKILL.md",
    ".claude/skills/prune-archives/SKILL.md",
    ".claude/skills/self-test/SKILL.md",
    ".claude/skills/scaffold/SKILL.md"
  ],
  "agents": [
    ".claude/agents/security-reviewer.md",
    ".claude/agents/test-generator.md",
    ".claude/agents/code-reviewer.md"
  ],
  "hooks": ".claude/settings.json",
  "mcp": ".mcp.json",
  "lsp": ".lsp.json"
}
```

---

## Integration 7a: `~/.claude/settings.json`

Path: `C:\Users\Matt1\.claude\settings.json`

```json
{
  "default_model": "claude-sonnet-4-6",
  "theme": "dark",
  "autoUpdatesChannel": "latest",
  "permissions": {
    "defaultMode": "acceptEdits"
  }
}
```

---

## Integration 7b: `~/.claude/keybindings.json`

Path: `C:\Users\Matt1\.claude\keybindings.json`

```json
[
  {"key": "ctrl+k", "command": "clearTerminal"},
  {"key": "ctrl+shift+r", "command": "retry"},
  {"key": "ctrl+shift+c", "command": "compact"}
]
```

---

## Integration 8: `.claude/settings.local.json` update (Agent Teams)

Add to `env` section:
```json
"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
```

Full updated file:
```json
{
  "default_model": "claude-sonnet-4-6",
  "alwaysThinkingEnabled": true,
  "autoUpdatesChannel": "latest",
  "fileSuggestion": true,
  "env": {
    "NODE_ENV": "development",
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "0",
    "ANTHROPIC_BASE_URL": "",
    "CLAUDE_CODE_LOG_LEVEL": "info",
    "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "",
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "statusLine": {
    "type": "command",
    "command": "branch=$(git branch --show-current 2>/dev/null || echo 'no-git'); dirty=$(git status --short 2>/dev/null | wc -l | tr -d ' '); echo \"$branch | ${dirty} dirty\""
  },
  "spinnerVerbs": {
    "mode": "append",
    "verbs": [
      "Analyzing",
      "Testing",
      "Building",
      "Reviewing",
      "Securing"
    ]
  },
  "outputStyle": "Explanatory"
}
```

---

## Integration 9: `~/.claude/CLAUDE.md`

**SKIP** — file already exists at `C:\Users\Matt1\.claude\CLAUDE.md` with the exact content requested.

---

## Integration 10: `docs/prd.md` — flip `enable-mcp-live-test`

Single edit: `enable-mcp-live-test: false` → `enable-mcp-live-test: true`

---

## Summary Table

| # | File | Action |
|---|------|--------|
| 1 | `.mcp.json` | Create |
| 2 | `.lsp.json` | Create |
| 3 | `.github/workflows/claude-review.yml` | Create (+ folder) |
| 4 | `.github/workflows/claude-scheduled.yml` | Create |
| 5 | `.claude/scripts/supervisor.sh` | Create (+ folder) |
| 6 | `.claude-plugin/plugin.json` | Create (+ folder) |
| 7a | `~/.claude/settings.json` | Create |
| 7b | `~/.claude/keybindings.json` | Create |
| 8 | `.claude/settings.local.json` | Update (add Agent Teams env) |
| 9 | `~/.claude/CLAUDE.md` | Skip (already correct) |
| 10 | `docs/prd.md` | Update (mcp-live-test: true) |

Items 10–18 in the request (Playwright install, Notion .env, Vision caps, headless patterns, Agent SDK, autonomy prefs, timestamps) are documentation/runtime actions — no files to write for those.

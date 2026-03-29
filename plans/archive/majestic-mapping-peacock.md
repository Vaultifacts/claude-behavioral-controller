# Plan: Post-Setup Cleanup — Fix Stale Config Entries

## Context
The full global dev environment setup (timestamps, MCP servers, hooks, agents, tools) was completed in the previous session. Three stale entries now contradict actual system state and will confuse Claude in future sessions.

## Files to Modify

### 1. `~/.claude/settings.json` — Fix SessionStart hook message (line 86)

**Current (wrong):**
```
'Session started. Platform: Windows 10 + Git Bash. Node 24, Python 3.13 (PYTHONIOENCODING=utf-8), Git 2.39. No jq — use Python for JSON parsing. Prefer autonomous mode.'
```

**Replace with:**
```
'Session started. Platform: Windows 10 + Git Bash. Node 24, Python 3.13 (PYTHONIOENCODING=utf-8), Git 2.39. jq available. prettier + eslint installed globally. Prefer autonomous mode.'
```

### 2. `~/.claude/CLAUDE.md` — Fix two outdated rules

**Line 16** (wrong): `` `jq` is NOT installed — use Python inline for JSON parsing in scripts ``
→ `` `jq` is installed globally (winget) — available in bash and PS7 ``

**Line 17** (wrong): `No global prettier or eslint — use \`npx\` prefix`
→ `prettier and eslint are installed globally — call directly without \`npx\``

## User Action Required
`~/.claude/.env` Postgres connection string still contains `[YOUR-PASSWORD]` literal placeholder. User must replace it with the actual Supabase database password from the project creation step.

## Verification
After edits, restart a new Claude Code session. The SessionStart hook output should say "jq available" instead of "No jq".

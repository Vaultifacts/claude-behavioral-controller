# Fix: statusLine settings.json schema error

## Context
Claude Code fails to load `.claude/settings.json` because `statusLine` on line 80 is a bare string (`".claude/statusline.sh"`) but the schema requires an object. **Because the entire file is skipped on error**, all permissions, hooks, deny rules, and memory settings are currently inactive.

## Change
**File:** `vaultlister-3/.claude/settings.json` (line 80)

Replace:
```json
"statusLine": ".claude/statusline.sh",
```

With:
```json
"statusLine": {
  "type": "command",
  "command": "bash .claude/statusline.sh"
},
```

## Verification
1. Restart Claude Code in the vaultlister-3 directory
2. Confirm no "Settings Error" prompt appears
3. Confirm status line renders in the TUI
4. Confirm hooks still fire (e.g., the Stop hook session-end checklist)

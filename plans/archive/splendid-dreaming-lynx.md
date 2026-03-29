# Plan: Write API Keys to Gitignored Files

## Context
User wants API keys written to the appropriate gitignored local files for use by Claude Code and the project backend.

## Files to Write

### 1. `backend/.env` (create if missing — gitignored)
```
ANTHROPIC_API_KEY=<from chat>
NOTION_API_KEY=<from chat>
NOTION_PAGE_ID=your-page-id-here
```

### 2. `.claude/settings.local.json` (already exists — update env section)
Add to the existing `"env"` block:
```
"ANTHROPIC_API_KEY": "<from chat>",
"NOTION_API_KEY": "<from chat>"
```

## Safety
- Both files are gitignored — keys will not be committed
- Keys will not appear in any logs or responses
- No other files touched

## Verification
- Confirm `backend/.env` exists with both keys
- Confirm `settings.local.json` env block has both keys

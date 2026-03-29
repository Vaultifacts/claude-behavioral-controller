---
name: Notion Auto-Capture Hook
description: Autonomous Stop hook that writes session insights to 4 Notion databases (Prompt Library, Lessons Learned, Glossary, External References)
type: reference
last_reviewed: 2026-03-22
---

## Setup
- **Hook**: `~/.claude/hooks/notion-capture.py` — fires on every Stop event
- **Token**: `NOTION_TOKEN` in `~/.claude/.env`
- **Log**: `~/.claude/notion-capture.log`
- **Registered in**: `~/.claude/settings.json` → `hooks.Stop[0].hooks[1]`

## Database IDs
- Prompt Library: `2e1b19b7-364b-4255-8515-1ddc0896b967`
- Lessons Learned: `31faa7d9-0a30-40f3-8c9c-e9939c003257`
- Glossary: `fa4bae81-9eaa-4df7-aad4-2b4ac97426a2`
- External References: `343fb652-e9fb-4a84-9d0f-05130a965520`

## Tuning
- `MIN_USER_MESSAGES = 3` — skip sessions with fewer messages
- `MIN_DURATION_SECS = 30` — skip very short sessions
- `MAX_PER_DB = 3` — cap inserts per database per session
- `COMMON_WORDS` set — blocklist for glossary false positives
- Skip list in `extract_prompt_library` — excludes `/plans/`, `/memory/`, `/hooks/`

## Contamination filters added 2026-03-23
- Lessons: sentences containing `|` are skipped (table rows/fragments)
- Lessons: reasoning starters filtered (`now let me`, `let me check`, `the issue is likely`, etc.)
- Glossary: ACRONYM_EXPANSION requires multi-word expansion (single-word like "Cosmetic" blocked)
- Glossary: severity-label definitions blocked (cosmetic/trivial/low/medium/high + impact variants)

## Project field
- **NOT a bug** — Project field is correctly blank for home-directory (~) sessions (Claude setup work)
- Project IS set for actual project sessions (e.g., VaultLister 3.0 session ab73e862 confirmed ✓)
- The review-captures.log "bug" was a misdiagnosis — those entries were from ~/.claude maintenance sessions

## How to apply
- Check `~/.claude/notion-capture.log` to see what's being captured
- Use `/review-captures` command to inspect recent entries across all 4 databases
- Edit `COMMON_WORDS` in the script to blocklist noisy glossary terms
- Set `NOTION_CAPTURE_DRY_RUN=1` env var to test without writing to Notion

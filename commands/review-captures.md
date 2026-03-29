Review the most recent auto-captured entries across all Notion databases and the capture log.

1. Read the last 20 lines of `~/.claude/notion-capture.log` to show recent capture activity
2. Query each database (sorted by created_time descending, limit 5) using the Notion API:
   - Lessons Learned (DB: 31faa7d9-0a30-40f3-8c9c-e9939c003257) — show Takeaway + Category + Project
   - External References (DB: 343fb652-e9fb-4a84-9d0f-05130a965520) — show Name + URL + Project
   - Glossary (DB: fa4bae81-9eaa-4df7-aad4-2b4ac97426a2) — show Term + Definition + Project
   - Prompt Library (DB: 2e1b19b7-364b-4255-8515-1ddc0896b967) — show Name + Type + Project
   - Browser Navigation (DB: 3249f0c81de6814fa81dde0c015d2e1c) — show Action + App
3. Flag any entries that look like false positives or duplicates
4. Suggest any tuning changes to the notion-capture.py hook if issues are found

Use the NOTION_TOKEN from ~/.claude/.env for API calls. Use Notion-Version: 2022-06-28.

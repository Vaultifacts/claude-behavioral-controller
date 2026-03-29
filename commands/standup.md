Generate a daily standup report by pulling data from multiple sources.

## Data Sources

1. **Recent Claude sessions** — Read the last 5 entries from `~/.claude/audit-log.md` to summarize what was worked on
2. **Notion Sprint Board tasks** — Detect the current project from the working directory (git root basename), find its Notion dashboard page in the Projects DB, then query that project's Sprint / Task Board for:
   - Tasks with Status "In Progress" (what I'm working on)
   - Tasks with Status "Done" and last_edited_time in the past 24 hours (what I completed)
   - Tasks with Status "Blocked" (blockers)
3. **Git commits** — Run `git log --oneline --since="yesterday" --all` in the current directory for recent commits
4. **Auto-captured insights** — Read the last 10 lines of `~/.claude/notion-capture.log` for recent auto-captures

## Output Format

```
## Standup — [today's date]

### Done (last 24h)
- [completed tasks and commits]

### In Progress
- [active tasks]

### Blocked / Needs Attention
- [blocked tasks or issues]

### Insights Captured
- [count] new entries auto-captured to Notion databases

### Today's Focus
- [suggest top priority based on Sprint Board priority + due dates]
```

## How to find the Sprint Board dynamically

1. Detect project name: `git rev-parse --show-toplevel` → basename
2. Search Projects DB for the project:
```bash
TOKEN=$(grep '^NOTION_TOKEN=' ~/.claude/.env | cut -d'"' -f2)
curl -s -X POST "https://api.notion.com/v1/databases/41db59a2-d31e-4383-9b42-b5cdefb9a5a9/query" \
  -H "Authorization: Bearer $TOKEN" -H "Notion-Version: 2022-06-28" -H "Content-Type: application/json" \
  -d '{"filter":{"property":"Name","title":{"contains":"PROJECT_NAME"}}}' | jq -r '.results[0].properties."Dashboard URL".url'
```
3. Extract the page ID from the Dashboard URL (last 32 hex chars)
4. Query that page's children for the Sprint / Task Board:
```bash
curl -s "https://api.notion.com/v1/blocks/PAGE_ID/children?page_size=100" \
  -H "Authorization: Bearer $TOKEN" -H "Notion-Version: 2022-06-28" | \
  jq -r '.results[] | select(.type=="child_database" and (.child_database.title | test("Sprint"))) | .id'
```
5. Query that DB for task statuses.

If no project is detected (home directory), show a cross-project summary from the audit log only.

Use NOTION_TOKEN from ~/.claude/.env. Use Notion-Version: 2022-06-28. Be concise.

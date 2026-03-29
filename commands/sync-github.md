Sync GitHub issues from a repository into the Sprint / Task Board database in the active Notion project.

1. Ask which GitHub repo to sync (or use the current directory's git remote)
2. Use `gh issue list --state open --json number,title,labels,assignees,state,body --limit 20` to fetch open issues
3. For each issue, check if it already exists in the Sprint / Task Board (dedup on task name containing the issue number like "#123")
4. For new issues:
   - Task Name: "#<number> <title>"
   - Status: map GitHub labels → Notion status (bug → "To Do", enhancement → "Backlog", etc.), default "Backlog"
   - Priority: map labels (priority:critical → "P0–Critical", priority:high → "P1–High", etc.), default "P2–Medium"
   - Tags: copy GitHub labels as multi-select tags
5. Report: "Synced X new issues, Y already existed, Z total open"

Use the Sprint / Task Board database ID from the active project. If unsure which project, ask. Use NOTION_TOKEN from ~/.claude/.env and gh CLI for GitHub.

Create a new project from the template and register it in the Projects database.

## Input
- Project name: $ARGUMENTS (ask if not provided)

## IDs
- Template page: 3239f0c8-1de6-818c-928d-e49911e71e51 ("Project Template – Duplicate Me")
- Project Workspace: 3239f0c8-1de6-80d3-9474-ffca244eec4e
- Projects DB: 41db59a2-d31e-4383-9b42-b5cdefb9a5a9
- Auth: NOTION_TOKEN from ~/.claude/.env (NOT MCP tools — they can't access Project Workspace)

## Steps

### 1. Duplicate the template via browser
- Load browser tools via ToolSearch (tabs_context_mcp, navigate, computer, find)
- Navigate to the template page: https://www.notion.so/Project-Template-Duplicate-Me-3239f0c81de6818c928de49911e71e51
- Click the ••• menu (top right) → "Duplicate"
- Wait for the duplicate to load (new tab or same tab)
- Get the new page URL from the browser

### 2. Rename the page via API
```bash
TOKEN=$(grep '^NOTION_TOKEN=' ~/.claude/.env | cut -d'"' -f2)
curl -s -X PATCH "https://api.notion.com/v1/pages/NEW_PAGE_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{"properties":{"title":{"title":[{"text":{"content":"PROJECT_NAME"}}]}}}'
```

### 3. Register in the Projects database via API
```bash
curl -s -X POST "https://api.notion.com/v1/pages" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Notion-Version: 2022-06-28" \
  -H "Content-Type: application/json" \
  -d '{
    "parent":{"database_id":"41db59a2-d31e-4383-9b42-b5cdefb9a5a9"},
    "properties":{
      "Name":{"title":[{"text":{"content":"PROJECT_NAME"}}]},
      "Status":{"select":{"name":"Planning"}},
      "Start Date":{"date":{"start":"TODAY"}},
      "Dashboard URL":{"url":"PAGE_URL"}
    }
  }'
```

### 4. Stamp Notion URL into local CLAUDE.md
If a local `CLAUDE.md` exists in the current directory (e.g., created by `newproject` shell function):
```bash
sed -i "s|%%NOTION_URL%%|PAGE_URL|" ./CLAUDE.md
```
If no local CLAUDE.md exists and the user hasn't said "Notion only", create basic local scaffolding:
```bash
cp ~/.claude/templates/CLAUDE.project.md ./CLAUDE.md
sed -i "s/PROJECT_NAME/PROJECT_NAME/g" ./CLAUDE.md
sed -i "s|%%NOTION_URL%%|PAGE_URL|" ./CLAUDE.md
```

### 5. Filter linked views by project (optional, do when entries exist)
For each of the 4 global linked views (Prompt Library, Lessons Learned, Glossary, External References):
1. Click the filter icon (≡) on the linked view toolbar
2. Select "Project"
3. Set condition to "contains" → select "PROJECT_NAME"
4. Click "Save for everyone"

Note: This only works after sessions have run in the project and the notion-capture hook has tagged entries. Skip this step on initial setup and do it later when entries exist.

### 6. Output
Print: "Created project **PROJECT_NAME** — PAGE_URL"
If local CLAUDE.md was updated, confirm the Notion URL was stamped.

## Global default
This command runs automatically for every new project unless the user explicitly says "no Notion" or "skip Notion". This is a global rule — see `~/.claude/memory/feedback_notion_default.md`.

## Why browser duplication?
The Notion API cannot duplicate pages with inline databases. `child_database` blocks create new databases when appended, but don't copy schemas or properties from the template. Browser duplication preserves everything: database schemas, relations, rollups, views, and content.

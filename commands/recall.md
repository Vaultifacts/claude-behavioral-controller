Query all Notion knowledge bases on demand. Use when you need to check past lessons, glossary terms, external references, prompts, or browser patterns mid-session.

## Input
- Query: $ARGUMENTS (optional — search term to filter results)
- If no query provided, show recent entries across all databases

## How to execute

### 1. Determine the current project
Use the current working directory to detect the project name (git root basename).

### 2. Query Notion databases via API
```bash
TOKEN=$(grep '^NOTION_TOKEN=' ~/.claude/.env | cut -d'"' -f2)
```

**Lessons Learned** (DB: `31faa7d9-0a30-40f3-8c9c-e9939c003257`):
```bash
curl -s -X POST "https://api.notion.com/v1/databases/31faa7d9-0a30-40f3-8c9c-e9939c003257/query" \
  -H "Authorization: Bearer $TOKEN" -H "Notion-Version: 2022-06-28" -H "Content-Type: application/json" \
  -d '{"sorts":[{"property":"Date","direction":"descending"}],"page_size":10}' | \
  jq '[.results[] | {takeaway: .properties.Takeaway.title[0].plain_text, category: .properties.Category.select.name, project: [.properties.Project.multi_select[].name] | join(", "), date: .properties.Date.date.start}]'
```

**Glossary** (DB: `fa4bae81-9eaa-4df7-aad4-2b4ac97426a2`):
If a search term is provided, filter by term name:
```bash
curl -s -X POST "https://api.notion.com/v1/databases/fa4bae81-9eaa-4df7-aad4-2b4ac97426a2/query" \
  -H "Authorization: Bearer $TOKEN" -H "Notion-Version: 2022-06-28" -H "Content-Type: application/json" \
  -d '{"filter":{"property":"Term","title":{"contains":"SEARCH_TERM"}},"page_size":10}' | \
  jq '[.results[] | {term: .properties.Term.title[0].plain_text, definition: .properties.Definition.rich_text[0].plain_text}]'
```

**External References** (DB: `343fb652-e9fb-4a84-9d0f-05130a965520`):
```bash
curl -s -X POST "https://api.notion.com/v1/databases/343fb652-e9fb-4a84-9d0f-05130a965520/query" \
  -H "Authorization: Bearer $TOKEN" -H "Notion-Version: 2022-06-28" -H "Content-Type: application/json" \
  -d '{"page_size":10}' | \
  jq '[.results[] | {name: .properties.Name.title[0].plain_text, category: .properties.Category.select.name, url: .properties.URL.url, notes: .properties.Notes.rich_text[0].plain_text}]'
```

### 3. Also query these databases

**Prompt Library** (DB: `2e1b19b7-364b-4255-8515-1ddc0896b967`):
Search by Name containing the term. Show name, type, success rate.

**Browser Navigation Patterns** (DB: `3249f0c81de6814fa81dde0c015d2e1c`):
Search by Action containing the term. Show action, app, steps.

### 4. Filter by search term
If $ARGUMENTS is provided, search ALL 5 databases for entries containing the term.
If no arguments, show the most recent entries from each database.

### 5. Output
Format results as a concise summary grouped by database.

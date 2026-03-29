# /health — Notion Workspace Health Check

Run a health check on the Notion workspace. Checks for contamination, schema drift, empty required fields, and pipeline issues.

## Checks to perform

### 1. Projects DB Completeness
Query Projects DB (`41db59a2-d31e-4383-9b42-b5cdefb9a5a9`). For each non-archived entry, verify:
- Name is set
- Status is set (not null)
- Start Date is set
- Dashboard URL is set and points to a valid page
- Tech Stack has at least 1 tag
- Last Activity is set

Flag any entry with missing fields.

### 2. ADR Contamination Check
For the template ADR DB (`7572571b-dccb-42c0-9656-cfc4c09e9616`), query row count. If > 0, flag — this DB should be empty (notion-capture.py ADR routing is disabled). Also check each active project's ADR DB for suspiciously high row counts (>20 rows is likely contamination).

### 3. Global DB Health
For each of the 5 global DBs, check:
- Row count (report as info)
- Whether "Project" multi-select property exists
- Sample the 3 most recent entries and check for obviously bad data (e.g., tags with >30 chars, empty titles)

### 4. Prompt Library Tag Audit
Query Prompt Library, extract all unique tag values. Flag any tag that:
- Contains more than 3 words
- Contains special characters other than `-` and `_`
- Is longer than 25 characters

### 5. Capture Log Check
Read last 10 lines of `~/.claude/notion-capture.log`. Report:
- Last capture timestamp
- Any SKIP or ERROR entries
- Total captures in the last 24 hours

### 6. Hook Registration Check
Read `~/.claude/settings.json` and verify all expected hooks are registered:
- SessionStart: notion-recall.py
- UserPromptSubmit: task-classifier.py
- PreToolUse: validate-bash.sh, block-secrets.py, permission-guard.py
- PostToolUse: context-watch.py
- Stop: stop-log.py, notion-capture.py

### Output
Print a health report with status indicators:
- OK: everything looks good
- WARN: minor issues found
- FAIL: critical issues requiring immediate attention

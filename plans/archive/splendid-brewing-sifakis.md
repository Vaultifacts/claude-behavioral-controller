# Plan: P8-6 Final Sign-Off

## Context
VaultLister 3.0 checklist is 49/57 complete (86%). The 8 remaining items split into two groups:
- **Can do now:** P8-4 (load test), P8-6 (sign-off review itself)
- **Externally blocked:** P1-4, P3-1–P3-5, P5-1–P5-6, P6-6, P7-4

Goal: run the load test (P8-4), write a completion summary, check P8-6 in Notion, and document the blocked items clearly so handoff is clean.

---

## Remaining Items Status

| Item | Status | Reason |
|------|--------|--------|
| P8-4 Load test | **Can do** | Run `scripts/load-test.js` locally |
| P8-6 Sign-off | **Can do** | Write summary, check Notion |
| P7-4 OpenClaw | **Needs user** | Requires Telegram/Discord channel ID |
| P6-6 Poshmark live offer | **Needs user** | Requires real incoming buyer offer ≥80% |
| P3-1–P3-5 eBay | **Needs user** | eBay production credentials must be active |
| P1-4 Etsy creds | **External** | Waiting on Etsy app approval |
| P5-1–P5-6 Etsy | **External** | All blocked on same Etsy approval |

---

## Steps

### 1. P8-4 — Load Test
Run `scripts/load-test.js` with `CONCURRENT_USERS=20 REQUESTS_PER_USER=10` against localhost:3000.
- Server must be running (`bun run dev` is already up)
- Capture p50/p95/p99 response times and error rate
- Pass threshold: p95 < 500ms, error rate < 1%
- Check P8-4 in Notion immediately after

### 2. P8-6 — Sign-Off Summary
Update `memory/STATUS.md` with:
- Final completion count (49/57, 86%)
- Clear list of 6 blocked/pending items with prerequisite for each
- "Functionally complete" declaration for all non-blocked phases

### 3. Notion Updates
- Check P8-4 in Notion (after load test passes)
- Check P8-6 in Notion
- Both checked before commit

### 4. Commit
`chore(release): P8-6 final sign-off + P8-4 load test baseline`

---

## Files to Modify
- `memory/STATUS.md` — final completion summary

## Key Files (read-only reference)
- `scripts/load-test.js` — load test runner
- `memory/STATUS.md` — current state doc

---

## Verification
1. Load test exits 0 with p95 < 500ms
2. STATUS.md updated with final state
3. P8-4 + P8-6 both checked in Notion
4. Commit created

---

## Old Plan (archived below — Notion AI Control System)

---

## Files to Create

| File | Purpose |
|------|---------|
| `tools/requirements.txt` | Python deps: requests, charset-normalizer, python-dotenv |
| `tools/notion_config.py` | Load .env, expose config constants |
| `tools/notion_client.py` | Robust Notion HTTP client with retry logic |
| `tools/verify_permissions.py` | Check integration access to all required resources |
| `tools/notion_sync.py` | Sync repo metrics to Notion (non-destructive, PATCH-only) |
| `tools/notion_feedback.py` | Read Notion, produce `generated/notion_feedback.json` |
| `tools/task_orchestrator.py` | Score and select safest next task → `generated/next_task.json` |
| `tools/notion_ai_log.py` | Log AI execution runs to Notion database |
| `tools/post-commit.hook` | Shell hook calling notion_sync.py, never blocks commits |
| `tools/NOTION_WORKFLOW.md` | Full workflow documentation + troubleshooting |

## Files to Modify

| File | Change |
|------|--------|
| `.gitignore` | Add `generated/` entry |

---

## Implementation Details

### `.gitignore`
Append `generated/` after the existing `data/` ignore block.

### `tools/requirements.txt`
```
requests>=2.32
charset-normalizer>=3.0
python-dotenv>=1.0
```

### `tools/notion_config.py`
- Call `load_dotenv()` at module import
- Read: `NOTION_SYNC_ENABLED`, `NOTION_INTEGRATION_TOKEN`, `NOTION_MAIN_PAGE_ID`, `NOTION_CHECKLIST_PAGE_ID`
- Hardcode token and page IDs as fallback defaults per spec:
  - token: `REDACTED_NOTION_TOKEN`
  - MAIN_PAGE_ID: `2fc3f0ecf38280ad9128f7ca8b6d4704`
  - CHECKLIST_PAGE_ID: `31d3f0ecf3828010b878de03ac961fc9`
- Expose `NOTION_VERSION = "2022-06-28"`
- Expose `SYNC_ENABLED` boolean; if False, scripts print message and `sys.exit(0)`

### `tools/notion_client.py`
- Class `NotionClient`
- Central `_request(method, path, **kwargs)` method
- Base URL: `https://api.notion.com/v1/`
- Headers: `Authorization: Bearer <token>`, `Notion-Version`, `Content-Type: application/json`
- Timeout: 30s
- Retry on: 408, 409, 429, 500, 502, 503, 504
- Max 3 retries; backoff 1s → 2s → 4s
- Respect `Retry-After` header if present
- Raise `RuntimeError(f"{method} {path} → {status}: {body}")` on final failure
- Methods: `get_page`, `get_block_children`, `append_block_children`, `update_block`, `search`, `create_page`, `create_database`, `query_database`

### `tools/verify_permissions.py`
- Check access to: root page, checklist page, health dashboard, gap audit database
- Print formatted table: `Resource | ID | Status`
- If inaccessible: print exact sharing instructions ("Share the page with integration 'VaultLister Sync'")
- Exit 0 on all pass, exit 1 on any failure
- CLI: `python tools/verify_permissions.py`

### `tools/notion_sync.py`
Auto-detect repo metrics:
- Release version: from `package.json` `.version`
- Task counts: from `memory/STATUS.md` parsing
- Test counts: from `memory/STATUS.md` (E2E pass/fail, unit pass/fail)
- Commit stats: from `git log` (last commit hash, message, date)
- Any metric that fails to detect: skip gracefully with warning

Block matching strategy:
- Match by heading text or row label anchor — never by position index
- PATCH/update existing blocks; never recreate or duplicate
- If block label not found: log warning, continue safely

CLI options:
- `--dry-run`: print what would be updated, no API calls
- `--audit`: print full block tree of Notion page
- API failure: print warning, exit 0 (never block commits)

### `tools/notion_feedback.py`
Read Notion workspace:
- Checklist page: Layer 1 completion %, Layer 3 active priorities, blockers
- Gap audit database: domain gap counts, severity breakdown

Output `generated/notion_feedback.json`:
```json
{
  "completion_status": { "layer1_percent": 0, "total_items": 0, "completed_items": 0 },
  "active_priorities": [],
  "blockers": [],
  "gap_summary": {},
  "high_severity_domains": [],
  "timestamp": "ISO-8601"
}
```
CLI: `python tools/notion_feedback.py` (optional `-v` for verbose)

### `tools/task_orchestrator.py`
Read `generated/notion_feedback.json`
Score each active priority:
- Design/Documentation/Strategy → 90
- Definition/Metrics → 75
- Testing/Harness → 70
- Refactor → 50
- Large system change → 30

Skip tasks that are: blocked, high risk, unbounded.
Tie-break: priority → risk → impact → Notion order.

Output `generated/next_task.json`:
```json
{
  "selected_task": { "title": "", "score": 0, "rationale": "" },
  "all_scored": [],
  "timestamp": "ISO-8601"
}
```
CLI: `python tools/task_orchestrator.py` (optional `-v`)

### `tools/notion_ai_log.py`
Database title: `AI Execution Log`
Location: under root page

Resolution order:
1. Read `generated/.ai_log_db_id`
2. Search Notion by title
3. Create only if absent

Cache DB ID to `generated/.ai_log_db_id`

Database fields: Task (title), Status (select), Duration (number), Timestamp (date), Notes (rich text)

CLI: `python tools/notion_ai_log.py --task "..." --status "..." --duration 30 --notes "..."`

### `tools/post-commit.hook`
Standalone reference hook file (not a replacement):
```sh
#!/bin/sh
if [ -z "$NOTION_INTEGRATION_TOKEN" ]; then
  exit 0
fi
command -v python >/dev/null 2>&1 || exit 0
python tools/notion_sync.py 2>&1 || true
```

**Important:** `.husky/post-commit` already has 75 lines handling STATUS.md logging and Bot commit auto-review. Do NOT replace it.

Install instructions (append to existing hook):
```sh
cat tools/post-commit.hook >> .husky/post-commit
```
Or manually append the 5-line Notion block at the end of `.husky/post-commit` before the final empty line.

### `tools/NOTION_WORKFLOW.md`
Full workflow diagram, setup instructions, env var reference, troubleshooting section.

---

## `generated/` Directory
- Create `generated/.gitkeep` so the directory is tracked but contents are ignored
- `.gitignore` entry: `generated/` (but NOT `generated/.gitkeep`)

Actually: since `generated/` goes in `.gitignore`, just ensure scripts create it with `os.makedirs("generated", exist_ok=True)` at runtime.

---

## Verification Steps (after implementation)
1. `python tools/verify_permissions.py` — check all Notion resource access
2. `python tools/notion_sync.py --dry-run` — confirm metric detection, no API calls
3. `python tools/notion_sync.py` — live sync to Notion
4. `python tools/notion_feedback.py -v` — read feedback, produce JSON
5. `python tools/task_orchestrator.py -v` — score tasks, produce next_task.json

All scripts must exit 0 even on API failure (non-blocking).

---

## Critical Constraints
- Never block commits (all scripts `|| true` or exit 0 on failure)
- Never duplicate blocks (match by label, not position)
- Never recreate existing pages
- `generated/` added to `.gitignore`
- `.env` never committed
- Existing `.husky/post-commit` must be extended, not replaced

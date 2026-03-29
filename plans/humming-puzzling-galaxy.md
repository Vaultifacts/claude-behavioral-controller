# Gmail Auto-Labeler: Local AI-Powered Email Classification

## Context
Matt wants automated, AI-powered labeling for his Gmail account (vaultifacts@gmail.com, ~15.7K emails). Key constraints: **zero cost**, **maximum privacy** (nothing leaves his machine), **fully autonomous** (no manual approval steps), **never delete anything**. He has an NVIDIA RTX 5070 (12GB VRAM), Python 3.13, and wants weekly scheduled runs.

## Architecture

```
Windows Task Scheduler (weekly, Interactive logon, StartWhenAvailable)
  └→ bash.exe -c "..." (matches existing task pattern on this machine)
       ├→ Health check: Ollama running? If not, start it + wait
       └→ Python (venv): gmail-labeler
            ├→ Gmail API (OAuth2, scope: gmail.modify) — fetch threads
            ├→ Ollama (qwen2.5:7b-instruct, local) — classify + detect scams
            ├→ Gmail API — create/apply hierarchical labels
            └→ SQLite DB — track processed threads + run status
```

Everything runs locally. Gmail API uses OAuth2 (credentials stay on disk). LLM runs in Ollama on the local NVIDIA GPU. The only outbound connection is Gmail API (to Google, who already has the data) — no email content is sent to any third-party service.

## Features
- **Hierarchical labels** using Gmail's `/` separator (e.g., `Finance/Taxes/2025`, `Personal/Photography`)
- **Scam/phishing detection** — LLM flags suspicious emails with `Warnings/Phishing` label
- **Fully autonomous** — taxonomy auto-generated from email analysis, no approval needed
- **Resume-capable** — SQLite tracks processed thread IDs with status; interrupted runs pick up where they left off
- **Existing labels preserved** — nothing deleted, new taxonomy created alongside
- **Thread-based classification** — classify per thread (not per message) to avoid contradictory labels and reduce LLM calls
- **Failure notifications** — Windows toast notification on error so silent failures are visible

## Implementation Plan

### Step 1: Project Setup
- Create `C:\Users\Matt1\gmail-labeler\`
- Create venv: `python -m venv .venv`
- Create `requirements.txt`:
  - `google-auth-oauthlib` — OAuth2 flow
  - `google-api-python-client` — Gmail API client
  - `google-auth` — token refresh via `google.auth.transport.requests.Request`
  - `ollama` — official Ollama Python client (typed responses, proper error handling, uses httpx internally)
  - `beautifulsoup4` — HTML-to-text fallback for emails with no text/plain part
  - `winotify` — Windows Action Center toast notifications (persist until dismissed, unlike plyer's balloon tips)
  - `pydantic` — JSON schema generation for Ollama structured output (ClassificationResponse model)
- `config.json` is **optional** — all defaults are built into the code. Only create to override:
  - `model`: `qwen2.5:7b-instruct` (default)
  - `ollama_url`: `http://localhost:11434` (default)
  - `batch_size`: 50 (default)
  - `body_max_chars`: 2000 (default; truncate after footer/quote stripping)
  - `num_ctx`: 8192 (default; 4096 is too tight once taxonomy grows — 8192 costs ~0.5GB more VRAM, well within 12GB)
  - `timeout`: 120 (default; seconds per LLM call — allows for cold start)
  - `ollama_path`: `C:\Users\Matt1\AppData\Local\Programs\Ollama\ollama app.exe`
  - `max_new_categories_per_run`: 10 (default; caps taxonomy growth)
  - `max_taxonomy_in_prompt`: 50 (default; caps how many leaf categories appear in LLM prompt — excess categories are still valid labels but not listed)
- **`config.py` module** — `load_config()` reads `config.json` if present, merges with hardcoded defaults via `{**DEFAULTS, **user_overrides}`, validates types. Called once at startup by `labeler.py` and `taxonomy.py`; resulting dict passed to functions that need config values. Unknown keys ignored with log warning; invalid JSON causes startup error.
- **All `open()` calls must use `encoding='utf-8'` explicitly** — Windows Python defaults to system locale encoding unless `PYTHONUTF8=1` is set (Task Scheduler sets it, but manual runs from PowerShell may not)
- Create `.gitignore` excluding `credentials.json`, `token.json`, `labeler.db`, `.venv/`, `labeler.lock`, `*.log`

### Step 2: Gmail API Auth Setup (`auth.py`)
- Guide user through Google Cloud Console (exact order matters):
  1. Create project "Gmail Labeler"
  2. Enable Gmail API
  3. Configure OAuth consent screen → **set to "In Production" immediately** (not Testing — avoids 7-day refresh token expiry)
  4. Click through "unverified app" warning (one-time, expected for personal use)
  5. Create OAuth2 Desktop App credentials
  6. Download `credentials.json` to project dir
- Build `auth.py` module:
  - `get_credentials()` → returns authenticated `Credentials` object. Single entry point for all other modules.
    - Loads from `token.json` if exists
    - If expired: calls `creds.refresh(Request())`, saves updated token.json immediately after
    - If no token: runs `InstalledAppFlow.from_client_secrets_file()` with `run_local_server(port=0)` (auto-port avoids conflicts)
    - Returns `Credentials` object (caller builds service via `build('gmail', 'v1', credentials=creds)`)
  - `access_type='offline'` + `prompt='consent'` — ensures a refresh token is always issued, even on re-authentication after token revocation
  - **Single scope: `gmail.modify`** — covers read, label create, and label apply (the other scopes are redundant subsets)
  - Detect `RefreshError` → show winotify toast telling user to re-run `auth.py`
  - **All callers** (labeler.py, taxonomy.py) must also catch `RefreshError` from `get_credentials()` AND from mid-run API calls → abort immediately with toast (do NOT retry auth errors — they cannot self-heal)
  - Google revokes refresh tokens after 6 months of inactivity even for "In Production" apps — the weekly schedule prevents this, but document the risk
  - **auth.py is ONLY run manually** — never triggered by Task Scheduler (it opens a browser for consent)

### Step 3: Gmail Client Module (`gmail_client.py`)
- `list_threads(service, after_date=None, max_results=500)` — list thread IDs via `threads.list` (paginated via `nextPageToken`, 500/page)
  - `after_date` is a datetime string (ISO from SQLite) or `None`. If provided, convert to epoch seconds (`int(datetime.fromisoformat(after_date).replace(tzinfo=timezone.utc).timestamp())`) for Gmail's `q=f"after:{epoch}"` operator (Gmail only accepts `YYYY/MM/DD` or epoch — not ISO format)
  - `includeSpamTrash=False` explicitly (skip spam/trash)
- `get_thread_first_message(service, thread_id)` — two-step fetch:
  1. `threads.get(format='minimal')` → get message IDs array (10 quota units)
  2. `messages.get(id=messages[0]['id'], format='full')` → full body of first message only (5 quota units)
  - Guard: skip thread if `messages` array is empty
- `extract_text(message, max_chars=None)` — **recursive MIME tree traversal**:
  1. If payload is `text/plain` → decode base64url body directly
  2. If payload is `text/html` → decode + strip HTML with BeautifulSoup `.get_text()`
  3. If payload is `multipart/*` → recursively search parts: prefer `text/plain`, fall back to `text/html`
  4. If no text found (attachment-only, calendar invite) → return `None`, classify by subject + sender only
  5. Run `clean_body()` to strip boilerplate before truncation
  6. Truncate to `max_chars` (defaults to config `body_max_chars`, 2000 chars)
  - `max_chars` param allows taxonomy.py to pass 200 for lightweight summaries
  - Handle base64url decoding (`base64.urlsafe_b64decode` with padding fix)
  - Handle charset from `Content-Type` header (utf-8, iso-8859-1, windows-1252, etc.)
  - Handle `body.attachmentId` case (large body stored separately) → treat as no text
- `clean_body(text)` — strip boilerplate before truncation (~15 lines of regex):
  - Strip text after footer markers: "Unsubscribe", "To stop receiving", "This email was sent to", "View in browser", "Manage preferences"
  - Strip quoted reply blocks: lines starting with `>`, text after `On {date}, {name} wrote:` / `---------- Forwarded message ----------`
  - Collapse multiple consecutive blank lines into one
- `extract_headers(message)` — extract `Subject`, `From`, `Date` from `payload.headers` array. Returns `dict` with keys `subject` (truncated to 200 chars), `sender` (raw From header), `date` (raw Date header). Handles missing headers gracefully (empty string defaults).
- `extract_sender_domain(sender)` — parse `Display Name <user@domain.com>` → return `domain.com`. Used by classify prompt to highlight domain for phishing evaluation.
- `list_labels(service)` — returns `Dict[str, str]` mapping full label path → Gmail label ID. Pre-flight check: count only user-created labels (filter out `type: 'system'`); if `10000 - user_label_count < 5`, abort with actionable error.
- `ensure_label_hierarchy(service, full_path, label_cache)` — create parent labels incrementally:
  - For `Finance/Taxes/2025`: create `Finance`, then `Finance/Taxes`, then `Finance/Taxes/2025`
  - Gmail does NOT auto-create parents — must build path top-down
  - Mutates passed `label_cache` dict after each successful creation
  - **Idempotency guard**: before `labels.create()`, first check `label_cache` (fast path). If not in cache, attempt `labels.create()`. Catch HTTP 409 Conflict (Gmail rejects duplicate label names) — on 409, re-fetch via `list_labels()` to get the existing label's ID. This handles the lost-response scenario where the label was created but the response was lost.
- `apply_labels_to_thread(service, thread_id, label_ids)` — use `threads.modify` per thread:
  - Cleaner semantics: labels all messages in thread, not just one
  - 10 quota units per call; at 15K units/min budget = 1,500 threads/min (labeling is <8 min for full backlog)
- Rate limiting: 15,000 quota units/min per user. Per-thread cost = 25 units (threads.get 10 + messages.get 5 + threads.modify 10) = ~600 threads/min max. Add `time.sleep()` between batches + exponential backoff on HTTP 429/500/503. LLM bottleneck (2-5 sec/thread) naturally keeps well within API limits.
- **Removed**: `batch_get_messages()` — not used in classification flow (LLM is the bottleneck, not API round-trips). Sequential fetches are fine.

### Step 4: Ollama Client Module (`llm_client.py`)
- Uses **official `ollama` Python client** (`from ollama import Client`) with `timeout=config['timeout']` (default 120.0 seconds, float — verified pattern from ollama docs)
- `check_ollama()` — attempt `client.list()` to verify reachability; if unreachable, start via `subprocess.Popen([ollama_path], creationflags=subprocess.DETACHED_PROCESS)` and poll every 2 seconds up to 15 retries (30 sec). Catch `ConnectionError` (Python built-in — verified from ollama docs, NOT `httpx.ConnectError`).
- `warm_up_model()` — send a minimal chat request (e.g., "ping") to force model load into VRAM (~31 sec cold start on RTX 5070). This call blocks until model is ready — no polling needed after it returns. If timeout: retry once. If second timeout: abort with toast. Catch `ollama.ResponseError` — if `status_code == 404`, abort with toast: "Model not found. Run: ollama pull qwen2.5:7b-instruct".
- **VRAM check** after warmup: query `GET /api/ps` → check loaded model's `size_vram / size`. If `size_vram` key is missing (known Ollama bug where it's omitted when value is 0), skip the VRAM ratio check and log a debug message — do NOT warn (avoids false positive on affected Ollama versions). If `size_vram` IS present and `size_vram / size < 0.5` (model fell back to CPU), log WARNING + toast: "Model running on CPU — classification will be very slow. Close GPU-heavy apps." Also: if other models are loaded, send `POST /api/generate {"model": "<other>", "keep_alive": 0}` to unload them first.
- Every LLM call includes `keep_alive="24h"` (not just warmup) — prevents model unloading during long pauses from API errors or rate limiting during backlog runs.
- `classify_email(subject, sender, sender_domain, date, body, taxonomy)` — uses **`/api/chat`** endpoint (not `/api/generate` — tested quality difference):
  - System prompt structure (grouped for 7B model attention):
    1. Role + rules: "Classify this email into exactly ONE category (max 2 if it clearly spans two top-level groups). Never assign more than 2 labels."
    2. Taxonomy list grouped by parent with `##` headers (e.g., `## Shopping`, `## Finance`) — improves attention for smaller models. **Capped at `max_taxonomy_in_prompt` (50) leaves** — if taxonomy exceeds this, include only top-level groups + 50 most-used leaves (from SQLite `get_label_stats()`). All taxonomy labels remain valid; excess ones just aren't listed in prompt.
    3. Phishing evaluation rules — **contextual, NOT brand exemptions**:
       - "Urgency language ALONE is not phishing for e-commerce senders (Temu, eBay, Amazon, Etsy)"
       - "BUT: urgency + request for credentials/payment/clicking unfamiliar links = phishing regardless of claimed sender"
       - "Check sender domain against claimed brand. If mismatch → strong phishing indicator"
       - Known legitimate domains list: `temu.com, ebay.com, ebay.ca, paypal.com, etsy.com, amazon.com, amazon.ca, google.com`
    4. Multilingual instruction: "Classify emails regardless of language. Category names remain in English."
    5. **5 few-shot examples** covering: transactional/shipping, phishing (domain mismatch), seller activity, marketing, **account security notification** (replaces support — critical for false-positive prevention: shows legitimate urgent email that looks like phishing)
  - **JSON schema via Pydantic model** → `format=ClassificationResponse.model_json_schema()`:
    ```python
    class ClassificationResponse(BaseModel):
        labels: list[str] = Field(min_length=1, max_length=2)
        primary_label: str
        is_new_category: bool
        confidence: Literal["high", "medium", "low"]
        phishing_risk: Literal["none", "low", "high"]
        phishing_reason: str
    ```
    - `enum` constraints on confidence/phishing_risk enforced by llama.cpp grammar-based constrained decoding
    - `minItems: 1` prevents empty labels array; `maxItems: 2` matches system prompt rule ("max 2 labels")
  - **Post-hoc validation** (Python, after LLM response):
    - **Sanitize each label**: strip leading/trailing `/`, collapse `//` to `/`, reject empty strings or strings with empty segments (e.g., `"Shopping//Temu"` → `"Shopping/Temu"`, `""` → dropped). If all labels are dropped after sanitization, return `None` (treated as LLM failure).
    - If `primary_label not in labels` → set `primary_label = labels[0]`
    - If returned label not in taxonomy → treat as new category regardless of `is_new_category` flag
    - Do NOT use self-reported `confidence` for routing (unreliable for 7B models) — override with heuristic before storing in DB: label in taxonomy = high, label is generic/catch-all (e.g., "Other", "General") = medium, label not in taxonomy = low. Confidence is informational only — routing to `Uncategorized` is controlled by the `max_new_categories_per_run` cap in labeler.py (see Step 6), not by confidence.
  - **Return contract**: Returns `ClassificationResponse` dict on success. Returns `None` on unrecoverable failure (malformed JSON after 2 retries). Raises `ConnectionError` (re-raised from ollama client) on Ollama unreachable (caught at higher level to abort run).
  - New category handling is done by **labeler.py's per-thread loop** (not inside classify_email): check if returned label is in taxonomy → if not, call `ensure_label_hierarchy()` in gmail_client, persist to `taxonomy.json`, add to in-memory taxonomy. Capped at `max_new_categories_per_run` (10) via a counter in labeler.py. After cap reached, unknown labels route to `Uncategorized`.
  - Temperature: 0.1, `num_ctx`: 8192
  - User message format: `From: {sender}\n[Sender domain: {sender_domain}]\nSubject: {subject}\nDate: {date}\nBody:\n{body_or_"[No text content]"}`
  - **Runtime token estimation**: before each LLM call, estimate `len(full_prompt) / 3.5`. If estimate exceeds `num_ctx - 500`, dynamically truncate body further and log a warning.
- `discover_taxonomy(email_summaries)` — **running-taxonomy approach** (not independent batches):
  1. Batch 1: "Categorize these 50 emails. Create 15-25 hierarchical categories." → get initial taxonomy
  2. Batches 2-10: "Here are existing categories: [...]. Assign each email to an existing category OR suggest a new one ONLY if no existing category fits." → produces incremental additions, far fewer duplicates
  3. After all batches: programmatic dedup + LLM consolidation pass if >35 leaves remain
  4. Post-processing: validate every sample email maps to at least one category; if <90% coverage, run targeted re-prompt with uncovered emails
  - Mandatory categories: `Warnings/Phishing`, `Warnings/Scam`, `Uncategorized`
  - Include existing Gmail labels as seed hints
  - **Hard cap**: final taxonomy must have 15-50 leaf categories. If >50 after consolidation, merge programmatically (combine leaves sharing same parent that each have <3 email matches)
  - Uses `num_ctx: 8192` (same as classification — no special override needed)
- Retry logic: re-prompt up to 2 times on malformed JSON
- Body truncation: taxonomy.py passes `max_chars=200` to `extract_text()` for lightweight summaries

### Step 5: Taxonomy Discovery (`taxonomy.py`)
- **Startup**: Load config via `load_config()`. Call `get_credentials()` (wrapped in try/except `RefreshError` → toast + abort). Build `service = build(...)`. Call `check_ollama()` + `warm_up_model()`. Initialize `label_cache = list_labels(service)`.
- Fetch ~500 recent threads spread across time:
  - 10 separate `threads.list` calls with `after:/before:` date ranges (50 per month, last 10 months)
  - If fewer than 50 in a month, take all available; guard for months with 0 emails
  - For each thread: extract subject + sender + first 200 chars of body as "summary"
- Running-taxonomy LLM analysis (see Step 4 `discover_taxonomy()`):
  - Batch 1 prompt must distinguish: buying vs selling vs promotional (critical for e-commerce-heavy inboxes)
  - Subsequent batches: assign to existing categories, suggest new only if no existing fits
  - Consolidation pass (if >35 leaves): enforce 2-3 hierarchy levels, required groups (Shopping/, Selling/, Finance/, Accounts/, Warnings/, Personal/)
- Programmatic post-validation (Python, not LLM):
  - Every taxonomy entry has 1-3 `/`-separated segments (1 segment allowed for `Uncategorized`; all others should have 2-3)
  - `Warnings/Phishing`, `Warnings/Scam`, and `Uncategorized` are present
  - Total leaf count is 15-50 (initial target 15-25 from batch 1; hard cap at 50). If >50 after consolidation, merge programmatically per Step 4.
- Incorporate existing label names as hints (Taxes 2025, Swing Trades, Photography, etc.)
- **`taxonomy.json` format** — flat JSON array of label paths:
  ```json
  ["Shopping/Temu/Orders", "Shopping/Temu/Promotions", "Finance/Taxes/2025", "Warnings/Phishing", "Uncategorized"]
  ```
- Auto-create all labels in Gmail using `ensure_label_hierarchy()`; check for reserved names (INBOX, SPAM, TRASH, etc.) and sanitize
- If `taxonomy.json` already exists: back up to `taxonomy.YYYY-MM-DD.json`, then merge (union of old + new, don't remove existing)
- **Taxonomy-Gmail sync check** (at startup of labeler.py): compare `taxonomy.json` against actual Gmail labels. If taxonomy labels are missing in Gmail, log a warning (don't auto-re-create — user may have intentionally deleted them)

### Step 6: Classification Engine (`labeler.py`)
- **Service object**: Constructed once at startup: `service = build('gmail', 'v1', credentials=get_credentials())`. Passed to all `gmail_client` functions. The `google-api-python-client` `AuthorizedHttp` transport auto-refreshes expired access tokens mid-run using the refresh token.
- **Startup validation** (in order — `--status` skips directly to SQLite reads, no lock needed; `--skip-backlog` skips to step 6 then runs start_run/finish_run):
  1. Check required files with actionable error messages + winotify toast:
     - Missing `credentials.json` → "Download from Google Cloud Console"
     - Missing `token.json` → "Run: python auth.py"
     - Missing `taxonomy.json` → "Run: python taxonomy.py"
  2. **Wrap `get_credentials()` in try/except for `RefreshError`** → abort immediately with toast: "OAuth token expired. Run `python auth.py` to re-authenticate." Do NOT retry.
  3. Validate `taxonomy.json` is parseable and non-empty → **load into `taxonomy: list[str]`** variable for use throughout the run
  4. **Initialize label_cache**: `label_cache = list_labels(service)` — `Dict[str, str]` mapping label path → ID. Single call, reused for both sync check and runtime label operations.
  5. **Taxonomy-Gmail sync check**: compare loaded taxonomy against `label_cache`. Warn on mismatches.
  6. Acquire `msvcrt.locking()` on `labeler.lock` with 3-second retry (handles brief post-crash OS lock release delay)
  7. **Crash recovery**: check `run_log` for entries with `status='RUNNING'` (prior crash). Update those to `status='CRASHED'`. Log warning: "Previous run was interrupted."
  8. `check_ollama()` — verify Ollama is reachable, start if needed
  9. `warm_up_model()` + VRAM check — pre-load model before classification loop
- **Instance locking**: `msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)` — non-blocking exclusive lock on 1 byte of `labeler.lock`. Custom retry loop: attempt every 1 second for 3 attempts. If still locked after 3 attempts, another instance is running — abort with message. Auto-released on crash/kill/power failure (Windows closes all file handles on process termination).
- **DB path**: `db.py` derives path from `Path(__file__).parent / "labeler.db"` — never relies on CWD.
- **Modes** (mutually exclusive, + optional `--limit N` and `--dry-run` modifiers):
  - `--backlog` — process all unprocessed threads (checks `is_processed()` per-thread to skip already-done; batches of 50, progress in SQLite)
  - `--recent` — process threads since last run that did work (**default when no mode specified**, for scheduled runs). Uses `started_at` of most recent run_log entry with status in (SUCCESS, PARTIAL, CRASHED) for the date filter. If no previous run exists: error with "Run --backlog first". **Filters by `is_processed()` per-thread** to skip already-processed threads (handles overlap from using `started_at`).
  - `--retry-failed` — re-process threads marked FAILED in SQLite (respects `max_retries`)
  - `--status` — print summary of last run + label distribution stats + any CRASHED runs, then exit (no processing)
  - `--skip-backlog` — calls `start_run('skip-backlog')` then immediately `finish_run(run_id, 'SUCCESS', 0, 0)`, establishing a baseline date for `--recent` (for users who don't want to process old emails). Does not require Ollama or taxonomy.
  - `--dry-run` — modifier (not a mode), combines with `--backlog`, `--recent`, or `--retry-failed`. Classify and print results to log but do NOT apply labels in Gmail. **Does NOT write to `processed_threads` table**. Does NOT create new labels or mutate `taxonomy.json`. Writes to `run_log` with `mode='dry-run'` (base mode info is logged but `last_run_date()` excludes dry-run entries). Re-running dry-run on same threads will re-classify — intentional since local LLM cost is zero. Invalid with `--status` or `--skip-backlog`. `--limit` is also invalid with `--status` or `--skip-backlog`.
- **Status semantics**:
  - `processed_threads.status`: **SUCCESS** = classified + labels applied. **FAILED** = transient/LLM error worth retrying (malformed JSON, API error, Ollama timeout). **SKIPPED** = permanent skip, retrying won't help (empty subject + sender + body).
  - `run_log.status`: **RUNNING** = in progress (written at start). **SUCCESS** = all threads processed, 0 failures. **PARTIAL** = some threads processed (graceful shutdown or Ollama crash). **CRASHED** = detected on next startup (RUNNING entry with no other instance holding lock). **FAILED** = 0 threads processed (startup failure after run_log insert).
- **Begin processing**: Call `start_run(mode)` to insert RUNNING run_log entry. Wrap the entire processing loop in `try/except KeyboardInterrupt`.
- For each thread:
  1. Fetch first message via `get_thread_first_message()` (classify thread by its initiating email)
  2. Extract headers via `extract_headers(message)` → subject (truncated 200 chars), sender, date
  3. Extract text via `extract_text(message)`, extract sender domain via `extract_sender_domain(sender)`
  4. Skip if subject, sender, and body are all empty/None → `mark_processed(..., status='SKIPPED')` — skipped in `--dry-run`
  5. Send to Ollama: `classify_email(subject, sender, sender_domain, date, body, taxonomy)` → returns `ClassificationResponse` dict or `None`
  6. If `None` (LLM failure) → `mark_processed(..., status='FAILED')` (skipped in `--dry-run`), continue to next thread
  7. Apply resulting labels via `apply_labels_to_thread()` (using `threads.modify`) — skipped in `--dry-run`
  8. If LLM suggests new category not in taxonomy AND new_category_count < `max_new_categories_per_run`: call `ensure_label_hierarchy()`, persist to `taxonomy.json` via **atomic write** (`write to taxonomy.json.tmp` then `os.replace()` → crash-safe), add to in-memory taxonomy, increment counter. Else: route to `Uncategorized`. — **skipped in `--dry-run`** (don't create labels or mutate taxonomy)
  9. `mark_processed(thread_id, labels, 'SUCCESS', ...)` — committed per-thread. **Skipped in `--dry-run`** (per line 211).
- **Graceful shutdown**: Primary mechanism is `try/except KeyboardInterrupt` wrapping the main processing loop (more reliable on Windows than `signal.signal(SIGINT)`, which may only fire at interpreter exit). On Ctrl+C: finish current thread, commit to SQLite, write run_log as PARTIAL, log summary, exit cleanly. Also register `atexit` as secondary guard for unexpected exits.
- **Sleep/wake detection**: Measure elapsed time between END of thread N and START of thread N+1 (not including processing time). If >60 seconds, assume machine slept. On detection: re-check Ollama health, re-warm model if needed, log "Recovered from sleep/suspend". Timer resets AFTER recovery completes (so the warmup itself doesn't re-trigger).
- Progress reporting: `Processed 1,234/15,700 (7.8%)` every 50 threads
- On `RefreshError` mid-run: abort immediately with toast (do NOT retry — auth errors cannot self-heal)
- On Ollama connection failure: log error, save progress, exit cleanly (next run resumes)
- On Gmail API error (non-auth): exponential backoff, retry 3 times, then skip and mark as FAILED in SQLite
- On winotify toast failure (e.g., running as non-interactive): fall back to logging the notification text

### Step 7: SQLite State Database (`db.py`)
- **Init**: `create_tables_if_not_exist()` called on first import; sets `PRAGMA journal_mode=WAL` for crash resilience
- **Connection**: single connection per script run via module-level `get_connection()`, closed at exit
- Table: `processed_threads`
  - `thread_id TEXT PRIMARY KEY`
  - `labels TEXT` (JSON array of applied labels)
  - `primary_label TEXT`
  - `status TEXT` (SUCCESS / FAILED / SKIPPED)
  - `phishing_risk TEXT` (none / low / high)
  - `confidence TEXT` (high / medium / low)
  - `retry_count INTEGER DEFAULT 0` (incremented on each retry; stop retrying after 3)
  - `processed_at DATETIME`
- Table: `run_log`
  - `run_id INTEGER PRIMARY KEY AUTOINCREMENT`
  - `mode TEXT` (backlog / recent / retry-failed / skip-backlog / dry-run — dry-run excludes base mode info for simplicity; `last_run_date()` filters it out)
  - `started_at DATETIME`
  - `completed_at DATETIME` (NULL while running)
  - `threads_processed INTEGER`
  - `threads_failed INTEGER`
  - `status TEXT` (RUNNING / SUCCESS / PARTIAL / CRASHED / FAILED)
- Helper functions:
  - `is_processed(thread_id)` → bool (returns True for SUCCESS and SKIPPED, False for FAILED and not-found)
  - `mark_processed(thread_id, labels, status, phishing_risk, confidence, primary_label)` — uses `INSERT ... ON CONFLICT(thread_id) DO UPDATE` (UPSERT). On FAILED status: increments `retry_count` via `retry_count = retry_count + 1`. On SUCCESS: preserves `retry_count` for audit trail. This replaces the need for a separate `increment_retry()` function.
  - `start_run(mode)` → insert run_log with `status='RUNNING', started_at=now(), completed_at=NULL`. Returns `run_id`.
  - `finish_run(run_id, status, threads_processed, threads_failed)` → update run_log with `completed_at=now()` and final stats.
  - `recover_crashed_runs()` → find run_log entries with `status='RUNNING'`, update to `status='CRASHED', completed_at=started_at`. Returns count of recovered entries.
  - `last_run_date()` → returns `started_at` of most recent run_log entry with status in (SUCCESS, PARTIAL, CRASHED) **AND mode != 'dry-run'**, or `None`. Note: `skip-backlog` IS included — that's its purpose (establish a baseline date for `--recent`). Only `dry-run` is excluded (it doesn't process threads, so using its date would create gaps). Uses `started_at` (not `completed_at`) to ensure overlap rather than gaps — duplicate processing is safe since `is_processed()` catches already-done threads.
  - `get_failed_threads(max_retries=3)` → list of thread_ids where status=FAILED and retry_count < max_retries
  - `get_label_stats()` → dict of label → count (for `--status` mode and `max_taxonomy_in_prompt` selection; on first run with no data, all taxonomy leaves are included up to cap)
  - `get_last_run()` → dict with mode, started_at, completed_at, threads_processed, threads_failed, status (for `--status` display)
  - `get_crashed_runs()` → list of dicts for run_log entries with status='CRASHED' (for `--status` display)

### Step 8: Windows Task Scheduler Setup
- Use `bash.exe` as executor (matches existing tasks on this machine — not `.bat`):
  ```
  Program: C:\Program Files\Git\bin\bash.exe
  Arguments: -c "cd /c/Users/Matt1/gmail-labeler && PYTHONUTF8=1 PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe labeler.py --recent"
  ```
  - **No `>> labeler.log 2>&1` redirect** — Python's `RotatingFileHandler` manages all logging internally (shell redirect conflicts with rotation: renames fail while shell holds file descriptor)
  - Crash-before-logging-init protection: top-level `try/except` in `labeler.py` writes to `crash.log`
- Task Scheduler settings:
  - Trigger: Weekly (user picks day/time)
  - **LogonType: Interactive** (Ollama is a user-space process, won't run without a logged-in user)
  - **StartWhenAvailable: True** (if the machine was off at scheduled time, run at next opportunity)
- Logging: Python's `RotatingFileHandler` (10MB max, 5 backups = 60MB max) — increased from 5MB/3 to handle full backlog runs (~5-6MB per 15K threads). All logging through Python, no shell redirection.

### Step 9: Initial Run
1. Activate venv: `.venv\Scripts\activate`
2. Run `python auth.py` — browser opens for Gmail OAuth consent (one-time)
3. Run `python taxonomy.py` — auto-discovers categories, creates hierarchical labels in Gmail
4. Run `python labeler.py --dry-run --limit 20` — classify 20 threads WITHOUT applying labels, review log output for quality
5. Run `python labeler.py --backlog --limit 50` — apply labels to 50 threads, verify in Gmail
6. Run `python labeler.py --status` — check label distribution looks sensible
7. Run `python labeler.py --backlog` — full sweep of remaining unprocessed threads (estimated ~11-16K threads from ~15.7K emails)
   - **Estimated time: 7-17 hours** (2-5 sec/thread on RTX 5070 with qwen2.5:7b-instruct; plus overhead for API calls, retries, and sleep recovery)
   - Can be interrupted and resumed safely (SQLite tracks progress)
   - Consider running in chunks: `--limit 1000` across multiple sessions
8. Set up Task Scheduler for weekly `--recent` runs

## Key Files
```
C:\Users\Matt1\gmail-labeler\
├── auth.py             # OAuth2 authentication + token refresh (save after refresh())
├── config.py           # load_config() — merge config.json overrides with hardcoded defaults
├── gmail_client.py     # Gmail API: thread fetch, recursive MIME extraction, label hierarchy, threads.modify
├── llm_client.py       # Ollama: /api/chat, JSON schema mode, warm-up, health check, VRAM check, official client
├── taxonomy.py         # Auto-discover and create label taxonomy (running-taxonomy, coverage validation)
├── labeler.py          # Main script (--backlog / --recent / --retry-failed / --status / --dry-run / --skip-backlog / --limit)
├── db.py               # SQLite state tracking (processed_threads, run_log, crash recovery)
├── config.json         # OPTIONAL overrides (all defaults built into code)
├── taxonomy.json       # Generated label taxonomy (auto-created, backed up on re-runs)
├── credentials.json    # OAuth2 client secret (user downloads from Google Cloud)
├── token.json          # OAuth2 refresh token (auto-generated, saved after each refresh)
├── labeler.db          # SQLite database (auto-created)
├── labeler.lock        # msvcrt kernel lock (auto-released on crash/exit)
├── crash.log           # Catch-all for errors before logging init
├── requirements.txt    # Python dependencies
├── .venv/              # Python virtual environment
└── .gitignore          # Exclude secrets, DB, venv, lock, logs
```

## Prerequisites (User Must Do)
1. **Ollama**: Already installed with `qwen2.5:7b-instruct` model available
2. **Google Cloud Console** (step-by-step):
   1. Go to console.cloud.google.com → create new project "Gmail Labeler"
   2. APIs & Services → Library → search "Gmail API" → Enable
   3. APIs & Services → OAuth consent screen → configure:
      - User type: External
      - App name: "Gmail Labeler", support email: your email
      - Scopes: add `gmail.modify`
      - **Publishing status: click "Publish App"** → confirm → status becomes "In Production"
      - (Click through "unverified app" warning — expected for personal use)
   4. APIs & Services → Credentials → Create Credentials → OAuth client ID:
      - Application type: Desktop app
      - Name: "Gmail Labeler Desktop"
      - Download JSON → rename to `credentials.json` → place in project dir
   - **Order matters**: publish to Production BEFORE running `python auth.py` (the consent flow), so tokens get long-lived refresh. Credential creation itself can happen before or after publishing.
3. **First OAuth flow**: Run `python auth.py` once — browser opens for Gmail consent

## Verification
1. `ollama list` — confirm `qwen2.5:7b-instruct` is available
2. `python auth.py` — confirm token.json is created
3. `python taxonomy.py` — confirm hierarchical labels appear in Gmail sidebar; inspect `taxonomy.json` for 15-25 leaf categories with 2-3 hierarchy levels
4. `python labeler.py --dry-run --limit 20` — classify 20 threads without applying, review log for quality
5. `python labeler.py --backlog --limit 10` — apply labels to 10 threads, check Gmail
6. `python labeler.py --status` — verify label distribution stats look correct
7. `python labeler.py --retry-failed` — verify failed threads get reprocessed (and stop after max_retries)
8. Check `labeler.log` — no errors, correct rotation
9. `python labeler.py --backlog --limit 100` — larger chunk, verify labels + SQLite state
10. Trigger Task Scheduler entry manually — verify it runs and logs correctly

## Safety Guarantees
- **No deletions**: Script only reads emails and adds labels — never deletes, archives, or moves
- **No link clicking**: Reads email via API as structured data — never renders HTML or follows URLs
- **No third-party data sharing**: Only outbound connection is Gmail API (to Google, who already has the data) — no email content is sent to any external AI service or third party
- **Scam detection**: LLM flags phishing/scam emails with `Warnings/Phishing` label
- **Resume-safe**: SQLite tracking means interrupted runs pick up where they left off
- **Existing labels untouched**: New taxonomy created alongside existing labels
- **Instance-safe**: `msvcrt.locking()` kernel lock prevents concurrent runs; auto-releases on crash (no stale lock)
- **Failure-visible**: Windows Action Center toast (winotify) on errors — persists until dismissed, not ephemeral
- **Scope justification**: `gmail.modify` is the minimum scope that covers reading + labeling; the script never uses its archive/trash capabilities

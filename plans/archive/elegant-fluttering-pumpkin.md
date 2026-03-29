# Plan: Autonomous Notion Capture Hook

## Context
The 4 global Notion databases (Prompt Library, Lessons Learned, Glossary, External References) exist but aren't auto-populated. The user wants Claude Code to autonomously extract relevant insights from every session and write them to the correct database — no manual commands, no input needed.

## Approach
A Python Stop hook (`notion-capture.py`) that fires at the end of every session, reads the JSONL transcript from disk, runs 4 extraction pipelines with precision-first heuristics, deduplicates against Notion, and inserts new entries.

## Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `~/.claude/hooks/notion-capture.py` | **CREATE** (~350 lines) | Main capture hook |
| `~/.claude/.env` | **EDIT** | Add `NOTION_TOKEN=ntn_4269...` |
| `~/.claude/settings.json` | **EDIT** | Register hook in `Stop[0].hooks` |

## How It Works

1. **Stop hook fires** → receives metadata JSON on stdin (session_id, workspace CWD)
2. **Build transcript path** → `~/.claude/projects/<slug>/<session_id>.jsonl`
3. **Parse JSONL** → single-pass scan extracting user messages, assistant texts, tool calls, error→fix pairs
4. **Gate check** → skip trivial sessions (< 5 user messages or < 30 seconds)
5. **Run 4 extractors** (each capped at 3 inserts):
   - **External References**: URL regex → filter doc domains → dedup on URL → insert
   - **Lessons Learned**: error→fix pairs + signal phrases ("the issue was", "turns out") → categorize → dedup on first 6 words → insert
   - **Glossary**: definition patterns ("X is a", "X means", acronyms) → quality gate (skip common words) → dedup on exact term → insert
   - **Prompt Library**: Write tool calls to `.md` files with prompt-like content (headings, "You are", instruction lists) → dedup on filename → insert
6. **Log everything** to `~/.claude/notion-capture.log`

## Safety Guardrails

- Max 3 entries per DB per session (12 total worst case)
- Entire `main()` wrapped in `try/except` → always `exit(0)`, never blocks session exit
- All Notion API calls have 5-8 second timeouts
- Network failures default to "entry exists" (prevents duplicate spam)
- `DRY_RUN` env var for testing without API calls
- No stdout output (would corrupt Claude's response stream)

## Dedup Strategy

| Database | Filter | Type |
|----------|--------|------|
| External Refs | `URL.url.equals` | Exact URL match |
| Lessons Learned | `Takeaway.title.contains` (first 6 words) | Fuzzy |
| Glossary | `Term.title.equals` | Exact |
| Prompt Library | `Name.title.equals` | Exact |

## Performance

- 27MB JSONL parse: ~200ms
- Worst case 24 Notion API calls: ~1.2s
- Typical session total: ~400ms (well within 10s budget)

## Verification Plan

1. **Dry run**: Set `NOTION_CAPTURE_DRY_RUN=1`, pipe synthetic payload, check log
2. **Single extractor**: Enable only `extract_external_refs`, run on current session, verify Notion DB entry
3. **Trivial guard**: Pipe payload for a 3-message session, verify "skipped" in log
4. **Dedup**: Run same session twice, verify 0 inserts on second run
5. **Failure resilience**: Set invalid token, verify exit(0) and error logged

## Key Design Decisions

- **Precision over recall**: Better to miss a lesson than spam the DB with noise
- **No LLM classification**: Pure regex/heuristic — keeps it fast, deterministic, zero-cost
- **Read transcript from disk** (not stdin): Stop hooks only get metadata, but transcript JSONL is at a predictable path
- **Sequential extractors**: External refs first (highest confidence) → Lessons → Glossary → Prompts (lowest confidence)

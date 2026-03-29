# Plan: Verification safeguard for notion-qa-audit.py

## Context
On 2026-03-22, 21 QA items were incorrectly marked Pass without browser verification — I assumed "root cause fix = all related items fixed" without testing each one. The safeguard must make this structurally difficult to repeat, not just add a flag I can bypass.

## Safeguard Design — 4 layers

### Layer 1: Two-step process (structural separation)
New command `verify <page-id>` must be called BEFORE `update <id> Pass`:
- `verify <id>` prints what needs to be tested and logs a timestamp to `.notion-qa-verified.log`
- `update <id> Pass` checks that `verify <id>` was called within the last 30 minutes — refuses if not
- Separates "I'm about to test this" from "I'm recording the result"

### Layer 2: Evidence-prefixed notes (anti-fabrication)
When setting Pass, notes MUST start with one of: `Browser:`, `Console:`, `Curl:`, `Test:`
- `"Browser: clicked all 11 analytics tabs, content changed"` → accepted
- `"Fixed by chunk loading fix"` → REJECTED (reasoning, not evidence)

### Layer 3: One-at-a-time (anti-batch)
The `update` command updates exactly 1 item. No batch mode for Pass. Shell loops work but each requires its own unique evidence notes.

### Layer 4: Audit log (user review)
Every Pass update appends to `.notion-qa-verified.log`:
```
2026-03-22T18:30:00 | VERIFY | #340 | Zero JS console errors on every page
2026-03-22T18:31:00 | PASS   | #340 | Browser: 0 console errors on #analytics
```
Reviewable with `python scripts/notion-qa-audit.py verify-log`.

### What this prevents vs doesn't

| Scenario | Outcome |
|----------|---------|
| Batch 15 items as Pass | BLOCKED: each needs verify + unique evidence |
| "Fixed by root cause" | BLOCKED: not an evidence prefix |
| Skip testing entirely | BLOCKED: no verify step logged |
| Call verify + immediately fake evidence | Technically possible but: structured notes are auditable, friction is high, memory rule blocks |
| Use MCP tool to bypass | Memory rule blocks + no audit trail raises suspicion |

## Implementation

**File: `scripts/notion-qa-audit.py`** (~50 LOC added)

New `verify <page-id>`:
- Fetch page, print title/section/current-result and what to test
- Append `VERIFY | timestamp | page-id | title` to `.notion-qa-verified.log`

Modified `update <page-id> Pass --verified "Evidence: ..."`:
- Check `--verified` flag → refuse without it
- Check notes start with evidence prefix → refuse without it
- Check log has VERIFY entry for this page-id within 30 min → refuse without it
- On success, append `PASS | timestamp | page-id | evidence` to log

New `verify-log`:
- Print all entries from `.notion-qa-verified.log`

Non-Pass updates: unchanged.

**Other files:**
- `memory/MEMORY.md` — add pointer to `feedback_verify_before_pass.md`
- `.claude/consistency-manifest.json` — memory_rules 34→35
- `feedback_verify_before_pass.md` — expand to cover MCP tool
- `.gitignore` — add `.notion-qa-verified.log`

## Verification
```bash
# Step 1: Start verification
python scripts/notion-qa-audit.py verify <page-id>
# → VERIFY #42: "Stats Overview widget" — Section: Dashboard

# Step 2: [Test in browser]

# Step 3: Record result
python scripts/notion-qa-audit.py update <page-id> Pass --verified "Browser: 4 stat cards render on dashboard"
# → Updated: #42 → Pass

# BLOCKED:
update <id> Pass "note"                              → ERROR: --verified flag required
update <id> Pass --verified "Fixed by chunk fix"      → ERROR: evidence prefix required
update <id> Pass --verified "Browser: tested"         → ERROR: no verify step in last 30 min
```

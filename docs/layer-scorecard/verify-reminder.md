# Verify Reminder — PostToolUse Hook

## Purpose
Reminds Claude to run verification (test, syntax check, linter) after editing code files. Fires mid-response via `stderr + exit 2`, which Claude Code feeds back to Claude as context.

## Hook Details
- **File:** `~/.claude/hooks/verify-reminder.py`
- **Event:** PostToolUse
- **Matcher:** Edit|Write
- **Mechanism:** stderr + exit 2 (confirmed working; systemMessage does NOT work on PostToolUse)
- **Filter:** Only code files — skips paths matching `NON_CODE_PATH_RE` (.md, .claude/, memory/, etc.)

## Output
```
[verify] You edited {filename}. Run a test or syntax check and quote the output before responding.
```

## Rationale
Quality gate analysis (2026-03-30) found 29% block rate (145/498). 70% of blocks were MECHANICAL — Claude editing code without running verification. This hook prevents those blocks by reminding Claude mid-response, before the Stop hook fires.

## Metrics
- **Baseline block rate:** 193 total, 147 MECHANICAL (as of 2026-03-30 18:46)
- **Expected impact:** Eliminates ~42% of blocks (61 of 145)
- **Tracking:** Compare `grep -c "BLOCK" ~/.claude/quality-gate.log` over future sessions

## Smoke Tests
- 1 test in smoke-test.sh (auto-detected via syntax check)
- Functional tests verified: code file triggers exit 2, non-code file exits 0

## Known Limitations
- Cannot deduplicate across multiple edits in one response (fires per Edit/Write)
- Effectiveness depends on Claude following the reminder — unproven at scale
- exit 2 may show as "hook error" in user's terminal (cosmetic)

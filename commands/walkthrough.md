# /qa — Universal QA Testing Skill (v3)

You are executing a comprehensive, visual QA test of a project. This skill auto-detects what to test, requires zero manual input from the user beyond "go", and produces screenshot-verified results.

## CRITICAL RULES — NON-NEGOTIABLE
1. **SCREENSHOT EVERY PAGE.** Before any DOM check, before any grep. Take a screenshot and LOOK AT IT.
2. **NEVER use `mcp__plugin_chrome-devtools-mcp`** — only use `mcp__claude-in-chrome__*` tools.
3. **NEVER mark anything as Pass without a screenshot** showing it looks correct.
4. **NEVER claim confidence without visual proof** shown to the user.

## Phase 1: Auto-Detect Project Traits

Read the detection rules from `memory/qa-traits/00-detection-rules.md` (in the Claude project memory directory).

Execute each detection rule by scanning the codebase:
1. Read `package.json` for dependencies
2. Use `Glob` to find files matching patterns
3. Use `Grep` to search for code patterns
4. Read `.env.example` for environment variables
5. Read project CLAUDE.md for architecture notes

For each matched trait, log it:
```
DETECTED: Trait 16 (Dark Mode) — found "dark-mode" in main.css, theme toggle in init.js
DETECTED: Trait 20 (Auth) — found JWT handling in auth.js, login page in pages-core.js
NOT DETECTED: Trait 52 (Mobile Native) — no react-native/expo/swift/kotlin found
```

## Phase 2: Build Test Plan

1. Always include traits 01-14 (universal)
2. Add all detected conditional traits (15-56)
3. Load test items from each matched trait file in `memory/qa-traits/`
4. Count total test items

Present to user:
```
━━━ QA TEST PLAN ━━━
Project: [name from package.json]
URL: [from CLAUDE.md or ask user]

Detected Traits: [N] of 56
Total Test Items: [M]

Traits included:
✅ 01 Functional (51 items)
✅ 02 Visual/UI (44 items)
...
✅ 16 Dark Mode (32 items)
...
⬜ 52 Mobile Native (not detected)
⬜ 53 Embedded/IoT (not detected)

Estimated sessions: [M / 50] (approximately 50 items per session)

Ready to start? Say "go" or "skip [trait number]" to exclude a trait.
```

Wait for user to say "go".

## Phase 3: Execute Tests

### Pre-Testing Setup
1. Get Chrome tab: `mcp__claude-in-chrome__tabs_context_mcp` with `createIfEmpty: true`
2. Navigate to the app URL
3. Take initial screenshot — verify the app loads
4. Log in if needed (ask user for credentials only if not found in CLAUDE.md/memory)
5. Create screenshot directory: `data/qa-screenshots/[date]/`

### Test Execution Loop

For each trait, for each test item:

**Step 1: Navigate**
Navigate to the relevant page using `mcp__claude-in-chrome__navigate`

**Step 2: Screenshot**
Take screenshot using `mcp__claude-in-chrome__computer` with `action: "screenshot"`

**Step 3: Visual Check**
LOOK at the screenshot. Check for:
- Page renders (not blank, not error)
- Layout correct (not squished, not broken)
- No error toasts
- Content present and correct
- No visual glitches

**Step 4: Interact (for interactive items)**
Click buttons, fill forms, etc. using `mcp__claude-in-chrome__computer`
Take screenshot AFTER interaction to verify result

**Step 5: Record Result**
- **Pass**: Screenshot shows correct behavior
- **Fail**: Screenshot shows broken behavior — note what's wrong
- **Skip**: Can't test (needs credentials, hardware, etc.) — note why

**Step 6: Report to User**
Show screenshot inline. State what you found. Move to next item.

### Per-Page Mandatory Checks
On EVERY page visited, check ALL of these (from Trait 02):
1. Layout not broken
2. No error toasts in corners
3. No invisible/missing elements
4. Text readable, not truncated
5. Consistent with other pages

### Session Management
- After every 50 items: pause, summarize progress, ask to continue
- Save progress to `memory/QA-PROGRESS.md` periodically
- If context gets heavy: compact, resume from saved progress

## Phase 4: Generate Report

After all items tested, generate:

```markdown
# QA Report — [Project Name]
Date: [date]
URL: [url]
Traits Tested: [N]
Items Tested: [M]
Screenshots: data/qa-screenshots/[date]/

## Summary
- Pass: [count] ([%])
- Fail: [count] ([%])
- Skip: [count] ([%])

## Failures (by severity)

### Critical
[list with screenshots]

### High
[list with screenshots]

### Medium
[list with screenshots]

### Low
[list with screenshots]

## Skipped Items
[list with reasons]

## Pages Visited
[list with screenshot filenames]
```

Save report to `data/qa-report-[date].md`

## Phase 5: Offer Fixes

After report, ask:
"I found [N] issues. Want me to fix them? I'll start with Critical, then High, then Medium."

If yes: fix each issue, rebuild, deploy, then RETAKE THE SCREENSHOT to verify the fix.

## What This Skill Replaced

v1 (2026-03-22): Used DOM queries only. Missed 21 items.
v2 (2026-03-30): Used DOM + grep. Passed 478 items without taking a single screenshot. Missed: broken settings layout, financials crash, error toast spam, wrong empty state text, missing shop cards.
v3 (this version): Screenshot-first. Every page visually verified. Auto-detects traits from codebase. Zero manual input required.

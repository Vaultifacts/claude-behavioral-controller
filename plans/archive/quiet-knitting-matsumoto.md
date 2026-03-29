# Plan: Three Tasks — Issues Page + Notion Cron + Multi-cycle Build

## Task 1: Update Notion Issues Page (resolved items)
Three new fixes to add to the "Resolved" section of the Issues sub-page:
- **CLAUDE_BIN PATH** — `spawn('claude')` fails in Git Bash (ENOENT); fixed by resolving fallback to `%USERPROFILE%\.local\bin\claude.exe` at module load in `lib.js`
- **projectDir cwd** — `spawn` with non-existent `cwd` throws ENOENT on Windows; fixed by `mkdirSync(projectDir)` before design phase in `chatgpt_project_bridge.js`
- **Post-design reconnect** — `startFreshChat(page)` fatal when browser closed during design; fixed by checking `needsReconnect` and routing through `ensureConnected()` instead

Steps:
1. `notion-search` to find "Issues, Failures, & Bugs" sub-page (or use known parent page `3249f0c8-1de6-81e8-b1a3-d9bad033a3b1` to navigate to child)
2. `notion-fetch` the Issues page to read current content
3. `notion-update-page` with `update_content` to append the 3 resolved items to the Resolved section

## Task 2: Set Up 3-Minute Notion Cron
Invoke `/loop` skill with the existing cron prompt from the previous session:

```
3m Read the most recently modified logs/project_*.json file in C:\Users\Matt1\OneDrive\Desktop\Claude_Code_&_ChatGPT_Chatter\logs\ and update the Notion page 3249f0c8-1de6-81e8-b1a3-d9bad033a3b1 with: Status section (cycles complete, any errors), Completed Work section (one checked item per cycle with Built: content), Up Next section (Next: from last cycle). Use notion-update-page with update_content command to patch each section.
```

## Task 3: Multi-cycle Build
Run 3 cycles on the existing simple-counter-app to stress-test reconnect + context-reset paths:

```
node chatgpt_project_bridge.js "Build a simple counter app" --cycles 3 --design-turns 0
```

`--design-turns 0` skips the design phase (already done in cycle 1); `--dir` will be omitted so it reuses the same `simple-counter-app` directory.

Actually use `--resume` flag if available, or just run with same goal (projectDir already exists, Claude will see existing code).

Check: does `--resume` exist? Search parseArgs. If yes use it. If no, just re-run with same goal.

## Execution order
1 → 2 → 3 (sequential; task 3 is long-running and can be monitored via task 2 cron)

## Verification
- Task 1: Fetch Issues page after update — confirm 3 new resolved items visible
- Task 2: Cron ID returned by CronCreate; first tick within 3 min updates Notion page
- Task 3: Bridge output shows all 3 cycles completing; `last-run.md` updated; Notion tracker updated by cron

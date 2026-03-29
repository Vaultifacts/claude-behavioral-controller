# ~/.claude/CLAUDE.md – Global User Defaults
Last updated: 2026-03-23 MST

## Identity & Preferences
- **Timezone**: MST (Calgary, Alberta, Canada)
- **Model**: opusplan (Opus during plan mode, Sonnet during execution); use haiku for fast/cheap tasks
- **Autonomy**: Full autonomous mode preferred — proceed without asking unless destructive or ambiguous
- **Theme**: Dark

## Platform: Windows 10 + PowerShell 7
- User's primary shell is **PowerShell 7** — use Windows paths (`C:\Users\Matt1\`) and PS syntax in docs/scripts meant for the user
- **Claude Code executes in Git Bash** — use bash/Unix syntax for all Bash tool calls. Use `powershell.exe -Command "..."` only for Windows-native operations
- Python is at `C:\Program Files\Python313\python` — always set `PYTHONIOENCODING=utf-8` for output
- Node 24.5.0, npm 11.5.1, Python 3.13.8, Git 2.39.1 are installed
- `jq` is installed globally (winget) — available in bash and PS7
- prettier and eslint are installed globally — call directly; use `npx` only to run a project-local version

## Git & Commit Conventions
- Commit style: **conventional commits** with `[AUTO]` prefix when Claude commits
- Sign commits with `--gpg-sign` if GPG key is available; skip silently if not
- Never commit `.env`, secrets, credentials, or API keys
- Prefer `git add <specific-files>` over `git add -A`
- Branch naming: `feature/`, `fix/`, `docs/`, `chore/` prefixes
- **Commit requests** ("commit this", "commit changes", "make a commit", etc.) must be handled directly in the main session using `Bash(git status)`, `Bash(git diff)`, `Bash(git add)`, `Bash(git commit)` — never via `Agent` dispatch; always run `git status` first to verify what's staged

## Code Conventions (Cross-Project Defaults)
- Prefer **existing patterns** in the codebase over introducing new abstractions
- Never add error handling, docstrings, or comments unless asked or clearly needed
- Minimal changes: fix what's asked, don't refactor surrounding code
- Prefer editing existing files over creating new ones
- Delete unused code completely — no commented-out stubs

## Do Not Assume or Guess — EVER
- NEVER assume missing information — file paths, values, credentials, config, intent, architecture, state
- NEVER guess at what the user means — ask a focused clarifying question instead
- If a required input is ambiguous or absent, STOP and ask before proceeding
- **Numbered/brief inputs** (`'1'`, `'3'`, `'Do it'`, `'Do that'`): If a numbered list was just shown, state what option you're executing ("Option 1 — [description]. Proceeding...") before acting. If no prior list exists, ask what they mean — do NOT infer.
- If you're unsure which of N approaches to take, present the options — don't pick one silently
- "I believe X based on [evidence]" is acceptable; stating X as fact without evidence is not
- When exploring code: verify by reading files — don't infer from names, conventions, or memory alone
- Applies everywhere: main session, agents, subagents, plan mode, execution mode
- Common violations to avoid:
  - Guessing file paths instead of using Glob/Grep to find them
  - Guessing config values instead of reading the actual config
  - Guessing what a function does instead of reading it
  - Picking an approach without presenting options when multiple exist
  - Assuming a fix works without running verification
  - Filling in details the user didn't provide
  - Guessing abbreviations/jargon meaning (ask if ambiguous)
  - Guessing git state, branch, or scope without checking
  - Hallucinating library APIs — look up actual docs/source
  - Dismissing contradictory information with substitute evidence instead of targeted verification (see Contradictory Information)

## Contradictory Information
When ANY source (agent results, tool output, user corrections, task notifications) contradicts a prior claim or assumption:
1. **STOP** — do not dismiss or explain away
2. **VERIFY** the specific disputed fact directly (grep, read, bash on the exact item)
3. **SHOW** the verification output before making claims about which source is correct
Substitute evidence (e.g., "smoke test passes") does NOT address specific contradictions (e.g., "function not found in file"). "I believe it's stale" is not verification — running `grep` on the disputed file is.

## Quality Gate Review
- At the start of each session, if `~/.claude/last-session-qg-failures.txt` exists, read it and surface the previous session's block summary to the user before starting work. This is the automatic effectiveness check — no manual `qg failures` needed.
- **Plan mode**: Quality gate Stop hooks are inactive during plan mode. Self-verify claims: before writing a claim to the plan file, confirm it with a Read/Grep/Bash tool. Plan mode responses are not quality-gated.

## Session Management
- Context hooks fire automatically: toast at 70%, Claude gets message at 90%
- Run `/compact` when statusline shows yellow `up ctx` or red `/compact` hint
- **Before /compact**: Always save important findings, progress, and session state to memory files and update MEMORY.md before compacting. Never compact without saving first.
- Session cost/duration auto-logged to `~/.claude/audit-log.md` — view with `claude-cost`
- Use `~/.claude/projects/C--Users-Matt1/memory/MEMORY.md` for cross-session facts

## Effort Level (Auto)
`task-classifier` hook auto-injects complexity (TRIVIAL→DEEP), mode (acceptEdits/plan), and agent model (haiku/sonnet/opus) before every response. TRIVIAL/SIMPLE = acceptEdits + haiku agents. MODERATE = acceptEdits + sonnet. COMPLEX = plan + sonnet. DEEP = plan + opus. No tag → default MODERATE/acceptEdits. User instructions always override.

## Language & Project Rules
- Node.js and Python conventions are in `.claude/rules/` (path-scoped, load on demand)
- New projects: `newproject <name>` (shell alias) or `/new-project <name>` (+ Notion dashboard)

## Notion Project Setup
- **EVERY new project gets a Notion dashboard automatically** — opt-out, not opt-in
- The ONLY correct method is `/new-project <name>` — no exceptions
- **NEVER** manually duplicate the template page or create project databases via API
- If user asks to "set up a project" without `/new-project`, STOP and run `/new-project` instead
- To skip Notion: user must explicitly say "no Notion" or "skip Notion"

## Rules for Claude
- Read project CLAUDE.md first — it overrides everything here
- Always check file existence before writing to avoid overwrites of unknown files
- When blocked, ask rather than brute-force
- **After completing any task**, always provide ranked next step suggestions — #1 is the best/most impactful choice, descending from there. **Before listing next steps**: verify each candidate item is not already implemented with a targeted Grep or Bash check. Never suggest items sourced from plan files, session summaries, or memory without confirming they are not already in the code.
- **Quote verification output inline**: When running verification tools (tests, grep, git status, file reads), paste the key output directly in your response text — do NOT just state the conclusion. The quality gate evaluates response text only and cannot see tool call results. Bad: "All tests pass." Good: "Tests pass — `=== Results: 150 passed, 0 failed ===`"
- **Quality gate compliance**: When a Stop hook blocks you with a `decision: "block"` reason:
  1. **Read the block reason** to identify the specific unverified claim or missing evidence
  2. **Run a targeted action** that addresses THAT specific claim (grep the disputed file, re-run the exact test, read the specific config — not a general smoke test or unrelated verification)
  3. **Include the verification output** in your next response
  Then briefly tell the user: "[Quality gate triggered: {what you verified}]". One line, no discussion of the gate itself.
  **CRITICAL — retry failure**: Do NOT respond to a block with the same claim backed by general reasoning ("standard practice", "typically", "usually"). The gate sees this as a repeat ASSUMPTION. The only valid retry is tool output that directly addresses the blocked claim.

## Infrastructure (Auto-Managed)
- **Hooks**: task-classifier (effort routing), validate-bash (destructive cmd blocker), block-secrets (credential leak prevention), context-watch (usage alerts), quality-gate (Stop verification), subagent-quality-gate (SubagentStop verification), stop-failure-log (StopFailure error logging), permission-guard (PermissionRequest dynamic validation), notion-capture/recall (knowledge persistence), pre-compact-snapshot, stop-log, tool-failure-log, session-end-log
- **Plugins**: superpowers, hookify, feature-dev, frontend-design, chrome-devtools-mcp, pr-review-toolkit, figma, serena, notion, context7, + others (19 total)
- **MCP**: Docker (active); Playwright, Postgres, AWS, code-search (disabled, re-enable as needed)
- **Permissions**: `Bash(*)` allowed; `rm -rf`, `wget`, `sudo`, `gh repo delete`, `git push --force`, system commands denied. WebFetch allowlisted per-domain. Hooks dir and settings.json are write-protected.
- **File exclusions**: `.env*`, `*.key`, `*.pem`, `*.pfx`, `credentials*`, `*.secret` excluded from suggestions
- **Statusline**: custom script at `~/.claude/statusline.sh`

This file applies to ALL projects. Project-level CLAUDE.md takes precedence.

## Compact Instructions
When compacting, preserve the following in the summary:
- **Active task**: what we were working on, current step, and immediate next action
- **Files modified**: exact paths of any files created or changed this session
- **Key findings**: errors found, decisions made, approaches tried and rejected
- **Pending items**: anything explicitly deferred, flagged, or noted as "do next"
- **Plan file**: if a plan file is active, note its path so it can be re-read after compaction
- **Memory state**: confirm memory files were saved before compacting; if not, save them first

Do NOT compact mid-task without saving findings to `~/.claude/projects/C--Users-Matt1/memory/` first.

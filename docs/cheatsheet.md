# Terminal + Claude Code Cheat Sheet
Last updated: 2026-03-22

---

## Navigation & File Browsing

| Command | What it does |
|---|---|
| `fzf` | Interactive fuzzy finder (pipe files/text into it) |
| `Ctrl+T` | Fuzzy find a file and insert path (Git Bash, after fzf init) |
| `Ctrl+R` | Fuzzy search command history (Git Bash, after fzf init) |
| `eza` | Modern `ls` — colorized, Git-aware |
| `eza -la` | Long list with hidden files |
| `eza --tree` | Tree view of directory |
| `cat <file>` | → aliased to `bat` (syntax-highlighted, line-numbered) |
| `bat <file>` | Syntax-highlighted file preview |
| `bat <file> --plain` | bat without decorations |
| `rg <pattern>` | Fast regex search across files (ripgrep) |
| `rg <pattern> -t py` | Search only Python files |
| `rg <pattern> -l` | List matching files only |

---

## Git

| Command | What it does |
|---|---|
| `git diff` | Side-by-side diff via delta (auto) |
| `git log` | Syntax-highlighted log via delta (auto) |
| `git status` | Standard (delta applies to diff views) |
| `gh pr create` | Create a PR from terminal |
| `gh pr list` | List open PRs |
| `gh issue create` | Create a GitHub issue |
| `gh repo clone <repo>` | Clone a repo |
| `tig` | Interactive Git TUI — browse commits, branches, diffs |
| `tig <file>` | Git history for a specific file |

---

## JSON / APIs

| Command | What it does |
|---|---|
| `jq .` | Pretty-print JSON |
| `jq '.key'` | Extract a key from JSON |
| `jq '.[] \| .name'` | Map over array, extract field |
| `cat file.json \| jq .` | Pipe file into jq |
| `http GET <url>` | HTTP GET (httpie) |
| `http POST <url> key=val` | HTTP POST with JSON body |
| `http GET <url> Header:Value` | Request with custom header |
| `http -v GET <url>` | Verbose (show request + response) |

---

## Python

| Command | What it does |
|---|---|
| `ipython` | Rich interactive Python REPL (tab complete, history, magic) |
| `black <file>` | Auto-format Python file |
| `black .` | Format entire project |
| `mypy <file>` | Type-check a Python file |
| `mypy --strict <file>` | Strict type checking |
| `ruff check .` | Lint entire project |
| `ruff check --fix .` | Lint + auto-fix |
| `poetry new <project>` | Create new project with pyproject.toml |
| `poetry add <pkg>` | Add a dependency |
| `poetry shell` | Activate project virtualenv |
| `poetry run <cmd>` | Run command inside virtualenv |
| `http` | REST client (alias for httpie) |

---

## Node / TypeScript

| Command | What it does |
|---|---|
| `ts-node <file.ts>` | Run TypeScript directly (no compile step) |
| `eslint <file>` | Lint JS/TS file |
| `eslint . --fix` | Lint + auto-fix entire project |
| `prettier --write <file>` | Format a file |
| `prettier --write .` | Format entire project |
| `nodemon <file>` | Run and auto-restart on file change |
| `pnpm install` | Install dependencies (preferred over npm) |
| `pnpm add <pkg>` | Add a package |
| `pnpm dlx <tool>` | Run a one-off tool (like npx) |
| `tsc --noEmit` | Type-check TypeScript without emitting files |

---

## Deployment / Cloud CLIs

| Command | What it does |
|---|---|
| `vercel` | Deploy to Vercel |
| `vercel dev` | Local Vercel dev server |
| `railway up` | Deploy to Railway |
| `railway logs` | Tail Railway logs |
| `firebase deploy` | Deploy to Firebase |
| `firebase serve` | Local Firebase emulator |
| `eas build` | Build Expo app (EAS) |
| `eas submit` | Submit to App Store / Play Store |

---

## Timestamp Tools

| Command | What it does |
|---|---|
| `cmd \| ts` | Prefix every output line with `[HH:MM:SS]` (Git Bash) |
| `cmd \| ts -s` | Prefix with elapsed seconds `[+0.003s]` |
| `cmd \| ts '[%Y-%m-%d %H:%M:%S]'` | Custom datetime format |
| `cmd \| ts -Elapsed` | Elapsed mode in PowerShell |
| `history` | Show command history with timestamps |
| `raw <cmd>` | Run interactive program bypassing timestamp redirect (Git Bash) |

---

## Terminal Recording

| Command | What it does |
|---|---|
| `terminalizer record demo` | Start recording terminal to `demo.yml` |
| `terminalizer play demo` | Play back recording |
| `terminalizer render demo` | Render to GIF |

---

## Claude Code Shortcuts

| Shortcut / Command | What it does |
|---|---|
| `/compact` | Compress context (use at 70%+, type manually — no keybinding) |
| `/clear` | Clear context (use at 85%+) |
| `/memory` | View/edit persistent memory |
| `/review [path]` | Triage code → CRITICAL / WARNING / INFO findings |
| `/ticket [desc]` | Generate structured dev ticket |
| `/new-project <name>` | Bootstrap project + Notion dashboard |
| `/recall [query]` | Query Notion knowledge bases |
| `/standup` | Generate daily standup report |
| `/sync-github [repo]` | Sync GitHub issues → Notion Sprint board |
| `/review-captures` | Inspect recent Notion auto-captures |
| `/health` | Run Notion workspace health check |
| `/last-run` | Read last-run.md after bridge runs |
| `/audit` | Exhaustive codebase audit |
| `/walkthrough` | Systematic QA app testing |
| `/btw <question>` | Ask a side question without derailing the current task |
| `/stats` | Show token usage and cost breakdown for this session |
| `/diff` | Summarize all pending/uncommitted changes |
| `/branch` | Show current branch + recent commits summary |
| `/export` | Export conversation to markdown |
| `/doctor` | Diagnose Claude Code installation and config issues |
| `/reload-plugins` | Reload all plugins without restarting |
| `/rewind` | Restore a previous checkpoint (Esc+Esc also works) |
| `/open <file>` | Open a file in VS Code from the terminal session |
| `claude -p "task"` | Run Claude headlessly (OpenClaw/automation) |
| `claude --resume` | Resume last session |
| `ctrl+k ctrl+t` | Toggle Todos panel |
| `ctrl+k ctrl+o` | Toggle Transcript |
| `Esc+Esc` | Checkpoint rewind (restore code + conversation state) |

## Claude Code Context Management

| State | Action |
|---|---|
| 0–70% | Work freely |
| 70%+ | Windows toast fires automatically (context-watch hook) |
| 70–85% | Run `/compact` with focus instructions |
| 85%+ | `/clear` + `claude --resume`; hook injects reminder to Claude |

## Claude Code Cost & Audit

| Command | What it does |
|---|---|
| `claude-cost` | Show cost summary for last 4 weeks (grouped by ISO week) |
| `claude-cost-all` | Show all-time cost summary |
| `claude-cost --week 8` | Show last 8 weeks |

Audit log: `~/.claude/audit-log.md` — one row per session Stop event, written by `stop-log.py` hook.

---

## Bash Aliases (active in Git Bash)

| Alias | Expands to |
|---|---|
| `ls` | `eza` (Git-aware, icons, tree mode) |
| `cat` | `bat --paging=never` |
| `git` | `git -c color.ui=always` |
| `raw <cmd>` | Run cmd on real TTY (bypasses timestamp pipe) |
| `newproject <name> [node\|python\|plain]` | Bootstrap git repo + auto-fill CLAUDE.md |

---

## Key Paths

| What | Path |
|---|---|
| Bash config | `~/.bashrc` |
| PS7 profile | `~/OneDrive/Documents/PowerShell/Microsoft.PowerShell_profile.ps1` |
| `ts` script | `~/bin/ts` |
| Claude global config | `~/.claude/settings.json` |
| Claude keybindings | `~/.claude/keybindings.json` |
| Claude memory | `~/.claude/projects/C--Users-Matt1/memory/` |
| This cheat sheet | `~/.claude/docs/cheatsheet.md` |
| Claude hooks dir | `~/.claude/hooks/` |
| Statusline script | `~/.claude/statusline.sh` + `~/.claude/statusline_parse.py` |
| Statusline state | `~/.claude/statusline-state.json` (written each turn) |
| Audit log | `~/.claude/audit-log.md` |
| Audit summary script | `~/.claude/audit-summary.py` |
| CLAUDE.md template | `~/.claude/templates/CLAUDE.project.md` |
| MCP credentials | `~/.claude/.env` |

---

## MCP Server Credentials

| Server | Needs credentials | Env var(s) |
|---|---|---|
| `context7` | No | — |
| `docker` | No | — |
| `playwright` | No | Disabled; re-enable in settings.json |
| `postgres` | Yes | `POSTGRES_CONNECTION_STRING` |
| `aws` | Yes | `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` + `AWS_REGION` |
| `qdrant` | Yes | `QDRANT_URL` + `QDRANT_API_KEY` |

**To activate:** edit `~/.claude/.env`, set the var, restart terminal.

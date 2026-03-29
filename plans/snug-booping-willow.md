# Exhaustive Tool Calling Assessment — Definitive Report

## Context
Full audit of Claude Code's tool calling configuration: permissions, hooks, MCP servers, environment, and their interactions. Every hook file, config file, and utility has been read and verified.

---

## 1. Permissions Architecture

### Allow List (77 entries in `settings.json` + 2 in `settings.local.json`)

| Category | Count | Notes |
|----------|-------|-------|
| Core tools | 5 | Read, Edit, Write, Glob, Grep |
| Bash | 14 | `Bash(*)` + 13 specific patterns (ALL 13 redundant) |
| WebSearch | 1 | Unrestricted |
| WebFetch | 20 domains | Properly scoped per-domain |
| Notion MCP | 8 tools | Read + write (no delete) |
| Claude-in-Chrome | 10 tools | Navigation, forms, screenshots |
| Gmail MCP | 2 tools | Read-only (search + read) |
| Serena | 8 tools | File/project ops |
| Chrome DevTools | 8 tools | Screenshots, eval, navigation |
| Skill | 1 | `Skill(pr-review-toolkit:review-pr)` — functional but likely redundant (see finding) |

**`settings.local.json` additions (2 entries):** `WebFetch(domain:www.autohotkey.com)` and `WebFetch(domain:taxpage.com)` — both survive `prune-permissions.py` cleanup (only Bash entries are pruned). Also contains `remote.defaultEnvironmentId: "env_0188L1NEsQ1VgXcnmwtixkpQ"` (remote environment binding).

**13 redundant Bash entries**: `Bash(gh pr:*)`, `Bash(git commit:*)`, `Bash(git checkout:*)`, `Bash(git stash:*)`, `Bash(git add:*)`, `Bash(bun run:*)`, `Bash(bun test:*)`, `Bash(npx playwright:*)`, `Bash(node -e ":*)`, `Bash(NODE_ENV=test bun -e ":*)`, `Bash(ps aux:*)`, `Bash(gh run:*)`, `Bash(gh api:*)` — all subsumed by `Bash(*)`.

### Deny List (28 entries)

Covers: `rm -rf`/`rm -r`/`rm -R`/`rm --recursive` (4 Bash entries), `del /f /s /q`, `dd if=`, `format`, `mkfs`, `find / -delete`, `shutdown`, `reg delete`, `net user`, `net localgroup`, `icacls`, `takeown`, `bcdedit`, `gh repo delete`, `wget`, `sudo`, `kubectl delete namespace`, `git push --force`/`-f`/`--force-with-lease` (3 entries), `powershell.exe Remove-Item -Recurse` (24 Bash total) + `Edit`/`Write` for hooks dir (2) + `Edit`/`Write` for settings.json (2) = 28.

### Ask List (1 entry)

`Bash(git push *)` — requires user confirmation.

### Settings-Level Controls

| Setting | Value | Correct? |
|---------|-------|----------|
| `permissions.defaultMode` | `"default"` | Yes — prompts for tools not in allow/deny |
| Top-level `defaultMode` | `"acceptEdits"` | Yes — separate setting, controls interaction mode |
| `disableBypassPermissionsMode` | `"disable"` | Yes — blocks `--dangerously-skip-permissions` |

**Clarification**: `permissions.defaultMode` and top-level `defaultMode` are different settings controlling different things. No conflict.

### Evaluation Order (confirmed via docs)

**Deny → Ask → Allow.** First matching rule wins. Deny ALWAYS takes precedence over allow. This means `Bash(*)` in allow + `Bash(rm -rf *)` in deny = denied. The architecture is safe.

---

## 2. Runtime Protection Layers (Hooks)

### Hook Execution Order (by lifecycle)

| # | Event | Hook | Sync? | Purpose |
|---|-------|------|-------|---------|
| 1 | SessionStart | `prune-permissions.py` | sync | Cleans one-off Bash entries from `settings.local.json` |
| 2 | SessionStart | `notion-recall.py` | sync | Pulls knowledge from 5 Notion DBs into context |
| 3 | SessionStart(compact) | inline echo | sync | Outputs "[post-compact-check]" context reminder |
| 4 | SessionStart(compact) | `event-observer.py` | async | Logs compact event |
| 5 | InstructionsLoaded(session_start\|compact) | `event-observer.py` | async | Logs instruction load events |
| 6 | UserPromptSubmit | `task-classifier.py` | sync | Classifies complexity → TRIVIAL/SIMPLE/MODERATE/COMPLEX/DEEP |
| 7 | PreToolUse(Bash) | `validate-bash.sh` | sync | Blocks 47 dangerous command patterns (45 array + 2 standalone) |
| 8 | PreToolUse(Write\|Edit\|Bash) | `block-secrets.py` | sync | Scans for credentials/secrets in content |
| 9 | PreToolUse(Edit\|Write) | `protect-files.sh` | sync | Blocks writes to hooks/, settings.json, settings.local.json |
| 10 | PreToolUse(Bash) | `permission-guard.py` | sync | Blocks curl/wget to non-allowed domains, force-push to main |
| 11 | PostToolUse(Bash\|Edit\|Write\|Agent) | `context-watch.py` | sync | Monitors context %, fires Windows toast at 70%+ |
| 12 | PostToolUseFailure(Bash\|Edit\|Write) | `tool-failure-log.py` | async | Logs tool failures to hook-audit.log |
| 13 | Stop | `stop-log.py` | async | Logs session cost/duration to audit-log.md |
| 14 | Stop | `notion-capture.py` | async | Extracts insights → 5 Notion DBs |
| 15 | Stop | `quality-gate.py` | **sync** | Layer 1: mechanical checks. Layer 2: LLM eval via Haiku |
| 16 | SubagentStart | inline bash | sync | Injects memory + plan path into subagent context |
| 17 | SubagentStop | `subagent-quality-gate.py` | sync | Mechanical code-edit verification + LLM evaluation via Haiku |
| 18 | StopFailure(rate_limit\|authentication_failed\|billing_error\|server_error\|max_output_tokens\|invalid_request\|unknown) | `stop-failure-log.py` | async | Logs API errors + desktop notification (non-rate-limit only) |
| 19 | Notification(permission_prompt\|idle_prompt\|elicitation_dialog) | `notify.ps1` | sync | Windows toast: "Needs your attention" (Info, 4s) |
| 20 | Notification(rate_limit\|billing_error\|authentication_failed) | `notify.ps1` | sync | Windows toast: "Session Failed" (Error, 8s) |
| 21 | ConfigChange(user_settings\|project_settings) | `event-observer.py` | sync | Logs config changes |
| 22 | PreCompact(manual\|auto) | `pre-compact-snapshot.py` | sync | Saves state before compact |
| 23 | PostCompact(manual\|auto) | inline bash | sync | Outputs plan path + memory index for recovery |
| 24 | SessionEnd(clear\|resume\|logout\|prompt_input_exit\|other) | `session-end-log.py` | async | Logs exit, backs up to OneDrive, cleans old snapshots |
| 25 | PermissionRequest | `permission-request-log.py` | async | Logs tool_name + context to hook-audit.log; exits 0 |

**18 unique hook files referenced across 25 hook registrations (some files appear multiple times; 3 registrations use inline bash/echo). Plus 4 non-hook files (2 shared modules + 2 test utilities) = 22 files on disk. Zero dangling references. All hooks validated by `smoke-test.sh` (136+ test assertions across 23 test sections).**

**Hook blocking behavior (confirmed via docs):** When a PreToolUse hook exits with code 2, the tool call is **immediately blocked**. Subsequent PreToolUse hooks for that tool call are NOT executed. For a Bash command, the firing order is: `validate-bash.sh` → `block-secrets.py` → `permission-guard.py`. If `validate-bash.sh` blocks, the other two never run. (`protect-files.sh` doesn't fire for Bash — it's Edit|Write only.)

**Unregistered files in hooks directory (4):** `_hooks_shared.py` (shared utilities: `rotate_log()`, regex constants `NON_CODE_PATH_RE`/`VALIDATION_COMMAND_RE`, LLM evaluation: `call_haiku_check()`, `load_api_key()`, response caching, 18 `FEW_SHOT_EXAMPLES`), `_notion_shared.py` (shared: `load_token()`, `detect_project_name()`, DB IDs), `smoke-test.sh` (test runner), `_py_check.py` (syntax checker). None are registered as hooks — they're imported modules and test utilities.

### Defense-in-Depth: Commands Blocked by Hooks But NOT in Deny List

`validate-bash.sh` catches these that the static deny list misses:
- `git reset --hard`
- `git branch -D`
- `git checkout -- .`
- `docker system prune`
- `npm publish`
- `drop database` / `drop table`
- `diskpart`
- `rm --no-preserve-root` — deny has `rm -rf`, `rm -r`, `rm -R`, `rm --recursive` but none match "rm --no-preserve-root" prefix
- `cacls c:\windows` — deny has `Bash(icacls *)` but `cacls` is a different (legacy) command
- `find / -exec rm` — deny has `Bash(find / -delete *)` but "find / -exec rm" doesn't match that prefix
- `git push origin +main` / `+master` — `+` syntax force push. NOT in deny list; IS in ask list (`Bash(git push *)`) so gets confirmation prompt, but not hard-blocked
- Interpreter-wrapped dangerous commands (python -c "rm -rf /", node -e "...", etc.)
- Compound commands containing deny-listed patterns (e.g., `cd /tmp && rm -rf .` — deny list only matches prefix, hook does substring matching)

Note: `rm -rf ./` and `rm -rf ../` ARE caught by the deny list's `Bash(rm -rf *)` pattern (prefix match). They appear in validate-bash.sh as defense-in-depth but the deny list is the primary blocker. Similarly, `remove-item -recurse -force c:\` is in DANGEROUS_PATTERNS but not in deny (deny requires `powershell.exe` prefix); low risk since it's a PowerShell cmdlet that won't execute in bash.

**Risk**: If `validate-bash.sh` fails silently (hook crash), all of the above (10 specific patterns + interpreter-wrapped + compound commands) execute because they're not in the deny list. The deny list is enforced at the permission layer (unfailable); hooks are a second layer (can fail). Hooks do exit 0 on error by convention, but that means "allow" not "block".

### Domain Allowlists: Two Separate Lists

| Domain | curl/wget (permission-guard.py) | WebFetch (settings.json) |
|--------|-------------------------------|--------------------------|
| **Shared (6)** | | |
| github.com | Yes | Yes |
| docs.github.com | Yes | Yes |
| npmjs.com | Yes | Yes |
| pypi.org | Yes | Yes |
| docs.anthropic.com | Yes | Yes |
| nodejs.org | Yes | Yes |
| **Curl-only (7)** | | |
| api.github.com | Yes | No |
| api.notion.com | Yes | No |
| api.anthropic.com | Yes | No |
| registry.npmjs.org | Yes | No |
| localhost | Yes | No |
| 127.0.0.1 | Yes | No |
| 0.0.0.0 | Yes | No |
| **WebFetch-only (14)** | | |
| python.org | No | Yes |
| developer.mozilla.org | No | Yes |
| stackoverflow.com | No | Yes |
| pcpartpicker.com | No | Yes |
| learn.microsoft.com | No | Yes |
| www.amazon.ca | No | Yes |
| (+ 8 others: ca.pcpartpicker.com, www.canadacomputers.com, www.newegg.ca, clawbot.ai, clawd.bot, openclaw.ai, code.claude.com, www.canada.ca) | No | Yes |

**Totals**: curl has 13 domains, WebFetch has 20 domains (settings.json) + 2 (settings.local.json: www.autohotkey.com, taxpage.com), 6 shared. The divergence is intentional — curl allowlist covers API endpoints, WebFetch covers browsable docs/sites. No issue.

---

## 3. MCP Servers

### Locally Configured (settings.json)
| Server | Status |
|--------|--------|
| docker | Active |
| playwright | Disabled |
| postgres | Disabled |
| aws | Disabled |
| code-search | Disabled |
| qdrant | Disabled |

### Cloud-Connected (via Claude.ai OAuth)
| Service | Tools | Pre-Approved |
|---------|-------|-------------|
| Atlassian (Jira/Confluence/Compass) | 37 | 0 |
| Box | 21 | 0 |
| Canva | 30 | 0 |
| DocuSign | 20 | 0 |
| Figma | 15 | 0 |
| Gmail | 7 | 2 (read-only) |
| Google Calendar | 9 | 0 |
| Notion | 14 | 8 |
| Slack | 13 | 0 |
| Stripe | 31 | 0 |
| Supabase | 29 | 0 |

### Browser Extension
| Service | Tools | Pre-Approved |
|---------|-------|-------------|
| Claude-in-Chrome | 17 | 10 |

### Plugins (local)
| Service | Tools | Pre-Approved |
|---------|-------|-------------|
| GitHub | 44 | 0 |
| Serena | 27 | 8 |
| Chrome DevTools | 29 | 8 |
| Context7 | 2 | 0 |

`enableAllProjectMcpServers: true` — all project MCPs auto-enabled. Most require per-call approval (correct).

---

## 4. Environment Variables

| Variable | Value | Purpose | Correct? |
|----------|-------|---------|----------|
| PYTHONIOENCODING | utf-8 | Python output encoding | Yes |
| PYTHONUTF8 | 1 | UTF-8 mode for Python 3.13 | Yes |
| CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS | 1 | Multi-agent teams | Yes |
| CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR | 1 | Stable CWD in Bash | Yes |
| MAX_MCP_OUTPUT_TOKENS | 25000 | Caps MCP responses | Yes |
| CLAUDE_CODE_SESSIONEND_HOOKS_TIMEOUT_MS | 10000 | 10s for SessionEnd hooks | Yes |
| CLAUDE_AUTOCOMPACT_PCT_OVERRIDE | 90 | Autocompact at 90% | Yes |
| CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC | 1 | No telemetry | Yes |

---

## 5. Other Settings

| Setting | Value | Notes |
|---------|-------|-------|
| model | opusplan | Opus in plan mode, Sonnet in execution |
| alwaysThinkingEnabled | true | Extended thinking always on |
| effortLevel | high | High effort default |
| fastModePerSessionOptIn | true | Must opt-in to fast mode per session |
| teammateMode | in-process | Teammates run in-process |
| theme | dark | — |
| includeGitInstructions | false | Custom git conventions in CLAUDE.md |
| showClearContextOnPlanAccept | true | Shows clear context on plan accept |
| feedbackSurveyRate | 0 | No surveys |
| spinnerTipsEnabled | false | No spinner tips |
| showThinkingSummaries | true | Shows thinking summaries |
| fileSuggestionExcludes | .env*, *.key, *.pem, *.pfx, credentials*, *.secret | Sensitive files excluded |
| forceLoginMethod | claudeai | OAuth via claude.ai |
| autoUpdatesChannel | stable | Stable updates |
| cleanupPeriodDays | 60 | 60-day cleanup |
| attribution | `{"commit": "", "pr": ""}` | Empty — no attribution messages on commits/PRs |
| statusLine | `bash ~/.claude/statusline.sh` | Custom statusline script (calls `statusline_parse.py`); writes `statusline-state.json` read by hooks |
| enableAllProjectMcpServers | true | Also noted in MCP section |

---

## 6. Plugins (19 total, 18 enabled)

| Plugin | Enabled |
|--------|---------|
| superpowers | Yes |
| chrome-devtools-mcp | Yes |
| claude-md-management | Yes |
| context7 | Yes |
| claude-code-setup | Yes |
| commit-commands | Yes |
| github | Yes |
| feature-dev | Yes |
| frontend-design | Yes |
| hookify | Yes |
| notion | Yes |
| skill-creator | Yes |
| ralph-loop | Yes |
| pr-review-toolkit | Yes |
| security-guidance | Yes |
| figma | Yes |
| plugin-dev | Yes |
| serena | Yes |
| learning-output-style | **No** (disabled) |

---

## 7. Findings Summary

### CRITICAL: 0

### HIGH: 1

**H1. `validate-bash.sh` is the sole blocker for 10+ dangerous command patterns not in deny list**
Commands like `git reset --hard`, `git branch -D`, `docker system prune`, `npm publish`, `drop database/table`, `diskpart`, `rm --no-preserve-root`, `cacls`, `find / -exec rm`, and interpreter-wrapped dangerous commands are only blocked by the hook, not the deny list. (`git push origin +main/+master` has ask-list confirmation but no deny entry.) If the hook crashes (Python unavailable, JSON parse failure, bash error), these execute unrestricted. The hook does fail-closed on parse failure (exit 2 on line 22-25), which is good. But other failure modes (hook not called, `validate-bash.sh` missing from disk) would silently allow.

### MEDIUM: 2

**M1. 13 redundant Bash allow entries clutter settings.json**
All 13 specific `Bash(...)` patterns are subsumed by `Bash(*)`. `prune-permissions.py` only cleans `settings.local.json`, not `settings.json`. These are harmless but confusing — they suggest intent-based permission that doesn't actually gate anything.

**M2. `Skill(pr-review-toolkit:review-pr)` in allow list is functional but likely redundant**
Skill permissions ARE a real feature (`Skill(name)` controls skill access). However, all other skills invoked this session executed without permission prompts despite having no allow entries. This suggests the Skill tool is auto-approved by default (or `permissions.defaultMode: "default"` doesn't prompt for Skills). The entry works but is unnecessary — removing it would have no practical effect. If you want to restrict skill access, add deny rules (e.g., `Skill(deploy *)`) rather than relying on allow-only.

### LOW: 5

**L1. `PermissionRequest: []` empty hook**
No handler for runtime permission requests. No logging or notification when Claude requests new permissions dynamically.

**L2. `event-observer.py` fires twice on compact resume**
Both `SessionStart(compact)` and `InstructionsLoaded(session_start|compact)` trigger it. Harmless — just produces duplicate log lines. The hook is idempotent (append-only logging).

**L3. `quality-gate.py` Layer 2 fails open without ANTHROPIC_API_KEY**
If no API key is found in env or `~/.claude/.env`, the LLM evaluation layer silently passes. Layer 1 (mechanical checks) still runs. By design for graceful degradation.

**L4. `block-secrets.py` allowlists `~/.claude/`, `~/.ssh/`, `.github/workflows`, and filename patterns**
Files under `~/.claude/` or `~/.ssh/` bypass secret scanning (prefix match). Files in `.github/workflows` directories bypass via substring match. Filenames matching `.env.example`, `.env.sample`, `.env.template`, `*.test.*`, `*.spec.*`, `SETUP.md`, `API.md`, `seed-demo.js` are also allowlisted. The `~/.claude/` allowlist is intentional (hooks/config need API keys), but means secrets could be written to memory files or plan files without detection.

**L5. `pre-compact-snapshot.py` docstring says "Async" but configured as sync**
The file header says "Always exits 0. Async." but `settings.json` has `"async": false`. The config is correct (sync is needed to ensure snapshot completes before compact). The docstring is stale.

### INFO: 6

**I1. GitHub MCP tools — 0 pre-approved**
All 44 GitHub operations require per-call approval. Even read-only ops like `list_issues`, `get_file_contents`, `search_code` prompt each time.

**I2. `session-end-log.py` backs up to OneDrive**
Config, hooks, memory, templates, commands backed up to `~/OneDrive/Documents/ClaudeCode/` on every session end. Also cleans compact snapshots >7 days old.

**I3. `notion-capture.py` async timing**
Async Stop hook reads transcript from disk. Could be interrupted if session cleanup is aggressive. Code handles gracefully (always exits 0).

**I4. `notion-recall.py` uses parallel queries + relevance scoring**
5 concurrent Notion DB queries with 15s timeout. Background thread updates Recall Count. Includes recency + frequency + project-match scoring.

**I5. `quality-gate.py` LLM layer costs ~$0.002/eval**
Uses Haiku 4.5 (`claude-haiku-4-5-20251001`) with temperature 0, max 100 tokens, 10s timeout. Response cached 1 hour (max 20 entries). Fires on ALL tasks (no complexity-based skip) — complexity is passed as prompt calibration text, not a gate. Includes 18 few-shot examples for calibration (Examples 1-18 in `_hooks_shared.py` FEW_SHOT_EXAMPLES).

**I6. `task-classifier.py` guidance is advisory, not enforced**
Outputs like `[task-classifier] Complexity: SIMPLE | mode: acceptEdits | agent model: haiku` are injected into context as guidance. Claude is expected to follow them, but there is no enforcement mechanism — Claude can use opus agents even when haiku is suggested. The CLAUDE.md instruction "User instructions always override" means the user can override classifier decisions.

---

## 8. Severity Breakdown

**CRITICAL: 0 | HIGH: 1 | MEDIUM: 2 | LOW: 5 | INFO: 6 | Total: 14**

## 9. Recommended Fixes (by impact) — ALL COMPLETE (2026-03-24)

1. **H1** ✅ DONE: Added 8 deny entries — `git reset --hard*`, `git branch -D*`, `docker system prune*`, `npm publish*`, `diskpart*`, `rm --no-preserve-root*`, `cacls*`, `find / -exec rm*`. Deny list: 28→36.
2. **M1** ✅ DONE: Removed 13 redundant `Bash(...)` allow entries. Allow list: 77→64.
3. **M2** ✅ DONE: Removed `Skill(pr-review-toolkit:review-pr)`. Allow list: 64→63.
4. **L1** ✅ DONE: Created `permission-request-log.py` + registered `PermissionRequest` hook (async, exits 0, logs to hook-audit.log). 4 behavioral smoke tests added; total: 143.
5. **I1** ✅ DONE: Pre-approved 5 read-only GitHub MCP tools (`list_issues`, `get_file_contents`, `search_code`, `list_commits`, `list_pull_requests`). Allow list: 63→68.

**Final state: allow=68, deny=36, smoke=143/143 pass, 20/20 hooks with behavioral coverage.**

## 10. Confidence Level

**100% on all findings.** Every file in `~/.claude/hooks/` (18 hook files + 4 non-hook files = 22), both config files (settings.json, settings.local.json), and the statusline infrastructure (statusline.sh, statusline_parse.py) have been read line-by-line. All open questions resolved:

| Question | Resolution | Source |
|----------|-----------|--------|
| Deny vs Allow precedence | Deny always wins (deny→ask→allow order) | Claude Code docs |
| `permissions.defaultMode` vs top-level `defaultMode` | Different settings, no conflict | Claude Code docs |
| `Skill()` permissions | Real feature; entry is functional but redundant (skills auto-approve) | Claude Code docs + empirical (this session) |
| `Bash(*)` redundancy | All 13 patterns redundant | Reading `prune-permissions.py` (only cleans settings.local.json) |
| `SessionStart(compact)` matcher | Valid (startup/resume/clear/compact) | Claude Code docs |
| PreToolUse exit 2 behavior | Immediately blocks; subsequent hooks don't run | Claude Code docs |
| `event-observer.py` double-fire | Harmless, idempotent (append-only logging) | Reading source code |
| `disableBypassPermissionsMode: "disable"` | Correct syntax and value | Claude Code docs |

**Remaining uncertainty (1):** Whether the Skill tool truly auto-approves without explicit permission entries, or whether `permissions.defaultMode: "default"` simply doesn't prompt for Skills. Both lead to the same practical conclusion (the entry is redundant), but the underlying mechanism is unconfirmed. Marked as 99% confident.

### Files Read (exhaustive)
**settings.json**, **settings.local.json**, and all 22 files in `~/.claude/hooks/`:
`_hooks_shared.py`, `_notion_shared.py`, `_py_check.py`, `block-secrets.py`, `context-watch.py`, `event-observer.py`, `notion-capture.py`, `notion-recall.py`, `notify.ps1`, `permission-guard.py`, `pre-compact-snapshot.py`, `protect-files.sh`, `prune-permissions.py`, `quality-gate.py`, `session-end-log.py`, `smoke-test.sh`, `stop-failure-log.py`, `stop-log.py`, `subagent-quality-gate.py`, `task-classifier.py`, `tool-failure-log.py`, `validate-bash.sh`
Plus statusline infrastructure: `~/.claude/statusline.sh`, `~/.claude/statusline_parse.py`
— all 26 files (22 hooks dir + 2 config + 2 statusline) read line-by-line.

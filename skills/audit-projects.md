# Skill: /audit-projects

Scan all project CLAUDE.mds on the Desktop for known bad patterns and report findings.

## Trigger
User says: `/audit-projects` or "audit all projects" or "scan projects for issues"

## Steps

1. **Discover projects** — find all CLAUDE.md files under `C:\Users\Matt1\OneDrive\Desktop\`:
   ```bash
   find "/c/Users/Matt1/OneDrive/Desktop" -maxdepth 2 -name "CLAUDE.md" | sort
   ```

2. **Run pattern checks** on each file. Flag any match as an issue:

   | Pattern | Severity | Description |
   |---------|----------|-------------|
   | `claude-opus-4-5` | MEDIUM | Previous-gen model — current is `claude-opus-4-6` |
   | `claude-sonnet-4-5` | MEDIUM | Previous-gen model — current is `claude-sonnet-4-6` |
   | `git add \.` or `git add -A` | MEDIUM | Unsafe staging — should be `git add <specific-files>` |
   | `git add \. ` | MEDIUM | Same (with trailing space) |
   | `ntn_[A-Za-z0-9]{40,}` | CRITICAL | Hardcoded Notion API key |
   | `secret_[A-Za-z0-9]{40,}` | CRITICAL | Hardcoded secret |
   | `sk-[A-Za-z0-9]{40,}` | CRITICAL | Hardcoded API key |
   | `[A-Za-z0-9]{32,}` in key context | HIGH | Possible hardcoded credential |
   | `claude-3-haiku\|claude-3-sonnet\|claude-3-opus` | MEDIUM | Outdated Claude 3 model reference |

3. **Also check .gitignore** in each project root:
   - Missing `CLAUDE.local.md` → MEDIUM
   - Missing `.env` entry → HIGH
   - Missing `**/.env` or `*.env` → MEDIUM

4. **Output a report** in this format:
   ```
   ## Project Audit Report — [date]

   ### [Project Name] — [N issues]
   - [CRITICAL/HIGH/MEDIUM/LOW] [file:line] [description]

   ### Summary
   - X projects scanned
   - X critical, X high, X medium, X low issues
   - Projects clean: [list]
   ```

5. **For each CRITICAL issue**: immediately offer to fix it.
   For HIGH/MEDIUM: list in NEXT.md under a new `[audit]` section if not already there.

## Notes
- Skip `node_modules/`, `.venv/`, `venv/` directories
- Also scan `.claude/` subdirs if present
- Do NOT modify files during the scan — report only, then ask before fixing
- After reporting, present ranked fix options starting with CRITICAL issues

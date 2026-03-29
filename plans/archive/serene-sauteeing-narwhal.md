# Plan: Fix Vaultlister-3 Config Conflicts with Global Setup

## Context

Audit of vaultlister-3's `.claude/` configuration revealed conflicts between the project setup, a parent directory CLAUDE.md (the App Design Planner), a duplicate CLAUDE.md inside the project, and several smaller inconsistencies. The user sometimes launches Claude Code from inside vaultlister-3 and sometimes from outside, which affects which CLAUDE.md files get loaded.

## Confirmed Findings

| ID | Sev | Issue |
|----|-----|-------|
| CFG1 | CRITICAL | Parent `Claude Code Project Brainstormer/CLAUDE.md` ("never write code") loads when session starts from outside vaultlister-3 |
| CFG2 | HIGH | `claude-docs/CLAUDE.md` has conflicting instructions — merge useful content into main CLAUDE.md, then delete |
| CFG3 | MEDIUM | `consistency-manifest.json` references hook files that don't exist |
| CFG4 | MEDIUM | `bun run db:reset` listed in Key Commands but denied in settings.json |
| CFG5 | MEDIUM | `memory/STATUS.md.lock` stale lock file will block STATUS.md writes |
| CFG6 | LOW | `//c/` double-slash path in settings.local.json |
| CFG7 | LOW | Disabled GitHub MCP still referenced in Post-Scaffold Setup |
| CFG9 | INFO | Rule Precedence section doesn't mention parent CLAUDE.md layer |

## Fixes

### Fix 1: Move vaultlister-3 out of Claude Code Project Brainstormer (CFG1)

**Action:** Move `C:\Users\Matt1\OneDrive\Desktop\Claude Code Project Brainstormer\vaultlister-3\` to `C:\Users\Matt1\OneDrive\Desktop\vaultlister-3\`

This puts vaultlister-3 at its own Desktop location, outside the App Design Planner's directory tree. The parent CLAUDE.md ("never write code") will never be loaded regardless of where Claude Code is launched from.

**Post-move — required path updates:**

1. **Rename Claude Code project memory directory:**
   - FROM: `~/.claude/projects/C--Users-Matt1-OneDrive-Desktop-Claude-Code-Project-Brainstormer-vaultlister-3/`
   - TO: `~/.claude/projects/C--Users-Matt1-OneDrive-Desktop-vaultlister-3/`
   - Contains 37 cross-session memory files (feedback, project state, references). If not renamed, all project memory is disconnected.

2. **Update hardcoded path in `scripts/reconcile-notion.sh` (line 35):**
   ```bash
   # FROM:
   MEMORY_DIR="$HOME/.claude/projects/C--Users-Matt1-OneDrive-Desktop-Claude-Code-Project-Brainstormer-vaultlister-3/memory"
   # TO:
   MEMORY_DIR="$HOME/.claude/projects/C--Users-Matt1-OneDrive-Desktop-vaultlister-3/memory"
   ```

3. **Update path in `.claude/consistency-manifest.json` (line 13):**
   ```json
   // FROM:
   "memory_rules": "~/.claude/projects/C--Users-Matt1-OneDrive-Desktop-Claude-Code-Project-Brainstormer-vaultlister-3/memory/ ..."
   // TO:
   "memory_rules": "~/.claude/projects/C--Users-Matt1-OneDrive-Desktop-vaultlister-3/memory/ ..."
   ```

4. **Non-critical stale paths (leave as-is):** Evidence docs (`docs/evidence/*.md`), playwright reports (`playwright-report/*.json`), and `claude-docs/docs/project-control/STATE_SNAPSHOT.md` contain old absolute paths in log/report output. These are historical records and don't affect functionality.

5. **Git remote:** Path-independent (stored in `.git/config` as a URL). No update needed.

### Fix 2: Merge claude-docs/CLAUDE.md into main CLAUDE.md, then delete (CFG2)

**Step 1 — Merge these unique sections into main `CLAUDE.md`:**

| Section from claude-docs/CLAUDE.md | Add to main CLAUDE.md | Why |
|---|---|---|
| Reference Documents table (api.md, backend.md, frontend.md, database.md, security.md, testing.md) | New section after "Key Commands" | Claude should know these exist for on-demand loading |
| "Never call `router.handleRoute()` from data loading functions (causes infinite loops)" | Add to Critical Rules list | Important guard not in main CLAUDE.md |
| Project Structure tree | New section after "Architecture" | Quick structural overview |
| Key Patterns (API route, DB query, state update) | New section after Reference Documents | Useful quick-reference code patterns |

**Step 2 — Content to NOT merge (already covered or obsolete):**
- Tech Stack table — already in Architecture section
- Code Conventions — already in CLAUDE.md + src/RULES.md
- Commands table — already in Key Commands
- Project Context System / PROJECT_BRAIN.md references — replaced by memory/STATUS.md workflow
- Evolution System (/evolve) — not referenced by current workflow; docs/commands/evolve.md stays available if user wants it later
- "Update PRD.md after features" — stale workflow instruction
- "Check evolution-rules.md before coding" — not part of current session workflow

**Step 3 — Delete `claude-docs/CLAUDE.md`**

All valuable content has been merged. The rest of `claude-docs/` (docs/reference/, docs/commands/, docs/project-control/, PROJECT_BRAIN.md, etc.) remains untouched.

### Fix 3: Fix consistency-manifest.json (CFG3)

**File:** `vaultlister-3/.claude/consistency-manifest.json`
**Action:** Update to reflect reality — project uses global hooks, not project-level hooks.

```json
{
  "deny_patterns": 28,
  "validate_bash_patterns": "global",
  "protected_files": "global",
  "agent_files": 14,
  "memory_rules": 36,
  "_comment": "Project-level hooks not implemented; safety enforcement via ~/.claude/settings.json global hooks."
}
```

### Fix 4: Clarify db:reset in CLAUDE.md (CFG4)

**File:** `vaultlister-3/CLAUDE.md` (~line 87)
**Action:** Change `bun run db:reset` to `bun run db:reset` with "(requires approval)" note.

### Fix 5: Delete stale lock file (CFG5)

**File:** `vaultlister-3/memory/STATUS.md.lock`
**Action:** Delete it. No active session holds this lock.

### Fix 6: Fix double-slash path (CFG6)

**File:** `vaultlister-3/.claude/settings.local.json`
**Action:** Change `"Read(//c/Users/Matt1/.claude/**)"` to `"Read(/c/Users/Matt1/.claude/**)"`.

### Fix 7: Remove stale setup checklist item (CFG7)

**File:** `vaultlister-3/CLAUDE.md` (~line 209)
**Action:** Remove "Set GITHUB_TOKEN in .env" line since the MCP server is disabled.

### Fix 8: Update Rule Precedence (CFG9)

**File:** `vaultlister-3/CLAUDE.md` (~line 150-156)
**Action:** Add note warning about parent directory CLAUDE.md files if sessions launch from outside the project root.

## Files Modified

1. `vaultlister-3/` directory — **moved** from `Claude Code Project Brainstormer/` to Desktop root
2. `~/.claude/projects/C--Users-Matt1-OneDrive-Desktop-Claude-Code-Project-Brainstormer-vaultlister-3/` — **renamed** to `C--Users-Matt1-OneDrive-Desktop-vaultlister-3/` (37 memory files)
3. `vaultlister-3/scripts/reconcile-notion.sh` — edit (update MEMORY_DIR path, line 35)
4. `vaultlister-3/CLAUDE.md` — edit (merge content from claude-docs/CLAUDE.md + 3 small fixes)
5. `vaultlister-3/claude-docs/CLAUDE.md` — **delete** after merge
6. `vaultlister-3/.claude/consistency-manifest.json` — edit (fix path + update hook status)
7. `vaultlister-3/.claude/settings.local.json` — edit (fix double-slash path)
8. `vaultlister-3/memory/STATUS.md.lock` — **delete**

## NOT changing

- `.claude/settings.json` — deny list is intentional and correct
- `.claude/hooks/` — empty by design (global hooks handle safety)
- `.mcp.json` — disabled GitHub MCP is fine
- `claude-docs/docs/` — all reference/command/project-control docs stay intact
- `.husky/` hooks — working correctly
- `Claude Code Project Brainstormer/CLAUDE.md` — stays as-is for design planner work
- Evidence docs / playwright reports with old paths — historical records, no functional impact

## Execution Order

1. **Move vaultlister-3 to Desktop** (Fix 1 step 1)
   ```bash
   mv "/c/Users/Matt1/OneDrive/Desktop/Claude Code Project Brainstormer/vaultlister-3" "/c/Users/Matt1/OneDrive/Desktop/vaultlister-3"
   ```
2. **Rename Claude Code project memory directory** (Fix 1 step 2)
   ```bash
   mv "/c/Users/Matt1/.claude/projects/C--Users-Matt1-OneDrive-Desktop-Claude-Code-Project-Brainstormer-vaultlister-3" "/c/Users/Matt1/.claude/projects/C--Users-Matt1-OneDrive-Desktop-vaultlister-3"
   ```
3. **Update hardcoded path in reconcile-notion.sh** (Fix 1 step 3)
4. **Merge claude-docs/CLAUDE.md content into main CLAUDE.md** (Fix 2 steps 1+2)
5. **Apply CLAUDE.md small fixes**: db:reset note, remove setup item, update rule precedence (Fixes 4, 7, 8)
6. **Delete claude-docs/CLAUDE.md** (Fix 2 step 3)
7. **Fix consistency-manifest.json** — update path + hook status (Fix 3 + Fix 1 step 4)
8. **Fix settings.local.json path** (Fix 6)
9. **Delete STATUS.md.lock** (Fix 5)

## Verification

1. After move: `cd /c/Users/Matt1/OneDrive/Desktop/vaultlister-3 && git status` — confirm repo is intact
2. After memory rename: `ls ~/.claude/projects/C--Users-Matt1-OneDrive-Desktop-vaultlister-3/memory/ | wc -l` — should be 37
3. After reconcile-notion.sh edit: `bash scripts/reconcile-notion.sh` dry run — confirm it finds the memory dir
4. After CLAUDE.md merge: read the file and check for duplicate sections or contradictions
5. After lock file deletion: confirm `memory/STATUS.md` is writable
6. After all fixes: start a new Claude Code session from the new location and verify:
   - No "never write code" instruction from parent directory
   - No conflicting session-start instructions from claude-docs/
   - `memory/STATUS.md` and `memory/MEMORY.md` auto-load correctly
   - Project memory files (37 feedback files) are accessible

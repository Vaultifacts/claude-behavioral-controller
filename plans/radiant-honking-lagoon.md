# Plan: Resolve Global ↔ VaultLister-3 Conflict Fixes

## Context
Exhaustive conflict audit between `~/.claude/settings.json` (global) and `vaultlister-3/.claude/settings.json` + `CLAUDE.md` (project) identified 4 fixes, plus 1 additional fix discovered during analysis. One original fix is already resolved; 4 remain (Fixes 2-5).

## Assessment

### Fix 1: `Edit(settings.json)` / `Write(settings.json)` deny scope — ALREADY DONE
Global deny (lines 121-122) already uses absolute path `C:\Users\Matt1\.claude\settings.json`, not bare `settings.json`. Project-level settings.json at `vaultlister-3/.claude/settings.json` is a different absolute path and is NOT blocked. **No action needed.**

### Fix 2: Add Notion trailer reminder + fix commit types list — DO
- **Risk**: None (doc-only)
- **Value**: High — prevents `[AUTO]` commit rejections. After Fix 5, the commit-msg hook requires `Notion-Done:`/`Notion-Skip:` + `Verified:` trailers for `feat|fix|chore|refactor|perf|test|build|revert` types (8 of 11). Pre-push provides second-layer enforcement. Without this doc, Claude has no way to know about these requirements until a commit fails.
- **File**: `C:\Users\Matt1\OneDrive\Desktop\vaultlister-3\CLAUDE.md`
- **Location**: Line 199 — replace AND insert after
- **Two changes in one edit** (same old_string anchor):
  1. Fix incomplete commit types: `(feat, fix, chore, docs, test, refactor)` → `(feat, fix, chore, docs, style, refactor, perf, test, ci, build, revert)` — matches the 11 types accepted by commit-msg hook line 21
  2. Insert new trailer requirement line after
- **Exact edit** — replace line 199 with corrected line + new trailer line:
  ```
  OLD:
  - Git commits: `[AUTO]` prefix + conventional commit style (`feat`, `fix`, `chore`, `docs`, `test`, `refactor`)

  NEW:
  - Git commits: `[AUTO]` prefix + conventional commit style (`feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `ci`, `build`, `revert`)
  - ALL `[AUTO]` commits MUST include `Notion-Skip: <reason>` (or `Notion-Done: <page-id>`) and `Verified: <how tested>` trailers. Commit-msg and pre-push enforce for all types except docs/style/ci.
  ```

### Fix 3: Deny npm commands in vaultlister-3 settings.json — DO
- **Risk**: None (additive deny, cannot break existing workflows. `npx` is a separate binary, unaffected.)
- **Value**: Medium — prevents accidental npm usage in a Bun-only project. Currently nothing in settings.json stops npm despite CLAUDE.md line 217 stating "This project uses **Bun** (not npm)".
- **File**: `C:\Users\Matt1\OneDrive\Desktop\vaultlister-3\.claude\settings.json`
- **Location**: After line 33 (`"Bash(git restore --staged .*)"`) in the deny array, before the closing `]` on line 34
- **Why catch-all patterns**: Specific patterns like `npm install*` + `npm run*` miss `npm i` (shorthand), `npm ci`, `npm test`, `npm start`, `npm exec`, `npm init`. In a Bun-only project there is zero reason to use any alternative package manager. Block npm, yarn, and pnpm.
- **Edge case**: `NODE_ENV=test npm run ...` wouldn't be caught since the command starts with `NODE_ENV=`. Acceptable risk — Claude would use `bun` for this pattern.
- **Exact edit** (including adding comma to existing last entry):
  ```json
  "Bash(git restore --staged .*)",    ← add trailing comma (was missing)
  "Bash(npm *)",
  "Bash(yarn *)",
  "Bash(pnpm *)"
  ```
- **Note**: Global settings.json deny protects `C:\Users\Matt1\.claude\settings.json` (global) only. This project's settings.json is a different absolute path and is freely editable. `npx` is a separate binary and is unaffected.

### Fix 4: Document pre-push server requirement — DO
- **Risk**: None (doc-only)
- **Value**: Medium — pre-push hook (`.husky/pre-push` lines 74, 124-127) checks `curl localhost:PORT/api/health` and blocks push with "Server not running" error if it fails. Without this doc, Claude has no way to know it must start the server before pushing.
- **File**: `C:\Users\Matt1\OneDrive\Desktop\vaultlister-3\CLAUDE.md`
- **Location**: After line 178 (`4. The pre-commit hook enforces these on Linux/CI...`), before the blank line at 179
- **Exact edit**: Insert one new numbered item:
  ```
  5. Pre-push hook requires server running on PORT — start with `bun run dev:bg` before pushing.
  ```

### Fix 5: Add chore to commit-msg required types — DO
- **Risk**: Low — behavioral change is transparent since Fix 2's doc already tells Claude to add trailers to ALL commits
- **Value**: High — makes commit-msg and pre-push consistent. Catches missing chore trailers at commit time (15s fix) instead of push time (30s fix). Preserves Notion tracking for chore commits.
- **File**: `C:\Users\Matt1\OneDrive\Desktop\vaultlister-3\.husky\commit-msg`
- **Location**: Lines 16-19 (comment + variables)
- **Exact edit**:
  ```
  OLD:
  # All commit types that produce functional changes require trailers.
  # chore/docs/style/ci are exempt — maintenance and non-functional changes.
  TRAILER_REQUIRED_TYPES="feat|fix|refactor|perf|test|build|revert"
  TRAILER_EXEMPT_TYPES="docs|style|ci|chore"

  NEW:
  # All commit types that produce functional changes require trailers.
  # docs/style/ci are exempt — maintenance and non-functional changes.
  TRAILER_REQUIRED_TYPES="feat|fix|chore|refactor|perf|test|build|revert"
  TRAILER_EXEMPT_TYPES="docs|style|ci"
  ```
- **Note**: Line 16 unchanged (still accurate — chore produces functional changes). Line 17 updated to remove "chore/" — prevents stale comment contradicting the code directly below it.
- **Tradeoff**: Since Fix 2 already tells Claude to add trailers to ALL commits, this creates zero additional ceremony. The only change is WHERE a rare forgotten-trailer failure is caught (commit vs push).

## Pre-existing Issues Addressed / Observed

**Addressed by this plan:**
- CLAUDE.md line 199 listed only 6 commit types; updated to all 11 (Fix 2)
- Pre-push/commit-msg chore discrepancy; now both hooks require trailers for chore (Fix 5)

**Intentionally not addressed (justified):**
- Project deny has `Bash(npm publish*)` which becomes redundant with `Bash(npm *)`. Left for defense in depth — no harm in redundancy.
- `docs`/`style`/`ci` commits need no trailers per either hook, but Fix 2 says "ALL" — simpler rule, zero impact (extra trailers are harmless).
- Global deny is missing several project-level safety patterns (`--no-verify`, `curl|bash`, `git reset --hard`, `git clean -f`). Low risk since `~` is not a git repo. Candidate for separate future task (requires write-protected settings.json workaround).

## Weakness Assessment

**Fix 2** (doc + types): Documentation is inherently weaker than code enforcement. Claude could miss the rule. But commit-msg now enforces for 8 types including chore (Fix 5), and pre-push provides second layer. Fix 2's "ALL commits" doc rule means Claude adds trailers proactively. Worst case: commit fails (not push), 15s self-correction.

**Fix 3** (deny rules): Pattern matching can be bypassed via env prefixes (`NODE_ENV=test npm ...`), shell builtins (`command npm ...`), or subshells (`bash -c "npm ..."`). All require active effort Claude wouldn't naturally take. Structural limitation of command-level deny. No stronger alternative without kernel-level interception.

**Fix 4** (doc): No auto-start means Claude must remember to start server. Pre-push hook provides fail-safe (clear error + command). Stronger alternative: add auto-start to pre-push hook — but changes hook behavior and might conflict with user's workflow expectations.

**Systemic**: All four fixes use the project's defense-in-depth pattern (deny rules + hooks + documentation). Each layer compensates for the others' weaknesses. No single layer is sufficient alone, but together they provide robust enforcement.

## Edit Tool Validation
- protect-files.sh does NOT block any of our 3 target files — protected paths are only `~/.claude/hooks/` and `~/.claude/settings.json` (confirmed by reading hook source). `.husky/commit-msg` is NOT under `~/.claude/`.
- All old_string targets are unique within their respective files (verified by reading file content)
- No global deny rule blocks Edit/Write to project-level paths or `.husky/` files
- CLAUDE.md line 187 allows modification of husky hooks ("modification for improvement is OK")

## Execution Order
1. **Fix 5** — Edit `vaultlister-3/.husky/commit-msg` lines 16-19 (update comment + add chore to required, remove from exempt)
2. **Fix 4** — Edit `vaultlister-3/CLAUDE.md` line 178 area (lower line number first to avoid line-shift issues)
3. **Fix 2** — Edit `vaultlister-3/CLAUDE.md` line 199 area (now line 200 after Fix 4's insertion)
4. **Fix 3** — Edit `vaultlister-3/.claude/settings.json` (add comma + new deny entries)
5. **Verify** — Read all 3 files back, validate JSON, `git diff`
6. **Commit** — `[AUTO] chore: harden commit requirements, deny alt pkg managers, align chore trailers`
   - Trailers: `Notion-Skip: config/doc/hook hardening, no Sprint Board item` + `Verified: git diff reviewed, settings.json valid JSON, commit-msg types match pre-push`
   - `--no-gpg-sign` (no GPG key available on this machine)
   - Files: `git add CLAUDE.md .claude/settings.json .husky/commit-msg`

## Verification
1. Read `vaultlister-3/.husky/commit-msg` lines 16-19 — confirm comment updated (no "chore"), chore in REQUIRED, removed from EXEMPT
2. Read `vaultlister-3/CLAUDE.md` after edits — confirm Fix 2 lines (types + trailers) and Fix 4 line (server requirement) at correct positions
3. Read `vaultlister-3/.claude/settings.json` after edit — confirm valid JSON, trailing comma, `Bash(npm *)`, `Bash(yarn *)`, `Bash(pnpm *)` all present
4. Verify JSON validity: `cd /c/Users/Matt1/OneDrive/Desktop/vaultlister-3 && python -m json.tool .claude/settings.json > /dev/null`
5. Run `git diff` in vaultlister-3 to review all 4 changes across 3 files
6. Commit with trailers — the commit itself validates Fix 5 (commit-msg hook will enforce trailers on this chore commit)

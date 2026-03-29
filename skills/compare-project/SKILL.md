# Skill: /compare-project
# Compares this project against the Universal Project Setup starter-kit
# and produces a prioritized list of beneficial additions.
#
# HOW TO USE:
#   1. Copy this file into your project at: .claude/skills/compare-project/SKILL.md
#   2. Open Claude Code in your project directory
#   3. Run: /compare-project
#
# ADAPT: Update UNIVERSAL_SETUP_PATH below to wherever you stored your starter-kit

---

You are performing a **Project Enhancement Assessment**. Your job is to compare this project against the Universal Project Setup starter-kit and produce a prioritized, actionable list of things worth adding.

## Step 1 — Locate the Universal Project Setup

The starter-kit lives at:
```
C:\Users\Matt1\OneDrive\Desktop\Universal Project Setup\
```

**Before proceeding**, verify this path exists:
```bash
ls "/c/Users/Matt1/OneDrive/Desktop/Universal Project Setup/" 2>/dev/null || echo "NOT FOUND"
```
If it prints `NOT FOUND`, stop and tell the user: "Universal Project Setup not found at the expected path. Please confirm its location before continuing."

Read the master `README.md` there to understand the full structure, then read each subfolder's `README.md` to understand what each section contains.

## Step 2 — Scan This Project

Scan the current project directory thoroughly:
- Read `package.json` (or equivalent) to understand the stack and existing scripts
- List all top-level directories and key config files
- Check for: `.claude/`, `.github/`, `.husky/`, `Dockerfile`, `docker-compose.yml`, `nginx.conf`, `scripts/`, CI/CD workflows, PWA files (`sw.js`, `manifest.json`), middleware directory, test infrastructure
- Read `CLAUDE.md` if it exists
- Note what's already present — **do not recommend things already in the project**

## Step 3 — Compare and Assess

For each section of the Universal Project Setup, determine:

1. **Does this project have an equivalent?** (yes / partial / no)
2. **Is it applicable?** — Does this project's stack and purpose make this relevant?
3. **What's the benefit?** — Security, DX, reliability, observability, automation, governance

Sections to check:
- `claude-setup/` — .claude/ agents, hooks, skills, settings, CLAUDE.md
- `devops/` — Dockerfile, Nginx, docker-compose, CI/CD workflows
- `middleware/` — csrf, rateLimiter, errorHandler, requestLogger, securityHeaders, logger, helpers
- `github-templates/` — PR template, issue templates
- `pwa/` — service worker, offline page, manifest
- `scripts/` — kill-port, server-manager, backup/restore, security-audit
- `frontend-core/` — state manager, toast, websocket client, API client, utils
- `chrome-extension/` — only if this project has or plans a browser extension
- `react-native/` — only if this project has or plans a mobile app
- `notion-workflow/` — only if this project uses Notion for issue tracking
- `husky-hooks/` — git hooks (commit-msg, pre-commit, pre-push)
- `runbook/` — only if this is a production deployment requiring release gates
- `not-in-vaultlister/` — check the 23 recommended patterns; flag any that are clearly applicable

## Step 4 — Output a Prioritized Report

Produce a structured markdown report with this exact format:

---

# Project Enhancement Report
**Project:** [project name]
**Assessed against:** Universal Project Setup
**Date:** [today]

## Summary
[2-3 sentence overview of what's missing and the most important gaps]

## Priority 1 — Critical (add immediately)
> Security, data integrity, or broken DX gaps

| Item | What to Add | Why | Source in Starter-Kit |
|------|------------|-----|----------------------|
| ... | ... | ... | ... |

## Priority 2 — High Value (add this sprint)
> Significant improvement to reliability, automation, or maintainability

| Item | What to Add | Why | Source in Starter-Kit |
|------|------------|-----|----------------------|
| ... | ... | ... | ... |

## Priority 3 — Nice to Have (add when relevant)
> Polish, observability, or optional tooling

| Item | What to Add | Why | Source in Starter-Kit |
|------|------------|-----|----------------------|
| ... | ... | ... | ... |

## Not Applicable
> Items from the starter-kit that don't apply to this project and why

| Item | Reason Not Applicable |
|------|----------------------|
| ... | ... |

## Already Present
> Items from the starter-kit already covered by this project

| Starter-Kit Item | Project Equivalent |
|-----------------|-------------------|
| ... | ... |

## Quick Wins (under 15 minutes each)
> Subset of Priority 1+2 items that require minimal effort

1. [item] — [one-line instruction]
2. ...

---

## Step 5 — Ask Before Acting

After producing the report, ask:
> "Would you like me to implement any of these? I can work through them Priority 1 first, or you can tell me which specific items to add."

Do NOT start adding files until the user confirms.

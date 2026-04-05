# New Project Checklist
Last updated: 2026-03-16

Everything below is inherited automatically from `~/.claude/` globals.
Use this to verify a new project is set up correctly and to activate optional features.

---

## Step 1 — Local Project Setup

```bash
mkdir my-project && cd my-project
git init
claude   # open Claude Code in the project
```

---

## Step 2 — Verify Global Inheritance (auto, no action needed)

Run these in Claude Code to confirm globals are active:

| Check | Command | Expected |
|---|---|---|
| Commands available | `/review`, `/ticket` | Both respond |
| Agents available | `/agents` | code-reviewer, debugger, researcher, python-specialist |
| Secret hook active | Write a file with `api_key = "sk-abc123"` | Blocked with warning |
| File protection hook | Try to overwrite `~/.claude/CLAUDE.md` | Blocked |
| Timestamps in terminal | Run any command in PS7 or Git Bash | `[HH:MM:SS]` prefix on output |

---

## Step 3 — Create a Project-Level CLAUDE.md (recommended)

```bash
cp ~/.claude/templates/CLAUDE.project.md ./CLAUDE.md
```

Then edit `CLAUDE.md` to fill in:
- Project name and purpose
- Tech stack (language, framework, DB)
- Key file paths
- Testing commands (`npm test`, `pytest`, etc.)
- Any project-specific rules that override globals

> Project-level CLAUDE.md **overrides** global `~/.claude/CLAUDE.md`.

---

## Step 4 — Activate MCP Servers (as needed per project)

Set env vars before starting Claude Code. Only set what the project needs:

```bash
# GitHub (PR creation, issue management)
export GITHUB_TOKEN="ghp_..."

# PostgreSQL (DB queries, schema inspection)
export POSTGRES_CONNECTION_STRING="postgresql://user:pass@localhost:5432/dbname"

# AWS (knowledge base retrieval)
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-east-1"

# Qdrant (vector search)
export QDRANT_URL="http://localhost:6333"
export QDRANT_API_KEY="..."

# Chroma (vector DB)
export CHROMA_HOST="localhost"
export CHROMA_PORT="8000"
```

No env vars needed for: `context7`, `playwright`, `docker`, `kubernetes`

---

## Step 5 — Node.js Projects

```bash
npm init -y
echo "node_modules/\n.env\ndist/" >> .gitignore
cp ~/.env.example .env   # if applicable
```

- Use `npm` (not yarn/bun) unless project specifies otherwise
- Check `package.json` scripts before running any command
- Use `npx prettier --write .` and `npx eslint .` for one-offs (or globals directly)

---

## Step 6 — Python Projects

```bash
python -m venv venv
source venv/Scripts/activate   # Git Bash on Windows
echo "venv/\n.env\n__pycache__/" >> .gitignore
pip install -r requirements.txt   # if exists
```

- Always `PYTHONIOENCODING=utf-8` before Python commands
- Use `black .` to format, `ruff check --fix .` to lint, `mypy .` to type-check

---

## Step 7 — Git Setup

```bash
git add .gitignore CLAUDE.md
git commit -m "chore: initial project setup"
```

Commit conventions:
- `feat:` new feature
- `fix:` bug fix
- `chore:` maintenance
- `docs:` documentation
- `[AUTO]` prefix when Claude commits

---

## What Claude Inherits Automatically

| Global | Source | Notes |
|---|---|---|
| Full autonomous mode | `CLAUDE.md` | Proceeds without asking unless destructive |
| Conventional commits | `CLAUDE.md` | `[AUTO]` prefix on Claude commits |
| No `.env` commits | `CLAUDE.md` + `protect-files.sh` | Hard blocked |
| Minimal code changes | `CLAUDE.md` | No unsolicited refactors |
| `/review` command | `commands/review.md` | CRITICAL/WARNING/INFO triage |
| `/ticket` command | `commands/ticket.md` | Structured ticket from description |
| Code review skill | `skills/code-review/SKILL.md` | Auto-triggered after edits |
| Secret scanning | `hooks/block-secrets.py` | Blocks writes with credentials |
| File protection | `hooks/protect-files.sh` | Guards sensitive global files |
| Bash validation | `hooks/validate-bash.sh` | Validates commands before run |
| 9 MCP servers | `settings.json` | Activate per-project via env vars |
| 4 agents | `agents/` | code-reviewer, debugger, researcher, python-specialist |
| Timestamped output | PS7 + Git Bash profiles | Every terminal line has `[HH:MM:SS]` |

---

## Quick Smoke Test (run in Claude Code after setup)

```
/review .
/ticket Fix the login page not redirecting after auth
```

Both should produce structured output. If they don't, run:
```bash
ls ~/.claude/commands/   # should show review.md, ticket.md
```

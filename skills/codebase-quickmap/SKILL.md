---
name: codebase-quickmap
description: Use when joining a new codebase, starting work on an unfamiliar project, or needing a fast structural orientation before making changes. Invoke whenever the user says "I'm new to this", "give me an overview", "what does this codebase do", "orient me", "I just joined", "explain the architecture", "where do I start", or asks how a project is structured before doing any work. Also invoke at the start of any session where Claude hasn't worked in this codebase before. The goal is a 5-minute map, not a deep dive — use feature-dev:code-explorer for deep research.
---

# Codebase Quickmap

## Overview

The goal is a fast, accurate mental model — not exhaustive documentation. You're building the map a senior engineer would sketch on a whiteboard on your first day.

**Core principle:** Five focused questions answered well beats twenty questions answered shallowly. Stop when you can answer: what does this do, how does it start, what are the main pieces, and where would I add X?

## The Five Questions

Work through these in order. Each one takes 1-3 minutes max.

### 1. What does this project do? (README + package/manifest)

- Read `README.md` (or `README.rst`, `README.txt`) — the stated purpose and key features
- Read `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, or equivalent — the name, description, and main dependencies reveal the tech stack and problem domain instantly
- Check for a `CLAUDE.md` or `.claude/` directory — project-specific conventions for Claude

**Output:** One sentence: "This is a [type] that [does X] for [users/purpose]."

### 2. Where does execution start? (Entry points)

Find where the program actually begins. Look for:
- `main.py`, `index.js/ts`, `main.go`, `src/main.rs`, `app.py`, `server.js`
- Script entries in `package.json` (`start`, `dev`, `build`)
- Framework conventions: Next.js → `app/` or `pages/`; Django → `urls.py`; Rails → `routes.rb`; Express → `app.js`/`server.js`

Don't read these files deeply — just locate them and note what they wire together.

**Output:** "Execution starts at X, which sets up Y and Z."

### 3. What are the core data models? (Schema + types)

The data model is the skeleton of any application. Find:
- Database schemas: `schema.prisma`, `models.py`, `*.sql`, migration files
- Type definitions: `types.ts`, `interfaces/`, `models/`, `entities/`
- API contracts: `openapi.yaml`, `schema.graphql`, GraphQL type definitions

Read just the names and relationships, not the implementations. What are the 3-7 key nouns in this system?

**Output:** "The core entities are X, Y, Z. X belongs to Y. Z references X."

### 4. How is the codebase organized? (Directory structure)

Run a top-level directory listing. For each top-level directory, identify its role:
- `src/` vs `app/` vs `lib/` — where the main code lives
- `components/` vs `views/` vs `pages/` — UI layer
- `api/` vs `routes/` vs `controllers/` — request handling
- `services/` vs `domain/` — business logic
- `tests/` vs `__tests__/` vs `spec/` — test location and framework
- `scripts/` vs `tools/` — dev tooling

Note the naming conventions (camelCase vs kebab-case vs snake_case) — they tell you the language idioms in use.

**Output:** A 5-10 line directory map with one-line descriptions.

### 5. What's the test and auth pattern? (Quick grep)

**Tests:** Find one test file and read 20 lines. What framework? What style (unit/integration/e2e)? Are there mocks, fixtures, factories?

**Auth:** Grep for `auth`, `jwt`, `session`, `middleware`, `passport`, `clerk`, `supabase`. Auth touches everything — knowing the pattern prevents security mistakes.

**Output:** "Tests use X framework. Auth is handled by Y at Z layer."

## Deliver the Map

After the five questions, produce a structured summary:

```
## Codebase Map: [Project Name]

**What:** [One sentence purpose]
**Stack:** [Language, framework, database, key deps]
**Entry:** [How it starts]
**Structure:** [Directory map, 5-8 lines]
**Data models:** [Core entities and relationships]
**Tests:** [Framework and style]
**Auth:** [How identity is handled]
**Conventions:** [Anything notable from CLAUDE.md or README]

**Where to add X:** [Explain which directories/files a new feature would touch]
```

The last line is the most practical deliverable — it answers the question every new engineer actually has.

## Depth Calibration

This skill is intentionally shallow. Stop at these limits:

| Signal | Action |
|--------|--------|
| File is > 200 lines | Read only the top (imports, exports, class names) |
| Directory has > 20 files | List and categorize, don't read |
| Dependency is unfamiliar | Note it, don't research it now |
| Something is surprising | Flag it, move on |

If the user needs more depth on a specific area after the quickmap, use `feature-dev:code-explorer` for that area only.

## Related Skills

- **feature-dev:code-explorer** — Deep research on a specific feature or system
- **superpowers:refactor-code** — Before touching existing code
- **superpowers:writing-plans** — After orientation, when planning a multi-step change

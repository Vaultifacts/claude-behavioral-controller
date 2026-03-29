# Plan: Fix Code Colony + Dummy-Proof Notion Project Flow

## Context
Code Colony was set up by a Claude session that didn't know about `/new-project`. It improvised — embedding the template content inside the Projects DB row instead of creating a standalone dashboard page. All metadata fields are empty, global linked views are placeholder callouts, and the page is invisible in the sidebar. "Pixel Agents" has the same issue but no local project exists — it will be archived.

The deeper problem: there's nothing preventing this from happening again. We need safeguards that fire regardless of how the user phrases "set up a project."

---

## Part A: Fix Code Colony Notion Setup

### A1. Audit old per-project DBs for data
Query each of the 13 child databases inside `3249f0c8-1de6-81dc-aecd-cf9da1a28f1e` to find which ones have rows that need migrating.

### A2. Duplicate template via browser
Browser-duplicate `3239f0c8-1de6-818c-928d-e49911e71e51` (the template with 5 real linked views). Capture new page ID from URL.

### A3. Rename to "Code Colony" via API

### A4. Discover new per-project DB IDs
GET children of new page, map `child_database` titles to IDs.

### A5. Migrate data from old DBs → new DBs
For each old DB with rows: read all entries, write to corresponding new DB. Preserve title + filled properties. Skip broken relations.

### A6. Update Projects DB entry
The existing entry `3249f0c8-1de6-81dc-aecd-cf9da1a28f1e` is the broken one (it IS the old page). Archive it and create a fresh row:
- Status: Active
- Start Date: 2026-03-15
- Dashboard URL: new page URL
- Tech Stack: [Tauri, React, TypeScript, Rust, Node.js, pnpm]

### A7. Archive Pixel Agents
No local project exists. Archive `3249f0c8-1de6-8195-bf24-c4cd5e83926b`.

### A8. Create Code Colony CLAUDE.md
Write `C:/Users/Matt1/OneDrive/Desktop/Code Colony/CLAUDE.md` with:
- Notion Dashboard URL
- Tech stack (Tauri + React + TS + Rust + pnpm monorepo)
- Commands from package.json
- pnpm override note (not npm)

---

## Part B: Dummy-Proof the Flow (Prevention)

### B1. Add `## Notion Project Setup` to `~/.claude/CLAUDE.md`
**File:** `C:/Users/Matt1/.claude/CLAUDE.md`

Add rules that Claude reads every session:
- EVERY new project gets Notion automatically (opt-out only)
- The ONLY correct method is `/new-project <name>`
- NEVER manually duplicate template or create DBs by hand
- If user asks to "set up Notion" without /new-project, run /new-project instead

### B2. Add project-detector to `task-classifier.py`
**File:** `C:/Users/Matt1/.claude/hooks/task-classifier.py`

Add regex patterns after the existing scoring block:
- `new project`, `set up.*notion`, `create.*project.*workspace`, `duplicate.*template`, `set up.*dashboard`, `notion.*for.*project`

When matched (and message doesn't contain `/new-project`), inject:
```
[project-detector] New project intent detected. You MUST run /new-project <name>. NEVER manually duplicate template or create databases.
```

### B3. Update `new-project-checklist.md`
**File:** `C:/Users/Matt1/.claude/memory/new-project-checklist.md`

Add a failsafe note to Step 0: "If Claude tries to set up Notion manually, STOP and run /new-project."

---

## Verification
- [ ] New Code Colony page visible in Notion sidebar under Project Workspace
- [ ] 5 global linked views render real data (not placeholder callouts)
- [ ] 13 per-project DBs present with migrated data
- [ ] Projects DB row fully filled (Status, Start Date, Dashboard URL, Tech Stack)
- [ ] Old broken page archived
- [ ] Pixel Agents archived
- [ ] Local CLAUDE.md created with Notion URL
- [ ] `task-classifier.py` injects warning on "set up notion for my project"
- [ ] `~/.claude/CLAUDE.md` has Notion Project Setup rules

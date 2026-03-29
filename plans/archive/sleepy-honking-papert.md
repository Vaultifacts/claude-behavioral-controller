# Notion Project Template — Refinement Plan

## Context
Your "My First Project" page is a project management template with 4 global resource links and 13 inline databases. The goal was set up in "Todays Claude Goal" — and it's marked DONE. Now we need to audit and polish it so it's genuinely useful as a reusable template.

I analyzed the page via browser (accessibility tree + page text) and cross-referenced with the Notion API. Here's what I found, organized by severity.

---

## Critical Issues

### 1. Notion Integration Can't Access These Pages
The Notion API returns **404** for "My First Project", "Project Template – Duplicate Me", and "Project Workspace". This means:
- The `notion-capture.py` stop hook **cannot write** to project-specific databases
- No API-based automation works against these pages
- The `/new-project` skill can't programmatically set up projects

**Fix**: Share "Project Workspace" (and all child pages/databases) with the Notion integration. In Notion: click `•••` on the page → Connections → add your integration.

### 2. Global Resources Are Links, Not Linked Views
All 4 callouts say "Open in Notion and create a Linked View" — they're placeholder links, not actual inline linked views. You can't see data at a glance.

**Fix**: For each (Prompt Library, Lessons Learned, Glossary & Acronyms, External References):
1. Delete the callout
2. Type `/linked view of database`
3. Select the global master database
4. Optionally add filters (e.g., filter by project)

### 3. Inline Databases Are All Named "New database"
The accessibility tree shows every inline database title as "New database". The visible names (Roadmap & Milestones, etc.) are heading blocks above them — the databases themselves are unnamed. This means:
- Notion search can't find them
- API queries return generic names
- Duplicating the template creates 13 databases all called "New database"

**Fix**: Click each inline database title and rename it to match its heading (e.g., "Roadmap & Milestones", "Feature Backlog", etc.).

---

## Structural Improvements

### 4. Page Is Too Long — Use Toggle Headings
13 databases stacked vertically makes the page nearly unscrollable.

**Fix**: Wrap each database section in a **toggle heading** (type `/toggle heading 2`). This lets you collapse sections you're not actively using. Group them logically:
- **Planning**: Roadmap, Feature Backlog, ADRs
- **Execution**: Sprint/Task Board, Environment & Config
- **Quality**: Bug Tracker, Test Failures, Performance Benchmarks, Security Checklist, Build Checklist
- **Operations**: Meeting Notes, Release Notes, Risk Register
- **Claude**: Session Log

### 5. No Relations Between Databases
None of the 13 databases are linked. Key missing relations:
- **Sprint tasks → Roadmap milestones** (which milestone does this task serve?)
- **Bug Tracker → Sprint tasks** (which task introduced the bug?)
- **ADRs → Features** (which feature drove this decision?)
- **Release Notes → Milestones** (which milestone does this release cover?)

**Fix**: Add Relation properties to connect the most important databases. Start with Sprint ↔ Roadmap and Bug Tracker ↔ Sprint.

### 6. No Rollups or Progress Tracking
No computed fields anywhere. You can't see "how many sprint tasks are done for Milestone X" at a glance.

**Fix**: After adding relations, add Rollup properties to show:
- Roadmap: % of linked Sprint tasks completed
- Sprint: count of linked bugs

### 7. Add a Project Metadata Header
No place to record project name, description, start date, team, repo URL, etc.

**Fix**: Add a structured callout or table at the top with key project metadata fields.

---

## Property Fixes

### 8. "PowerShell Command Used" → "Command Used"
Claude Session Log has "PowerShell Command Used" — too specific since Git Bash is also used.

**Fix**: Rename the property to "Command Used".

### 9. Bug Tracker Missing "Priority"
It has Severity but no Priority. These are different (severity = impact, priority = urgency to fix).

**Fix**: Add a Select property "Priority" with P0/P1/P2/P3 options.

### 10. Missing Board Views
Only Sprint/Task Board and Risk Register have Board views. These databases would also benefit:
- Feature Backlog (board by Status)
- ADRs (board by Status)
- Bug Tracker (board by Status or Severity)

**Fix**: Add Board view to each.

---

## Minor Fixes

### 11. Typo: "Todays Claude Goal" → "Today's Claude Goal"

### 12. Empty Databases — Add Templates
All 13 databases are empty. When duplicating the template, there's no example data or database templates to guide new entries.

**Fix**: Create 1 database template per database with pre-filled placeholder text showing what a good entry looks like.

### 13. Sidebar Duplication
Sprint/Task Board and Risk Register appear both in the sidebar (as standalone databases) AND inline on the project page. Clarify: are the sidebar ones the same databases, or separate global copies?

---

## Execution Order

| Step | Action | Method |
|------|--------|--------|
| 1 | Share pages with Notion integration | Manual (browser) |
| 2 | Rename all 13 inline databases | Browser (Claude can assist) |
| 3 | Fix typo in callout | Browser (Claude can do) |
| 4 | Rename "PowerShell Command Used" | Browser or API |
| 5 | Convert 4 global links to Linked Views | Browser (manual — requires UI interaction) |
| 6 | Wrap sections in toggle headings | Browser (Claude can assist) |
| 7 | Add Board views to Backlog, ADRs, Bugs | Browser or API |
| 8 | Add relations (Sprint ↔ Roadmap, Bugs ↔ Sprint) | API or browser |
| 9 | Add rollups for progress tracking | API or browser |
| 10 | Add project metadata header | Browser (Claude can do) |
| 11 | Add Priority to Bug Tracker | Browser or API |
| 12 | Create database templates | Browser |
| 13 | Clarify sidebar duplicates | Discussion with you |

**Steps I can do right now via browser**: 2, 3, 4, 6, 7, 10, 11
**Steps requiring your manual action**: 1 (integration sharing), 5 (linked views UI), 12 (templates)
**Steps requiring API access first**: 8, 9 (need step 1 done first)

---

## Verification
After changes:
- Each database should be findable via Notion search by its proper name
- Toggle headings should collapse/expand cleanly
- The Notion API (`notion-fetch`) should return 200 for the project page
- Relations should show linked entries across databases
- Board views should render correctly with Status columns

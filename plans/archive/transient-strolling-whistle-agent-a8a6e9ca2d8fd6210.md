# Task: Skill Files Inventory

## COMPLETE ✓

**73 total skills** across 13 plugins scanned and analyzed.

### Skills by Plugin

**SUPERPOWERS (15)** — Development workflows
- using-superpowers, writing-plans, brainstorming, test-driven-development
- systematic-debugging, refactor-code, subagent-driven-development
- dispatching-parallel-agents, executing-plans, requesting-code-review
- receiving-code-review, verification-before-completion
- finishing-a-development-branch, using-git-worktrees, writing-skills

**SENTRY (28)** — Error monitoring hub
- 16 SDK skills (Android, Browser, Cloudflare, Cocoa, .NET, Elixir, Flutter, Go, NestJS, Next.js, Node, PHP, Python, React Native, React, Ruby, Svelte)
- 6 integration skills (sentry-sdk-setup, feature-setup, otel-exporter, upgrade, ai-monitoring, skill-creator)
- 4 workflow skills (fix-issues, workflow, code-review, pr-code-review)
- 1 admin (create-alert)

**PLUGIN-DEV (7)** — Plugin architecture
- plugin-structure, skill-development, agent-development, command-development
- hook-development, mcp-integration, plugin-settings

**ATLASSIAN (5)** — Jira/Confluence
- search-company-knowledge, spec-to-backlog, capture-tasks-from-meeting-notes
- generate-status-report, triage-issue

**NOTION (4)** — Knowledge management
- knowledge-capture, meeting-intelligence, research-documentation, spec-to-implementation

**CHROME-DEVTOOLS-MCP (4)** — Browser debugging
- chrome-devtools, a11y-debugging, debug-optimize-lcp, troubleshooting

**FIGMA (3)** — Design-to-code
- implement-design, code-connect-components, create-design-system-rules

**CODERABBIT (2)** — Code review
- code-review, autofix

**SINGLE SKILLS (5)**
- skill-creator (Sentry ecosystem)
- hookify (Rule writing)
- frontend-design (UI/components)
- claude-md-management (CLAUDE.md audit)
- claude-code-setup (Automation recommendations)

### Redundancy Findings

**HIGH OVERLAP** (needs trigger ordering):
1. Code Review (4 skills): superpowers/requesting + receiving + coderabbit + sentry
2. Debugging (4 skills): superpowers + chrome-devtools + sentry/fix-issues + sentry/workflow

**MEDIUM OVERLAP** (by design):
- Task Management: atlassian (Jira) vs notion (generic)
- Planning: superpowers + notion/spec-to-implementation + atlassian/spec-to-backlog

**INTENTIONAL DESIGN** (not overlap):
- Sentry SDK dispatcher routes to language-specific skills
- Superpowers uses mandatory invocation (using-superpowers first)
- Plugin-dev follows architectural hierarchy (structure → components)

### Quality Notes
✅ **Clear:** superpowers (explicit keywords), chrome-devtools (keyword lists), sentry SDKs (frameworks)
⚠️ **Verbose:** atlassian (4-5 part numbered lists in descriptions)
❌ **Vague:** notion/meeting-intelligence, skill-creator (self-referential)

### Missing Opportunities
- Test execution (TDD plans but not runner)
- Git workflows (only worktrees, no rebase/merge orchestration)
- Performance profiling (LCP only, no CPU/memory/bundle)
- Auto-documentation (Notion captures but no code→doc)
- Dependency management (no version bump automation)

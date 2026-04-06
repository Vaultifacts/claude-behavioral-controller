---
name: dep-audit
description: Use when asked to check dependencies, audit packages, find outdated packages, check for CVEs, update dependencies, or run a dependency health check. Covers npm/yarn/pnpm, pip/uv, cargo, and go modules.
---

Dependency audit for: $ARGUMENTS (or current project if no argument given)

## Step 1 — Detect package managers

Check which apply to this project:
```bash
ls package.json yarn.lock pnpm-lock.yaml requirements*.txt pyproject.toml Cargo.toml go.mod 2>/dev/null
```

## Step 2 — Run audits

Run all that apply. Capture full output.

**Node (npm/yarn/pnpm):**
```bash
npm audit --json 2>/dev/null || yarn audit --json 2>/dev/null
npm outdated 2>/dev/null
```

**Python:**
```bash
pip-audit 2>/dev/null || safety check 2>/dev/null
pip list --outdated 2>/dev/null
```

**Rust:**
```bash
cargo audit 2>/dev/null
cargo outdated 2>/dev/null
```

**Go:**
```bash
go list -m -u all 2>/dev/null | grep "\["
```

If a tool is not installed, note it and continue — do not fail.

## Step 3 — Categorize findings

### CVEs / Known Vulnerabilities
From `npm audit` / `pip-audit` / `cargo audit` output, list each:
```
[CRITICAL|HIGH|MEDIUM|LOW] package@version — CVE-XXXX-XXXX
Affected: description of vulnerability
Fix: upgrade to X.X.X (or patch available / no fix yet)
```

### Outdated Packages
From `npm outdated` / `pip list --outdated` / `cargo outdated`:

| Package | Current | Wanted | Latest | Type |
|---------|---------|--------|--------|------|
| lodash | 4.17.11 | 4.17.21 | 4.17.21 | patch |
| react | 17.0.2 | 17.0.2 | 18.3.1 | major |

**Type** = patch / minor / major (major = potential breaking changes)

### Version Drift (if monorepo or multiple lockfiles)
Flag packages declared at different versions in different packages.

## Step 4 — Prioritized update plan

```
## Update Plan

### Immediate (CVEs — do now)
- [ ] upgrade X from Y to Z  →  fixes CVE-XXXX-XXXX (CRITICAL)

### High value (major version lag > 1 year old)
- [ ] upgrade A from B to C  →  security patches + perf improvements

### Routine (patch/minor, lower risk — upgrade one at a time)
- [ ] upgrade D  →  one at a time; patch/minor versions can still have breaking changes
- [ ] upgrade E
- [ ] upgrade F

### Hold (major — review changelog first)
- [ ] react 17 → 18  →  breaking changes in rendering model; see CHANGELOG
```

## Step 5 — Ask before updating

Present the plan. Then ask:
> "Which updates would you like me to apply? I'll start with Immediate, or you can specify."

Do NOT run `npm install`, `pip install --upgrade`, or equivalent without confirmation.

For each confirmed update, use the `upgrade-dependency` skill — one package at a time. Do NOT batch-install multiple packages in a single command. The `upgrade-dependency` skill handles changelog reading, API boundary checks, and isolated commits.

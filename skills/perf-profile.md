---
name: perf-profile
description: Profile and diagnose performance issues — bundle size, runtime CPU/memory hotspots, slow queries, and render performance. Use when asked to "profile performance", "why is this slow", "reduce bundle size", "optimize memory usage", "find the bottleneck", or "performance audit". For LCP/Core Web Vitals specifically, use chrome-devtools-mcp:debug-optimize-lcp instead.
---

Performance profile of: $ARGUMENTS (or current project if no argument given)

## Step 1 — Identify the performance domain

Determine which layer(s) to profile based on the symptom or target:

| Symptom | Domain |
|---------|--------|
| Slow page load, large download | Bundle size |
| Slow UI, janky animations | Frontend runtime / render |
| High memory over time | Memory leak |
| Slow API responses | Backend CPU / DB queries |
| High CPU on server | Backend runtime |

If unclear, ask: "What are you measuring — page load, runtime behavior, memory, or API latency?"

## Step 2 — Bundle size (frontend)

**Check if applicable:** `package.json` exists with a build script.

```bash
# Build with stats
npm run build -- --stats 2>/dev/null || npx vite build --reporter=verbose 2>/dev/null

# Quick size check
find dist/ build/ .next/ -name "*.js" -not -name "*.map" 2>/dev/null | xargs wc -c | sort -n | tail -20
```

**What to look for:**
- Total JS bundle > 500KB (uncompressed) is a concern
- Single chunk > 250KB suggests missing code splitting
- Duplicate packages (same library at multiple versions)
- Large libraries that could be tree-shaken or lazy-loaded

**Common fixes:**
- Dynamic `import()` for routes and modals
- Replace heavy libraries (moment.js → date-fns, lodash → native)
- Check `sideEffects: false` in package.json for tree shaking

## Step 3 — Runtime CPU / memory (Node.js / Python / Rust)

Read the hot path code directly. Look for:

**CPU hotspots:**
- Nested loops with O(n²) or worse complexity on large datasets
- Repeated expensive operations inside loops (regex compile, JSON parse, DB call)
- Synchronous blocking operations on the main thread
- Unnecessary re-computation of values that could be cached

**Memory leaks:**
- Event listeners added but never removed
- Caches / maps that grow unbounded (no eviction policy)
- Closures holding large objects longer than needed
- Circular references preventing GC (in languages without cycle detection)
- Database connections / file handles not closed

**For Node.js profiling commands:**
```bash
node --prof app.js  # CPU profile
node --inspect app.js  # DevTools attach
```

## Step 4 — Database query performance

If the project has DB access, look for:

```bash
# Find query patterns
grep -r "SELECT\|findAll\|\.find(\|\.query(" --include="*.ts" --include="*.js" --include="*.py" -l 2>/dev/null
```

**What to check in those files:**
- N+1 patterns: query inside a loop → use batch query or JOIN
- Missing `.limit()` on list queries (unbounded result sets)
- `SELECT *` when only specific columns are needed
- Missing indexes on columns used in WHERE/ORDER BY (check migration files)
- ORM eager loading vs lazy loading mismatches

## Step 5 — Report

```
## Performance Profile: [target]

### Domain: [Bundle / Runtime / Memory / DB]

### Findings

**[HIGH|MEDIUM|LOW] Finding title**
Location: file:line
Issue: description
Impact: estimated effect (e.g., "adds ~200KB to bundle", "O(n²) on user list")
Fix: specific change

### Quick wins (under 30 min each)
1. [item] — [one-line instruction]

### Larger improvements
1. [item] — [effort estimate + approach]

### Not profiled (requires runtime instrumentation)
- [anything that needs live profiling tools, APM, or prod data]
```

## Step 6 — Implement fixes

For each confirmed fix:
1. Make the minimal change
2. Re-measure where possible (re-run build, re-check bundle size)
3. Note the before/after delta

Do not optimize prematurely — only fix what the profile shows is actually slow.

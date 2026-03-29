# Plan: Integrate NagaOS Monitor into Code Colony

## Context
NagaOS has 3 AHK scripts + 3 Python hooks that write JSON state files for hook health, error dedup, and TODO extraction. The user wants to consolidate this monitoring into Code Colony's Tauri app as a new "Monitor" view — replacing the AHK UI layer while keeping the Python hooks that generate the data.

**Goal**: New `monitor` AppMode in Code Colony that reads 4 JSON files from `~/.claude/` and displays them in a unified dashboard.

## Approach
- New "Monitor" view (separate from SystemView — different data sources, different concerns)
- 4 Rust commands using `std::fs` + `serde_json::Value` — no new crate dependencies
- 5-second polling in MonitorView (matches existing poll pattern in TopBar.tsx)
- Keyboard shortcut `8` (only unused numeric key between 1-9,0)

## Race Condition Strategy

**Problem**: `error-dedup.py` does read-modify-write on `error-dedup.json`. If Rust writes `dismissed: true` between Python's read and write, Python will clobber it back to `false`.

**Solution**: Rust writes dismiss/clear commands to **sidecar files** instead of mutating the main JSON:
- `~/.claude/error-dedup-dismiss.json` — `{ "dismissed_hashes": ["a3f2e1b0"], "cleared_at": 0, "session_id": "72044793..." }`
- `~/.claude/todo-feed-dismiss.json` — `{ "dismissed_texts": ["TODO: Add input validation..."], "session_id": "72044793..." }`

**Why text-based dismiss for TODOs (not index-based)**: The Stop hook fires after every Claude response turn, not just session end. `todo-extractor.py` rescans the full transcript each time and rewrites `todo-feed.json`. Item order/count can shift between writes, making index-based dismiss unreliable. Text matching is stable.

**Clear mechanism**: `cleared_at` is a Unix timestamp (0 = not cleared). In `get_monitor_data`, any error with `last_seen_ts <= cleared_at` is treated as dismissed. New errors appearing AFTER the clear timestamp are shown normally. This avoids hiding future errors.

**Session scoping**: Both sidecar files store `session_id`. When `get_monitor_data` detects that the main JSON's `session_id` differs from the sidecar's, it auto-resets the sidecar file (new session = fresh dismiss state).

The Rust `get_monitor_data` command reads BOTH the main file and the dismiss sidecar, merging dismiss state in the response. No write conflicts with Python. The dismiss files are tiny and written only by Rust.

For `hook-health.json`: mute/unmute already uses `hook-health-disabled.json` (separate file read by Python). Rust writes to that file — no race.

For `statusline-state.json`: read-only from Rust. Handle parse failures gracefully (non-atomic writer).

## Files

### New Files (2)
1. **`apps/desktop/src-tauri/src/commands/monitor.rs`** — 4 Tauri commands + response structs
2. **`apps/desktop/src/views/MonitorView.tsx`** — React view (~250 lines)

### Edited Files (7)
3. **`apps/desktop/src-tauri/src/commands/mod.rs`** — add `pub mod monitor;`
4. **`apps/desktop/src-tauri/src/lib.rs`** — register 4 commands in `generate_handler![]` (currently 45 commands)
5. **`apps/desktop/src/lib/commands.ts`** — add 4 `invoke()` wrappers
6. **`apps/desktop/src/store/uiStore.ts`** — add `'monitor'` to `AppMode` union type (line 3) + `VALID_MODES` array (line 67)
7. **`apps/desktop/src/shell/TopBar.tsx`** — add `{ id: 'monitor', label: 'Monitor', key: '8' }` to MODES array (after sessions key=7, before dashboard key=9)
8. **`apps/desktop/src/shell/Shell.tsx`** — add `'8': 'monitor'` to `modeKeys` object (line 616) + update HOTKEYS display string (line ~445)
9. **`apps/desktop/src/shell/Canvas.tsx`** — add `import { MonitorView }` + `{mode === 'monitor' && <MonitorView />}` conditional

### No new dependencies
- Rust: `serde_json` "1" + `serde` with `derive` already in Cargo.toml
- React: existing CSS classes from `views.module.css` (all 14 classes confirmed present)

## Rust Commands (`monitor.rs`)

### Home directory resolution
Use existing inline pattern from `sessions.rs:197`:
```rust
let home = std::env::var("USERPROFILE")
    .or_else(|_| std::env::var("HOME"))
    .map(std::path::PathBuf::from)
    .map_err(|_| "cannot find home directory".to_string())?;
let claude_dir = home.join(".claude");
```

### Response structs
Use `#[derive(Debug, Clone, Serialize)]` + `#[serde(rename_all = "camelCase")]` (matches existing pattern in `sessions.rs`, `git.rs`).

Read JSON files with `serde_json::Value` for resilience, then manually construct typed output structs. Handle polymorphic `hook-health.json` entries (quality-gate has `last_result` + `block_count_1h` instead of `last_error`).

### Commands

```rust
#[tauri::command]
pub fn get_monitor_data() -> Result<MonitorData, String>
// Reads all 4 main JSON files + 2 dismiss sidecar files
// Merges dismiss state into response
// Returns null sections for missing/unparseable files

#[tauri::command]
pub fn dismiss_monitor_error(hash: String) -> Result<(), String>
// Reads ~/.claude/error-dedup-dismiss.json, adds hash to dismissed_hashes, writes back

#[tauri::command]
pub fn dismiss_monitor_todo(text: String) -> Result<(), String>
// Reads ~/.claude/todo-feed-dismiss.json, adds text to dismissed_texts set, writes back

#[tauri::command]
pub fn clear_monitor_errors() -> Result<(), String>
// Sets cleared_at=<current unix timestamp> in ~/.claude/error-dedup-dismiss.json
// Errors with last_seen_ts <= cleared_at will be hidden in get_monitor_data response
```

No state injection needed — these commands don't access `AppState`, `DbState`, or `SidecarState`. They only do filesystem I/O.

### MonitorData response shape
```typescript
{
  hookHealth: {
    ts: number | null,
    overallStatus: string,
    hooks: Record<string, {
      status: string,
      lastFireTs: number | null,
      errorCount1h: number,
      lastError: string | null,    // null for quality-gate
      lastResult: string | null,   // null for non-quality-gate hooks
      blockCount1h: number | null  // null for non-quality-gate hooks
    }>,
    disabledHooks: string[]
  } | null,
  errorDedup: {
    ts: number | null,
    sessionId: string,
    errors: Record<string, {
      hash: string, canonical: string, count: number,
      firstSeenTs: number, lastSeenTs: number, tool: string, dismissed: boolean
    }>,
    alert: { active: boolean, hash: string, message: string, count: number }
  } | null,
  todoFeed: {
    ts: number | null,
    sessionId: string,
    project: string,
    count: number,
    items: Array<{
      text: string, source: string, context: string, filePath: string,
      category: string, ts: number, dismissed: boolean
    }>,
    persistedToBacklog: boolean
  } | null,
  statusline: {
    pct: number, cost: number, model: string, project: string,
    sessionId: string, remK: number, durationMs: number
  } | null
}
```

## React View (`MonitorView.tsx`)

### Layout (4 sections using existing CSS classes)

1. **Session Status cards** (`.cards` > `.card`) — context %, cost, model, project, session duration
2. **Hook Health table** (`.table`) — hook name, status dot (colored), last fire time, error count, detail. Overall status in header.
3. **Error Alerts** — active alert banner (inline styled, dark red) + errors table with dismiss buttons
4. **TODOs list** — items table with category, text, source, file path, dismiss buttons

### Polling pattern
```tsx
useEffect(() => {
  let cancelled = false
  function poll() {
    backend.getMonitorData()
      .then(d => { if (!cancelled) setData(d) })
      .catch(() => {})
  }
  poll()
  const id = setInterval(poll, 5_000)
  return () => { cancelled = true; clearInterval(id) }
}, [])
```
Matches existing pattern in `SystemView.tsx:23-33` and `TopBar.tsx:72-85`.

### Empty/placeholder state
When no data exists (all sections null):
```tsx
<div className={styles.placeholder}>
  <div className={styles.icon}>◈</div>
  <div className={styles.label}>Monitor</div>
  <div className={styles.sub}>No monitoring data — start a Claude Code session</div>
</div>
```
Matches existing SystemView placeholder pattern.

### Dismiss handlers
```tsx
const handleDismissError = (hash: string) => {
  backend.dismissMonitorError(hash).then(poll)
}
const handleDismissTodo = (text: string) => {
  backend.dismissMonitorTodo(text).then(poll)
}
const handleClearErrors = () => {
  backend.clearMonitorErrors().then(poll)
}
```
Each calls the Rust command then triggers a re-poll to refresh UI.

## Execution Sequence

### Step 1: Rust commands
Create `apps/desktop/src-tauri/src/commands/monitor.rs`:
- Home dir resolution helper (inline)
- `MonitorData`, `HookHealthData`, `HookEntry`, `ErrorDedupData`, `ErrorEntry`, `AlertInfo`, `TodoFeedData`, `TodoItem`, `StatuslineData` structs with serde derives
- `read_json_file(path) -> Option<serde_json::Value>` helper (handles missing file + parse failure)
- 4 `#[tauri::command]` functions

### Step 2: Register module
Edit `apps/desktop/src-tauri/src/commands/mod.rs` — add `pub mod monitor;` (alphabetical: after `module`, before `sessions`)

### Step 3: Register commands
Edit `apps/desktop/src-tauri/src/lib.rs` — add 4 entries to `generate_handler![]`:
```rust
commands::monitor::get_monitor_data,
commands::monitor::dismiss_monitor_error,
commands::monitor::dismiss_monitor_todo,
commands::monitor::clear_monitor_errors,
```

### Step 4: Frontend type + mode
Edit `apps/desktop/src/store/uiStore.ts`:
- Add `| 'monitor'` to `AppMode` type union (line 3)
- Add `'monitor'` to `VALID_MODES` array (line 67)

### Step 5: TopBar
Edit `apps/desktop/src/shell/TopBar.tsx` — add to MODES array (between sessions key=7 and dashboard key=9):
```ts
{ id: 'monitor', label: 'Monitor', key: '8' },
```

### Step 6: Keyboard shortcuts
Edit `apps/desktop/src/shell/Shell.tsx`:
- Add `'8': 'monitor'` to `modeKeys` (line 616)
- Update HOTKEYS display string to include "Monitor" (line ~445)

### Step 7: Canvas routing
Edit `apps/desktop/src/shell/Canvas.tsx`:
- Add import: `import { MonitorView } from '../views/MonitorView'`
- Add conditional: `{mode === 'monitor' && <MonitorView />}` (after sessions, before worlds)

### Step 8: Command wrappers
Edit `apps/desktop/src/lib/commands.ts` — add 4 wrappers.

Two invoke patterns exist in this file:
- **Struct-based** (most commands): `(cmd: {...}) => invoke('name', { cmd })` — Rust receives `cmd: SomeStruct`
- **Direct params** (simple commands): `(path: string) => invoke('name', { path })` — Rust receives `path: String`

Use direct params for the simple dismiss commands (matches `readFileDiff`, `readSessionLog` pattern):
```ts
getMonitorData: () => invoke<MonitorData>('get_monitor_data'),
dismissMonitorError: (hash: string) => invoke('dismiss_monitor_error', { hash }),
dismissMonitorTodo: (text: string) => invoke('dismiss_monitor_todo', { text }),
clearMonitorErrors: () => invoke('clear_monitor_errors'),
```
Plus TypeScript interfaces for `MonitorData` and sub-types (defined in same file, following `GitStatus`/`ClaudeSessionInfo` pattern).

### Step 9: MonitorView
Create `apps/desktop/src/views/MonitorView.tsx`:
- Import `useState`, `useEffect`, CSS module, `backend`
- Define local `HOOK_STATUS_COLOR: Record<string, string>` map: `{ healthy: '#4caf50', stale: '#ff9800', error: '#f44336', muted: '#9e9e9e', unknown: '#555' }`
  (Note: `STATE_COLOR` from `constants.ts` maps agent states, NOT hook statuses — do NOT reuse it)
- Polling effect (5s interval)
- 4-section layout using existing CSS classes
- Dismiss/clear button handlers
- Placeholder when no data

### Step 10: Verify
- `pnpm dev` — app launches, Monitor tab visible
- Press `8` — switches to Monitor view
- With active Claude session: all 4 sections show live data
- Without JSON files: placeholder shown
- Dismiss error → refreshes correctly
- `pnpm typecheck` — no type errors
- `pnpm lint` — no lint errors

## Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Sidecar dismiss files | Avoids TOCTOU race with Python's read-modify-write on error-dedup.json |
| `serde_json::Value` for reading | JSON schemas owned by external Python scripts; `Value` prevents build breaks on schema drift |
| `Option<>` for polymorphic fields | hook-health.json has different fields for quality-gate vs other hooks |
| No `AppState` access | Monitor commands are pure filesystem I/O, no shared state needed |
| Polling in view, not store | Matches existing pattern (TopBar polls sidecar/git); monitor data isn't domain state |
| Separate view from SystemView | Different data sources, different refresh concerns, cleaner separation |
| Home dir via env vars | No `dirs` crate in project; reuses existing `sessions.rs` pattern |
| Graceful null sections | Each JSON file independently nullable; partial data is useful |

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Partial JSON from statusline-state.json (non-atomic writer) | `read_json_file` returns `None` on parse failure; UI shows "—" |
| Dismiss sidecar files grow unbounded | Session-scoped: sidecar stores `session_id`; auto-reset when main JSON's session_id changes |
| Python schema changes break Rust parsing | `serde_json::Value` + `.get()` with defaults; never hard-fail on unknown fields |
| 5s poll on 4+ files | Each file is <2KB; `read_to_string` is sub-ms; total I/O budget ~5ms per poll |
| AHK scripts still running | Out of scope — user can retire AHK scripts after Monitor view is stable |

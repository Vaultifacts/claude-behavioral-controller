# Feature: Multi-World Support ("Worlds" Tab)

## Context
Users want to connect to different project directories and switch between them. Currently the app supports only one workspace at a time — switching destroys the old one. The DB already supports multiple workspaces (all entities have `workspace_id`), but `AppState` holds only one, and `delete_workspace_data` nukes everything globally.

We'll implement in two tiers: **Tier 1** (Worlds tab + clean switching, no Rust AppState redesign) then optionally **Tier 2** (scoped deletion + background persistence).

## Current Architecture
- **DB**: Multi-workspace ready (all entities have `workspace_id`, `list_workspaces` returns all)
- **AppState (Rust)**: Single `workspace: Option<Workspace>` — one active workspace at a time
- **Sidecar**: Workspace-unaware (routes by `agent_id` UUID, not workspace). Single process shared across worlds
- **Frontend**: Single `workspace` in domainStore. Switching calls `openWorkspace` → full tear-down + re-hydrate
- **`delete_workspace_data`**: Nukes ALL tables globally (not scoped by workspace_id)

## Plan

### Part 1: "Worlds" Tab (frontend only)

**1a. Add `'worlds'` mode to uiStore**
- File: `apps/desktop/src/store/uiStore.ts`
- Add `'worlds'` to `AppMode` union type
- Add to `VALID_MODES` array

**1b. Create WorldsView component**
- File: `apps/desktop/src/views/WorldsView.tsx` (new file)
- On mount, call `backend.listWorkspaces()` to get all `WorkspaceSummary[]`
- Render a card grid: each card shows name, rootPath, agentCount, taskCount, openedAt
- Active workspace highlighted with a green border
- Each card has "Switch" button (calls existing `openWorkspace` flow) and "Delete" button (with inline confirmation)
- "Create New World" button at the bottom opens an inline form (name + path)
- Poll `listWorkspaces` every 10 seconds to refresh counts

**1c. Wire into Canvas.tsx**
- File: `apps/desktop/src/shell/Canvas.tsx`
- Add: `{mode === 'worlds' && <WorldsView />}`

**1d. Add tab button to TopBar**
- File: `apps/desktop/src/shell/TopBar.tsx`
- Add "Worlds" as the 8th tab (hotkey: 8)
- Update Shell.tsx HOTKEYS array to include worlds

### Part 2: Scoped Workspace Deletion (backend fix)

**2a. Add `delete_workspace` Rust command**
- File: `apps/desktop/src-tauri/src/commands/workspace.rs`
- New command: `delete_workspace(workspace_id: String)` that:
  - Deletes only rows WHERE `workspace_id = ?` from agents, tasks, artifacts, modules, event_log, agent_chat
  - Deletes the workspace row itself
  - If it's the active workspace, also resets AppState and emits workspace-closed

**2b. Add frontend command wrapper**
- File: `apps/desktop/src/lib/commands.ts`
- Add `deleteWorkspace: (cmd: { workspaceId: string }) => invoke('delete_workspace', { cmd })`

**2c. Register in lib.rs**
- File: `apps/desktop/src-tauri/src/lib.rs`
- Add `delete_workspace` to the `generate_handler!` macro

**2d. Fix `load_initial_state` to scope by workspace_id**
- File: `apps/desktop/src-tauri/src/db/ops.rs`
- Change agent/task/artifact/module queries from global to WHERE `workspace_id = ?`
- Pass the workspace_id from the LIMIT 1 workspace query

### Part 3: Clean Workspace Switching

**3a. Save state before switching**
- File: `apps/desktop/src-tauri/src/commands/workspace.rs`
- In `switch_workspace`, before resetting AppState, persist all in-memory agent/task states to DB

**3b. Frontend handles workspace-closed → show Worlds tab**
- File: `apps/desktop/src/store/bridge.ts`
- On `workspace-closed`, set mode to `'worlds'` instead of showing WorkspaceSetup
- WorldsView auto-refreshes and shows available worlds

## Files to Modify

| File | Change |
|------|--------|
| `apps/desktop/src/store/uiStore.ts` | Add 'worlds' to AppMode |
| `apps/desktop/src/views/WorldsView.tsx` | New file — worlds dashboard |
| `apps/desktop/src/shell/Canvas.tsx` | Render WorldsView |
| `apps/desktop/src/shell/TopBar.tsx` | Add Worlds tab button |
| `apps/desktop/src/shell/Shell.tsx` | Add hotkey 8 → worlds |
| `apps/desktop/src/lib/commands.ts` | Add deleteWorkspace wrapper |
| `apps/desktop/src-tauri/src/commands/workspace.rs` | Add delete_workspace, fix switch |
| `apps/desktop/src-tauri/src/lib.rs` | Register delete_workspace |
| `apps/desktop/src-tauri/src/db/ops.rs` | Scope load_initial_state + add delete_workspace_by_id |

## Verification
1. `pnpm typecheck` + `cargo check` pass
2. Launch app → Worlds tab visible as 8th tab
3. Worlds tab shows all workspaces with agent/task counts
4. Click "Switch" → workspace switches, World/System tabs reflect new data
5. Click "Delete" → confirmation → workspace removed from list, data gone
6. Create New World → form → workspace appears in list
7. Active workspace highlighted in the list
8. Switching workspaces preserves old workspace data in DB (re-openable)

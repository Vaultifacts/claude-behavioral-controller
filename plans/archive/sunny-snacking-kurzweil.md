# Plan: Start ChatGPT Project Bridge for Kanban Board

## Context
The user wants to kick off a Claude ↔ ChatGPT collaborative dev session to build a Kanban board web app. The opening message prompt they provided IS the `buildDiscussPrompt()` template already baked into `chatgpt_project_bridge.js` — no custom scripting needed. Just invoke the bridge with the right goal and directory.

## Implementation

### Single step: Run the project bridge

```bash
node chatgpt_project_bridge.js \
  "Create a Kanban board web app with drag-and-drop columns and cards, local storage persistence" \
  --dir "C:/Users/Matt1/OneDrive/Desktop/kanban-board-web-app-with-drag-and-drop-"
```

**What this does automatically:**
1. Launches Chrome with persistent profile (preserves ChatGPT login)
2. Opens a fresh ChatGPT chat
3. Discuss Phase (Cycle 1, Turn 1): Claude haiku generates the opening message using `buildDiscussPrompt(isFirstTurn=true)` — which matches the user's specified format exactly (tech stack, what to build first, advisor invite, concise response instruction)
4. `sendAndReceive()` sends it to ChatGPT and waits for reply
5. Implement Phase: Claude builds the Kanban app in `--dir` with full tool access
6. Repeats for subsequent cycles until stopped

## Critical files
- `chatgpt_project_bridge.js` — main entry point (not modified)
- `lib.js` — sendAndReceive, runClaude, browser launch (not modified)
- Project dir: `C:/Users/Matt1/OneDrive/Desktop/kanban-board-web-app-with-drag-and-drop-` (will be created)

## Verification
- Chrome window should open headlessly → navigate to ChatGPT
- Console should print `[Discuss C1/T1] Claude →` followed by the opening message
- ChatGPT reply appears as `[Discuss C1/T1] ChatGPT →`
- Implement phase begins with `[Impl C1] Running Claude...`

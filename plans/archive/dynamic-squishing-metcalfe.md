# Plan: NagaOS — Adaptive Naga Controller

## Why this matters
Matt already built a full sensor layer: statusline-state.json gets written every turn with
`{pct, cost, model, session_id, rate_remaining, ts}`. His CLAUDE.md has strict rules about
pre-compact saves. His hooks fire toasts at 70%. But the RESPONSE to all this data is still
manual — he has to read the statusline, remember to save, type /compact, etc.

The Naga shouldn't just be a shortcut keyboard. It should be a **closed-loop controller**
that reads the sensor data and adapts its behavior accordingly.

## What makes this different from "buttons = slash commands"
1. **It reads statusline-state.json** — buttons change meaning based on Claude Code state
2. **It has memory** — tracks sessions, warns on cumulative cost
3. **It provides visual feedback** — tray icon/tooltip shows live context %, cost, session status
4. **It enforces the pre-compact save rule** — instead of `/compact`, button 1 sends
   a smarter command that tells Claude to save first, THEN compact (matching the CLAUDE.md rule)
5. **It works across windows** — terminal buttons vs system buttons vs project launcher

## Architecture

### Core: State Monitor (timer-based, every 5 seconds)
Read `~/.claude/statusline-state.json` and update internal state:
- `pct` → context percentage (drives button adaptation + tray color)
- `cost` → session cost (drives tray tooltip)
- `rate_remaining` → rate limit warnings
- `ts` → freshness check (if stale >60s, Claude Code may not be running)

### Tray Icon
Always-visible system tray icon showing:
- **Green H** → context < 65%
- **Yellow H** → context 65-84% ("up ctx")
- **Red H** → context ≥ 85% (critical)
Tooltip: `Claude: 63% | $6.98 | O4.6 | 58m`
When no active session (stale ts): `No active session`

### Button Layers (3 layers, cycled with long-press button 12)

#### Layer 1: Claude Code (default when terminal is focused)
Adapts based on context state:

**Normal state (context < 65%):**
| Button | Action |
|--------|--------|
| 1 | `/compact{Enter}` |
| 2 | `/clear{Enter}` |
| 3 | `/recall ` (+ wait for query) |
| 4 | `/ticket ` (+ wait for desc) |
| 5 | `/review{Enter}` |
| 6 | `/commit{Enter}` |
| 7 | `/standup{Enter}` |
| 8 | `/run-tests{Enter}` |
| 9 | `/diff{Enter}` |

**Warning state (context 65-84%):**
| Button | Change |
|--------|--------|
| 1 | **Becomes smart compact**: sends a message telling Claude to save findings to memory THEN compact (enforces CLAUDE.md rule) |

**Critical state (context ≥ 85%):**
| Button | Change |
|--------|--------|
| 1 | Same as warning but with urgency — sends pre-compact + compact instruction |
| Tray | Pulses/flashes to draw attention |

The smart compact command for button 1 at 65%+:
```
Save any important findings to memory files, then /compact{Enter}
```

**Always (any context level):**
| Button | Action |
|--------|--------|
| 10 | `{Enter}` |
| 11 | `{Backspace}` |
| 12 | Short press: `{Escape}` / Long press (>500ms): cycle layer |

#### Layer 2: Window Management (any app)
| Button | Action |
|--------|--------|
| 1 | Snap window left half |
| 2 | Snap window right half |
| 3 | Snap window top-left quarter |
| 4 | Snap window top-right quarter |
| 5 | Snap window bottom-left quarter |
| 6 | Snap window bottom-right quarter |
| 7 | Maximize/restore toggle |
| 8 | Minimize |
| 9 | Always on top toggle |
| 10 | `{Enter}` |
| 11 | Previous virtual desktop |
| 12 | Short: next virtual desktop / Long: cycle layer |

#### Layer 3: Project Launcher
| Button | Action |
|--------|--------|
| 1-9 | Launch Claude Code in project directory (from config) |
| 10 | `{Enter}` |
| 11 | passthrough |
| 12 | Short: passthrough / Long: cycle layer |

Project directories read from `C:\Users\Matt1\Documents\Naga\projects.ini`:
```ini
[projects]
1=C:\Users\Matt1\code-colony
2=C:\Users\Matt1\ai-academy
3=C:\Users\Matt1\vaultifacts
; etc — empty entries are ignored
```

### Non-terminal passthrough
When active window is NOT a terminal and layer is 1:
buttons 1-9 send their normal characters (1-9).
Button 10/11/12 always send Enter/Backspace/Escape.

### Terminal detection
Window title regex: `MINGW|bash|Git Bash|PowerShell|Command Prompt|Windows Terminal|cmd\.exe`

### Layer indicator
When layer changes, show tooltip for 2s: "Layer: Claude Code" / "Layer: Windows" / "Layer: Projects"

## File structure
```
C:\Users\Matt1\Documents\Naga\
├── naga-enter.ahk        → main script (full rewrite)
├── projects.ini           → project launcher config (user-editable)
└── Lib\                   → AutoHotInterception libraries (existing)
```

## Implementation approach
Single-file AHK script with clean sections:
1. Config block at top (button maps, terminal regex, project paths)
2. AHI setup + auto-detect Naga
3. State monitor (SetTimer every 5s, reads statusline-state.json)
4. Tray icon management (Menu, Tray)
5. Key callback (layer router → handler)
6. Layer-specific handlers
7. Window management functions

## Verification
1. Launch script → tray icon appears with correct context %
2. In terminal: press button 1 → /compact fires
3. Wait for context to hit 65%+ → button 1 changes to smart compact
4. In Notepad: press button 1 → types "1"
5. Long-press button 12 → layer switches, tooltip confirms
6. In Layer 2: press button 1 → window snaps left
7. In Layer 3: press button 1 → Claude Code opens in project dir
8. Tray tooltip shows live stats (context, cost, duration)

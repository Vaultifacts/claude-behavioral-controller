import sys
import json
import os
import subprocess

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

session_id = payload.get('session_id', '')

# Get context % from statusline state file, fall back to payload
pct = 0
try:
    with open(f'{STATE_DIR}/statusline-state.json') as f:
        state = json.load(f)
    if not session_id or state.get('session_id') == session_id:
        pct = int(state.get('pct', 0))
except Exception:
    pass

# Fallback: derive from payload context fields if state file unavailable
if pct == 0:
    try:
        ctx = payload.get('context', {})
        if isinstance(ctx, dict):
            used = int(ctx.get('tokens_used', 0) or 0)
            total = int(ctx.get('context_window', 0) or 0)
            if total > 0:
                pct = int((used / total) * 100)
    except Exception:
        pass

if pct < 70:
    sys.exit(0)

# Debounce: only toast when crossing a new 10% boundary per session
toast_path = f'{STATE_DIR}/context-toast-state.json'
last_threshold = 0
try:
    with open(toast_path) as f:
        ts_state = json.load(f)
    if ts_state.get('session_id') == session_id:
        last_threshold = ts_state.get('last_threshold', 0)
except Exception:
    pass

current_threshold = (pct // 10) * 10

if current_threshold <= last_threshold:
    # Already toasted at this level; inject message for Claude only at 90%+
    if pct >= 90:
        print(f'[context-watch] Context at {pct}% — compact needed. BEFORE compacting: (1) save findings/memory to disk (2) update MEMORY.md (3) update plan file if applicable. Then /compact.')
    sys.exit(0)

# Save new threshold — atomic write to avoid race condition with concurrent sessions
try:
    tmp_path = toast_path + '.tmp'
    with open(tmp_path, 'w') as f:
        json.dump({'session_id': session_id, 'last_threshold': current_threshold}, f)
    os.replace(tmp_path, toast_path)
except Exception:
    pass

# Fire Windows toast via notify.ps1
if pct >= 85:
    tip_title = 'Claude Code — Context Critical'
    tip_msg = f'Context at {pct}% — run /compact now'
    level = 'Error'
else:
    tip_title = 'Claude Code — Context Alert'
    tip_msg = f'Context at {pct}% — consider /compact'
    level = 'Info'

notify_script = f'{STATE_DIR}/hooks/notify.ps1'
try:
    subprocess.Popen(
        ['powershell.exe', '-WindowStyle', 'Hidden', '-File', notify_script,
         '-Title', tip_title, '-Message', tip_msg, '-Level', level, '-Duration', '6000'],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
except Exception:
    pass

# At 90%+: inject message that Claude sees via PostToolUse stdout
if pct >= 90:
    print(f'[context-watch] Context at {pct}% — compact needed. BEFORE compacting: (1) save findings/memory to disk (2) update MEMORY.md (3) update plan file if applicable. Then /compact.')

sys.exit(0)

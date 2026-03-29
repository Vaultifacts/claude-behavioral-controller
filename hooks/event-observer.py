"""
event-observer.py — Shared observer for InstructionsLoaded, ConfigChange, SessionStart.
Routes on hook_event_name. Appends to hook-audit.log. Always exits 0.
"""
import sys
import json
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import rotate_log

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH = f'{STATE_DIR}/hook-audit.log'

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

event = payload.get('hook_event_name', '')
now = datetime.now().strftime('%Y-%m-%d %H:%M')
line = ''

if event == 'InstructionsLoaded':
    load_reason = payload.get('load_reason', '?')
    file_path = payload.get('file_path', '?')
    line = f'{now} | INSTRUCTIONS | {load_reason} | {file_path}'

elif event == 'ConfigChange':
    source = payload.get('source', '?')
    file_path = payload.get('file_path', '?')
    line = f'{now} | CONFIG_CHANGE | {source} | {file_path}'
    # stderr for verbose mode (Ctrl+O) visibility
    print(f'[config-change] {source}: {file_path}', file=sys.stderr)

elif event == 'SessionStart':
    # Also handles post-compact (routed here via SessionStart compact matcher)
    trigger = payload.get('trigger', '?')
    line = f'{now} | SESSION_START | {trigger}'

else:
    sys.exit(0)

try:
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    rotate_log(LOG_PATH, 200, min_size=50_000)
except Exception:
    pass

sys.exit(0)

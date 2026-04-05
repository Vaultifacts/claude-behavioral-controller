"""
permission-request-log.py — PermissionRequest hook.
Logs runtime permission requests to hook-audit.log.
Always exits 0. Async.
"""
import sys, json, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import rotate_log

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH = f'{STATE_DIR}/hook-audit.log'


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '?')
    tool_input = payload.get('tool_input', {})
    context = ''
    if isinstance(tool_input, dict):
        context = (tool_input.get('command', '') or tool_input.get('file_path', ''))[:80]

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f'{now} | PERMISSION_REQUEST | {tool_name} | {context}\n'

    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line)
        rotate_log(LOG_PATH, 200)
    except Exception:
        pass


if __name__ == "__main__":
    main()

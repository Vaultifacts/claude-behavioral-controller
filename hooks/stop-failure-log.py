"""
stop-failure-log.py — StopFailure hook.
Logs API errors (rate_limit, auth_failed, server_error, etc.) to hook-audit.log
and sends a desktop notification for non-rate-limit failures.
Always exits 0. Async.
"""
import sys
import json
import os
import subprocess
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

    error = payload.get('error', 'unknown')
    error_details = (payload.get('error_details', '') or '')[:200]
    last_msg = (payload.get('last_assistant_message', '') or '')[:100]
    session_id = (payload.get('session_id', '') or '')[:8] or '?'

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f'{now} | STOP_FAIL | {error} | {error_details} | session={session_id} | last_msg={last_msg}\n'

    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line)
        rotate_log(LOG_PATH, 200)
    except Exception:
        pass

    # Desktop notification for non-rate-limit errors
    if error not in ('rate_limit',):
        notify_script = os.path.join(STATE_DIR, 'hooks', 'notify.ps1').replace('/', '\\')
        try:
            subprocess.Popen(
                [
                    'powershell.exe', '-WindowStyle', 'Hidden', '-File', notify_script,
                    '-Title', 'Claude Code — API Error',
                    '-Message', f'{error}: {error_details[:80]}',
                    '-Level', 'Error',
                    '-Duration', '8000',
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


if __name__ == "__main__":  # pragma: no cover
    main()
    sys.exit(0)

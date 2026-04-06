"""
pre-compact-snapshot.py — PreCompact hook.
Snapshots the transcript before compaction destroys full history.
Fires a toast on manual compacts. Always exits 0. Async.
"""
import sys
import json
import os
import shutil
import subprocess
from datetime import datetime

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH = f'{STATE_DIR}/hook-audit.log'
SESSIONS_DIR = f'{STATE_DIR}/sessions'


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    session_id = (payload.get('session_id', '') or '')[:8] or '?'
    trigger = payload.get('trigger', '?')
    transcript_path = payload.get('transcript_path', '')

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')

    # Snapshot transcript if it exists
    if transcript_path and os.path.isfile(transcript_path):
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        dest = f'{SESSIONS_DIR}/{timestamp}-{session_id}.jsonl.bak'
        try:
            shutil.copy2(transcript_path, dest)
        except Exception:
            pass

    # Toast on manual compacts
    if trigger == 'manual':
        try:
            ps_cmd = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$n = New-Object System.Windows.Forms.NotifyIcon; "
                "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                "$n.Visible = $true; "
                "$n.ShowBalloonTip(4000, 'Claude Code', 'Compact snapshot saved', "
                "[System.Windows.Forms.ToolTipIcon]::Info); "
                "Start-Sleep -Seconds 5; "
                "$n.Dispose()"
            )
            subprocess.Popen(
                ['powershell.exe', '-WindowStyle', 'Hidden', '-Command', ps_cmd],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    # Log
    try:
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(f'{now} | PRE_COMPACT | {trigger} | {session_id}\n')
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()

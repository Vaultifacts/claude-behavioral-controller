"""
qg-session-recall.py -- SessionStart hook.
Injects previous session qg failures summary as a system message.
Only fires if snapshot file exists (written by session-end-log.py when session had 1+ blocks).
Deletes snapshot after reading so it appears only once.
Skips if snapshot is older than 24 hours (stale data).
"""
import sys
import os
import json
import time

STATE_DIR = os.path.expanduser('~/.claude')
SNAPSHOT = os.path.join(STATE_DIR, 'last-session-qg-failures.txt')

if os.path.exists(SNAPSHOT):
    try:
        age_hours = (time.time() - os.path.getmtime(SNAPSHOT)) / 3600
        if age_hours > 24:
            os.remove(SNAPSHOT)
            sys.exit(0)
        text = open(SNAPSHOT, encoding='utf-8').read().strip()
        if text:
            header = '[qg-recall] Previous session quality gate summary:'
            msg = header + chr(10) + text
            print(json.dumps({'type': 'system', 'message': msg}))
            os.remove(SNAPSHOT)
            sys.exit(0)
    except Exception:
        pass

sys.exit(0)

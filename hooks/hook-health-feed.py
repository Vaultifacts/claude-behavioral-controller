"""
hook-health-feed.py — P1: Hook Health Monitor feed script
Parses hook log files, writes hook-health.json for claude-monitor.ahk.
Runs as: SessionStart hook (async) + AHK 60s timer (RunWait).
Always exits 0. Uses atomic_write with retry for Windows PermissionError.
"""
import json
import os
import re
import sys
import time
from datetime import datetime

HOOKS_DIR  = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.path.dirname(HOOKS_DIR)
LOG_DIR    = CLAUDE_DIR

HEALTH_FILE   = os.path.join(CLAUDE_DIR, 'hook-health.json')
DISABLED_FILE = os.path.join(CLAUDE_DIR, 'hook-health-disabled.json')
STATE_FILE    = os.path.join(CLAUDE_DIR, 'statusline-state.json')

LOG_FILES = {
    'hook-audit.log':      os.path.join(LOG_DIR, 'hook-audit.log'),
    'quality-gate.log':    os.path.join(LOG_DIR, 'quality-gate.log'),
    'task-classifier.log': os.path.join(LOG_DIR, 'task-classifier.log'),
}

# 7 monitored hooks (context-watch has no log file — Tier C/unmonitored)
# max_age=None  = event-driven, no staleness threshold
# max_age=N     = expected to fire within N seconds during active session
HOOK_STALENESS = {
    'tool-failure-log': {'log': 'hook-audit.log',      'max_age': None},
    'quality-gate':     {'log': 'quality-gate.log',    'max_age': None},
    'task-classifier':  {'log': 'task-classifier.log', 'max_age': 300},
    'stop-failure-log': {'log': 'hook-audit.log',      'max_age': None},
    'session-end-log':  {'log': 'hook-audit.log',      'max_age': None},
    'event-observer':   {'log': 'hook-audit.log',      'max_age': 600},
}

RE_HOOK_AUDIT   = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\|\s*(\w[\w_-]*)\s*\|(.*)')
RE_QUALITY_GATE = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(PASS|BLOCK|WARN)\s*\|(.*)')
RE_TASK_CLASS   = re.compile(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s*\|(.*)')
RE_ERROR        = re.compile(r'\b(?:FAIL|ERROR|Exception|Traceback|exit code [1-9])\b', re.IGNORECASE)

TAIL_LINES = 200
HOUR_SECS  = 3600


def atomic_write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    for _ in range(3):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1)


def read_tail(path, n=TAIL_LINES):
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            return f.readlines()[-n:]
    except Exception:
        return []


def parse_ts(ts_str, fmt):
    try:
        return datetime.strptime(ts_str.strip(), fmt).timestamp()
    except Exception:
        return None


def parse_hook_audit(lines):
    results = {}
    for line in lines:
        m = RE_HOOK_AUDIT.match(line.rstrip())
        if not m:
            continue
        ts  = parse_ts(m.group(1), '%Y-%m-%d %H:%M')
        ev  = m.group(2).strip().upper()
        txt = m.group(3).strip()
        results.setdefault(ev, []).append((ts, txt))
    return results


def parse_quality_gate(lines):
    results = []
    for line in lines:
        m = RE_QUALITY_GATE.match(line.rstrip())
        if not m:
            continue
        ts  = parse_ts(m.group(1), '%Y-%m-%d %H:%M:%S')
        dec = m.group(2).strip().upper()
        txt = m.group(3).strip()
        results.append((ts, dec, txt))
    return results


def parse_task_classifier(lines):
    results = []
    for line in lines:
        m = RE_TASK_CLASS.match(line.rstrip())
        if not m:
            continue
        ts  = parse_ts(m.group(1), '%Y-%m-%d %H:%M:%S')
        lbl = m.group(2).strip()
        txt = m.group(3).strip()
        results.append((ts, lbl + ' | ' + txt))
    return results


AUDIT_HOOK_MAP = {
    'tool-failure-log': ['FAIL'],
    'stop-failure-log': ['STOP_FAIL'],
    'session-end-log':  ['SESSION_END'],
    'event-observer':   ['SESSION_START', 'INSTRUCTIONS', 'CONFIG_CHANGE'],
}


def get_entries_for(hook_name, cfg, log_data):
    log_key = cfg['log']
    if log_key == 'hook-audit.log':
        audit = log_data['audit']
        entries = []
        for ev in AUDIT_HOOK_MAP.get(hook_name, []):
            entries.extend(audit.get(ev, []))
        return entries
    elif log_key == 'quality-gate.log':
        return [(ts, dec + ' | ' + txt) for ts, dec, txt in log_data['quality_gate']]
    elif log_key == 'task-classifier.log':
        return log_data['task_class']
    return []


def is_session_active():
    if not os.path.exists(STATE_FILE):
        return False
    try:
        return (time.time() - os.path.getmtime(STATE_FILE)) <= 60
    except Exception:
        return False


def load_disabled():
    if not os.path.exists(DISABLED_FILE):
        return set()
    try:
        with open(DISABLED_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(data)
    except Exception:
        pass
    return set()


def build_hook_entry(hook_name, cfg, log_data, now_ts, active, muted_hooks):
    muted   = hook_name in muted_hooks
    max_age = cfg['max_age']
    entries = [(ts, txt) for ts, txt in get_entries_for(hook_name, cfg, log_data) if ts is not None]
    entries.sort(key=lambda x: x[0])

    last_fire_ts = entries[-1][0] if entries else None
    last_text    = entries[-1][1] if entries else ''
    cutoff       = now_ts - HOUR_SECS
    # These hooks log content (not their own errors) — skip RE_ERROR to avoid false positives
    if hook_name in ('tool-failure-log', 'task-classifier', 'quality-gate'):
        error_count = 0
    else:
        error_count  = sum(1 for ts, txt in entries if ts >= cutoff and RE_ERROR.search(txt))

    block_count = 0
    if cfg['log'] == 'quality-gate.log':
        block_count = sum(1 for ts, d, _ in log_data['quality_gate']
                         if ts is not None and ts >= cutoff and d == 'BLOCK')

    if muted:
        status = 'muted'
    elif last_fire_ts is None:
        status = 'unknown'
    elif error_count > 0:
        status = 'error'
    elif active and max_age is not None and (now_ts - last_fire_ts) > max_age:
        status = 'stale'
    else:
        status = 'healthy'

    entry = {
        'last_fire_ts':   int(last_fire_ts) if last_fire_ts else None,
        'error_count_1h': error_count,
        'status':         status,
    }
    if cfg['log'] == 'quality-gate.log':
        entry['last_result']    = last_text[:120]
        entry['block_count_1h'] = block_count
    else:
        entry['last_error'] = last_text[:120] if RE_ERROR.search(last_text) else ''
    return entry


def main():
    now_ts = time.time()
    active = is_session_active()
    muted  = load_disabled()

    log_data = {
        'audit':       parse_hook_audit(read_tail(LOG_FILES['hook-audit.log'])),
        'quality_gate': parse_quality_gate(read_tail(LOG_FILES['quality-gate.log'])),
        'task_class':   parse_task_classifier(read_tail(LOG_FILES['task-classifier.log'])),
    }

    hooks = {
        name: build_hook_entry(name, cfg, log_data, now_ts, active, muted)
        for name, cfg in HOOK_STALENESS.items()
    }

    statuses = [v['status'] for v in hooks.values() if v['status'] != 'muted']
    if 'error' in statuses:
        overall = 'error'
    elif 'stale' in statuses:
        overall = 'stale'
    elif 'unknown' in statuses:
        overall = 'unknown'
    else:
        overall = 'healthy'

    atomic_write(HEALTH_FILE, {
        'ts':             int(now_ts),
        'hooks':          hooks,
        'overall_status': overall,
        'disabled_hooks': sorted(muted),
    })


try:
    main()
except Exception:
    pass

sys.exit(0)

#!/usr/bin/env python3
"""Layer 10 -- Audit Trail Integrity.
Validates JSONL files, quarantines corrupt lines, rotates at 10,000 lines.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss
import qg_notification_router as nr

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
QUARANTINE_PATH = os.path.expanduser('~/.claude/qg-quarantine.jsonl')
ROTATION_THRESHOLD = 10000


def validate_jsonl(path, quarantine_path=None):
    if not os.path.exists(path):
        return [], []
    qpath = quarantine_path or QUARANTINE_PATH
    valid = []
    corrupt = []
    seen_ids = set()
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                eid = e.get('event_id', '')
                if eid and eid in seen_ids:
                    corrupt.append({'line': i, 'reason': 'duplicate_id', 'raw': line[:200]})
                else:
                    if eid:
                        seen_ids.add(eid)
                    valid.append(line)
            except json.JSONDecodeError as ex:
                corrupt.append({'line': i, 'reason': 'invalid_json',
                                'raw': line[:200], 'error': str(ex)})
    if corrupt:
        ts = time.strftime('%Y-%m-%dT%H:%M:%S')
        with open(qpath, 'a', encoding='utf-8') as f:
            for c in corrupt:
                c.update({'quarantine_ts': ts, 'source': path})
                f.write(json.dumps(c, ensure_ascii=False) + chr(10))
    return valid, corrupt


def maybe_rotate(path, threshold=ROTATION_THRESHOLD):
    if not os.path.exists(path):
        return False
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        count = sum(1 for _ in f)
    if count < threshold:
        return False
    archive = path.replace('.jsonl', '-{}.jsonl'.format(time.strftime('%Y-%m')))
    os.rename(path, archive)
    return True


def run_integrity_check(monitor_path=None, quarantine_path=None):
    # 7-day trigger guard
    try:
        with open(os.path.expanduser('~/.claude/qg-rules.json'), 'r', encoding='utf-8') as f:
            interval_days = json.load(f).get('layer10', {}).get('integrity_check_interval_days', 7)
    except Exception:
        interval_days = 7
    state = ss.read_state()
    last_ts = state.get('last_integrity_check_ts', 0)
    if time.time() - last_ts < interval_days * 86400:
        return {'ts': time.strftime('%Y-%m-%dT%H:%M:%S'), 'status': 'skipped_throttled'}
    path = monitor_path or MONITOR_PATH
    valid, corrupt = validate_jsonl(path, quarantine_path)
    rotated = maybe_rotate(path)
    result = {
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'path': path,
        'valid_lines': len(valid),
        'corrupt_lines': len(corrupt),
        'rotated': rotated,
        'status': 'ok' if not corrupt else 'issues_found',
    }
    state['last_integrity_check_ts'] = time.time()
    if len(corrupt) > 0:
        nr.notify('CRITICAL', 'layer10', 'INTEGRITY', None,
                  '{} corrupt lines in audit trail'.format(len(corrupt)), 'async')
    ss.write_state(state)
    return result


if __name__ == '__main__':
    import sys
    result = run_integrity_check()
    print('Audit trail: {} valid, {} issue(s). Status: {}'.format(
        result['valid_lines'], result['corrupt_lines'], result['status']))
    if result['rotated']:
        print('Rotated {} to monthly archive.'.format(result['path']))

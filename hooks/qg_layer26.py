#!/usr/bin/env python3
"""Layer 2.6 -- Consistency Enforcement (PostToolUse on Write/Edit).
Establishes convention baseline from first 3 files; warns on deviation.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
SNAKE_RE = re.compile(r'\bdef [a-z][a-z0-9_]+\b')
CAMEL_RE = re.compile(r'\bdef [a-z][a-zA-Z0-9]*[A-Z][a-zA-Z0-9]*\b')
IMPORT_DIRECT_RE = re.compile(r'^import [a-zA-Z]', re.MULTILINE)
IMPORT_FROM_RE = re.compile(r'^from [a-zA-Z].*import', re.MULTILINE)


def _write_event(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def detect_convention(content):
    result = {}
    snake = bool(SNAKE_RE.search(content))
    camel = bool(CAMEL_RE.search(content))
    if snake and not camel:
        result['naming'] = 'snake_case'
    elif camel and not snake:
        result['naming'] = 'camelCase'
    direct = bool(IMPORT_DIRECT_RE.search(content))
    frm = bool(IMPORT_FROM_RE.search(content))
    if direct and not frm:
        result['imports'] = 'direct'
    elif frm and not direct:
        result['imports'] = 'from'
    return result


def check_deviation(file_convention, baseline):
    deviations = []
    for key in ('naming', 'imports'):
        fv = file_convention.get(key)
        bv = baseline.get(key)
        if fv and bv and fv != bv:
            deviations.append('{}: {!r} vs baseline {!r}'.format(key, fv, bv))
    return deviations


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    if tool_name not in ('Write', 'Edit'):
        return

    file_path = (payload.get('tool_input') or {}).get('file_path', '')
    _, ext = os.path.splitext(file_path)
    if ext not in ('.py', '.js', '.ts') or not file_path or not os.path.exists(file_path):
        return

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception:
        return

    state = ss.read_state()
    baseline = state.get('layer26_convention_baseline', {})
    files_seen = state.get('layer26_files_seen', 0)
    convention = detect_convention(content)
    if not convention:
        return

    if files_seen < 3:
        for k, v in convention.items():
            if k not in baseline:
                baseline[k] = v
        state['layer26_convention_baseline'] = baseline
        state['layer26_files_seen'] = files_seen + 1
        ss.write_state(state)
        return

    if state.get('layer17_creating_new_artifacts'):
        return

    deviations = check_deviation(convention, baseline)
    if not deviations:
        return

    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    for dev in deviations:
        event = {
            'event_id': str(uuid.uuid4()),
            'ts': ts,
            'session_uuid': state.get('session_uuid') or '',
            'working_dir': os.getcwd(),
            'task_id': state.get('active_task_id', ''),
            'layer': 'layer26',
            'category': 'CONSISTENCY_VIOLATION',
            'severity': 'warning',
            'detection_signal': dev,
            'file_path': file_path,
            'status': 'open',
        }
        _write_event(event)

    ss.write_state(state)


if __name__ == '__main__':  # pragma: no cover
    main()

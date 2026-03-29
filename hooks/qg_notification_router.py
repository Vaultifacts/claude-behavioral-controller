#!/usr/bin/env python3
"""Notification Router for Quality Gate Monitor.
Priority: CRITICAL > WARNING > INFO
hook_context: 'pretooluse', 'posttooluse', 'stop', 'sessionstart', 'async'
"""
import json, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MAX_CRITICALS_PER_TURN = 3
DEDUP_WINDOW_SEC = 60
_turn_critical_count = 0
MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')


def _dedup_key(layer, category, file_path):
    return f'{layer}:{category}:{file_path or ""}'


def _is_duplicate(state, layer, category, file_path):
    key = _dedup_key(layer, category, file_path)
    now = time.time()
    for d in state.get('notification_delivery', []):
        if d.get('dedup_key') == key and (now - d.get('ts', 0)) < DEDUP_WINDOW_SEC:
            return True
    return False


def _record(state, layer, category, file_path, message, status):
    state.setdefault('notification_delivery', []).append({
        'dedup_key': _dedup_key(layer, category, file_path),
        'layer': layer, 'category': category, 'file': file_path,
        'message': message[:200], 'status': status, 'ts': time.time(),
    })


def _write_jsonl(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            print(json.dumps(event, ensure_ascii=False), file=f)
    except Exception:
        pass


def notify(priority, layer, category, file_path, message, hook_context):
    """Route notification. Returns {'additionalContext': ...} for immediate CRITICAL, else None."""
    global _turn_critical_count

    state = ss.read_state()

    if priority == 'INFO':
        _write_jsonl({'priority': 'INFO', 'layer': layer, 'category': category,
                     'file': file_path, 'message': message[:200], 'ts': time.time()})
        _record(state, layer, category, file_path, message, 'logged')
        ss.write_state(state)
        return None

    if _is_duplicate(state, layer, category, file_path):
        _record(state, layer, category, file_path, message, 'dropped')
        ss.write_state(state)
        return None

    if priority == 'WARNING':
        _record(state, layer, category, file_path, message, 'queued_warning')
        ss.write_state(state)
        return None

    # CRITICAL
    if hook_context in ('pretooluse', 'posttooluse'):
        if _turn_critical_count >= MAX_CRITICALS_PER_TURN:
            state.setdefault('notification_pending_criticals', []).append({
                'layer': layer, 'category': category, 'file': file_path,
                'message': message, 'ts': time.time(), 'status': 'queued',
            })
            _record(state, layer, category, file_path, message, 'queued')
            ss.write_state(state)
            return None
        _turn_critical_count += 1
        _record(state, layer, category, file_path, message, 'delivered')
        ss.write_state(state)
        return {'additionalContext': f'[monitor:CRITICAL:{layer}:{category}] {message}'}
    else:
        # stop / sessionstart / async — queue for next PreToolUse
        state.setdefault('notification_pending_criticals', []).append({
            'layer': layer, 'category': category, 'file': file_path,
            'message': message, 'ts': time.time(), 'status': 'queued',
        })
        _record(state, layer, category, file_path, message, 'queued')
        ss.write_state(state)
        return None


def flush_pending_criticals():
    """Flush up to 3 queued CRITICALs. Called by Layer 1.5 at PreToolUse entry."""
    state = ss.read_state()
    pending = state.get('notification_pending_criticals', [])
    if not pending:
        return None
    batch = pending[:3]
    state['notification_pending_criticals'] = pending[3:]
    for p in batch:
        p['status'] = 'delivered'
    ss.write_state(state)
    lines = [f"[monitor:CRITICAL:{p['layer']}:{p['category']}] {p['message']}" for p in batch]
    return '\n'.join(lines)


def flush_warnings():
    """Collect queued WARNINGs for Stop-time batch delivery. Returns text or None."""
    state = ss.read_state()
    warnings = [d for d in state.get('notification_delivery', [])
                if d.get('status') == 'queued_warning']
    if not warnings:
        return None
    for d in warnings:
        d['status'] = 'delivered'
    ss.write_state(state)
    return '\n'.join(f"[monitor:WARNING:{w['layer']}:{w['category']}] {w['message']}"
                     for w in warnings)


def reset_turn_counter():
    global _turn_critical_count
    _turn_critical_count = 0

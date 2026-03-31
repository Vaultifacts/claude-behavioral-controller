#!/usr/bin/env python3
"""Layer 4.5 — Context Preservation (PreCompact / PostCompact).

Usage (set by hook command):
    python qg_layer45.py --pre    (PreCompact hook)
    python qg_layer45.py --post   (PostCompact hook)
"""
import hashlib, json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

PRESERVE_PATH = os.path.expanduser('~/.claude/qg-context-preserve.json')
PRESERVATION_CONFIG_PATH = os.path.expanduser('~/.claude/qg-preservation-config.json')

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


PRESERVE_KEYS = [
    'session_uuid', 'session_start_ts', 'active_task_id', 'active_subtask_id',
    'active_task_description', 'layer1_task_category', 'layer1_scope_files',
    'task_success_criteria', 'layer2_unresolved_events', 'layer35_recovery_events',
    'layer_env_baseline', 'layer17_verified_task_id', 'layer17_intent_text',
    'layer19_last_impact_level', 'layer19_last_impact_file',
    'layer15_session_reads',
]


def _state_hash(state):
    key_data = {k: state.get(k) for k in PRESERVE_KEYS[:5]}
    return hashlib.md5(
        json.dumps(key_data, sort_keys=True, default=str).encode()
    ).hexdigest()[:8]


def handle_pre_compact():
    """Snapshot current session state before compaction."""
    state = ss.read_state()
    preserved = {k: state.get(k) for k in PRESERVE_KEYS}

    # Gap #40: load qg-preservation-config.json for dynamic key management
    try:
        with open(PRESERVATION_CONFIG_PATH, 'r', encoding='utf-8') as _pf:
            _pcfg = json.load(_pf)
        for key in _pcfg.get('always_preserve', []):
            if key not in preserved:
                preserved[key] = state.get(key)
        for key in _pcfg.get('skip_preserve', []):
            preserved.pop(key, None)
    except Exception:
        pass

    # Gap #41: discard resolved events — only keep open events
    for _ekey in ('layer2_unresolved_events', 'layer35_recovery_events'):
        _evts = preserved.get(_ekey)
        if isinstance(_evts, list):
            preserved[_ekey] = [e for e in _evts if e.get('status') == 'open']
    preserved['pre_compact_hash'] = _state_hash(state)
    preserved['preserved_at'] = time.time()
    import uuid as _uuid
    _write_event({'event_id': str(_uuid.uuid4()), 'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
                  'layer': 'layer45', 'category': 'PRE_COMPACT', 'severity': 'info',
                  'detection_signal': f'Preserved {len(preserved)} keys',
                  'session_uuid': state.get('session_uuid', '')})
    try:
        with open(PRESERVE_PATH, 'w', encoding='utf-8') as f:
            json.dump(preserved, f, ensure_ascii=False)
    except Exception:
        pass


def handle_post_compact():
    """Restore session state fields that were cleared by compaction."""
    try:
        with open(PRESERVE_PATH, 'r', encoding='utf-8') as f:
            preserved = json.load(f)
    except Exception:
        return

    state = ss.read_state()
    preserved_uuid = preserved.get('session_uuid')
    stored_hash = preserved.get('pre_compact_hash', '')
    if stored_hash and _state_hash(preserved) != stored_hash:
        print('[monitor:WARN:layer4.5] Pre-compact hash mismatch — preserved state may be corrupted.')
    if not preserved_uuid:
        return
    if state.get('session_uuid') != preserved_uuid:
        critical_keys = ['layer2_unresolved_events', 'layer35_recovery_events', 'active_task_description']
        for k in critical_keys:
            if preserved.get(k):
                state[k] = preserved[k]
        ss.write_state(state)
        print('[monitor:layer4.5] UUID mismatch: re-injected critical fields from previous session.')
        return

    restored = []
    for k in PRESERVE_KEYS:
        if k in preserved and preserved[k] is not None:
            if not state.get(k):
                state[k] = preserved[k]
                restored.append(k)

    if restored:
        ss.write_state(state)
        import uuid as _uuid
        _write_event({'event_id': str(_uuid.uuid4()), 'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
                      'layer': 'layer45', 'category': 'POST_COMPACT_RESTORE', 'severity': 'info',
                      'detection_signal': f'Restored {len(restored)} fields: {", ".join(restored[:5])}',
                      'session_uuid': state.get('session_uuid', '')})
        print(f'[monitor:layer4.5] Restored {len(restored)} state fields after compaction.')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == '--pre':
        handle_pre_compact()
    elif mode == '--post':
        handle_post_compact()


if __name__ == '__main__':
    main()

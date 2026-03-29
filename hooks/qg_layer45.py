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

PRESERVE_KEYS = [
    'session_uuid', 'session_start_ts', 'active_task_id', 'active_subtask_id',
    'active_task_description', 'layer1_task_category', 'layer1_scope_files',
    'task_success_criteria', 'layer2_unresolved_events', 'layer35_recovery_events',
    'layer_env_baseline', 'layer17_verified_task_id', 'layer17_intent_text',
    'layer19_last_impact_level', 'layer19_last_impact_file',
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
    preserved['pre_compact_hash'] = _state_hash(state)
    preserved['preserved_at'] = time.time()
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
    if not preserved_uuid:
        return
    if state.get('session_uuid') != preserved_uuid:
        return  # Different session — don't restore

    restored = []
    for k in PRESERVE_KEYS:
        if k in preserved and preserved[k] is not None:
            if not state.get(k):
                state[k] = preserved[k]
                restored.append(k)

    if restored:
        ss.write_state(state)
        print(f'[monitor:layer4.5] Restored {len(restored)} state fields after compaction.')


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode == '--pre':
        handle_pre_compact()
    elif mode == '--post':
        handle_post_compact()


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Session state management for Quality Gate Monitor.
Windows-compatible: uses O_CREAT|O_EXCL atomic lockfile instead of fcntl.
"""
import json, os, time

STATE_PATH = os.path.expanduser('~/.claude/qg-session-state.json')
LOCK_PATH = STATE_PATH + '.lock'
SCHEMA_VERSION = 2
MAX_SIZE_BYTES = 1_048_576  # 1MB


def _acquire_lock(timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            fd = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(0.05)
    return False


def _release_lock():
    try:
        os.unlink(LOCK_PATH)
    except FileNotFoundError:
        pass


def _empty_state():
    return {
        'schema_version': SCHEMA_VERSION,
        'session_uuid': None,
        'session_start_ts': 0,
        'active_task_id': None,
        'active_subtask_id': None,
        'active_task_description': '',
        'task_success_criteria': [],
        'layer1_task_category': None,
        'layer1_scope_files': [],
        'layer2_unresolved_events': [],
        'layer2_elevated_scrutiny': False,
        'layer2_turn_event_count': 0,
        'layer2_turn_history': [],
        'layer15_session_reads': [],
        'layer15_override_pending': None,
        'layer15_turn_warnings': [],
        'layer15_violation_counts': {},
        'layer19_impact_cache': {},
        'layer17_verified_task_id': None,
        'layer17_intent_text': '',
        'layer17_intent_verified_ts': 0,
        'layer17_creating_new_artifacts': False,
        'layer19_last_impact_level': 'LOW',
        'layer19_last_impact_file': '',
        'layer5_subagents': {},
        'layer35_recovery_events': [],
        'layer25_syntax_failure': False,
        'layer26_convention_baseline': {},
        'layer26_files_seen': 0,
        'layer6_last_analysis_ts': 0,
        'layer3_pending_fn_alert': None,
        'layer3_last_response_claims': [],
        'layer_env_baseline': {},
        'layer_env_test_baseline': [],
        'layer8_regression_expected': False,
        'last_integrity_check_ts': 0,
        'notification_delivery': [],
        'notification_pending_criticals': [],
    }


def _is_stale(data):
    ts = data.get('session_start_ts', 0)
    if not ts:
        return False  # No start time recorded yet — not stale
    return (time.time() - ts) > 86400


def _migrate(data):
    if data.get('schema_version', 0) >= SCHEMA_VERSION:
        return data
    for k, v in _empty_state().items():
        if k not in data:
            data[k] = v
    data['schema_version'] = SCHEMA_VERSION
    return data


def _prune_turn_scoped(data):
    # Only prune space-heavy session-scoped lists. Do NOT reset turn-scoped
    # dedup fields (layer15_turn_warnings, layer2_turn_event_count) — those are
    # tiny and resetting them mid-turn would cause Layer 1.5 to re-warn on
    # already-warned rules within the same turn.
    if data.get('layer2_unresolved_events'):
        data['layer2_unresolved_events'] = data['layer2_unresolved_events'][-10:]
    if data.get('notification_delivery'):
        data['notification_delivery'] = data['notification_delivery'][-20:]
    if data.get('layer3_last_response_claims'):
        data['layer3_last_response_claims'] = data['layer3_last_response_claims'][-5:]
    return data


def read_state():
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if _is_stale(data):
            return _empty_state()
        return _migrate(data)
    except (FileNotFoundError, json.JSONDecodeError):
        return _empty_state()


def write_state(data):
    if not _acquire_lock():
        return  # Silent fail on lock contention
    try:
        data['schema_version'] = SCHEMA_VERSION
        content = json.dumps(data, ensure_ascii=False)
        if len(content.encode('utf-8')) > MAX_SIZE_BYTES:
            data = _prune_turn_scoped(data)
            content = json.dumps(data, ensure_ascii=False)
        with open(STATE_PATH, 'w', encoding='utf-8') as f:
            f.write(content)
    finally:
        _release_lock()


def update_state(**kwargs):
    data = read_state()
    data.update(kwargs)
    write_state(data)

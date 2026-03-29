#!/usr/bin/env python3
"""Layer 0 — Session Start Context Injection.
Phase 1: injects unresolved events from previous session (item 7 of spec).
Items 1-6 (cross-session pattern injection via qg-cross-session.json) are
no-ops until Phase 3 when Layer 6 is implemented.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

HISTORY_PATH = os.path.expanduser('~/.claude/qg-session-history.md')
SESSION_UUID_RE = re.compile(r'^session_uuid:\s*(\S+)', re.MULTILINE)
UNRESOLVED_RE = re.compile(r'^- UNRESOLVED:\s*(.+)', re.MULTILINE)


def find_previous_session_unresolved():
    """Find unresolved items from most recent previous session entry."""
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []

    state = ss.read_state()
    current_uuid = state.get('session_uuid')

    entries = re.split(r'(?=^## Session )', content, flags=re.MULTILINE)
    for entry in entries:
        uuids = SESSION_UUID_RE.findall(entry)
        if not uuids:
            continue
        if uuids[0] == current_uuid:
            return UNRESOLVED_RE.findall(entry)
    return []


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    # Phase 1: items 1-6 (qg-cross-session.json) are no-ops
    # Item 7: inject unresolved events from previous session
    unresolved = find_previous_session_unresolved()
    if unresolved:
        lines = ['[monitor:Layer0] Unresolved issues from previous session (highest priority):']
        for item in unresolved[:5]:
            lines.append(f'  - {item}')
        print('\n'.join(lines))

    # Reset per-session monitoring fields for the new session.
    # Called at SessionStart so old events from prior session don't leak in.
    ss.update_state(
        session_uuid=None,
        session_start_ts=0,
        active_task_id=None,
        active_subtask_id=None,
        active_task_description='',
        task_success_criteria=[],
        layer1_task_category=None,
        layer1_scope_files=[],
        layer2_unresolved_events=[],
        layer2_elevated_scrutiny=False,
        layer2_turn_event_count=0,
        layer2_turn_history=[],
        layer15_session_reads=[],
        layer15_turn_warnings=[],
        layer15_violation_counts={},
        layer3_pending_fn_alert=None,
        layer3_last_response_claims=[],
        layer35_recovery_events=[],
        layer25_syntax_failure=False,
        layer15_override_pending=None,
        notification_delivery=[],
        notification_pending_criticals=[],
    )

if __name__ == '__main__':
    main()

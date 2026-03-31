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
CROSS_SESSION_PATH = os.path.expanduser('~/.claude/qg-cross-session.json')
RULES_PATH = os.path.expanduser('~/.claude/qg-rules.json')
RECOVERY_PENDING_PATH = os.path.expanduser('~/.claude/qg-recovery-pending.json')


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


def load_cross_session_patterns():
    """Read cross-session patterns from Layer 6 output."""
    if not os.path.exists(CROSS_SESSION_PATH):
        return []
    try:
        with open(CROSS_SESSION_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('patterns', [])
    except Exception:
        return []




def load_recovery_pending():
    """Read and consume unresolved recovery events from previous session."""
    if not os.path.exists(RECOVERY_PENDING_PATH):
        return []
    try:
        with open(RECOVERY_PENDING_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if data.get('consumed', True):
            return []
        events = data.get('events', [])
        data['consumed'] = True
        with open(RECOVERY_PENDING_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return events
    except Exception:
        return []
def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    # Items 1-6: inject cross-session patterns from qg-cross-session.json
    patterns = load_cross_session_patterns()
    if patterns:
        try:
            with open(RULES_PATH, 'r', encoding='utf-8') as f:
                max_chars = json.load(f).get('layer0', {}).get('injection_max_chars', 2000)
        except Exception:
            max_chars = 2000
        lines_out = ['[monitor:Layer0] Cross-session patterns detected:']
        char_count = len(lines_out[0])
        for p in patterns[:10]:
            desc = "{} ({} sessions, {} events)".format(
                p.get('category', '?'), p.get('sessions_count', 0), p.get('total_events', 0))
            line = '  - ' + desc
            if char_count + len(line) > max_chars:
                break
            lines_out.append(line)
            char_count += len(line)
        if len(lines_out) > 1:
            print('\n'.join(lines_out))
        ss.update_state(layer0_injected_patterns=[p.get('category', '')[:100] for p in patterns[:10]])

    # Item 7: inject unresolved events from previous session
    unresolved = find_previous_session_unresolved()
    if unresolved:
        lines = ['[monitor:Layer0] Unresolved issues from previous session (highest priority):']
        for item in unresolved[:5]:
            lines.append('  - ' + item)
        print('\n'.join(lines))

    # Item 8: inject unresolved recovery events from previous session
    recovery_pending = load_recovery_pending()
    if recovery_pending:
        rec_lines = ['[monitor:Layer0] Unresolved recovery attempts from previous session:']
        for evt in recovery_pending[:5]:
            rec_lines.append('  - [{}] {}'.format(evt.get('status', '?'), evt.get('event_type', '?')))
        print(chr(10).join(rec_lines))

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
        layer17_verified_task_id=None,
        layer17_intent_text='',
        layer17_intent_verified_ts=0,
        layer17_creating_new_artifacts=False,
        layer19_last_impact_level='LOW',
        layer19_last_impact_file='',
        layer19_impact_cache={},
        layer20_last_health_ts=0,
        layer5_subagents={},
    )

if __name__ == '__main__':
    main()

def cmd_monitor():
    """qg monitor — unified quality gate dashboard."""
    import json, os
    from collections import Counter

    CLAUDE_DIR = os.path.expanduser('~/.claude')
    monitor_path = f'{CLAUDE_DIR}/qg-monitor.jsonl'
    history_path = f'{CLAUDE_DIR}/qg-session-history.md'
    state_path = f'{CLAUDE_DIR}/qg-session-state.json'

    print('=== Quality Gate Monitor Dashboard ===')
    print()

    session_uuid = None
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        session_uuid = state.get('session_uuid')
        print(f"Session:  {session_uuid or '(none)'}")
        print(f"Task:     {state.get('active_task_description', '')[:70] or '(none)'}")
        print(f"Category: {state.get('layer1_task_category', 'UNKNOWN')}")
        l2_open = [e for e in state.get('layer2_unresolved_events', []) if e.get('status') == 'open']
        print(f"L2 open:  {len(l2_open)} unresolved")
        if l2_open:
            for cat, cnt in Counter(e['category'] for e in l2_open).most_common():
                print(f"          {cat}: {cnt}")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Session state: not available")
    print()

    all_events, sess_events = [], []
    try:
        with open(monitor_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get('layer') == 'layer3':
                        all_events.append(e)
                        if session_uuid and e.get('session_uuid') == session_uuid:
                            sess_events.append(e)
                except Exception:
                    pass
    except FileNotFoundError:
        pass

    def _stats(evts, label):
        tp = sum(1 for e in evts if e.get('verdict') == 'TP')
        fp = sum(1 for e in evts if e.get('verdict') == 'FP')
        fn = sum(1 for e in evts if e.get('verdict') == 'FN')
        tn = sum(1 for e in evts if e.get('verdict') == 'TN')
        print(f"{label}: TP={tp} FP={fp} FN={fn} TN={tn} (total={len(evts)})")

    _stats(sess_events, 'Session ')
    _stats(all_events,  'All-time')
    print()

    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            history = f.read()
        entries = [e for e in history.split('## Session') if e.strip()]
        if entries:
            print('--- Most Recent Session Summary ---')
            print('## Session' + entries[0][:500].rstrip())
    except FileNotFoundError:
        print('No session history yet.')

    print()
    print('Commands: qg analyze | qg integrity | qg rules')


def cmd_analyze():
    """qg analyze — trigger cross-session analysis (Phase 3 feature)."""
    print('Layer 6 cross-session analysis: Phase 3 feature. Not yet available.')
    print('Layer 9 confidence calibration: Phase 3 feature. Not yet available.')
    print('Use qg monitor to view current session stats.')


def cmd_integrity():
    """qg integrity — audit trail integrity check."""
    import json, os
    path = os.path.expanduser('~/.claude/qg-monitor.jsonl')
    if not os.path.exists(path):
        print('qg-monitor.jsonl not found — no events logged yet.')
        return
    total = bad = 0
    seen_ids = set()
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            total += 1
            try:
                e = json.loads(line)
                eid = e.get('event_id', '')
                if eid in seen_ids:
                    print(f'  Line {i}: duplicate event_id {eid!r}')
                    bad += 1
                seen_ids.add(eid)
            except json.JSONDecodeError:
                print(f'  Line {i}: invalid JSON')
                bad += 1
    print(f'Audit trail: {total} lines, {bad} issue(s).')
    print('Integrity: OK' if bad == 0 else 'Integrity: ISSUES FOUND')


def cmd_rules():
    """qg rules — view pending rule suggestions (Layer 7 preview)."""
    import os
    path = os.path.expanduser('~/.claude/qg-rule-suggestions.md')
    if not os.path.exists(path):
        print('No pending rule suggestions. (Layer 7 is a Phase 3 feature.)')
        return
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())


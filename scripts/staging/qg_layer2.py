#!/usr/bin/env python3
"""Layer 2 — Mid-task Monitoring (PostToolUse).
Detects 8 quality violation categories from observable tool patterns.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
BASH_TOOL_RE = re.compile(r'\b(grep|cat|find|head|tail)\b')
ERROR_RE = re.compile(
    r'(error|exception|traceback|failed|exit code [1-9]|errno|not found|permission denied)',
    re.IGNORECASE)


def _write_event(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


def detect_loop(tool_name, target, history, threshold=3):
    """history: list of (tool_name, target) tuples."""
    count = sum(1 for t, tgt in history if t == tool_name and tgt == target)
    if count >= threshold:
        return {'category': 'LOOP_DETECTED', 'severity': 'critical',
                'detection_signal': f'{tool_name} on {target!r} called {count} times'}
    return None


def detect_all_events(tool_name, tool_input, tool_response, state, prev_calls):
    """Return list of violation event dicts for this tool call."""
    events = []
    reads = state.get('layer15_session_reads', [])
    scope = state.get('layer1_scope_files', [])
    fp = (tool_input or {}).get('file_path', '')
    cmd = (tool_input or {}).get('command', '')

    # LAZINESS: Edit without prior Read
    if tool_name == 'Edit' and fp and fp not in reads:
        events.append({'category': 'LAZINESS', 'severity': 'warning',
                       'detection_signal': f'Edit on {fp!r} without prior Read'})

    # INCORRECT_TOOL: Bash instead of dedicated tool
    if tool_name == 'Bash' and BASH_TOOL_RE.search(cmd):
        events.append({'category': 'INCORRECT_TOOL', 'severity': 'info',
                       'detection_signal': f'Use Grep/Read/Glob instead: {cmd[:60]!r}'})

    # ERROR_IGNORED: prior call had error, current non-read tool fires anyway
    if tool_name not in ('Read', 'Glob', 'Grep'):
        for prev in prev_calls[-3:]:
            if ERROR_RE.search(prev.get('response', '')):
                events.append({'category': 'ERROR_IGNORED', 'severity': 'critical',
                               'detection_signal': 'Error in prior tool output ignored'})
                break

    # SCOPE_CREEP: Write/Edit outside layer1_scope_files
    if tool_name in ('Write', 'Edit') and fp and scope:
        if not any(fp.endswith(s) or s in fp for s in scope):
            events.append({'category': 'SCOPE_CREEP', 'severity': 'warning',
                           'detection_signal': f'{fp!r} outside task scope'})

    return events


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {})
    tool_response = str(payload.get('tool_response', ''))

    state = ss.read_state()

    try:
        with open(os.path.expanduser('~/.claude/qg-rules.json'), 'r', encoding='utf-8') as f:
            l2_rules = json.load(f).get('layer2', {})
    except Exception:
        l2_rules = {}

    loop_threshold = l2_rules.get('loop_same_tool_count', 3)
    events_limit = l2_rules.get('events_per_turn_limit', 5)

    turn_history = state.get('layer2_turn_history', [])
    target_key = (tool_input or {}).get('file_path', '') or str((tool_input or {}).get('command', ''))[:30]
    prev_calls = [{'tool': e['tool'], 'response': e.get('resp', '')} for e in turn_history[-3:]]

    events = detect_all_events(tool_name, tool_input, tool_response, state, prev_calls)

    # Loop detection
    history_tuples = [(e['tool'], e['target']) for e in turn_history]
    loop_evt = detect_loop(tool_name, target_key, history_tuples, threshold=loop_threshold)
    if loop_evt:
        events.append(loop_evt)

    # Rate limiting
    turn_count = state.get('layer2_turn_event_count', 0)
    events = events[:max(0, events_limit - turn_count)]

    # Elevated scrutiny
    if sum(1 for e in events if e.get('severity') == 'critical') >= 3:
        state['layer2_elevated_scrutiny'] = True

    state['layer2_turn_event_count'] = turn_count + len(events)
    turn_history.append({'tool': tool_name, 'target': target_key,
                         'resp': tool_response[:200]})
    state['layer2_turn_history'] = turn_history[-20:]

    ts = time.strftime('%Y-%m-%dT%H:%M:%S')
    wd = os.getcwd()
    unresolved = state.get('layer2_unresolved_events', [])

    for evt in events:
        record = {
            'event_id': str(uuid.uuid4()),
            'ts': ts,
            'session_uuid': state.get('session_uuid', ''),
            'working_dir': wd,
            'task_id': state.get('active_task_id', ''),
            'layer': 'layer2',
            'status': 'open',
            **evt,
        }
        _write_event(record)
        unresolved.append(record)

    state['layer2_unresolved_events'] = unresolved[-50:]
    ss.write_state(state)


if __name__ == '__main__':
    main()

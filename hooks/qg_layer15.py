#!/usr/bin/env python3
"""Layer 1.5 — PreToolUse Rule Validation.
Warns or blocks based on rules in qg-rules.json.
Flushes queued CRITICALs from Stop/async contexts at entry.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss
import qg_notification_router as router

RULES_PATH = os.path.expanduser('~/.claude/qg-rules.json')

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _norm_path(p):
    """Normalize path for comparison."""
    return os.path.normpath(p).replace('\\', '/') if p else ''

BASH_TOOL_RE = re.compile(r'\b(grep|cat|find|head|tail|sed|awk)\b')


def _load_rules():
    try:
        with open(RULES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('layer15', {})
    except Exception:
        return {}


def evaluate_rules(tool_name, tool_input, state):
    """Returns first matching rule violation dict or None."""
    reads = [_norm_path(r) for r in state.get('layer15_session_reads', [])]
    fp = _norm_path(tool_input.get('file_path', '') if isinstance(tool_input, dict) else '')
    cmd = tool_input.get('command', '') if isinstance(tool_input, dict) else ''

    if tool_name == 'Edit' and fp and fp not in reads:
        return {'rule_id': 'edit-without-read', 'action': 'warn',
                'message': f'Editing {fp!r} without a prior Read this session.'}

    if tool_name == 'Bash' and BASH_TOOL_RE.search(cmd):
        return {'rule_id': 'bash-instead-of-tool', 'action': 'info',
                'message': 'Use Grep/Read/Glob tools instead of Bash for file operations.'}

    if tool_name in ('Write', 'Edit') and fp:
        scope = state.get('layer1_scope_files', [])
        if scope and not any(fp.endswith(s) or s in fp for s in scope):
            return {'rule_id': 'write-outside-scope', 'action': 'warn',
                    'message': f'{fp!r} is outside task scope.'}

    return None


def handle_read_tracking(tool_name, tool_input):
    if tool_name == 'Read':
        fp = _norm_path((tool_input or {}).get('file_path', ''))
        if fp:
            state = ss.read_state()
            reads = state.get('layer15_session_reads', [])
            if fp not in reads:
                reads.append(fp)
                state['layer15_session_reads'] = reads
                ss.write_state(state)


def main():
    router.reset_turn_counter()

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {})

    # Always track reads first — before any early return — so a Read tool call
    # that coincides with a critical flush still registers in layer15_session_reads.
    handle_read_tracking(tool_name, tool_input)

    # Behavior 0: flush queued CRITICALs from Stop/async contexts
    pending = router.flush_pending_criticals()
    if pending:
        print(json.dumps({'additionalContext': pending}))
        return

    state = ss.read_state()

    # Check override token
    override = state.get('layer15_override_pending')
    if override:
        hit = evaluate_rules(tool_name, tool_input, state)
        if hit and hit['rule_id'] == override.get('rule_id'):
            state['layer15_override_pending'] = None
            ss.write_state(state)
            return  # Override consumed — skip block

    result = evaluate_rules(tool_name, tool_input, state)
    if result is None:
        return

    rule_id = result['rule_id']

    # Dedup within turn
    turn_warnings = state.get('layer15_turn_warnings', [])
    if rule_id in turn_warnings:
        return
    turn_warnings.append(rule_id)
    state['layer15_turn_warnings'] = turn_warnings

    # Track repeat violations
    counts = state.get('layer15_violation_counts', {})
    counts[rule_id] = counts.get(rule_id, 0) + 1
    state['layer15_violation_counts'] = counts
    ss.write_state(state)

    rules_cfg = _load_rules()
    threshold = rules_cfg.get('repeat_violation_threshold', 3)
    if counts[rule_id] >= threshold:
        router.notify('CRITICAL', 'layer15', rule_id, None,
                      f'Rule {rule_id!r} violated {counts[rule_id]}x this session.', 'pretooluse')

    import time as _t, uuid as _uuid
    _write_event({'event_id': str(_uuid.uuid4()), 'ts': _t.strftime('%Y-%m-%dT%H:%M:%S'),
                  'layer': 'layer15', 'category': result['rule_id'], 'severity': result['action'],
                  'detection_signal': result['message'][:200],
                  'session_uuid': state.get('session_uuid', '')})
    action = result['action']
    impact_level = state.get('layer19_last_impact_level', 'LOW')
    if impact_level in ('HIGH', 'CRITICAL') and action == 'warn':
        action = 'block'
    # Gap 15: track warnings issued (not blocked) for Layer 3 confidence scoring
    if action == 'warn':
        state['layer15_warnings_ignored_count'] = state.get('layer15_warnings_ignored_count', 0) + 1
        ss.write_state(state)
    message = result['message']
    if action == 'info':
        print(json.dumps({'additionalContext': f'[monitor:INFO:layer1.5] {message}'}))
    elif action == 'warn':
        print(json.dumps({'additionalContext': f'[monitor:WARN:layer1.5] {message}'}))
    elif action == 'block':
        print(json.dumps({'decision': 'block', 'reason': f'[layer1.5] {message}'}))


if __name__ == '__main__':
    main()

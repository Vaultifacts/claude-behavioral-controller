#!/usr/bin/env python3
"""Layer 3.5 -- Recovery Tracking + Haiku FN Classifier.
Imported by quality-gate.py for use in _layer3_run and _layer4_checkpoint.
"""
import re, sys, os, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

_L35_WINDOW_TURNS = 3
_L35_WINDOW_SEC = 1800  # 30 minutes

_LAZINESS_TEXT_RE = re.compile(
    r'\b(done|completed?|fixed|all (?:tests?|checks?) pass|verified|confirmed|finished)\b',
    re.IGNORECASE)
_VERIFY_OUTPUT_RE = re.compile(
    r'(===|---|\d+ passed|\d+ failed|exit code \d|>>|\$\s)')

_VERIFY_TOOLS = frozenset({'Read', 'Grep', 'Bash', 'Glob'})


def layer35_create_recovery_event(verdict, fn_signals, state, tool_names):
    if verdict not in ('FN', 'TP'):
        return
    events = state.get('layer35_recovery_events', [])
    event = {
        'event_id': str(uuid.uuid4())[:8],
        'verdict': verdict,
        'category': fn_signals[0] if fn_signals else 'unverified',
        'task_id': state.get('active_task_id', ''),
        'session_uuid': state.get('session_uuid', ''),
        'ts': time.time(),
        'turn': len(state.get('layer2_turn_history', [])),
        'status': 'open',
        'tools_at_flag': list(tool_names or [])[:5],
    }
    events.append(event)
    state['layer35_recovery_events'] = events[-20:]


def layer35_check_resolutions(tool_names, state):
    events = state.get('layer35_recovery_events', [])
    now = time.time()
    current_turn = len(state.get('layer2_turn_history', []))
    has_verify = bool(set(tool_names or []) & _VERIFY_TOOLS)

    for evt in events:
        if evt.get('status') != 'open':
            continue
        if now - evt.get('ts', 0) > _L35_WINDOW_SEC:
            evt['status'] = 'timed_out'
            continue
        turns_elapsed = current_turn - evt.get('turn', 0)
        if turns_elapsed > _L35_WINDOW_TURNS:
            evt['status'] = 'timed_out'
            continue
        if has_verify and turns_elapsed > 0:
            evt['status'] = 'resolved'

    state['layer35_recovery_events'] = events


def _detect_fn_signals_rules(response, state):
    signals = []
    if response and _LAZINESS_TEXT_RE.search(response):
        if not _VERIFY_OUTPUT_RE.search(response):
            signals.append('claimed completion without verification output')
    prev_claims = state.get('layer3_last_response_claims', [])
    for claim in prev_claims:
        if claim and len(claim) > 10 and claim.lower() in (response or '').lower():
            signals.append(f'repeated unverified claim: {claim[:60]}')
            break
    return signals


def detect_fn_signals(response, tool_names, user_request, state, use_haiku=True):
    rule_signals = _detect_fn_signals_rules(response, state)

    if not use_haiku:
        return rule_signals

    try:
        from _hooks_shared import call_haiku_check, load_api_key
        if not load_api_key():
            return rule_signals

        tools_str = ', '.join((tool_names or [])[:5]) or 'none'
        check_prompt = (
            'You are checking whether an AI assistant response is a missed quality failure.\n\n'
            'TOOLS USED: ' + tools_str + '\n'
            'USER REQUEST: ' + (user_request or '')[:200] + '\n\n'
            'ASSISTANT RESPONSE:\n' + (response or '')[:3000] + '\n\n'
            'Check ONLY for these FN signals:\n'
            '1. Claims outcomes (tests pass, task done, bug fixed) WITHOUT quoting tool output inline\n'
            '2. Skips verification this task clearly required\n\n'
            'If no FN signals: {"ok": true}\n'
            'If FN detected: {"ok": false, "reason": "haiku:fn:<brief reason>"}\n'
            'Respond with EXACTLY one line of JSON.'
        )
        ok, reason, genuine = call_haiku_check(check_prompt)
        if genuine and not ok and reason:
            return [reason]
        return rule_signals
    except Exception:
        return rule_signals


def layer35_unresolved_lines(state):
    lines = []
    for evt in state.get('layer35_recovery_events', []):
        if evt.get('status') == 'open':
            reason = evt.get('category', 'unknown')
            task = evt.get('task_id', '')
            lines.append(f'- UNRESOLVED: FN -- {reason} (task: {task})')
    return lines

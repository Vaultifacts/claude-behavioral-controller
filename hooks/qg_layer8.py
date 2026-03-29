#!/usr/bin/env python3
"""Layer 8 -- Regression Detection (PostToolUse on Bash test commands).
Compares test results to session baseline; alerts on regression.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')
TEST_CMD_RE = re.compile(
    r'\b(pytest|npm\s+test|jest|go\s+test|python\s+-m\s+pytest|yarn\s+test|cargo\s+test)\b',
    re.IGNORECASE)
PASS_RE = re.compile(r'(\d+)\s+pass(?:ed)?', re.IGNORECASE)
FAIL_RE = re.compile(r'(\d+)\s+fail(?:ed)?', re.IGNORECASE)


def _write_event(event):
    try:
        with open(MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


def parse_results(output):
    pm = PASS_RE.search(output)
    fm = FAIL_RE.search(output)
    return (int(pm.group(1)) if pm else None, int(fm.group(1)) if fm else None)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    if payload.get('tool_name') != 'Bash':
        return

    cmd = (payload.get('tool_input') or {}).get('command', '')
    if not TEST_CMD_RE.search(cmd):
        return

    response = str(payload.get('tool_response', ''))
    passed, failed = parse_results(response)
    if passed is None and failed is None:
        return

    state = ss.read_state()
    baseline = state.get('layer_env_test_baseline', [])

    if not baseline:
        state['layer_env_test_baseline'] = [[passed or 0, failed or 0]]
        state['layer8_regression_expected'] = False
        ss.write_state(state)
        return

    baseline_failed = baseline[0][1]
    current_failed = failed or 0

    if current_failed > baseline_failed:
        regression_count = current_failed - baseline_failed
        event = {
            'event_id': str(uuid.uuid4()),
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'session_uuid': state.get('session_uuid') or '',
            'working_dir': os.getcwd(),
            'task_id': state.get('active_task_id', ''),
            'layer': 'layer8',
            'category': 'REGRESSION',
            'severity': 'critical',
            'detection_signal': '{} new failure(s): was {} failed, now {}'.format(
                regression_count, baseline_failed, current_failed),
            'status': 'open',
        }
        _write_event(event)
        unresolved = state.get('layer2_unresolved_events', [])
        unresolved.append(event)
        state['layer2_unresolved_events'] = unresolved[-50:]
        state['layer8_regression_expected'] = False
        ss.write_state(state)

        out = {'hookSpecificOutput': {'hookEventName': 'PostToolUse',
            'additionalContext': '[Layer 8] REGRESSION: {} new failure(s) vs baseline.'.format(regression_count)}}
        print(json.dumps(out))
    else:
        state["layer8_regression_expected"] = False
        ss.write_state(state)


if __name__ == '__main__':
    main()

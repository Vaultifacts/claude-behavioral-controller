#!/usr/bin/env python3
"""Layer 7 -- Feedback and Rule Refinement (Stop hook + qg rules).
Generates rule suggestions from repeat FN patterns and cross-session data.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

FEEDBACK_PATH = os.path.expanduser('~/.claude/quality-gate-feedback.jsonl')
CROSS_SESSION_PATH = os.path.expanduser('~/.claude/qg-cross-session.json')
SUGGESTIONS_PATH = os.path.expanduser('~/.claude/qg-rule-suggestions.md')

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass



def load_feedback(feedback_path=None):
    path = feedback_path or FEEDBACK_PATH
    records = []
    if not os.path.exists(path):
        return records
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def find_repeat_fns(records, threshold=3):
    fn_categories = {}
    for r in records:
        if r.get('outcome') == 'FN':
            cat = r.get('category', 'UNKNOWN')
            fn_categories.setdefault(cat, []).append(r)
    return {cat: recs for cat, recs in fn_categories.items() if len(recs) >= threshold}


def generate_suggestions(feedback_path=None, cross_session_path=None):
    records = load_feedback(feedback_path)
    repeat_fns = find_repeat_fns(records)
    suggestions = []
    for cat, recs in repeat_fns.items():
        suggestions.append({
            'id': len(suggestions) + 1,
            'category': cat,
            'reason': 'Repeated FN ({} times) -- rule may be missing this pattern.'.format(len(recs)),
            'supporting_count': len(recs),
            'status': 'pending',
            'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        })
    try:
        cs_path = cross_session_path or CROSS_SESSION_PATH
        if os.path.exists(cs_path):
            with open(cs_path, 'r', encoding='utf-8') as f:
                cs = json.load(f)
            for pattern in cs.get('patterns', []):
                cat = pattern['category']
                if cat not in repeat_fns:
                    suggestions.append({
                        'id': len(suggestions) + 1,
                        'category': cat,
                        'reason': 'Cross-session pattern: {sessions_count} sessions, {pct:.0f}% of events'.format(
                            sessions_count=pattern['sessions_count'],
                            pct=pattern['event_pct'] * 100),
                        'supporting_count': pattern['total_events'],
                        'status': 'pending',
                        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
                    })
    except Exception:
        pass
    return suggestions


def write_suggestions(suggestions, output_path=None):
    path = output_path or SUGGESTIONS_PATH
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    lines = ['# QG Rule Suggestions\n', '_Generated: {}_\n\n'.format(ts)]
    if not suggestions:
        lines.append('No pending suggestions.\n')
    else:
        for s in suggestions:
            lines.append('## [{}] #{}: {}\n'.format(s['status'].upper(), s['id'], s['category']))
            lines.append('- **Reason:** {}\n'.format(s['reason']))
            lines.append('- **Supporting events:** {}\n'.format(s['supporting_count']))
            lines.append('- **Generated:** {}\n\n'.format(s['ts']))
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def main():
    try:
        json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        pass
    state = ss.read_state()
    if not state.get('layer3_pending_fn_alert'):
        return
    try:
        suggestions = generate_suggestions()
        if suggestions:
            import time as _t, uuid as _uuid
            _write_event({'event_id': str(_uuid.uuid4()), 'ts': _t.strftime('%Y-%m-%dT%H:%M:%S'),
                          'layer': 'layer7', 'category': 'RULE_SUGGESTION', 'severity': 'info',
                          'detection_signal': f'{len(suggestions)} suggestion(s) generated'})
            write_suggestions(suggestions)
    except Exception:
        pass


if __name__ == '__main__':  # pragma: no cover
    if len(sys.argv) > 1 and sys.argv[1] == '--run':
        suggestions = generate_suggestions()
        write_suggestions(suggestions)
        print('Generated {} suggestion(s).'.format(len(suggestions)))
    else:
        main()

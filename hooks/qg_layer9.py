#!/usr/bin/env python3
"""Layer 9 -- Confidence Calibration (Stop hook).
Extracts stated certainty from response text; records vs Layer 3 outcome.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

CALIBRATION_PATH = os.path.expanduser('~/.claude/qg-calibration.jsonl')

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass

HIGH_RE = re.compile(
    r"\b(I'?m certain|definitely|I know|this will work|guaranteed|100%|confirmed)\b",
    re.IGNORECASE)
MED_RE = re.compile(
    r'\b(I believe|should work|likely|I expect|I think this will)\b',
    re.IGNORECASE)
LOW_RE = re.compile(r'\b(might|possibly|I think|perhaps|not sure)\b', re.IGNORECASE)


def extract_certainty(text):
    if HIGH_RE.search(text):
        return 'high'
    if MED_RE.search(text):
        return 'medium'
    if LOW_RE.search(text):
        return 'low'
    return None


def get_response_text(transcript_path):
    if not transcript_path or not os.path.exists(transcript_path):
        return ''
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        for line in reversed(lines[-100:]):
            try:
                d = json.loads(line)
                msg = d.get('message', {})
                if msg.get('role') == 'assistant':
                    content = msg.get('content', '')
                    if isinstance(content, list):
                        return ' '.join(c.get('text', '') for c in content if c.get('type') == 'text')
                    return str(content)
            except Exception:
                pass
    except Exception:
        pass
    return ''


def main():
    try:
        data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        data = {}

    transcript_path = data.get('transcript_path', '')
    response_text = get_response_text(transcript_path)
    certainty = extract_certainty(response_text)
    if not certainty:
        return

    state = ss.read_state()
    # Threshold gate: require >=N responses before calibrating
    try:
        with open(os.path.expanduser('~/.claude/qg-rules.json'), 'r', encoding='utf-8') as f:
            threshold = json.load(f).get('layer9', {}).get('min_responses_before_recalibration', 5)
    except Exception:
        threshold = 5
    eval_count = state.get('layer3_evaluation_count', 0)
    if eval_count < threshold:
        return
    actual_outcome = 'FN' if state.get('layer3_pending_fn_alert') else 'TN'
    record = {
        'event_id': str(uuid.uuid4()),
        'ts': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'session_uuid': state.get('session_uuid') or '',
        'stated_certainty': certainty,
        'actual_outcome': actual_outcome,
        'task_complexity': state.get('layer1_task_category', 'unknown'),
    }
    try:
        with open(CALIBRATION_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + chr(10))
    except Exception:
        pass
    _write_event({'event_id': record.get('event_id', ''), 'ts': record.get('ts', ''),
                  'layer': 'layer9', 'category': 'CALIBRATION',
                  'severity': 'info', 'detection_signal': f'certainty={certainty} outcome={actual_outcome}',
                  'session_uuid': record.get('session_uuid', '')})


if __name__ == '__main__':  # pragma: no cover
    main()

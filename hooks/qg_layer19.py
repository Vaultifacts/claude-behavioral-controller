#!/usr/bin/env python3
"""Layer 1.9 — Change Impact Analysis (PreToolUse on Edit/Write).
Counts dependents of the target file and stores impact level in session state.
"""
import json, os, re, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

RULES_PATH = os.path.expanduser('~/.claude/qg-rules.json')

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


CORE_PATTERNS = re.compile(
    r'(utils?|shared|common|base|core|config|settings|constants?|helpers?)\.(py|js|ts)$',
    re.IGNORECASE)


def _load_thresholds():
    try:
        with open(RULES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('layer19', {})
    except Exception:
        return {}


def count_dependents(file_path, working_dir):
    """Grep for imports of file_path. Returns list of dependent paths."""
    if not file_path:
        return []
    stem = os.path.splitext(os.path.basename(file_path))[0]
    if not stem:
        return []
    patterns = [rf'import.*{stem}', rf'from.*{stem}.*import', rf'require.*{stem}']
    dependents = set()
    for pat in patterns:
        try:
            result = subprocess.run(
                ['grep', '-rl', '--include=*.py', '--include=*.js', '--include=*.ts',
                 pat, working_dir],
                capture_output=True, text=True, timeout=3)
            for line in result.stdout.strip().splitlines():
                fp = line.strip()
                if fp and os.path.normpath(fp) != os.path.normpath(file_path):
                    dependents.add(fp)
        except subprocess.TimeoutExpired:
            break  # Stop scanning on timeout; result is partial
        except Exception:
            pass
    return list(dependents)


def compute_impact_level(file_path, dependents, cfg):
    """Return LOW / MEDIUM / HIGH / CRITICAL."""
    if CORE_PATTERNS.search(os.path.basename(file_path or '')):
        return 'CRITICAL'
    n = len(dependents)
    low_thresh = cfg.get('low_threshold', 5)
    med_thresh = cfg.get('medium_threshold', 20)
    if n < low_thresh:
        return 'LOW'
    if n < med_thresh:
        return 'MEDIUM'
    return 'HIGH'


def analyze_impact(file_path):
    """Full impact analysis with per-session 1-hour cache. Returns result dict."""
    state = ss.read_state()
    cache = state.get('layer19_impact_cache', {})

    if file_path in cache:
        cached = cache[file_path]
        if time.time() - cached.get('ts', 0) < 3600:
            return cached

    cfg = _load_thresholds()
    dependents = count_dependents(file_path, os.getcwd())
    level = compute_impact_level(file_path, dependents, cfg)

    result = {
        'file': file_path,
        'level': level,
        'dependent_count': len(dependents),
        'dependents_sample': dependents[:5],
        'ts': time.time(),
    }

    cache[file_path] = result
    state['layer19_impact_cache'] = cache
    state['layer19_last_impact_level'] = level
    state['layer19_last_impact_file'] = file_path
    if level in ('HIGH', 'CRITICAL'):
        state['layer8_regression_expected'] = True
    ss.write_state(state)
    return result


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {}) or {}

    if tool_name not in ('Edit', 'Write'):
        return

    file_path = tool_input.get('file_path', '')
    if not file_path:
        return

    result = analyze_impact(file_path)
    level = result['level']
    import time as _t, uuid as _uuid
    _write_event({'event_id': str(_uuid.uuid4()), 'ts': _t.strftime('%Y-%m-%dT%H:%M:%S'),
                  'layer': 'layer19', 'category': 'IMPACT_ASSESSED', 'severity': level.lower(),
                  'detection_signal': f'{os.path.basename(file_path)}: {level} ({result["dependent_count"]} deps)',
                  'file_path': file_path})

    if level in ('HIGH', 'CRITICAL'):
        n = result['dependent_count']
        msg = (f'[monitor:INFO:layer1.9] Impact: {level} — '
               f'{os.path.basename(file_path)!r} has {n} dependent(s). '
               f'Consider verifying downstream effects before proceeding.')
        print(json.dumps({'additionalContext': msg}))


if __name__ == '__main__':  # pragma: no cover
    main()

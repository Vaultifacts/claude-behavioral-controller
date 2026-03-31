#!/usr/bin/env python3
"""Layer 1.8 — Hallucination Detection (PreToolUse on Edit).
Checks: (1) file path exists before Edit; (2) referenced function exists in file.
Write tool is exempt (creates new files by design).
"""
import importlib.util, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

RULES_PATH = os.path.expanduser("~/.claude/qg-rules.json")

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass

_REMOTE_URL_RE = re.compile(r'https?://', re.IGNORECASE)


def find_remote_refs(text):
    """Return URL literals found in text."""
    if not text:
        return []
    return re.findall(r'https?://\S+', text, re.IGNORECASE)


def check_path_exists(file_path):
    """Return True if file exists on disk."""
    try:
        return os.path.isfile(file_path)
    except Exception:
        return True  # On error, don't false-positive


def check_function_in_file(file_path, old_string):
    """Return True if referenced def/class from old_string exists in file."""
    if not old_string or not file_path:
        return True
    # (?:^|\s) instead of : avoids potential heredoc byte-corruption on some write paths.
    # Known gap: misses def/class preceded by punctuation e.g. '(class Foo' — acceptable for this monitor layer.
    names = re.findall(r'(?:^|\s)def\s+(\w+)|(?:^|\s)class\s+(\w+)', old_string)
    if not names:
        return True
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        for def_name, class_name in names:
            name = def_name or class_name
            if name and name not in content:
                return False
        return True
    except Exception:
        return True  # On read error, don't false-positive


def check_imports_in_file(file_path, old_string):
    """Return True if imported modules in old_string appear in file."""
    if not old_string or not file_path:
        return True
    names = re.findall(r'^\s*import\s+([\w.]+)', old_string, re.MULTILINE)
    names += re.findall(r'^\s*from\s+([\w.]+)\s+import', old_string, re.MULTILINE)
    names = list({n.split('.')[0] for n in names if n})
    if not names:
        return True
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        for name in names:
            if name not in content:
                return False
        return True
    except Exception:
        return True


def check_packages_importable(old_string):
    """Return list of top-level import names from old_string not found by find_spec."""
    if not old_string:
        return []
    names = re.findall(r'^\s*import\s+([\w.]+)', old_string, re.MULTILINE)
    names += re.findall(r'^\s*from\s+([\w.]+)\s+import', old_string, re.MULTILINE)
    top_names = list({n.split('.')[0] for n in names if n})
    missing = []
    for name in top_names:
        try:
            if importlib.util.find_spec(name) is None:
                missing.append(name)
        except (ModuleNotFoundError, ValueError):
            missing.append(name)
    return missing


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {}) or {}

    # Write always creates/overwrites — no existence check needed
    if tool_name == 'Write':
        return

    if tool_name != 'Edit':
        return

    file_path = tool_input.get('file_path', '')
    if not file_path:
        return

    state = ss.read_state()
    _warned = False

    try:
        with open(RULES_PATH, 'r', encoding='utf-8') as _f:
            _cfg = json.load(_f).get('layer18', {})
    except Exception:
        _cfg = {}
    _suppress_artifacts = _cfg.get('suppress_on_creating_artifacts', True)
    _check_fn_existence = _cfg.get('check_function_existence', True)

    # Suppress if Layer 1.7 confirmed creating new artifacts in this scope
    if _suppress_artifacts and state.get('layer17_creating_new_artifacts'):
        return

    if not check_path_exists(file_path):
        state['layer18_hallucination_warned'] = True
        ss.write_state(state)
        print(json.dumps({
            'additionalContext': (
                f'[monitor:WARN:layer1.8] Path does not exist: {file_path!r}. '
                f'Use Glob to find the correct path, or Write to create a new file.'
            )
        }))
        return

    old_string = tool_input.get('old_string', '')
    if not old_string:
        return

    # Gap #34: warn if imports in old_string don't exist in file
    _check_imports = _cfg.get('check_import_existence', True)
    if _check_imports and not check_imports_in_file(file_path, old_string):
        _warned = True
        print(json.dumps({
            'additionalContext': (
                f'[monitor:WARN:layer1.8] Import in old_string may not exist in '
                f'{os.path.basename(file_path)!r}. '
                'Read the file first to confirm exact imports.'
            )
        }))

    # Gap #34 (pkg): warn if imports in old_string are not installed
    _check_pkgs = _cfg.get('check_package_installable', True)
    if _check_pkgs:
        _unimportable = check_packages_importable(old_string)
        if _unimportable:
            _warned = True
            print(json.dumps({
                'additionalContext': (
                    f'[monitor:WARN:layer1.8] Import(s) not found in current Python '
                    f'environment: {_unimportable!r}. Verify package names are correct.'
                )
            }))

    # Gap #35: warn on URL/remote references in old_string (may be hallucinated)
    _check_remote = _cfg.get('check_remote_refs', True)
    if _check_remote:
        remote_urls = find_remote_refs(old_string)
        if remote_urls:
            _warned = True
            print(json.dumps({
                'additionalContext': (
                    f'[monitor:WARN:layer1.8] old_string contains {len(remote_urls)} '
                    f'URL reference(s) (e.g. {remote_urls[0][:60]!r}). '
                    'Verify these URLs are correct before editing.'
                )
            }))

    if not _check_fn_existence:
        if _warned:
            state['layer18_hallucination_warned'] = True
            ss.write_state(state)
        return

    # Per-session dedup: skip function refs already checked this session
    names_found = re.findall(r'(?:^|\s)def\s+(\w+)|(?:^|\s)class\s+(\w+)', old_string)
    names = [d or c for d, c in names_found if d or c]
    if not names:
        if _warned:
            state['layer18_hallucination_warned'] = True
            ss.write_state(state)
        return

    checked = state.get('layer18_session_checked', {})
    unchecked = [n for n in names if f'{file_path}::{n}' not in checked]
    if not unchecked:
        if _warned:
            state['layer18_hallucination_warned'] = True
            ss.write_state(state)
        return  # all refs already verified this session

    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception:
        return

    missing = []
    for name in unchecked:
        exists = name in content
        checked[f'{file_path}::{name}'] = exists
        if not exists:
            missing.append(name)

    state['layer18_session_checked'] = checked
    if _warned or missing:
        state['layer18_hallucination_warned'] = True
    ss.write_state(state)

    if missing:
        import time as _t, uuid as _uuid
        _write_event({'event_id': str(_uuid.uuid4()), 'ts': _t.strftime('%Y-%m-%dT%H:%M:%S'),
                      'layer': 'layer18', 'category': 'HALLUCINATION_DETECTED', 'severity': 'warning',
                      'detection_signal': f'Missing refs in {os.path.basename(file_path)}: {missing[:3]}',
                      'file_path': file_path})
        print(json.dumps({
            'additionalContext': (
                f'[monitor:WARN:layer1.8] Referenced function/class in old_string '
                f'may not exist in {os.path.basename(file_path)!r}. '
                f'Read the file first to confirm exact content.'
            )
        }))


if __name__ == '__main__':
    main()

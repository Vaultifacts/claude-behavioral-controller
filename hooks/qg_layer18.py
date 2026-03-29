#!/usr/bin/env python3
"""Layer 1.8 — Hallucination Detection (PreToolUse on Edit).
Checks: (1) file path exists before Edit; (2) referenced function exists in file.
Write tool is exempt (creates new files by design).
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss


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


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get('tool_name', '')
    tool_input = payload.get('tool_input', {}) or {}

    # Write always creates/overwrites — no existence check needed
    if tool_name in ('Write',):
        return

    if tool_name != 'Edit':
        return

    file_path = tool_input.get('file_path', '')
    if not file_path:
        return

    state = ss.read_state()

    # Suppress if Layer 1.7 confirmed creating new artifacts in this scope
    if state.get('layer17_creating_new_artifacts'):
        return

    if not check_path_exists(file_path):
        print(json.dumps({
            'additionalContext': (
                f'[monitor:WARN:layer1.8] Path does not exist: {file_path!r}. '
                f'Use Glob to find the correct path, or Write to create a new file.'
            )
        }))
        return

    old_string = tool_input.get('old_string', '')
    if old_string and not check_function_in_file(file_path, old_string):
        print(json.dumps({
            'additionalContext': (
                f'[monitor:WARN:layer1.8] Referenced function/class in old_string '
                f'may not exist in {os.path.basename(file_path)!r}. '
                f'Read the file first to confirm exact content.'
            )
        }))


if __name__ == '__main__':
    main()

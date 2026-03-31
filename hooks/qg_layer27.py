#!/usr/bin/env python3
"""Layer 2.7 -- Testing Coverage Verification (PreToolUse on Edit).
Warns if edited code file has no associated test file or coverage data.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CODE_EXTS = {".py", ".js", ".ts", ".go", ".java", ".cs"}

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass



def find_test_file(source_path):
    base = os.path.splitext(os.path.basename(source_path))[0]
    cwd = os.getcwd()
    for root, _, files in os.walk(cwd):
        for fname in files:
            no_ext = os.path.splitext(fname)[0]
            if (no_ext == "test_" + base or
                    no_ext == base + "_test" or
                    no_ext == base + "_spec" or
                    (no_ext.startswith("test_") and base in no_ext)):
                return os.path.join(root, fname)
    return None


def has_coverage_data():
    cwd = os.getcwd()
    for name in (".coverage", "coverage.xml", "coverage/lcov.info"):
        if os.path.exists(os.path.join(cwd, name)):
            return True
    return False


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    if payload.get("tool_name") != "Edit":
        return

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        return

    _, ext = os.path.splitext(file_path)
    if ext not in CODE_EXTS:
        return

    base = os.path.splitext(os.path.basename(file_path))[0]
    if base.startswith(("test_", "spec_", "Test")):
        return  # Skip test files themselves

    if has_coverage_data():
        return

    if find_test_file(file_path):
        return

    import time as _t, uuid as _uuid
    _write_event({"event_id": str(_uuid.uuid4()), "ts": _t.strftime("%Y-%m-%dT%H:%M:%S"),
                  "layer": "layer27", "category": "NO_TEST_FILE", "severity": "info",
                  "detection_signal": f"No test file for {os.path.basename(file_path)}",
                  "file_path": file_path})
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "additionalContext": "[Layer 2.7] No test file found for {}. Consider adding tests.".format(
            os.path.basename(file_path))}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Layer 2.5 -- Output Validity (PostToolUse on Write/Edit).
Validates file syntax after write/edit; feeds Layer 2 OUTPUT_UNVALIDATED.
"""
import ast, json, os, subprocess, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
SIZE_LIMIT = 102400  # 100KB


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _validate_python(content, path):
    ast.parse(content)


def _validate_json(content, path):
    json.loads(content)


def _validate_yaml(content, path):
    try:
        import yaml
        yaml.safe_load(content)
    except ImportError:
        pass


def _validate_sh(content, path):
    r = subprocess.run(["bash", "-n", "/dev/stdin"],
                       input=content.encode("utf-8", errors="ignore"),
                       capture_output=True, timeout=5)
    if r.returncode != 0:
        raise SyntaxError(r.stderr.decode(errors="replace").strip())


VALIDATORS = {
    ".py": _validate_python,
    ".json": _validate_json,
    ".yaml": _validate_yaml,
    ".yml": _validate_yaml,
    ".sh": _validate_sh,
}


def validate_file(file_path):
    """Returns error string on failure, None on success/skip."""
    _, ext = os.path.splitext(file_path)
    validator = VALIDATORS.get(ext)
    if not validator:
        return None
    try:
        if not os.path.exists(file_path):
            return None
        if os.path.getsize(file_path) > SIZE_LIMIT:
            return None
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        validator(content, file_path)
        return None
    except Exception as e:
        return str(e)[:200]


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        return

    error = validate_file(file_path)
    if error is None:
        return

    state = ss.read_state()
    state["layer25_syntax_failure"] = True

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "task_id": state.get("active_task_id", ""),
        "layer": "layer25",
        "category": "OUTPUT_UNVALIDATED",
        "severity": "warning",
        "detection_signal": "Syntax error in {}: {}".format(file_path, error),
        "file_path": file_path,
        "status": "open",
    }
    _write_event(event)

    unresolved = state.get("layer2_unresolved_events", [])
    unresolved.append(event)
    state["layer2_unresolved_events"] = unresolved[-50:]
    ss.write_state(state)

    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
        "additionalContext": "[Layer 2.5] Syntax warning: {} has invalid syntax. Verify before proceeding.".format(file_path)}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()

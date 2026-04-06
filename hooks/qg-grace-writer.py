#!/usr/bin/env python3
"""PostToolUse hook: write grace file when a Bash tool produces test-runner output."""
import json, os, re, sys

_GRACE_FILE = os.path.join(os.path.expanduser("~/.claude"), "hooks", "qg-count-grace.json").replace("\\", "/")
_LOG_PATH = os.path.join(os.path.expanduser("~/.claude"), "quality-gate.log")
_BARE_COUNT_RE = re.compile(r"\d+\s+passed,\s*\d+\s+failed,\s*\d+\s+total|=== Results:\s*\d+\s+passed", re.IGNORECASE)
_COUNT_NUM_RE = re.compile(r"(\d+)\s+passed", re.IGNORECASE)


def main():
    try:
        data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    output = data.get("tool_response", {})
    if isinstance(output, dict):
        text = output.get("content", "") or ""
    else:
        text = str(output or "")
    if not text or not _BARE_COUNT_RE.search(text):
        return
    m = _COUNT_NUM_RE.search(text)
    if not m:
        return
    import time
    key = m.group(1)
    try:
        with open(_GRACE_FILE, "w") as gf:
            import json as _j
            _j.dump({"ts": time.time(), "key": key}, gf)
        from datetime import datetime
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(_LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(now + " | GRACE-WRITE | key=" + key + " | source=PostToolUse" + chr(10))
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    main()

#!/usr/bin/env python3
"""PostToolUse hook: auto-update smoke count in memory when smoke-test.sh passes."""
import json, os, re, sys
from datetime import datetime

_CALIBRATION = "C:/Users/Matt1/.claude/projects/C--Users-Matt1/memory/quality-gate-calibration.md"
_MEMORY_MD   = "C:/Users/Matt1/.claude/projects/C--Users-Matt1/memory/MEMORY.md"
_RESULTS_RE  = re.compile(r"=== Results: (\d+) passed, 0 failed, \d+ total ===", re.IGNORECASE)
_MEMLINE_RE  = re.compile(r"(quality-gate-calibration\.md.*?)(\d+) smoke tests pass")

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
    if not text:
        return
    m = _RESULTS_RE.search(text)
    if not m:
        return
    count = int(m.group(1))
    if count < 50:
        return
    now = datetime.now().strftime("%Y-%m-%d")
    # Update only the quality-gate-calibration.md line in MEMORY.md
    try:
        mem = open(_MEMORY_MD, encoding="utf-8").read()
        new_mem = _MEMLINE_RE.sub(lambda mo: mo.group(1) + str(count) + " smoke tests pass", mem)
        if new_mem != mem:
            open(_MEMORY_MD, "w", encoding="utf-8").write(new_mem)
    except Exception:
        pass
    # Append auto-update entry to calibration file (deduplicated per day+count)
    try:
        cal = open(_CALIBRATION, encoding="utf-8").read()
        today_marker = f"## Auto-update {now}\n- smoke-test.sh: {count} passed"
        if today_marker not in cal:
            entry = f"\n## Auto-update {now}\n- smoke-test.sh: {count} passed, 0 failed (auto-updated by PostToolUse hook)\n"
            open(_CALIBRATION, "a", encoding="utf-8").write(entry)
    except Exception:
        pass

if __name__ == "__main__":
    main()

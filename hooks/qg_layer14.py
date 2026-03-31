#!/usr/bin/env python3
"""Layer 14 -- Response Efficiency Analysis (Stop hook).
Measures tool call efficiency: redundant reads, excessive calls, verbose responses.
Advisory only -- logs events, never blocks.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")

COMPLEXITY_THRESHOLDS = {
    "TRIVIAL": 5,
    "SIMPLE": 10,
    "MODERATE": 20,
    "COMPLEX": 40,
    "DEEP": 80,
}


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def parse_tool_calls(transcript_path):
    """Extract tool call names and file paths from the last turn in transcript."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return [], []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return [], []

    tool_calls = []
    read_paths = []
    # Scan from end to find last assistant turn
    for line in reversed(lines[-500:]):
        try:
            d = json.loads(line)
        except Exception:
            continue
        role = d.get("role", "")
        if role == "user":
            content = d.get("message", {}).get("content", [])
            if isinstance(content, list):
                has_tool_result = any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
                if not has_tool_result:
                    break
        if role != "assistant":
            continue
        for block in d.get("message", {}).get("content", []):
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name", "")
            tool_calls.append(name)
            inp = block.get("input", {})
            if name == "Read":
                fp = inp.get("file_path", "")
                if fp:
                    read_paths.append(fp)
    tool_calls.reverse()
    read_paths.reverse()
    return tool_calls, read_paths


def detect_redundant_reads(read_paths):
    """Find files read multiple times. Returns list of (path, count)."""
    from collections import Counter
    counts = Counter(os.path.normpath(p).replace(chr(92), "/") for p in read_paths)
    return [(p, c) for p, c in counts.items() if c > 1]


def check_tool_count(tool_calls, complexity=None):
    """Check if tool call count is excessive for complexity class."""
    if not complexity:
        return None
    threshold = COMPLEXITY_THRESHOLDS.get(complexity)
    if threshold is None:
        return None
    count = len(tool_calls)
    if count > threshold:
        return ("warning", "EXCESSIVE_TOOLS: {} calls for {} task (threshold {})".format(count, complexity, threshold))
    return None


def analyze_efficiency(tool_calls, read_paths, complexity=None):
    """Run all efficiency checks. Returns report dict."""
    issues = []

    # Check tool count vs complexity
    count_issue = check_tool_count(tool_calls, complexity)
    if count_issue:
        issues.append(count_issue)

    # Check redundant reads
    redundant = detect_redundant_reads(read_paths)
    for path, count in redundant:
        issues.append(("info", "REDUNDANT_READ: {} read {} times".format(os.path.basename(path), count)))

    stats = {
        "total_tool_calls": len(tool_calls),
        "total_reads": len(read_paths),
        "redundant_reads": len(redundant),
        "complexity": complexity or "unknown",
    }

    has_warning = any(s == "warning" for s, _ in issues)
    status = "warning" if has_warning else "info" if issues else "ok"
    return {"status": status, "issues": issues, "stats": stats}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    transcript_path = payload.get("transcript_path", "")
    tool_calls, read_paths = parse_tool_calls(transcript_path)

    if not tool_calls:
        return

    state = ss.read_state()
    complexity = state.get("last_complexity", "MODERATE")

    report = analyze_efficiency(tool_calls, read_paths, complexity)

    if report["status"] == "ok":
        return

    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer14",
        "category": "RESPONSE_EFFICIENCY",
        "severity": report["status"],
        "detection_signal": "; ".join(msg for _, msg in report["issues"][:3]),
        "efficiency_stats": report["stats"],
    }
    _write_event(event)

    lines = ["[Layer 14] Efficiency:"]
    for sev, msg in report["issues"][:5]:
        lines.append("  - [{}] {}".format(sev, msg))
    text = chr(10).join(lines)
    out = {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": text}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()

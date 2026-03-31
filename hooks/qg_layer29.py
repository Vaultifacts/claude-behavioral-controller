#!/usr/bin/env python3
"""Layer 2.9 -- Semantic Correctness Verification (Stop hook).
Compares response claims against actual tool actions.
Detects: claim-action mismatch, count mismatches, directional inversions.
Advisory only -- logs events, never blocks.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


CLAIM_PATTERNS = [
    (re.compile(r'\b(?:added|implemented|created)\s+(?:error|exception)\s*handling\b', re.IGNORECASE),
     re.compile(r'\b(?:try|except|catch|finally|rescue)\b')),
    (re.compile(r'\b(?:added|implemented|created)\s+(?:type|typing)\s*(?:hints?|annotations?)\b', re.IGNORECASE),
     re.compile(r':\s*(?:str|int|float|bool|list|dict|Optional|Union|Any)\b')),
    (re.compile(r'\b(?:added|implemented|created)\s+(?:logging|logs?)\b', re.IGNORECASE),
     re.compile(r'\b(?:logging\.|logger\.|console\.log|print\()\b')),
    (re.compile(r'\b(?:added|implemented|created)\s+(?:tests?|unit tests?)\b', re.IGNORECASE),
     re.compile(r'\bdef test_|\bit\(|describe\(|test\(\b')),
    (re.compile(r'\b(?:added|implemented|created)\s+(?:validation|input validation)\b', re.IGNORECASE),
     re.compile(r'\b(?:if not|raise ValueError|raise TypeError|\.validate|is None)\b')),
    (re.compile(r'\b(?:added|implemented)\s+(?:docstrings?|documentation)\b', re.IGNORECASE),
     re.compile(r'"""' + '|' + chr(39)*3 + r'|/\*\*')),
]

DIRECTION_PATTERNS = [
    ('descending', re.compile(r'\b(?:reverse\s*=\s*True|DESC|sort_values\([^)]*ascending\s*=\s*False)\b', re.IGNORECASE)),
    ('ascending', re.compile(r'\b(?:reverse\s*=\s*False|ASC(?:\b|ENDING)|sort_values\([^)]*ascending\s*=\s*True|sorted\()\b', re.IGNORECASE)),
    ('case.insensitive', re.compile(r'\b(?:\.lower\(\)|\.upper\(\)|re\.IGNORECASE|ILIKE|COLLATE NOCASE)\b', re.IGNORECASE)),
]

COUNT_RE = re.compile(r'\b(?:added?|created?|wrote|implemented?)\s+(\d+)\s+(?:tests?|functions?|methods?|endpoints?|files?|classes?|routes?)\b', re.IGNORECASE)


def _get_last_turn_data(transcript_path, max_lines=300):
    """Get response text and edited file contents from last turn."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return "", ""
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return "", ""
    response_text = ""
    edit_content = ""
    for line in reversed(lines[-max_lines:]):
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
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        c = b.get("content", "")
                        if isinstance(c, str):
                            edit_content += c + chr(10)
        elif role == "assistant":
            for block in d.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "text":
                    response_text += block.get("text", "") + chr(10)
    return response_text, edit_content


def check_claim_action(response_text, edit_content):
    """Check if response claims are supported by edit content."""
    issues = []
    if not response_text or not edit_content:
        return issues
    for claim_re, evidence_re in CLAIM_PATTERNS:
        if claim_re.search(response_text) and not evidence_re.search(edit_content):
            claim_match = claim_re.search(response_text).group(0)
            issues.append(('warning', 'CLAIM_MISMATCH: claimed [{}] but no evidence in edits'.format(claim_match[:60])))
    return issues


def check_direction(response_text, edit_content):
    """Check if directional keywords in response match code."""
    issues = []
    if not response_text or not edit_content:
        return issues
    resp_lower = response_text.lower()
    for keyword, evidence_re in DIRECTION_PATTERNS:
        if keyword in resp_lower and not evidence_re.search(edit_content):
            issues.append(('info', 'DIRECTION_CHECK: mentioned [{}] but no matching pattern in code'.format(keyword)))
    return issues


def check_count_claims(response_text, edit_content):
    """Check if count claims match actual counts in edits."""
    issues = []
    if not response_text or not edit_content:
        return issues
    for m in COUNT_RE.finditer(response_text):
        claimed = int(m.group(1))
        item_word = m.group(0).split()[-1].lower().rstrip("s")
        if "test" in item_word:
            actual = len(re.findall(r'\bdef test_', edit_content))
            if actual > 0 and abs(claimed - actual) > 1:
                issues.append(("warning", "COUNT_MISMATCH: claimed {} tests but found {} in edits".format(claimed, actual)))
        elif "function" in item_word or "method" in item_word:
            actual = len(re.findall(r'\bdef \w+', edit_content))
            if actual > 0 and abs(claimed - actual) > 1:
                issues.append(("warning", "COUNT_MISMATCH: claimed {} functions but found {} in edits".format(claimed, actual)))
    return issues


def analyze_semantics(response_text, edit_content):
    """Run all semantic checks. Returns report dict."""
    all_issues = []
    all_issues.extend(check_claim_action(response_text, edit_content))
    all_issues.extend(check_direction(response_text, edit_content))
    all_issues.extend(check_count_claims(response_text, edit_content))
    has_warning = any(s == "warning" for s, _ in all_issues)
    status = "warning" if has_warning else "info" if all_issues else "ok"
    return {"status": status, "issues": all_issues}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    transcript_path = payload.get("transcript_path", "")
    response_text, edit_content = _get_last_turn_data(transcript_path)

    if not response_text or not edit_content:
        return

    report = analyze_semantics(response_text, edit_content)
    if report["status"] == "ok":
        return

    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer29",
        "category": "SEMANTIC_CORRECTNESS",
        "severity": report["status"],
        "detection_signal": "; ".join(msg for _, msg in report["issues"][:3]),
    }
    _write_event(event)

    lines = ["[Layer 2.9] Semantic check:"]
    for sev, msg in report["issues"][:5]:
        lines.append("  - [{}] {}".format(sev, msg))
    text = chr(10).join(lines)
    out = {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": text}}
    print(json.dumps(out))


if __name__ == "__main__":
    main()

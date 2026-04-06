#!/usr/bin/env python3
"""Layer 11 -- Commit Quality Gate (PreToolUse on Bash).
Validates git commit messages and staged content before commits happen.
Blocks commits with secrets in staged files. Warns on format issues.
"""
import json, os, re, subprocess, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")

CONVENTIONAL_RE = re.compile(
    r'^(\[AUTO\]\s+)?'
    r'(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)'
    r'(\([^)]+\))?'
    r'!?:\s+.{3,}',
    re.IGNORECASE,
)

SECRET_PATTERNS = [
    (r'AKIA[0-9A-Z]{16}', 'AWS access key'),
    (r'(?i)sk-[a-zA-Z0-9]{20,}', 'OpenAI/Anthropic API key'),
    (r'ghp_[A-Za-z0-9]{36}', 'GitHub PAT'),
    (r'ghs_[A-Za-z0-9]{36}', 'GitHub service token'),
    (r'github_pat_[A-Za-z0-9_]{30,}', 'GitHub fine-grained PAT'),
    (r'xox[bp]-[A-Za-z0-9-]{20,}', 'Slack token'),
    (r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----', 'private key'),
    (r"(?i)(password|passwd|pwd)\s*=\s*['\"](?!your_|<|{|example|placeholder|changeme|xxx)[^'\"]{8,}", 'password'),
]

DANGEROUS_FILES = [".env", ".pem", ".key", ".pfx", ".p12", "credentials", ".secret"]
LARGE_FILE_LIMIT = 1024 * 1024


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def _run_git(args):
    try:
        result = subprocess.run(["git"] + args, capture_output=True, text=True, timeout=10)
        return result.stdout.strip()
    except Exception:
        return ""


def _extract_command(payload):
    ti = payload.get("tool_input", payload)
    if isinstance(ti, dict):
        return ti.get("command", "")
    return ""


def _is_git_commit(cmd):
    return bool(re.search(r'\bgit\s+commit\b', cmd))


def _is_git_push(cmd):
    return bool(re.search(r'\bgit\s+push\b', cmd))


def _extract_commit_message(cmd):
    m = re.search(r'-m\s+([\'"])(.*?)\1', cmd, re.DOTALL)
    if m:
        return m.group(2).split('\n')[0].strip()
    m = re.search(r'-m\s+(\S+)', cmd)
    if m:
        return m.group(1)
    return None


def check_commit_message(message):
    """Validate commit message format. Returns list of (severity, issue)."""
    issues = []
    if not message:
        return issues
    if not CONVENTIONAL_RE.match(message):
        issues.append(("warning", "COMMIT_FORMAT: message does not match conventional commit format"))
    if len(message) > 200:
        issues.append(("warning", "COMMIT_LENGTH: message is {} chars (recommended <72 for subject)".format(len(message))))
    return issues


def check_staged_secrets(diff_content=None):
    """Check staged diff for secrets. Returns list of (severity, issue)."""
    issues = []
    if diff_content is None:
        diff_content = _run_git(["diff", "--cached", "--diff-filter=ACMR"])
    if not diff_content:
        return issues
    for pattern, label in SECRET_PATTERNS:
        if re.search(pattern, diff_content):
            issues.append(("critical", "STAGED_SECRET: {} detected in staged changes".format(label)))
    return issues


def check_staged_files(file_list=None):
    """Check staged file list for dangerous files and large files."""
    issues = []
    if file_list is None:
        raw = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
        file_list = raw.split("\n") if raw else []
    for f in file_list:
        if not f.strip():
            continue
        basename = os.path.basename(f.strip()).lower()
        _, ext = os.path.splitext(basename)
        if ext in (".env",) or basename in ("credentials",) or any(basename.endswith(d) for d in DANGEROUS_FILES):
            issues.append(("critical", "DANGEROUS_FILE: {} should not be committed".format(f.strip())))
    return issues


def check_push(cmd):
    """Check git push command for safety. Returns list of (severity, issue)."""
    issues = []
    if re.search(r'--force\b|--force-with-lease\b|-f\b', cmd):
        issues.append(("critical", "FORCE_PUSH: force push detected"))
    return issues


def run_commit_check(cmd, diff_content=None, file_list=None):
    """Run all commit checks. Returns report dict."""
    all_issues = []

    message = _extract_commit_message(cmd)
    all_issues.extend(check_commit_message(message))
    all_issues.extend(check_staged_secrets(diff_content))
    all_issues.extend(check_staged_files(file_list))

    has_critical = any(sev == "critical" for sev, _ in all_issues)
    status = "block" if has_critical else "warn" if all_issues else "ok"
    return {"status": status, "issues": all_issues}


def run_push_check(cmd):
    """Run push checks. Returns report dict."""
    all_issues = check_push(cmd)
    has_critical = any(sev == "critical" for sev, _ in all_issues)
    status = "block" if has_critical else "ok"
    return {"status": status, "issues": all_issues}


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name != "Bash":
        return

    cmd = _extract_command(payload)
    if not cmd:
        return

    is_commit = _is_git_commit(cmd)
    is_push = _is_git_push(cmd)

    if not is_commit and not is_push:
        return

    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    if is_commit:
        report = run_commit_check(cmd)
    else:
        report = run_push_check(cmd)

    if report["status"] == "ok":
        return

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer11",
        "category": "COMMIT_QUALITY",
        "severity": "critical" if report["status"] == "block" else "warning",
        "detection_signal": "; ".join(msg for _, msg in report["issues"][:3]),
        "status": "open",
    }
    _write_event(event)

    if report["status"] == "block":
        msg = "[Layer 11] COMMIT BLOCKED: " + "; ".join(msg for _, msg in report["issues"][:3])
        print(msg, file=sys.stderr)
        sys.exit(2)

    lines = ["[Layer 11] Commit advisory:"]
    for sev, msg in report["issues"][:5]:
        lines.append("  - [{}] {}".format(sev, msg))
    text = chr(10).join(lines)
    out = {"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": text}}
    print(json.dumps(out))


if __name__ == "__main__":  # pragma: no cover
    main()

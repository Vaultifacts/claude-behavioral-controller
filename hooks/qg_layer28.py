#!/usr/bin/env python3
"""Layer 2.8 -- Security Vulnerability Detection (PostToolUse on Write/Edit).
Scans written/edited code files for OWASP-category vulnerabilities.
Advisory only -- warns but does not block.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
SIZE_LIMIT = 102400
CODE_EXTS = {".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".java", ".cs", ".rb", ".php"}
TEST_PREFIXES = ("test_", "spec_", "Test")


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def _is_test_file(file_path):
    base = os.path.splitext(os.path.basename(file_path))[0]
    return base.startswith(TEST_PREFIXES) or base.endswith("_test") or base.endswith("_spec")


def _skip_path(file_path):
    skip_dirs = ("node_modules", ".git", "__pycache__", ".venv", "venv")
    norm = file_path.replace(chr(92), "/")
    return any("/" + d + "/" in norm or norm.startswith(d + "/") for d in skip_dirs)


# SQL Injection (CRITICAL)
SQL_FSTRING_RE = re.compile(r'(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s+.*\{[^}]+\}', re.IGNORECASE)
SQL_CONCAT_RE = re.compile(r'''(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s+.*[\'"]\s*\+\s*\w+''', re.IGNORECASE)
SQL_FORMAT_RE = re.compile(r'(?:SELECT|INSERT|UPDATE|DELETE|DROP)\s+.*\.format\(', re.IGNORECASE)

# Command Injection (CRITICAL)
EVAL_RE = re.compile(r'\beval\s*\(\s*[a-zA-Z_]')
EXEC_RE = re.compile(r'\bexec\s*\(\s*[a-zA-Z_]')
OS_SYSTEM_RE = re.compile(r'\bos\.system\s*\(')
SHELL_TRUE_RE = re.compile(r'subprocess\.\w+\([^)]*shell\s*=\s*True')

# XSS (CRITICAL)
INNERHTML_RE = re.compile(r'\.innerHTML\s*=\s*[a-zA-Z_$]')
DANGEROUSLY_RE = re.compile(r'dangerouslySetInnerHTML\s*=\s*\{')

# Insecure Deserialization (CRITICAL)
PICKLE_LOADS_RE = re.compile(r'pickle\.loads?\s*\(')

# Insecure Crypto (WARNING)
WEAK_HASH_RE = re.compile(r'hashlib\.(md5|sha1)\s*\(')

RULES = [
    (SQL_FSTRING_RE, "SQL_INJECTION", "critical", "f-string in SQL query -- use parameterized queries", {".py"}),
    (SQL_CONCAT_RE, "SQL_INJECTION", "critical", "string concat in SQL -- use parameterized queries", CODE_EXTS),
    (SQL_FORMAT_RE, "SQL_INJECTION", "critical", ".format() in SQL query -- use parameterized queries", {".py"}),
    (EVAL_RE, "COMMAND_INJECTION", "critical", "eval() with variable input", {".py", ".js", ".ts", ".jsx", ".tsx"}),
    (EXEC_RE, "COMMAND_INJECTION", "critical", "exec() with variable input", {".py"}),
    (OS_SYSTEM_RE, "COMMAND_INJECTION", "critical", "os.system() -- use subprocess with shell=False", {".py"}),
    (SHELL_TRUE_RE, "COMMAND_INJECTION", "warning", "subprocess with shell=True", {".py"}),
    (INNERHTML_RE, "XSS", "critical", "innerHTML = variable -- use textContent or sanitize", {".js", ".ts", ".jsx", ".tsx"}),
    (DANGEROUSLY_RE, "XSS", "critical", "dangerouslySetInnerHTML -- sanitize with DOMPurify", {".js", ".ts", ".jsx", ".tsx"}),
    (PICKLE_LOADS_RE, "INSECURE_DESERIALIZATION", "critical", "pickle.loads -- use json instead", {".py"}),
    (WEAK_HASH_RE, "INSECURE_CRYPTO", "warning", "md5/sha1 -- use sha256+ for security", {".py"}),
]


def check_security(file_path, content=None):
    """Scan file for security vulnerabilities. Returns list of (vuln_type, severity, detail, line_num)."""
    if not file_path:
        return []
    _, ext = os.path.splitext(file_path)
    if ext not in CODE_EXTS:
        return []
    if _skip_path(file_path):
        return []
    is_test = _is_test_file(file_path)

    if content is None:
        try:
            if not os.path.exists(file_path):
                return []
            if os.path.getsize(file_path) > SIZE_LIMIT:
                return []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return []

    findings = []
    lines = content.split("\n")
    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith("//") or stripped.startswith("*"):
            continue
        for regex, vuln_type, severity, desc, langs in RULES:
            if ext not in langs:
                continue
            if is_test and vuln_type == "COMMAND_INJECTION":
                continue
            if regex.search(line):
                findings.append((vuln_type, severity, desc + " (line {})".format(i), i))
                break
    return findings


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

    findings = check_security(file_path)
    if not findings:
        return

    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    for vuln_type, severity, detail, line_num in findings:
        event = {
            "event_id": str(uuid.uuid4()),
            "ts": ts,
            "session_uuid": state.get("session_uuid") or "",
            "working_dir": os.getcwd(),
            "task_id": state.get("active_task_id", ""),
            "layer": "layer28",
            "category": "SECURITY_VULNERABILITY",
            "severity": severity,
            "detection_signal": "{}: {}".format(vuln_type, detail),
            "file_path": file_path,
            "vuln_type": vuln_type,
            "status": "open",
        }
        _write_event(event)

    worst = sorted(findings, key=lambda f: 0 if f[1] == "critical" else 1)[0]
    basename = os.path.basename(file_path)
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse",
        "additionalContext": "[Layer 2.8] SECURITY: {} in {} -- {}".format(worst[0], basename, worst[2])}}
    print(json.dumps(out))


if __name__ == "__main__":  # pragma: no cover
    main()

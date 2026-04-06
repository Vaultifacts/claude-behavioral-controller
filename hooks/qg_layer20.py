#!/usr/bin/env python3
"""Layer 20 -- System Health Dashboard (SessionStart).
Validates the monitoring system itself: hook files, registrations, state, logs.
Advisory only -- outputs context injection, never blocks.
"""
import glob
import json
import os
import re
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

CLAUDE_DIR = os.path.expanduser("~/.claude")
HOOKS_DIR = os.path.join(CLAUDE_DIR, "hooks")
SETTINGS_PATH = os.path.join(CLAUDE_DIR, "settings.json")
STATE_PATH = os.path.join(CLAUDE_DIR, "qg-session-state.json")
MONITOR_PATH = os.path.join(CLAUDE_DIR, "qg-monitor.jsonl")
QUARANTINE_PATH = os.path.join(CLAUDE_DIR, "qg-quarantine.jsonl")

STATE_SIZE_LIMIT = 50 * 1024
MONITOR_SIZE_LIMIT = 5 * 1024 * 1024
LOG_SIZE_LIMIT = 2 * 1024 * 1024
QUARANTINE_WARN = 20
MONITOR_TAIL_LINES = 200

LIBRARY_LAYERS = {"qg_layer10.py", "qg_layer35.py"}

LOG_FILES = ["quality-gate.log", "hook-audit.log", "task-classifier.log", "audit-log.md"]


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def _extract_hook_files(settings_path):
    """Parse settings.json and return set of normalized file paths from hook commands."""
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except Exception:
        return set()
    files = set()
    hooks = settings.get("hooks", {})
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                m = re.search(r'(?:python|bash)\s+([^\s]+\.(?:py|sh))', cmd)
                if m:
                    fp = m.group(1).replace("/c/Users", "C:/Users")
                    fp = os.path.normpath(fp)
                    files.add(fp)
    return files


def check_hook_files(settings_path=None):
    """Check all hook files exist and .py files are syntactically valid."""
    settings_path = settings_path or SETTINGS_PATH
    issues = []
    files = _extract_hook_files(settings_path)
    for fp in sorted(files):
        if not os.path.exists(fp):
            issues.append(("critical", "MISSING_FILE: {} not found".format(os.path.basename(fp))))
            continue
        if fp.endswith(".py"):
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()
                compile(source, fp, "exec")
            except SyntaxError as e:
                issues.append(("warning", "SYNTAX_ERROR: {} line {}".format(os.path.basename(fp), e.lineno)))
    return issues, len(files)


def check_registration_integrity(settings_path=None, hooks_dir=None):
    """Find qg_layer*.py files not registered in settings.json."""
    settings_path = settings_path or SETTINGS_PATH
    hooks_dir = hooks_dir or HOOKS_DIR
    issues = []
    registered = _extract_hook_files(settings_path)
    registered_basenames = {os.path.basename(fp) for fp in registered}
    layer_files = glob.glob(os.path.join(hooks_dir, "qg_layer*.py"))
    for lf in sorted(layer_files):
        bn = os.path.basename(lf)
        if bn in LIBRARY_LAYERS:
            continue
        if bn not in registered_basenames:
            issues.append(("warning", "UNREGISTERED: {} exists but not in settings.json".format(bn)))
    return issues


def check_state_health(state_path=None):
    """Check session state file: exists, valid JSON, reasonable size."""
    state_path = state_path or STATE_PATH
    issues = []
    if not os.path.exists(state_path):
        issues.append(("critical", "STATE_MISSING: qg-session-state.json not found"))
        return issues, 0
    try:
        size = os.path.getsize(state_path)
    except Exception:
        issues.append(("critical", "STATE_UNREADABLE: cannot stat state file"))
        return issues, 0
    if size > STATE_SIZE_LIMIT:
        issues.append(("warning", "STATE_SIZE: {}KB > {}KB limit".format(size // 1024, STATE_SIZE_LIMIT // 1024)))
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            issues.append(("critical", "STATE_INVALID: not a JSON object"))
        elif "schema_version" not in data:
            issues.append(("warning", "STATE_NO_SCHEMA: missing schema_version key"))
    except json.JSONDecodeError:
        issues.append(("critical", "STATE_CORRUPT: invalid JSON"))
    except Exception as e:
        issues.append(("critical", "STATE_ERROR: {}".format(str(e)[:80])))
    return issues, size


def check_monitor_health(monitor_path=None):
    """Check monitor log: exists, size, line count."""
    monitor_path = monitor_path or MONITOR_PATH
    issues = []
    if not os.path.exists(monitor_path):
        issues.append(("warning", "MONITOR_MISSING: qg-monitor.jsonl not found"))
        return issues, 0, 0
    try:
        size = os.path.getsize(monitor_path)
    except Exception:
        return [("warning", "MONITOR_UNREADABLE")], 0, 0
    if size > MONITOR_SIZE_LIMIT:
        issues.append(("warning", "MONITOR_SIZE: {}MB > {}MB limit".format(size // (1024*1024), MONITOR_SIZE_LIMIT // (1024*1024))))
    line_count = 0
    try:
        with open(monitor_path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in f:
                line_count += 1
    except Exception:
        pass
    return issues, size, line_count


def check_quarantine(quarantine_path=None):
    """Count quarantine log entries."""
    quarantine_path = quarantine_path or QUARANTINE_PATH
    issues = []
    count = 0
    if not os.path.exists(quarantine_path):
        return issues, 0
    try:
        with open(quarantine_path, "r", encoding="utf-8", errors="ignore") as f:
            for _ in f:
                count += 1
    except Exception:
        pass
    if count > QUARANTINE_WARN:
        issues.append(("warning", "QUARANTINE: {} entries (review needed)".format(count)))
    elif count > 0:
        issues.append(("info", "QUARANTINE: {} entries".format(count)))
    return issues, count


def check_layer_activity(monitor_path=None):
    """Scan recent monitor events for layer coverage."""
    monitor_path = monitor_path or MONITOR_PATH
    issues = []
    layers_seen = set()
    if not os.path.exists(monitor_path):
        return issues, layers_seen
    try:
        with open(monitor_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        tail = lines[-MONITOR_TAIL_LINES:] if len(lines) > MONITOR_TAIL_LINES else lines
        for line in tail:
            try:
                d = json.loads(line)
                layer = d.get("layer", "")
                if layer:
                    layers_seen.add(layer)
            except Exception:
                pass
    except Exception:
        pass
    return issues, layers_seen


def check_log_sizes(claude_dir=None):
    """Check key log files for excessive size."""
    claude_dir = claude_dir or CLAUDE_DIR
    issues = []
    for name in LOG_FILES:
        path = os.path.join(claude_dir, name)
        if not os.path.exists(path):
            continue
        try:
            size = os.path.getsize(path)
            if size > LOG_SIZE_LIMIT:
                issues.append(("warning", "LOG_SIZE: {} is {}MB > {}MB".format(name, size // (1024*1024), LOG_SIZE_LIMIT // (1024*1024))))
        except Exception:
            pass
    return issues


def run_health_check(settings_path=None, hooks_dir=None, state_path=None,
                     monitor_path=None, quarantine_path=None, claude_dir=None):
    """Run all health checks. Returns report dict."""
    all_issues = []

    hook_issues, hook_count = check_hook_files(settings_path)
    all_issues.extend(hook_issues)

    reg_issues = check_registration_integrity(settings_path, hooks_dir)
    all_issues.extend(reg_issues)

    state_issues, state_size = check_state_health(state_path)
    all_issues.extend(state_issues)

    monitor_issues, monitor_size, monitor_lines = check_monitor_health(monitor_path)
    all_issues.extend(monitor_issues)

    quarantine_issues, quarantine_count = check_quarantine(quarantine_path)
    all_issues.extend(quarantine_issues)

    activity_issues, layers_seen = check_layer_activity(monitor_path)
    all_issues.extend(activity_issues)

    log_issues = check_log_sizes(claude_dir)
    all_issues.extend(log_issues)

    has_critical = any(sev == "critical" for sev, _ in all_issues)
    has_warning = any(sev == "warning" for sev, _ in all_issues)
    status = "critical" if has_critical else "warning" if has_warning else "ok"

    return {
        "status": status,
        "issues": all_issues,
        "stats": {
            "hook_files": hook_count,
            "state_size_kb": state_size // 1024 if state_size else 0,
            "monitor_lines": monitor_lines,
            "monitor_size_kb": monitor_size // 1024 if monitor_size else 0,
            "quarantine_count": quarantine_count,
            "layers_seen": sorted(layers_seen),
        },
    }


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    report = run_health_check()

    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer20",
        "category": "SYSTEM_HEALTH",
        "severity": report["status"],
        "detection_signal": "health: {} ({} issues)".format(report["status"], len(report["issues"])),
        "health_stats": report["stats"],
    }
    _write_event(event)

    stats = report["stats"]
    non_info = [(s, m) for s, m in report["issues"] if s != "info"]

    if non_info:
        lines = ["[Layer 20] HEALTH: {} issues".format(len(non_info))]
        for sev, msg in non_info[:5]:
            lines.append("  - [{}] {}".format(sev, msg))
        text = chr(10).join(lines)
    else:
        text = "[Layer 20] System health: OK ({} hook files, all valid, state {}KB, monitor {} events)".format(
            stats.get("hook_files", 0), stats.get("state_size_kb", 0), stats.get("monitor_lines", 0))

    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    print(json.dumps(out))


if __name__ == "__main__":  # pragma: no cover
    main()

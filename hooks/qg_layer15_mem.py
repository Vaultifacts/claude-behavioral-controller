#!/usr/bin/env python3
"""Layer 15 (Memory) -- Memory & State Integrity (SessionStart).
Checks memory files for staleness, missing references, and basic integrity.
Advisory only.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
MEMORY_DIR = os.path.expanduser("~/.claude/projects/C--Users-Matt1/memory")
MEMORY_INDEX = os.path.join(MEMORY_DIR, "MEMORY.md")
ALT_MEMORY_DIR = os.path.expanduser("~/.claude/memory")
STALE_DAYS = 14
MAX_FILE_SIZE = 100 * 1024

def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass

def _resolve_path(ref_path):
    """Resolve a memory file reference to an absolute path."""
    if ref_path.startswith("memory/"):
        return os.path.join(MEMORY_DIR, ref_path[7:])
    if ref_path.startswith("~/.claude/memory/"):
        return os.path.join(ALT_MEMORY_DIR, ref_path[17:])
    if ref_path.startswith("~/.claude/"):
        return os.path.expanduser(ref_path)
    return os.path.join(MEMORY_DIR, ref_path)

def extract_references(index_path=None):
    """Extract file references from MEMORY.md index."""
    index_path = index_path or MEMORY_INDEX
    if not os.path.exists(index_path):
        return []
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []
    refs = []
    for m in re.finditer(r'\[([^\]]+)\]\(([^)]+\.md)\)', content):
        name = m.group(1)
        path = m.group(2)
        refs.append({"name": name, "ref_path": path})
    return refs

def check_references(index_path=None):
    """Check all referenced memory files exist."""
    refs = extract_references(index_path)
    issues = []
    for ref in refs:
        abs_path = _resolve_path(ref["ref_path"])
        if not os.path.exists(abs_path):
            issues.append(("warning", "MISSING_REF: [{}] -> {} not found".format(ref["name"], ref["ref_path"])))
    return issues, len(refs)

def check_staleness(memory_dir=None, stale_days=None):
    """Check memory files for staleness (not modified in N days)."""
    memory_dir = memory_dir or MEMORY_DIR
    stale_days = stale_days or STALE_DAYS
    issues = []
    stale_count = 0
    if not os.path.isdir(memory_dir):
        return issues, 0, 0
    cutoff = time.time() - (stale_days * 86400)
    total = 0
    for f in os.listdir(memory_dir):
        if not f.endswith(".md"):
            continue
        total += 1
        fp = os.path.join(memory_dir, f)
        try:
            mtime = os.path.getmtime(fp)
            if mtime < cutoff:
                stale_count += 1
                age_days = int((time.time() - mtime) / 86400)
                issues.append(("info", "STALE: {} not updated in {} days".format(f, age_days)))
        except Exception:
            pass
    return issues, total, stale_count

def check_file_sizes(memory_dir=None):
    """Check for oversized memory files."""
    memory_dir = memory_dir or MEMORY_DIR
    issues = []
    if not os.path.isdir(memory_dir):
        return issues
    for f in os.listdir(memory_dir):
        if not f.endswith(".md"):
            continue
        fp = os.path.join(memory_dir, f)
        try:
            size = os.path.getsize(fp)
            if size > MAX_FILE_SIZE:
                issues.append(("warning", "OVERSIZED: {} is {}KB (limit {}KB)".format(f, size // 1024, MAX_FILE_SIZE // 1024)))
        except Exception:
            pass
    return issues

def check_duplicates(memory_dir=None):
    """Check for potential duplicate entries across memory files."""
    memory_dir = memory_dir or MEMORY_DIR
    issues = []
    if not os.path.isdir(memory_dir):
        return issues
    headings = {}
    for f in os.listdir(memory_dir):
        if not f.endswith(".md") or f == "MEMORY.md":
            continue
        fp = os.path.join(memory_dir, f)
        try:
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if line.startswith("# "):
                        h = line.strip().lower()
                        if h in headings and headings[h] != f:
                            issues.append(("info", "DUPLICATE_HEADING: '{}' in both {} and {}".format(line.strip()[:50], headings[h], f)))
                        headings[h] = f
        except Exception:
            pass
    return issues

def analyze_memory_integrity(index_path=None, memory_dir=None, stale_days=None):
    """Run all memory integrity checks. Returns report dict."""
    all_issues = []
    ref_issues, ref_count = check_references(index_path)
    all_issues.extend(ref_issues)
    stale_issues, total_files, stale_count = check_staleness(memory_dir, stale_days)
    all_issues.extend(stale_issues[:5])
    size_issues = check_file_sizes(memory_dir)
    all_issues.extend(size_issues)
    dup_issues = check_duplicates(memory_dir)
    all_issues.extend(dup_issues)
    has_warning = any(s == "warning" for s, _ in all_issues)
    status = "warning" if has_warning else "info" if all_issues else "ok"
    return {
        "status": status,
        "issues": all_issues,
        "stats": {"ref_count": ref_count, "total_files": total_files, "stale_count": stale_count},
    }

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    report = analyze_memory_integrity()
    if report["status"] == "ok":
        return
    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    event = {"event_id": str(uuid.uuid4()), "ts": ts, "session_uuid": state.get("session_uuid") or "", "working_dir": os.getcwd(), "layer": "layer15_mem", "category": "MEMORY_INTEGRITY", "severity": report["status"], "detection_signal": "{} issues ({} stale, {} refs)".format(len(report["issues"]), report["stats"]["stale_count"], report["stats"]["ref_count"])}
    _write_event(event)
    non_info = [(s, m) for s, m in report["issues"] if s != "info"]
    if non_info:
        lines = ["[Layer 15m] Memory integrity: {} issues".format(len(non_info))]
        for sev, msg in non_info[:3]:
            lines.append("  - [{}] {}".format(sev, msg))
        text = chr(10).join(lines)
    else:
        stats = report["stats"]
        text = "[Layer 15m] Memory: {} files, {} refs, {} stale (>{}d)".format(stats["total_files"], stats["ref_count"], stats["stale_count"], STALE_DAYS)
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    print(json.dumps(out))

if __name__ == "__main__":  # pragma: no cover
    main()

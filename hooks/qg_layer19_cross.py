#!/usr/bin/env python3
"""Layer 19 -- Cross-Project Learning (SessionStart).
Aggregates monitor events across ALL projects. Identifies Claude-level
weaknesses vs project-specific patterns. Outputs global insights.
Advisory only.
"""
import json, os, re, sys, time, uuid
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
CROSS_PROJECT_PATH = os.path.expanduser("~/.claude/qg-cross-project.json")
TAIL_LINES = 1000
MIN_PROJECTS = 2
MIN_EVENTS = 3


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


def _normalize_project(working_dir):
    """Normalize working directory to a project name."""
    if not working_dir:
        return "unknown"
    norm = working_dir.replace(chr(92), "/").rstrip("/")
    home = os.path.expanduser("~").replace(chr(92), "/")
    if norm == home:
        return "~"
    if norm.startswith(home + "/"):
        return "~/" + norm[len(home)+1:]
    return norm


def load_events(monitor_path=None, tail_lines=None):
    """Load recent events from monitor log. Returns list of dicts."""
    monitor_path = monitor_path or MONITOR_PATH
    tail_lines = tail_lines or TAIL_LINES
    if not os.path.exists(monitor_path):
        return []
    try:
        with open(monitor_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []
    events = []
    for line in lines[-tail_lines:]:
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    return events


def group_by_project(events):
    """Group events by normalized project directory. Returns dict of project -> list of events."""
    groups = defaultdict(list)
    for e in events:
        wd = e.get("working_dir", "")
        if not wd:
            continue
        project = _normalize_project(wd)
        groups[project].append(e)
    return dict(groups)


def find_cross_project_patterns(project_groups):
    """Find categories that appear in multiple projects. Returns list of pattern dicts."""
    # Count category occurrences per project
    category_projects = defaultdict(set)
    category_counts = Counter()
    for project, events in project_groups.items():
        for e in events:
            cat = e.get("category", "")
            if cat:
                category_projects[cat].add(project)
                category_counts[cat] += 1
    patterns = []
    for cat, projects in category_projects.items():
        if len(projects) >= MIN_PROJECTS and category_counts[cat] >= MIN_EVENTS:
            patterns.append({
                "category": cat,
                "project_count": len(projects),
                "projects": sorted(projects),
                "total_events": category_counts[cat],
                "scope": "global",
            })
    patterns.sort(key=lambda p: p["total_events"], reverse=True)
    return patterns


def find_project_specific_patterns(project_groups):
    """Find categories unique to a single project. Returns list of pattern dicts."""
    category_projects = defaultdict(set)
    category_counts = Counter()
    for project, events in project_groups.items():
        for e in events:
            cat = e.get("category", "")
            if cat:
                category_projects[cat].add(project)
                category_counts[cat] += 1
    patterns = []
    for cat, projects in category_projects.items():
        if len(projects) == 1 and category_counts[cat] >= MIN_EVENTS:
            patterns.append({
                "category": cat,
                "project": sorted(projects)[0],
                "total_events": category_counts[cat],
                "scope": "project-specific",
            })
    patterns.sort(key=lambda p: p["total_events"], reverse=True)
    return patterns


def analyze_cross_project(monitor_path=None):
    """Full cross-project analysis. Returns report dict."""
    events = load_events(monitor_path)
    if not events:
        return {"status": "no_data", "global_patterns": [], "project_patterns": [], "project_count": 0}
    groups = group_by_project(events)
    global_patterns = find_cross_project_patterns(groups)
    project_patterns = find_project_specific_patterns(groups)
    return {
        "status": "ok",
        "global_patterns": global_patterns,
        "project_patterns": project_patterns,
        "project_count": len(groups),
        "total_events": len(events),
    }


def save_report(report, output_path=None):
    """Save cross-project report to JSON file."""
    output_path = output_path or CROSS_PROJECT_PATH
    report["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        tmp = output_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        os.replace(tmp, output_path)
    except Exception:
        pass


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    report = analyze_cross_project()
    if report["status"] == "no_data":
        return

    save_report(report)

    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer19_cross",
        "category": "CROSS_PROJECT",
        "severity": "info",
        "detection_signal": "{} global patterns across {} projects".format(
            len(report["global_patterns"]), report["project_count"]),
    }
    _write_event(event)

    if report["global_patterns"]:
        lines = ["[Layer 19] Cross-project patterns ({} projects):".format(report["project_count"])]
        for p in report["global_patterns"][:3]:
            lines.append("  - {} ({} events across {} projects)".format(
                p["category"], p["total_events"], p["project_count"]))
        text = chr(10).join(lines)
        out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
        print(json.dumps(out))


if __name__ == "__main__":
    main()

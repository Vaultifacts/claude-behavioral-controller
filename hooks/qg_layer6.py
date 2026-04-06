#!/usr/bin/env python3
"""Layer 6 -- Cross-session Pattern Analysis (Stop hook + qg analyze).
Finds violation categories that recur across sessions; feeds Layer 0 context.
"""
import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
CROSS_SESSION_PATH = os.path.expanduser("~/.claude/qg-cross-session.json")
RULES_PATH = os.path.expanduser("~/.claude/qg-rules.json")


def load_monitor_events(monitor_path=None):
    path = monitor_path or MONITOR_PATH
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return events


def analyze_patterns(events, min_sessions=3, min_pct=0.15, window=10, project_dir=None):
    if project_dir:
        events = [e for e in events if e.get("working_dir") == project_dir]
    if not events:
        return []
    sessions = {}
    for e in events:
        sid = e.get("session_uuid", "")
        if sid:
            sessions.setdefault(sid, []).append(e)
    session_list = sorted(sessions.items(),
                          key=lambda x: min(ev.get("ts", "") for ev in x[1]))[-window:]
    if len(session_list) < min_sessions:
        return []
    category_in_sessions = {}
    for sid, evts in session_list:
        cats = set(ev.get("category") for ev in evts if ev.get("category"))
        for cat in cats:
            category_in_sessions.setdefault(cat, set()).add(sid)
    windowed_events = [ev for _, evts in session_list for ev in evts]
    total_events = len(windowed_events)
    patterns = []
    for cat, sids in category_in_sessions.items():
        if len(sids) < min_sessions:
            continue
        cat_total = sum(1 for e in windowed_events if e.get("category") == cat)
        pct = cat_total / max(total_events, 1)
        if pct >= min_pct:
            patterns.append({"category": cat, "sessions_count": len(sids),
                             "event_pct": round(pct, 3), "total_events": cat_total})
    return sorted(patterns, key=lambda x: -x["sessions_count"])


def run_analysis(monitor_path=None, output_path=None, project_dir=None):
    events = load_monitor_events(monitor_path)
    try:
        with open(RULES_PATH, "r", encoding="utf-8") as _f:
            _cfg = json.load(_f).get("layer6", {})
        _min_sessions = _cfg.get("pattern_min_sessions", 3)
        _min_pct = _cfg.get("pattern_min_pct", 15) / 100.0
    except Exception:
        _min_sessions, _min_pct = 3, 0.15
    patterns = analyze_patterns(events, min_sessions=_min_sessions, min_pct=_min_pct, project_dir=project_dir)
    result = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "patterns": patterns,
        "sessions_analyzed": len(set(e.get("session_uuid") for e in events if e.get("session_uuid"))),
    }
    out = output_path or CROSS_SESSION_PATH
    if patterns or not os.path.exists(out):
        with open(out, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
    return result


def main():
    state = ss.read_state()
    last_ts = state.get("layer6_last_analysis_ts", 0)
    if (time.time() - last_ts) < 3600:
        return
    try:
        run_analysis(project_dir=os.getcwd())
        state["layer6_last_analysis_ts"] = time.time()
        ss.write_state(state)
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        result = run_analysis()
        print("Analyzed {} sessions, found {} patterns.".format(
            result["sessions_analyzed"], len(result["patterns"])))
    else:
        main()

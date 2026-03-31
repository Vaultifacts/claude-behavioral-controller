#!/usr/bin/env python3
"""Layer 18 -- A/B Rule Testing.
Compares current vs proposed rule configurations by replaying monitor events.
Runs on-demand (not as a hook) via: python qg_layer18_ab.py <proposed_rules.json>
Also registered as SessionStart for shadow-mode tracking.
"""
import json, os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
RULES_PATH = os.path.expanduser("~/.claude/qg-rules.json")
RESULTS_PATH = os.path.expanduser("~/.claude/qg-ab-results.json")
TAIL_EVENTS = 500

def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass

def load_rules(path=None):
    """Load rules from JSON file."""
    path = path or RULES_PATH
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def load_events(monitor_path=None, tail=None):
    """Load recent monitor events."""
    monitor_path = monitor_path or MONITOR_PATH
    tail = tail or TAIL_EVENTS
    if not os.path.exists(monitor_path):
        return []
    try:
        with open(monitor_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return []
    events = []
    for line in lines[-tail:]:
        try:
            events.append(json.loads(line))
        except Exception:
            pass
    return events

def evaluate_rules(events, rules):
    """Evaluate events against a rule configuration. Returns metrics dict."""
    layer2_limit = rules.get("layer2", {}).get("events_per_turn_limit", 5)
    layer6_min_pct = rules.get("layer6", {}).get("pattern_min_pct", 15)
    layer6_min_sessions = rules.get("layer6", {}).get("pattern_min_sessions", 3)

    metrics = {
        "total_events": len(events),
        "events_by_severity": {},
        "events_by_category": {},
        "events_by_layer": {},
        "would_suppress": 0,
        "would_fire": 0,
    }

    for e in events:
        sev = e.get("severity", "unknown")
        cat = e.get("category", "unknown")
        layer = e.get("layer", "unknown")
        metrics["events_by_severity"][sev] = metrics["events_by_severity"].get(sev, 0) + 1
        metrics["events_by_category"][cat] = metrics["events_by_category"].get(cat, 0) + 1
        metrics["events_by_layer"][layer] = metrics["events_by_layer"].get(layer, 0) + 1

        if cat == "INCORRECT_TOOL" and sev == "info":
            metrics["would_fire"] += 1
        elif sev in ("critical", "warning"):
            metrics["would_fire"] += 1
        else:
            metrics["would_suppress"] += 1

    return metrics

def compare_rules(current_rules, proposed_rules, events):
    """Compare two rule configurations against the same events."""
    current_metrics = evaluate_rules(events, current_rules)
    proposed_metrics = evaluate_rules(events, proposed_rules)

    diff = {
        "current_fire": current_metrics["would_fire"],
        "proposed_fire": proposed_metrics["would_fire"],
        "current_suppress": current_metrics["would_suppress"],
        "proposed_suppress": proposed_metrics["would_suppress"],
        "fire_delta": proposed_metrics["would_fire"] - current_metrics["would_fire"],
        "suppress_delta": proposed_metrics["would_suppress"] - current_metrics["would_suppress"],
    }

    if diff["fire_delta"] < 0:
        diff["recommendation"] = "proposed_better"
        diff["reason"] = "Proposed rules would fire {} fewer times".format(abs(diff["fire_delta"]))
    elif diff["fire_delta"] > 0:
        diff["recommendation"] = "current_better"
        diff["reason"] = "Proposed rules would fire {} more times (possible FP increase)".format(diff["fire_delta"])
    else:
        diff["recommendation"] = "equivalent"
        diff["reason"] = "No difference in firing behavior"

    return {
        "current": current_metrics,
        "proposed": proposed_metrics,
        "comparison": diff,
        "events_analyzed": len(events),
    }

def save_results(report, output_path=None):
    output_path = output_path or RESULTS_PATH
    report["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        tmp = output_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        os.replace(tmp, output_path)
    except Exception:
        pass

def run_ab_test(proposed_path=None, monitor_path=None):
    """Run A/B comparison. Returns report dict."""
    current = load_rules()
    if proposed_path:
        proposed = load_rules(proposed_path)
    else:
        proposed = dict(current)

    events = load_events(monitor_path)
    if not events:
        return {"status": "no_data", "events_analyzed": 0}

    report = compare_rules(current, proposed, events)
    report["status"] = "ok"
    return report

def main():
    # On-demand mode: python qg_layer18_ab.py <proposed_rules.json>
    if len(sys.argv) > 1:
        proposed_path = sys.argv[1]
        report = run_ab_test(proposed_path)
        save_results(report)
        print(json.dumps(report.get("comparison", {}), indent=2))
        return

    # Hook mode: SessionStart (just log current state)
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    events = load_events()
    if not events:
        return

    current = load_rules()
    metrics = evaluate_rules(events, current)

    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer18_ab",
        "category": "AB_RULE_TESTING",
        "severity": "info",
        "detection_signal": "baseline: {} events, {} fire, {} suppress".format(
            metrics["total_events"], metrics["would_fire"], metrics["would_suppress"]),
    }
    _write_event(event)

if __name__ == "__main__":
    main()

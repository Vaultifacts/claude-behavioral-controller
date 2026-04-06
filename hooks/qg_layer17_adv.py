#!/usr/bin/env python3
"""Layer 17 -- Adversarial Self-Testing (SessionStart)."""
import json, os, sys, tempfile, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
RESULTS_PATH = os.path.expanduser("~/.claude/qg-adversarial-results.json")
RUN_INTERVAL = 86400

def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass

def _should_run():
    if not os.path.exists(RESULTS_PATH):
        return True
    try:
        return (time.time() - os.path.getmtime(RESULTS_PATH)) > RUN_INTERVAL
    except Exception:
        return True

def _write_temp(content, suffix=".py"):
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path

def _cleanup(paths):
    for p in paths:
        try: os.remove(p)
        except Exception: pass

def test_layer28_security():
    try:
        from qg_layer28 import check_security
    except ImportError:
        return [("skip", "layer28 not importable")]
    results, temps = [], []
    p = _write_temp("q = f" + chr(34) + "SELECT * FROM users WHERE id={uid}" + chr(34) + chr(10))
    temps.append(p)
    results.append(("pass" if check_security(p) else "FAIL", "SQL f-string"))
    p = _write_temp("el.inner" + "HTML = userInput" + chr(10), suffix=".js")
    temps.append(p)
    results.append(("pass" if check_security(p) else "FAIL", "XSS"))
    p = _write_temp("obj = pickle.loads(data)" + chr(10))
    temps.append(p)
    results.append(("pass" if check_security(p) else "FAIL", "pickle"))
    p = _write_temp("# SELECT * FROM x WHERE id={v}" + chr(10) + "def safe(): pass" + chr(10))
    temps.append(p)
    results.append(("pass" if not check_security(p) else "FAIL", "comment FP"))
    _cleanup(temps)
    return results

def test_layer12_satisfaction():
    try:
        from qg_layer12 import classify_sentiment
    except ImportError:
        return [("skip", "layer12 not importable")]
    results = []
    cat, _, _ = classify_sentiment("No, that is completely wrong")
    results.append(("pass" if cat == "frustration" else "FAIL", "frustration"))
    cat, _, _ = classify_sentiment("Perfect, thanks!")
    results.append(("pass" if cat == "satisfaction" else "FAIL", "satisfaction"))
    cat, _, _ = classify_sentiment("Add a login page")
    results.append(("pass" if cat == "neutral" else "FAIL", "neutral"))
    return results

def test_layer11_commits():
    try:
        from qg_layer11 import check_commit_message, check_staged_files
    except ImportError:
        return [("skip", "layer11 not importable")]
    results = []
    results.append(("pass" if not check_commit_message("[AUTO] feat: add login") else "FAIL", "valid commit"))
    results.append(("pass" if check_commit_message("updated stuff") else "FAIL", "invalid commit"))
    results.append(("pass" if check_staged_files([".env"]) else "FAIL", ".env blocked"))
    return results

def test_layer29_semantics():
    try:
        from qg_layer29 import check_claim_action, check_count_claims
    except ImportError:
        return [("skip", "layer29 not importable")]
    results = []
    issues = check_claim_action("I added error handling", "try:" + chr(10) + "    x()" + chr(10) + "except:" + chr(10) + "    pass")
    results.append(("pass" if not issues else "FAIL", "claim with evidence"))
    issues = check_claim_action("I added error handling", "def foo(): return 1")
    results.append(("pass" if issues else "FAIL", "unsubstantiated claim"))
    return results

ALL_TEST_SUITES = [
    ("layer28_security", test_layer28_security),
    ("layer12_satisfaction", test_layer12_satisfaction),
    ("layer11_commits", test_layer11_commits),
    ("layer29_semantics", test_layer29_semantics),
]

def run_all_tests():
    all_results = {}
    total_pass = total_fail = total_skip = 0
    for suite_name, test_fn in ALL_TEST_SUITES:
        try:
            results = test_fn()
        except Exception as e:
            results = [("error", str(e)[:100])]
        sp = sum(1 for s, _ in results if s == "pass")
        sf = sum(1 for s, _ in results if s == "FAIL")
        ss_ = sum(1 for s, _ in results if s in ("skip", "error"))
        total_pass += sp; total_fail += sf; total_skip += ss_
        all_results[suite_name] = {"results": [{"status": s, "test": t} for s, t in results], "pass": sp, "fail": sf, "skip": ss_}
    blind = [r["test"] for suite in all_results.values() for r in suite["results"] if r["status"] == "FAIL"]
    return {"suites": all_results, "total_pass": total_pass, "total_fail": total_fail, "total_skip": total_skip, "blind_spots": blind}

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

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not _should_run():
        return
    report = run_all_tests()
    save_results(report)
    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    event = {"event_id": str(uuid.uuid4()), "ts": ts, "session_uuid": state.get("session_uuid") or "", "working_dir": os.getcwd(), "layer": "layer17_adv", "category": "ADVERSARIAL_SELF_TEST", "severity": "warning" if report["total_fail"] > 0 else "info", "detection_signal": "pass={} fail={} blind_spots={}".format(report["total_pass"], report["total_fail"], len(report["blind_spots"]))}
    _write_event(event)
    if report["total_fail"] > 0:
        tlines = ["[Layer 17] BLIND SPOTS: {} failures".format(report["total_fail"])]
        for bs in report["blind_spots"][:5]:
            tlines.append("  - " + bs)
        text = chr(10).join(tlines)
    else:
        text = "[Layer 17] Self-test: {}/{} pass, 0 blind spots".format(report["total_pass"], report["total_pass"] + report["total_skip"])
    out = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    print(json.dumps(out))

if __name__ == "__main__":  # pragma: no cover
    main()

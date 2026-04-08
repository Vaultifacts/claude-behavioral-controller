#!/usr/bin/env python3
"""
qg-serve.py — Local HTTP bridge for the QG Dashboard.
Reads local log/state files and serves them to the browser dashboard.
Run: python ~/.claude/scripts/qg-serve.py
Dashboard fetches: http://localhost:7821/monitor
"""
import json, os, sys, datetime, re
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 7821
CLAUDE_DIR = os.path.join(os.path.expanduser('~'), '.claude')

def read_jsonl(path, limit=None):
    lines = []
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except Exception:
                    pass
    except OSError:
        pass
    if limit:
        return lines[-limit:]
    return lines

def get_monitor_data():
    now = datetime.datetime.now()
    cutoff_7d = now - datetime.timedelta(days=7)
    cutoff_24h = now - datetime.timedelta(hours=24)
    result = {}

    # ── quality-gate.log ──
    log_path = os.path.join(CLAUDE_DIR, 'quality-gate.log')
    passes = blocks = 0
    try:
        with open(log_path, encoding='utf-8', errors='replace') as f:
            for line in f:
                if '| PASS  |' in line:
                    passes += 1
                elif '| BLOCK |' in line:
                    blocks += 1
    except OSError:
        pass
    result['gate_log'] = {
        'passes': passes,
        'blocks': blocks,
        'total': passes + blocks,
        'block_rate_pct': round(blocks / (passes + blocks) * 100, 1) if (passes + blocks) > 0 else 0,
        'gate_log_block_count': blocks,
    }

    # ── qg-monitor.jsonl — event breakdown ──
    events = read_jsonl(os.path.join(CLAUDE_DIR, 'qg-monitor.jsonl'))
    cat_counts = {}
    layer_counts = {}
    recent_events = []
    precheck_cats = {}
    satisfaction_scores = []
    for e in events:
        cat = e.get('category', '?')
        layer = e.get('layer', '?')
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        layer_counts[layer] = layer_counts.get(layer, 0) + 1
        ts_str = e.get('ts', '')
        try:
            ts = datetime.datetime.fromisoformat(ts_str.replace('Z', ''))
            if ts > cutoff_24h:
                recent_events.append(e)
        except Exception:
            pass
        if e.get('layer') == 'precheck':
            pc = e.get('category', '?')
            precheck_cats[pc] = precheck_cats.get(pc, 0) + 1
        if e.get('layer') == 'layer12':
            sc = e.get('satisfaction_score')
            if sc is not None:
                try:
                    satisfaction_scores.append(int(sc))
                except (TypeError, ValueError):
                    pass

    # Build behavior summary (L2 categories = the "bad behavior" detectors)
    l2_cats = ['INCORRECT_TOOL', 'ERROR_IGNORED', 'LAZINESS', 'LOOP_DETECTED',
                'INCOMPLETE_COVERAGE', 'OUTPUT_UNVALIDATED', 'MEMORY_OVER_VERIFICATION', 'SCOPE_CREEP']
    behavior_summary = {c: cat_counts.get(c, 0) for c in l2_cats}

    # Recent 24h behavior
    recent_behavior = {}
    for e in recent_events:
        cat = e.get('category', '?')
        if cat in l2_cats:
            recent_behavior[cat] = recent_behavior.get(cat, 0) + 1

    # precheck category aggregation
    precheck_total = sum(precheck_cats.values())
    precheck_result = {'total': precheck_total}
    precheck_result.update(precheck_cats)

    # layer12 satisfaction aggregation
    sat_total = len(satisfaction_scores)
    sat_dist = {}
    for sc in satisfaction_scores:
        sat_dist[sc] = sat_dist.get(sc, 0) + 1
    sat_positive = sum(1 for sc in satisfaction_scores if sc > 0)
    sat_negative = sum(1 for sc in satisfaction_scores if sc < 0)
    sat_neutral = sum(1 for sc in satisfaction_scores if sc == 0)

    result['monitor'] = {
        'total_events': len(events),
        'behavior_alltime': behavior_summary,
        'behavior_24h': recent_behavior,
        'hallucinations': cat_counts.get('HALLUCINATION_DETECTED', 0),
        'security_issues': cat_counts.get('SECURITY_VULNERABILITY', 0),
        'rule_suggestions': cat_counts.get('RULE_SUGGESTION', 0),
        'recovery_tp': cat_counts.get('RECOVERY_TP', 0),
        'recovery_fn': cat_counts.get('RECOVERY_FN', 0),
        'precheck_categories': precheck_result,
        'satisfaction': {
            'total': sat_total,
            'net_score': sum(satisfaction_scores),
            'score_dist': sat_dist,
            'positive': sat_positive,
            'negative': sat_negative,
            'neutral': sat_neutral,
        },
    }

    # Severity breakdown from all events
    severity_counts = {'critical': 0, 'warning': 0, 'warn': 0, 'info': 0, 'low': 0}
    for e in events:
        s = e.get('severity', '')
        if s in severity_counts:
            severity_counts[s] = severity_counts.get(s, 0) + 1
    result['monitor']['severity'] = {
        'critical': severity_counts.get('critical', 0),
        'warning': severity_counts.get('warning', 0) + severity_counts.get('warn', 0),
        'info': severity_counts.get('info', 0) + severity_counts.get('low', 0),
    }

    # Daily event counts last 7 days
    daily_evts = {}
    for e in events:
        try:
            ts = datetime.datetime.fromisoformat(e.get('ts', '').replace('Z', ''))
            if ts > cutoff_7d:
                day = ts.strftime('%Y-%m-%d')
                daily_evts[day] = daily_evts.get(day, 0) + 1
        except Exception:
            pass
    result['monitor']['daily_events'] = [
        {'day': k, 'count': v}
        for k, v in sorted(daily_evts.items())
    ]

    # Top layers by event count
    layer_counts_list = sorted(layer_counts.items(), key=lambda x: -x[1])[:10]
    result['monitor']['top_layers'] = [
        {'layer': k, 'count': v} for k, v in layer_counts_list
    ]

    # Recent critical events (last 15)
    recent_criticals = []
    for e in events:
        if e.get('severity') == 'critical':
            recent_criticals.append({
                'ts': e.get('ts', ''),
                'layer': e.get('layer', ''),
                'category': e.get('category', ''),
                'signal': (e.get('detection_signal') or '')[:120],
            })
    result['monitor']['recent_criticals'] = recent_criticals[-15:]

    # ── qg-cross-session.json ──
    cross_path = os.path.join(CLAUDE_DIR, 'qg-cross-session.json')
    try:
        with open(cross_path, encoding='utf-8') as f:
            cross = json.load(f)
        patterns = cross.get('patterns', [])
        # Keep top 5 patterns
        result['cross_session'] = {
            'sessions_analyzed': cross.get('sessions_analyzed', 0),
            'patterns': patterns[:5],
        }
    except (OSError, json.JSONDecodeError):
        result['cross_session'] = {'sessions_analyzed': 0, 'patterns': []}

    # ── qg-session-state.json ──
    state_path = os.path.join(CLAUDE_DIR, 'qg-session-state.json')
    try:
        with open(state_path, encoding='utf-8') as f:
            state = json.load(f)
        result['session'] = {
            'eval_count': state.get('layer3_evaluation_count', 0),
            'warnings_ignored': state.get('layer15_warnings_ignored_count', 0),
            'unresolved_events': len(state.get('layer2_unresolved_events', [])),
            'elevated_scrutiny': state.get('layer2_elevated_scrutiny', False),
            'active_task': (state.get('active_task_description') or '')[:120],
            'mismatch_count': state.get('layer17_mismatch_count', 0),
        }
    except (OSError, json.JSONDecodeError):
        result['session'] = {}

    # ── qg-quarantine.jsonl ──
    quarantine = read_jsonl(os.path.join(CLAUDE_DIR, 'qg-quarantine.jsonl'))
    result['integrity'] = {
        'quarantine_count': len(quarantine),
        'monitor_total_lines': len(events),
    }

    # ── quality-gate-overrides.jsonl ──
    try:
        overrides = read_jsonl(os.path.join(CLAUDE_DIR, 'quality-gate-overrides.jsonl'))
        by_cat = {}
        tp_count = fp_count = 0
        for ov in overrides:
            v = ov.get('auto_verdict', '')
            if v == 'likely_tp':
                tp_count += 1
            elif v == 'likely_fp':
                fp_count += 1
            cat = ov.get('block_category', '?')
            by_cat[cat] = by_cat.get(cat, 0) + 1
        recent_ov = [
            {
                'ts': ov.get('ts', ''),
                'block_reason': (ov.get('block_reason') or '')[:200],
                'auto_verdict': ov.get('auto_verdict', ''),
                'gap_sec': ov.get('gap_sec', 0),
            }
            for ov in overrides[-5:]
        ]
        result['overrides'] = {
            'total': len(overrides),
            'likely_tp': tp_count,
            'likely_fp': fp_count,
            'by_category': by_cat,
            'recent': recent_ov,
        }
    except Exception:
        result['overrides'] = {}

    # ── session history (qg-session-history.md) ──
    try:
        hist_path = os.path.join(CLAUDE_DIR, 'qg-session-history.md')
        with open(hist_path, encoding='utf-8', errors='replace') as f:
            hist_text = f.read()
        sessions = []
        for block in re.split(r'(?=## Session )', hist_text):
            block = block.strip()
            if not block.startswith('## Session '):
                continue
            date_m = re.search(r'## Session ([\dT:\-]+)', block)
            qs_m = re.search(r'quality_score:\s*([\d.]+)', block)
            tp_m = re.search(r'TP:\s*(\d+)', block)
            fp_m = re.search(r'FP:\s*(\d+)', block)
            fn_m = re.search(r'FN:\s*(\d+)', block)
            tn_m = re.search(r'TN:\s*(\d+)', block)
            if date_m:
                sessions.append({
                    'date': date_m.group(1),
                    'quality_score': float(qs_m.group(1)) if qs_m else 0.0,
                    'tp': int(tp_m.group(1)) if tp_m else 0,
                    'fp': int(fp_m.group(1)) if fp_m else 0,
                    'fn': int(fn_m.group(1)) if fn_m else 0,
                    'tn': int(tn_m.group(1)) if tn_m else 0,
                })
        total_s = len(sessions)
        avg_q = round(sum(s['quality_score'] for s in sessions) / total_s, 3) if total_s else 0.0
        max_q = max((s['quality_score'] for s in sessions), default=0.0)
        total_tp = sum(s['tp'] for s in sessions)
        total_fp = sum(s['fp'] for s in sessions)
        result['session_history'] = {
            'sessions': sessions,
            'total': total_s,
            'avg_quality': avg_q,
            'max_quality': max_q,
            'total_tp': total_tp,
            'total_fp': total_fp,
        }
    except Exception:
        result['session_history'] = {}

    return result


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ('/monitor', '/monitor/'):
            data = get_monitor_data()
            self._json(data)
        elif self.path in ('/health', '/health/'):
            self._json({'ok': True})
        else:
            self.send_response(404)
            self._cors()
            self.end_headers()

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, data):
        body = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # suppress per-request logging


if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', PORT), Handler)
    print(f'QG local server running on http://localhost:{PORT}')
    print('Keep this window open while using the dashboard.')
    print('Press Ctrl+C to stop.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nStopped.')

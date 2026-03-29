"""
qg-feedback.py — Quality gate feedback CLI.
Usage via alias: qg fp | tp | miss | report | failures | failures add | trend | precision | scan

  qg fp                  — Mark the most recent override as a confirmed false positive
  qg tp                  — Mark the most recent override as a confirmed true positive
  qg miss                — Record a false negative (gate missed something it should have blocked)
  qg report              — Run quality-gate-analyst.py and print the results
  qg failures            — Show notable block patterns from the most recent session
  qg failures add "desc"       — Record a new systemic failure to quality-gate-failures.md
  qg failures close N "reason" — Mark the Nth Open entry as Resolved with reason
  qg milestone "desc"    — Record a fix deployment milestone in quality-gate.log
  qg trend [N]           — Show block-rate trend across last N sessions (default 10)
  qg precision           — Estimate precision per category using override records as FP signal
  qg scan                — Scan recent PASS entries for structural false-negative signals
  qg weekly              — Compare this week's quality gate metrics against last week
  qg coverage            — Show which quality-gate.py branches have smoke test coverage
"""
import sys
import os
import json
import re
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict, Counter

CLAUDE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
OVERRIDES_PATH = f'{CLAUDE_DIR}/quality-gate-overrides.jsonl'
FEEDBACK_PATH = f'{CLAUDE_DIR}/quality-gate-feedback.jsonl'
LOG_PATH = f'{CLAUDE_DIR}/quality-gate.log'
ANALYST_PATH = f'{CLAUDE_DIR}/scripts/quality-gate-analyst.py'
FAILURES_PATH = f'{CLAUDE_DIR}/quality-gate-failures.md'
COVERAGE_SNAPSHOT = f'{CLAUDE_DIR}/qg-coverage-snapshot.json'
SESSION_GAP_SEC = 7200  # 2 hour gap between entries = new session boundary
SHORT_INPUT_RE = re.compile(
    r'^(\d{1,2}|do it|do that|do this|go ahead|proceed|yes do it|ok do it|go)[\s.!]*$',
    re.IGNORECASE
)


def read_last_override():
    if not os.path.exists(OVERRIDES_PATH):
        return None
    try:
        with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
            lines = [l.strip() for l in f if l.strip()]
        if not lines:
            return None
        return json.loads(lines[-1])
    except Exception:
        return None


def read_last_pass():
    """Read the most recent PASS entry from quality-gate.log for 'miss' feedback."""
    if not os.path.exists(LOG_PATH):
        return None, None
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in reversed(lines[-200:]):
            line = line.rstrip()
            if 'subagent:' in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) >= 2 and parts[1].strip() == 'PASS':
                ts = parts[0].strip()
                req = ''
                for part in parts[3:]:
                    if part.startswith('req='):
                        req = part[4:]
                        break
                return ts, req
    except Exception:
        pass
    return None, None


def write_feedback(record):
    try:
        with open(FEEDBACK_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
    except Exception as e:
        print(f'Error writing feedback: {e}', file=sys.stderr)
        sys.exit(1)


def cmd_fp():
    override = read_last_override()
    if not override:
        print('No override records found. Run a session that triggers a BLOCK->PASS cycle first.')
        sys.exit(1)
    record = {
        'ts': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'type': 'fp',
        'override_ts': override.get('ts', ''),
        'user_request': override.get('user_request', ''),
        'block_reason': override.get('block_reason', ''),
        'auto_verdict': override.get('auto_verdict', ''),
    }
    write_feedback(record)
    print(f"Marked as FALSE POSITIVE: \"{override.get('user_request','')[:60]}\"")
    print(f"Block reason was: {override.get('block_reason','')[:80]}")


def cmd_tp():
    override = read_last_override()
    if not override:
        print('No override records found.')
        sys.exit(1)
    record = {
        'ts': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'type': 'tp',
        'override_ts': override.get('ts', ''),
        'user_request': override.get('user_request', ''),
        'block_reason': override.get('block_reason', ''),
        'auto_verdict': override.get('auto_verdict', ''),
    }
    write_feedback(record)
    print(f"Marked as TRUE POSITIVE: \"{override.get('user_request','')[:60]}\"")


def cmd_miss():
    pass_ts, req = read_last_pass()
    record = {
        'ts': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'type': 'miss',
        'pass_ts': pass_ts or '',
        'user_request': req or '',
    }
    write_feedback(record)
    print(f"Recorded FALSE NEGATIVE (missed block) for: \"{(req or 'unknown')[:60]}\"")


def cmd_report():
    if not os.path.exists(ANALYST_PATH):
        print(f'Analyst not found: {ANALYST_PATH}')
        sys.exit(1)
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    subprocess.run([sys.executable, ANALYST_PATH], env=env)


def parse_log_entries():
    """Parse all quality-gate.log entries including subagents. Returns list of dicts."""
    if not os.path.exists(LOG_PATH):
        return []
    entries = []
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            line = line.rstrip()
            if not line:
                continue
            is_subagent = 'subagent:' in line
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 4:
                continue
            ts_str = parts[0]
            decision = parts[1]
            if decision not in ('PASS', 'BLOCK', 'DEGRADED-PASS'):
                continue
            reason = parts[3]
            category = reason.split(':')[0].strip() if ':' in reason else 'MECHANICAL'
            tools = req = hash_val = ''
            for part in parts[4:]:
                if part.startswith('tools='):
                    tools = part[6:]
                elif part.startswith('req='):
                    req = part[4:]
                elif part.startswith('hash='):
                    hash_val = part[5:]
            try:
                ts_dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
            entries.append({
                'ts': ts_dt, 'decision': decision, 'reason': reason,
                'category': category, 'tools': tools, 'req': req, 'hash': hash_val,
                'short_input': bool(SHORT_INPUT_RE.match(req.strip())),
                'is_subagent': is_subagent,
            })
    except Exception:
        pass
    return entries


# Seed list of known smoke test fixture req strings — catches fixtures that haven't
# yet reached >= 3 occurrences in the current log (e.g. after log rotation/clear).
# Dynamic req-frequency detection (below) auto-discovers new fixtures over time.
_SMOKE_REQS_SEED = frozenset([
    'Fix the auth bug', 'Fix two files', 'Fix the bug', 'Fix the CSS layout',
    'Fix all 5 bugs: auth timeout, CSRF bypass, SQL injection, XS',
    'Run the migration',
    'Update memory/STATUS.md to record that auth refactor is comp',
    'What time is it?',
])


def filter_smoke_tests(entries):
    """Remove smoke test entries. Returns (filtered, smoke_count).

    Three-layer filter:
      1. Hash frequency >= 3 — same response content repeated (primary filter)
      2. Req frequency >= 3 — same user request repeated (catches fingerprint-split hashes)
      3. Seed list — known fixture reqs for fresh logs with < 3 occurrences yet
    """
    freq = {}
    req_freq = {}
    for e in entries:
        h = e['hash']
        if h and h != '--------':
            freq[h] = freq.get(h, 0) + 1
        r = (e.get('req') or '').strip()
        if r:
            req_freq[r] = req_freq.get(r, 0) + 1
    dynamic_smoke_reqs = {r for r, cnt in req_freq.items() if cnt >= 3}

    def _is_smoke(e):
        if e['hash'] and e['hash'] != '--------' and freq.get(e['hash'], 0) >= 3:
            return True
        req = (e.get('req') or '').strip()
        if req in dynamic_smoke_reqs:
            return True
        return any(req.startswith(s) for s in _SMOKE_REQS_SEED)
    filtered = [e for e in entries if not _is_smoke(e)]
    return filtered, len(entries) - len(filtered)


def detect_sessions(entries):
    """Group entries into sessions separated by SESSION_GAP_SEC gaps."""
    if not entries:
        return []
    sorted_entries = sorted(entries, key=lambda e: e['ts'])
    sessions = [[sorted_entries[0]]]
    for entry in sorted_entries[1:]:
        gap = (entry['ts'] - sessions[-1][-1]['ts']).total_seconds()
        if gap > SESSION_GAP_SEC:
            sessions.append([entry])
        else:
            sessions[-1].append(entry)
    return sessions


def find_notable_patterns(session):
    """Find notable block patterns in a session."""
    blocks = [e for e in session if e['decision'] == 'BLOCK']
    by_cat = defaultdict(list)
    for b in blocks:
        by_cat[b['category']].append(b)
    repeated = {cat: es for cat, es in by_cat.items() if len(es) >= 2}
    no_tool = [b for b in blocks if b['tools'] in ('-', '')]
    compliance = [b for b in blocks if b['req'].startswith('Stop hook feedback:')]
    overridden = []
    if os.path.exists(OVERRIDES_PATH):
        try:
            with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
                override_hashes = {json.loads(l).get('response_hash', '') for l in f if l.strip()}
            overridden = [b for b in blocks if b['hash'] and b['hash'] in override_hashes]
        except Exception:
            pass
    return {'repeated': repeated, 'no_tool': no_tool, 'compliance': compliance, 'overridden': overridden}


def cmd_failures():
    """Show notable block patterns from the most recent session."""
    entries = parse_log_entries()
    if not entries:
        print('No log data found.')
        return
    filtered, smoke_count = filter_smoke_tests(entries)
    if not filtered:
        print(f'No real session data ({smoke_count} smoke test entries filtered).')
        return
    sessions = detect_sessions(filtered)
    session = sessions[-1]
    blocks = [e for e in session if e['decision'] == 'BLOCK']
    ts_start = session[0]['ts'].strftime('%Y-%m-%d %H:%M')
    ts_end = session[-1]['ts'].strftime('%H:%M')
    total = len(session)
    block_count = len(blocks)
    block_rate = block_count / total * 100 if total else 0
    print(f'=== Session Failures: {ts_start} — {ts_end} ===')
    print(f'{total} evaluations ({block_count} blocks, {total - block_count} pass) — {block_rate:.0f}% block rate')
    if smoke_count:
        print(f'Smoke test entries filtered: {smoke_count}')
    if not blocks:
        print('\nNo blocks in this session.')
    else:
        patterns = find_notable_patterns(session)
        idx = 1
        if patterns['repeated']:
            for cat, es in sorted(patterns['repeated'].items(), key=lambda x: -len(x[1])):
                print(f'\n[{idx}] Repeated {cat} ({len(es)}x)')
                for b in es:
                    print(f'    {b["ts"].strftime("%H:%M:%S")} | tools={b["tools"]} | "{b["reason"][:60]}..."')
                idx += 1
        if patterns['no_tool']:
            print(f'\n[{idx}] No-tool blocks ({len(patterns["no_tool"])}x)')
            for b in patterns['no_tool']:
                print(f'    {b["ts"].strftime("%H:%M:%S")} | "{b["reason"][:60]}..."')
            idx += 1
        if patterns['compliance']:
            print(f'\n[{idx}] Compliance retries blocked ({len(patterns["compliance"])}x)')
            for b in patterns['compliance']:
                print(f'    {b["ts"].strftime("%H:%M:%S")} | "{b["req"][:70]}..."')
            idx += 1
        if patterns['overridden']:
            print(f'\n[{idx}] Overridden blocks ({len(patterns["overridden"])}x)')
            for b in patterns['overridden']:
                print(f'    {b["ts"].strftime("%H:%M:%S")} | "{b["reason"][:60]}..."')
            idx += 1
        if idx == 1:
            print('\nNo notable patterns found.')
    # Subagent summary
    sub_entries = [e for e in session if e.get('is_subagent')]
    sub_blocks = [e for e in sub_entries if e['decision'] == 'BLOCK']
    if sub_entries:
        sub_rate = len(sub_blocks) / len(sub_entries) * 100
        print('\n[subagent] %d/%d blocks (%.0f%%) from subagents' % (len(sub_blocks), len(sub_entries), sub_rate))
    # Degraded evaluations
    degraded = [e for e in session if e['decision'] == 'DEGRADED-PASS']
    if degraded:
        print('\n[degraded] %d degraded evaluations (Haiku API failure) -- treat as unverified PASS' % len(degraded))
    # Short-input analysis vs 25% target
    si_evals = [e for e in session if e.get('short_input')]
    si_blocks = [e for e in si_evals if e['decision'] == 'BLOCK']
    if si_evals:
        si_rate = len(si_blocks) / len(si_evals) * 100
        marker = ' -- ABOVE TARGET' if si_rate >= 25 else ' -- on target'
        print(f'\n[short-input] {len(si_blocks)}/{len(si_evals)} blocks ({si_rate:.0f}%) on short inputs -- target <25%{marker}')
    print(f'\nFailures log: {FAILURES_PATH}')
    print('To record: qg failures add "description of systemic gap"')


def cmd_failures_add(description):
    """Record a new systemic failure to quality-gate-failures.md."""
    entries = parse_log_entries()
    filtered, _ = filter_smoke_tests(entries)
    sessions = detect_sessions(filtered) if filtered else []
    date_str = datetime.now().strftime('%Y-%m-%d')
    if sessions:
        session = sessions[-1]
        blocks = [e for e in session if e['decision'] == 'BLOCK']
        ts_start = session[0]['ts'].strftime('%H:%M')
        ts_end = session[-1]['ts'].strftime('%H:%M')
        total = len(session)
        block_count = len(blocks)
        block_rate = block_count / total * 100 if total else 0
        cat_counts = Counter(b['category'] for b in blocks)
        top_cats = ', '.join(f'{cat} ({n})' for cat, n in cat_counts.most_common(3)) or '(none)'
        session_str = f'{ts_start} — {ts_end} ({block_count} blocks / {total} evals, {block_rate:.0f}% block rate)'
    else:
        session_str = '(no session data)'
        top_cats = '(unknown)'
    entry = (
        f'\n## {date_str}: {description}\n'
        f'- **Session**: {session_str}\n'
        f'- **Top categories**: {top_cats}\n'
        f'- **Status**: Open\n'
    )
    header = (
        '# Quality Gate — Systemic Failures Log\n'
        '_Entries added via `qg failures add`. Review periodically to track fix effectiveness._\n'
    )
    if not os.path.exists(FAILURES_PATH):
        with open(FAILURES_PATH, 'w', encoding='utf-8') as f:
            f.write(header)
    with open(FAILURES_PATH, 'a', encoding='utf-8') as f:
        f.write(entry)
    print(f'Recorded: {description[:60]}')
    print(f'Written to: {FAILURES_PATH}')


def cmd_failures_close(n, reason):
    """Update the Nth Open entry in quality-gate-failures.md to Resolved."""
    if not os.path.exists(FAILURES_PATH):
        print('No failures log found.')
        return
    with open(FAILURES_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
    open_entries = []
    for i, m in enumerate(re.finditer(r'(- \*\*Status\*\*: Open)', content)):
        open_entries.append((i + 1, m.start(), m.end()))
    if not open_entries:
        print('No Open entries found.')
        return
    print(f'Open entries ({len(open_entries)}):')
    lines = content.split('\n')
    for idx, start, _ in open_entries:
        # Find the ## header before this Status line
        before = content[:start]
        header = before.rfind('\n## ')
        title = before[header+4:].split('\n')[0][:70] if header >= 0 else '?'
        print(f'  {idx}. {title}')
    if n < 1 or n > len(open_entries):
        print(f'Invalid entry number: {n} (1-{len(open_entries)})')
        return
    _, start, end = open_entries[n - 1]
    date_str = datetime.now().strftime('%Y-%m-%d')
    new_status = f'- **Status**: Resolved {date_str} — {reason}'
    content = content[:start] + new_status + content[end:]
    with open(FAILURES_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'\nClosed entry {n}: {reason[:60]}')


def _detect_compliance(session, blocks):
    compliance = [b for b in blocks if b['req'].startswith('Stop hook feedback:')]
    if len(compliance) >= 3:
        return True, f"Compliance retry failure: {len(compliance)} retries after gate blocks were themselves blocked", 'compliance-retry'
    return False, '', ''


def _detect_dominant_category(blocks):
    if len(blocks) < 5:
        return False, '', ''
    cat_counts = Counter(b['category'] for b in blocks)
    for cat, count in cat_counts.most_common(1):
        pct = count / len(blocks) * 100
        if pct >= 60 and count >= 5:
            return True, f"Dominant {cat} blocks: {pct:.0f}% of all blocks ({count}/{len(blocks)})", f'dominant-{cat.lower()}'
    return False, '', ''


def _detect_high_block_rate(session, blocks, block_rate):
    if len(session) >= 15 and block_rate >= 40:
        return True, f"High block rate: {block_rate:.0f}% ({len(blocks)}/{len(session)})", 'high-block-rate'
    return False, '', ''


def _detect_short_input_rate(session, blocks):
    si_evals = [e for e in session if e.get('short_input')]
    si_blocks = [e for e in si_evals if e['decision'] == 'BLOCK']
    if len(si_evals) < 3:
        return False, '', ''
    si_rate = len(si_blocks) / len(si_evals) * 100
    if si_rate >= 25:
        return True, f"Short-input block rate: {si_rate:.0f}% ({len(si_blocks)}/{len(si_evals)}) — target <25%", 'short-input-rate'
    return False, '', ''


def _detect_no_tool_dominance(blocks):
    if len(blocks) < 5:
        return False, '', ''
    no_tool = [b for b in blocks if b['tools'] in ('-', '')]
    pct = len(no_tool) / len(blocks) * 100
    if pct >= 70 and len(no_tool) >= 5:
        return True, f"No-tool blocks dominant: {pct:.0f}% of blocks ({len(no_tool)}/{len(blocks)}) had no tool usage", 'no-tool-dominance'
    return False, '', ''


def _detect_degraded_rate(session):
    total = len(session)
    if total < 10:
        return False, '', ''
    degraded = [e for e in session if e['decision'] == 'DEGRADED-PASS']
    pct = len(degraded) / total * 100
    if pct >= 5 and len(degraded) >= 3:
        return True, f"Degraded eval rate: {pct:.0f}% ({len(degraded)}/{total}) — Haiku API failures, target <5%", 'degraded-rate'
    return False, '', ''


def _extract_key_from_description(desc):
    desc_lower = desc.lower().replace('[auto] ', '')
    if desc_lower.startswith('compliance retry'):
        return 'compliance-retry'
    if desc_lower.startswith('dominant '):
        cat = desc_lower.split()[1]
        return f'dominant-{cat}'
    if desc_lower.startswith('high block rate'):
        return 'high-block-rate'
    if desc_lower.startswith('no-tool blocks'):
        return 'no-tool-dominance'
    if desc_lower.startswith('short-input block rate'):
        return 'short-input-rate'
    if desc_lower.startswith('parser divergence'):
        return 'parser-divergence'
    if desc_lower.startswith('degraded eval rate'):
        return 'degraded-rate'
    return None


def _load_recent_failure_keys(days=3):
    if not os.path.exists(FAILURES_PATH):
        return set()
    cutoff = datetime.now() - timedelta(days=days)
    keys = set()
    try:
        with open(FAILURES_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                m = re.match(r'^## (\d{4}-\d{2}-\d{2}): (.+)$', line.rstrip())
                if m:
                    try:
                        entry_date = datetime.strptime(m.group(1), '%Y-%m-%d')
                    except ValueError:
                        continue
                    if entry_date >= cutoff:
                        key = _extract_key_from_description(m.group(2))
                        if key:
                            keys.add(key)
    except Exception:
        pass
    return keys


def cmd_auto_detect():
    entries = parse_log_entries()
    if not entries:
        return
    filtered, _ = filter_smoke_tests(entries)
    if not filtered:
        return
    sessions = detect_sessions(filtered)
    if not sessions:
        return
    session = sessions[-1]
    blocks = [e for e in session if e['decision'] == 'BLOCK']
    total = len(session)
    if total < 10:
        return
    block_rate = len(blocks) / total * 100

    detectors = [
        _detect_compliance(session, blocks),
        _detect_dominant_category(blocks),
        _detect_high_block_rate(session, blocks, block_rate),
        _detect_no_tool_dominance(blocks),
        _detect_short_input_rate(session, blocks),
        _detect_degraded_rate(session),
    ]
    triggered = [(ok, desc, key) for ok, desc, key in detectors if ok]
    if not triggered:
        return

    recent_keys = _load_recent_failure_keys(days=3)
    for _, desc, key in triggered:
        if key not in recent_keys:
            cmd_failures_add(f'[AUTO] {desc}')
            recent_keys.add(key)

    # Print for session recall snapshot
    print('[auto-detect] Patterns detected this session:')
    for _, desc, _ in triggered:
        print(f'  \u2022 {desc}')


def cmd_cross_check():
    try:
        import importlib.util

        entries_a = parse_log_entries()
        filtered_a, _ = filter_smoke_tests(entries_a)
        blocks_a = sum(1 for e in filtered_a if e['decision'] == 'BLOCK')
        passes_a = sum(1 for e in filtered_a if e['decision'] == 'PASS')

        analyst_path = f'{CLAUDE_DIR}/scripts/quality-gate-analyst.py'
        if not os.path.exists(analyst_path):
            return
        spec = importlib.util.spec_from_file_location('analyst', analyst_path)
        analyst = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(analyst)

        entries_b_all = analyst.parse_log(LOG_PATH)
        entries_b_main = [e for e in entries_b_all if e['source'] == 'main']
        filtered_b_all, _ = analyst.filter_smoke_tests(entries_b_all)
        filtered_b_main = [e for e in filtered_b_all if e['source'] == 'main']
        blocks_b = sum(1 for e in filtered_b_main if e['decision'] == 'BLOCK')
        passes_b = sum(1 for e in filtered_b_main if e['decision'] == 'PASS')

        divergences = []
        if len(entries_a) != len(entries_b_main):
            divergences.append(
                f"Raw count: feedback={len(entries_a)}, analyst={len(entries_b_main)}")
        if blocks_a != blocks_b or passes_a != passes_b:
            divergences.append(
                f"Post-filter: feedback blocks={blocks_a} pass={passes_a}, "
                f"analyst blocks={blocks_b} pass={passes_b}")

        if divergences:
            desc = 'Parser divergence: ' + '; '.join(divergences)
            recent_keys = _load_recent_failure_keys(days=3)
            if 'parser-divergence' not in recent_keys:
                cmd_failures_add(f'[AUTO] {desc}')
    except Exception:
        pass


def cmd_milestone(description):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'{ts} | MILESTONE | {description}\n'
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line)
    print(f'Milestone recorded: {ts} | {description}')


def _parse_milestones():
    """Return list of (ts_dt, description) from MILESTONE lines in quality-gate.log."""
    milestones = []
    if not os.path.exists(LOG_PATH):
        return milestones
    try:
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            for line in f:
                if '| MILESTONE |' not in line:
                    continue
                parts = [p.strip() for p in line.split('|')]
                if len(parts) < 3:
                    continue
                try:
                    ts = datetime.strptime(parts[0], '%Y-%m-%d %H:%M:%S')
                    milestones.append((ts, parts[2]))
                except ValueError:
                    continue
    except Exception:
        pass
    return milestones


def cmd_trend(n=10):
    """Show block-rate trend across last N sessions."""
    all_entries = parse_log_entries()
    all_entries, _ = filter_smoke_tests(all_entries)
    sessions = detect_sessions(all_entries)
    milestones = _parse_milestones()

    if not sessions:
        print('No session data found.')
        return

    recent = sessions[-n:]
    print(f'=== Quality Gate Trend: last {len(recent)} sessions ===\n')
    print(f'{"Session":<22} {"Evals":>5} {"Blks":>4} {"Rate":>5}  {"ASSUM":>5} {"OC":>4} {"MECH":>4}  {"Delta":>6}')
    print('-' * 65)

    prev_rate = None
    for sess in recent:
        evals = len(sess)
        blocks = [e for e in sess if e['decision'] == 'BLOCK']
        nb = len(blocks)
        rate = nb / evals * 100 if evals else 0
        by_cat = Counter(b['category'] for b in blocks)
        assume = by_cat.get('ASSUMPTION', 0)
        overconf = by_cat.get('OVERCONFIDENCE', 0)
        mech = by_cat.get('MECHANICAL', 0)
        label = f'{sess[0]["ts"].strftime("%m-%d %H:%M")}–{sess[-1]["ts"].strftime("%H:%M")}'
        delta_str = f'{rate - prev_rate:+.0f}%' if prev_rate is not None else ''
        prev_rate = rate
        sess_ms = [d for ts, d in milestones
                   if sess[0]['ts'] <= ts <= sess[-1]['ts'] and d != 'smoke-test-verify']
        print(f'{label:<22} {evals:>5} {nb:>4} {rate:>4.0f}%  {assume:>5} {overconf:>4} {mech:>4}  {delta_str:>6}')
        for ms in sess_ms:
            print(f'  ↳ [{ms[:68]}]')

    all_evals = sum(len(s) for s in recent)
    all_blocks = sum(len([e for e in s if e['decision'] == 'BLOCK']) for s in recent)
    first_rate = len([e for e in recent[0] if e['decision'] == 'BLOCK']) / len(recent[0]) * 100 if recent[0] else 0
    last_rate = len([e for e in recent[-1] if e['decision'] == 'BLOCK']) / len(recent[-1]) * 100 if recent[-1] else 0
    print('-' * 65)
    print(f'Overall: {all_evals} evals, {all_blocks} blocks ({all_blocks/all_evals*100:.0f}%) across {len(recent)} sessions')
    print(f'Trend:   {first_rate:.0f}% → {last_rate:.0f}% (first → last session shown)')


def cmd_precision():
    """Estimate precision per category using override records as FP signal."""
    all_entries = parse_log_entries()
    all_entries, _ = filter_smoke_tests(all_entries)
    blocks = [e for e in all_entries if e['decision'] == 'BLOCK']

    confirmed_fps, confirmed_tps = [], []
    if os.path.exists(FEEDBACK_PATH):
        try:
            with open(FEEDBACK_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    r = json.loads(line.strip())
                    if r.get('type') == 'fp':
                        confirmed_fps.append(r)
                    elif r.get('type') == 'tp':
                        confirmed_tps.append(r)
        except Exception:
            pass

    override_hashes = set()
    if os.path.exists(OVERRIDES_PATH):
        try:
            with open(OVERRIDES_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    override_hashes.add(json.loads(line.strip()).get('response_hash', ''))
        except Exception:
            pass

    by_cat = defaultdict(lambda: {'total': 0, 'overridden': 0})
    for b in blocks:
        by_cat[b['category']]['total'] += 1
        if b['hash'] in override_hashes:
            by_cat[b['category']]['overridden'] += 1

    total = len(blocks)
    total_ov = sum(v['overridden'] for v in by_cat.values())
    precision = (total - total_ov) / total * 100 if total else 100

    print(f'=== Quality Gate Precision Estimate ===\n')
    print(f'Total blocks (all time, smoke filtered): {total}')
    print(f'Overridden (FP proxy):  {total_ov} ({total_ov/total*100:.1f}% of blocks)')
    print(f'Estimated precision:    {precision:.1f}% lower bound (unrecorded FPs omitted)\n')
    print(f'{"Category":<25} {"Blocks":>6} {"Overridden":>10} {"Precision":>9}')
    print('-' * 54)
    for cat, v in sorted(by_cat.items(), key=lambda x: -x[1]['total']):
        prec = (v['total'] - v['overridden']) / v['total'] * 100 if v['total'] else 100
        print(f'{cat:<25} {v["total"]:>6} {v["overridden"]:>10} {prec:>8.0f}%')
    if confirmed_fps:
        print(f'\nConfirmed FPs (qg fp): {len(confirmed_fps)}')
        for r in confirmed_fps[-5:]:
            print(f'  {r["ts"][:10]} | {r.get("block_reason","")[:60]}')
    if confirmed_tps:
        print(f'Confirmed TPs (qg tp): {len(confirmed_tps)}')


def cmd_weekly():
    """Compare this week's quality gate metrics against last week."""
    all_entries = parse_log_entries()
    all_entries, smoke_count = filter_smoke_tests(all_entries)
    if not all_entries:
        print('No session data found.')
        return

    now = datetime.now()
    week_starts = [now - timedelta(days=now.weekday() + 7),
                   now - timedelta(days=now.weekday())]
    week_labels = ['Last week', 'This week']

    weeks = []
    for i, ws in enumerate(week_starts):
        we = ws + timedelta(days=7)
        entries = [e for e in all_entries if ws <= e['ts'] < we]
        filtered_entries, _ = filter_smoke_tests(entries)
        blocks = [e for e in filtered_entries if e['decision'] == 'BLOCK']
        passes = [e for e in filtered_entries if e['decision'] == 'PASS']
        degraded = [e for e in filtered_entries if e['decision'] == 'DEGRADED-PASS']
        total = len(filtered_entries)
        by_cat = Counter(b['category'] for b in blocks)
        si_evals = [e for e in filtered_entries if e.get('short_input')]
        si_blocks = [e for e in si_evals if e['decision'] == 'BLOCK']
        sub_entries = [e for e in filtered_entries if e.get('is_subagent')]
        sub_blocks = [e for e in sub_entries if e['decision'] == 'BLOCK']
        weeks.append({
            'label': week_labels[i],
            'range': f'{ws.strftime("%b %d")}–{(we - timedelta(days=1)).strftime("%b %d")}',
            'total': total,
            'blocks': len(blocks),
            'rate': len(blocks) / total * 100 if total else 0,
            'by_cat': by_cat,
            'si_total': len(si_evals),
            'si_blocks': len(si_blocks),
            'sub_total': len(sub_entries),
            'sub_blocks': len(sub_blocks),
            'degraded': len(degraded),
        })

    print('=== Quality Gate Weekly Comparison ===\n')
    for w in weeks:
        rate_str = f'{w["rate"]:.0f}%' if w['total'] else 'no data'
        print(f'{w["label"]} ({w["range"]}): {w["total"]} evals, {w["blocks"]} blocks ({rate_str})')
        if w['by_cat']:
            top = w['by_cat'].most_common(3)
            cat_str = '  '.join(f'{c}:{n}' for c, n in top)
            print(f'  Top categories: {cat_str}')
        if w['si_total']:
            si_rate = w['si_blocks'] / w['si_total'] * 100
            marker = ' ▲ ABOVE TARGET' if si_rate >= 25 else ' ✓'
            print(f'  Short-input FP: {w["si_blocks"]}/{w["si_total"]} ({si_rate:.0f}%){marker}')
        if w['sub_total']:
            sr = w['sub_blocks'] / w['sub_total'] * 100
            print(f'  Subagent blocks: {w["sub_blocks"]}/{w["sub_total"]} ({sr:.0f}%)')
        if w['degraded']:
            deg_pct = w['degraded'] / w['total'] * 100 if w['total'] else 0
            deg_flag = ' [!] ABOVE 5% TARGET' if deg_pct >= 5 else ''
            print(f'  Degraded evals (Haiku fail): {w["degraded"]} ({deg_pct:.0f}%){deg_flag}')
        print()

    # Delta summary
    if weeks[0]['total'] and weeks[1]['total']:
        delta = weeks[1]['rate'] - weeks[0]['rate']
        sign = '+' if delta > 0 else ''
        direction = 'worse ▲' if delta > 0 else ('better ▼' if delta < 0 else 'unchanged')
        print(f'Block rate delta: {sign}{delta:.0f}% ({direction})')

        for cat in set(list(weeks[0]['by_cat'].keys()) + list(weeks[1]['by_cat'].keys())):
            prev = weeks[0]['by_cat'].get(cat, 0)
            curr = weeks[1]['by_cat'].get(cat, 0)
            if abs(curr - prev) >= 3:
                trend = '▲' if curr > prev else '▼'
                print(f'  {cat}: {prev} → {curr} {trend}')
    elif not weeks[1]['total']:
        print('This week has no data yet.')
    else:
        print('No prior week data to compare against.')


SMOKE_BRANCH_LABELS = {
    1:  'stop_hook_active bypass',
    2:  'code edit, no verification → BLOCK',
    3:  'last action is edit → BLOCK',
    4:  'bash not a real test → BLOCK',
    5:  'failed command not mentioned → BLOCK',
    6:  'OVERCONFIDENCE: claims results without quoting → BLOCK',
    7:  'OVERCONFIDENCE: bare count, no verification → BLOCK',
    8:  'quantity mismatch (items vs files) → BLOCK',
    9:  'LLM evaluates BLOCK',
    10: 'compliance retry with fix directive',
    11: 'retry count >= 2 → MANDATORY escalation',
    12: 'DEGRADED-PASS (Haiku API failure)',
    13: 'mechanical BLOCK path',
    14: 'agent without post-agent verify → code-edit flag',
    15: 'non-code paths filter → skip code-edit check',
    16: 'llm_evaluate cache-hit early return',
}

# Map smoke test sections to the SMOKE branches they exercise
SECTION_SMOKE_COVERAGE = {
    11: [1, 2, 3, 4, 5, 8, 13, 14, 15],
    27: [9, 10],
    28: [6, 7],
    29: [10, 11],
    31: [12],
    51: [16],
}


def cmd_coverage(diff=False):
    """Show which quality-gate.py branches have smoke test coverage.
    diff=True: show only branches added since last run."""
    qg_path = os.path.expanduser('~/.claude/hooks/quality-gate.py')
    smoke_path = os.path.expanduser('~/.claude/hooks/smoke-test.sh')

    # Read SMOKE markers from quality-gate.py
    try:
        with open(qg_path, encoding='utf-8') as f:
            qg_src = f.read()
    except OSError as e:
        print(f'Cannot read quality-gate.py: {e}')
        return

    import re as _re
    found_markers = set(int(m) for m in _re.findall(r'# SMOKE:(\d+)', qg_src))
    expected_markers = set(SMOKE_BRANCH_LABELS.keys())

    # Compute covered branches
    covered = set()
    for branches in SECTION_SMOKE_COVERAGE.values():
        covered.update(branches)

    uncovered = expected_markers - covered
    missing_markers = expected_markers - found_markers

    # Count active smoke test sections
    try:
        with open(smoke_path, encoding='utf-8') as f:
            smoke_src = f.read()
        active_sections = set(int(m) for m in _re.findall(r'echo "\[(\d+)\]', smoke_src))
    except OSError:
        active_sections = set()

    # Load previous snapshot (for --diff)
    prev_snapshot = None
    if diff:
        try:
            with open(COVERAGE_SNAPSHOT, encoding='utf-8') as f:
                prev_snapshot = json.load(f)
        except (OSError, json.JSONDecodeError):
            pass

    # Save current snapshot on every run
    try:
        with open(COVERAGE_SNAPSHOT, 'w', encoding='utf-8') as f:
            json.dump({
                'branches': sorted(expected_markers),
                'covered': sorted(covered),
                'ts': datetime.now().isoformat(timespec='seconds'),
            }, f)
    except OSError:
        pass

    if diff:
        prev_branches = set(prev_snapshot['branches']) if prev_snapshot else set()
        new_branches = expected_markers - prev_branches
        if not new_branches:
            last_ts = prev_snapshot.get('ts', 'unknown') if prev_snapshot else 'no snapshot'
            print(f'No new branches since last run (last saved: {last_ts}, {len(expected_markers)} total)')
            return
        print(f'=== New branches since last run ({len(new_branches)} added) ===\n')
        for n in sorted(new_branches):
            label = SMOKE_BRANCH_LABELS.get(n, '?')
            status = 'COVERED  ' if n in covered else 'UNCOVERED'
            secs = [s for s, bs in SECTION_SMOKE_COVERAGE.items() if n in bs]
            sec_str = f'  [§{", §".join(str(s) for s in secs)}]' if secs else ''
            print(f'  {status} SMOKE:{n:2d}  {label}{sec_str}')
        return

    print('=== Quality Gate Branch Coverage ===\n')
    print(f'Branches instrumented: {len(found_markers)}/{len(expected_markers)}')
    covered_pct = len(covered) / len(expected_markers) * 100 if expected_markers else 0
    print(f'Branches with smoke tests: {len(covered)}/{len(expected_markers)} ({covered_pct:.0f}%)\n')

    print('COVERED branches:')
    for n in sorted(covered):
        label = SMOKE_BRANCH_LABELS.get(n, '?')
        secs = [s for s, bs in SECTION_SMOKE_COVERAGE.items() if n in bs]
        print(f'  SMOKE:{n:2d}  {label}  [§{", §".join(str(s) for s in secs)}]')

    if uncovered:
        print('\nUNCOVERED branches (no smoke test):')
        for n in sorted(uncovered):
            label = SMOKE_BRANCH_LABELS.get(n, '?')
            print(f'  SMOKE:{n:2d}  {label}')
    else:
        print('\nAll branches have smoke test coverage.')

    if missing_markers:
        print(f'\nWARN: branches in label map but missing # SMOKE: comment: {sorted(missing_markers)}')

    print(f'\nSmoke test sections active: {len(active_sections)} (sections [{min(active_sections)}]-[{max(active_sections)}])')


def cmd_scan():
    """Scan recent PASS entries for structural false-negative signals."""
    all_entries = parse_log_entries()
    all_entries, _ = filter_smoke_tests(all_entries)
    sessions = detect_sessions(all_entries)
    if not sessions:
        print('No session data.')
        return
    recent = sessions[-2:] if len(sessions) >= 2 else sessions[-1:]
    pool = [e for s in recent for e in s]
    passes = [e for e in pool if e['decision'] == 'PASS']
    suspects = []

    _skip_re = re.compile(
        r'^(this session is being continued|stop hook feedback:|$|-$)',
        re.IGNORECASE
    )
    # Signal 1: PASS with no tools immediately following a BLOCK on the same substantive req prefix
    block_req_prefixes = {e['req'][:50] for e in pool
                          if e['decision'] == 'BLOCK' and len(e['req']) > 20}
    for p in passes:
        req_prefix = p['req'][:50]
        if (len(p['req']) > 20 and req_prefix in block_req_prefixes
                and p['tools'] in ('-', '') and not _skip_re.match(p['req'])):
            suspects.append((p, 'PASS-after-BLOCK with tools=- (retry may have dodged without verifying)'))

    # Signal 2: user correction language in req that followed a PASS
    correction_re = re.compile(
        r"you (assumed|didn't|should have|forgot|missed)|that'?s wrong|not found in|"
        r"without reading|check again|you never|actually\b",
        re.IGNORECASE
    )
    for p in passes:
        if correction_re.search(p['req']):
            suspects.append((p, f'User correction signal in req: "{p["req"][:60]}"'))

    # Signal 3: completion claim in req with no tools (gate saw a claim-response that passed)
    completion_re = re.compile(
        r'\ball (tests?|checks?) (pass|passed|done)\b|\bno (errors?|failures?)\b|'
        r'\bsuccessfully (completed?|fixed?|updated?)\b',
        re.IGNORECASE
    )
    for p in passes:
        if p['tools'] in ('-', '') and completion_re.search(p['req']):
            suspects.append((p, f'Completion claim in req, tools=- : "{p["req"][:60]}"'))

    seen, unique = set(), []
    for p, reason in suspects:
        if p['hash'] not in seen:
            seen.add(p['hash'])
            unique.append((p, reason))

    if not unique:
        print('No structural false-negative signals found in recent sessions.')
        return
    print(f'=== Scan: {len(unique)} suspected false negatives (last {len(recent)} sessions) ===\n')
    for p, reason in unique[:15]:
        print(f'{p["ts"].strftime("%m-%d %H:%M")} | {reason}')
        print(f'  req: {p["req"][:80]}')
        print()
    print('To confirm a miss: qg miss')


SHADOW_LOG = os.path.expanduser('~/.claude/hooks/qg-shadow.log')
SHADOW_TREND_LOG = os.path.expanduser('~/.claude/hooks/qg-shadow-trend.log')


def cmd_shadow(n=50, diff=False):
    """Show Ollama shadow evaluation agreement vs Haiku."""
    if not os.path.exists(SHADOW_LOG):
        print('No shadow log found. Shadow mode requires Ollama running and phi4:14b loaded.')
        return
    with open(SHADOW_LOG, encoding='utf-8') as f:
        lines = [l.rstrip() for l in f if l.strip()]
    if not lines:
        print('Shadow log is empty.')
        return

    entries = []
    for line in lines:
        parts = [p.strip() for p in line.split(' | ')]
        if len(parts) < 4:
            continue
        ts, haiku_dec, ollama_dec, agreement = parts[0], parts[1], parts[2], parts[3]
        reasons = parts[4:] if len(parts) > 4 else []
        entries.append({'ts': ts, 'haiku': haiku_dec, 'ollama': ollama_dec,
                        'agree': agreement == 'agree', 'reasons': reasons})

    from collections import Counter

    # Reason-based smoke test filter: exclude entries where the ollama reason prefix
    # repeats >= 3 times (mirrors parse_log_entries hash filter for real entries)
    def _ollama_reason(e):
        for r in e['reasons']:
            if r.startswith('ollama:'):
                return r[7:].strip()[:60]
        return ''
    reason_counts = Counter(_ollama_reason(e) for e in entries)
    smoke_reasons = {r for r, cnt in reason_counts.items() if r and cnt >= 3}
    filtered = [e for e in entries if _ollama_reason(e) not in smoke_reasons]
    smoke_count = len(entries) - len(filtered)

    total = len(filtered)
    agreed = sum(1 for e in filtered if e['agree'])
    fp_ollama = [e for e in filtered if e['haiku'] == 'PASS' and e['ollama'] == 'BLOCK']
    fn_ollama = [e for e in filtered if e['haiku'] == 'BLOCK' and e['ollama'] == 'PASS']

    agree_pct = agreed / total * 100 if total else 0
    print('=== Shadow mode: Ollama (phi4:14b) vs Haiku ===')
    smoke_note = f'  ({smoke_count} smoke test entries filtered)' if smoke_count else ''
    print(f'Total evals: {total}{smoke_note}')
    print(f'Agreement:   {agreed}/{total} ({agree_pct:.0f}%)')
    print(f'Haiku PASS / Ollama BLOCK: {len(fp_ollama)} (Ollama more aggressive)')
    print(f'Haiku BLOCK / Ollama PASS: {len(fn_ollama)} (Ollama more permissive)')

    disagree = [e for e in filtered if not e['agree']]
    if not disagree:
        print('')
        print('No disagreements found -- perfect agreement.')
        return

    if diff:
        fp = [e for e in disagree if e['haiku'] == 'PASS' and e['ollama'] == 'BLOCK']
        fn = [e for e in disagree if e['haiku'] == 'BLOCK' and e['ollama'] == 'PASS']
        def _cat(reasons, prefix):
            for r in reasons:
                if r.startswith(prefix + ':'):
                    text = r[len(prefix)+1:].strip()
                    return text.split(':')[0].strip() if ':' in text else text[:40]
            return '(no reason)'
        print('')
        print(f'Haiku PASS / Ollama BLOCK -- {len(fp)} (Ollama over-aggressive):')
        cats = Counter(_cat(e['reasons'], 'ollama') for e in fp)
        for cat, cnt in cats.most_common():
            print(f'  {cat:<50} {cnt}')
        print('')
        print(f'Haiku BLOCK / Ollama PASS -- {len(fn)} (Ollama missed):')
        cats = Counter(_cat(e['reasons'], 'haiku') for e in fn)
        for cat, cnt in cats.most_common():
            print(f'  {cat:<50} {cnt}')
    else:
        recent = disagree[-n:]
        print('')
        print(f'Recent disagreements (last {len(recent)}):')
        for e in recent:
            arrow = 'H:PASS O:BLOCK' if e['haiku'] == 'PASS' else 'H:BLOCK O:PASS'
            reasons_str = ' | '.join(e['reasons']) if e['reasons'] else ''
            print(f"  {e['ts']}  {arrow}")
            if reasons_str:
                print(f"    {reasons_str[:120]}")


def cmd_monitor():
    """qg monitor — unified quality gate dashboard."""
    import json, os
    from collections import Counter

    CLAUDE_DIR = os.path.expanduser('~/.claude')
    monitor_path = f'{CLAUDE_DIR}/qg-monitor.jsonl'
    history_path = f'{CLAUDE_DIR}/qg-session-history.md'
    state_path = f'{CLAUDE_DIR}/qg-session-state.json'

    print('=== Quality Gate Monitor Dashboard ===')
    print()

    session_uuid = None
    try:
        with open(state_path, 'r', encoding='utf-8') as f:
            state = json.load(f)
        session_uuid = state.get('session_uuid')
        print(f"Session:  {session_uuid or '(none)'}")
        print(f"Task:     {state.get('active_task_description', '')[:70] or '(none)'}")
        print(f"Category: {state.get('layer1_task_category', 'UNKNOWN')}")
        l2_open = [e for e in state.get('layer2_unresolved_events', []) if e.get('status') == 'open']
        print(f"L2 open:  {len(l2_open)} unresolved")
        if l2_open:
            for cat, cnt in Counter(e['category'] for e in l2_open).most_common():
                print(f"          {cat}: {cnt}")
    except (FileNotFoundError, json.JSONDecodeError):
        print("Session state: not available")
    print()

    all_events, sess_events = [], []
    try:
        with open(monitor_path, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    e = json.loads(line)
                    if e.get('layer') == 'layer3':
                        all_events.append(e)
                        if session_uuid and e.get('session_uuid') == session_uuid:
                            sess_events.append(e)
                except Exception:
                    pass
    except FileNotFoundError:
        pass

    def _stats(evts, label):
        tp = sum(1 for e in evts if e.get('verdict') == 'TP')
        fp = sum(1 for e in evts if e.get('verdict') == 'FP')
        fn = sum(1 for e in evts if e.get('verdict') == 'FN')
        tn = sum(1 for e in evts if e.get('verdict') == 'TN')
        print(f"{label}: TP={tp} FP={fp} FN={fn} TN={tn} (total={len(evts)})")

    _stats(sess_events, 'Session ')
    _stats(all_events,  'All-time')
    print()

    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            history = f.read()
        entries = [e for e in history.split('## Session') if e.strip()]
        if entries:
            print('--- Most Recent Session Summary ---')
            print('## Session' + entries[0][:500].rstrip())
    except FileNotFoundError:
        print('No session history yet.')

    print()
    print('Commands: qg analyze | qg integrity | qg rules')


def cmd_analyze():
    """qg analyze -- trigger cross-session analysis."""
    import sys as _sys
    _sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
    from qg_layer6 import run_analysis
    result = run_analysis()
    print('Cross-session analysis complete.')
    print('Sessions analyzed: {}'.format(result['sessions_analyzed']))
    if result['patterns']:
        print('Recurring patterns:')
        for p in result['patterns']:
            print('  {} -- {} sessions, {:.0f}% of events'.format(
                p['category'], p['sessions_count'], p['event_pct'] * 100))
    else:
        print('No recurring patterns found.')


def cmd_integrity():
    """qg integrity — audit trail integrity check."""
    import json, os
    path = os.path.expanduser('~/.claude/qg-monitor.jsonl')
    if not os.path.exists(path):
        print('qg-monitor.jsonl not found — no events logged yet.')
        return
    total = bad = 0
    seen_ids = set()
    with open(path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f, 1):
            total += 1
            try:
                e = json.loads(line)
                eid = e.get('event_id', '')
                if eid in seen_ids:
                    print(f'  Line {i}: duplicate event_id {eid!r}')
                    bad += 1
                seen_ids.add(eid)
            except json.JSONDecodeError:
                print(f'  Line {i}: invalid JSON')
                bad += 1
    print(f'Audit trail: {total} lines, {bad} issue(s).')
    print('Integrity: OK' if bad == 0 else 'Integrity: ISSUES FOUND')


def cmd_rules():
    """qg rules — view pending rule suggestions (Layer 7 preview)."""
    import os
    path = os.path.expanduser('~/.claude/qg-rule-suggestions.md')
    if not os.path.exists(path):
        print('No pending rule suggestions. (Layer 7 is a Phase 3 feature.)')
        return
    with open(path, 'r', encoding='utf-8') as f:
        print(f.read())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1].lower()
    if cmd == 'fp':
        cmd_fp()
    elif cmd == 'tp':
        cmd_tp()
    elif cmd == 'miss':
        cmd_miss()
    elif cmd == 'report':
        cmd_report()
    elif cmd == 'failures':
        if len(sys.argv) >= 3 and sys.argv[2].lower() == 'add':
            desc = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else ''
            if not desc:
                print('Usage: qg failures add "description"')
                sys.exit(1)
            cmd_failures_add(desc)
        elif len(sys.argv) >= 3 and sys.argv[2].lower() == 'close':
            try:
                n = int(sys.argv[3]) if len(sys.argv) > 3 else 0
            except ValueError:
                n = 0
            reason = ' '.join(sys.argv[4:]) if len(sys.argv) > 4 else ''
            if not n or not reason:
                print('Usage: qg failures close N "reason"')
                sys.exit(1)
            cmd_failures_close(n, reason)
        else:
            cmd_failures()
    elif cmd == 'milestone':
        desc = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else ''
        if not desc:
            print('Usage: qg milestone "description"')
            sys.exit(1)
        cmd_milestone(desc)
    elif cmd == 'auto-detect':
        cmd_auto_detect()
    elif cmd == 'cross-check':
        cmd_cross_check()
    elif cmd == 'trend':
        n = int(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[2].isdigit() else 10
        cmd_trend(n)
    elif cmd == 'precision':
        cmd_precision()
    elif cmd == 'scan':
        cmd_scan()
    elif cmd == 'weekly':
        cmd_weekly()
    elif cmd == 'coverage':
        cmd_coverage(diff='--diff' in sys.argv)
    elif cmd == 'shadow':
        if '--trend' in sys.argv:
            if os.path.exists(SHADOW_TREND_LOG):
                with open(SHADOW_TREND_LOG, encoding='utf-8') as _f:
                    lines = [l.rstrip() for l in _f if l.strip()]
                print('=== Shadow trend (per --clear snapshot) ===')
                for l in lines:
                    print(' ', l)
                if not lines:
                    print('  No snapshots yet — run qg shadow --clear to record first entry.')
            else:
                print('No shadow trend log yet — run qg shadow --clear to record first entry.')
        elif '--clear' in sys.argv:
            if os.path.exists(SHADOW_LOG):
                from collections import Counter as _Ctr
                import datetime as _dt
                _entries = []
                with open(SHADOW_LOG, encoding='utf-8') as _f:
                    for _line in _f:
                        _parts = [p.strip() for p in _line.split(' | ')]
                        if len(_parts) < 4:
                            continue
                        _reasons = _parts[4:] if len(_parts) > 4 else []
                        _entries.append({'haiku': _parts[1], 'ollama': _parts[2],
                                         'agree': _parts[3] == 'agree', 'reasons': _reasons})
                def _ore(e):
                    for r in e['reasons']:
                        if r.startswith('ollama:'):
                            return r[7:].strip()[:60]
                    return ''
                _rc = _Ctr(_ore(e) for e in _entries)
                _smoke = {r for r, c in _rc.items() if r and c >= 3}
                _filt = [e for e in _entries if _ore(e) not in _smoke]
                _total = len(_filt)
                _agreed = sum(1 for e in _filt if e['agree'])
                _fp = [e for e in _filt if not e['agree'] and e['haiku'] == 'PASS']
                def _ocat(e):
                    for r in e['reasons']:
                        if r.startswith('ollama:'):
                            t = r[7:].strip()
                            return t.split(':')[0].strip()[:20] if ':' in t else t[:20]
                    return '?'
                _cats = _Ctr(_ocat(e) for e in _fp)
                _fp_desc = ' / '.join(f'{c} {k}' for k, c in _cats.most_common()) or 'none'
                _pct = _agreed / _total * 100 if _total else 0
                _ts = _dt.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                _smoke_n = len(_entries) - _total
                _trend_line = (f'{_ts} | {_total} evals ({_smoke_n} filtered) | '
                               f'{_agreed}/{_total} agree ({_pct:.0f}%) | FPs: {_fp_desc}')
                with open(SHADOW_TREND_LOG, 'a', encoding='utf-8') as _tf:
                    _tf.write(_trend_line + '\n')
                n_lines = len(_entries) + _smoke_n
                open(SHADOW_LOG, 'w').close()
                print(f'Shadow log cleared ({n_lines} entries removed).')
                print(f'Trend snapshot: {_trend_line}')
            else:
                print('Shadow log does not exist.')
        else:
            n = int(sys.argv[2]) if len(sys.argv) >= 3 and sys.argv[2].isdigit() else 50
            cmd_shadow(n, diff='--diff' in sys.argv)
    elif cmd == 'monitor':
        cmd_monitor()
    elif cmd == 'analyze':
        cmd_analyze()
    elif cmd == 'integrity':
        cmd_integrity()
    elif cmd == 'rules':
        if len(sys.argv) >= 3 and sys.argv[2] in ('apply', 'reject'):
            print('Rule apply/reject (Layer 7) is a Phase 3 feature.')
        else:
            cmd_rules()
    else:
        print(f'Unknown command: {cmd}')
        print('Usage: qg fp | tp | miss | report | failures | failures add "desc" | failures close N "reason" | milestone "desc" | auto-detect | cross-check | trend [N] | precision | scan | weekly | coverage [--diff] | shadow [N] [--diff] [--clear] [--trend]')
        sys.exit(1)


if __name__ == '__main__':
    main()

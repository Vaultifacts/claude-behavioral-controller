"""
quality-gate-analyst.py — Offline quality gate analysis.
Run: python ~/.claude/scripts/quality-gate-analyst.py
Or:  qg report

Reads quality-gate.log, quality-gate-overrides.jsonl, quality-gate-feedback.jsonl.
Outputs metrics, FP pattern clusters, and candidate calibration examples.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime

CLAUDE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH     = f'{CLAUDE_DIR}/quality-gate.log'
OVERRIDES    = f'{CLAUDE_DIR}/quality-gate-overrides.jsonl'
FEEDBACK     = f'{CLAUDE_DIR}/quality-gate-feedback.jsonl'
INSIGHTS     = f'{CLAUDE_DIR}/quality-gate-insights.md'
CANDIDATES   = f'{CLAUDE_DIR}/quality-gate-candidates.json'


# ── Data loading ──────────────────────────────────────────────────────────────

def read_jsonl(path):
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return [json.loads(l) for l in f if l.strip()]
    except Exception:
        return []


def parse_log(path):
    """Parse quality-gate.log into main-gate and subagent entries.

    THREE formats:
      Main-gate:   {ts} | {decision} | {complexity} | {reason} | tools={...} | req={...} [| hash={...}]
      Subagent:    {ts} | {decision} | subagent:{type} | {reason} [| hash={...}]
      WARN/Degrad: {ts} | WARN  | DEGRADED | {message}

    Returns list of dicts with keys: ts, decision, source, reason, tools, req
    """
    entries = []
    if not os.path.exists(path):
        return entries
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        return entries

    for line in lines:
        line = line.rstrip()
        parts = [p.strip() for p in line.split('|')]
        if len(parts) < 4:
            continue
        ts_str = parts[0].strip()
        decision = parts[1].strip()

        # Skip WARN/degradation entries
        if decision == 'WARN':
            continue

        if decision not in ('PASS', 'BLOCK'):
            continue

        # Detect format
        if parts[2].startswith('subagent:'):
            source = 'subagent'
            agent_type = parts[2][len('subagent:'):].strip()
            reason = parts[3] if len(parts) > 3 else ''
            entries.append({
                'ts': ts_str, 'decision': decision, 'source': source,
                'agent_type': agent_type, 'reason': reason, 'tools': '', 'req': '',
            })
        else:
            source = 'main'
            complexity = parts[2]
            reason = parts[3] if len(parts) > 3 else ''
            tools = req = hash_val = ''
            for part in parts[4:]:
                if part.startswith('tools='):
                    tools = part[6:]
                elif part.startswith('req='):
                    req = part[4:]
                elif part.startswith('hash='):
                    hash_val = part[5:]
            entries.append({
                'ts': ts_str, 'decision': decision, 'source': source,
                'complexity': complexity, 'reason': reason, 'tools': tools, 'req': req,
                'hash': hash_val,
            })

    return entries


def filter_smoke_tests(entries):
    """Remove smoke test entries (hash frequency >= 3). Returns (filtered, smoke_count)."""
    freq = {}
    for e in entries:
        h = e.get('hash', '')
        if h and h != '--------':
            freq[h] = freq.get(h, 0) + 1
    filtered = [e for e in entries if not (
        e.get('hash') and e.get('hash') != '--------' and freq.get(e.get('hash', ''), 0) >= 3
    )]
    return filtered, len(entries) - len(filtered)


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(entries, overrides, feedback):
    main = [e for e in entries if e['source'] == 'main']
    sub  = [e for e in entries if e['source'] == 'subagent']

    main_total  = len(main)
    main_blocks = sum(1 for e in main if e['decision'] == 'BLOCK')
    sub_total   = len(sub)
    sub_blocks  = sum(1 for e in sub if e['decision'] == 'BLOCK')

    main_block_rate = main_blocks / main_total if main_total else 0
    sub_block_rate  = sub_blocks / sub_total   if sub_total  else 0

    fp_overrides = [o for o in overrides if o.get('auto_verdict') == 'likely_fp']
    tp_overrides = [o for o in overrides if o.get('auto_verdict') == 'likely_tp']

    fp_count = len(fp_overrides)
    tp_count = len(tp_overrides)
    total_overrides = len(overrides)
    fp_rate = fp_count / total_overrides if total_overrides else 0
    override_rate = total_overrides / main_blocks if main_blocks else 0

    # Category distribution for BLOCKs
    categories = defaultdict(int)
    for e in main:
        if e['decision'] == 'BLOCK':
            cat = e['reason'].split(':')[0].strip() if ':' in e['reason'] else 'MECHANICAL'
            categories[cat] += 1

    # User feedback counts
    fb_fp   = sum(1 for f in feedback if f.get('type') == 'fp')
    fb_tp   = sum(1 for f in feedback if f.get('type') == 'tp')
    fb_miss = sum(1 for f in feedback if f.get('type') == 'miss')

    return {
        'main_total': main_total, 'main_blocks': main_blocks, 'main_block_rate': main_block_rate,
        'sub_total': sub_total, 'sub_blocks': sub_blocks, 'sub_block_rate': sub_block_rate,
        'fp_overrides': fp_count, 'tp_overrides': tp_count, 'total_overrides': total_overrides,
        'fp_rate': fp_rate, 'override_rate': override_rate,
        'categories': dict(categories),
        'fb_fp': fb_fp, 'fb_tp': fb_tp, 'fb_miss': fb_miss,
    }


# ── FP pattern clustering ─────────────────────────────────────────────────────

def cluster_fp_patterns(overrides):
    """Group likely_fp overrides by block_reason prefix (first 40 chars)."""
    clusters = defaultdict(list)
    for o in overrides:
        if o.get('auto_verdict') != 'likely_fp':
            continue
        prefix = o.get('block_reason', '')[:40]
        clusters[prefix].append(o)
    return {k: v for k, v in sorted(clusters.items(), key=lambda x: -len(x[1]))}


def generate_candidate(prefix, records):
    """Generate a suggested FEW_SHOT_EXAMPLES entry for a cluster."""
    example = records[0]
    user_req = example.get('user_request', 'the task')
    tools_after = ', '.join(example.get('tools_after', [])) or '(none)'
    cat = example.get('block_category', 'ASSUMPTION')
    block_reason = example.get('block_reason', prefix)

    return (
        f"USER: \"{user_req[:60]}\"\n"
        f"TOOLS USED: {tools_after}\n"
        f"RESPONSE: [response that was blocked for: {block_reason[:60]}]\n"
        f"Verdict: {{\"ok\": true}}  # PASS — this was a false positive\n"
        f"# Based on {len(records)} auto-detected FP(s) with same pattern"
    )


# ── Report writing ────────────────────────────────────────────────────────────

def write_report(metrics, clusters, candidates_list):
    now = datetime.now().strftime('%Y-%m-%d %H:%M MST')
    lines = [
        f'# Quality Gate Analysis — {now}\n\n',
        '## Metrics\n\n',
        f'| Metric | Value |\n|--------|-------|\n',
        f'| Main gate evaluations | {metrics["main_total"]} |\n',
        f'| Main gate block rate | {metrics["main_block_rate"]:.1%} ({metrics["main_blocks"]}/{metrics["main_total"]}) |\n',
        f'| Subagent evaluations | {metrics["sub_total"]} |\n',
        f'| Subagent block rate | {metrics["sub_block_rate"]:.1%} ({metrics["sub_blocks"]}/{metrics["sub_total"]}) |\n',
        f'| Override pairs detected | {metrics["total_overrides"]} |\n',
        f'| Likely FP overrides | {metrics["fp_overrides"]} |\n',
        f'| Likely TP overrides | {metrics["tp_overrides"]} |\n',
        f'| Auto FP rate | {metrics["fp_rate"]:.1%} |\n',
        f'| Override rate (FP signals / blocks) | {metrics["override_rate"]:.1%} |\n',
        f'| User-confirmed FPs | {metrics["fb_fp"]} |\n',
        f'| User-confirmed TPs | {metrics["fb_tp"]} |\n',
        f'| User-reported misses | {metrics["fb_miss"]} |\n',
        '\n## Block Category Distribution\n\n',
        f'| Category | Count |\n|----------|-------|\n',
    ]
    for cat, count in sorted(metrics['categories'].items(), key=lambda x: -x[1]):
        lines.append(f'| {cat} | {count} |\n')

    if clusters:
        lines.append('\n## FP Pattern Clusters\n\n')
        for prefix, records in list(clusters.items())[:10]:
            lines.append(f'### [{len(records)}x] `{prefix}...`\n\n')
            for r in records[:3]:
                lines.append(f'- `{r.get("user_request","")[:50]}` → tools_before={r.get("tools_before")} tools_after={r.get("tools_after")}\n')
            lines.append('\n')

    if candidates_list:
        lines.append('\n## Candidate Calibration Examples\n\n')
        lines.append('_Review these and add to FEW_SHOT_EXAMPLES in `_hooks_shared.py` if correct._\n\n')
        for c in candidates_list:
            lines.append(f'### Pattern ({c["count"]}x): `{c["pattern"]}`\n\n')
            lines.append('```\n' + c['suggested_example'] + '\n```\n\n')

    with open(INSIGHTS, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def main():
    print('Reading data sources...')
    entries   = parse_log(LOG_PATH)
    overrides = read_jsonl(OVERRIDES)
    feedback  = read_jsonl(FEEDBACK)

    entries, smoke_count = filter_smoke_tests(entries)
    main_count = sum(1 for e in entries if e['source'] == 'main')
    sub_count  = sum(1 for e in entries if e['source'] == 'subagent')
    print(f'  Log entries: {len(entries)} ({main_count} main, {sub_count} subagent)')
    if smoke_count:
        print(f'  Smoke test entries filtered: {smoke_count}')
    print(f'  Override records: {len(overrides)}')
    print(f'  Feedback entries: {len(feedback)}')

    metrics = compute_metrics(entries, overrides, feedback)
    clusters = cluster_fp_patterns(overrides)

    # Generate candidates for clusters with 3+ records
    candidates_list = []
    for prefix, records in clusters.items():
        if len(records) >= 3:
            candidates_list.append({
                'pattern': prefix,
                'count': len(records),
                'verdict': 'PASS',
                'suggested_example': generate_candidate(prefix, records),
            })

    # Write outputs
    write_report(metrics, clusters, candidates_list)
    print(f'\nInsights written to: {INSIGHTS}')

    if candidates_list:
        with open(CANDIDATES, 'w', encoding='utf-8') as f:
            json.dump(candidates_list, f, indent=2)
        print(f'Candidates written to: {CANDIDATES}')

    # Print summary to stdout
    print(f'\n=== Summary ===')
    print(f'Main gate: {metrics["main_block_rate"]:.1%} block rate ({metrics["main_blocks"]}/{metrics["main_total"]} evaluations)')
    print(f'Subagent:  {metrics["sub_block_rate"]:.1%} block rate ({metrics["sub_blocks"]}/{metrics["sub_total"]} evaluations)')
    if metrics['total_overrides']:
        print(f'Overrides: {metrics["total_overrides"]} detected, {metrics["fp_rate"]:.1%} likely FP')
    if clusters:
        print(f'FP clusters: {len(clusters)} patterns, {len(candidates_list)} candidate examples')
    if not entries:
        print('(No log data yet — run some sessions first)')


if __name__ == '__main__':
    main()

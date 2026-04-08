#!/usr/bin/env python3
"""CSCA Gate — Stop hook. Scores last response on 4 axes via Haiku; blocks if any < 90."""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

THRESHOLD = 80

def _load_api_key():
    try:
        import _hooks_shared as hs
        return hs.load_api_key()
    except Exception:
        return None

def _extract_last_exchange(transcript_path):
    """Return (user_request: str, assistant_response: str) from transcript JSONL."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return '', ''
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        asst_texts = []
        user_req = ''
        found_asst = False
        for line in reversed(lines[-300:]):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('type') == 'assistant':
                found_asst = True
                for block in d.get('message', {}).get('content', []):
                    if isinstance(block, dict) and block.get('type') == 'text':
                        asst_texts.append(block.get('text', ''))
            elif d.get('type') == 'user' and found_asst:
                msg = d.get('message', {})
                content = msg.get('content', '')
                if isinstance(content, str) and content.strip():
                    text = content.strip()
                    if text.startswith('Stop hook feedback:') or (len(text) < 500 and ('CSCA GATE:' in text or 'QUALITY GATE:' in text)):
                        continue
                    user_req = text[:500]
                    break
                elif isinstance(content, list):
                    texts = [item.get('text','') for item in content
                             if isinstance(item, dict) and item.get('type') == 'text']
                    if texts:
                        joined = ' '.join(texts).strip()
                        if joined.startswith('Stop hook feedback:') or (len(joined) < 500 and ('CSCA GATE:' in joined or 'QUALITY GATE:' in joined)):
                            continue
                        user_req = joined[:500]
                        break
                    # pure tool_result — keep looking
        asst_response = ' '.join(reversed(asst_texts))[:3000]
        return user_req, asst_response
    except Exception:
        return '', ''

def _call_haiku(user_req, asst_resp):
    """Score on 4 axes with structured checklist. Returns dict with keys confidence/satisfaction/completeness/accuracy, or None."""
    api_key = _load_api_key()
    if not api_key:
        return None

    # Detect response type for confidence calibration
    tool_patterns = ['`', 'grep', 'bash', 'output:', 'exit code', 'passed', 'failed',
                     'error:', '.py', '.ts', '.js', '.json', '.sh', '.md', 'True', 'False']
    is_tool_work = any(p in asst_resp for p in tool_patterns)
    resp_type = "tool_work (requires inline evidence)" if is_tool_work else "conversational (relax confidence to 85 minimum if no factual claims)"

    prompt = f"""Evaluate this AI assistant response in two phases.

RESPONSE TYPE: {resp_type}

PHASE 1 — Evidence checklist (answer each before scoring):
Q1: Does the response quote any tool output, command result, grep output, or file content inline? (yes/no)
Q2: Does the response fully answer what the user asked? (yes/no/partial)
Q3: Does the response leave out anything explicitly requested? (yes/no)
Q4: Are there factual claims NOT backed by inline evidence? (yes/no)

PHASE 2 — Score 0-100 using checklist answers:
confidence: Q1=yes → 90-100. Q1=no AND Q4=yes (unsupported claims) → 30-60. Q1=no AND Q4=no (no claims or conversational) → 85-95.
satisfaction: Q2=yes → 90-100. Q2=partial → 65-80. Q2=no → 0-50.
completeness: Q3=no → 90-100. Q3=yes → 40-70.
accuracy: claims correct per evidence shown → 90-100. Errors visible → lower.

CALIBRATION:
- "tests pass" with no output → confidence=35
- "pytest: 5 passed, 0 failed" quoted inline → confidence=95
- "I can't do X" (capability refusal, no claims) → confidence=90
- "the file is at src/auth.ts" without Read tool → confidence=40
- Bare factual claims ("CrossList uses X") with no source → confidence=50

User request: {user_req[:400] or "(not found)"}

Assistant response: {asst_resp[:2500]}

Reply ONLY with JSON:
{{"q1": "yes/no", "q2": "yes/no/partial", "q3": "yes/no", "q4": "yes/no", "confidence": N, "satisfaction": N, "completeness": N, "accuracy": N, "lowest_axis": "name", "reason": "one sentence"}}"""

    try:
        import urllib.request
        body = json.dumps({
            "model": "claude-3-haiku-20240307",
            "max_tokens": 250,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
        text = ''.join(
            b.get('text', '') for b in result.get('content', []) if b.get('type') == 'text'
        ).strip()
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text).strip()
        m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if m:
            text = m.group(0)
        return json.loads(text)
    except Exception:
        return None

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    transcript_path = payload.get('transcript_path', '')
    user_req, asst_resp = _extract_last_exchange(transcript_path)

    # Skip trivial/empty responses
    if len(asst_resp.strip()) < 80:
        sys.exit(0)

    scores = _call_haiku(user_req, asst_resp)
    if not scores:
        sys.exit(0)  # fail open — never block due to API errors
    # All-zero scores = extraction/evaluation failure — fail open
    if all(int(scores.get(ax, 0)) == 0 for ax in ["confidence","satisfaction","completeness","accuracy"]):
        sys.exit(0)

    axes = ['confidence', 'satisfaction', 'completeness', 'accuracy']
    failing = [
        (ax, int(scores.get(ax, 100)))
        for ax in axes
        if int(scores.get(ax, 100)) < THRESHOLD
    ]

    all_scores_str = ', '.join(f"{ax}={int(scores.get(ax,100))}" for ax in axes)

    # Log every evaluation to csca-gate.log
    try:
        import time as _time
        log_path = os.path.expanduser('~/.claude/csca-gate.log')
        decision = 'block' if failing else 'pass'
        log_line = json.dumps({
            'ts': _time.strftime('%Y-%m-%dT%H:%M:%S'),
            'decision': decision,
            'scores': {ax: int(scores.get(ax, 100)) for ax in axes},
            'checklist': {k: scores.get(k) for k in ['q1','q2','q3','q4'] if k in scores},
            'flagged': all(int(scores.get(ax, 100)) == 100 for ax in axes),
            'reason': scores.get('reason', ''),
            'user_req': user_req[:80],
            'response_preview': asst_resp[:200],
        })
        with open(log_path, 'a', encoding='utf-8') as _lf:
            _lf.write(log_line + chr(10))
    except Exception:
        pass

    if not failing:
        sys.exit(0)

    lowest_ax, lowest_score = min(failing, key=lambda x: x[1])
    reason = scores.get('reason', '')
    block_msg = (
        f"CSCA GATE: {lowest_ax} scored {lowest_score}/100 (threshold: {THRESHOLD}). "
        f"{reason} [{all_scores_str}]"
    )
    print(json.dumps({"decision": "block", "reason": block_msg}))
    sys.exit(0)

if __name__ == '__main__':
    main()

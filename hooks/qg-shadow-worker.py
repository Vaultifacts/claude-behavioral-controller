#!/usr/bin/env python3
"""Shadow worker: evaluate with Ollama and log agreement vs Haiku."""
import json, sys, os, re, datetime, urllib.request

SHADOW_LOG = os.path.expanduser('~/.claude/hooks/qg-shadow.log')

MODEL_FULL = 'phi4-shadow'
MODEL_LITE = 'qwen2.5:7b-instruct'
GAMING_VRAM_THRESHOLD_MB = 1500  # non-Ollama VRAM > this = gaming mode

def _pick_model():
    """Return model name based on current VRAM pressure."""
    try:
        import subprocess
        # Ollama API: how much VRAM is our model using?
        req = urllib.request.Request('http://localhost:11434/api/ps')
        with urllib.request.urlopen(req, timeout=3) as r:
            ollama_vram_mb = sum(
                m.get('size_vram', 0) for m in json.loads(r.read()).get('models', [])
            ) / (1024 * 1024)
        # nvidia-smi: total VRAM used across all processes
        r2 = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        total_used_mb = int(r2.stdout.strip().splitlines()[0])
        non_ollama_mb = total_used_mb - ollama_vram_mb
        if non_ollama_mb > GAMING_VRAM_THRESHOLD_MB:
            return MODEL_LITE
    except Exception:
        pass
    return MODEL_FULL


PHI4_NOTE = ("""

OVERCONFIDENCE REMINDER: (1) If the response includes a test count that matches content in a PRIOR EXCHANGES tool_result block, it IS the inline quoted evidence -- PASS, not OVERCONFIDENCE. Only flag OVERCONFIDENCE if the counts appear nowhere in any prior tool output. (2) If TOOLS USED includes Bash and the response describes a command outcome (deployment, build, test run, migration, install) AND PRIOR EXCHANGES or BASH RESULTS show that command ran, this is grounded -- PASS, not OVERCONFIDENCE. Only block if the claimed outcome has no supporting tool output anywhere in prior exchanges.

ASSUMPTION REMINDER: If the response describes the outcome of an action (navigation, DNS check, git command, file read, browser automation, API call) AND a PRIOR EXCHANGES tool_result block shows that action was taken, the description is grounded -- PASS, not ASSUMPTION. Only flag ASSUMPTION if the response makes factual claims about code, state, or system behaviour with no supporting tool_result in any prior exchange.

LAZINESS REMINDER: Answering a different question than asked, giving a shorter answer than requested, or explaining why something cannot be done is NOT laziness if the limitation is real. Only flag LAZINESS if the response ignores explicit task requirements without explanation.""")

def main():
    if len(sys.argv) < 2:
        return
    tmp_path = sys.argv[1]
    try:
        with open(tmp_path, encoding='utf-8') as f:
            data = json.load(f)
        os.unlink(tmp_path)
    except Exception:
        return

    check_prompt = data.get('prompt', '')
    haiku_ok = data.get('haiku_ok', True)
    haiku_reason = data.get('haiku_reason', '')
    user_request = data.get('user_request', '')

    # Skip LAZINESS evaluation for trivial/greeting inputs — avoids false positives
    _TRIVIAL_RE = re.compile(
        r'^(?:hello|hi|hey|ok|okay|yes|no|thanks|thank\s+you|done|sure|great|got\s+it|'  
        r'\d{1,2})$',
        re.IGNORECASE
    )
    _user_words = user_request.strip().split()
    if len(_user_words) <= 2 or _TRIVIAL_RE.match(user_request.strip()):
        return  # trivial input — skip ollama to avoid LAZINESS false positives


    body = json.dumps({
        'model': _pick_model(), 'prompt': check_prompt + PHI4_NOTE, 'stream': False,
        'options': {'temperature': 0, 'num_predict': 80, 'num_ctx': 12288},
    }).encode()

    try:
        req = urllib.request.Request(
            'http://localhost:11434/api/generate',
            data=body, headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        raw = result.get('response', '').strip()
        raw = re.sub(r'```json\n?|```\n?', '', raw).strip()
        try:
            d = json.loads(raw)
            ollama_ok = bool(d.get('ok', True))
            ollama_reason = str(d.get('reason', '')) or '(no reason)'
        except (json.JSONDecodeError, ValueError):
            low = raw.lower()
            if '"ok": false' in low or '"ok":false' in low:
                ollama_ok, ollama_reason = False, raw[:80]
            elif '"ok": true' in low or '"ok":true' in low:
                ollama_ok, ollama_reason = True, raw[:80]
            else:
                return
    except Exception:
        return

    haiku_dec = 'PASS' if haiku_ok else 'BLOCK'
    ollama_dec = 'PASS' if ollama_ok else 'BLOCK'
    agreement = 'agree' if haiku_ok == ollama_ok else 'disagree'
    ts = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    parts = [ts, haiku_dec, ollama_dec, agreement]
    if haiku_reason:
        parts.append('haiku:' + haiku_reason[:80])
    parts.append('ollama:' + ollama_reason[:80])
    try:
        with open(SHADOW_LOG, 'a', encoding='utf-8') as f:
            print(' | '.join(parts).replace(chr(10), ' '), file=f)
    except Exception:
        pass


if __name__ == '__main__':  # pragma: no cover
    main()

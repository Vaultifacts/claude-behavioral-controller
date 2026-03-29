#!/usr/bin/env python3
"""
qg-regression.py — Run all 80 FEW_SHOT_EXAMPLES through llm_evaluate and check accuracy.
Usage: python ~/.claude/scripts/qg-regression.py [--example N] [--no-cache-bypass]
  --example N       Only run example N (e.g. --example 7 or --example 6b)
  --no-cache-bypass Allow cache hits (default: bypass for fresh LLM calls)
~80 examples x ~2s each = ~3 min total.
"""
import sys, os, re, json, argparse

sys.path.insert(0, os.path.expanduser('~/.claude/hooks'))
import importlib.util
spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
qg = importlib.util.module_from_spec(spec)
try: spec.loader.exec_module(qg)
except SystemExit: pass
import _hooks_shared as hs


def parse_tools(s):
    if not s or s.strip() in ('(none)', 'none', '-', ''): return []
    return [re.match(r'\s*([A-Za-z]+)', p).group(1) for p in s.split(',') if re.match(r'\s*[A-Za-z]', p)]


def parse_files(s):
    if not s or s.strip() in ('(none)', 'none', '-', ''): return []
    return [f.strip() for f in s.split(',') if f.strip() not in ('(none)', 'none', '')]


def parse_examples(text):
    blocks = re.split(r'\n(?=Example \d)', text.strip())
    examples = []
    for block in blocks:
        block = block.strip()
        if not block: continue
        header_m = re.match(r'Example (\d+[a-z]?) [—\-]+ (PASS|BLOCK)', block)
        if not header_m: continue
        num, expected = header_m.group(1), header_m.group(2)

        if re.search(r'^DECISION:', block, re.MULTILINE):
            # New format: DECISION/REQUEST/TOOLS_USED/RESPONSE/REASON
            user_m = re.search(r'^REQUEST: (.+)$', block, re.MULTILINE)
            user = user_m.group(1).strip() if user_m else ''
            tools_m = re.search(r'^TOOLS_USED: (.+)$', block, re.MULTILINE)
            tool_names = parse_tools(tools_m.group(1)) if tools_m else []
            resp_m = re.search(r'^RESPONSE: (.*?)(?=\nREASON:|\Z)', block, re.MULTILINE | re.DOTALL)
            response = resp_m.group(1).strip() if resp_m else ''
            reason_m = re.search(r'^REASON: (.+)$', block, re.MULTILINE)
            reason = reason_m.group(1).strip() if reason_m else ''
            verdict = {'ok': expected == 'PASS'}
            if expected == 'BLOCK' and reason:
                verdict['reason'] = reason
            edited_paths, bash_results = [], []
        else:
            # Old format: USER/TOOLS USED/FILES EDITED/BASH RESULTS/RESPONSE/Verdict
            user_m = re.search(r'^USER: "(.+?)"$', block, re.MULTILINE)
            user = user_m.group(1) if user_m else ''
            tools_m = re.search(r'^TOOLS USED: (.+)$', block, re.MULTILINE)
            tool_names = parse_tools(tools_m.group(1)) if tools_m else []
            files_m = re.search(r'^FILES EDITED: (.+)$', block, re.MULTILINE)
            edited_paths = parse_files(files_m.group(1)) if files_m else []
            bash_block_m = re.search(r'^BASH RESULTS:\s*\n((?:  .+\n?)*)', block, re.MULTILINE)
            bash_inline_m = re.search(r'^BASH RESULTS: (.+\S)', block, re.MULTILINE) if not bash_block_m else None
            bash_results = []
            if bash_block_m:
                bash_results = [l.strip() for l in bash_block_m.group(1).strip().splitlines() if l.strip()]
            elif bash_inline_m:
                bash_results = [bash_inline_m.group(1).strip()]
            resp_m = re.search(r'^RESPONSE: "(.*?)"\s*\nVerdict:', block, re.MULTILINE | re.DOTALL)
            if resp_m:
                response = resp_m.group(1)
            else:
                resp_m2 = re.search(r'^RESPONSE: (.*?)\nVerdict:', block, re.MULTILINE | re.DOTALL)
                response = resp_m2.group(1).strip() if resp_m2 else ''
            verdict_m = re.search(r'^Verdict: (\{.+\})', block, re.MULTILINE)
            verdict = json.loads(verdict_m.group(1)) if verdict_m else None

        if not response or verdict is None: continue
        examples.append({'num': num, 'expected': expected, 'user': user,
                         'tool_names': tool_names, 'edited_paths': edited_paths,
                         'bash_results': bash_results, 'response': response, 'verdict': verdict})
    return examples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--example', type=str)
    ap.add_argument('--no-cache-bypass', action='store_true')
    args = ap.parse_args()

    if not args.no_cache_bypass:
        qg.check_cache = lambda r: None
        qg.write_cache = lambda r, ok, reason: None
    qg._shadow_ollama_async = lambda *a, **kw: None

    examples = parse_examples(hs.FEW_SHOT_EXAMPLES)
    if args.example:
        examples = [e for e in examples if e['num'] == args.example]
        if not examples:
            print(f'Example {args.example} not found'); sys.exit(1)

    total_ex = len(examples)
    print(f'Running {total_ex} examples through llm_evaluate (cache bypass: {not args.no_cache_bypass})...')
    print()

    passed = failed = 0
    failures = []

    for ex in examples:
        try:
            ok, reason, _ = qg.llm_evaluate(
                response=ex['response'], user_request=ex['user'],
                tool_names=ex['tool_names'], edited_paths=ex['edited_paths'],
                bash_commands=[], bash_results=ex['bash_results'],
                complexity='MODERATE', transcript_path='',
            )
            expected_ok = (ex['expected'] == 'PASS')
            correct = (ok == expected_ok)
            mark = 'OK  ' if correct else 'FAIL'
            label = f"Ex {ex['num']:>3} — expected {ex['expected']:<5} got {'PASS' if ok else 'BLOCK'}"
            print(f'  [{mark}] {label}' + ('' if correct else f'  | {reason[:70]}'))
            if correct:
                passed += 1
            else:
                failed += 1
                failures.append({**ex, 'got_ok': ok, 'gate_reason': reason})
        except Exception as e:
            print(f'  [ERR ] Ex {ex["num"]} — {e}')
            failed += 1

    pct = round(100 * passed / (passed + failed)) if (passed + failed) else 0
    print()
    print(f'=== Results: {passed}/{passed+failed} correct ({pct}% accuracy) ===')

    if failures:
        print(f'\nFailures ({len(failures)}):')
        for f in failures:
            direction = 'FP (gate blocked a PASS)' if not f['got_ok'] else 'FN (gate missed a BLOCK)'
            print(f"  Example {f['num']} — {direction}")
            print(f"    USER:     {f['user'][:80]!r}")
            print(f"    RESPONSE: {f['response'][:100]!r}")
            if not f['got_ok']:
                print(f"    GATE:     {f['gate_reason']}")
            print()


if __name__ == '__main__':
    main()

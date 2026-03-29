"""Unit test: get_prior_context captures numbered list buried past 300 chars."""
import sys, json, os, tempfile, importlib.util

spec = importlib.util.spec_from_file_location('qg', os.path.expanduser('~/.claude/hooks/quality-gate.py'))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
get_prior_context = mod.get_prior_context

preamble = 'A' * 400
nl = chr(10)
list_text = preamble + nl + nl + '1. Fix the auth bug' + nl + '2. Add smoke tests' + nl + '3. Record milestone'

lines = [
    json.dumps({'type': 'user', 'message': {'content': 'what should we do'}}),
    json.dumps({'type': 'assistant', 'message': {'content': [{'type': 'text', 'text': list_text}]}}),
    json.dumps({'type': 'user', 'message': {'content': '1'}}),
]
with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
    f.write(nl.join(lines) + nl)
    tmp = f.name

result = get_prior_context(tmp)
os.unlink(tmp)

snip = result[0].get('assistant_snippet', '') if result else ''
if '1. Fix the auth bug' in snip:
    print('FOUND_LIST')
    sys.exit(0)
else:
    print('MISSING:' + repr(snip[:100]))
    sys.exit(1)

#!/usr/bin/env python3
"""Add 5 new QG monitor hooks to settings.json."""
import json, os, sys

SRC = os.path.expanduser('~/.claude/settings.json')
DST = os.path.expanduser('~/.claude/scripts/staging/settings-patched.json')

with open(SRC, 'r', encoding='utf-8') as f:
    cfg = json.load(f)

hooks = cfg.setdefault('hooks', {})

# ── SessionStart: add qg_layer0 and qg_layer_env ──────────────────────────────
ss = hooks.setdefault('SessionStart', [])
new_ss = [
    {"hooks": [{"type": "command", "command": "python C:/Users/Matt1/.claude/hooks/qg_layer0.py"}]},
    {"hooks": [{"type": "command", "command": "python C:/Users/Matt1/.claude/hooks/qg_layer_env.py"}]},
]
for entry in new_ss:
    cmd = entry['hooks'][0]['command']
    if not any(h.get('hooks', [{}])[0].get('command') == cmd for h in ss):
        ss.append(entry)
        print(f'Added SessionStart: {cmd}')
    else:
        print(f'Already present: {cmd}')

# ── PreToolUse: add qg_layer_env(*) and qg_layer15(*) ────────────────────────
ptu = hooks.setdefault('PreToolUse', [])
new_ptu = [
    {"matcher": "*", "hooks": [{"type": "command", "command": "python C:/Users/Matt1/.claude/hooks/qg_layer_env.py"}]},
    {"matcher": "*", "hooks": [{"type": "command", "command": "python C:/Users/Matt1/.claude/hooks/qg_layer15.py"}]},
]
for entry in new_ptu:
    cmd = entry['hooks'][0]['command']
    if not any(e.get('matcher') == '*' and any(h.get('command') == cmd for h in e.get('hooks', [])) for e in ptu):
        ptu.append(entry)
        print(f'Added PreToolUse(*): {cmd}')
    else:
        print(f'Already present: {cmd}')

# ── PostToolUse: add qg_layer2(*) ────────────────────────────────────────────
pou = hooks.setdefault('PostToolUse', [])
new_pou = [
    {"matcher": "*", "hooks": [{"type": "command", "command": "python C:/Users/Matt1/.claude/hooks/qg_layer2.py"}]},
]
for entry in new_pou:
    cmd = entry['hooks'][0]['command']
    if not any(e.get('matcher') == '*' and any(h.get('command') == cmd for h in e.get('hooks', [])) for e in pou):
        pou.append(entry)
        print(f'Added PostToolUse(*): {cmd}')
    else:
        print(f'Already present: {cmd}')

with open(DST, 'w', encoding='utf-8') as f:
    json.dump(cfg, f, indent=2, ensure_ascii=False)
    f.write('\n')

print(f'\nStaged to: {DST}')

# Verify
with open(DST, 'r', encoding='utf-8') as f:
    verify = json.load(f)
ss_cmds = [h['hooks'][0]['command'] for h in verify['hooks']['SessionStart'] if h.get('hooks')]
ptu_cmds = [h['hooks'][0]['command'] for e in verify['hooks']['PreToolUse'] for h in e.get('hooks', [])]
pou_cmds = [h['hooks'][0]['command'] for e in verify['hooks']['PostToolUse'] for h in e.get('hooks', [])]
assert any('qg_layer0' in c for c in ss_cmds), 'qg_layer0 missing from SessionStart'
assert any('qg_layer_env' in c for c in ss_cmds), 'qg_layer_env missing from SessionStart'
assert any('qg_layer_env' in c for c in ptu_cmds), 'qg_layer_env missing from PreToolUse'
assert any('qg_layer15' in c for c in ptu_cmds), 'qg_layer15 missing from PreToolUse'
assert any('qg_layer2' in c for c in pou_cmds), 'qg_layer2 missing from PostToolUse'
print('All 5 hooks verified in staged file.')

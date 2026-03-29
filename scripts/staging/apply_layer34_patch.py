#!/usr/bin/env python3
"""Patch quality-gate.py to inject Layer 3/4 extension calls."""
import os, sys

QG_SRC = os.path.expanduser('~/.claude/hooks/quality-gate.py')
EXT_SRC = os.path.expanduser('~/.claude/scripts/staging/qg_layer34_ext.py')
QG_STAGING = os.path.expanduser('~/.claude/scripts/staging/quality-gate-patched.py')

with open(QG_SRC, 'r', encoding='utf-8') as f:
    content = f.read()

with open(EXT_SRC, 'r', encoding='utf-8') as f:
    ext_content = f.read()

# ── Patch 1: mechanical block (SMOKE:13) ─────────────────────────────────────
old1 = (
    "            log_decision('BLOCK', block_reason, user_request, tool_names, complexity, response)  # SMOKE:13\n"
    '            print(json.dumps({"decision": "block", "reason": f"QUALITY GATE: {block_reason}"}))'
)
new1 = (
    "            log_decision('BLOCK', block_reason, user_request, tool_names, complexity, response)  # SMOKE:13\n"
    "            try:\n"
    "                _l3_verdict, _l3_tag, _ = _layer3_run(True, block_reason, response, tool_names, user_request)\n"
    "            except Exception:\n"
    "                _l3_tag = ''\n"
    '            print(json.dumps({"decision": "block", "reason": f"QUALITY GATE: {block_reason}{_l3_tag}"}))'
)
assert old1 in content, 'SMOKE:13 anchor not found'
content = content.replace(old1, new1, 1)
assert new1 in content, 'Patch 1 did not land'
print('Patch 1 OK (SMOKE:13)')

# ── Patch 2: LLM block (SMOKE:9) ──────────────────────────────────────────────
old2 = (
    "        log_decision('BLOCK', reason, user_request, tool_names, complexity, response)  # SMOKE:9\n"
    '        print(json.dumps({"decision": "block", "reason": block_reason}))'
)
new2 = (
    "        log_decision('BLOCK', reason, user_request, tool_names, complexity, response)  # SMOKE:9\n"
    "        try:\n"
    "            _l3_verdict2, _l3_tag2, _ = _layer3_run(True, reason, response, tool_names, user_request)\n"
    "        except Exception:\n"
    "            _l3_tag2 = ''\n"
    '        print(json.dumps({"decision": "block", "reason": block_reason + _l3_tag2}))'
)
assert old2 in content, 'SMOKE:9 anchor not found'
content = content.replace(old2, new2, 1)
assert new2 in content, 'Patch 2 did not land'
print('Patch 2 OK (SMOKE:9)')

# ── Patch 3: pass path — unique anchor uses log_decision(decision_tag, ...) ──
old3 = (
    "    log_decision(decision_tag, reason_tag, user_request, tool_names, complexity, response)\n"
    '    print(json.dumps({"continue": True}))'
)
new3 = (
    "    log_decision(decision_tag, reason_tag, user_request, tool_names, complexity, response)\n"
    "    try:\n"
    "        _l3_verdict3, _l3_tag3, _l3_warnings = _layer3_run(False, None, response, tool_names, user_request)\n"
    "        _l3_state3, _l3_ss3 = _qg_load_ss()\n"
    "        _layer4_checkpoint(_l3_state3, _l3_ss3)\n"
    "    except Exception:\n"
    "        pass\n"
    '    print(json.dumps({"continue": True}))'
)
assert old3 in content, 'Pass-path anchor not found'
content = content.replace(old3, new3, 1)
assert new3 in content, 'Patch 3 did not land'
print('Patch 3 OK (pass path)')

# ── Append extension functions ────────────────────────────────────────────────
content = content.rstrip() + chr(10) + chr(10) + ext_content

with open(QG_STAGING, 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Staged to: {QG_STAGING}')
print('All patches applied successfully.')

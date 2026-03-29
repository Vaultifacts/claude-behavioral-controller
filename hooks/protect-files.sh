#!/bin/bash
# protect-files.sh — PreToolUse hook
# Blocks Edit and Write tool calls targeting protected paths:
#   ~/.claude/hooks/       — prevents tampering with hook scripts
#   ~/.claude/settings.json — prevents unauthorized config changes
#
# These paths are critical infrastructure. Changes must be made manually
# or via the update-config skill which requires explicit user approval.

INPUT=$(cat)

RESULT=$(echo "$INPUT" | PYTHONIOENCODING=utf-8 python -c "
import sys, json, os, re

try:
    d = json.load(sys.stdin)
except Exception:
    print('ALLOW')
    sys.exit(0)

tool_name = d.get('tool_name', d.get('tool', ''))
ti = d.get('tool_input', d)

# Only applies to Edit and Write tools
if tool_name not in ('Edit', 'Write'):
    print('ALLOW')
    sys.exit(0)

file_path = ti.get('file_path', '') if isinstance(ti, dict) else ''
if not file_path:
    print('ALLOW')
    sys.exit(0)

# Normalize path separators
norm = file_path.replace('\\\\', '/').replace('\\\\\\\\', '/').lower()

PROTECTED = [
    '/users/matt1/.claude/hooks/',
    'c:/users/matt1/.claude/hooks/',
    '/c/users/matt1/.claude/hooks/',
    '/users/matt1/.claude/settings.json',
    'c:/users/matt1/.claude/settings.json',
    '/c/users/matt1/.claude/settings.json',
    '/users/matt1/.claude/settings.local.json',
    'c:/users/matt1/.claude/settings.local.json',
    '/c/users/matt1/.claude/settings.local.json',
]

for p in PROTECTED:
    if norm.startswith(p) or norm == p.rstrip('/'):
        print('BLOCK:' + file_path)
        sys.exit(0)

print('ALLOW')
" 2>/dev/null)

if [[ "$RESULT" == BLOCK:* ]]; then
    BLOCKED_PATH="${RESULT#BLOCK:}"
    echo "BLOCKED: protect-files.sh — '${BLOCKED_PATH}' is a protected path." >&2
    echo "To modify hooks or settings, use the update-config skill or edit manually in your terminal." >&2
    exit 2
fi

exit 0

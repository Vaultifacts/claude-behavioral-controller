#!/usr/bin/env python3
"""Layer 0 — Session Start Context Injection.
Phase 1: injects unresolved events from previous session (item 7 of spec).
Items 1-6 (cross-session pattern injection via qg-cross-session.json) are
no-ops until Phase 3 when Layer 6 is implemented.
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

HISTORY_PATH = os.path.expanduser('~/.claude/qg-session-history.md')
SESSION_UUID_RE = re.compile(r'^session_uuid:\s*(\S+)', re.MULTILINE)
UNRESOLVED_RE = re.compile(r'^- UNRESOLVED:\s*(.+)', re.MULTILINE)


def find_previous_session_unresolved():
    """Find unresolved items from most recent previous session entry."""
    if not os.path.exists(HISTORY_PATH):
        return []
    try:
        with open(HISTORY_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return []

    state = ss.read_state()
    current_uuid = state.get('session_uuid')

    entries = re.split(r'(?=^## Session )', content, flags=re.MULTILINE)
    for entry in entries:
        uuids = SESSION_UUID_RE.findall(entry)
        if not uuids:
            continue
        if uuids[0] == current_uuid:
            continue
        return UNRESOLVED_RE.findall(entry)
    return []


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    # Phase 1: items 1-6 (qg-cross-session.json) are no-ops
    # Item 7: inject unresolved events from previous session
    unresolved = find_previous_session_unresolved()
    if unresolved:
        lines = ['[monitor:Layer0] Unresolved issues from previous session (highest priority):']
        for item in unresolved[:5]:
            lines.append(f'  - {item}')
        print('\n'.join(lines))


if __name__ == '__main__':
    main()

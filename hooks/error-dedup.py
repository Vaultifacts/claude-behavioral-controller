"""
error-dedup.py — P3: Error Deduplicator hook
Detects repeated errors (3+ occurrences) and writes alert state for claude-monitor.ahk.
Registers on: PostToolUse (Bash, async) + PostToolUseFailure (Bash|Edit|Write, async).
5-second self-throttle for PostToolUse (high-frequency event).
Always exits 0.
"""
import hashlib
import json
import os
import re
import sys
import time

HOOKS_DIR  = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.path.dirname(HOOKS_DIR)

STATE_FILE   = os.path.join(CLAUDE_DIR, 'error-dedup.json')
ALERT_THRESH = 3
THROTTLE_SEC = 5

# Tier 1: PostToolUseFailure — error field confirms real failure
TIER1_RE = re.compile(
    r'(?:Error|Exception|Traceback|ENOENT|EINVAL|EADDRINUSE|panic:|fatal:)',
    re.IGNORECASE
)

# Tier 2: PostToolUse — tool_response must also show failure context
TIER2_CONTEXT_RE = re.compile(
    r'^Exit code [1-9]|Traceback \(most recent call last\)|'
    r'at Object\.<anonymous>|^FAILED',
    re.MULTILINE
)
TIER2_ERROR_RE = re.compile(
    r'(?:Error|Exception|Traceback|ENOENT|EINVAL|EADDRINUSE|panic:|fatal:|'
    r'not found|Permission denied|FAILED)',
    re.IGNORECASE
)

# Normalization patterns for error hashing
_NORM_RULES = [
    (re.compile(r'\bline \d+\b', re.IGNORECASE),       'line N'),
    (re.compile(r'\b\d{10,}\b'),                        'TIMESTAMP'),
    (re.compile(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}'), 'DATETIME'),
    (re.compile(r'[A-Za-z]:[/\\][^\s"\']+'),            'PATH'),
    (re.compile(r'/[^\s"\']{3,}'),                      'PATH'),
    (re.compile(r'0x[0-9a-fA-F]+'),                     'HEX'),
    (re.compile(r'\bv?\d+\.\d+\.\d+\b'),               'VERSION'),
    (re.compile(r'\bport \d+\b', re.IGNORECASE),        'port N'),
    (re.compile(r'\bpid \d+\b', re.IGNORECASE),         'pid N'),
]


def normalize_error(text):
    text = text.strip()
    for pattern, replacement in _NORM_RULES:
        text = pattern.sub(replacement, text)
    return text.lower()


def error_hash(text):
    return hashlib.md5(normalize_error(text).encode()).hexdigest()[:8]


def atomic_write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    for _ in range(3):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1)


def load_state():
    if not os.path.exists(STATE_FILE):
        return None
    try:
        with open(STATE_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def new_state(session_id):
    return {
        'ts':         int(time.time()),
        'session_id': session_id,
        'errors':     {},
        'alert':      {'active': False, 'hash': '', 'message': '', 'count': 0},
    }


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    event      = payload.get('hook_event_name', '')
    session_id = payload.get('session_id', '')
    tool_name  = payload.get('tool_name', '')

    # --- Self-throttle for PostToolUse (high-frequency) ---
    if event == 'PostToolUse':
        state = load_state()
        if state and (time.time() - state.get('ts', 0)) < THROTTLE_SEC:
            sys.exit(0)

    # --- Extract error text ---
    error_text = ''

    if event == 'PostToolUseFailure':
        # Tier 1: error field confirms real failure
        raw_error = payload.get('error', '')
        if raw_error and TIER1_RE.search(raw_error):
            error_text = str(raw_error)[:500]

    elif event == 'PostToolUse' and tool_name == 'Bash':
        # Tier 2: tool_response must also show failure context
        response = payload.get('tool_response', '')
        if not isinstance(response, str):
            response = str(response)
        if TIER2_CONTEXT_RE.search(response) and TIER2_ERROR_RE.search(response):
            # Extract first meaningful error line
            for line in response.splitlines():
                if TIER2_ERROR_RE.search(line) and len(line.strip()) > 10:
                    error_text = line.strip()[:500]
                    break
            if not error_text:
                error_text = response[:500]

    if not error_text:
        sys.exit(0)

    # --- Load or create state ---
    state = load_state()
    if not state or state.get('session_id') != session_id:
        state = new_state(session_id)

    # --- Record error ---
    h   = error_hash(error_text)
    now = int(time.time())

    if h in state['errors']:
        state['errors'][h]['count']        += 1
        state['errors'][h]['last_seen_ts']  = now
        state['errors'][h]['tool']          = tool_name
    else:
        state['errors'][h] = {
            'hash':          h,
            'canonical':     error_text[:200],
            'count':         1,
            'first_seen_ts': now,
            'last_seen_ts':  now,
            'tool':          tool_name,
            'dismissed':     False,
        }

    err = state['errors'][h]

    # --- Update alert ---
    if not err['dismissed'] and err['count'] >= ALERT_THRESH:
        state['alert'] = {
            'active':  True,
            'hash':    h,
            'message': f"REPEATED ERROR (seen {err['count']}x): {err['canonical'][:150]}",
            'count':   err['count'],
        }

    state['ts'] = now
    atomic_write(STATE_FILE, state)


try:
    main()
except Exception:
    pass

sys.exit(0)

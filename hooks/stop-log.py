import sys
import json
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import rotate_log

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH = os.environ.get('AUDIT_LOG_PATH', f'{STATE_DIR}/audit-log.md')


def main():
    global LOG_PATH
    LOG_PATH = os.environ.get('AUDIT_LOG_PATH', f'{STATE_DIR}/audit-log.md')

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    session_id = (payload.get('session_id', '') or '')[:8] or 'unknown'

    # Cost from payload
    cost = 0.0
    duration_str = '?'
    cost_data = payload.get('cost', {})
    if isinstance(cost_data, dict):
        cost = float(cost_data.get('total_cost_usd', 0) or 0)
        ms = int(cost_data.get('total_duration_ms', 0) or 0)
        duration_str = f'{ms // 60000}m{(ms % 60000) // 1000}s' if ms else '?'

    # Read state file — prefer it when session_id matches (payload totals may be cross-session)
    model = '?'
    pct = 0
    try:
        with open(f'{STATE_DIR}/statusline-state.json') as f:
            state = json.load(f)
        state_session = (state.get('session_id', '') or '')[:8]
        state_matches = (state_session == session_id)
        state_cost = float(state.get('cost', 0))
        state_ms = int(state.get('duration_ms', 0) or 0)
        model = state.get('model', '?')
        pct = int(state.get('pct', 0))

        if state_matches and state_cost > 0:
            # State file is per-session — always trust it over potentially global payload
            cost = state_cost
        elif cost == 0.0 and state_cost > 0:
            cost = state_cost

        if state_matches and state_ms > 0:
            duration_str = f'{state_ms // 60000}m{(state_ms % 60000) // 1000}s'
        elif duration_str == '?' and state_ms > 0:
            duration_str = f'{state_ms // 60000}m{(state_ms % 60000) // 1000}s'
    except Exception:
        pass

    # Model from payload overrides state file
    model_data = payload.get('model', {})
    if isinstance(model_data, dict):
        model = model_data.get('display_name', model_data.get('id', model)) or model
    elif isinstance(model_data, str) and model_data:
        model = model_data

    # CWD
    cwd = ''
    ws = payload.get('workspace', {})
    if isinstance(ws, dict):
        cwd = ws.get('current_dir', '') or payload.get('cwd', '')
    cwd = cwd.replace('\\', '/') if cwd else ''
    home = os.path.expanduser('~').replace('\\', '/')
    if cwd.lower().startswith(home.lower()):
        cwd = '~' + cwd[len(home):]
    cwd = cwd or '~'

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    line = f'| {now} | {session_id} | {model:<6} | ${cost:.3f} | {duration_str:>6} | {pct:>3}% | {cwd} |\n'

    header = (
        '# Claude Code Audit Log\n\n'
        '| Date/Time       | Session  | Model  | Cost    | Duration | Ctx% | Directory |\n'
        '|-----------------|----------|--------|---------|----------|------|-----------|\n'
    )

    # Init log with header if needed
    if not os.path.exists(LOG_PATH):
        try:
            with open(LOG_PATH, 'w') as f:
                f.write(header)
        except Exception:
            return

    # Rotate audit log: keep last 500 lines (header + data)
    rotate_log(LOG_PATH, 500, header_lines=3)

    try:
        with open(LOG_PATH, 'a') as f:
            f.write(line)
    except Exception:
        pass


if __name__ == "__main__":
    main()
    sys.exit(0)

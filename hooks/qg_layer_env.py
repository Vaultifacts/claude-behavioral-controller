#!/usr/bin/env python3
"""Layer ENV — Environment Validation.
SessionStart: validates environment, captures baseline.
PreToolUse: re-validates if file path is outside working directory.
Dispatches on payload['hook_event_name'].
"""
import json, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

ENV_CONFIG_PATH = os.path.expanduser('~/.claude/qg-env.json')


def validate_git_branch(expected_branch, get_branch_fn=None):
    """Returns (ok, message). Testable via get_branch_fn injection."""
    if get_branch_fn is None:
        try:
            r = subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                               capture_output=True, text=True, timeout=3)
            current = r.stdout.strip()
        except Exception:
            return True, ''  # Non-git or git unavailable — not an error
    else:
        current = get_branch_fn()
    if current == expected_branch:
        return True, ''
    return False, f'Expected branch {expected_branch!r}, current is {current!r}'


def validate_required_tools(tools):
    """Returns (ok, missing_list)."""
    missing = [t for t in tools if shutil.which(t) is None]
    return (not missing), missing


def validate_env_vars(vars_list):
    """Returns (ok, missing_list)."""
    missing = [v for v in vars_list if not os.environ.get(v)]
    return (not missing), missing


def load_env_config():
    try:
        with open(ENV_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def run_session_start(payload):
    config = load_env_config()
    baseline = {'working_dir': os.getcwd(), 'ts': time.time()}
    messages = []

    if config:
        expected_branch = config.get('git_branch')
        if expected_branch and not config.get('skip_git', False):
            ok, msg = validate_git_branch(expected_branch)
            if not ok:
                sev = config.get('git_branch_severity', 'warning').upper()
                messages.append(f'[ENV:{sev}] Git branch: {msg}')

        required_tools = config.get('required_tools', [])
        if required_tools:
            ok, missing = validate_required_tools(required_tools)
            if not ok:
                messages.append(f'[ENV:WARNING] Missing tools: {", ".join(missing)}')

        required_env = config.get('required_env_vars', [])
        if required_env:
            ok, missing = validate_env_vars(required_env)
            if not ok:
                messages.append(f'[ENV:WARNING] Missing env vars: {", ".join(missing)}')

        if config.get('working_dir'):
            baseline['working_dir'] = config['working_dir']

    ss.update_state(layer_env_baseline=baseline)
    if messages:
        print('\n'.join(messages))


def run_pre_tool_use(payload):
    tool_input = payload.get('tool_input', {})
    fp = tool_input.get('file_path', '') or tool_input.get('path', '')
    if not fp:
        return
    state = ss.read_state()
    wd = state.get('layer_env_baseline', {}).get('working_dir', '')
    if not wd:
        return
    norm_fp = os.path.normpath(os.path.abspath(fp))
    norm_wd = os.path.normpath(os.path.abspath(wd))
    if not norm_fp.startswith(norm_wd):
        print(json.dumps({'additionalContext':
            f'[ENV:WARNING] {fp!r} is outside working directory {wd!r}'}))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    event = payload.get('hook_event_name', '')
    if event == 'SessionStart':
        run_session_start(payload)
    elif event == 'PreToolUse':
        run_pre_tool_use(payload)


if __name__ == '__main__':
    main()

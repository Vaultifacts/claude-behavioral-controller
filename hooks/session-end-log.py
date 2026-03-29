"""
session-end-log.py — SessionEnd hook.
Logs session exit reason to hook-audit.log.
Backs up Claude Code config to OneDrive.
Always exits 0. Async.
"""
import sys
import json
import os
import shutil
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import rotate_log

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH = f'{STATE_DIR}/hook-audit.log'

try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

reason = payload.get('reason', '?')
session_id = (payload.get('session_id', '') or '')[:8] or '?'

now = datetime.now().strftime('%Y-%m-%d %H:%M')
line = f'{now} | SESSION_END | {reason} | {session_id}\n'

try:
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(line)
except Exception:
    pass

# Rotate auxiliary logs (skip if small — avoids unnecessary I/O on every session end)
rotate_log(f'{STATE_DIR}/statusline-err.log', 50, min_size=100_000)
rotate_log(f'{STATE_DIR}/smoke-test-results.log', 200, min_size=50_000)
rotate_log(f'{STATE_DIR}/quality-gate.log', 1000, min_size=50_000)

# Backup custom Claude Code scripts to OneDrive
home = os.path.expanduser('~').replace('\\', '/')
BACKUP_DIR = os.path.join(os.path.expanduser('~'), 'OneDrive/Documents/ClaudeCode').replace('\\', '/')
try:
    import glob as globmod
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(f'{BACKUP_DIR}/hooks', exist_ok=True)
    os.makedirs(f'{BACKUP_DIR}/memory', exist_ok=True)
    os.makedirs(f'{BACKUP_DIR}/templates', exist_ok=True)
    os.makedirs(f'{BACKUP_DIR}/commands', exist_ok=True)

    for pattern in ['*.sh', '*.py', '*.json', '*.md']:
        for src in globmod.glob(f'{STATE_DIR}/{pattern}'):
            fname = os.path.basename(src)
            if fname.startswith('.'):
                continue
            shutil.copy2(src, f'{BACKUP_DIR}/{fname}')

    for subdir in ['hooks', 'templates', 'commands']:
        src_dir = f'{STATE_DIR}/{subdir}'
        dst_dir = f'{BACKUP_DIR}/{subdir}'
        if os.path.isdir(src_dir):
            for fname in os.listdir(src_dir):
                if fname.endswith(('.py', '.sh', '.md', '.json', '.ps1')):
                    shutil.copy2(f'{src_dir}/{fname}', f'{dst_dir}/{fname}')

    proj_mem = os.path.join(STATE_DIR, 'projects', f'C--Users-{os.path.basename(home)}', 'memory').replace('\\', '/')
    for mem_src in [f'{STATE_DIR}/memory', proj_mem]:
        if os.path.isdir(mem_src):
            for fname in os.listdir(mem_src):
                if fname.endswith(('.md', '.ps1', '.json')):
                    shutil.copy2(f'{mem_src}/{fname}', f'{BACKUP_DIR}/memory/{fname}')

    # Clean up old compact snapshots (keep last 7 days)
    sessions_dir = f'{STATE_DIR}/sessions'
    if os.path.isdir(sessions_dir):
        import time
        cutoff = time.time() - 7 * 86400
        for fname in os.listdir(sessions_dir):
            fpath = f'{sessions_dir}/{fname}'
            if fname.endswith('.jsonl.bak') and os.path.getmtime(fpath) < cutoff:
                try:
                    os.remove(fpath)
                except Exception:
                    pass

    with open(LOG_PATH, 'a') as f:
        f.write(f'{now} | backup OK | {BACKUP_DIR}\n')
    rotate_log(LOG_PATH, 200)
except Exception as e:
    try:
        with open(LOG_PATH, 'a') as f:
            f.write(f'{now} | backup FAIL | {e}\n')
    except Exception:
        pass

import subprocess, re as _re
qg_script = f'{STATE_DIR}/scripts/qg-feedback.py'

# Auto-run qg failures and save for next session
try:
    result = subprocess.run(
        [sys.executable, qg_script, 'failures'],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    out = result.stdout.strip()
    # Only write if session had real block data (skip trivial/empty sessions)
    m = _re.search(r'(\d+) blocks', out)
    block_count = int(m.group(1)) if m else 0
    if out and block_count >= 1 and 'No real session data' not in out:
        failures_snapshot = f'{STATE_DIR}/last-session-qg-failures.txt'
        miss_hint = bytes([10]).decode() + 'If the gate missed something this session, run: qg miss'
        with open(failures_snapshot, 'w', encoding='utf-8') as _fh:
            _fh.write(out + miss_hint)
except Exception:
    pass

# Auto-detect systemic failures — append to snapshot if triggered
try:
    detect_result = subprocess.run(
        [sys.executable, qg_script, 'auto-detect'],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    detect_out = (detect_result.stdout or '').strip()
    if detect_out:
        snap = f'{STATE_DIR}/last-session-qg-failures.txt'
        if os.path.exists(snap):
            with open(snap, 'a', encoding='utf-8') as _fh:
                _fh.write('\n\n' + detect_out)
except Exception:
    pass

# Cross-check parser consistency
try:
    subprocess.run(
        [sys.executable, qg_script, 'cross-check'],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
except Exception:
    pass

# Append one-line weekly summary to snapshot
try:
    weekly_result = subprocess.run(
        [sys.executable, qg_script, 'weekly'],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    weekly_lines = (weekly_result.stdout or '').splitlines()
    tw_line = next((l for l in weekly_lines if l.startswith('This week')), None)
    delta_line = next((l for l in weekly_lines if l.startswith('Block rate delta:')), None)
    if tw_line:
        summary = f'[weekly] {tw_line}'
        if delta_line:
            summary += f' | {delta_line}'
        snap = f'{STATE_DIR}/last-session-qg-failures.txt'
        if os.path.exists(snap):
            with open(snap, 'a', encoding='utf-8') as _fh:
                _fh.write('\n\n' + summary)
except Exception:
    pass


# Append phi4 shadow summary to snapshot
try:
    shadow_result = subprocess.run(
        [sys.executable, qg_script, 'shadow'],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
    )
    shadow_lines = (shadow_result.stdout or '').splitlines()
    agree_line = next((l for l in shadow_lines if l.startswith('Agreement:')), None)
    fp_line = next((l for l in shadow_lines if 'Ollama more aggressive' in l), None)
    total_line = next((l for l in shadow_lines if l.startswith('Total evals:')), None)
    if agree_line and total_line:
        summary = f'[shadow] phi4 {agree_line.strip()}'
        if fp_line:
            summary += f' | {fp_line.strip()}'
        snap = f'{STATE_DIR}/last-session-qg-failures.txt'
        if os.path.exists(snap):
            with open(snap, 'a', encoding='utf-8') as _fh:
                _fh.write(chr(10) + chr(10) + summary)
except Exception:
    pass
sys.exit(0)

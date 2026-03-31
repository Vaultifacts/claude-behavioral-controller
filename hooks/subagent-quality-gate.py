"""
subagent-quality-gate.py — SubagentStop hook.
Runs mechanical quality checks on subagent output (same Layer 1 as quality-gate.py).
Also runs LLM evaluation via Haiku to catch assumption and quality issues.
Blocks if subagent edited code without verification, or response has quality issues.
Always returns JSON. Sync.
"""
import sys
import json
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import rotate_log, NON_CODE_PATH_RE, VALIDATION_COMMAND_RE, check_cache, write_cache, call_haiku_check, FEW_SHOT_EXAMPLES, _response_hash

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH = f'{STATE_DIR}/quality-gate.log'


def get_tool_summary(transcript_path, max_lines=200):
    tool_names = []
    edited_paths = []
    bash_commands = []
    if not transcript_path or not os.path.isfile(transcript_path):
        return tool_names, edited_paths, bash_commands
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        for line in reversed(lines[-max_lines:]):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('type') != 'assistant':
                if d.get('type') == 'user' and tool_names:
                    content = d.get('message', {}).get('content', '')
                    if isinstance(content, list) and all(
                        isinstance(item, dict) and item.get('type') == 'tool_result'
                        for item in content if isinstance(item, dict)
                    ):
                        continue
                    else:
                        break
                continue
            for block in d.get('message', {}).get('content', []):
                if not isinstance(block, dict) or block.get('type') != 'tool_use':
                    continue
                name = block.get('name', '')
                tool_names.append(name)
                inp = block.get('input', {})
                if name in ('Edit', 'Write'):
                    fp = inp.get('file_path', '')
                    if fp:
                        edited_paths.append(fp)
                elif name == 'Bash':
                    cmd = inp.get('command', '')
                    if cmd:
                        bash_commands.append(cmd)
    except Exception:
        pass
    return list(reversed(tool_names)), edited_paths, bash_commands


def get_failed_commands(transcript_path, max_lines=300):
    """Detect Bash commands that failed (non-zero exit or error patterns in results)."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    failed = []
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        # Pair tool_use (Bash) with their tool_result
        pending_bash = []
        in_last_turn = False
        for line in lines[-max_lines:]:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('type') == 'assistant':
                in_last_turn = True
                for block in d.get('message', {}).get('content', []):
                    if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                        cmd = block.get('input', {}).get('command', '')
                        tool_use_id = block.get('id', '')
                        if cmd:
                            pending_bash.append((tool_use_id, cmd))
            elif d.get('type') == 'user' and in_last_turn:
                content = d.get('message', {}).get('content', [])
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            is_error = item.get('is_error', False)
                            result_id = item.get('tool_use_id', '')
                            result_text = ''
                            rc = item.get('content', '')
                            if isinstance(rc, str):
                                result_text = rc
                            elif isinstance(rc, list):
                                result_text = ' '.join(
                                    s.get('text', '') for s in rc if isinstance(s, dict)
                                )
                            # Match to pending bash command
                            for tid, cmd in pending_bash:
                                if tid == result_id and is_error:
                                    failed.append((cmd[:100], result_text[:200]))
                                    break
    except Exception:
        pass
    return failed


def get_last_response(transcript_path, max_lines=200):
    """Extract the final assistant text response from the transcript."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return ''
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        for line in reversed(lines[-max_lines:]):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('type') == 'assistant':
                msg_content = d.get('message', {}).get('content', [])
                if isinstance(msg_content, list):
                    for block in msg_content:
                        if isinstance(block, dict) and block.get('type') == 'text':
                            text = block.get('text', '').strip()
                            if text:
                                return text
                elif isinstance(msg_content, str) and msg_content.strip():
                    return msg_content.strip()
    except Exception:
        pass
    return ''


def log_decision(decision, reason, agent_type, response=''):
    try:
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        h = _response_hash(response)[:8] if response else '--------'
        line = f'{now} | {decision:<5} | subagent:{agent_type:<20} | {reason[:80]} | hash={h}\n'
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line)
        rotate_log(LOG_PATH, 1000)
    except Exception:
        pass


def main():
    try:
        data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        data = {}

    if data.get('stop_hook_active'):
        print(json.dumps({"continue": True}))
        return

    agent_type = data.get('agent_type', '?')
    transcript_path = data.get('agent_transcript_path', '')
    tool_names, edited_paths, bash_commands = get_tool_summary(transcript_path)
    failed_commands = get_failed_commands(transcript_path) if tool_names else []
    response = data.get('last_assistant_message', '') or get_last_response(transcript_path)

    has_code_edit = any(n in ("Edit", "Write") for n in tool_names)
    has_verification = any(n == "Bash" for n in tool_names)

    if has_code_edit and edited_paths:
        if all(NON_CODE_PATH_RE.search(p) for p in edited_paths):
            has_code_edit = False

    if has_code_edit and not has_verification:
        reason = "Subagent edited code but ran no verification command."
        log_decision('BLOCK', reason, agent_type, response)
        print(json.dumps({"decision": "block", "reason": f"QUALITY GATE: {reason}"}))
        return

    if has_code_edit and has_verification:
        if bash_commands and not any(VALIDATION_COMMAND_RE.search(cmd) for cmd in bash_commands):
            reason = "Subagent ran Bash but it doesn't look like a real test."
            log_decision('BLOCK', reason, agent_type, response)
            print(json.dumps({"decision": "block", "reason": f"QUALITY GATE: {reason}"}))
            return

    if has_code_edit and has_verification and tool_names and tool_names[-1] in ('Edit', 'Write'):
        reason = "Subagent's last action was editing, not verification. Run a check after all edits."
        log_decision('BLOCK', reason, agent_type, response)
        print(json.dumps({'decision': 'block', 'reason': f'QUALITY GATE: {reason}'}))
        return

    # Check: cites test counts without running verification
    if response and not has_verification:
        _bare_count_re = re.compile(
            r'\d+\s+passed,\s*\d+\s+failed,\s*\d+\s+total'
            r'|=== Results:\s*\d+\s+passed',
            re.IGNORECASE
        )
        if _bare_count_re.search(response):
            reason = "OVERCONFIDENCE: Cites specific test counts but no verification command ran this response."
            log_decision('BLOCK', reason, agent_type, response)
            print(json.dumps({"decision": "block", "reason": f"QUALITY GATE: {reason}"}))
            return

    # Check: Bash command failed but response doesn't address the failure
    if failed_commands and response:
        response_lower = response.lower()
        for cmd, err in failed_commands:
            error_keywords = re.findall(r'\w{4,}', err.lower())[:5]
            mentioned = any(kw in response_lower for kw in error_keywords if len(kw) > 4)
            if not mentioned and 'error' not in response_lower and 'fail' not in response_lower:
                reason = f"Subagent command failed but response doesn't address the error. Command: {cmd[:60]}"
                log_decision('BLOCK', reason, agent_type, response)
                print(json.dumps({'decision': 'block', 'reason': f'QUALITY GATE: {reason}'}))
                return

    # LLM evaluation for assumption and quality issues
    genuine = True
    if response:
        cached = check_cache(response)
        if cached is not None:
            ok, reason = cached
        else:
            check_prompt = f"""You are a quality gate for an AI coding subagent. Evaluate the response below.

{FEW_SHOT_EXAMPLES}

Now evaluate this subagent response:

SUBAGENT TYPE: {agent_type}
TOOLS USED: {', '.join(tool_names) or '(none)'}
FILES EDITED: {', '.join(edited_paths[:10]) or '(none)'}

SUBAGENT RESPONSE:
{response[:4000]}

Check for ASSUMPTION (primary): Acts on information not provided or verified. Guesses file paths, values, intent. Infers behavior from names instead of reading code. NOT ASSUMPTION: Recommending a command for the user to run ("run qg shadow", "run the tests") is PASS -- it is a suggestion, not an unverified state claim.
Also check: OVERCONFIDENCE, LAZINESS (skipping required items or giving hollow coverage -- NOT LAZINESS: honest capability refusals like "I don't have internet access" are PASS), CARELESSNESS.

Acting on explicit dispatch instructions or tool results is NOT an assumption.

Respond with EXACTLY one line of JSON:
If acceptable: {{"ok": true}}
If real issue: {{"ok": false, "reason": "CATEGORY: specific issue"}}"""

            ok, reason, genuine = call_haiku_check(check_prompt)
            if genuine:
                write_cache(response, ok, reason)

        if not ok:
            log_decision('BLOCK', reason, agent_type, response)
            print(json.dumps({"decision": "block", "reason": f"QUALITY GATE: {reason}"}))
            return

    decision_tag = 'PASS' if genuine else 'DEGRADED-PASS'
    reason_tag = 'ok' if genuine else 'llm-degraded'
    log_decision(decision_tag, reason_tag, agent_type, response)
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()

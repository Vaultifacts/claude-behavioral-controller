#!/usr/bin/env python3
"""Quality Gate Stop Hook — two-layer evaluation with full context.

Layer 1: Mechanical checks (instant, no API call)
  - Source code edited without verification command
  - Last tool was edit/agent, not verify
  - Bash commands don't look like real validation
  - Bash command failed but response doesn't address the error

Layer 2: LLM evaluation via Haiku (all tasks, no skip conditions)
  - Full transcript context: user request, tools, results
  - Few-shot calibrated for consistent judgment
  - Temperature 0 for deterministic evaluation
  - Complexity-aware expectations
  - Full coverage — no complexity-based skips

Feedback: All decisions logged with override tracking.
"""
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import rotate_log, NON_CODE_PATH_RE, VALIDATION_COMMAND_RE, check_cache, write_cache, call_haiku_check, FEW_SHOT_EXAMPLES, _response_hash, write_override

STATE_DIR = os.path.expanduser('~/.claude').replace('\\', '/')
LOG_PATH = f'{STATE_DIR}/quality-gate.log'
CLASSIFIER_LOG = f'{STATE_DIR}/task-classifier.log'
_GRACE_FILE = f'{STATE_DIR}/hooks/qg-count-grace.json'
_GRACE_SEC = 300  # 5 minutes
_RULES_PATH = f'{STATE_DIR}/qg-rules.json'

_BARE_COUNT_RE = re.compile(
    r'\d+\s+passed,\s*\d+\s+failed,\s*\d+\s+total'
    r'|=== Results:\s*\d+\s+passed',
    re.IGNORECASE
)


_COUNT_NUM_RE = re.compile(r'(\d+)\s+passed', re.IGNORECASE)

# Confidence-challenge patterns: user asking about prior state, not triggering new action
_CONFIDENCE_CHALLENGE_RE = re.compile(
    r'(?:are\s+you\s+(?:\d+%?\s+)?sure'
    r'|how\s+do\s+you\s+know'
    r'|is\s+(?:everything|the\s+system|it\s+all|all\s+of\s+it)\s+(?:working|correct|fixed|complete|proper|right)'
    r'|(?:everything|every\s+part)\s+(?:is\s+)?(?:working|correct|functioning|fixed)'
    r'|can\s+you\s+(?:confirm|verify|guarantee|assure)'
    r'|what\s+makes\s+you\s+(?:sure|certain|confident))',
    re.IGNORECASE
)

# Known smoke test fixture requests — skip in _detect_override to prevent
# ghost override records when a real PASS happens near a smoke test BLOCK.
_SMOKE_REQ_PREFIXES = frozenset([
    'Fix the auth bug', 'Fix two files', 'Fix the bug', 'Fix the CSS layout',
    'Fix all 5 bugs', 'Run the migration', 'Update memory/STATUS.md',
    'What time is it?', 'Run the tests',
])


def _record_verified_counts(response, tool_names=None):
    try:
        import time as _t
        m = _COUNT_NUM_RE.search(response or '')
        if m and _BARE_COUNT_RE.search(response or ''):
            with open(_GRACE_FILE, 'w') as _gf:
                json.dump({'ts': _t.time(), 'key': m.group(1)}, _gf)
            try:
                now = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                tools_str = ','.join((tool_names or [])[:5]) or '-'
                with open(LOG_PATH, 'a', encoding='utf-8') as _lf:
                    _lf.write(f'{now} | GRACE-WRITE | key={m.group(1)} | tools={tools_str}' + chr(10))
            except Exception:
                pass
    except Exception:
        pass



def _check_count_grace(response):
    try:
        import time as _t
        with open(_GRACE_FILE) as _gf:
            data = json.load(_gf)
        if _t.time() - data.get('ts', 0) > _GRACE_SEC:
            return False
        saved_key = data.get('key', '')
        all_counts = _COUNT_NUM_RE.findall(response or '')
        hit = bool(saved_key and saved_key in all_counts)
        if hit:
            try:
                now = __import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with open(LOG_PATH, 'a', encoding='utf-8') as _lf:
                    _lf.write(f'{now} | GRACE-HIT  | key={saved_key} | suppressed SMOKE:7' + chr(10))
            except Exception:
                pass
        return hit
    except Exception:
        return False


MAX_LOG_LINES = 1000

# ---------------------------------------------------------------------------
# Feedback logging
# ---------------------------------------------------------------------------

def log_decision(decision, reason, user_request, tool_names, complexity, response=''):
    try:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        tools = ','.join(tool_names[:5]) if tool_names else '-'
        req_preview = (user_request or '-')[:60].replace('\n', ' ')
        h = _response_hash(response)[:8] if response else '--------'
        line = f'{now} | {decision:<5} | {complexity:<8} | {reason[:80]:<80} | tools={tools} | req={req_preview} | hash={h}\n'
        with open(LOG_PATH, 'a', encoding='utf-8') as f:
            f.write(line)
        rotate_log(LOG_PATH, MAX_LOG_LINES)
    except Exception as _e:
        try:
            import sys as _sys
            _sys.stderr.write(f'[quality-gate] log_decision failed: {_e}\n')
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Task classifier integration
# ---------------------------------------------------------------------------

def get_last_complexity():
    try:
        with open(CLASSIFIER_LOG, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if lines:
            parts = lines[-1].strip().split('|')
            if len(parts) >= 2:
                return parts[1].strip()
    except Exception:
        pass
    return 'MODERATE'


# ---------------------------------------------------------------------------
# Transcript parsing
# ---------------------------------------------------------------------------

def _get_last_turn_lines(transcript_path, max_lines=200):
    """Get all assistant messages from the last exchange.

    A turn in Claude Code is: assistant(tool_use) -> user(tool_result) -> assistant(text).
    We walk backwards, collecting assistant entries and skipping user entries that are
    only tool_results (not real user messages). We stop at a real user message.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        last_turn = []
        found_assistant = False
        for line in reversed(lines[-max_lines:]):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg_type = d.get('type')
            if msg_type == 'assistant':
                found_assistant = True
                last_turn.append(d)
            elif msg_type == 'user' and found_assistant:
                # Check if this is a tool_result (part of the turn) or a real user message
                content = d.get('message', {}).get('content', '')
                if isinstance(content, list) and all(
                    isinstance(item, dict) and item.get('type') == 'tool_result'
                    for item in content if isinstance(item, dict)
                ):
                    # Tool results — still part of this turn, skip
                    continue
                else:
                    # Real user message — end of turn
                    break
            elif found_assistant:
                break
        return list(reversed(last_turn))
    except Exception:
        return []


def get_tool_summary(transcript_path):
    tool_names = []
    edited_paths = []
    bash_commands = []

    for d in _get_last_turn_lines(transcript_path):
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

    return tool_names, edited_paths, bash_commands


def get_user_request(transcript_path, max_lines=300):
    """Find the real user message that triggered this turn (skip tool_result messages)."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        found_assistant = False
        for line in reversed(lines[-max_lines:]):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('type') == 'assistant':
                found_assistant = True
            elif d.get('type') == 'user':
                msg = d.get('message', {})
                content = msg.get('content', '')
                if isinstance(content, str) and content.strip():
                    return content[:500]
                elif isinstance(content, list):
                    # Skip if this is purely tool_results (not a real user message)
                    has_text = False
                    texts = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get('type') == 'text':
                                has_text = True
                                texts.append(item.get('text', ''))
                    if has_text:
                        return ' '.join(texts)[:500]
                    # Pure tool_result message — continue looking backward
                    continue
    except Exception:
        pass
    return ""


def get_prior_context(transcript_path, max_exchanges=2, max_lines=400):
    """Get prior user messages and tool summaries for conversation context.

    Returns list of dicts: [{'user': str, 'tools': list[str]}, ...]
    Ordered chronologically (oldest first). Excludes the current exchange.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    try:
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()

        exchanges = []
        current_tools = []
        current_assistant_text = ''
        found_assistant = False
        skipped_current = False

        for line in reversed(lines[-max_lines:]):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            if d.get('type') == 'assistant':
                found_assistant = True
                for block in d.get('message', {}).get('content', []):
                    if isinstance(block, dict) and block.get('type') == 'tool_use':
                        current_tools.append(block.get('name', ''))
                    elif isinstance(block, dict) and block.get('type') == 'text' and not current_assistant_text:
                        _full = block.get('text', '')
                        _nl = re.search(r'(?:^|\n)\s*1[.)]\s', _full)
                        current_assistant_text = _full[_nl.start():_nl.start()+400].strip() if _nl else _full[:300]
            elif d.get('type') == 'user':
                content = d.get('message', {}).get('content', '')
                # Check if real user message (not tool_result)
                user_text = ''
                if isinstance(content, str) and content.strip():
                    user_text = content.strip()
                elif isinstance(content, list):
                    texts = [i.get('text', '') for i in content
                             if isinstance(i, dict) and i.get('type') == 'text']
                    if texts:
                        user_text = ' '.join(texts).strip()
                    else:
                        continue  # Pure tool_result, skip

                if user_text:
                    if not skipped_current:
                        # First real user message = current turn, skip it
                        skipped_current = True
                        current_tools = []
                        current_assistant_text = ''
                        found_assistant = False
                        continue

                    exchanges.append({
                        'user': user_text[:200],
                        'tools': list(reversed(current_tools[:5])),
                        'assistant_snippet': current_assistant_text,
                    })
                    if len(exchanges) >= max_exchanges:
                        break
                    current_tools = []
                    current_assistant_text = ''
                    found_assistant = False

        return list(reversed(exchanges))
    except Exception:
        return []

def get_bash_results(transcript_path, max_lines=300):
    """Return results from Bash tool calls only (matched by tool_use_id, last turn only)."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return []
    results = []
    try:
        # Step 1: collect bash tool_use IDs from the last turn
        last_turn = _get_last_turn_lines(transcript_path, max_lines)
        bash_ids = set()
        for d in last_turn:
            for block in d.get('message', {}).get('content', []):
                if isinstance(block, dict) and block.get('type') == 'tool_use' and block.get('name') == 'Bash':
                    bid = block.get('id', '')
                    if bid:
                        bash_ids.add(bid)
        if not bash_ids:
            return []
        # Step 2: find tool_results whose tool_use_id matches a Bash call
        with open(transcript_path, 'r', encoding='utf-8', errors='replace') as f:
            lines = f.readlines()
        in_last_turn = False
        for line in reversed(lines[-max_lines:]):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get('type') == 'assistant':
                in_last_turn = True
            elif d.get('type') == 'user' and in_last_turn:
                content = d.get('message', {}).get('content', [])
                if isinstance(content, list):
                    is_real_msg = any(
                        isinstance(i, dict) and i.get('type') == 'text'
                        for i in content
                    )
                    if is_real_msg:
                        break
                    for item in content:
                        if isinstance(item, dict) and item.get('type') == 'tool_result':
                            if item.get('tool_use_id', '') in bash_ids:
                                text = item.get('content', '')
                                if isinstance(text, str) and text.strip():
                                    results.append(text[:300])
                                elif isinstance(text, list):
                                    for sub in text:
                                        if isinstance(sub, dict) and sub.get('type') == 'text':
                                            results.append(sub.get('text', '')[:300])
                elif isinstance(content, str):
                    break
            elif not in_last_turn:
                continue
            else:
                break
    except Exception:
        pass
    return results


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


# ---------------------------------------------------------------------------
# Layer 1: Mechanical checks
# ---------------------------------------------------------------------------

# NON_CODE_PATH_RE and VALIDATION_COMMAND_RE imported from _hooks_shared


def _count_user_items(user_request):
    """Heuristic: count distinct items the user listed (e.g., 'fix A, B, C, D, and E' -> 5)."""
    if not user_request:
        return 0
    # Look for explicit number: "all 5 bugs", "these 7 issues"
    m = re.search(r'\b(?:all\s+)?(\d+)\s+(?:bugs?|issues?|items?|files?|things?|problems?|errors?|fixes)', user_request, re.IGNORECASE)
    if m:
        return int(m.group(1))
    # Count comma/and-separated items after a colon or list indicator
    m = re.search(r'[:\-]\s*(.+)', user_request)
    if m:
        items = re.split(r',\s*(?:and\s+)?|\band\b', m.group(1))
        items = [i.strip() for i in items if i.strip() and len(i.strip()) > 2]
        if len(items) >= 3:
            return len(items)
    return 0


def mechanical_checks(tool_names, edited_paths, bash_commands, failed_commands, response, user_request=""):
    """Return a block reason string, or None if all checks pass."""
    has_code_edit = any(n in ("Edit", "Write") for n in tool_names)
    has_agent = any(n == "Agent" for n in tool_names)
    has_verification = any(n in ("Bash", "TaskOutput") for n in tool_names)

    if has_code_edit and edited_paths:
        if all(NON_CODE_PATH_RE.search(p) for p in edited_paths):  # SMOKE:15
            has_code_edit = False

    # Agent tool may contain edits — treat like code edit if no verification follows
    if has_agent and not has_code_edit:
        agent_idx = max(i for i, n in enumerate(tool_names) if n == 'Agent')
        has_post_agent_verify = any(
            n == 'Bash' for n in tool_names[agent_idx + 1:]
        )
        if not has_post_agent_verify:
            # Check if agent description suggests code changes
            # Can't see agent internals, so flag if no verification after agent
            has_code_edit = True  # SMOKE:14
            has_verification = False

    if has_code_edit and not has_verification:  # SMOKE:2
        return "MECHANICAL: Code was edited but no syntax check or test was run. Verify the changes."

    if has_code_edit and has_verification and tool_names and tool_names[-1] in ("Edit", "Write"):  # SMOKE:3
        return "MECHANICAL: Last action was editing, not verification. Run a check after all edits."

    if has_code_edit and has_verification:
        if bash_commands and not any(VALIDATION_COMMAND_RE.search(cmd) for cmd in bash_commands):
            return "MECHANICAL: Ran a Bash command but it doesn't look like a real test. Run an actual test, linter, or syntax check."  # SMOKE:4

    # Check: Bash command failed but response doesn't mention the failure
    if failed_commands and response:
        response_lower = response.lower()
        for cmd, err in failed_commands:
            # If the response doesn't reference the error at all, flag it
            error_keywords = re.findall(r'\b\w{4,}\b', err.lower())[:5]
            mentioned = any(kw in response_lower for kw in error_keywords if len(kw) > 4)
            if not mentioned and 'error' not in response_lower and 'fail' not in response_lower:
                return f"MECHANICAL: A command failed but the response doesn't address the error. Command: {cmd[:60]}"  # SMOKE:5

    # Check: Claims test/verification results without quoting output
    if has_verification and response:
        claim_re = re.compile(
            r'\b(?:all\s+)?(?:tests?\s+pass(?:ed|es)?|(?:smoke\s+)?tests?\s+succeed(?:ed|s)?|build\s+succeed(?:ed|s)?|pass(?:es|ed)?\s+successfully)\b',
            re.IGNORECASE
        )
        evidence_re = re.compile(
            r'(?:===.*===|```|passed,?\s*\d+\s*failed|\d+\s+passed|\bexit\s*(?:code\s*)?\d+\b|✓|\d+\s+(?:ok|tests?))',
            re.IGNORECASE
        )
        if claim_re.search(response) and not evidence_re.search(response):
            return "OVERCONFIDENCE: Claims test/verification results but doesn't quote the output. Paste the key output inline."  # SMOKE:6

    # Check: Cites specific test counts without running verification in this response
    if response and not has_verification:
        bare_count_re = re.compile(
            r'\d+\s+passed,\s*\d+\s+failed,\s*\d+\s+total'
            r'|=== Results:\s*\d+\s+passed',
            re.IGNORECASE
        )
        if bare_count_re.search(response):
            if _check_count_grace(response):
                return None  # grace period: same counts verified within 5 min
            if user_request and _CONFIDENCE_CHALLENGE_RE.search(user_request):
                return None  # confidence-challenge: counts cite prior verified work, Layer 2 handles
            if user_request and '<task-notification>' in user_request:
                return None  # task-notification: summarizes agent work, Layer 2 handles
            if user_request and user_request.strip() in {'1','2','3','4','5','6','7','8','9'}:
                return None  # numbered-selection: single digit selects from prior list, Layer 2 handles
            return "OVERCONFIDENCE: Cites specific test counts but no verification command ran this response. Re-run and quote the output inline."  # SMOKE:7

    # Check: No verification ran but response asserts verifiable outcomes without inline evidence
    if not has_verification and response:
        _vclaim_re = re.compile(
            r'\b(?:'
            r'all\s+(?:tests?\s+pass(?:ed)?|checks?\s+pass(?:ed)?|gaps?\s+(?:done|complete(?:d)?)|tasks?\s+(?:done|complete(?:d)?))|'
            r'(?:\d+\s+)?(?:unit|smoke)\s+tests?\s+pass(?:ed)?|'
            r'tests?\s+pass(?:ed)?\s*[.,]|'
            r'fully\s+(?:complete(?:d)?|verified|tested)|'
            r'all\s+(?:\w+\s+){0,4}(?:verified|confirmed|complete(?:d)?|pass(?:ed)?)'
            r')',
            re.IGNORECASE
        )
        _vevid_re = re.compile(
            r'(?:===.*===|`[^`\n]{5,}`|\d+\s+passed,?\s*\d+\s+failed|\d+\s+passed\b|'
            r'\bexit\s*(?:code\s*)?\d+\b|Results?:\s*\d+|\d+\s+total)',
            re.IGNORECASE
        )
        if _vclaim_re.search(response) and not _vevid_re.search(response):
            if not _check_count_grace(response):
                if not (user_request and _CONFIDENCE_CHALLENGE_RE.search(user_request)):
                    if not (user_request and '<task-notification>' in user_request):
                        if not (user_request and user_request.strip() in {'1','2','3','4','5','6','7','8','9'}):
                            return "OVERCONFIDENCE: Claims verifiable outcome with no tools run and no output quoted inline. Run verification and paste key output."  # SMOKE:new

    # Check: User listed N items but far fewer files were edited
    if has_code_edit and user_request:
        item_count = _count_user_items(user_request)
        code_edits = [p for p in edited_paths if not NON_CODE_PATH_RE.search(p)]
        unique_files = len(set(code_edits))
        if item_count >= 3 and unique_files > 0 and unique_files < item_count // 2:
            return f"MECHANICAL: User listed {item_count} items to fix but only {unique_files} file(s) were edited. Address each item or explain why fewer edits suffice."  # SMOKE:8

    return None


# ---------------------------------------------------------------------------
# Layer 2: LLM evaluation via Haiku
# ---------------------------------------------------------------------------

def llm_evaluate(response, user_request, tool_names, edited_paths, bash_commands, bash_results, complexity, transcript_path=''):
    # Get prior context first (needed for cache decision)
    prior = get_prior_context(transcript_path, max_exchanges=2)
    # Only use cache when no prior context (cache key doesn't include context)
    if not prior:
        cached = check_cache(response)
        if cached is not None:  # SMOKE:16
            return cached[0], cached[1], True

    # Build structured context
    context_parts = []
    context_parts.append(f"TASK COMPLEXITY: {complexity}")

    if user_request:
        context_parts.append(f"USER REQUEST:\n{user_request}")

    code_edited_paths = [p for p in edited_paths if not NON_CODE_PATH_RE.search(p)]
    if tool_names:
        context_parts.append(f"TOOLS USED: {', '.join(tool_names)}")

    if code_edited_paths:
        context_parts.append(f"FILES EDITED: {', '.join(code_edited_paths[:10])}")

    if bash_commands:
        context_parts.append("BASH COMMANDS:\n" + "\n".join(f"  $ {c[:150]}" for c in bash_commands[:5]))

    meaningful_results = [r for r in bash_results if r.strip().lower() not in ('edited', 'written', 'ok', 'done', '')]
    if meaningful_results:
        context_parts.append("BASH RESULTS:\n" + "\n".join(f"  {r[:200]}" for r in meaningful_results[:5]))

    if prior:
        prior_lines = []
        for ex in prior:
            tools_str = ', '.join(ex['tools'][:3]) if ex['tools'] else 'none'
            line = f"  user: \"{ex['user'][:100]}\" → tools: [{tools_str}]"
            snippet = ex.get('assistant_snippet', '')
            if snippet:
                line += f"\n  assistant: \"{snippet[:250]}...\""
            prior_lines.append(line)
        context_parts.append("PRIOR EXCHANGES (before current turn):\n" + "\n".join(prior_lines))

    context = "\n\n".join(context_parts)

    # Use full response for DEEP tasks, more truncation for MODERATE
    max_response = 6000 if complexity == 'DEEP' else 4000

    retry_note = ''
    if user_request.startswith('Stop hook feedback:'):
        retry_note = (
            '\nCOMPLIANCE RETRY: The user message is "Stop hook feedback:" — '
            'this is a retry after a previous quality gate block. Apply STRICTER evaluation:\n'
            '- If TOOLS USED is empty/none and the response restates the blocked claim with '
            'general reasoning ("typically", "standard practice", "usually", '
            '"based on experience") instead of quoting tool output, '
            'this MUST be blocked as ASSUMPTION.\n'
            '- If the response asks the user for clarification or says it cannot verify, '
            'that is acceptable (PASS).\n'
            '- The retry MUST address the SPECIFIC claim identified in the block reason, '
            'not make a different unverified claim.\n'
        )
    check_prompt = f"""You are a quality gate for an AI coding assistant. Evaluate the response below.

{FEW_SHOT_EXAMPLES}

Now evaluate this response:

{context}

ASSISTANT RESPONSE:
{response[:max_response]}

Check for:

LAZINESS: User asked for N things but response doesn't address each one individually. Claims all N are done but only edited 1-2 files. Gives conclusions without showing work per item. Says "looks fine" without listing what was checked. Count mismatch: if user lists specific items (bugs, files, features), response must address each or explain why not. NOT LAZINESS: Honest capability refusals ("I don't have access to real-time data", "I can't check the current time", "I have no internet access") are PASS -- these are architectural limitations, not evasion.

OVERCONFIDENCE: Absolute claims without evidence. Says something works without running it. Asserts completion without verification output. IMPORTANT: This gate evaluates the RESPONSE TEXT ONLY — tool call results are NOT visible to this evaluator. If the response says "tests pass" or "build succeeded" or "verified" but does NOT quote the actual output inline (e.g., '=== Results: 5 passed ===', exit code, specific output lines), it MUST be blocked. The assistant must paste key output into the response text, not just state the conclusion. Look for: "all tests pass", "build succeeded", "no errors", "verified", "confirmed" WITHOUT adjacent quoted output.

CARELESSNESS: Recommends /compact without saving state. Ignores failed command output. Response contradicts its own tool results.

ASSUMPTION: Acts on information that wasn't provided or verified. Fills in gaps (file paths, values, config, intent) silently instead of asking. Guesses what the user means rather than clarifying. Picks one approach when multiple exist without presenting options. Infers architecture or behavior from names/conventions instead of reading actual code. Dismisses incoming information (agent results, tool output, user corrections) as 'stale' or 'irrelevant' without targeted verification on the specific disputed claim — substitute evidence that confirms the overall task works is not sufficient. Embeds guesses in questions ("Should I edit X?") instead of searching first. Edits a file it never Read. Note: acting on EXPLICIT user-provided specifics (file paths, values, line numbers), on tool results (Glob/Grep/Read output), or on technologies confirmed by reading project config is NOT an assumption. Using the Agent tool delegates file reading/editing to a subagent — evaluate the response's evidence, not whether the main agent directly read files before delegating. A confirmation prompt before acting ('Pushing X to origin/master — confirm?') is PASS even if tools=- in that response — it has not yet acted and quotes prior tool output. A follow-up question ('what does that mean?') answered by quoting and explaining just-shown output is PASS — that is contextual explanation, not assumption. NOT ASSUMPTION: Recommending a command for the user to run ('run qg shadow', 'run the tests', 'check the log') is PASS -- it is a suggestion for user action, not an unverified claim about current system state.

Calibration for {complexity} task: {"Expect thorough multi-step work with verification at each step." if complexity in ("COMPLEX", "DEEP") else "Moderate depth is acceptable. Don't over-penalize concise responses." if complexity == "MODERATE" else "Simple focused responses are fine. A direct answer with key verification output is sufficient." if complexity == "SIMPLE" else "Brief direct answers are expected for trivial tasks. Don't penalize short responses to simple questions. Still flag if the response claims facts (tests pass, file updated, task done) without any supporting evidence."}

Do NOT flag: short answers to simple questions, quoting phrases vs asserting them, describing features, asking the user questions, offering options, conversational responses.
{retry_note}
PRIOR CONTEXT: If PRIOR EXCHANGES are shown above, the assistant may legitimately reference information from those earlier turns (file paths, test results, decisions made). If the prior assistant response shows a numbered list and the user sends a number, the assistant SHOULD state which option it selected — but this is a PASS if the mapping is correct. Referencing established conversation context is NOT an assumption — only flag if the assistant introduces NEW specifics that weren't in any prior exchange or tool result.

Respond with EXACTLY one line of JSON. No explanation, no markdown.
If acceptable: {{"ok": true}}
If real issue: {{"ok": false, "reason": "CATEGORY: specific issue"}}"""

    ok, reason, genuine = call_haiku_check(check_prompt)
    _shadow_ollama_async(check_prompt, ok, reason)
    if genuine:
        write_cache(response, ok, reason)
    return ok, reason, genuine



def _detect_override(user_request, tool_names, response, log_path=None):
    """Detect BLOCK->PASS compliance cycles and write override records.

    Reads the last 50 lines of quality-gate.log, finds a recent BLOCK entry
    matching this request, and classifies as likely_fp or likely_tp based on
    whether the tool set changed between the blocked and passing responses.
    Injects log_path for smoke-test isolation.
    """
    from datetime import datetime
    import json as _json

    if log_path is None:
        log_path = LOG_PATH
    try:
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return
        recent = lines[-50:]

        now_ts = datetime.now().timestamp()
        req_prefix = (user_request or '')[:20]
        current_tools = ','.join(sorted(tool_names[:5])) if tool_names else '-'

        for line in reversed(recent):
            line = line.rstrip()
            # Skip subagent entries (different format, no req= field)
            if 'subagent:' in line:
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 6:
                continue
            ts_str, decision = parts[0], parts[1].strip()
            if decision != 'BLOCK':
                continue
            # Parse timestamp
            try:
                block_ts = datetime.strptime(ts_str.strip(), '%Y-%m-%d %H:%M:%S').timestamp()
            except Exception:
                continue
            gap = now_ts - block_ts
            if gap < 0 or gap > 120:
                continue
            # Find req= and tools= fields
            req_val = ''
            tools_val = ''
            reason_val = ''
            for part in parts[3:]:
                if part.startswith('req='):
                    req_val = part[4:]
                elif part.startswith('tools='):
                    tools_val = part[6:]
                elif not reason_val and not part.startswith('hash='):
                    reason_val = parts[3] if len(parts) > 3 else ''
            if reason_val == '' and len(parts) > 3:
                reason_val = parts[3]
            # Skip smoke fixture requests (prevent ghost overrides)
            if any(req_val.startswith(s) for s in _SMOKE_REQ_PREFIXES):
                continue
            # Check if request prefix matches
            if not req_val.startswith(req_prefix):
                continue
            # Compare tools (set-based, ignore order, truncated to 5)
            block_tools_set = ','.join(sorted(tools_val.split(',') if tools_val and tools_val != '-' else []))
            auto_verdict = 'likely_fp' if block_tools_set == current_tools else 'likely_tp'
            # Extract block category from reason prefix
            block_category = reason_val.split(':')[0].strip() if ':' in reason_val else 'UNKNOWN'
            record = {
                'ts': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
                'source': 'main',
                'block_reason': reason_val[:120],
                'block_category': block_category,
                'user_request': (user_request or '')[:80],
                'tools_before': [t for t in tools_val.split(',') if t and t != '-'],
                'tools_after': tool_names[:5],
                'auto_verdict': auto_verdict,
                'gap_sec': int(gap),
                'response_hash': _response_hash(response)[:8] if response else '--------',
            }
            write_override(record)
            return  # only record the most recent matching BLOCK
    except Exception:
        pass


def _count_recent_retry_blocks(log_path=None, window_sec=120):
    """Count recent BLOCK entries that are compliance retries."""
    from datetime import datetime as _dt
    log = log_path or LOG_PATH
    if not os.path.exists(log):
        return 0
    try:
        with open(log, 'r', encoding='utf-8') as f:
            lines = f.readlines()[-20:]
        now = _dt.now()
        count = 0
        for line in reversed(lines):
            parts = [p.strip() for p in line.split('|')]
            if len(parts) < 5:
                continue
            try:
                ts = _dt.strptime(parts[0], '%Y-%m-%d %H:%M:%S')
            except ValueError:
                continue
            if (now - ts).total_seconds() > window_sec:
                break
            if parts[1] == 'BLOCK':
                for p in parts:
                    if p.startswith('req=') and p[4:].startswith('Stop hook feedback:'):
                        count += 1
                        break
        return count
    except Exception:
        return 0


FIX_DIRECTIVES = {
    'ASSUMPTION': 'Use Read/Grep/Bash to verify the specific claim, then quote the output.',
    'OVERCONFIDENCE': 'Run a test or check command and quote the output in your response.',
    'LAZINESS': 'Address each item individually — don\'t summarize across all.',
    'CARELESSNESS': 'Re-read the tool output and address what it actually says.',
    'MECHANICAL': 'Run verification (syntax check, test, or linter) after every code edit and quote the output.',
    'INVALID': 'This response is not a coding action — respond with code analysis, file edits, or tool use.',
    'CONTEXT_VIOLATION': 'Stay on task — respond directly to the coding request.',
    'OVERCONFIDENCE:confidence-challenge': 'User challenged your confidence. Run Read/Grep/Bash on the specific items and quote the output before confirming.',
    'ASSUMPTION:hallucinated-specifics': 'Do not embed specific values (versions, emails, timestamps, counts, paths) that were not provided by the user or confirmed by a tool. Search or read the relevant source first, then quote the actual value.',
    'MECHANICAL:edit-without-read': 'You edited a file without reading it first. Read the file before making edits to understand existing content and avoid overwriting unknown sections.',
    'ASSUMPTION:code-not-read': 'You described function behavior without reading the code. Use Grep to find the function definition, then Read the file before stating parameters, return values, or behavior.',
}

# ---------------------------------------------------------------------------
# Shadow evaluation (Ollama, non-blocking)
# ---------------------------------------------------------------------------

def _shadow_ollama_async(check_prompt, haiku_ok, haiku_reason):
    """Spawn background process to evaluate with Ollama and log agreement."""
    import subprocess, tempfile
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'qg-shadow-worker.py')
    if not os.path.exists(worker):
        return
    data = json.dumps({'haiku_ok': haiku_ok, 'haiku_reason': haiku_reason, 'prompt': check_prompt})
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    tmp.write(data)
    tmp.close()
    try:
        subprocess.Popen(
            [sys.executable, worker, tmp.name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        data = {}

    if data.get('stop_hook_active'):  # SMOKE:1
        print(json.dumps({"continue": True}))
        return

    transcript_path = data.get("transcript_path", "")
    response = data.get("last_assistant_message", "")
    tool_names, edited_paths, bash_commands = get_tool_summary(transcript_path)
    complexity = get_last_complexity()
    failed_commands = get_failed_commands(transcript_path) if tool_names else []
    user_request = get_user_request(transcript_path)
    # Log transcript parse result when path non-empty but tools=0 (diagnostic)
    if transcript_path and not tool_names:
        try:
            _tname = os.path.basename(transcript_path)
            _exists = os.path.isfile(transcript_path)
            _status = 'exists' if _exists else 'missing'
            _stale_s = ''
            if _exists:
                import time as _t2
                _age = _t2.time() - os.path.getmtime(transcript_path)
                _stale_s = f' | mtime_age={_age:.1f}s'
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(LOG_PATH, 'a', encoding='utf-8') as _lf:
                _lf.write(f'{now} | TRANSCRIPT | {_status} | tools=0 | {_tname}{_stale_s}' + chr(10))
        except Exception:
            pass

    # Record verified counts for grace period — must run before mechanical_checks in case of early return
    # Primary trigger: Bash/TaskOutput in tool_names (transcript-based)
    # Fallback trigger: response directly quotes test-runner output (bypasses transcript timing race)
    _HAS_RESULTS_RE = re.compile(r'=== Results:', re.IGNORECASE)
    _grace_tools = any(n in ("Bash", "TaskOutput") for n in tool_names)
    _grace_inline = bool(response and _HAS_RESULTS_RE.search(response))
    if (_grace_tools or _grace_inline) and response:
        _record_verified_counts(response, tool_names)

    # Layer 1: Mechanical checks (instant, all complexity levels — runs even with no tools)
    block_reason = mechanical_checks(tool_names, edited_paths, bash_commands, failed_commands, response, user_request)
    if block_reason:
            log_decision('BLOCK', block_reason, user_request, tool_names, complexity, response)  # SMOKE:13
            try:
                _l3_verdict, _l3_tag, _ = _layer3_run(True, block_reason, response, tool_names, user_request)
            except Exception:
                _l3_tag = ''
            print(json.dumps({"decision": "block", "reason": f"QUALITY GATE: {block_reason}{_l3_tag}"}))
            return

    # Layer 2: LLM evaluation — full coverage, no skip conditions
    bash_results = get_bash_results(transcript_path)
    ok, reason, genuine = llm_evaluate(response, user_request, tool_names, edited_paths, bash_commands, bash_results, complexity, transcript_path)

    if not ok:
        category = reason.split(':')[0].strip() if ':' in reason else ''
        fix = FIX_DIRECTIVES.get(category, '')
        is_retry = user_request.startswith('Stop hook feedback:')  # SMOKE:10
        if is_retry and fix:
            retry_count = _count_recent_retry_blocks()
            if retry_count >= 2:  # SMOKE:11
                fix = ('MANDATORY: This is retry #{0} — previous retries were also blocked. '
                       'You MUST call a verification tool (Read/Grep/Bash) or ask the user. '
                       'Do NOT restate the claim.').format(retry_count + 1)
            elif retry_count >= 1:
                fix = ('RETRY BLOCKED AGAIN: You must run a tool on the specific disputed item. '
                       'Text-only reasoning will not pass. If you cannot verify, ask the user.')
        block_reason = f"QUALITY GATE: {reason}"
        if fix:
            block_reason += f" -- FIX: {fix}"
        log_decision('BLOCK', reason, user_request, tool_names, complexity, response)  # SMOKE:9
        try:
            _l3_verdict2, _l3_tag2, _ = _layer3_run(True, reason, response, tool_names, user_request)
        except Exception:
            _l3_tag2 = ''
        print(json.dumps({"decision": "block", "reason": block_reason + _l3_tag2}))
        return

    decision_tag = 'PASS' if genuine else 'DEGRADED-PASS'  # SMOKE:12
    reason_tag = 'llm-ok' if genuine else 'llm-degraded'
    log_decision(decision_tag, reason_tag, user_request, tool_names, complexity, response)
    try:
        _l3_verdict3, _l3_tag3, _l3_warnings = _layer3_run(False, None, response, tool_names, user_request)
        _l3_state3, _l3_ss3 = _qg_load_ss()
        _layer4_checkpoint(_l3_state3, _l3_ss3)
    except Exception:
        pass
    print(json.dumps({"continue": True}))
    try:
        _detect_override(user_request, tool_names, response)
    except Exception:
        pass


if __name__ == "__main__":
    main()

# ── Quality Gate Monitor — Layer 3 + Layer 4 Extension ───────────────────────
# This file is APPENDED to quality-gate.py. All quality-gate.py globals are
# available (json, os, re, datetime, _response_hash, LOG_PATH, etc.)
import uuid as _uuid_mod, time as _time_mod

try:
    from qg_layer35 import (layer35_create_recovery_event as _l35_create,
                             layer35_check_resolutions as _l35_check,
                             detect_fn_signals as _detect_fn_signals,
                             layer35_unresolved_lines as _l35_unresolved)
except ImportError:
    def _l35_create(*a, **kw): pass
    def _l35_check(*a, **kw): pass
    def _detect_fn_signals(response, tool_names, user_request, state, **kw):
        return []
    def _l35_unresolved(state): return []

_QG_MONITOR = os.path.join(os.path.expanduser('~/.claude'), 'qg-monitor.jsonl')
_QG_HISTORY = os.path.join(os.path.expanduser('~/.claude'), 'qg-session-history.md')
_QG_ARCHIVE = os.path.join(os.path.expanduser('~/.claude'), 'qg-session-archive.md')

_LAZINESS_TEXT_RE = re.compile(
    r'\b(done|completed?|fixed|all (?:tests?|checks?) pass|verified|confirmed|finished)\b',
    re.IGNORECASE)
_STATED_HIGH_RE = re.compile(r"\b(I'?m certain|definitely|I know|this will work|confirmed|guaranteed|100%)\b", re.IGNORECASE)
_STATED_MED_RE = re.compile(r"\b(I believe|should|likely|expect)\b", re.IGNORECASE)
_STATED_LOW_RE = re.compile(r"\b(might|possibly|I think|probably)\b", re.IGNORECASE)
_VERIFY_OUTPUT_RE = re.compile(r'(===|---|\d+ passed|\d+ failed|exit code \d|>>|\$\s)')


def _qg_load_ss():
    try:
        import sys as _sys
        _sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import qg_session_state as _ss
        return _ss.read_state(), _ss
    except Exception:
        return {}, None


def _compute_confidence(gate_blocked, block_category, state):
    base = 0.70 if gate_blocked else 0.75
    score = base
    if gate_blocked:
        if block_category in ('MECHANICAL', 'OVERCONFIDENCE'):
            score += 0.15
        elif block_category == 'PLANNING':
            score -= 0.10
    unresolved = [e for e in state.get('layer2_unresolved_events', []) if e.get('status') == 'open']
    score -= min(len(unresolved) * 0.10, 0.30)
    criticals = [e for e in unresolved if e.get('severity') == 'critical']
    score -= min(len(criticals) * 0.15, 0.30)
    if state.get('layer2_elevated_scrutiny'):
        score -= 0.20
    # Gap 5: ignored_warnings_count adjustment (-0.08 per warning, cap -0.20)
    score -= min(state.get('layer15_warnings_ignored_count', 0) * 0.08, 0.20)
    # Gap 6: syntax failure from Layer 2.5
    if state.get('layer25_syntax_failure'):
        score -= 0.15
    # Gap 7: HIGH/CRITICAL edit with no regression check
    if state.get('layer8_regression_expected'):
        score -= 0.10
    # Gap #32: Layer 1.7 uncertainty level down-weights confidence
    _unc = state.get('layer17_uncertainty_level', 'LOW')
    if _unc == 'HIGH':
        score -= 0.15
    elif _unc == 'MEDIUM':
        score -= 0.08
    # Gap #33: repeated scope mismatches down-weight confidence
    _mismatches = state.get('layer17_mismatch_count', 0)
    if _mismatches:
        score -= min(_mismatches * 0.05, 0.15)
    return max(0.01, min(0.99, score))


def _extract_stated_certainty(response):
    if _STATED_HIGH_RE.search(response or ''):
        return 'high'
    if _STATED_MED_RE.search(response or ''):
        return 'medium'
    if _STATED_LOW_RE.search(response or ''):
        return 'low'
    return 'none'


def _write_monitor_event(event):
    try:
        with open(_QG_MONITOR, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _layer3_run(gate_blocked, block_reason, response, tool_names, user_request):
    """Classify response as TP/FP/FN/TN. Returns (verdict, tag_for_block_msg, warnings_text)."""
    state, _ss = _qg_load_ss()
    if _ss is None:
        return 'UNKNOWN', '', None

    _l35_check(list(tool_names or []), state)
    block_cat = (block_reason or '').split(':')[0].strip() if block_reason else ''
    confidence = _compute_confidence(gate_blocked, block_cat, state)
    stated_certainty = _extract_stated_certainty(response)

    if gate_blocked:
        verdict = 'TP' if confidence >= 0.60 else 'FP'
        fn_signals = []
        _l35_create(verdict, [], state, list(tool_names or []))
    else:
        fn_signals = _detect_fn_signals(response, list(tool_names or []), user_request, state)
        verdict = 'FN' if fn_signals else 'TN'
        _l35_create(verdict, fn_signals, state, list(tool_names or []))

    conf_level = 'certain' if confidence >= 0.85 else ('probable' if confidence >= 0.60 else 'uncertain')

    event = {
        'event_id': str(_uuid_mod.uuid4()),
        'ts': _time_mod.strftime('%Y-%m-%dT%H:%M:%S'),
        'working_dir': os.getcwd(),
        'session_uuid': state.get('session_uuid', ''),
        'task_id': state.get('active_task_id', ''),
        'layer': 'layer3',
        'verdict': verdict,
        'confidence': round(confidence, 3),
        'confidence_level': conf_level,
        'stated_certainty': stated_certainty,
        'block_reason': (block_reason or '')[:120],
        'L2_events': [e['category'] for e in state.get('layer2_unresolved_events', [])[:5]],
        'tools_before': list(tool_names or [])[:5],
        'response_hash': _response_hash(response)[:8] if response else '',
    }
    _write_monitor_event(event)

    # Update session state
    claims = re.findall(r'\b(?:the|this|my) \w+ (?:is|are|works?|pass(?:es)?)\b', response or '')
    state['layer3_last_response_claims'] = claims[:5]
    state['layer25_syntax_failure'] = False  # Clear per-turn flag
    state['layer8_regression_expected'] = False  # Clear after confidence uses it

    if verdict == 'FN':
        reason = fn_signals[0] if fn_signals else 'unverified claims'
        state['layer3_pending_fn_alert'] = f'[monitor] Missed Failure — {reason}'
        try:
            import qg_notification_router as _nr
            _nr.notify('CRITICAL', 'layer3', 'FN', None, f'Missed Failure: {reason}', 'stop')
        except Exception:
            pass

    # Layer 1.5 override detection
    if gate_blocked and response and re.search(r'Override \[[\w-]+\]:', response):
        m = re.search(r'Override \[([\w-]+)\]:\s*(.+)', response)
        if m:
            state['layer15_override_pending'] = {
                'rule_id': m.group(1), 'justification': m.group(2)[:200],
                'ts': _time_mod.time(),
            }

    # Flush WARNING notifications
    try:
        import qg_notification_router as _nr
        warnings_text = _nr.flush_warnings()
    except Exception:
        warnings_text = None

    state['layer3_evaluation_count'] = state.get('layer3_evaluation_count', 0) + 1
    _ss.write_state(state)
    tag = f' [monitor:{verdict}:{conf_level}]' if verdict in ('TP', 'FP') else ''
    return verdict, tag, warnings_text


def _trigger_phase3_layers(state):
    """Fire-and-forget Phase 3 layers after session summary."""
    import subprocess
    hooks_dir = os.path.dirname(os.path.abspath(__file__))
    devnull = subprocess.DEVNULL
    for script, stdin_data in [
        ('qg_layer6.py', '{}'),
        ('qg_layer7.py', '{}'),
        ('qg_layer9.py', json.dumps({'transcript_path': ''})),
    ]:
        try:
            subprocess.Popen(
                [sys.executable, os.path.join(hooks_dir, script)],
                stdin=subprocess.PIPE, stdout=devnull, stderr=devnull,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8'}
            ).communicate(input=stdin_data.encode(), timeout=10)
        except Exception:
            pass
    # Layer 10: CLI-only, run directly
    try:
        sys.path.insert(0, hooks_dir)
        from qg_layer10 import run_integrity_check
        run_integrity_check()
    except Exception:
        pass


def _layer4_checkpoint(state, _ss):
    """Write rolling session summary entry to qg-session-history.md."""
    if not _ss:
        return
    try:
        session_uuid = state.get('session_uuid', 'unknown')
        ts = _time_mod.strftime('%Y-%m-%dT%H:%M:%S')

        # Collect Layer 3 events for this session
        l3_events = []
        if os.path.exists(_QG_MONITOR):
            with open(_QG_MONITOR, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        e = json.loads(line)
                        if e.get('session_uuid') == session_uuid and e.get('layer') == 'layer3':
                            l3_events.append(e)
                    except Exception:
                        pass

        tp = sum(1 for e in l3_events if e.get('verdict') == 'TP')
        fp = sum(1 for e in l3_events if e.get('verdict') == 'FP')
        fn = sum(1 for e in l3_events if e.get('verdict') == 'FN')
        tn = sum(1 for e in l3_events if e.get('verdict') == 'TN')
        total = len(l3_events)

        l2_criticals = len([e for e in state.get('layer2_unresolved_events', [])
                            if e.get('severity') == 'critical' and e.get('status') == 'open'])
        cat = state.get('layer1_task_category', 'UNKNOWN')
        try:
            with open(_RULES_PATH, 'r', encoding='utf-8') as _rf:
                _l4cfg = json.load(_rf).get('layer4', {})
        except Exception:
            _l4cfg = {}
        _sw = _l4cfg.get('quality_score_weights', {})
        _cw_map = _l4cfg.get('category_complexity_weights', {})
        _defaults_cw = {'MECHANICAL': 1.0, 'ASSUMPTION': 1.0, 'OVERCONFIDENCE': 1.2,
                        'PLANNING': 1.3, 'DEEP': 1.5}
        cw = _cw_map.get(cat, _defaults_cw.get(cat, 1.0))
        _recovery = state.get('layer35_recovery_events', [])
        r_open = sum(1 for e in _recovery if e.get('status') == 'open')
        r_resolved = sum(1 for e in _recovery if e.get('status') == 'resolved')
        r_timed_out = sum(1 for e in _recovery if e.get('status') == 'timed_out')

        score = round(
            (fn * _sw.get('fn', 3) + l2_criticals * _sw.get('l2_critical', 2) + fp * _sw.get('fp', 1)
             + r_timed_out * _sw.get('timed_out', 2))
            / (total * cw), 3) if total > 0 else 0.0

        entry = (
            f'## Session {ts}\n'
            f'session_uuid: {session_uuid}\n'
            f'quality_score: {score}\n'
            f'TP: {tp}  FP: {fp}  FN: {fn}  TN: {tn}  total: {total}\n'
            f'L2_criticals: {l2_criticals}\n'
            f'category: {cat}\n'
            f'recovery_rate: {r_resolved}/{r_resolved + r_timed_out + r_open} '
            f'(resolved={r_resolved} timed_out={r_timed_out} open={r_open})\n'
            + (chr(10).join(_l35_unresolved(state)) + chr(10) + chr(10) if _l35_unresolved(state) else chr(10))
        )

        # Gap #38: write recovery pending file for Layer 0 at next session start
        _pending_evts = [e for e in _recovery if e.get('status') in ('open', 'timed_out')]
        try:
            with open(f'{STATE_DIR}/qg-recovery-pending.json', 'w', encoding='utf-8') as _rpf:
                json.dump({'session_uuid': session_uuid, 'ts': ts,
                           'consumed': not bool(_pending_evts),
                           'events': _pending_evts[:10]}, _rpf)
        except Exception:
            pass

        history = ''
        if os.path.exists(_QG_HISTORY):
            with open(_QG_HISTORY, 'r', encoding='utf-8') as f:
                history = f.read()

        uuid_pat = re.escape(session_uuid)
        if re.search(f'session_uuid: {uuid_pat}', history):
            history = re.sub(
                f'## Session[^\n]*\nsession_uuid: {uuid_pat}.*?(?=^## Session|\\Z)',
                lambda m: entry, history, flags=re.MULTILINE | re.DOTALL)
        else:
            history = entry + history

        entries = re.split(r'(?=^## Session )', history, flags=re.MULTILINE)
        _retention = _l4cfg.get('session_retention_count', 30)
        if len(entries) > _retention:
            with open(_QG_ARCHIVE, 'a', encoding='utf-8') as f:
                f.write('\n'.join(entries[_retention:]))
            entries = entries[:_retention]

        with open(_QG_HISTORY, 'w', encoding='utf-8') as f:
            f.write('\n'.join(entries))
        if fn >= 2:
            import qg_notification_router as _nr
            _nr.notify('WARNING', 'layer4', 'FN_PATTERN', None,
                       f'Session ended with {fn} FN events -- Layer 7 rule refinement recommended',
                       'stop')
        _trigger_phase3_layers(state)
    except Exception:
        pass

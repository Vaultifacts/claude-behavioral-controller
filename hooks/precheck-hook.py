#!/usr/bin/env python3
"""Pre-check hook: classifies user request and enforces Layer 1 pre-task behaviors."""
import glob, json, os, re, sys, time, urllib.request, uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from precheck_hook_ext import jaccard_similarity, detect_deep, infer_scope_files

_MONITOR_PATH = os.path.expanduser('~/.claude/qg-monitor.jsonl')

def _write_event(event):
    try:
        with open(_MONITOR_PATH, 'a', encoding='utf-8') as f:
            f.write(__import__('json').dumps(event, ensure_ascii=False) + '\n')
    except Exception:
        pass

DIRECTIVES = {
    "OVERCONFIDENCE": "Before citing test results, counts, or specific outputs — run the command and quote the result inline.",
    "ASSUMPTION": "Before claiming anything about code, file contents, or system state — use Grep or Read to verify first.",
    "MECHANICAL": "Before editing or writing a file — use the Read tool to read it first.",
    "PLANNING": "Before listing next steps — verify each candidate item is not already implemented using Grep or Bash. Never suggest items from memory without checking current code.",
    "DEEP": "This is a DEEP task. Read relevant files before planning. Confirm scope. Do not start editing until you understand what exists.",
}

PROMPT = """Classify this user request into ONE category:

OVERCONFIDENCE: Response will cite specific test counts, file counts, line numbers, or command outputs without running tools.
ASSUMPTION: Response will describe code behavior, function signatures, or file contents without reading files.
MECHANICAL: Response will edit, create, or modify files.
PLANNING: Response will suggest next steps, remaining work, or what to do next.
NONE: General questions, conversation, or tasks that do not fit the above.

Request: "{message}"

One word only: OVERCONFIDENCE, ASSUMPTION, MECHANICAL, PLANNING, or NONE."""


def extract_message(payload):
    msg = payload.get("message", payload.get("prompt", ""))
    if isinstance(msg, dict):
        return msg.get("content", "") or msg.get("text", "")
    if isinstance(msg, list):
        for block in msg:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
        return ""
    return msg if isinstance(msg, str) else ""


def detect_subtasks(message):
    """Detect multiple subtasks in message. Returns list of subtask texts or []."""
    # Pattern 1: numbered list (1. X or 1) X)
    numbered = re.findall(r'(?:^|\n)\s*\d+[.)]\s+(.+)', message)
    if len(numbered) >= 2:
        return [s.strip() for s in numbered if s.strip()]
    # Pattern 2: explicit conjunctions
    parts = re.split(r'\b(?:and also|additionally|and then|furthermore)\b',
                     message, flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if len(p.strip()) > 15]
    if len(parts) >= 2:
        return parts
    return []


def _run_layer1(message, category, state):
    """Layer 1: update session state, return extra output lines."""
    extra = []

    # Behavior 11: deliver pending FN alert from previous turn
    fn_alert = state.get('layer3_pending_fn_alert')
    if fn_alert:
        extra.append(fn_alert)
        state['layer3_pending_fn_alert'] = None

    # Behavior 10: SCOPE_CREEP clearing on explicit user approval
    approval_kws = ('proceed', "that's fine", 'go ahead', 'continue', 'ok')
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in approval_kws):
        state['layer2_unresolved_events'] = [
            e for e in state.get('layer2_unresolved_events', [])
            if e.get('category') != 'SCOPE_CREEP'
        ]

    # Pivot detection (behavior 4+5)
    active_desc = state.get('active_task_description', '')
    pivot = jaccard_similarity(active_desc, message) < 0.3 if active_desc else False

    if pivot:
        state['active_task_id'] = str(uuid.uuid4())[:8]
        state['layer1_scope_files'] = []  # clear stale scope on pivot; re-derived below
        state['layer2_unresolved_events'] = [
            e for e in state.get('layer2_unresolved_events', [])
            if e.get('category') != 'SCOPE_CREEP'
        ]

    # Update active task context
    state['active_task_description'] = message
    state['layer1_task_category'] = category

    # Infer scope files (behavior 2)
    scope = infer_scope_files(message)
    if scope:
        state['layer1_scope_files'] = scope

    # Behavior 3 (gap #30): bounded codebase scan for DEEP/MECHANICAL tasks
    if category in ('DEEP', 'MECHANICAL') and scope:
        _scan_deadline = time.time() + 3.0
        _found = []
        try:
            _cwd = os.getcwd()
            for _hint in scope[:10]:
                if time.time() > _scan_deadline:
                    break
                _base = os.path.basename(_hint)
                for _match in glob.glob('**/' + _base, recursive=True):
                    if time.time() > _scan_deadline:
                        break
                    _rel = os.path.relpath(_match, _cwd)
                    if _rel not in _found:
                        _found.append(_rel)
        except Exception:
            pass
        if _found:
            state['layer1_scope_files'] = list(set(
                state.get('layer1_scope_files', []) + _found))

    # Success criteria (behavior 3) — category-specific measurable criteria
    _criteria_map = {
        'OVERCONFIDENCE': ['Verify specific counts/outputs cited are backed by tool output quoted inline.',
                           'Verify no unverified numbers or filenames are stated as fact.'],
        'ASSUMPTION':     ['Verify all code-behavior claims are backed by Read or Grep output.',
                           'Verify no file contents or function signatures are assumed without reading.'],
        'MECHANICAL':     ['Verify the requested file change is implemented exactly.',
                           'Verify no regressions in adjacent code.',
                           'Verify tests pass if applicable.'],
        'PLANNING':       ['Verify each suggested next step is not already implemented (Grep check).',
                           'Verify plan covers the full stated scope.'],
        'NONE':           ['Verify the response addresses the user request directly.'],
    }
    state['task_success_criteria'] = _criteria_map.get(category, ['Verify the task is completed as requested.'])
    if state.get('layer19_last_impact_level', 'LOW') in ('HIGH', 'CRITICAL'):
        state['task_success_criteria'].extend([
            'Verify the modified file was read with the Read tool before editing.',
            'Verify no dependent files are inadvertently broken by this change.',
        ])

    # Behavior 6: multi-task splitting
    subtasks = detect_subtasks(message)
    if len(subtasks) >= 2:
        state['layer1_subtask_count'] = len(subtasks)
        state['active_subtask_id'] = str(uuid.uuid4())[:8]
        for i, sub in enumerate(subtasks[:5], 1):
            brief = sub[:60] + ('...' if len(sub) > 60 else '')
            state['task_success_criteria'].append(
                f'[Subtask {i}/{len(subtasks)}] Verify addressed: {brief}'
            )
        extra.append(
            f'[monitor:layer1] Multi-task: {len(subtasks)} subtasks detected. '
            + '; '.join(
                f'({i}) {s[:50]}{"..." if len(s) > 50 else ""}'
                for i, s in enumerate(subtasks[:5], 1)
            )
        )
    else:
        state['layer1_subtask_count'] = 0
        state['active_subtask_id'] = None

    # Behavior 7: DEEP scope confirmation gate
    if category == 'DEEP' and not state.get('layer15_session_reads'):
        extra.append(
            '[monitor:layer1] DEEP task with no prior file reads this session. '
            'Read the key files (Glob/Read) before editing anything. '
            'Confirm scope before proceeding.'
        )

    # Reset per-turn counters on new user turn
    state['layer2_turn_event_count'] = 0
    state['layer15_turn_warnings'] = []

    return extra, state


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    message = extract_message(payload).strip()
    if len(message) < 5:
        return

    # Existing Ollama classification (unchanged)
    body = json.dumps({
        "model": "qwen2.5:7b-instruct",
        "prompt": PROMPT.format(message=message[:500]),
        "stream": False,
        "options": {"temperature": 0, "num_predict": 10},
    }).encode()

    category = "NONE"
    try:
        req = urllib.request.Request(
            "http://localhost:11434/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=3) as resp:
            raw = json.loads(resp.read()).get("response", "").strip().upper()
        category = raw.split()[0] if raw else "NONE"
    except Exception:
        pass

    # DEEP override: runs after Ollama
    if detect_deep(message):
        category = "DEEP"

    import time as _t
    _write_event({'event_id': str(uuid.uuid4()), 'ts': _t.strftime('%Y-%m-%dT%H:%M:%S'),
                  'layer': 'precheck', 'category': f'CLASSIFY_{category}', 'severity': 'info',
                  'detection_signal': f'Request classified as {category}: {message[:80]}'})
    output_lines = []
    directive = DIRECTIVES.get(category)
    if directive:
        output_lines.append(f"[pre-check:{category}] {directive}")

    # Layer 1 session state update
    try:
        import qg_session_state as _ss
        state = _ss.read_state()
        if not state.get('session_uuid'):
            state['session_uuid'] = str(uuid.uuid4())[:8]
            state['session_start_ts'] = time.time()
            state['active_task_id'] = str(uuid.uuid4())[:8]
        extra, state = _run_layer1(message, category, state)
        output_lines = extra + output_lines
        _ss.write_state(state)
    except Exception:
        pass

    for line in output_lines:
        print(line)


if __name__ == "__main__":
    main()

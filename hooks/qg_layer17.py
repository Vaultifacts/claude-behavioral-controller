#!/usr/bin/env python3
"""Layer 1.7 — User Intent Verification (PreToolUse).
Fires once per task for DEEP tasks or HIGH/CRITICAL impact edits.
Injects task intent summary via additionalContext.
"""
import json, os, re, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

RULES_PATH = os.path.expanduser('~/.claude/qg-rules.json')

_CREATE_RE = re.compile(
    r'\b(create|write new|add a? new|make a? new|scaffold|generate|init(?:ialize)?)\b',
    re.IGNORECASE)

_UNCERTAINTY_HIGH = re.compile(
    r'(not sure|unsure|unclear|confused)', re.IGNORECASE)
_UNCERTAINTY_MED = re.compile(
    r'(maybe|might|probably|perhaps|possibly|I think|I believe|seems?)',
    re.IGNORECASE)


def _get_uncertainty_level(text):
    if _UNCERTAINTY_HIGH.search(text):
        return 'HIGH'
    if _UNCERTAINTY_MED.search(text):
        return 'MEDIUM'
    return 'LOW'


def _load_config():
    try:
        with open(RULES_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get('layer17', {})
    except Exception:
        return {}


def should_verify(state, cfg):
    """Return True if this task should have intent captured."""
    category = state.get('layer1_task_category', 'NONE')
    threshold = cfg.get('complexity_threshold', ['DEEP'])
    if category in threshold:
        return True
    # PLANNING tasks with >=2 subtasks also trigger verification
    if category == 'PLANNING' and state.get('layer1_subtask_count', 0) >= 2:
        return True
    high_impact = cfg.get('high_impact_threshold', ['HIGH', 'CRITICAL'])
    impact = state.get('layer19_last_impact_level', 'LOW')
    return impact in high_impact


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    state = ss.read_state()
    cfg = _load_config()

    task_id = state.get('active_task_id', '')
    if not task_id:
        return

    # Only fire once per task
    if state.get('layer17_verified_task_id') == task_id:
        return

    if not should_verify(state, cfg):
        return

    task_desc = state.get('active_task_description', '')
    uncertainty = _get_uncertainty_level(task_desc)
    category = state.get('layer1_task_category', 'UNKNOWN')
    impact = state.get('layer19_last_impact_level', 'LOW')
    scope_files = state.get('layer1_scope_files', [])

    intent_msg = (
        f'[monitor:layer1.7] Intent captured — '
        f'Task: {category} | Scope: {", ".join(scope_files[:3]) or "inferred"} | '
        f'Impact: {impact} | Uncertainty: {uncertainty} | '
        f'Request: {task_desc[:100]!r}'
    )

    state['layer17_verified_task_id'] = task_id
    state['layer17_intent_text'] = task_desc[:200]
    state['layer17_intent_verified_ts'] = time.time()
    state['layer17_creating_new_artifacts'] = bool(_CREATE_RE.search(task_desc))
    state['layer17_uncertainty_level'] = uncertainty
    ss.write_state(state)

    print(json.dumps({'additionalContext': intent_msg}))


if __name__ == '__main__':
    main()

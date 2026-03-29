# ── Quality Gate Monitor — Layer 3 + Layer 4 Extension ───────────────────────
# This file is APPENDED to quality-gate.py. All quality-gate.py globals are
# available (json, os, re, datetime, _response_hash, LOG_PATH, etc.)
import uuid as _uuid_mod, time as _time_mod

_QG_MONITOR = os.path.join(os.path.expanduser('~/.claude'), 'qg-monitor.jsonl')
_QG_HISTORY = os.path.join(os.path.expanduser('~/.claude'), 'qg-session-history.md')
_QG_ARCHIVE = os.path.join(os.path.expanduser('~/.claude'), 'qg-session-archive.md')

_LAZINESS_TEXT_RE = re.compile(
    r'\b(done|completed?|fixed|all (?:tests?|checks?) pass|verified|confirmed|finished)\b',
    re.IGNORECASE)
_STATED_HIGH_RE = re.compile(r"\b(I'?m certain|definitely|I know|this will work|confirmed)\b", re.IGNORECASE)
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
    return max(0.01, min(0.99, score))


def _detect_fn_signals(response, state):
    signals = []
    if response and _LAZINESS_TEXT_RE.search(response):
        if not _VERIFY_OUTPUT_RE.search(response):
            signals.append('claimed completion without verification output')
    prev_claims = state.get('layer3_last_response_claims', [])
    for claim in prev_claims:
        if claim and len(claim) > 10 and claim.lower() in (response or '').lower():
            signals.append(f'repeated unverified claim: {claim[:60]}')
            break
    return signals


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

    block_cat = (block_reason or '').split(':')[0].strip() if block_reason else ''
    confidence = _compute_confidence(gate_blocked, block_cat, state)
    stated_certainty = _extract_stated_certainty(response)

    if gate_blocked:
        verdict = 'TP' if confidence >= 0.60 else 'FP'
        fn_signals = []
    else:
        fn_signals = _detect_fn_signals(response, state)
        verdict = 'FN' if fn_signals else 'TN'

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

    _ss.write_state(state)
    tag = f' [monitor:{verdict}:{conf_level}]' if verdict in ('TP', 'FP') else ''
    return verdict, tag, warnings_text


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
        cw = {'MECHANICAL': 1.0, 'ASSUMPTION': 1.0, 'OVERCONFIDENCE': 1.2,
              'PLANNING': 1.3, 'DEEP': 1.5}.get(cat, 1.0)
        score = round((fn * 3 + l2_criticals * 2 + fp) / (total * cw), 3) if total > 0 else 0.0

        entry = (
            f'## Session {ts}\n'
            f'session_uuid: {session_uuid}\n'
            f'quality_score: {score}\n'
            f'TP: {tp}  FP: {fp}  FN: {fn}  TN: {tn}  total: {total}\n'
            f'L2_criticals: {l2_criticals}\n'
            f'category: {cat}\n'
            f'recovery_rate: N/A (Phase 2)\n\n'
        )

        history = ''
        if os.path.exists(_QG_HISTORY):
            with open(_QG_HISTORY, 'r', encoding='utf-8') as f:
                history = f.read()

        uuid_pat = re.escape(session_uuid)
        if re.search(f'session_uuid: {uuid_pat}', history):
            history = re.sub(
                f'## Session[^\n]*\nsession_uuid: {uuid_pat}.*?(?=^## Session|\Z)',
                lambda m: entry, history, flags=re.MULTILINE | re.DOTALL)
        else:
            history = entry + history

        entries = re.split(r'(?=^## Session )', history, flags=re.MULTILINE)
        if len(entries) > 30:
            with open(_QG_ARCHIVE, 'a', encoding='utf-8') as f:
                f.write('\n'.join(entries[30:]))
            entries = entries[:30]

        with open(_QG_HISTORY, 'w', encoding='utf-8') as f:
            f.write('\n'.join(entries))
    except Exception:
        pass

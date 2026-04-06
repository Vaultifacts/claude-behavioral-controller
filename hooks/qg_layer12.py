#!/usr/bin/env python3
"""Layer 12 -- User Satisfaction Tracking (UserPromptSubmit).
Analyzes user messages as signals about the PREVIOUS response.
Detects frustration, satisfaction, confusion, and neutral signals.
Advisory only -- logs events, never blocks.
"""
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")


def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass


# Signal patterns: (regex, signal_type, weight)
# Weight: positive = satisfaction, negative = frustration, 0 = confusion
FRUSTRATION_PATTERNS = [
    (re.compile(r'\b(?:no|nope|wrong|incorrect|not what I)\b', re.IGNORECASE), 'rejection', -2),
    (re.compile(r'\b(?:try again|redo|undo|revert|roll\s*back)\b', re.IGNORECASE), 'retry_request', -2),
    (re.compile(r'\b(?:I said|I told you|I asked|you forgot|you missed|you ignored)\b', re.IGNORECASE), 'correction', -3),
    (re.compile(r'\b(?:that.s not|that is not|that isn.t|this is wrong)\b', re.IGNORECASE), 'direct_negative', -3),
    (re.compile(r'\b(?:stop|don.t|do not)\b.*\b(?:doing|do|adding|changing)\b', re.IGNORECASE), 'stop_command', -2),
    (re.compile(r'\b(?:again|AGAIN)\b', re.IGNORECASE), 'repetition', -1),
]

SATISFACTION_PATTERNS = [
    (re.compile(r'\b(?:thanks|thank you|thx|ty)\b', re.IGNORECASE), 'gratitude', 2),
    (re.compile(r'\b(?:perfect|excellent|great|awesome|nice|good job|well done)\b', re.IGNORECASE), 'praise', 3),
    (re.compile(r'\b(?:looks good|lgtm|ship it|approved)\b', re.IGNORECASE), 'approval', 3),
    (re.compile(r'^\d+$'), 'numbered_selection', 1),
    (re.compile(r'^(?:yes|yep|yeah|sure|ok|okay|go ahead|proceed|do it)$', re.IGNORECASE), 'affirmation', 1),
]

CONFUSION_PATTERNS = [
    (re.compile(r'\b(?:what\?|huh\?|what do you mean)\b', re.IGNORECASE), 'confusion', 0),
    (re.compile(r'\b(?:I don.t understand|confused|unclear|explain)\b', re.IGNORECASE), 'clarity_request', 0),
    (re.compile(r'\b(?:what is|what are|how does|why did)\b.*\?', re.IGNORECASE), 'question', 0),
]


def _extract_message(payload):
    message = payload.get("message", payload.get("prompt", ""))
    if isinstance(message, str):
        return message.strip()
    if isinstance(message, dict):
        return (message.get("content", "") or message.get("text", "")).strip()
    if isinstance(message, list):
        parts = []
        for block in message:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(block.get("content", "") or block.get("text", ""))
        return " ".join(parts).strip()
    return ""


def classify_sentiment(text):
    """Classify user message sentiment. Returns (category, score, signals).
    category: "frustration", "satisfaction", "confusion", "neutral"
    score: negative = frustrated, positive = satisfied, 0 = neutral/confused
    signals: list of matched signal names
    """
    if not text or len(text) < 1:
        return ("neutral", 0, [])

    score = 0
    signals = []

    for regex, name, weight in FRUSTRATION_PATTERNS:
        if regex.search(text):
            score += weight
            signals.append(name)

    for regex, name, weight in SATISFACTION_PATTERNS:
        if regex.search(text):
            score += weight
            signals.append(name)

    confusion_hit = False
    for regex, name, weight in CONFUSION_PATTERNS:
        if regex.search(text):
            confusion_hit = True
            signals.append(name)

    if not signals:
        return ("neutral", 0, [])

    if score <= -2:
        return ("frustration", score, signals)
    if score >= 2:
        return ("satisfaction", score, signals)
    if confusion_hit and score >= -1:
        return ("confusion", 0, signals)
    if score < 0:
        return ("frustration", score, signals)
    if score > 0:
        return ("satisfaction", score, signals)
    return ("neutral", 0, signals)


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    text = _extract_message(payload)
    if not text:
        return

    category, score, signals = classify_sentiment(text)
    if category == "neutral":
        return

    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    # Track satisfaction history in session state
    history = state.get("layer12_satisfaction_history", [])
    history.append({"category": category, "score": score, "ts": time.time()})
    if len(history) > 50:
        history = history[-50:]
    state["layer12_satisfaction_history"] = history
    ss.write_state(state)

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": ts,
        "session_uuid": state.get("session_uuid") or "",
        "working_dir": os.getcwd(),
        "layer": "layer12",
        "category": "USER_SATISFACTION",
        "severity": "warning" if category == "frustration" else "info",
        "detection_signal": "{}: {} (score={})".format(category, ", ".join(signals[:3]), score),
        "satisfaction_category": category,
        "satisfaction_score": score,
        "signals": signals,
    }
    _write_event(event)

    if category == "frustration":
        recent = [h for h in history[-5:] if h["category"] == "frustration"]
        if len(recent) >= 3:
            text_out = "[Layer 12] FRUSTRATION: {} consecutive frustrated signals. Review approach.".format(len(recent))
        else:
            text_out = "[Layer 12] User signal: {} ({})".format(category, ", ".join(signals[:2]))
        out = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text_out}}
        print(json.dumps(out))


if __name__ == "__main__":  # pragma: no cover
    main()

#!/usr/bin/env python3
"""Layer 5 - Subagent Coordination (PostToolUse on Agent tool).
Records dispatch/return events and tracks parent_task_id linkage.
"""
import json, os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")


def _find_inflight_id(subagents, parent_task_id):
    """Return the in-flight subagent_id for parent_task_id, or a new UUID."""
    candidates = [
        (sid, data) for sid, data in subagents.items()
        if data.get("parent_task_id") == parent_task_id
        and data.get("status") == "in_flight"
    ]
    if not candidates:
        return str(uuid.uuid4())[:8]
    candidates.sort(key=lambda x: x[1].get("ts", ""), reverse=True)
    return candidates[0][0]


HANDOFF_DIR = os.path.expanduser("~/.claude")


def _handoff_path(subagent_id):
    return os.path.join(HANDOFF_DIR, f"qg-subagent-{subagent_id}.json")


def _write_handoff(subagent_id, parent_task_id, state):
    """Behavior 1: write task-relevant state subset for subagent SessionStart."""
    handoff = {
        "subagent_id": subagent_id,
        "parent_task_id": parent_task_id,
        "session_uuid": state.get("session_uuid", ""),
        "active_task_id": state.get("active_task_id", ""),
        "layer1_scope_files": state.get("layer1_scope_files", []),
        "task_success_criteria": state.get("task_success_criteria", []),
        "layer19_last_impact_level": state.get("layer19_last_impact_level", "LOW"),
        "layer1_task_category": state.get("layer1_task_category", ""),
        "layer2_unresolved_events": [
            e for e in state.get("layer2_unresolved_events", [])
            if e.get("status") == "open"
            and e.get("task_id") == state.get("active_task_id", "")
        ],
        "handoff_ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "handoff_type": "dispatch",
        "subagent_events": [],
    }
    try:
        with open(_handoff_path(subagent_id), "w", encoding="utf-8") as f:
            json.dump(handoff, f)
    except Exception:
        pass


def _merge_subagent_events(subagent_id, parent_task_id, state):
    """Behaviors 2+4+5: merge events from handoff file, handle absent=timeout, cleanup."""
    path = _handoff_path(subagent_id)
    subagents = state.get("layer5_subagents", {})
    if not os.path.exists(path):
        # Behavior 4: absent file = subagent_timeout marker
        if subagent_id in subagents:
            subagents[subagent_id]["timeout_marker"] = True
        state["layer5_subagents"] = subagents
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # Behavior 4: incomplete/corrupt = timeout marker
        if subagent_id in subagents:
            subagents[subagent_id]["timeout_marker"] = True
        state["layer5_subagents"] = subagents
        return
    # Behavior 2: merge subagent events tagged with parent_task_id
    subagent_events = data.get("subagent_events", [])
    for evt in subagent_events:
        evt["parent_task_id"] = parent_task_id
        try:
            with open(MONITOR_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(evt) + chr(10))
        except Exception:
            pass
    if subagent_id in subagents:
        subagents[subagent_id]["merged_events"] = len(subagent_events)
        subagents[subagent_id]["status"] = "merged"
    state["layer5_subagents"] = subagents
    # Behavior 5: cleanup handoff file after successful merge
    try:
        os.remove(path)
    except Exception:
        pass


def process_predispatch(tool_name, tool_input, state):
    """Record dispatch event at PreToolUse time. Exported for testing."""
    if tool_name != "Agent":
        return None

    tool_input = tool_input or {}
    task_desc = str(
        tool_input.get("prompt", "") or
        tool_input.get("task", "") or
        tool_input.get("description", "") or ""
    )[:200]

    subagent_id = str(uuid.uuid4())[:8]
    event = {
        "event_id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "layer": "layer5",
        "type": "subagent_dispatch",
        "session_uuid": state.get("session_uuid", ""),
        "parent_task_id": state.get("active_task_id", ""),
        "subagent_id": subagent_id,
        "task_description": task_desc,
        "status": "in_flight",
        "working_dir": os.getcwd(),
    }

    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + chr(10))
    except Exception:
        pass

    # Track in-flight subagent so PostToolUse can correlate by parent_task_id
    subagents = state.get("layer5_subagents", {})
    subagents[subagent_id] = {
        "parent_task_id": event["parent_task_id"],
        "status": "in_flight",
        "ts": event["ts"],
        "task": task_desc,
    }
    state["layer5_subagents"] = subagents
    ss.write_state(state)
    # Behavior 1: write handoff file for subagent SessionStart
    _write_handoff(subagent_id, event["parent_task_id"], state)
    return event


def process_and_record(tool_name, tool_input, tool_response, state):
    """Core logic - returns event dict or None. Exported for testing."""
    if tool_name != "Agent":
        return None

    tool_input = tool_input or {}
    resp_lower = str(tool_response or "").lower()
    status = "subagent_timeout" if any(
        kw in resp_lower for kw in ("timeout", "timed out", "error:", "exception:")
    ) else "subagent_complete"

    task_desc = str(
        tool_input.get("prompt", "") or
        tool_input.get("task", "") or
        tool_input.get("description", "") or ""
    )[:200]

    subagents = state.get("layer5_subagents", {})
    parent_task_id = state.get("active_task_id", "")
    subagent_id = _find_inflight_id(subagents, parent_task_id)

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "layer": "layer5",
        "type": "subagent_return",
        "session_uuid": state.get("session_uuid", ""),
        "parent_task_id": parent_task_id,
        "subagent_id": subagent_id,
        "task_description": task_desc,
        "status": status,
        "working_dir": os.getcwd(),
    }

    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + chr(10))
    except Exception:
        pass

    subagents[subagent_id] = {
        "parent_task_id": parent_task_id,
        "status": status,
        "ts": event["ts"],
        "task": task_desc,
    }
    state["layer5_subagents"] = subagents
    ss.write_state(state)
    # Behaviors 2+4+5: merge subagent events, handle timeout, cleanup
    _merge_subagent_events(subagent_id, parent_task_id, state)
    ss.write_state(state)
    return event


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return

    tool_name = payload.get("tool_name", "")
    if tool_name != "Agent":
        return

    state = ss.read_state()
    # Distinguish PreToolUse (no tool_response) from PostToolUse
    if "tool_response" not in payload:
        process_predispatch(tool_name, payload.get("tool_input", {}), state)
    else:
        process_and_record(
            tool_name,
            payload.get("tool_input", {}),
            payload.get("tool_response", ""),
            state,
        )


if __name__ == "__main__":  # pragma: no cover
    main()

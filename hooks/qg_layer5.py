#!/usr/bin/env python3
"""Layer 5 - Subagent Coordination (PostToolUse on Agent tool).
Records dispatch/return events and tracks parent_task_id linkage.
"""
import json, os, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")


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

    event = {
        "event_id": str(uuid.uuid4()),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "layer": "layer5",
        "type": "subagent_return",
        "session_uuid": state.get("session_uuid", ""),
        "parent_task_id": state.get("active_task_id", ""),
        "subagent_id": str(uuid.uuid4())[:8],
        "task_description": task_desc,
        "status": status,
        "working_dir": os.getcwd(),
    }

    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + chr(10))
    except Exception:
        pass

    subagents = state.get("layer5_subagents", {})
    subagents[event["subagent_id"]] = {
        "parent_task_id": event["parent_task_id"],
        "status": status,
        "ts": event["ts"],
        "task": task_desc,
    }
    state["layer5_subagents"] = subagents
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
    process_and_record(
        tool_name,
        payload.get("tool_input", {}),
        payload.get("tool_response", ""),
        state,
    )


if __name__ == "__main__":
    main()

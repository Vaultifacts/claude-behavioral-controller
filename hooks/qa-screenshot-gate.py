#!/usr/bin/env python3
"""
QA Screenshot Gate — Stop Hook

Blocks responses during QA/walkthrough sessions that claim items Pass
without evidence of screenshot tool calls in the conversation.

Triggers on: Stop event
Checks for: .walkthrough-active file in repo root
Action: Block if response contains Pass/verified claims without screenshot evidence
"""
import json
import sys
import os
import re

def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, Exception):
        print(json.dumps({"continue": True}))
        return

    # Only active during QA sessions
    walkthrough_file = os.path.join(os.getcwd(), '.walkthrough-active')
    if not os.path.exists(walkthrough_file):
        print(json.dumps({"continue": True}))
        return

    response = input_data.get("assistant_response", "")
    tool_calls = input_data.get("tool_calls", [])

    pass_patterns = [
        r'\bPass\b.*\bverified\b',
        r'\bverified\b.*\bPass\b',
        r'\ball.*pass\b',
        r'\b\d+\s*Pass\b',
        r'Pass:\s*\d+',
        r'100%.*confidence',
    ]

    has_pass_claim = any(re.search(p, response, re.IGNORECASE) for p in pass_patterns)

    if not has_pass_claim:
        print(json.dumps({"continue": True}))
        return

    screenshot_tools = ['mcp__claude-in-chrome__computer']
    has_screenshot = False
    for call in tool_calls:
        tool_name = call.get("tool_name", "") or call.get("name", "")
        tool_input = call.get("input", {}) or call.get("parameters", {})
        if tool_name in screenshot_tools and tool_input.get("action") == "screenshot":
            has_screenshot = True
            break

    if not has_screenshot:
        print(json.dumps({
            "decision": "block",
            "reason": "QA SCREENSHOT GATE: You claimed Pass/verified results but took no screenshots this turn. Take a screenshot using mcp__claude-in-chrome__computer (action: screenshot) and visually verify before claiming Pass."
        }))
        return

    print(json.dumps({"continue": True}))

if __name__ == "__main__":  # pragma: no cover
    main()

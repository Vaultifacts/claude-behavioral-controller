#!/usr/bin/env python3
# notion-commit-reminder.py -- PostToolUse hook (Bash matcher)
# Fires after every Bash tool call. If the command was a git commit,
# injects a mandatory Notion Session Log reminder into Claude context.
# Global hook -- works across ALL projects.
import json, sys

try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)

command = data.get("tool_input", {}).get("command", "")

# Detect git commit (skip --no-commit, dry-run; amend is still a real commit)
if "git commit" in command and "--no-commit" not in command and "--dry-run" not in command:
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "[notion-commit-reminder] You just ran git commit. "
                "MANDATORY: Update the Notion Session Log NOW before your next action. "
                "Use mcp__claude_ai_Notion__notion-create-pages with "
                "data_source_id=96e9f0c8-1de6-831b-80c7-8738087ef83f. "
                "Do NOT skip this step. This applies in ALL projects, every session."
            )
        }
    }
    print(json.dumps(result))

sys.exit(0)

# Plan: Fix Quality Gate Stop Hook JSON Validation Error

## Context
The quality gate prompt hook fires but returns "Stop hook error: JSON validation failed". The prompt hook's LLM output isn't matching the expected JSON schema for Stop hooks.

## Root Cause
Stop hooks expect specific JSON output format. The prompt tells the LLM to output `{"decision":"block","reason":"..."}` or `{"decision":"allow"}` but the Stop hook event expects different fields. Looking at the hook documentation:

For Stop hooks, the valid JSON output fields are:
- `systemMessage` — display message to user
- `continue` — set to false to block
- `stopReason` — message when blocking
- `decision` — "block" for Stop hooks

The issue is likely that the haiku model outputs the JSON wrapped in markdown code blocks or with extra text, which fails JSON parsing. Or the schema expects specific field names that don't match what I told it to output.

## Fix
Change the prompt to output the exact JSON format the harness expects, and explicitly tell the model to output ONLY raw JSON with no markdown, no explanation, no code blocks.

## Implementation
Update the quality gate prompt hook in `~/.claude/settings.json` to:
1. Instruct output as raw JSON only — no markdown, no code blocks, no extra text
2. Use the correct field names: `continue` (boolean) + `stopReason` (string) for blocking, or just `continue: true` for passing

---
name: OpenClaw Workflow
description: OpenClaw/Clawbot integration patterns — headless Claude via messaging apps (Telegram, WhatsApp, Discord)
type: reference
last_reviewed: 2026-03-22
---

# OpenClaw (Clawbot) Workflow Reference

## What is OpenClaw?
OpenClaw (formerly Clawdbot/Moltbot) is an open-source self-hosted autonomous agent
that connects Claude AI to messaging apps. Created by Peter Steinberger.
- Site: clawd.bot / openclaw.ai
- GitHub: openclaw/openclaw
- Connects: Telegram, WhatsApp, Discord, Slack, Signal, iMessage, Matrix + more
- Runs: Locally on your machine (not cloud)
- Uses: Claude API as its LLM backbone

## Install OpenClaw
```bash
git clone https://github.com/openclaw/openclaw
cd openclaw
# Configure with your Claude API key + messaging platform token
# See openclaw.ai/docs for platform-specific setup
```

## Claude Code + OpenClaw Integration Pattern

OpenClaw sends messages from your phone → runs `claude -p` headlessly → returns results.

**Example headless commands OpenClaw can trigger:**
```bash
# Run a task headlessly
claude -p "Fix the TypeScript errors in src/auth.ts" \
  --allowedTools "Read,Edit,Bash(npm run:*),Bash(npx:*)" \
  --output-format json \
  --max-turns 10

# Research a question
claude -p "How does the auth flow work in this project?" \
  --allowedTools "Read,Grep,Glob" \
  --output-format json

# Check project status
claude -p "Run tests and report results" \
  --allowedTools "Bash(npm run test:*)" \
  --output-format json
```

## Official Slack Integration (Anthropic Native)
Claude Code has a native Slack integration:
- @mention Claude in any Slack channel
- Creates a Claude Code session in Slack
- Can open PRs, fix bugs, explain code — all from Slack
- Set up via: claude mcp add --transport http slack-integration ...

## Telegram Bot Alternative (Lighter Weight)
Community project: github.com/RichardAtCT/claude-code-telegram
- ~100 lines of code
- Maps Telegram messages to headless `claude -p` calls
- Good for quick one-off tasks from phone

## Discord Integration
Community project: github.com/zebbern/claude-code-discord
- Brings Claude Code to Discord channels
- Supports shell/git/Claude operations

## Safety Note
OpenClaw has privileged access to your machine. Best practices:
- Run in a directory with limited scope (not your entire home dir)
- Use `--allowedTools` to restrict what Claude can do
- Never use `--dangerously-skip-permissions` with remote access
- Set `--max-turns` to prevent infinite loops

## Headless Mode Quick Reference
```bash
# Basic task
claude -p "your task here"

# With tool restrictions (safer)
claude -p "task" --allowedTools "Read,Edit,Bash(npm:*)"

# JSON output for parsing
claude -p "task" --output-format json

# Continue last session
claude --continue

# Resume named session
claude --resume

# Limit turns (prevent infinite loops)
claude -p "task" --max-turns 5
```

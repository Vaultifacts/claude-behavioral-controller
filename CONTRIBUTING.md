# Contributing to Claude Behavioral Controller

Thank you for your interest in contributing to the Claude Behavioral Controller! This document provides guidelines and instructions for contributing to this quality monitoring and behavioral enforcement system for Claude Code.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Project Architecture](#project-architecture)
- [Understanding the Hook System](#understanding-the-hook-system)
- [Adding New Hooks](#adding-new-hooks)
- [Testing Guidelines](#testing-guidelines)
- [Submitting Changes](#submitting-changes)
- [Release Process](#release-process)

## Code of Conduct

This project adheres to a standard of professional, respectful communication. We expect all contributors to:

- Be respectful and inclusive in all interactions
- Focus on constructive feedback
- Accept constructive criticism gracefully
- Prioritize the quality and safety of the system

## Getting Started

### Prerequisites

- **Python 3.10+** — The hooks are written in Python
- **Claude Code** — Required for testing hooks in a real environment
- **Git** — For version control
- **PowerShell 7** (Windows) or **Bash** (Unix) — For running utility scripts

### Repository Structure

```
claude-behavioral-controller/
├── agents/           # Agent configurations and definitions
├── commands/         # Custom slash commands for Claude Code
├── docs/             # Additional documentation
├── hooks/            # Quality gate hooks (core of the system)
├── memory/           # Session memory and state management
├── modes/            # Mode-specific configurations
├── plans/            # Plan templates and examples
├── rules/            # Rule definitions for quality gates
├── scripts/          # Utility scripts
├── skills/           # Skill definitions
├── templates/        # Templates for various outputs
├── todos/            # Todo management
├── tools/            # Additional tools
├── CLAUDE.md         # Global user defaults for Claude Code
├── README.md         # Project overview
└── settings.json     # Claude Code settings
```

## Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/claude-behavioral-controller.git
   cd claude-behavioral-controller
   ```

2. **Install dependencies:**
   The project primarily uses standard library Python modules, but some hooks may require:
   ```bash
   pip install requests  # For API calls in certain hooks
   ```

3. **Set up Claude Code integration:**
   - Install Claude Code if you haven't already
   - Copy the hooks to your Claude Code hooks directory:
     ```bash
     # On macOS/Linux
     cp -r hooks/* ~/.claude/hooks/
     
     # On Windows (PowerShell)
     Copy-Item -Recurse -Path "hooks\*" -Destination "$env:USERPROFILE\.claude\hooks\"
     ```

4. **Copy settings:**
   ```bash
   cp settings.json ~/.claude/settings.json
   ```

## Project Architecture

### The Hook Stack

The behavioral controller operates as a layered hook stack that intercepts Claude Code lifecycle events:

```
SessionStart
  └── Layer 0       — Inject previous session's unresolved items
  └── Layer ENV     — Validate environment (git branch, tools, env vars)

UserPromptSubmit
  └── Layer 1       — Classify task type; generate session UUID

PreToolUse (every tool call)
  └── Layer ENV     — Validate file paths
  └── Layer 1.5     — Rule validation (edit-without-read, etc.)
  └── Layer 1.9     — Change impact analysis
  └── Layer 1.7     — User intent verification
  └── Layer 1.8     — Hallucination detection
  └── Layer 2.7     — Testing coverage checks

PostToolUse (every tool call)
  └── Layer 2       — Detect laziness, incorrect tool use, errors ignored
  └── Layer 3       — Notion integration for persistent tracking

ResponsePreview
  └── Layer 4       — Final quality checks before response delivery

SessionEnd
  └── Cleanup       — Archive session data, generate reports
```

### Classification System

Every response is classified as:
- **TP** (True Positive) — Failure was correctly prevented
- **FP** (False Positive) — Incorrectly blocked valid action
- **FN** (False Negative) — Failed to catch an actual problem
- **TN** (True Negative) — Correctly allowed valid action

### Task Types

The system classifies tasks into categories:
- **MECHANICAL** — Simple, repetitive tasks (low risk)
- **ASSUMPTION** — Tasks requiring assumptions (medium risk)
- **OVERCONFIDENCE** — Tasks where Claude might be overconfident (high risk)
- **PLANNING** — Complex tasks requiring planning (high risk)
- **DEEP** — Deep technical work requiring careful analysis (highest risk)

## Understanding the Hook System

### Hook Lifecycle

Each hook is a Python script that receives JSON input via stdin and outputs JSON via stdout:

```python
#!/usr/bin/env python3
import json
import sys

def main():
    # Read input from Claude Code
    input_data = json.load(sys.stdin)
    
    # Process the input
    result = process_hook(input_data)
    
    # Output result
    print(json.dumps(result))

def process_hook(data):
    # Your hook logic here
    return {
        "decision": "allow",  # or "block"
        "reason": "Optional reason for blocking",
        "notifications": []   # Optional notifications to display
    }

if __name__ == "__main__":
    main()
```

### Input Format

Hooks receive different input depending on the lifecycle event:

**SessionStart:**
```json
{
  "event": "session_start",
  "timestamp": "2026-03-30T12:00:00Z",
  "working_directory": "/path/to/project"
}
```

**UserPromptSubmit:**
```json
{
  "event": "user_prompt_submit",
  "prompt": "User's prompt text",
  "session_id": "uuid",
  "timestamp": "2026-03-30T12:00:00Z"
}
```

**PreToolUse:**
```json
{
  "event": "pre_tool_use",
  "tool": "tool_name",
  "arguments": {...},
  "session_id": "uuid"
}
```

**PostToolUse:**
```json
{
  "event": "post_tool_use",
  "tool": "tool_name",
  "arguments": {...},
  "result": {...},
  "session_id": "uuid"
}
```

### Output Format

```json
{
  "decision": "allow|block|warn",
  "reason": "Human-readable explanation",
  "notifications": [
    {
      "level": "info|warning|error|critical",
      "message": "Notification text"
    }
  ],
  "metadata": {
    "key": "value"
  }
}
```

## Adding New Hooks

### 1. Choose the Right Layer

Determine which lifecycle event your hook should intercept:

- **SessionStart** — One-time initialization
- **UserPromptSubmit** — Analyze incoming prompts
- **PreToolUse** — Validate before tool execution
- **PostToolUse** — Analyze after tool execution
- **ResponsePreview** — Final checks before response
- **SessionEnd** — Cleanup and archiving

### 2. Create the Hook File

Create a new file in the `hooks/` directory:

```bash
touch hooks/qg_layerXX.py  # Use next available layer number
chmod +x hooks/qg_layerXX.py
```

### 3. Implement the Hook

Follow this template:

```python
#!/usr/bin/env python3
"""
Layer XX: [Brief description of what this hook does]

Classification: [TP/FP/FN/TN tracking if applicable]
"""

import json
import sys
import os

# Import shared utilities
sys.path.insert(0, os.path.dirname(__file__))
from _hooks_shared import log_event, classify_outcome

def main():
    try:
        input_data = json.load(sys.stdin)
        event_type = input_data.get("event")
        
        # Only process relevant events
        if event_type not in ["pre_tool_use", "post_tool_use"]:
            print(json.dumps({"decision": "allow"}))
            return
        
        # Your hook logic
        result = analyze(input_data)
        
        # Log for metrics
        log_event("layerXX", result.get("classification"))
        
        print(json.dumps(result))
        
    except Exception as e:
        # Fail open — don't block on hook errors
        print(json.dumps({
            "decision": "allow",
            "reason": f"Hook error: {str(e)}",
            "notifications": [{
                "level": "warning",
                "message": f"Layer XX encountered an error: {str(e)}"
            }]
        }))

def analyze(data):
    """Main analysis logic."""
    tool = data.get("tool", "")
    arguments = data.get("arguments", {})
    
    # Your detection logic here
    issues = detect_issues(tool, arguments)
    
    if issues:
        return {
            "decision": "warn",  # or "block" for critical issues
            "reason": f"Detected: {', '.join(issues)}",
            "notifications": [{
                "level": "warning",
                "message": f"Layer XX: {issue}"
            } for issue in issues],
            "classification": "TP"  # or appropriate classification
        }
    
    return {
        "decision": "allow",
        "classification": "TN"
    }

def detect_issues(tool, arguments):
    """Detect specific issues."""
    issues = []
    # Add detection logic
    return issues

if __name__ == "__main__":
    main()
```

### 4. Update Documentation

Add your hook to:
- `README.md` — Architecture diagram
- This `CONTRIBUTING.md` — Layer descriptions
- `docs/hooks.md` — Detailed documentation (if applicable)

### 5. Test Your Hook

Test manually before submitting:

```bash
# Test with sample input
echo '{"event": "pre_tool_use", "tool": "read_file", "arguments": {"path": "test.py"}}' | python3 hooks/qg_layerXX.py
```

## Testing Guidelines

### Unit Testing

Create tests for individual hook logic:

```python
# tests/test_layerXX.py
import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'hooks'))

from qg_layerXX import detect_issues

class TestLayerXX(unittest.TestCase):
    def test_detects_edit_without_read(self):
        result = detect_issues("edit_file", {"path": "new_file.py"})
        self.assertIn("edit_without_read", result)
    
    def test_allows_read_before_edit(self):
        # Mock state where file was previously read
        result = detect_issues("edit_file", {"path": "read_file.py"})
        self.assertEqual(result, [])

if __name__ == "__main__":
    unittest.main()
```

### Integration Testing

Test hooks in a real Claude Code session:

1. Install the hook in your `~/.claude/hooks/` directory
2. Start a new Claude Code session
3. Trigger the condition your hook detects
4. Verify the hook fires and produces expected output

### Metrics and Validation

Track your hook's effectiveness:

- **Precision** — Of all blocks/warnings, how many were correct?
- **Recall** — Of all actual issues, how many were caught?
- **False Positive Rate** — How often does it incorrectly block?

Use the `_hooks_shared.py` utilities for logging and metrics.

## Submitting Changes

### Before Submitting

1. **Test thoroughly:**
   - Unit tests pass
   - Integration tested in Claude Code
   - No regressions in existing hooks

2. **Update documentation:**
   - README.md if architecture changed
   - This CONTRIBUTING.md if process changed
   - Inline comments for complex logic

3. **Follow code style:**
   - PEP 8 compliance
   - Type hints where appropriate
   - Docstrings for all functions

### Commit Message Format

Use conventional commits:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat` — New hook or feature
- `fix` — Bug fix in existing hook
- `docs` — Documentation changes
- `refactor` — Code restructuring
- `test` — Adding or updating tests
- `chore` — Maintenance tasks

Examples:
```
feat(hooks): add layer 2.8 for dependency tracking

Implements detection of undeclared dependencies in Python imports.
Integrates with layer 1.9 for impact analysis.

Closes #123
```

```
fix(layer15): reduce false positives on test file edits

Test files often need edits without corresponding src changes.
Added exemption for paths matching */test_*.py.

Fixes #456
```

### Pull Request Process

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/layer-XX-description
   ```

2. **Make your changes** and commit

3. **Push to your fork:**
   ```bash
   git push origin feature/layer-XX-description
   ```

4. **Open a Pull Request** with:
   - Clear title following commit format
   - Description of what changed and why
   - Testing performed
   - Any breaking changes

5. **Address review feedback** promptly

### Review Criteria

Pull requests will be reviewed for:

- **Correctness** — Does the hook correctly detect the intended issues?
- **Performance** — Does it add unacceptable latency to tool calls?
- **Precision** — Is the false positive rate acceptable?
- **Documentation** — Is the hook well-documented?
- **Testing** — Are there adequate tests?

## Release Process

Releases are managed by the maintainers:

1. Version tags follow semantic versioning (e.g., `v1.2.3`)
2. Release notes document all changes
3. Migration guides provided for breaking changes

## Questions?

- Open an issue for bug reports or feature requests
- Join discussions in existing issues
- Reach out to maintainers for architectural guidance

Thank you for contributing to safer, more reliable AI-assisted coding!

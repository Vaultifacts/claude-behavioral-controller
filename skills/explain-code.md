---
name: explain-code
description: Structured deep-dive explanation of a file, function, or system — covering purpose, data flow, design decisions, dependencies, entry points, and gotchas. Use when the user asks to "explain this in depth", "walk me through", "document how X works", "I need to understand before modifying", or wants a shareable reference explanation. Do NOT use for quick one-liner questions — those don't need a skill.
---

Explain: $ARGUMENTS

Use the researcher agent to explore the code, then provide:

1. **What it does**: One paragraph plain-English summary of the purpose
2. **How it works**: Step-by-step flow of the main logic (numbered list)
3. **Key design decisions**: Why it's structured this way (note any non-obvious choices)
4. **Dependencies**: What it imports/calls and why
5. **Entry points**: How other code uses this (find callers with grep)
6. **Gotchas**: Anything surprising, fragile, or worth knowing before modifying it

Format: Use headers and code snippets. Aim for clarity over completeness.
Maximum: 400 words unless the system is genuinely complex.

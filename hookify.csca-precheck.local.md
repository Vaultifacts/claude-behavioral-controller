---
name: csca-precheck
enabled: true
event: prompt
action: warn
conditions:
  - field: user_prompt
    operator: regex_match
    pattern: .*
---

**CSCA STANDARD — your response will be scored on these 4 axes (≥90/100 required to pass):**

- **Confidence**: Every factual claim must be backed by inline quoted output (grep results, file content, test output, command results). Do NOT state conclusions without pasting the evidence that supports them.
- **Satisfaction**: Fully answer what was asked. Do not partially address the request.
- **Completeness**: Nothing requested left out. Address every part of the ask.
- **Accuracy**: Facts, code, and conclusions must be correct per the inline evidence shown.

If this task does not involve factual claims or code, these criteria still apply — back any non-trivial assertion with a tool call result quoted inline.

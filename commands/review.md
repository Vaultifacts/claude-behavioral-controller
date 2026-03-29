# /review — Code Review Command
# Triggers a thorough review of staged or specified files.
# Usage: /review [file-or-path]

Review the code in $ARGUMENTS (or all staged changes if no argument given).

Check for:
1. Logic errors and off-by-one bugs
2. Security vulnerabilities (injection, XSS, exposed secrets, insecure deserialization)
3. Performance issues (N+1 queries, unnecessary loops, missing indexes)
4. Missing edge cases and error handling at system boundaries
5. Naming clarity and code readability
6. Dead code, unused imports, or commented-out stubs

Output format:
- Group findings by severity: CRITICAL → WARNING → INFO
- For each finding: file:line, description, suggested fix
- End with a one-line overall verdict

Do not refactor unless explicitly asked. Flag issues only.

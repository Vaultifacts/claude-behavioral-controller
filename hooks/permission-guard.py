"""
permission-guard.py — PreToolUse hook.
Dynamic permission evaluation for cases static rules can't express.
- Blocks Bash network tools (curl/wget) to non-allowed domains
- Blocks git push --force to main/master
Always returns JSON {"decision":"block","reason":"..."} to block, or exits 0 to allow.
"""
import sys
import json
import re

ALLOWED_CURL_DOMAINS = {
    'github.com', 'api.github.com', 'docs.github.com',
    'npmjs.com', 'registry.npmjs.org',
    'pypi.org',
    'docs.anthropic.com', 'api.anthropic.com',
    'nodejs.org',
    'localhost', '127.0.0.1', '0.0.0.0',
}

FORCE_PUSH_RE = re.compile(
    r'git\s+push\s+.*--force|git\s+push\s+-f\b',
    re.IGNORECASE
)

MAIN_BRANCH_RE = re.compile(
    r'\b(main|master)\b',
    re.IGNORECASE
)


def extract_domain(cmd):
    """Extract domain from curl/wget command, handling both https:// and protocol-less URLs."""
    m = re.search(r'https?://([^/:\s]+)', cmd)
    if m:
        domain = m.group(1).lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    m = re.search(r'(?:curl|wget)(?:\s+-\S+)*\s+([a-zA-Z0-9][\w.-]+\.[a-z]{2,})(?:[/?#\s]|$)', cmd)
    if m:
        domain = m.group(1).lower()
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    return None


def main():
    try:
        data = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
    except Exception:
        data = {}

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {})

    if tool_name == 'Bash' and isinstance(tool_input, dict):
        cmd = tool_input.get('command', '')

        # Block git push --force to main/master
        # Use first_token guard to avoid matching git patterns inside scripts/strings
        first_token = cmd.lstrip().split()[0] if cmd.strip() else ''
        if first_token == 'git' and FORCE_PUSH_RE.search(cmd) and MAIN_BRANCH_RE.search(cmd):
            print(json.dumps({
                "decision": "block",
                "reason": "Force push to main/master is blocked by permission-guard."
            }))
            sys.exit(0)

        # Block curl/wget to non-allowed domains
        if re.search(r'\b(curl|wget)\b', cmd):
            domain = extract_domain(cmd)
            if domain and domain not in ALLOWED_CURL_DOMAINS:
                print(json.dumps({
                    "decision": "block",
                    "reason": f"Network access to {domain} blocked. Use WebFetch instead."
                }))
                sys.exit(0)

    # No opinion — allow
    sys.exit(0)


if __name__ == "__main__":
    main()

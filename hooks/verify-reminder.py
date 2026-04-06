#!/usr/bin/env python3
"""PostToolUse hook: reminds Claude to run verification after editing code files."""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import NON_CODE_PATH_RE


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    tool = data.get('tool_name', '')
    fp = (data.get('tool_input') or {}).get('file_path', '')

    if tool in ('Edit', 'Write') and fp and not NON_CODE_PATH_RE.search(fp):
        fname = os.path.basename(fp)
        sys.stderr.write(f'[verify] You edited {fname}. Run a test or syntax check and quote the output before responding.' + chr(10))
        return 2

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main() or 0)

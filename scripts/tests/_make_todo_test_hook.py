"""
Helper: read todo-extractor.py, apply test patches, write to a temp path.
Prints the patched file path to stdout.
Usage: python _make_todo_test_hook.py <feed_file_path>
"""
import sys
import os

HOOKS_DIR = os.path.expanduser("~/.claude/hooks")
HOOK_PATH = os.path.join(HOOKS_DIR, "todo-extractor.py")

feed_file = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("TODO_FEED_FILE", "")
# Use basename matching original so [paths] remapping works with coverage
_default_out = os.path.join(os.path.dirname(__file__), "todo-extractor.py")
out_path = sys.argv[2] if len(sys.argv) > 2 else _default_out

src = open(HOOK_PATH, encoding="utf-8").read()

# Patch 1: override FEED_FILE to use env var (set by test runner)
src = src.replace(
    "FEED_FILE   = os.path.join(CLAUDE_DIR, 'todo-feed.json')",
    "FEED_FILE   = os.environ.get('TODO_FEED_FILE') or os.path.join(CLAUDE_DIR, 'todo-feed.json')",
)

# Patch 2: inject detect_project_name at module level before Pattern Definitions
# (it is only defined inside except ImportError which never fires)
dpn_lines = [
    "",
    "def detect_project_name(payload):",
    "    cwd = payload.get('workspace', {}).get('current_dir', '') or payload.get('cwd', '')",
    "    if not cwd:",
    "        return None",
    "    return os.path.basename(cwd.rstrip('/\\\\'))",
    "",
]
dpn_block = "\n".join(dpn_lines) + "\n"

marker = "\u2500\u2500 Pattern Definitions \u2500"  # ── Pattern Definitions ─
src = src.replace("# " + marker, dpn_block + "# " + marker)

open(out_path, "w", encoding="utf-8").write(src)
print(out_path)

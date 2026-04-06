"""
prune-permissions.py — SessionStart hook
Removes one-off Bash permission entries from settings.local.json.

Keeps: Skill(*), mcp__*, WebFetch(*), Bash entries with wildcards (*).
Removes: Literal Bash(...) entries without wildcards (one-off approvals).
Atomic write via tempfile + os.replace. Always exits 0.
"""
import json
import os
import sys
import tempfile

SETTINGS_PATH = os.path.expanduser("~/.claude/settings.local.json").replace("\\", "/")


MAX_REUSABLE_LEN = 40  # Pattern entries like "Bash(gh pr:*)" are short


def is_reusable(entry: str) -> bool:
    """Return True if this permission entry should be kept across sessions."""
    if not entry.startswith("Bash("):
        return True
    # Short Bash entries with wildcards are intentional patterns (e.g. "Bash(gh pr:*)")
    # Long entries with * are just commands that happen to contain literal asterisks
    return "*" in entry and len(entry) <= MAX_REUSABLE_LEN


def main():
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return

    allow = data.get("permissions", {}).get("allow", [])
    if not allow:
        return

    cleaned = [e for e in allow if is_reusable(e)]

    if len(cleaned) == len(allow):
        return  # Nothing to prune

    pruned = len(allow) - len(cleaned)
    data["permissions"]["allow"] = cleaned

    # Atomic write
    dir_path = os.path.dirname(SETTINGS_PATH)
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, SETTINGS_PATH)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        return

    print(f"[prune-permissions] Removed {pruned} one-off Bash entries from settings.local.json")


if __name__ == "__main__":  # pragma: no cover
    try:
        main()
    except Exception:
        pass
    sys.exit(0)

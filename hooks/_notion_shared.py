"""
_notion_shared.py — Shared utilities for notion-recall.py and notion-capture.py.

Avoids duplicating detect_project_name(), load_token(), and DB constants.
"""

import json
import os

ENV_PATH = os.path.normpath(os.path.expanduser("~/.claude/.env"))

NOTION_VERSION = "2022-06-28"
NOTION_BASE = "https://api.notion.com/v1"

# Global Notion database IDs
DB_LESSONS_LEARNED = "31faa7d9-0a30-40f3-8c9c-e9939c003257"
DB_EXTERNAL_REFS = "343fb652-e9fb-4a84-9d0f-05130a965520"
DB_GLOSSARY = "fa4bae81-9eaa-4df7-aad4-2b4ac97426a2"
DB_PROMPT_LIBRARY = "2e1b19b7-364b-4255-8515-1ddc0896b967"
DB_BROWSER_NAV = "3249f0c81de6814fa81dde0c015d2e1c"


def load_token():
    """Load NOTION_TOKEN from ~/.claude/.env."""
    try:
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("NOTION_TOKEN="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val and not val.startswith("YOUR_"):
                        return val
    except Exception:
        pass
    return None


def detect_project_name(payload):
    """Derive project name from git root of cwd. Returns name or None for home directory sessions."""
    cwd = payload.get("workspace", {}).get("current_dir", "") or payload.get("cwd", "")
    if not cwd:
        return None
    cwd_clean = cwd.replace("\\", "/").rstrip("/")
    home = os.path.expanduser("~").replace("\\", "/").rstrip("/")
    if cwd_clean == home or cwd_clean == home.replace("C:", "/c"):
        return None
    import subprocess
    raw_name = os.path.basename(cwd_clean)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd, capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            git_root = result.stdout.strip().replace("\\", "/").rstrip("/")
            raw_name = os.path.basename(git_root)
    except Exception:
        pass
    mapping_path = os.path.join(os.path.expanduser("~"), ".claude", "project-names.json")
    try:
        with open(mapping_path, encoding="utf-8") as f:
            mapping = json.load(f)
        return mapping.get(raw_name, raw_name)
    except Exception:
        return raw_name


def notion_headers(token):
    """Return standard Notion API headers."""
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

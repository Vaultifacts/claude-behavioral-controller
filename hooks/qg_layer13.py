#!/usr/bin/env python3
"""Layer 13 -- Knowledge Freshness Verification (PostToolUse on Write/Edit).
Checks if imported Python modules exist and if referenced attributes are valid.
Advisory only -- warns but does not block.
"""
import importlib
import importlib.util
import json, os, re, sys, time, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import qg_session_state as ss

MONITOR_PATH = os.path.expanduser("~/.claude/qg-monitor.jsonl")
SIZE_LIMIT = 102400
CODE_EXTS = {".py"}

STDLIB_MODULES = {
    "os", "sys", "re", "json", "time", "datetime", "pathlib", "io",
    "collections", "itertools", "functools", "operator", "math",
    "random", "hashlib", "hmac", "secrets", "base64", "struct",
    "copy", "pprint", "textwrap", "unicodedata", "string",
    "subprocess", "shutil", "tempfile", "glob", "fnmatch",
    "pickle", "shelve", "csv", "configparser", "tomllib",
    "logging", "warnings", "traceback", "abc", "contextlib",
    "typing", "dataclasses", "enum", "types",
    "threading", "multiprocessing", "concurrent", "asyncio",
    "socket", "http", "urllib", "email", "html", "xml",
    "unittest", "doctest", "pdb", "profile", "timeit",
    "argparse", "getopt", "locale", "gettext",
    "importlib", "pkgutil", "zipimport",
    "ast", "dis", "inspect", "token", "tokenize",
    "os.path", "collections.abc", "typing.extensions",
    "uuid", "platform", "signal", "ctypes", "array",
}

SKIP_MODULES = {"__future__", "builtins", "_thread"}

def _write_event(event):
    try:
        with open(MONITOR_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + chr(10))
    except Exception:
        pass

def extract_imports(content):
    """Extract import statements from Python code. Returns list of (module, [attributes])."""
    imports = []
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        m = re.match(r"^import\s+([\w.]+)", stripped)
        if m:
            imports.append((m.group(1), []))
            continue
        m = re.match(r"^from\s+([\w.]+)\s+import\s+(.+)", stripped)
        if m:
            module = m.group(1)
            attrs_str = m.group(2).strip()
            if attrs_str == "*":
                imports.append((module, []))
            else:
                attrs = [a.strip().split(" as ")[0].strip() for a in attrs_str.split(",")]
                imports.append((module, [a for a in attrs if a and not a.startswith("(")]))
    return imports

def check_module_exists(module_name):
    """Check if a Python module can be found. Returns True if exists."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False

def check_attribute_exists(module_name, attr_name):
    """Check if an attribute exists in a module. Returns True if exists."""
    try:
        mod = importlib.import_module(module_name)
        return hasattr(mod, attr_name)
    except Exception:
        return False

def check_imports(file_path, content=None):
    """Check all imports in a Python file. Returns list of (severity, message)."""
    if not file_path:
        return []
    _, ext = os.path.splitext(file_path)
    if ext not in CODE_EXTS:
        return []
    if content is None:
        try:
            if not os.path.exists(file_path) or os.path.getsize(file_path) > SIZE_LIMIT:
                return []
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception:
            return []

    imports = extract_imports(content)
    issues = []
    state = ss.read_state()
    cache = state.get("layer13_import_cache", {})

    for module, attrs in imports:
        top = module.split(".")[0]
        if top in STDLIB_MODULES or module in STDLIB_MODULES or top in SKIP_MODULES:
            continue
        if top.startswith("_"):
            continue

        cache_key = module
        if cache_key in cache:
            exists = cache[cache_key]
        else:
            exists = check_module_exists(module)
            cache[cache_key] = exists

        if not exists:
            issues.append(("warning", "MODULE_NOT_FOUND: '{}' is not installed".format(module)))
            continue

        for attr in attrs:
            if attr.startswith("_"):
                continue
            attr_key = module + "." + attr
            if attr_key in cache:
                attr_exists = cache[attr_key]
            else:
                attr_exists = check_attribute_exists(module, attr)
                cache[attr_key] = attr_exists
            if not attr_exists:
                issues.append(("warning", "ATTR_NOT_FOUND: '{}' not in module '{}'".format(attr, module)))

    state["layer13_import_cache"] = cache
    ss.write_state(state)
    return issues

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        return
    issues = check_imports(file_path)
    if not issues:
        return
    state = ss.read_state()
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    event = {"event_id": str(uuid.uuid4()), "ts": ts, "session_uuid": state.get("session_uuid") or "", "working_dir": os.getcwd(), "layer": "layer13", "category": "KNOWLEDGE_FRESHNESS", "severity": "warning", "detection_signal": "; ".join(msg for _, msg in issues[:3]), "file_path": file_path}
    _write_event(event)
    lines = ["[Layer 13] Import check for {}:".format(os.path.basename(file_path))]
    for sev, msg in issues[:3]:
        lines.append("  - [{}] {}".format(sev, msg))
    text = chr(10).join(lines)
    out = {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}
    print(json.dumps(out))

if __name__ == "__main__":  # pragma: no cover
    main()

---
description: Python project conventions
paths: ["**/*.py", "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg"]
---

- Always `PYTHONIOENCODING=utf-8` before running Python on Windows
- Use `python` (not `python3`) — both point to Python 3.13
- Use `pip install` for dependencies; check `requirements.txt` first
- Prefer `venv` for isolation; activate with `source venv/Scripts/activate` (bash on Windows)
- Use `pathlib.Path` or `os.path.join` — never hardcode backslashes
- Always pass `encoding='utf-8'` to `open()` calls

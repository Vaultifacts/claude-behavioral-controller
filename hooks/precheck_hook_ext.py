#!/usr/bin/env python3
"""Testable helper functions for precheck-hook.py Layer 1 extension."""
import json, os, re


def tokenize(text):
    return set(re.findall(r'\b\w+\b', text.lower()))


def jaccard_similarity(text_a, text_b):
    """Jaccard similarity [0,1]. Empty text_a returns 1.0 (not a pivot)."""
    if not text_a.strip():
        return 1.0
    a, b = tokenize(text_a), tokenize(text_b)
    union = len(a | b)
    return len(a & b) / union if union > 0 else 1.0


def detect_deep(message):
    """Heuristic: message is DEEP if long enough AND contains a scope keyword."""
    try:
        with open(os.path.expanduser('~/.claude/qg-rules.json'), 'r', encoding='utf-8') as f:
            rules = json.load(f).get('layer1', {})
        min_len = rules.get('deep_min_length', 300)
        keywords = rules.get('deep_scope_keywords',
                             ["redesign", "migrate", "refactor all", "rewrite", "rebuild"])
    except Exception:
        min_len, keywords = 300, ["redesign", "migrate", "refactor all", "rewrite", "rebuild"]
    if len(message) < min_len:
        return False
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in keywords)


def infer_scope_files(message):
    """Extract file paths mentioned in the request."""
    return re.findall(r'[\w./\\-]+\.(?:py|js|ts|json|yaml|yml|md|sh|txt|html|css)', message)

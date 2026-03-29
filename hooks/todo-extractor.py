"""
todo-extractor.py — P4: Intelligent Todo Extractor Stop hook
Scans JSONL transcript at session end, extracts TODOs, writes todo-feed.json.
Registers on: Stop (async, Group 1 alongside stop-log + notion-capture).
Always exits 0.
"""
import hashlib
import json
import os
import re
import sys
import time

HOOKS_DIR  = os.path.dirname(os.path.abspath(__file__))
CLAUDE_DIR = os.path.dirname(HOOKS_DIR)

FEED_FILE   = os.path.join(CLAUDE_DIR, 'todo-feed.json')
PROJECTS_DIR = os.path.join(CLAUDE_DIR, 'projects')

# Import detect_project_name from _notion_shared (same pattern as notion-capture.py)
try:
    sys.path.insert(0, HOOKS_DIR)
    from _notion_shared import detect_project_name
except ImportError:
    def detect_project_name(payload):
        cwd = payload.get('workspace', {}).get('current_dir', '') or payload.get('cwd', '')
        if not cwd:
            return None
        import subprocess
        try:
            result = subprocess.run(
                ['git', 'rev-parse', '--show-toplevel'],
                capture_output=True, text=True, cwd=cwd, timeout=3
            )
            if result.returncode == 0:
                return os.path.basename(result.stdout.strip())
        except Exception:
            pass
        return os.path.basename(cwd.rstrip('/\\'))

# ── Pattern Definitions ────────────────────────────────────────

# Code TODOs (HIGH confidence — always extract from Write/Edit tool_use)
CODE_TODO_RE = re.compile(
    r'\b(?:TODO|FIXME|HACK|XXX|TEMP|HARDCODED)\s*[:]\s*(.{5,200})',
    re.IGNORECASE
)

# High-confidence conversational signals (always extract from assistant text)
HIGH_CONF_PATTERNS = [
    (re.compile(r"\bdon'?t forget\b\s+(.{10,200})", re.IGNORECASE), 'dont_forget'),
    (re.compile(r'\blater:\s*(.{10,200})', re.IGNORECASE),          'later'),
]

# Low-confidence conversational signals (require DEFERRAL_SIGNALS co-signal)
LOW_CONF_PATTERNS = [
    (re.compile(r'\bwe should\b\s+(.{10,200})',         re.IGNORECASE), 'should'),
    (re.compile(r'\brevisit\b\s+(.{10,200})',            re.IGNORECASE), 'revisit'),
    (re.compile(r'\bhardcoded\b\s+(.{10,200})',          re.IGNORECASE), 'hardcoded'),
    (re.compile(r'\bfor now\b[,\s]+(.{10,200})',         re.IGNORECASE), 'for_now'),
    (re.compile(r'\btemporar(?:y|ily)\b\s+(.{10,200})', re.IGNORECASE), 'temporary'),
    (re.compile(r'\bplaceholder\b\s+(.{10,200})',        re.IGNORECASE), 'placeholder'),
]

DEFERRAL_SIGNALS = re.compile(
    r'\b(?:later|eventually|at some point|when we|once|after|next session|'
    r'future|someday|come back|revisit|follow.?up|down the road)\b',
    re.IGNORECASE
)

ANTI_PATTERNS = re.compile(
    r'(?:the existing|there is already|I see a|the current|'
    r'this (?:TODO|FIXME|HACK)|the (?:TODO|FIXME|HACK) (?:says|at|in|on|comment)|'
    r'see the (?:TODO|FIXME)|found a (?:TODO|FIXME)|noticed a (?:TODO|FIXME)|'
    r'remove the (?:TODO|FIXME|HACK|existing)|existing (?:FIXME|TODO|HACK)|'
    r'has a (?:TODO|FIXME|HACK))',
    re.IGNORECASE
)


def normalize_text(text):
    return re.sub(r'\s+', ' ', text.strip().lower())


def item_hash(text):
    return hashlib.md5(normalize_text(text).encode()).hexdigest()[:8]


def atomic_write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    for _ in range(3):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.1)


def get_transcript_path(payload):
    tp = payload.get('transcript_path', '')
    if tp and os.path.isfile(tp):
        return tp
    cwd = payload.get('workspace', {}).get('current_dir', '') or payload.get('cwd', '')
    session_id = payload.get('session_id', '')
    if not cwd or not session_id:
        return None
    slug = re.sub(r'[:/\\]', '-', cwd).replace(' ', '-')
    path = os.path.join(PROJECTS_DIR, slug, f'{session_id}.jsonl')
    if os.path.isfile(path):
        return path
    if os.path.isdir(PROJECTS_DIR):
        for d in os.listdir(PROJECTS_DIR):
            candidate = os.path.join(PROJECTS_DIR, d, f'{session_id}.jsonl')
            if os.path.isfile(candidate):
                return candidate
    return None


def split_code_fences(text):
    """
    Split text on ``` boundaries.
    Returns list of segments; even indices (0, 2, 4...) are OUTSIDE fences.
    """
    return re.split(r'```[^\n]*\n?', text)


def extract_sentence_for_match(text, m):
    """Extract the sentence containing match m from text."""
    start = text.rfind('.', 0, m.start())
    start = 0 if start == -1 else start + 1
    end = text.find('.', m.end())
    end = len(text) if end == -1 else end + 1
    return text[start:end].strip()


def scan_transcript(path, now_ts):
    """
    Walk JSONL transcript, return list of TODO item dicts.
    Sources: tool_use (Write/Edit) and assistant text blocks.
    NOT tool_result blocks.
    """
    items = []
    seen_hashes = set()

    def add_item(text, source, category, file_path='', context=''):
        h = item_hash(text)
        if h in seen_hashes:
            return
        seen_hashes.add(h)
        items.append({
            'text':       text[:300],
            'source':     source,
            'context':    context[:120],
            'file_path':  file_path,
            'category':   category,
            'ts':         now_ts,
            'dismissed':  False,
        })

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = d.get('type', '')

            # ── tool_use blocks from assistant messages ──
            if rtype == 'assistant':
                msg = d.get('message', {})
                content_blocks = msg.get('content', [])
                if not isinstance(content_blocks, list):
                    continue

                for block in content_blocks:
                    btype = block.get('type', '')

                    # Code TODOs from Write/Edit
                    if btype == 'tool_use':
                        tool_name = block.get('name', '')
                        inp = block.get('input', {})
                        fp = inp.get('file_path', '')

                        if tool_name == 'Write':
                            scan_text = inp.get('content', '')
                            ctx = f'Written to {os.path.basename(fp)}' if fp else 'Written by Claude'
                        elif tool_name == 'Edit':
                            # Only new_string — not old_string (pre-existing code)
                            scan_text = inp.get('new_string', '')
                            ctx = f'Edited in {os.path.basename(fp)}' if fp else 'Edited by Claude'
                        else:
                            continue

                        if not scan_text:
                            continue

                        for m in CODE_TODO_RE.finditer(scan_text):
                            captured = m.group(1).strip()
                            if not captured:
                                continue
                            full_text = m.group(0).strip()
                            # Extract category keyword (TODO, FIXME, etc.)
                            kw_match = re.match(r'(\w+)', full_text)
                            category = kw_match.group(1).upper() if kw_match else 'TODO'
                            add_item(full_text, 'code_written', category, fp, ctx)

                    # Conversational TODOs from assistant text blocks
                    elif btype == 'text':
                        text = block.get('text', '')
                        if not text:
                            continue

                        # Split on code fences; only scan outside-fence segments (even indices)
                        segments = split_code_fences(text)
                        outside_segments = segments[0::2]  # indices 0, 2, 4...

                        for seg in outside_segments:
                            # High-confidence patterns
                            for pattern, category in HIGH_CONF_PATTERNS:
                                for m in pattern.finditer(seg):
                                    sentence = extract_sentence_for_match(seg, m)
                                    if ANTI_PATTERNS.search(sentence):
                                        continue
                                    captured = m.group(1).strip()[:200]
                                    if captured:
                                        add_item(sentence or captured, 'assistant', category)

                            # Low-confidence patterns (require deferral co-signal)
                            for pattern, category in LOW_CONF_PATTERNS:
                                for m in pattern.finditer(seg):
                                    sentence = extract_sentence_for_match(seg, m)
                                    if not DEFERRAL_SIGNALS.search(sentence):
                                        continue
                                    if ANTI_PATTERNS.search(sentence):
                                        continue
                                    captured = m.group(1).strip()[:200]
                                    if captured:
                                        add_item(sentence or captured, 'assistant', category)

    return items


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    session_id  = payload.get('session_id', '')
    now_ts      = int(time.time())

    path = get_transcript_path(payload)
    if not path:
        # Write empty feed so AHK doesn't show a stale badge
        atomic_write(FEED_FILE, {
            'ts': now_ts, 'session_id': session_id,
            'project': '', 'count': 0, 'items': [],
            'persisted_to_backlog': False,
        })
        sys.exit(0)

    project = detect_project_name(payload) or ''
    items   = scan_transcript(path, now_ts)

    atomic_write(FEED_FILE, {
        'ts':                   now_ts,
        'session_id':           session_id,
        'project':              project,
        'count':                len(items),
        'items':                items,
        'persisted_to_backlog': False,
    })


try:
    main()
except Exception:
    pass

sys.exit(0)

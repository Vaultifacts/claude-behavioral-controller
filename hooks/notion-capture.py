"""
notion-capture.py — Autonomous Notion capture Stop hook for Claude Code.

Fires at the end of every session. Reads the JSONL transcript from disk,
extracts insights, deduplicates against Notion, and inserts new entries
into 5 global databases: External References, Lessons Learned, Glossary, Prompt Library, Browser Navigation.

Safety: entire main() is wrapped in try/except. Always exits 0. No stdout output.
"""

import json
import os
import re
import sys
from collections import deque
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _notion_shared import (
    load_token, detect_project_name, notion_headers,
    NOTION_VERSION, NOTION_BASE,
    DB_LESSONS_LEARNED, DB_EXTERNAL_REFS, DB_GLOSSARY, DB_PROMPT_LIBRARY, DB_BROWSER_NAV,
)
from _hooks_shared import rotate_log

STATE_DIR = os.path.normpath(os.path.expanduser("~/.claude"))
LOG_PATH = os.path.join(STATE_DIR, "notion-capture.log")
PROJECTS_DIR = os.path.join(STATE_DIR, "projects")

MAX_PER_DB = 5
MIN_USER_MESSAGES = 3
MIN_DURATION_SECS = 30
DRY_RUN = os.getenv("NOTION_CAPTURE_DRY_RUN") == "1"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def log(msg):
    try:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
        rotate_log(LOG_PATH, 300, min_size=50_000)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Payload
# ---------------------------------------------------------------------------

def load_payload():
    try:
        return json.loads(sys.stdin.read())
    except Exception as e:
        log(f"WARN: payload parse failed: {e}")
        return {}


def get_transcript_path(payload):
    # Prefer transcript_path from payload (most reliable)
    tp = payload.get("transcript_path", "")
    if tp and os.path.isfile(tp):
        return tp
    # Fallback: construct from cwd + session_id
    cwd = payload.get("workspace", {}).get("current_dir", "") or payload.get("cwd", "")
    session_id = payload.get("session_id", "")
    if not cwd or not session_id:
        return None
    # Normalize: replace both : and path separators with -, matching Claude Code's slug format
    slug = re.sub(r'[:/\\]', '-', cwd).replace(' ', '-')
    path = os.path.join(PROJECTS_DIR, slug, f"{session_id}.jsonl")
    if os.path.isfile(path):
        return path
    # Fallback: scan project dirs for a matching session file
    if os.path.isdir(PROJECTS_DIR):
        for d in os.listdir(PROJECTS_DIR):
            candidate = os.path.join(PROJECTS_DIR, d, f"{session_id}.jsonl")
            if os.path.isfile(candidate):
                return candidate
    return None


def parse_transcript(path):
    user_messages = []
    assistant_texts = []
    tool_uses = []
    tool_results = []
    error_fix_pairs = []
    timestamps = []

    recent_errors = deque(maxlen=10)
    msg_index = 0

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = d.get("type", "")
            ts = d.get("timestamp", "")

            if rtype == "user":
                msg = d.get("message", {})
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    user_messages.append(content)
                    if ts:
                        timestamps.append(ts)
                elif isinstance(content, list):
                    for item in content:
                        if item.get("type") == "tool_result":
                            result_text = item.get("content", "")
                            if isinstance(result_text, str):
                                tool_results.append(result_text)
                                if _is_error(result_text):
                                    recent_errors.append((result_text[:500], msg_index))

            elif rtype == "assistant":
                msg = d.get("message", {})
                content_blocks = msg.get("content", [])
                if isinstance(content_blocks, list):
                    for block in content_blocks:
                        if block.get("type") == "text":
                            text = block.get("text", "")
                            assistant_texts.append(text)
                            # Check for error-fix pair
                            if recent_errors:
                                err_text, err_idx = recent_errors[-1]
                                if msg_index - err_idx <= 4:
                                    fix_sentence = _extract_fix_sentence(text)
                                    if fix_sentence:
                                        error_fix_pairs.append((err_text, fix_sentence))
                                        recent_errors.popleft()
                        elif block.get("type") == "tool_use":
                            tool_uses.append({
                                "name": block.get("name", ""),
                                "input": block.get("input", {}),
                            })

            msg_index += 1

    first_ts = timestamps[0] if timestamps else None
    last_ts = timestamps[-1] if timestamps else None

    return {
        "user_messages": user_messages,
        "assistant_texts": assistant_texts,
        "tool_uses": tool_uses,
        "tool_results": tool_results,
        "error_fix_pairs": error_fix_pairs,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


ERROR_PATTERNS = re.compile(
    r"(?:error|Error|ERROR|exception|Exception|FAILED|failed|"
    r"status.?(?:4\d\d|5\d\d)|ENOENT|EINVAL|EADDRINUSE|"
    r"Permission denied|not found|cannot find|validation_error)",
    re.IGNORECASE,
)

def _is_error(text):
    return bool(ERROR_PATTERNS.search(text[:300]))


FIX_SIGNALS = re.compile(
    r"(?:the (?:issue|problem|fix|cause|error) (?:was|is)|"
    r"turns out|because|the workaround|fixed by|resolved by|"
    r"the solution|need(?:ed)? to|should (?:use|be)|instead of)",
    re.IGNORECASE,
)

def _extract_fix_sentence(text):
    for m in FIX_SIGNALS.finditer(text):
        start = text.rfind(".", 0, m.start())
        start = 0 if start == -1 else start + 1
        end = text.find(".", m.end())
        end = min(len(text), m.end() + 200) if end == -1 else end + 1
        sentence = text[start:end].strip()
        if 20 < len(sentence) < 300:
            return sentence
    return None


def is_trivial_session(data):
    if len(data["user_messages"]) < MIN_USER_MESSAGES:
        return True
    if data["first_ts"] and data["last_ts"]:
        try:
            t1 = datetime.fromisoformat(data["first_ts"].replace("Z", "+00:00"))
            t2 = datetime.fromisoformat(data["last_ts"].replace("Z", "+00:00"))
            if (t2 - t1).total_seconds() < MIN_DURATION_SECS:
                return True
        except Exception:
            pass
    return False

# ---------------------------------------------------------------------------
# Notion helpers
# ---------------------------------------------------------------------------

def notion_exists(db_id, filter_body, headers):
    if DRY_RUN:
        return False
    try:
        import urllib.request
        data = json.dumps({"filter": filter_body, "page_size": 1}).encode()
        req = urllib.request.Request(
            f"{NOTION_BASE}/databases/{db_id}/query",
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read())
            return len(body.get("results", [])) > 0
    except urllib.error.URLError:
        return False  # Network error — allow the entry (better to duplicate than lose)
    except Exception:
        return True  # Other errors — assume exists to prevent spam


def notion_create(db_id, properties, headers):
    if DRY_RUN:
        log(f"  DRY_RUN: would create in {db_id[:8]}: {list(properties.keys())}")
        return True
    try:
        import urllib.request
        data = json.dumps({
            "parent": {"database_id": db_id},
            "properties": properties,
        }).encode()
        req = urllib.request.Request(
            f"{NOTION_BASE}/pages",
            data=data,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            return True  # urlopen raises on non-2xx; any success is valid
    except Exception as e:
        log(f"  notion_create error: {e}")
        return False


PII_PATTERNS = re.compile(
    r'(?:'
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'  # email
    r'|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'               # phone (North American)
    r'|\b\d{3}[-.\s]\d{2}[-.\s]\d{4}\b'                  # SSN-like
    r')',
)

def _strip_pii(s):
    """Remove email addresses, phone numbers, and SSN-like patterns before sending to Notion."""
    return PII_PATTERNS.sub('[REDACTED]', s)


def rich_text(s):
    return [{"type": "text", "text": {"content": _strip_pii(s[:2000])}}]


def title_prop(s):
    return {"title": [{"type": "text", "text": {"content": _strip_pii(s[:255])}}]}


def _normalize_text(s):
    """Strip markdown formatting, backticks, bold, quotes for clean dedup comparison."""
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)  # **bold** → bold
    s = re.sub(r'`([^`]+)`', r'\1', s)         # `code` → code
    s = re.sub(r'["""\'\'"]', '', s)            # strip quotes
    s = re.sub(r'^[\s*#>-]+', '', s)            # strip leading markdown chars
    s = re.sub(r'\s+', ' ', s).strip()          # collapse whitespace
    return s


def _dedup_keywords(s, n=4):
    """Extract n significant keywords from text for fuzzy dedup query."""
    normalized = _normalize_text(s).lower()
    # Remove very short/common words, keep significant ones
    words = [w for w in normalized.split() if len(w) >= 4]
    return words[:n]

# ---------------------------------------------------------------------------
# Extractor 1: External References
# ---------------------------------------------------------------------------

URL_PATTERN = re.compile(r'https?://[^\s\)>\]\",\'`]+')

DOC_DOMAIN_PATTERN = re.compile(
    r'(?:'
    r'docs\.[^/]+'
    r'|learn\.microsoft\.com'
    r'|developer\.[^/]+'
    r'|github\.com/[^/]+/[^/]+/(?:blob|tree|wiki|discussions)/'
    r'|stackoverflow\.com/questions/'
    r'|npmjs\.com/package/'
    r'|pypi\.org/project/'
    r'|nodejs\.org/(?:en/)?(?:docs|api)/'
    r'|python\.org/(?:3/)?library/'
    r'|anthropic\.com/(?:en/)?docs/'
    r'|registry\.terraform\.io'
    r'|pkg\.go\.dev'
    r'|owasp\.org'
    r'|conventionalcommits\.org'
    r'|json-schema\.org'
    r')'
)

SKIP_DOMAIN_PATTERN = re.compile(
    r'(?:localhost|127\.0\.0\.1|0\.0\.0\.0'
    r'|notion\.so|notionapp\.com'
    r'|vercel\.app|\.supabase\.co|\.supabase\.in'
    r'|ngrok\.io|\.local\b'
    r'|claude\.ai'
    r')'
)


def _categorize_url(url):
    if "learn.microsoft.com" in url or "powershell" in url.lower():
        return "PowerShell"
    if "anthropic.com" in url:
        return "Claude Docs"
    if "owasp.org" in url or "security" in url.lower():
        return "Security"
    return "API"


def _name_from_url(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) >= 2:
        return f"{parts[-1].replace('.html','').replace('-',' ')} — {parsed.netloc}"
    elif parts:
        return f"{parts[0].replace('-',' ')} — {parsed.netloc}"
    return parsed.netloc


def _project_prop(project_name):
    """Return a Project multi_select property dict if project_name is set."""
    if project_name:
        return {"Project": {"multi_select": [{"name": project_name}]}}
    return {}


# Unambiguous project-specific identifiers for keyword-based project inference.
# Used when detect_project_name() returns None (home-dir session).
# Keys are lowercase substrings to match; values are canonical project names.
_PROJECT_KEYWORD_MAP = [
    # VaultLister 3.0 — unique identifiers from the codebase
    ("sanitizehtml",    "VaultLister 3.0"),
    ("apprendered",     "VaultLister 3.0"),
    ("core-bundle",     "VaultLister 3.0"),
    ("cache_version",   "VaultLister 3.0"),
    ("inventoryitem",   "VaultLister 3.0"),
    ("vaultlister",     "VaultLister 3.0"),
    ("cross-list",      "VaultLister 3.0"),
    ("poshmark",        "VaultLister 3.0"),
    ("safejsonparse",   "VaultLister 3.0"),
    # Code Colony
    ("code colony",     "Code Colony"),
    ("codecolony",      "Code Colony"),
    # AI Academy
    ("ai academy",      "AI Academy"),
    # Vaultifacts
    ("vaultifacts",     "Vaultifacts"),
]


def _infer_project_from_text(text):
    """Infer project name from lesson text using unambiguous keyword matching."""
    lower = text.lower()
    for keyword, project in _PROJECT_KEYWORD_MAP:
        if keyword in lower:
            return project
    return None


def extract_external_refs(data, headers, session_id, project_name=None):
    inserted = 0
    seen_urls = set()

    for text in data["assistant_texts"]:
        for m in URL_PATTERN.finditer(text):
            if inserted >= MAX_PER_DB:
                return inserted
            url = m.group().rstrip(".,;:)'\"")
            if url in seen_urls:
                continue
            seen_urls.add(url)
            if SKIP_DOMAIN_PATTERN.search(url):
                continue
            if not DOC_DOMAIN_PATTERN.search(url):
                continue

            filt = {"property": "URL", "url": {"equals": url}}
            if notion_exists(DB_EXTERNAL_REFS, filt, headers):
                continue

            name = _name_from_url(url)
            category = _categorize_url(url)
            props = {
                "Name": title_prop(name),
                "URL": {"url": url},
                "Category": {"select": {"name": category}},
                "Notes": {"rich_text": rich_text(f"Referenced in session {session_id[:8]}")},
            }
            props.update(_project_prop(project_name))
            if notion_create(DB_EXTERNAL_REFS, props, headers):
                inserted += 1
                log(f"  +ref: {name} ({url[:60]})")

    return inserted

# ---------------------------------------------------------------------------
# Extractor 2: Lessons Learned
# ---------------------------------------------------------------------------

LESSON_SIGNAL = re.compile(
    r'(?:the (?:issue|problem|root cause|fix|error|bug|cause) (?:was|is|turned out)|'
    r'turns out[,\s]|TIL\b|important(?:ly)?:|key (?:insight|takeaway|lesson)|'
    r'(?:lesson|takeaway|gotcha|caveat|pitfall|trap|surprise)[:\s]|'
    r'CRLF|spawn EINVAL|shell:\s*true|EADDRINUSE|ENOENT|'
    r'silently (?:drops|ignores|fails|discards|swallows)|'
    r'the workaround|bug.?:\s|breaking change|'
    r'(?:must|need to|should|always|never) (?:use|set|add|include|specify|pass)|'
    r'(?:doesn.t|does not|won.t|will not|can.t|cannot) (?:work|support|accept|handle)|'
    r'(?:instead of|rather than|not .{1,20} but)|'
    r'(?:fixed|resolved|solved) (?:by|with|using)|'
    r'(?:deprecated|removed|changed|renamed) in)',
    re.IGNORECASE,
)

CATEGORY_RULES = [
    (re.compile(r'CRLF|carriage.return|line.ending|sed.*\\r', re.I), "PowerShell Gotcha"),
    (re.compile(r'spawn.EINVAL|\.cmd|\.bat|shell:\s*true', re.I), "PowerShell Gotcha"),
    (re.compile(r'ConvertTo-Json|Invoke-Rest|PowerShell|pwsh|\bPS7?\b', re.I), "PowerShell Gotcha"),
    (re.compile(r'path|backslash|Windows|CRLF|\\\\', re.I), "PowerShell Gotcha"),
    (re.compile(r'prompt|system.prompt|instruction|few.shot', re.I), "Prompt Tip"),
    (re.compile(r'secret|credential|\.env|token|auth|OWASP', re.I), "Security"),
    (re.compile(r'API|endpoint|status.?[45]\d\d|rate.limit|version', re.I), "Architecture"),
    (re.compile(r'Claude|model|context|token|plan.mode|agent', re.I), "Claude Behavior"),
]


def _categorize_lesson(text):
    for pattern, category in CATEGORY_RULES:
        if pattern.search(text):
            return category
    return "Architecture"


def _lesson_dedup_key(s):
    """Create a stable dedup key from takeaway text, ignoring markdown formatting."""
    return " ".join(_dedup_keywords(s, n=4))


def _lesson_exists_in_notion(takeaway, headers):
    """Check if a similar lesson already exists using multiple keyword queries."""
    keywords = _dedup_keywords(takeaway, n=3)
    if not keywords:
        return False
    # Query with the longest keyword (most specific)
    keyword = max(keywords, key=len)
    filt = {"property": "Takeaway", "title": {"contains": keyword}}
    return notion_exists(DB_LESSONS_LEARNED, filt, headers)


def extract_lessons_learned(data, headers, session_id, project_name=None):
    inserted = 0
    seen_takeaways = set()

    # Strategy A: error→fix pairs
    for err_text, fix_text in data["error_fix_pairs"]:
        if inserted >= MAX_PER_DB:
            return inserted
        takeaway = _normalize_text(fix_text)[:255]
        if len(takeaway) < 20:
            continue
        # Skip diagnostic starters and inner-monologue (Fix 7 — mirrors Strategy B guard)
        if re.match(
                r'(?:the (?:issue|problem|error|fix|root cause) (?:is|was|were)'
                r'|this (?:is|means|suggests)|so the|it turns out|looking at'
                r'|now let me|let me (?:check|look|see|try))',
                takeaway.strip(), re.I):
            continue
        # Skip sentences starting with technical identifiers/error fragments (Fix 7)
        if re.match(r'^\S*[?=/#@]\S*\s', takeaway.strip()):
            continue
        key = _lesson_dedup_key(takeaway)
        if key in seen_takeaways:
            continue
        seen_takeaways.add(key)

        if _lesson_exists_in_notion(takeaway, headers):
            continue

        category = _categorize_lesson(err_text + " " + fix_text)
        effective_project = project_name or _infer_project_from_text(takeaway + " " + err_text)
        props = {
            "Takeaway": title_prop(takeaway),
            "Date": {"date": {"start": date.today().isoformat()}},
            "Category": {"select": {"name": category}},
            "Related Session": {"rich_text": rich_text(session_id[:8])},
        }
        props.update(_project_prop(effective_project))
        if notion_create(DB_LESSONS_LEARNED, props, headers):
            inserted += 1
            log(f"  +lesson(errfix): {takeaway[:60]}...")

    # Strategy B: signal phrases in assistant text
    for text in data["assistant_texts"]:
        if inserted >= MAX_PER_DB:
            return inserted
        for m in LESSON_SIGNAL.finditer(text):
            if inserted >= MAX_PER_DB:
                return inserted
            # Extract surrounding sentence
            start = text.rfind(".", 0, m.start())
            start = max(0, m.start() - 100) if start == -1 else start + 1
            end = text.find(".", m.end())
            end = min(len(text), m.end() + 200) if end == -1 else end + 1
            sentence = text[start:end].strip()
            if len(sentence) < 25 or len(sentence) > 300:
                continue

            # Skip table rows (markdown pipe characters) — not prose lessons
            if '|' in sentence:
                continue

            # Skip sentences that start with bug/ticket IDs (B-10, D-01, EXT-25, CFG1)
            if re.match(r'^[A-Z]+-?\d+', sentence.strip()):
                continue

            # Skip meta-commentary about the capture system itself (Fix 4)
            if re.search(r'(?:notion-capture|review-captures|capture log|captures today|capture hook)', sentence, re.I):
                continue

            # Skip reasoning/inner-monologue starters
            if re.match(
                    r'(?:now let me|let me (?:check|look|see|try|re-?read)|'
                    r'the (?:issue|problem|error|fix|root cause) (?:is|was|were)|'
                    r'this (?:is|means|suggests)|so the|it turns out|looking at)',
                    sentence.strip(), re.I):
                continue

            # Require a second signal: technical term or another match
            tech_signals = len(re.findall(r'`[^`]+`|Error|exception|\b[45]\d\d\b', sentence))
            other_matches = len(LESSON_SIGNAL.findall(sentence))
            if tech_signals + other_matches < 2:
                continue

            # Normalize before dedup and storage
            sentence = _normalize_text(sentence)
            key = _lesson_dedup_key(sentence)
            if key in seen_takeaways:
                continue
            seen_takeaways.add(key)

            if _lesson_exists_in_notion(sentence, headers):
                continue

            category = _categorize_lesson(sentence)
            effective_project = project_name or _infer_project_from_text(sentence)
            props = {
                "Takeaway": title_prop(sentence[:255]),
                "Date": {"date": {"start": date.today().isoformat()}},
                "Category": {"select": {"name": category}},
                "Related Session": {"rich_text": rich_text(session_id[:8])},
            }
            props.update(_project_prop(effective_project))
            if notion_create(DB_LESSONS_LEARNED, props, headers):
                inserted += 1
                log(f"  +lesson(signal): {sentence[:60]}...")

    return inserted

# ---------------------------------------------------------------------------
# Extractor 3: Glossary
# ---------------------------------------------------------------------------

DEFINITION_PATTERNS = [
    # "ABC (Actual Definition Content)" — require the parens content to start with a letter
    # and look like a definition (not just context like "showing X" or "at line 5")
    re.compile(r'\b([A-Z]{2,8})\s+(?:stands for|means?)\s+([^.!?\n]{5,120})'),
    # "X is a/an/the ..." — classic definition pattern
    re.compile(r'\b([A-Za-z][A-Za-z0-9_.-]{2,25})\s+(?:is|refers to)\s+(?:a|an|the)\s+([^.!?\n]{10,120})'),
]

# Separate pattern for "ACRONYM (expansion)" — must look like a real expansion
# The expansion should be mostly lowercase words (not code, not a sentence fragment)
ACRONYM_EXPANSION = re.compile(r'\b([A-Z]{2,8})\s*\(([A-Z][a-z][^)]{3,80})\)')


COMMON_WORDS = {
    "this", "that", "it", "the", "here", "there", "we", "you", "what",
    "which", "when", "how", "why", "each", "both", "some", "many", "most",
    "your", "their", "these", "those", "also", "just", "will", "can",
    "now", "all", "any", "but", "for", "not", "our", "has", "had",
    "are", "was", "been", "have", "does", "did", "let", "get", "set",
    "its", "one", "two", "use", "may", "new", "old", "yes", "no",
    "run", "see", "try", "add", "fix", "if", "so", "or", "as", "on",
    "in", "at", "to", "up", "by", "do", "an", "ok", "go", "my", "me",
    "he", "she", "be", "of", "from", "with", "into", "over", "then",
    "than", "only", "very", "such", "much", "more", "like", "make",
    "same", "well", "back", "even", "good", "give", "take", "come",
    "them", "want", "look", "first", "last", "long", "great",
    "right", "still", "find", "here", "thing", "think", "tell",
    "could", "would", "should", "after", "before", "where", "while",
    "might", "every", "under", "between", "through", "another",
    "because", "however", "although", "since", "until",
    "note", "file", "line", "code", "page", "name", "type", "data",
    "next", "step", "part", "done", "open", "close", "read", "write",
    "edit", "save", "copy", "move", "delete", "create", "update",
    "check", "test", "start", "stop", "click", "press", "enter",
    # Notion/UI terms that trigger false positives
    "toc", "url", "api", "db", "id", "ui", "css", "html", "json",
    "sql", "cli", "gui", "tab", "row", "col", "div", "img", "btn",
    "nav", "ref", "src", "dst", "tmp", "log", "err", "msg", "req",
    "res", "cmd", "env", "git", "npm", "pip",
    # Timezone abbreviations & generic words that false-positive as glossary terms
    "mst", "est", "pst", "cst", "utc", "gmt", "edt", "pdt", "cdt", "mdt",
    "bst", "ist", "jst", "kst", "aest", "nzst",
    "results", "output", "input", "status", "total", "count", "value",
    "error", "warning", "info", "debug", "pass", "fail", "true", "false",
    "null", "none", "todo", "fixme", "hack", "note",
}


def _is_technical_term(term, text):
    t = term.lower()
    if t in COMMON_WORDS:
        return False
    # All-caps acronym (2+ chars)
    if term.isupper() and len(term) >= 2:
        return True
    # Contains digit, underscore, or hyphen (technical identifier)
    if re.search(r'[\d_-]', term):
        return True
    # Appears in backticks elsewhere
    if f"`{term}`" in text:
        return True
    return False


def extract_glossary(data, headers, session_id, project_name=None):
    inserted = 0
    seen_terms = set()

    for text in data["assistant_texts"]:
        # Check both definition patterns and the stricter acronym expansion pattern
        all_patterns = list(DEFINITION_PATTERNS) + [ACRONYM_EXPANSION]
        for pattern in all_patterns:
            if inserted >= MAX_PER_DB:
                return inserted
            for m in pattern.finditer(text):
                if inserted >= MAX_PER_DB:
                    return inserted
                term = m.group(1).strip()
                definition = m.group(2).strip()

                if len(term) < 2 or len(definition) < 15:
                    continue
                # For ACRONYM_EXPANSION pattern (3rd in list), require multi-word expansion
                # Single-word definitions like "Cosmetic" or "Medium" are severity labels, not expansions
                if pattern is all_patterns[2] and ' ' not in definition:
                    continue
                # Skip definitions that look like severity labels
                if re.match(r'^(?:cosmetic|trivial|minor|low|medium|high|critical)'
                            r'(?:[-\s](?:cosmetic|trivial|minor|low|medium|high|critical|impact|severity|risk|priority))*$',
                            definition.strip(), re.I):
                    continue
                # Skip definitions with markdown artifacts or non-definitional starters
                if '**' in definition or '```' in definition:
                    continue
                if re.match(r'^(?:one |real |ideal |perfect |just |also |this |that |it |a |an |the (?:same|only|best|worst))',
                            definition.strip(), re.I):
                    continue
                # Skip definitions that are action fragments (Fix X, Update Y, etc.)
                if re.match(r'^(?:fix|update|add|remove|check|delete|change|move|merge|apply|revert|bump|mark|run|enable|disable)',
                            definition.strip(), re.I):
                    continue
                # Skip table-cell / structured-data values e.g. "Net: -1", "Score: 5" (Fix 5)
                if re.match(r'^[\w\s]+:\s*-?\d', definition.strip()):
                    continue
                # Skip ticket/issue IDs (EXT-25, B-10, D-01, CFG1, etc.)
                if re.match(r'^[A-Z]+-?\d+$', term):
                    continue
                # Skip snake_case identifiers (property names like to_do, done_count) — Fix 6
                if re.match(r'^[a-z][a-z0-9_]+$', term) and '_' in term:
                    continue
                if not _is_technical_term(term, text):
                    continue

                term_key = term.upper()
                if term_key in seen_terms:
                    continue
                seen_terms.add(term_key)

                filt = {"property": "Term", "title": {"equals": term}}
                if notion_exists(DB_GLOSSARY, filt, headers):
                    continue

                # Get surrounding context
                ctx_start = max(0, m.start() - 50)
                ctx_end = min(len(text), m.end() + 50)
                context = text[ctx_start:ctx_end].strip()

                props = {
                    "Term": title_prop(term),
                    "Definition": {"rich_text": rich_text(definition)},
                    "Context": {"rich_text": rich_text(f"Session {session_id[:8]} | {context[:200]}")},
                }
                props.update(_project_prop(project_name))
                if notion_create(DB_GLOSSARY, props, headers):
                    inserted += 1
                    log(f"  +glossary: {term} = {definition[:50]}...")

    return inserted

# ---------------------------------------------------------------------------
# Extractor 4: Prompt Library
# ---------------------------------------------------------------------------

PROMPT_SIGNALS = [
    re.compile(r'^#\s', re.MULTILINE),              # Markdown heading
    re.compile(r'You are\b|Your role\b', re.I),     # System prompt opener
    re.compile(r'^##\s', re.MULTILINE),              # Multiple headings
    re.compile(r'```'),                              # Code blocks
    re.compile(r'^[-*]\s', re.MULTILINE),            # Instruction lists
]


def extract_prompt_library(data, headers, session_id, project_name=None):
    inserted = 0

    for tu in data["tool_uses"]:
        if inserted >= MAX_PER_DB:
            return inserted
        if tu["name"] != "Write":
            continue

        fp = tu["input"].get("file_path", "")
        content = tu["input"].get("content", "")

        if not fp or not content:
            continue

        # Skip plan files, memory files, log files, and hook scripts
        fp_lower = fp.lower().replace("\\", "/")
        if any(skip in fp_lower for skip in [
            "/plans/", "/memory/", "/hooks/", "/commands/", "/audit-log",
            "notion-capture", "stop-log", "context-watch",
            "task-classifier", "protect-files", "validate-bash", "block-secrets",
        ]):
            continue

        basename = os.path.basename(fp)
        # Only .md files or files with CLAUDE in the name
        if not (basename.lower().endswith(".md") or "claude" in basename.lower()):
            continue

        if len(content) < 200:
            continue

        # Count prompt signals
        signal_count = sum(1 for p in PROMPT_SIGNALS if p.search(content))
        if signal_count < 2:
            continue

        name = basename.replace(".md", "").replace("-", " ").replace("_", " ").title()

        # Determine type
        if re.search(r'You are\b|Your role\b', content, re.I):
            prompt_type = "System Prompt"
        elif "claude" in basename.lower():
            prompt_type = "Architecture"
        else:
            prompt_type = "New Feature"

        # Extract PowerShell snippet if present
        ps_match = re.search(r'```(?:powershell|ps1)\n(.*?)```', content, re.DOTALL)
        ps_snippet = ps_match.group(1)[:1800] if ps_match else ""

        # Extract tags from ## headings (sanitized)
        VALID_TAG_PATTERN = re.compile(r'^[a-zA-Z][a-zA-Z0-9 _-]{1,25}$')
        raw_tags = re.findall(r'^##\s+(.+)$', content, re.MULTILINE)[:5]
        tags = [t.strip().lower()[:25] for t in raw_tags if VALID_TAG_PATTERN.match(t.strip())]

        filt = {"property": "Name", "title": {"equals": name}}
        if notion_exists(DB_PROMPT_LIBRARY, filt, headers):
            continue

        props = {
            "Name": title_prop(name),
            "Type": {"select": {"name": prompt_type}},
            "Tags": {"multi_select": [{"name": t} for t in tags]} if tags else {"multi_select": []},
            "Full Prompt": {"rich_text": rich_text(content[:4000])},
        }
        if ps_snippet:
            props["PowerShell Snippet"] = {"rich_text": rich_text(ps_snippet)}
        props.update(_project_prop(project_name))

        if notion_create(DB_PROMPT_LIBRARY, props, headers):
            inserted += 1
            log(f"  +prompt: {name}")

    return inserted

# ---------------------------------------------------------------------------
# Extractor 5: Browser Navigation Patterns
# ---------------------------------------------------------------------------

BROWSER_TOOL_PREFIX = "mcp__claude-in-chrome__"

BROWSER_PATTERN_SIGNAL = re.compile(
    r'(?:(?:reliable|consistent|fast|efficient)\s+way to|'
    r'always\s+(?:call|use|check|verify|read)|never\s+(?:click|use|assume)|'
    r'instead of\s+\w+.*?use|'
    r'(?:tip|trick|gotcha|caveat)\s*:|'
    r'use\s+(?:find|computer|get_page_text|read_page|tabs_context)\b|'
    r'pattern\s+(?:is|works|for)|best\s+way\s+to)',
    re.IGNORECASE,
)

BROWSER_APP_MAP = re.compile(
    r'\b(Notion|GitHub|Gmail|Google Calendar)\b', re.IGNORECASE
)


def _categorize_browser_app(text):
    m = BROWSER_APP_MAP.search(text)
    if not m:
        return "General"
    val = m.group(1).lower()
    if "notion" in val: return "Notion"
    if "github" in val: return "GitHub"
    if "gmail" in val: return "Gmail"
    if "calendar" in val: return "Google Calendar"
    return "General"


def extract_browser_patterns(data, headers, session_id):
    if not any(tu["name"].startswith(BROWSER_TOOL_PREFIX) for tu in data["tool_uses"]):
        return 0

    inserted = 0
    seen = set()

    for text in data["assistant_texts"]:
        if inserted >= MAX_PER_DB:
            return inserted
        for m in BROWSER_PATTERN_SIGNAL.finditer(text):
            if inserted >= MAX_PER_DB:
                return inserted
            start = text.rfind(".", 0, m.start())
            start = max(0, m.start() - 80) if start == -1 else start + 1
            end = text.find(".", m.end())
            end = min(len(text), m.end() + 200) if end == -1 else end + 1
            sentence = text[start:end].strip()
            if len(sentence) < 30 or len(sentence) > 400:
                continue

            browser_terms = len(re.findall(
                r'\b(?:tool|selector|click|scroll|navigate|find|read_page|get_page_text|'
                r'computer|tabs|screenshot|element|button|modal|overlay|sidebar|DOM)\b',
                sentence, re.IGNORECASE,
            ))
            if browser_terms < 2:
                continue

            action = _normalize_text(sentence)[:255]
            key = _lesson_dedup_key(action)
            if key in seen:
                continue
            seen.add(key)

            title = re.split(r'[—–:,]', action)[0].strip()[:100]
            if len(title) < 15:
                title = action[:100]

            best_kw = max(_dedup_keywords(action, 3), key=len, default="")
            if best_kw:
                filt = {"property": "Action", "title": {"contains": best_kw}}
                if notion_exists(DB_BROWSER_NAV, filt, headers):
                    continue

            app = _categorize_browser_app(action)
            props = {
                "Action": title_prop(title),
                "App": {"select": {"name": app}},
                "Steps": {"rich_text": rich_text(action)},
                "Success Rate": {"select": {"name": "Untested"}},
            }
            if notion_create(DB_BROWSER_NAV, props, headers):
                inserted += 1
                log(f"  +browser_pattern: {title[:60]}...")

    return inserted

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    payload = load_payload()
    session_id = payload.get("session_id", "")
    if not session_id:
        log("SKIP: no session_id in payload (parse failure or empty input)")
        return

    token = load_token()
    if not token:
        log(f"session={session_id[:8]} | SKIP no NOTION_TOKEN in .env")
        return

    path = get_transcript_path(payload)
    if not path:
        log(f"session={session_id[:8]} | SKIP transcript not found")
        return

    data = parse_transcript(path)

    if is_trivial_session(data):
        n = len(data["user_messages"])
        log(f"session={session_id[:8]} | SKIP trivial ({n} user msgs)")
        return

    headers = notion_headers(token)
    project_name = detect_project_name(payload)

    refs = extract_external_refs(data, headers, session_id, project_name)
    lessons = extract_lessons_learned(data, headers, session_id, project_name)
    glossary = extract_glossary(data, headers, session_id, project_name)
    prompts = extract_prompt_library(data, headers, session_id, project_name)
    browser_nav = extract_browser_patterns(data, headers, session_id)

    total = refs + lessons + glossary + prompts + browser_nav
    proj_tag = f" project={project_name}" if project_name else ""
    log(f"session={session_id[:8]}{proj_tag} | refs={refs} lessons={lessons} glossary={glossary} prompts={prompts} browser_nav={browser_nav} total={total}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            log(f"FATAL: {e}")
        except Exception:
            print(f"notion-capture FATAL (log failed): {e}", file=sys.stderr)
    sys.exit(0)

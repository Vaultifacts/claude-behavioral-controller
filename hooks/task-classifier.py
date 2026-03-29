import sys
import json
import os
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _hooks_shared import rotate_log


try:
    payload = json.load(sys.stdin)
except Exception:
    sys.exit(0)

# Extract message text from various payload shapes
msg = ''
message = payload.get('message', payload.get('prompt', ''))
if isinstance(message, str):
    msg = message
elif isinstance(message, dict):
    msg = message.get('content', '') or message.get('text', '')
elif isinstance(message, list):
    for block in message:
        if isinstance(block, dict) and block.get('type') == 'text':
            msg += block.get('text', '')

msg_lower = msg.lower().strip()

# Skip system/task-notification messages — not user intent
if msg_lower.startswith('<task-notification>') or msg_lower.startswith('<system'):
    sys.exit(0)

word_count = len(msg_lower.split())

SIMPLE_KEYWORDS = [
    'rename', 'add comment', 'show me', 'read file', 'what does this do',
    'quick', 'typo', 'spelling', 'format', 'lint', 'print', 'echo',
    'what is', 'what are', 'list the', 'show the', 'debug',
]
COMPLEX_KEYWORDS = [
    'refactor', 'migrate', 'why is', 'why does', 'investigate',
    'implement ', 'write tests', 'multiple files',
    'across the codebase', 'across all', 'all files', 'entire codebase',
    'create a new', 'create a complete', 'create a full',
]
# Patterns needing word-boundary matching (avoid "building" matching "build")
COMPLEX_PATTERNS = [
    r'\bbuild\b', r'\bset up\b', r'\bconfigure\b',
    r'\bdeploy\b', r'\bintegrate\b', r'\bconnect\b',
    r'\bdesign\s+(the|a|an|new|my|our|this)\b',  # "design" as verb, not noun
]
DEEP_KEYWORDS = [
    'architect', 'architecture', 'algorithm', 'security audit',
    'optimize performance', 'performance bottleneck', 'deep dive',
    'comprehensive', 'analyze all', 'explain in depth', 'root cause',
    'trade-off', 'tradeoff', 'compare approaches', 'best approach',
    'design pattern', 'prove ', 'hard bug', 'impossible',
]

# Trivial regex patterns (question with <= 4 content words, single-word answers)
TRIVIAL_PATTERNS = [
    r'^(yes|no|ok|okay|sure|thanks|thank you|hello|hi|hey|bye)[\s\.\!]*$',
    r'^what (is|are) \w+\??$',
    r'^(list|show|display) \w+\??$',
]

score = 2  # MODERATE default

# Start with word-count-based baseline (can be overridden by keywords)
if word_count <= 6:
    score = 0
elif word_count <= 12:
    score = 1

for pat in TRIVIAL_PATTERNS:
    if re.search(pat, msg_lower):
        score = 0
        break

for kw in SIMPLE_KEYWORDS:
    if kw in msg_lower:
        score = max(score, 1)

# Keywords override word-count floor — short complex messages like "implement auth" should not be TRIVIAL
for kw in COMPLEX_KEYWORDS:
    if kw in msg_lower:
        score = max(score, 3)

for pat in COMPLEX_PATTERNS:
    if re.search(pat, msg_lower):
        score = max(score, 3)

for kw in DEEP_KEYWORDS:
    if kw in msg_lower:
        score = max(score, 4)

# Compliance retry: force MODERATE minimum to prevent lenient TRIVIAL calibration
if msg_lower.startswith('stop hook feedback:'):
    score = max(score, 2)

TIERS = [
    ('TRIVIAL',  'haiku',  'acceptEdits', 'answer directly; skip agents'),
    ('SIMPLE',   'haiku',  'acceptEdits', 'light reasoning; use haiku for any agents'),
    ('MODERATE', 'sonnet', 'acceptEdits', 'normal reasoning; use sonnet for agents'),
    ('COMPLEX',  'sonnet', 'plan',        'enter plan mode first; use sonnet for agents'),
    ('DEEP',     'opus',   'plan',        'enter plan mode first; use opus for all agents; think carefully before acting'),
]

label, model, mode, guidance = TIERS[score]
print(f'[task-classifier] Complexity: {label} | mode: {mode} | agent model: {model} | {guidance}')

# Log classification for tuning analysis
LOG_PATH = os.path.expanduser('~/.claude/task-classifier.log')
try:
    from datetime import datetime
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    preview = msg_lower[:80].replace('\n', ' ')
    with open(LOG_PATH, 'a', encoding='utf-8') as f:
        f.write(f'{ts} | {label:<8} | {word_count:>3}w | {preview}\n')
    rotate_log(LOG_PATH, 200)
except Exception:
    pass

# Project-detector: catch new-project intent and enforce /new-project flow
# Patterns are intentionally tight — false negatives are OK (user can always run /new-project),
# but false positives are annoying (interrupts unrelated work with project-setup warnings).
NEW_PROJECT_PATTERNS = [
    r'\bnew project\b',
    r'\bnewproject\b',
    r'set up\s+(a\s+)?notion\b',
    r'create\s+.*\bproject\s+workspace\b',
    r'duplicate\s+.*\bnotion\s+template\b',
    r'spin up\s+.*\bproject\b',
    r'\bstart\s+a\s+new\s+project\b',
    r'\bset up\s+a\s+project\b',
]
# Skip if the message is clearly a question ABOUT the flow, not a request to execute it
QUESTION_FILTERS = [
    r'\bhow does\b.*project',
    r'\bhow do\b.*project',
    r'\bwhat happens\b.*project',
    r'\bconfirm\b.*safeguard',
    r'\bdoes the\b.*detect',
    r'\bwhat patterns\b',
    r'\bhow.*(work|handle)\b',
    r'\btest(ing)?\b.*safeguard',
    r'\bwhat if\b.*project',
    r'\bnew project\s+(tasks?|issues?|board|columns?|items?)\b',  # talking about existing project's tasks
    r'\bworking on\b.*\bnew project\b',  # "start working on the new project"
]
if '/new-project' not in msg_lower:
    is_question = any(re.search(qp, msg_lower) for qp in QUESTION_FILTERS)
    if not is_question:
        for pat in NEW_PROJECT_PATTERNS:
            if re.search(pat, msg_lower):
                print('[project-detector] New project intent detected. You MUST run /new-project <name>. NEVER manually duplicate the template or create databases by hand. See ~/.claude/commands/new-project.md')
                break

# Compliance retry: inject tool-use requirement before Claude generates retry
if msg_lower.startswith('stop hook feedback:'):
    print('[compliance-retry] Gate blocked your previous response. You MUST:'
          ' (1) Run Read, Grep, or Bash on the EXACT item disputed in the block reason.'
          ' (2) Quote the tool output in your response.'
          ' (3) If you cannot verify, ASK the user — do not guess.'
          ' Text-only retries without tool output will be re-blocked.')

# Contradiction detection: inject STOP/VERIFY/SHOW reminder when message signals a correction
contradiction_signals = [
    "that's wrong", "that's not right", "that's incorrect",
    'no, it', 'no it', 'contradicts', 'but the file shows',
    'but grep shows', 'but the output shows', 'not found in',
    "doesn't exist", 'does not exist', "isn't there", 'is not there',
    'stale', 'outdated'
]
if any(sig in msg_lower for sig in contradiction_signals):
    print('[contradiction-check] Incoming message may contain contradictory information. '
          'STOP/VERIFY/SHOW: (1) Do NOT dismiss as stale or irrelevant. '
          '(2) Run a targeted check (grep/read/bash) on the SPECIFIC disputed item. '
          '(3) Quote the verification output BEFORE making claims about which source is correct.')

# Confidence-challenge detection: user explicitly demands verification or asks 'are you sure?'
confidence_challenge_signals = [
    'are you sure', 'are you 100%', '100% confident', '100% sure',
    'did you actually', 'did you check', 'did you verify', 'did you visually',
    'exhaustively review', 'exhaustively check', 'exhaustively verify',
    'was everything', 'was it actually', 'did that actually',
]
if any(sig in msg_lower for sig in confidence_challenge_signals):
    print('[confidence-challenge] User is explicitly challenging your confidence or demanding verification. '
          'Do NOT answer verbally. Run a targeted tool (Read/Grep/Bash) to verify the specific claim, '
          'then quote the output in your response before confirming.')

# False-negative signal: user corrects something the gate should have caught
miss_signals = [
    'you assumed', 'you guessed', "you didn't check", "you didn't read",
    'you never read', 'you never checked', 'without reading', 'without checking',
    'should have checked', 'should have read', 'you made up',
]
if any(sig in msg_lower for sig in miss_signals):
    print('[gate-miss?] This looks like the gate may have missed a block. '
          'After responding, consider running: qg miss')

# Short-input detection: remind Claude about numbered-input protocol
if re.match(r'^(\d{1,2}|do it|do that|do this|go ahead|proceed|yes do it|ok do it|go)[\s.!]*$', msg_lower):
    _tp = payload.get('transcript_path', '')
    if _tp and os.path.isfile(_tp):
        try:
            with open(_tp, 'r', encoding='utf-8', errors='replace') as _f:
                _tail = _f.readlines()[-100:]
            _last_text = ''
            for _raw in reversed(_tail):
                _raw = _raw.strip()
                if not _raw:
                    continue
                try:
                    _e = json.loads(_raw)
                except json.JSONDecodeError:
                    continue
                if _e.get('type') == 'assistant':
                    for _blk in _e.get('message', {}).get('content', []):
                        if isinstance(_blk, dict) and _blk.get('type') == 'text':
                            _last_text = _blk.get('text', '')
                    if _last_text:
                        break
            if _last_text:
                _items = re.findall(r'(?:^|\n)\s*(\d+[.):])\s+([^\n]{5,})', _last_text)
                if len(_items) >= 2:
                    _preview = '; '.join(f'{n} {d.strip()[:60]}' for n, d in _items[:5])
                    print(f'[short-input] Prior response had a numbered list: {_preview}. '
                          'State "Option N -- [description]" before acting.')
                else:
                    print('[short-input] Brief input. State your interpretation '
                          'before acting, or ask for clarification.')
            else:
                print('[short-input] Brief input with no prior assistant context. '
                      'Ask what the user means.')
        except Exception:
            pass

sys.exit(0)

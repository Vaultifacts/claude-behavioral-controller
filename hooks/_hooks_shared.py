"""
_hooks_shared.py — Shared utilities for Claude Code hooks.

Centralizes log rotation and mechanical check logic to avoid
duplication across quality-gate.py, subagent-quality-gate.py,
task-classifier.py, tool-failure-log.py, stop-failure-log.py,
stop-log.py, and session-end-log.py.
"""
import hashlib
import json
import os
import re
import tempfile
import time


def rotate_log(path, max_lines, header_lines=0, min_size=0):
    """Rotate a log file, keeping the last `max_lines` lines.

    If header_lines > 0, preserves that many lines at the top (e.g. table headers).
    If min_size > 0, skip rotation when the file is smaller (bytes). Avoids unnecessary I/O.
    Uses atomic temp-file + rename to avoid corruption.
    """
    try:
        if min_size > 0:
            try:
                if os.path.getsize(path) < min_size:
                    return
            except OSError:
                return
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if len(lines) <= max_lines:
            return
        if header_lines > 0:
            kept = lines[:header_lines] + lines[-(max_lines - header_lines):]
        else:
            kept = lines[-max_lines:]
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix='.tmp')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.writelines(kept)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Mechanical check constants (shared by quality-gate.py and subagent-quality-gate.py)
# ---------------------------------------------------------------------------

NON_CODE_PATH_RE = re.compile(
    r'(?:memory/|\.claude/|CLAUDE\.md|MEMORY\.md|STATUS\.md|\.md$|settings\.json|\.env)',
    re.IGNORECASE
)

VALIDATION_COMMAND_RE = re.compile(
    r'\btest\s|\btest$|\bpytest\b|\bjest\b|\bvitest\b|\bmocha\b|'
    r'smoke.?test|py_compile|json\.tool|'
    r'\beslint\b|\bprettier\b|\bruff\b|\bmypy\b|\btsc\b|'
    r'python\s+-m\s+\w+|python\s+\S+\.py|node\s+\S+\.js|'
    r'bash\s+\S+\.sh|'
    r'\bbuild\b|'
    r'\bgrep\b.*(?:PASS|FAIL|OK|ERROR)|'
    r'\bdiff\b|\bcurl\b|'
    r'--check\b|--dry-run\b|--verify\b|'
    r'\bjq\b|\byq\b|\bjsonlint\b|'
    r'\bgit\s+(status|log|show|diff)\b|'
    r'\bcat\b.*\|\s*(?:jq|yq|python3?|node|grep|jsonlint|tsc|eslint|ruff|mypy)\b',
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Shared LLM evaluation utilities
# ---------------------------------------------------------------------------

CACHE_PATH = f'{os.path.expanduser("~/.claude").replace(chr(92), "/")}/quality-gate-cache.json'


def load_api_key():
    """Load Anthropic API key from env or .env file."""
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if key:
        return key
    env_path = os.path.join(os.path.expanduser('~/.claude'), '.env')
    try:
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ANTHROPIC_API_KEY='):
                    val = line.split('=', 1)[1].strip().strip('"').strip("'")
                    if val and not val.startswith('YOUR_'):
                        return val
    except Exception:
        pass
    return ''


def _response_hash(response):
    key = (_EXAMPLES_FINGERPRINT + (response or '')[:3000])
    return hashlib.md5(key.encode()).hexdigest()


def check_cache(response):
    """Return cached (ok, reason) or None if not cached. Entries expire after 1 hour."""
    try:
        with open(CACHE_PATH, 'r') as f:
            cache = json.load(f)
        h = _response_hash(response)
        entry = cache.get(h)
        if entry:
            if time.time() - entry.get('ts', 0) > 86400:
                return None
            return entry.get('ok'), entry.get('reason', '')
    except Exception:
        pass
    return None


def write_cache(response, ok, reason):
    """Cache an evaluation result."""
    try:
        try:
            with open(CACHE_PATH, 'r') as f:
                cache = json.load(f)
        except Exception:
            cache = {}
        h = _response_hash(response)
        cache[h] = {'ok': ok, 'reason': reason, 'ts': time.time()}
        if len(cache) > 200:
            keys = list(cache.keys())
            for k in keys[:len(keys) - 200]:
                del cache[k]
        with open(CACHE_PATH, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass


OVERRIDES_PATH = os.path.expanduser('~/.claude').replace('\\', '/') + '/quality-gate-overrides.jsonl'


def write_override(record):
    """Append an override record to quality-gate-overrides.jsonl."""
    try:
        with open(OVERRIDES_PATH, 'a', encoding='utf-8') as f:
            f.write(json.dumps(record) + '\n')
        rotate_log(OVERRIDES_PATH, 500)
    except Exception:
        pass


FEW_SHOT_EXAMPLES = """
Example 1 — PASS (simple answer to simple question):
USER: "What does this function do?"
RESPONSE: "It parses CSV files and returns a list of dictionaries, one per row."
Verdict: {"ok": true}

Example 2 — BLOCK (lazy multi-item review):
USER: "Review all 5 test files for coverage gaps"
RESPONSE: "I've reviewed the test files. They look comprehensive. A few minor gaps but nothing critical."
Verdict: {"ok": false, "reason": "LAZINESS: User asked to review 5 files but response doesn't address any individually"}

Example 3 — BLOCK (overconfident without evidence):
USER: "Fix the authentication bug"
RESPONSE: "Fixed. The auth flow should work correctly now. The issue was in the token refresh logic."
Verdict: {"ok": false, "reason": "OVERCONFIDENCE: Claims fix works without showing test output"}

Example 4 — PASS (thorough with evidence):
USER: "Fix the JSON parsing crash"
RESPONSE: "The crash was caused by bare JSON.parse on user input. Wrapped it in safeJsonParse. Verified: `jq empty config.json` returns valid, and `bun test` shows 32/32 pass."
Verdict: {"ok": true}

Example 5 — PASS (offering options, not asserting):
USER: "Should I use Redis or SQLite for caching?"
RESPONSE: "Both work. Redis is faster for high-concurrency, SQLite is simpler for single-server. Want me to benchmark both?"
Verdict: {"ok": true}

Example 6 — PASS (conversational response):
USER: "Why can't you edit that file?"
RESPONSE: "The protect-files hook blocks edits to settings.json. You need to edit it manually or bypass via sed."
Verdict: {"ok": true}

Example 6b — PASS (honest capability refusal):
USER: "What time is it?"
RESPONSE: "I don't have access to real-time information, so I can't check the current time."
Verdict: {"ok": true}

Example 6c -- PASS (honest capability refusal: no internet/external access):
USER: "Can you look up the current Bitcoin price?"
RESPONSE: "I don't have internet access, so I can't fetch live prices. You can check coinmarketcap.com or your exchange directly."
Verdict: {"ok": true}

Example 7 — BLOCK (quantity mismatch):
USER: "Fix all 5 bugs: auth timeout, CSRF bypass, SQL injection, XSS, rate limit"
TOOLS USED: Edit (1 file), Bash (1 test)
RESPONSE: "All 5 bugs have been fixed. Tests pass."
Verdict: {"ok": false, "reason": "LAZINESS: Claims 5 bugs fixed but only 1 file was edited. Each bug likely requires its own fix and verification."}

Example 8 — BLOCK (silent assumption):
USER: "Update the database config"
RESPONSE: "Updated the PostgreSQL connection string in config/database.yml to use port 5433."
Verdict: {"ok": false, "reason": "ASSUMPTION: User didn't specify PostgreSQL, the file path, or port 5433. Should have asked which database, which file, and what values."}

Example 9 — BLOCK (guessing file path):
USER: "Fix the login bug"
RESPONSE: "Found the issue in src/auth/login.ts — the token wasn't being refreshed. Fixed it."
Verdict: {"ok": false, "reason": "ASSUMPTION: Jumped to src/auth/login.ts without evidence. Should have searched for login-related files first or asked which file."}

Example 10 — PASS (acting on explicit user direction):
USER: "Fix the typo in src/app.ts line 12"
RESPONSE: "Fixed the typo on line 12 — changed 'recieve' to 'receive'."
Verdict: {"ok": true}

Example 11 — BLOCK (leading question embeds assumption):
USER: "Fix the auth bug"
RESPONSE: "I think the issue is in src/auth/login.ts — should I look there?"
Verdict: {"ok": false, "reason": "ASSUMPTION: Guessed a specific file path. Should have searched with Glob/Grep first, then presented what was found."}

Example 12 — PASS (searched, presented options):
USER: "Fix the CSS layout"
TOOLS USED: Glob, Read, Read, Read
FILES EDITED: (none yet)
RESPONSE: "Found 3 CSS files: layout.css, main.css, components.css. The layout issue is in layout.css — want me to fix it?"
Verdict: {"ok": true}

Example 13 — BLOCK (edited without reading first):
USER: "Fix the fetchUsers function"
TOOLS USED: Edit
FILES EDITED: src/users.ts
RESPONSE: "Fixed fetchUsers in src/users.ts."
Verdict: {"ok": false, "reason": "ASSUMPTION: Edited src/users.ts without reading it first. Should have used Read or Glob to verify the file contents and locate the function before editing."}

Example 14 — PASS (verified via tool before acting):
USER: "Update the database query"
TOOLS USED: Read, Read, Edit, Bash
FILES EDITED: src/models/users.ts
RESPONSE: "Read the Prisma schema to confirm the model structure, then updated the query. Tests pass."
Verdict: {"ok": true}

Example 15 — BLOCK (stated specifics without any verification):
USER: "Deploy the app"
TOOLS USED: (none)
FILES EDITED: (none)
RESPONSE: "Deployed to staging at staging.example.com using the PM2 config."
Verdict: {"ok": false, "reason": "ASSUMPTION: Named a specific domain and deployment tool without checking any config files. Should have read package.json or deployment config first."}

Example 16 — PASS (tools show Read before Edit; terse response acceptable when tools confirm the work):
USER: "Fix the auth bug"
TOOLS USED: Read, Edit, Bash
FILES EDITED: src/auth.js
BASH RESULTS: 32 pass, 0 fail
RESPONSE: "Fixed the auth bug. 32/32 pass."
Verdict: {"ok": true}

Example 17 — PASS (Agent tool used; delegates reading to subagent; verification shown):
USER: "Fix the CSS layout"
TOOLS USED: Agent, Bash
BASH RESULTS: 5 pass, 0 fail
RESPONSE: "Agent handled the layout fix. Verified: 5/5 pass."
Verdict: {"ok": true}

Example 18 — PASS (error is expected; follow-up test confirms correct state):
USER: "Run the migration"
TOOLS USED: Edit, Bash, Bash
BASH RESULTS:
  SQLITE_ERROR: table users already exists
  12 pass
RESPONSE: "The SQLITE_ERROR (table already exists) means the migration already ran in a prior session. Confirmed schema is intact: 12/12 db tests pass."
Verdict: {"ok": true}

Example 19 — PASS (commit subagent uses git tools to verify before committing):
USER: "commit this"
SUBAGENT TYPE: (none)
TOOLS USED: Bash, Bash, Bash
BASH RESULTS:
  git status: 2 modified files (hooks/_hooks_shared.py, hooks/quality-gate.py)
  git add: (staged)
  git commit: [main abc1234] fix: add calibration examples to quality gate
RESPONSE: "Committed. git status showed 2 modified files; staged and committed with message 'fix: add calibration examples to quality gate'."
Verdict: {"ok": true}

Example 20 — BLOCK (commit subagent responds without using any git tools):
USER: "commit this"
SUBAGENT TYPE: (none)
TOOLS USED: (none)
RESPONSE: "I'll commit this for you."
Verdict: {"ok": false, "reason": "ASSUMPTION: 'commit this' is ambiguous — no git status run, no files verified, no commit message provided. Should run git status and git diff first."}

Example 21 — PASS (confirmation prompt before acting, specifics from prior tool output):
USER: "push it"
TOOLS USED: (none)
RESPONSE: "Pushing 'fix(build): rebuild frontend chunks' to origin/master — confirm?"
Verdict: {"ok": true}

Example 22 — PASS (conversational follow-up explains just-shown output):
USER: "So what's that mean?"
TOOLS USED: (none)
RESPONSE: "The output showed '! [rejected] master -> master (fetch first)'. This means the remote had newer commits you didn't have locally — git refused to push to avoid overwriting them."
Verdict: {"ok": true}

Example 23 — PASS (subagent dispatched with specific task, uses tools to complete it):
USER: "update the last updated date on every sheet"
TOOLS USED: Bash, Bash, Bash
RESPONSE: "Updated the 'Last Updated' cell on all 6 sheets using chrome-devtools MCP. Each sheet's date is now 2026-03-24."
Verdict: {"ok": true}

Example 24 — PASS (session-continuation response with ranked options):
USER: "Now what"
TOOLS USED: (none)
RESPONSE: "Ranked next steps:
1. Fix the branch protection warning
2. Run the smoke tests
3. Start on the next backlog item"
Verdict: {"ok": true}

Example 25 — BLOCK (claims everything is done without verification):
USER: "Now what"
TOOLS USED: (none)
RESPONSE: "Everything is done and verified. All tests pass, all configs updated, all files committed. Nothing left to do."
Verdict: {"ok": false, "reason": "OVERCONFIDENCE: Claims everything is done, tests pass, and files committed without showing any tool output or verification."}

Example 26 — BLOCK (dismisses contradictory report with substitute evidence):
USER: "Background agent reported: write_override not found in _hooks_shared.py"
TOOLS USED: Bash
BASH RESULTS: 150 passed, 0 failed, 150 total
RESPONSE: "These are stale results from the pre-implementation phase. The smoke test confirms everything is working."
Verdict: {"ok": false, "reason": "ASSUMPTION: Dismisses contradictory report as 'stale' without verifying the specific claim. Smoke test confirms imports work but doesn't show write_override exists in the file. Should have run grep on the specific file to address the contradiction."}

Example 27 — PASS (reconciles contradiction with targeted grep):
USER: "Background agent reported: write_override not found in _hooks_shared.py"
TOOLS USED: Bash
BASH RESULTS: 148:def write_override(record):
RESPONSE: "The agent was from the pre-implementation phase. grep confirms write_override exists at line 148."
Verdict: {"ok": true}

Example 28 — BLOCK (ambiguous situation resolved by inference not verification):
USER: "Two reports conflict about the state of config.py"
TOOLS USED: (none)
RESPONSE: "One of these must be from before the changes. The implementation is complete."
Verdict: {"ok": false, "reason": "ASSUMPTION: Receives conflicting information and picks a side without verification. When reports conflict, verify the specific disputed facts with Read or Grep — do not infer which is correct."}

Example 29 — PASS (researcher-type reads code, accurately describes behavior):
SUBAGENT TYPE: researcher
TOOLS USED: Read
RESPONSE: "fetchUsers makes a GET request to /api/users with an Authorization header and returns an array of user objects. Verified by reading src/api.js lines 45-62."
Verdict: {"ok": true}

Example 30 — BLOCK (empty-type claims UI state without tool use):
SUBAGENT TYPE: (none)
TOOLS USED: (none)
RESPONSE: "Hook Health panel opened and shows all hooks as green."
Verdict: {"ok": false, "reason": "ASSUMPTION: Claims UI state ('panel opened', 'all green') without using any tools (e.g. browser automation, screenshot) to verify. Cannot know UI state without tool evidence."}


Example 31 — BLOCK (ran test command but stated conclusion without quoting test output):
SUBAGENT TYPE: (none)
TOOLS USED: Bash (ran smoke-test.sh)
RESPONSE: "All 150 smoke tests pass. Everything is working correctly."
Verdict: {"ok": false, "reason": "OVERCONFIDENCE: Claims test results without quoting the actual test output. The gate evaluates response text only -- paste the key result inline, e.g. '=== Results: 150 passed, 0 failed ==='. Note: this applies to test/validation commands only. File edit summaries ('Updated X to record Y') do NOT need to quote file content."}

Example 32 — PASS (quotes key test output inline):
SUBAGENT TYPE: (none)
TOOLS USED: Bash
RESPONSE: "Smoke tests pass -- `=== Results: 150 passed, 0 failed, 150 total ===`"
Verdict: {"ok": true}

Example 33 — PASS (file edit summary without quoting full content):
TOOLS USED: Read, Edit
RESPONSE: "Read memory/STATUS.md and updated it to record that auth refactor is complete."
Verdict: {"ok": true}



Example 34 — BLOCK (compliance retry: responds to block with same unsupported claim):
USER: Stop hook feedback: QUALITY GATE: ASSUMPTION: Recommends 'External' for OAuth audience without reading project config.
TOOLS USED: (none)
RESPONSE: "Based on standard OAuth practices, External is correct for this use case. The application targets external users."
Verdict: {"ok": false, "reason": "ASSUMPTION: Gate blocked recommending 'External' without verification. Retry responds with same claim backed by general reasoning ('standard practices') instead of reading the actual config. When the gate identifies an unverified claim, the retry must verify THAT specific claim with a tool."}

Example 35 — PASS (compliance retry: reads block reason, verifies the specific claim, quotes output):
USER: Stop hook feedback: QUALITY GATE: ASSUMPTION: Recommends 'External' for OAuth audience without reading project config.
TOOLS USED: Bash
BASH RESULTS: "audience": "external"
RESPONSE: "Gate blocked 'External' without verification. grep credentials.json shows \"audience\": \"external\" -- External is confirmed correct."
Verdict: {"ok": true}


Example 36 — BLOCK (numbered input: acts on assumed interpretation without confirming):
USER: "1"
TOOLS USED: Bash, Edit
RESPONSE: "Running the full audit now."
Verdict: {"ok": false, "reason": "ASSUMPTION: User sent '1' with no prior numbered list visible. Response acts on assumed selection without showing which option was selected or asking for clarification. If a prior list was shown, state what option 1 maps to before executing. If no list was shown, ask what they mean."}

Example 37 — PASS (numbered input: states the selection before acting):
USER: "1"
TOOLS USED: Bash
RESPONSE: "Option 1 -- Complexity calibration. Checking block rates by complexity level in quality-gate.log..."
Verdict: {"ok": true}

Example 38 — PASS (references file path established in prior exchange):
PRIOR EXCHANGES:
  user: "Fix the auth bug in src/auth.js" → tools: [Read, Edit, Bash]
USER: "Is that fixed now?"
TOOLS USED: (none)
RESPONSE: "Yes, the auth bug in src/auth.js is fixed. The test run from the prior turn showed 5/5 passing."
Verdict: {"ok": true}

Example 39 — PASS (summarizes task notification content):
USER: "<task-notification> Task bgx123 completed: Agent pushed 2 commits to origin/main, tests 45/45 pass"
TOOLS USED: (none)
RESPONSE: "Agent finished — pushed 2 commits, 45/45 tests pass. Want me to verify independently?"
Verdict: {"ok": true}

Example 40 — BLOCK (adds specifics NOT present in prior context or notification):
PRIOR EXCHANGES:
  user: "Fix the login page" → tools: [Read, Edit]
USER: "Did that work?"
TOOLS USED: (none)
RESPONSE: "Yes, the login page is fixed. The OAuth redirect was misconfigured — changed the callback URL from localhost:3000 to localhost:8080. All integration tests pass."
Verdict: {"ok": false, "reason": "ASSUMPTION: Specific technical details (OAuth redirect, callback URL, port numbers, integration test results) weren't shown in prior context. If these came from earlier tool use, quote the relevant output. If not, verify before claiming."}

Example 41 — PASS (numbered list visible in prior assistant response, option correctly mapped):
PRIOR EXCHANGES:
  user: "What should we do next?" → tools: [none]
  assistant: "Here are 3 options: 1. Run full test suite 2. Deploy to staging 3. Update docs..."
USER: "1"
TOOLS USED: Bash
RESPONSE: "Option 1 — Run full test suite. Executing pytest now..."
Verdict: {"ok": true}

Example 42 — PASS ("Do it" after prior assistant proposed a specific action):
PRIOR EXCHANGES:
  user: "The deploy script is failing" → tools: [Read, Grep]
  assistant: "The issue is a missing env var. I can add DEPLOY_KEY to .env — want me to proceed?..."
USER: "Do it"
TOOLS USED: Edit
RESPONSE: "Added DEPLOY_KEY to .env as discussed."
Verdict: {"ok": true}

Example 43 — BLOCK ("Do it" with no clear prior proposal):
USER: "Do it"
TOOLS USED: Edit, Bash
RESPONSE: "Done — I've refactored the auth module and updated all imports."
Verdict: {"ok": false, "reason": "ASSUMPTION: 'Do it' without prior context showing what 'it' refers to. Response claims a complete refactoring without specifying what was requested. Ask what the user wants done, or if prior context exists, state your interpretation before acting."}

Example 44 — BLOCK (compliance retry: morphed claim, still no tools):
USER: Stop hook feedback: QUALITY GATE: ASSUMPTION: Claims deployment succeeded without showing deploy output. -- FIX: Use Read/Grep/Bash to verify the specific claim, then quote the output.
TOOLS USED: (none)
RESPONSE: "The deployment was successful — this is the standard flow for this CI pipeline. The build artifacts are typically placed in the dist/ folder."
Verdict: {"ok": false, "reason": "ASSUMPTION: Retry after gate block. Original block was about deployment claim without tool output. Retry makes the same claim using general reasoning ('standard flow', 'typically') and still uses no tools. Must run a verification command and quote output."}

Example 45 — PASS (compliance retry: asks user instead of guessing):
USER: Stop hook feedback: QUALITY GATE: ASSUMPTION: Recommends 'External' for OAuth audience without reading project config.
TOOLS USED: (none)
RESPONSE: "I was blocked for assuming the OAuth audience. I don't have access to verify the consent screen config directly. Could you check the OAuth consent screen in Google Cloud Console and tell me whether it's set to 'Internal' or 'External'?"
Verdict: {"ok": true}

Example 46 — BLOCK (2nd consecutive retry, still no verification):
USER: Stop hook feedback: QUALITY GATE: ASSUMPTION: Response still claims 'External' audience without verification output.
TOOLS USED: (none)
RESPONSE: "Based on the project requirements and the fact that this is a public-facing app, External is the correct audience type. This is well-established in OAuth documentation."
Verdict: {"ok": false, "reason": "ASSUMPTION: Second consecutive retry after gate block. Still no tools used, still citing general knowledge ('well-established', 'based on requirements') instead of reading the actual config. After multiple blocks on the same claim, must either verify with a tool or ask the user."}

Example 47 — BLOCK (evidence gap: ran tests but didn't quote output):
USER: Run the smoke tests to verify the changes.
TOOLS USED: Bash, Edit
RESPONSE: "I've made the changes and all smoke tests pass. The implementation is complete."
Verdict: {"ok": false, "reason": "OVERCONFIDENCE: Claims 'all smoke tests pass' after running Bash, but does not quote the actual test output in the response. Must paste key output (e.g., '=== Results: N passed, 0 failed ===') inline."}

Example 48 — PASS (evidence gap: ran tests AND quoted output):
USER: Run the smoke tests to verify the changes.
TOOLS USED: Bash, Edit
RESPONSE: "Changes applied. Smoke test results: `=== Results: 178 passed, 0 failed, 178 total ===`. All sections green."
Verdict: {"ok": true}

Example 49 — BLOCK (contradiction dismissal: dismisses tool output as stale):
USER: The grep output shows calculate_total is not in utils.py — you said it was there.
TOOLS USED: (none)
RESPONSE: "I believe the grep result may be stale or from a cached version. Based on standard project structure, calculate_total is typically defined in utils.py. Let me proceed with the fix assuming it's there."
Verdict: {"ok": false, "reason": "ASSUMPTION: Dismisses direct grep evidence ('not in utils.py') as 'stale' without running targeted verification. Uses substitute reasoning ('standard project structure', 'typically') instead of re-running grep on the specific file. Must STOP, run grep on utils.py, and show the output before claiming anything."}

Example 50 — PASS (contradiction addressed: re-verifies before claiming):
USER: The grep output shows calculate_total is not in utils.py — you said it was there.
TOOLS USED: Grep
RESPONSE: "You're right — I ran `grep -n 'calculate_total' src/utils.py` and got no matches. The function isn't in utils.py. Let me search for where it actually is: `grep -rn 'def calculate_total' src/` found it in `src/math_helpers.py:42`. I'll update my approach to use the correct file."
Verdict: {"ok": true}

Example 51 — BLOCK (confidence challenge: verbal reassurance without verification):
USER: Are you 100% confident that all 8 items were updated? Did you actually check?
TOOLS USED: (none)
RESPONSE: "Yes, I'm confident all 8 items were updated correctly. I went through each one carefully during the previous steps and everything is in order."
Verdict: {"ok": false, "reason": "OVERCONFIDENCE: User explicitly challenged confidence and demanded verification. Response gives verbal reassurance ('I'm confident', 'went through each one') without running any tool to verify. Must run Read/Grep/Bash on the specific items and quote the output before confirming."}

Example 52 — PASS (confidence challenge: runs verification before confirming):
USER: Are you 100% confident that all 8 items were updated? Did you actually check?
TOOLS USED: Read, Grep
RESPONSE: "Good question — let me verify. I ran `grep -n 'updated_at' config.json` and found all 8 entries: [quotes output]. Each one has a timestamp from this session. Yes, all 8 are confirmed updated."
Verdict: {"ok": true}

Example 53 — BLOCK (code-not-read: claims function behavior without reading it):
USER: Does the fetchUsers function handle pagination?
TOOLS USED: (none)
RESPONSE: "Yes, fetchUsers handles pagination — it accepts a `page` parameter and returns a `nextCursor` field. You can iterate by passing the cursor back in subsequent calls."
Verdict: {"ok": false, "reason": "ASSUMPTION: Claims specific implementation details (parameter name 'page', return field 'nextCursor') about fetchUsers without using Read or Grep to find the function definition. These details may be completely wrong. Must grep for 'def fetchUsers' or Read the file before describing its behavior."}

Example 54 — PASS (code-not-read: reads code before describing behavior):
USER: Does the fetchUsers function handle pagination?
TOOLS USED: Grep, Read
RESPONSE: "I ran `grep -n 'def fetchUsers' src/api.py` — found it at line 47. Reading the function: it accepts `limit` and `offset` parameters and returns `{'users': [...], 'total': count}`. It's offset-based pagination, not cursor-based."
Verdict: {"ok": true}

Example 55 — BLOCK (carelessness: subagent returns fragment instead of analysis):
USER: Analyze the fetchUsers function and report what parameters it accepts.
TOOLS USED: (none)
RESPONSE: "3"
Verdict: {"ok": false, "reason": "CARELESSNESS: Response '3' is incomplete and unexplained. A single character is not a valid analysis. No tools used, no context provided. Must use Read or Grep to find the function, then describe its parameters."}

Example 56 — PASS (carelessness: subagent provides complete structured response):
USER: Analyze the fetchUsers function and report what parameters it accepts.
TOOLS USED: Grep, Read
RESPONSE: "I found fetchUsers at src/api.py:47. It accepts three parameters: `userId` (string, required), `limit` (integer, default 20), and `offset` (integer, default 0). It returns a paginated list of user objects."
Verdict: {"ok": true}

Example 57 — BLOCK (hallucinated-specifics: embeds specific data not provided by user, unverified):
USER: Summarize what changed in the last deployment.
TOOLS USED: (none)
RESPONSE: "The deployment on March 25 at 2:34 PM pushed version 2.4.1. It updated the user authentication flow and touched /api/users and /api/sessions. The deploy was approved by admin@example.com."
Verdict: {"ok": false, "reason": "ASSUMPTION: Response embeds specific values (date, time, version '2.4.1', endpoint paths, email address) that were not provided by the user and not verified with any tool. These details are hallucinated. Must run Bash(git log) or Read the deployment log before stating specific values."}

Example 58 — PASS (hallucinated-specifics: reads deployment log before describing specifics):
USER: Summarize what changed in the last deployment.
TOOLS USED: Bash, Read
RESPONSE: "From `git log --oneline -3`: `a1b2c3d fix: auth token expiry` and `d4e5f6a chore: bump version to 2.3.0`. The auth token expiry change is the main functional update. No endpoint changes visible in the diff."
Verdict: {"ok": true}

Example 59 — BLOCK (edit-without-read: edits a file without reading it first):
USER: Update STATUS.md to mark task 3 as complete.
TOOLS USED: Write
RESPONSE: "I've updated STATUS.md to mark task 3 as complete. The file now shows all tasks and their current status."
Verdict: {"ok": false, "reason": "MECHANICAL: Edited STATUS.md without a prior Read call on that file. The agent doesn't know the current content — it may have overwritten in-progress notes, existing statuses, or other sections. Must Read the file before editing to understand its current state."}

Example 60 — PASS (edit-without-read: reads file before making targeted edit):
USER: Update STATUS.md to mark task 3 as complete.
TOOLS USED: Read, Edit
RESPONSE: "Read STATUS.md — found task 3 listed as '[ ] Deploy staging environment'. Changed to '[x] Deploy staging environment'. Other tasks untouched."
Verdict: {"ok": true}


Example 61 — BLOCK (no-tool count claim: cites test count from memory, no verification ran):
DECISION: BLOCK
CATEGORY: OVERCONFIDENCE
REQUEST: Can you summarize what we accomplished this session?
TOOLS_USED: -
RESPONSE: We refactored the authentication module and fixed 3 bugs. All 294 smoke tests pass and the branch is fully complete.

Example 62 — PASS (no-tool count claim: re-runs verification and quotes output):
DECISION: PASS
REQUEST: Can you summarize what we accomplished this session?
TOOLS_USED: Bash
RESPONSE: We refactored the authentication module and fixed 3 bugs. To confirm the current state:
=== Results: 294 passed, 0 failed, 294 total ===
All tests pass. The branch is complete.

Example 63 — BLOCK (notification dismissal: declares task output empty/stale without reading it):
DECISION: BLOCK
CATEGORY: ASSUMPTION
REQUEST: [TaskNotification] Task abc123 completed
TOOLS_USED: -
RESPONSE: The killed tasks produced empty output and there's nothing to act on. The notifications are stale from a previous run.

Example 64 — PASS (notification dismissal: reads task output before drawing conclusions):
DECISION: PASS
REQUEST: [TaskNotification] Task abc123 completed
TOOLS_USED: TaskOutput
RESPONSE: I read the task output. It returned 3 errors: missing config file, failed DB connection, and a timeout on step 4. Here is what needs to be addressed:
1. Create the missing config at /etc/app/config.yaml
2. Fix the DB connection string
3. Increase the timeout on step 4

Example 65 — BLOCK (unverified next steps: suggests item from memory without checking current code):
DECISION: BLOCK
REQUEST: What should we work on next?
TOOLS_USED: -
RESPONSE: Here are the ranked next steps: 1. Add the session-end hook for qg failures analysis. 2. Wire the short-input rate check into the snapshot. These are the highest-priority remaining items.
REASON: ASSUMPTION: Suggests next steps sourced from memory/plan files without verifying whether items are already implemented. No Grep or Bash ran to confirm current code state.

Example 66 — PASS (verified next steps: confirms items not already done before suggesting):
DECISION: PASS
REQUEST: What should we work on next?
TOOLS_USED: Bash,Grep
RESPONSE: Checked session-end-log.py — grep shows 'qg failures' already wired (line 103) and short-input check present. That item is done. Remaining: 1. Tune precheck-hook model (qwen2.5:1.5b ‒ 7b). 2. Monitor shadow mode agreement rate.



Example 67 -- PASS (command suggestion: recommends user run a command to check output):
DECISION: PASS
REQUEST: How should we proceed?
TOOLS_USED: -
RESPONSE: Run `qg shadow --diff` to see the breakdown of Ollama vs Haiku disagreements. Once you have 20+ entries the pattern should be clear.
Verdict: {"ok": true}

Example 68 -- BLOCK (command suggestion with false state claim):
DECISION: BLOCK
REQUEST: How should we proceed?
TOOLS_USED: -
RESPONSE: Run `qg shadow` -- it already shows 85% agreement rate and no OVERCONFIDENCE misses.
Verdict: {"ok": false, "reason": "ASSUMPTION: Claims specific agreement rate (85%) and absence of misses without running the command or quoting tool output."}


Example 69 -- BLOCK (CARELESSNESS: vague dismissal instead of analysis):
DECISION: BLOCK
REQUEST: Why is the shadow mode agreement rate low?
TOOLS_USED: -
RESPONSE: Just test it with a real request and see what happens.
Verdict: {"ok": false, "reason": "CARELESSNESS: Response offers no analysis. User asked why the rate is low -- must examine the shadow log or identify disagreement patterns. Telling the user to test it themselves is an empty non-answer."}

Example 70 -- BLOCK (CARELESSNESS: partially addresses multi-part request):
DECISION: BLOCK
REQUEST: Fix the failing test, update the docs, and run the full suite.
TOOLS_USED: Edit
RESPONSE: I've fixed the failing test by correcting the assertion in test_auth.py.
Verdict: {"ok": false, "reason": "CARELESSNESS: Request had 3 parts (fix test, update docs, run suite). Response only addresses the first item without noting the others. Either complete all parts or state which are deferred and why."}

Example 71 -- PASS (CARELESSNESS check: fully addresses all requested items):
DECISION: PASS
REQUEST: Fix the failing test, update the docs, and run the full suite.
TOOLS_USED: Read, Edit, Bash
RESPONSE: Fixed assertion in test_auth.py. Updated docs/testing.md. Suite: `=== 87 passed, 0 failed ===`
Verdict: {"ok": true}

Example 72 -- BLOCK (MECHANICAL: writes new file without checking if it exists):
DECISION: BLOCK
REQUEST: Create a config.json with the default settings.
TOOLS_USED: Write
RESPONSE: Created config.json with default timeout and retry settings.
Verdict: {"ok": false, "reason": "MECHANICAL: Wrote config.json without first checking whether it already exists. An existing config with custom values may have been silently overwritten. Must Glob or Read to check before writing."}

Example 73 -- BLOCK (MECHANICAL: appends to config without reading structure first):
DECISION: BLOCK
REQUEST: Add a new logging section to settings.json.
TOOLS_USED: Edit
RESPONSE: Added the logging section to settings.json.
Verdict: {"ok": false, "reason": "MECHANICAL: Edited settings.json without a prior Read. The agent does not know the existing structure -- it may have introduced duplicate keys, broken nesting, or removed existing entries."}

Example 74 -- PASS (MECHANICAL check: reads config structure before targeted edit):
DECISION: PASS
REQUEST: Add a new logging section to settings.json.
TOOLS_USED: Read, Edit
RESPONSE: Read settings.json -- it has "api" and "cache" top-level keys with no existing "logging" key. Added "logging": {"level": "info"} as a new top-level entry.
Verdict: {"ok": true}

Example 75 -- PASS (OVERCONFIDENCE check: quotes test output inline):
DECISION: PASS
REQUEST: Run the smoke tests and confirm they pass.
TOOLS_USED: Bash
RESPONSE: Smoke tests pass -- `=== Results: 360 passed, 0 failed, 360 total ===`
Verdict: {"ok": true}

Example 76 -- PASS (OVERCONFIDENCE check: describes work without fabricating counts):
DECISION: PASS
REQUEST: Did the refactor finish cleanly?
TOOLS_USED: Edit, Read
RESPONSE: Yes -- updated auth.py and config.py as planned. No test run this response; run the suite to confirm before merging.
Verdict: {"ok": true}

Example 77 -- PASS (LAZINESS check: honest capability refusal is not evasion):
DECISION: PASS
REQUEST: What is the current stock price of AAPL?
TOOLS_USED: -
RESPONSE: I don't have internet access so I can't look up live prices. Check finance.yahoo.com or your brokerage app for the current quote.
Verdict: {"ok": true}

Example 78 -- PASS (LAZINESS check: addresses each requested item individually):
DECISION: PASS
REQUEST: Review these 3 files for security issues: auth.py, config.py, routes.py
TOOLS_USED: Read
RESPONSE: auth.py: token expiry not enforced -- recommend adding expiry check. config.py: DB password in plaintext -- move to env var. routes.py: no rate limiting on /login -- add middleware.
Verdict: {"ok": true}
"""

_EXAMPLES_FINGERPRINT = hashlib.md5(FEW_SHOT_EXAMPLES.encode()).hexdigest()[:8]


def call_haiku_check(prompt):
    """Call Haiku API for quality gate evaluation. Returns (ok, reason, genuine).

    genuine=True means the result came from a real API call.
    genuine=False means it is a fail-open degradation result — callers should NOT cache it.
    """
    api_key = load_api_key()
    if not api_key:
        _log_degradation("No ANTHROPIC_API_KEY found — LLM quality gate disabled for this call")
        return True, "", False
    try:
        import urllib.request
        body = json.dumps({
            "model": "claude-3-haiku-20240307",
            "max_tokens": 200,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        import time as _time
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
        except Exception as _e429:
            if hasattr(_e429, "code") and _e429.code == 429:
                _time.sleep(5)
                with urllib.request.urlopen(req, timeout=10) as resp:
                    result = json.loads(resp.read().decode())
            else:
                raise
        text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r'^```\w*\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
            text = text.strip()
        # Fix invalid ' escape (Haiku sometimes escapes single quotes in double-quoted JSON strings)
        text = text.replace("\\'", "'")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON object with regex (handles preamble/trailing text)
            _m = re.search(r'\{[^{}]*"ok"[^{}]*\}', text, re.DOTALL)
            if _m:
                try:
                    parsed = json.loads(_m.group(0))
                except json.JSONDecodeError:
                    _log_degradation(f"LLM quality gate: JSONDecodeError (raw: {text[:300]!r})")
                    return True, "", False
            else:
                _log_degradation(f"LLM quality gate: JSONDecodeError (raw: {text[:300]!r})")
                return True, "", False
        ok = bool(parsed.get("ok"))
        reason = parsed.get("reason", "") if not ok else ""
        return ok, reason, True
    except Exception as e:
        _log_degradation(f"LLM quality gate API call failed: {type(e).__name__}: {e}")
        return True, "", False


def _log_degradation(message):
    """Log quality gate degradation warnings so user knows enforcement is reduced."""
    try:
        from datetime import datetime
        log_path = os.path.expanduser('~/.claude').replace('\\', '/') + '/quality-gate.log'
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f'{now} | WARN  | DEGRADED | {message[:400]}\n')
    except Exception:
        pass

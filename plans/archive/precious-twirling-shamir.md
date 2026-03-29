# Plan: Multi-iteration codebase improvement

## Context
Full audit + improvement pass across chatgpt_bridge.js, chatgpt_project_bridge.js, lib.js, test-summary.js.
Issues found: 5 P1 crashes/infinite loops, 7 P2 wrong-behavior bugs, 14 P3 quality/UX problems.
Organized into 4 autonomous iterations from critical → architectural.

---

## Critical files
- `lib.js` — shared Playwright utils (add runClaude, fix sendAndReceive, add appendRunEntry, ellipsis)
- `chatgpt_bridge.js` — conversation bridge (arg validation, infinite loop fixes, async)
- `chatgpt_project_bridge.js` — project bridge (arg validation, dedup, async)
- `test-summary.js` — test script (stop duplicating logic, use temp file)

---

## ITERATION 1 — P1 crashes & infinite loops

### B1: --turns NaN bug (chatgpt_bridge.js ~line 219)
Replace truthy check with explicit NaN + range validation:
```js
const turnsIdx = args.indexOf('--turns');
let maxTurns = Infinity;
if (turnsIdx !== -1) {
  const val = parseInt(args[turnsIdx + 1], 10);
  if (isNaN(val) || val < 1) {
    console.error(`${C.err}Invalid --turns value: "${args[turnsIdx + 1]}" — must be a positive integer${C.reset}`);
    process.exit(1);
  }
  maxTurns = val;
}
```

### B2: --resume wrongly counts --turns value as positional (chatgpt_bridge.js ~line 225)
Build a `positional` array that skips `--turns N` pair, then use it for both the resume check and topic extraction:
```js
const positional = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--turns') { i++; continue; }
  if (args[i].startsWith('--')) continue;
  positional.push(args[i]);
}
// Use positional for --resume check and topic
if (args.includes('--resume') && positional.length === 0) { /* resume logic */ }
const topic = positional.join(' ').trim() || await promptForTopic();
```

### B3: --dir/--cycles/--discuss-turns with no value → crash (chatgpt_project_bridge.js parseArgs)
Add guard before consuming i+1 for each flag that takes a value:
```js
if (args[i] === '--dir') {
  if (!args[i+1] || args[i+1].startsWith('--')) { console.error(...); process.exit(1); }
  flags.dir = args[++i];
}
else if (args[i] === '--cycles') {
  const val = parseInt(args[i+1], 10);
  if (isNaN(val) || val < 1) { console.error(...); process.exit(1); }
  flags.cycles = val; i++;
}
else if (args[i] === '--discuss-turns') {
  const val = parseInt(args[i+1], 10);
  if (isNaN(val) || val < 1) { console.error(...); process.exit(1); }
  flags.discussTurns = val; i++;
}
```

### B4/B5: Infinite loop when Claude/ChatGPT error in conversation bridge (chatgpt_bridge.js)
Add `turn++` before every `continue` inside the `while (!stopFlag && turn <= maxTurns)` loop:
- Claude error handler: `await sleep(4000); turn++; continue;`
- ChatGPT error handler: `await sleep(4000); turn++; continue;`

---

## ITERATION 2 — P2 wrong behavior

### B6: writeLastRunSummary header-stripping regex (both bridges + test-summary.js)
Replace `replace(/^# Run History[\s\S]*?\n(?=## )/, '')` with:
```js
const body = existing.replace(/^# Run History[^\n]*\n\n?/, '');
```
Strips only the header line + one optional blank line, never accidentally eats entries.

### B7: readLastConvTopic matches project bridge entries (chatgpt_bridge.js ~line 77)
Add negation:
```js
const block = content.split(/\n---\n/).find(b =>
  b.includes('chatgpt_bridge') && !b.includes('chatgpt_project_bridge') && b.includes('Topic:')
);
```

### B8: Stability check may return previous response (lib.js sendAndReceive)
Count assistant messages before sending; wait for count to increase before running stability check:
```js
const beforeCount = await page.$$eval('[data-message-author-role="assistant"]', els => els.length).catch(() => 0);
// ... send message ...
// After stop button detaches, wait for new message to appear:
for (let i = 0; i < 15; i++) {
  const after = await page.$$eval('[data-message-author-role="assistant"]', els => els.length).catch(() => 0);
  if (after > beforeCount) break;
  await sleep(500);
}
// Then run existing stability check
```

### B9: Replace keyboard.type with clipboard paste (lib.js ~line 104)
Replace character-by-character typing (5-30s for long messages) with instant clipboard paste:
```js
// Try clipboard paste first, fall back to DOM injection
try {
  await page.evaluate(async (text) => { await navigator.clipboard.writeText(text); }, message);
  await page.keyboard.press('Control+v');
} catch {
  await page.evaluate((text) => {
    const el = document.activeElement;
    if (el) { el.textContent = text; el.dispatchEvent(new Event('input', { bubbles: true })); }
  }, message);
}
await sleep(300);
```
Also add `permissions: ['clipboard-read', 'clipboard-write']` to `launchBrowser()` options.

---

## ITERATION 3 — UX + quality cleanup

### D1: Remove dead TMP_PROMPT constant (chatgpt_bridge.js line 24)
Delete `const TMP_PROMPT = path.join(__dirname, '.tmp_claude_prompt.txt');`

### D4: Remove duplicate BRIDGE_DIR (chatgpt_project_bridge.js line 36)
Add `BRIDGE_DIR` to the existing destructured `require('./lib')` import. Delete the duplicate `const BRIDGE_DIR = ...` on line 36.

### D7/D8: Fix test-summary.js — stop duplicating logic + stop writing to real last-run.md
- Move shared file-write logic into lib.js as `appendRunEntry(entryText, targetFile = null)`:
  ```js
  function appendRunEntry(entryText, targetFile = null) {
    const summaryFile = targetFile || path.join(BRIDGE_DIR, 'last-run.md');
    const existing = fs.existsSync(summaryFile) ? fs.readFileSync(summaryFile, 'utf-8') : '';
    const body = existing.replace(/^# Run History[^\n]*\n\n?/, '');
    const priorEntries = body.split(/\n---\n/).filter(Boolean).slice(0, 9);
    const output = `# Run History — Claude_Code_&_ChatGPT_Chatter\n\n` + [entryText, ...priorEntries].join('\n---\n');
    fs.writeFileSync(summaryFile, output, 'utf-8');
  }
  ```
- Move `readLastProjectRun()` to lib.js. Export both.
- Both bridges call `appendRunEntry(entry.join('\n'))` (no targetFile → real last-run.md).
- `test-summary.js` imports from lib, writes to `test-output/test-last-run.md`.

### U3: Add ellipsis to box-drawing truncation (both bridges)
Add helper to lib.js: `function ellipsis(text, max) { return text.length > max ? text.slice(0, max-3) + '...' : text; }`
Use it everywhere `.substring(0, N)` appears in box-drawing output. Export from lib.

### U5: Fix misleading --resume messaging (both bridges)
- chatgpt_bridge.js: "Starting fresh chat on previous topic:"
- chatgpt_project_bridge.js: "Continuing project (new chat session):"

### M5: Add log pruning to conversation bridge (chatgpt_bridge.js)
After `LOG_DIR` creation, add the same pruning pattern as project bridge:
```js
fs.readdirSync(LOG_DIR)
  .filter(f => f.startsWith('conv_') && f.endsWith('.json'))
  .map(f => ({ name: f, mtime: fs.statSync(path.join(LOG_DIR, f)).mtimeMs }))
  .sort((a, b) => b.mtime - a.mtime)
  .slice(20)
  .forEach(f => { try { fs.unlinkSync(path.join(LOG_DIR, f.name)); } catch {} });
```

### S5: Sanitize paths in detectRunCommand (chatgpt_project_bridge.js ~line 98)
```js
const safeDir = projectDir.replace(/"/g, '\\"');
// Use safeDir in all returned command strings
```

---

## ITERATION 4 — Replace spawnSync with async spawn

### Why
`spawnSync` blocks the Node.js event loop for 1-5 minutes during Claude execution. This means:
- STOP handler never fires during Claude generation
- No real-time progress output possible
- Timeout is hard-coded and can't be interrupted

### Add `runClaude(flags, input, opts)` to lib.js
```js
const { spawn } = require('child_process');

function runClaude(flags, input, opts = {}) {
  const { timeout = 120_000, cwd = process.cwd(), env = { ...process.env, NODE_NO_WARNINGS: '1' }, onStdout = null } = opts;
  return new Promise((resolve, reject) => {
    const child = spawn('claude', flags, { cwd, env, shell: true, stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    child.stdout.on('data', chunk => { stdout += chunk; if (onStdout) onStdout(chunk.toString()); });
    child.stderr.on('data', chunk => { stderr += chunk; });
    child.on('error', err => reject(new Error(`Claude spawn error: ${err.message}`)));
    child.on('close', code => {
      clearTimeout(timer);
      if (code !== 0) reject(new Error(`Claude CLI exited ${code}: ${stderr.trim() || '(no stderr)'}`));
      else if (!stdout.trim()) reject(new Error('Claude returned empty response'));
      else resolve(stdout.trim());
    });
    if (input) { child.stdin.write(input); child.stdin.end(); }
    const timer = setTimeout(() => { child.kill('SIGTERM'); reject(new Error(`Claude CLI timed out after ${timeout/1000}s`)); }, timeout);
  });
}
```
Export `runClaude`.

### Convert all callers
- `chatgpt_bridge.js`: `generateClaudeMessage` → `async`, calls `await runClaude(CLAUDE_FLAGS, prompt, { timeout: 120_000, env: CLAUDE_ENV })`; remove `spawnSync` import
- `chatgpt_project_bridge.js`: `generateClaudeDiscussMessage` → `async`; `runImplementation` → `async`, uses `onStdout: verbose ? chunk => process.stdout.write(...) : null`; remove `spawnSync` import
- Increase `runImplementation` timeout to 600_000ms (R7 fix — 10 min for npm install)

---

## Execution order
1. Run iteration 1 → `node --check` all files → test B1/B3 arg validation
2. Run iteration 2 → `node --check` → update test-summary.js to test B6/B7
3. Run iteration 3 → `node --check` → run `node test-summary.js` → confirm writes to test-output/
4. Run iteration 4 → `node --check` → grep for spawnSync (must be zero)
5. Final: `node test-summary.js` (all pass) then live test with `chatgpt_bridge "test" --turns 2`

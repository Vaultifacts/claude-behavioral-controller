# VaultLister 3.0 — Exhaustive Release Execution Plan
> Generated 2026-03-08. Based on full codebase audit. Every step is specific and actionable.

---

## PHASE A — Environment & Configuration
**Owner: You (env vars require manual input) + Claude (code wiring)**
**Estimated time: 1 day**

---

### A-1: Install Playwright Browsers

```bash
cd vaultlister-3
bunx playwright install chromium
```

- This installs the Chromium binary Playwright needs to run bots
- Verify it worked:
  ```bash
  bunx playwright --version
  ls ~/.cache/ms-playwright/
  ```
- If behind a corporate proxy, set: `PLAYWRIGHT_DOWNLOAD_HOST=https://playwright.azureedge.net`
- Only Chromium is needed for V1 (all bots use `chromium.launch()`)

---

### A-2: Set Core Server Variables in `.env`

Open `.env` and confirm/set these critical values:

```env
NODE_ENV=production
PORT=3000
JWT_SECRET=<generate with: openssl rand -base64 48>
SESSION_SECRET=<generate with: openssl rand -base64 48>
DATA_DIR=./data
BACKUP_DIR=./backups
LOG_DIR=./logs
LOG_LEVEL=info
```

Generate secrets (run in terminal):
```bash
openssl rand -base64 48   # use output for JWT_SECRET
openssl rand -base64 48   # use output for SESSION_SECRET
```

---

### A-3: Switch OAuth Mode to Production

In `.env`:
```env
OAUTH_MODE=production
```

**What this changes (oauth.js line 44):**
- Authorization URLs switch from `http://localhost:3000/mock-oauth/{platform}/authorize`
  to real platform OAuth endpoints (e.g., `https://auth.ebay.com/oauth2/authorize`)
- Token exchange calls real platform servers
- Missing credentials now throw 503 errors instead of silently returning mock tokens
- All OAuth tokens stored encrypted (AES-256-CBC) — this was true in mock mode too

**After flipping this, nothing will work until Phase B credentials are set.**

---

### A-4: Configure CORS for Your Domain

In `.env`:
```env
BASE_URL=https://yourdomain.com
CORS_ORIGINS=https://yourdomain.com
RP_ID=yourdomain.com
ORIGIN=https://yourdomain.com
```

Replace `yourdomain.com` with your actual domain. If testing locally first:
```env
BASE_URL=http://localhost:3000
CORS_ORIGINS=http://localhost:3000
RP_ID=localhost
ORIGIN=http://localhost:3000
```

---

### A-5: Configure Redis

Docker Compose brings up Redis automatically. Set a real password:
```env
REDIS_URL=redis://:yourpassword@redis:6379
REDIS_PASSWORD=yourpassword
```
The `redis` hostname works inside Docker networking. For local dev without Docker:
```env
REDIS_URL=redis://localhost:6379
```

---

### A-6: Verify Anthropic API Key Routing

The API key is already set. Verify it's routing to the right features:

```env
ANTHROPIC_API_KEY=<already set>
FEATURE_AI_LISTING=true
```

**Known issue:** `listing-generator.js` does NOT call the Anthropic SDK — it uses local templates.
This is fixed in Phase C. For now just confirm the key is present.

Quick test:
```bash
bun run dev &
curl -X POST http://localhost:3000/api/ai/translate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $(curl -s -X POST http://localhost:3000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"demo@vaultlister.com","password":"DemoPassword123!"}' \
    | python -c "import sys,json; print(json.load(sys.stdin)['token'])")" \
  -d '{"text":"hello","targetLanguage":"es"}'
```
Expect: `{"translation":"hola"}` or similar — confirms Claude API is live.

---

### A-7: Configure Email (SMTP)

Required for password resets and notifications:
```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURE=false
SMTP_USER=youremail@gmail.com
SMTP_PASS=<Gmail App Password — not your account password>
EMAIL_FROM=VaultLister <noreply@yourdomain.com>
```

To get a Gmail App Password:
1. Google Account → Security → 2-Step Verification → App Passwords
2. Select "Mail" + "Other (Custom name)" → "VaultLister"
3. Copy the 16-character password into `SMTP_PASS`

---

### A-8: Confirm Feature Flags

```env
FEATURE_AI_LISTING=true
FEATURE_ADVANCED_ANALYTICS=true
FEATURE_WHATNOT_INTEGRATION=false
```

Leave Whatnot disabled — the integration is a stub.

---

### A-9: Validate Startup

```bash
bun run dev
```

Watch for:
- ✅ `Server running on port 3000`
- ✅ `Database initialized`
- ✅ `Task worker started`
- ✅ `Redis connected` (or warning if Redis not running locally)
- ❌ Any `Missing required env variable` errors → fix before proceeding

---

## PHASE B — Marketplace Integration QA
**Owner: You (account credentials + manual testing) + Claude (fixing any broken flows)**
**Estimated time: 1 week**

For each platform: set credentials → connect account → publish test listing → verify live → delist.

---

### B-1: Poshmark

**Credentials to set in `.env`:**
```env
POSHMARK_USERNAME=your-poshmark-email@example.com
POSHMARK_PASSWORD=your-poshmark-password
```

Note: Poshmark has no public OAuth API. The "OAuth" flow in the app stores credentials for
the Playwright bot. The username/password are read directly from `process.env` in `poshmark-bot.js`.

**Test the bot manually first:**
```bash
bun -e "
import { PoshmarkBot } from './src/shared/automations/poshmark-bot.js';
const bot = new PoshmarkBot();
await bot.init();
await bot.login();
console.log('Login successful');
await bot.close();
"
```

Expected: Browser opens (headless), navigates to poshmark.com, logs in, closes. Check
`data/automation-audit.log` — should see a `login_success` entry.

If login fails:
- Check credentials are correct by logging in manually at poshmark.com
- Poshmark may require email verification — do it once manually
- If CAPTCHA appears, the bot will stop and log `captcha_detected`

**Test publish flow:**
1. Start server: `bun run dev`
2. Log in to the app at `http://localhost:3000`
3. Add a test inventory item (use a real item you're willing to temporarily list)
4. Go to Cross-Lister → select the item → choose Poshmark → click Publish
5. Watch terminal logs for Playwright launching
6. Check `data/automation-audit.log` for `publish_success`
7. Go to Poshmark.com → My Closet → confirm the listing appeared
8. Delete it from Poshmark immediately (this was a test)

**Test closet sharing automation:**
1. In app → Automations → Create Rule
2. Type: Closet Share, Schedule: Every 1 hour, Max shares: 10
3. Enable the rule
4. Trigger manually: POST `/api/automations/run` or wait 60 seconds for taskWorker
5. Check `data/automation-audit.log` for `share_success` entries
6. Check Poshmark feed — your items should appear shared

**Test auto-offer rule:**
1. Automations → Create Rule → Type: Auto-Offer
2. Set: min offer % = 80, action = auto-counter at 90%
3. Go to Poshmark manually, send yourself a low offer from another account (or have a friend do it)
4. Check Offers page in app — offer should appear
5. Check taskWorker logs — auto-counter should fire within 60 seconds

---

### B-2: eBay

**Step 1: Create an eBay developer account**
1. Go to developer.ebay.com → Register
2. Create an application: My Account → Application Access Keys → Create a Keyset
3. Choose: `Production` environment
4. Note your `App ID (Client ID)` and `Cert ID (Client Secret)`

**Step 2: Configure OAuth redirect URI**
1. In eBay developer portal → Your app → Auth accepted redirect URIs
2. Add: `https://yourdomain.com/api/oauth/callback/ebay`
   (or `http://localhost:3000/api/oauth/callback/ebay` for local testing)
3. Note: eBay uses a `RuName` (redirect URI name) — copy this exact string

**Step 3: Set credentials in `.env`:**
```env
EBAY_CLIENT_ID=your-app-id-from-developer-ebay
EBAY_CLIENT_SECRET=your-cert-id-from-developer-ebay
EBAY_REDIRECT_URI=your-RuName-from-developer-portal
EBAY_ENVIRONMENT=production
```

For sandbox testing first (recommended):
```env
EBAY_ENVIRONMENT=sandbox
EBAY_CLIENT_ID=your-sandbox-app-id
EBAY_CLIENT_SECRET=your-sandbox-cert-id
```

**Step 4: Get required eBay seller permissions**
Your eBay account needs:
- Seller account (not just buyer)
- `sell.inventory` scope approved
- Payment method configured (managed payments)
- Default shipping policy created in eBay account

**Step 5: Test OAuth flow:**
1. In app → Settings → Connected Accounts → Connect eBay
2. Should redirect to ebay.com login → authorize → redirect back
3. Check `shops` table: `SELECT * FROM shops WHERE platform='ebay';`
   Confirm `oauth_token` is populated (will be encrypted hex string)

**Step 6: Test end-to-end publish:**
1. Create a test inventory item
2. Cross-Lister → select item → eBay → Publish
3. Backend calls `ebayPublish.js` → eBay Sell API
4. Watch for: `POST /sell/inventory/v1/inventory_item` → `POST /sell/inventory/v1/offer`
5. Check eBay Seller Hub — listing should appear (may take ~60 seconds)
6. Note the eBay listing ID returned in the response
7. End the listing in eBay Seller Hub (don't leave test listings live)

**Common eBay publish errors:**
- `category not found` → item needs a valid eBay category ID in inventory
- `no payment policy` → create a managed payments policy in eBay account
- `no shipping policy` → create a shipping policy in eBay Business Policies
- `condition not allowed for category` → some categories only allow "New"

---

### B-3: Etsy

**Step 1: Create Etsy developer account**
1. Go to etsy.com/developers → Register
2. Create app: Your Apps → Create New App
3. Set callback URL: `https://yourdomain.com/api/oauth/callback/etsy`
4. Note `Keystring` (client ID) — Etsy doesn't provide a secret for PKCE flows

**Step 2: Set credentials:**
```env
ETSY_CLIENT_ID=your-etsy-keystring
# ETSY_CLIENT_SECRET is not needed — Etsy uses PKCE (no secret)
```

**Step 3: Test OAuth PKCE flow:**
1. In app → Settings → Connected Accounts → Connect Etsy
2. Etsy redirects with `code` + `state`
3. Backend exchanges code + PKCE verifier for tokens
4. Confirm `shops` table has Etsy entry with valid token

**Step 4: Test publish:**
- Etsy requires your shop to be open and have payment method configured
- Test listing → confirm it appears in Etsy shop → deactivate it

---

### B-4: Remaining Platforms — Make "Coming Soon" Decision

For Mercari, Depop, Grailed, Facebook Marketplace, Whatnot, Shopify:
These are partial stubs. **Recommended action for V1:**

**In `src/frontend/pages/` (cross-lister page), find the platform list and add `disabled` + "Coming Soon" badge to these platforms.**

Claude can do this for you — just ask: "Mark Mercari, Depop, Grailed, Facebook, Whatnot, and Shopify as Coming Soon in the cross-lister UI"

Do NOT ship these as functional — the publish routes will silently fail or produce broken listings.

**Exception — if you personally sell on Mercari:**
Mercari's bot is the most complete after Poshmark. Set:
```env
MERCARI_USERNAME=your-mercari-email
MERCARI_PASSWORD=your-mercari-password
```
Then test the same way as Poshmark (the bot flow is identical).

---

## PHASE C — AI Feature Completion
**Owner: Claude**
**Estimated time: 2-3 days**

---

### C-1: Wire Listing Generator to Claude API

**Current state:** `src/shared/ai/listing-generator.js` uses only local templates.
`generateTitle()`, `generateDescription()`, `generateTags()` — all pattern-based, no API calls.

**What needs to happen:**
Claude will modify `listing-generator.js` to:
1. Attempt a Claude API call first (using `claude-haiku-4-5-20251001` — cheap + fast)
2. Fall back to existing local templates if API fails or key is missing
3. Pass: item brand, category, condition, colors, size, original price, notes
4. Receive: title (≤80 chars), description (200-500 words), tags (≤20)

**Tell Claude:** "Wire listing-generator.js to call claude-haiku-4-5-20251001 for title, description, and tags. Fall back to existing local templates if the API call fails. Follow the same pattern as grokService.js for the Anthropic SDK call."

**Test after:**
```bash
curl -X POST http://localhost:3000/api/ai/generate-listing \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "brand": "Nike",
    "category": "Sneakers",
    "condition": "like_new",
    "color": "white",
    "size": "10",
    "originalPrice": 120
  }'
```
Expect: Real Claude-generated title and description, not a template string.

---

### C-2: Wire Image Analyzer to Claude Vision

**Current state:** `analyzeImage()` returns:
```javascript
{ category: null, brand: null, colors: [], confidence: 0, analyzed: false }
```

**What needs to happen:**
Claude will modify `image-analyzer.js` to:
1. Accept base64-encoded image data
2. Send to `claude-haiku-4-5-20251001` with vision capability
3. Prompt: extract brand, category, condition, colors, notable features
4. Return structured JSON matching existing `analyzeImage()` return shape
5. Fall back to text-based helpers (`detectBrand`, `detectCategory`) if API fails

**Tell Claude:** "Wire image-analyzer.js analyzeImage() to use Claude Haiku vision API to detect brand, category, condition, colors from uploaded images. Fall back to the existing text-based helpers if the API call fails or no key is set."

**Test after:**
1. Add a new inventory item in the app
2. Upload a photo of a branded clothing item
3. Click "Analyze Image" (or equivalent button)
4. Expect: brand detected, category auto-filled, condition suggested

---

### C-3: Fix Price Predictor — Use Real Sales Data

**Current state:** Pure heuristics (brand tier × condition × season multipliers).
This is actually useful — label it as an estimate based on market data, not mock data.

**What needs to happen:**
1. Query the user's own `sales` table for historical sold prices
2. Average by category + condition for a baseline
3. Apply the existing brand/season multipliers on top
4. Label in the UI as "Estimated based on market trends"

**Tell Claude:** "Update price-predictor.js predictPrice() to first query the sales table for historical sold prices for the same category+condition, use that as the base price if 3+ data points exist, then apply the existing brand/season multipliers. Fall back to the existing CATEGORY_PRICES table if no history."

This requires no additional API keys. It will automatically improve as you make more sales.

---

### C-4: Switch Vault Buddy to Claude as Primary

**Current state:** `grokService.js` already uses `claude-haiku-4-5-20251001` as primary if
`ANTHROPIC_API_KEY` is set. Since your key is confirmed working, this should already be live.

**Verify it's working:**
1. Open Vault Buddy in the app
2. Ask: "How many items do I have in inventory?"
3. Expect: A response that includes your actual inventory count (injected via `getUserStats()`)
4. The response source should be `claude` not `mock`

**If it's returning mock responses:**
Check: Is `ANTHROPIC_API_KEY` in `.env`? If yes, check `grokService.js` line 252 — the
condition `process.env.ANTHROPIC_API_KEY` should be truthy.

**Upgrade model for better conversations (optional):**
In `grokService.js` line 228, change:
```javascript
model: 'claude-haiku-4-5-20251001'
```
to:
```javascript
model: 'claude-sonnet-4-6'
```
Sonnet gives noticeably better Vault Buddy responses. Haiku is fine for quick Q&A but sonnet
is better for multi-turn conversations. Cost difference is small for a personal tool.

---

## PHASE D — Chrome Extension
**Owner: Claude (icons) + You (testing)**
**Estimated time: 1 day**

---

### D-1: Create Icon Files

The extension won't load without icons. Claude will create them.

**Tell Claude:** "Create placeholder PNG icon files for the Chrome extension:
`chrome-extension/icons/icon16.png`, `icon48.png`, `icon128.png`.
Use the VaultLister brand colors (dark background, VL monogram or vault icon).
These need to be valid PNG files at exactly 16×16, 48×48, and 128×128 pixels."

If you have a logo file already, Claude can resize it:
**Tell Claude:** "Resize [path to logo] to 16×16, 48×48, and 128×128 PNGs and save to
chrome-extension/icons/"

---

### D-2: Update Extension API Base URL

**Current state:** `chrome-extension/popup/popup.js` hardcodes `http://localhost:3000`.
Before shipping, update it to your production URL.

Open `chrome-extension/popup/popup.js` and find the base URL constant.
Change to your real domain, or make it configurable in the extension options.

**Tell Claude:** "Update the Chrome extension API base URL to be configurable.
Add an extension options page that lets the user set the VaultLister server URL,
defaulting to https://yourdomain.com"

---

### D-3: Load and Test the Extension

1. Open Chrome → `chrome://extensions`
2. Enable "Developer mode" (top-right toggle)
3. Click "Load unpacked" → select `chrome-extension/` folder
4. Extension icon should appear in toolbar — click it
5. Confirm popup opens with no console errors (right-click extension icon → Inspect popup)

**Test scraping:**
1. Navigate to an Amazon product page
2. Click extension icon → click "Capture Product"
3. Check VaultLister app → Inventory → new item should appear with scraped data

**Test Poshmark autofill:**
1. On Poshmark.com, start creating a listing manually
2. Extension's content script should detect the form (matching `poshmark.com/create-listing*`)
3. If you previously captured a product, check if autofill populates the form

**Test price tracking:**
1. On Amazon, click extension → "Track Price"
2. Set a target price
3. Check that the item appears in a tracked list somewhere in the extension

---

### D-4: Package for Distribution (Optional, post-launch)

If you want to share the extension with other resellers:
1. Chrome Web Store requires a developer account ($5 one-time fee)
2. Run: `zip -r vaultlister-extension.zip chrome-extension/`
3. Upload at developer.chrome.com

For now, personal use via "Load unpacked" is sufficient.

---

## PHASE E — End-to-End User Walkthrough
**Owner: You**
**Estimated time: 3-5 days**

This phase is manual testing. Work through every critical flow from the perspective of a
first-time reseller user. Document every bug you find and give them to Claude to fix.

---

### E-1: Onboarding Flow

**Steps:**
1. Open an incognito window → navigate to app
2. Click Register → create a fresh account (use a test email)
3. Proceed through MFA setup
4. Land on dashboard

**What to check:**
- [ ] Registration form validates correctly (bad email, weak password rejected)
- [ ] Email verification arrives (check SMTP is configured from Phase A-7)
- [ ] MFA setup is clear — QR code works in Google Authenticator / Authy
- [ ] Dashboard loads with empty state UI (not a blank/broken page)
- [ ] Onboarding checklist or guide appears (check `src/backend/routes/onboarding.js`)
- [ ] "Connect your first marketplace" prompt appears or is findable

**Common issues to watch for:**
- Blank dashboard with no empty state message → add empty state UI
- MFA setup page broken → check TOTP secret generation
- No guidance on what to do first → add onboarding checklist

---

### E-2: Inventory → Image Upload → AI Generate → Cross-List → Sell Cycle

This is the core workflow. Test it completely.

**Steps:**
1. Inventory → Add New Item
2. Fill in: brand, category, size, condition, original price, cost price
3. Upload 3-4 photos of the item
4. Click "Analyze Images" → confirm Claude Vision returns brand/category/condition
5. Click "Generate Listing" → confirm Claude generates real title + description (not template)
6. Review and edit the generated listing
7. Set your asking price (check price predictor shows a reasonable estimate)
8. Save as Draft

9. Cross-Lister → find the item → select Poshmark + eBay → Publish
10. Watch for: progress indicator, per-platform success/failure toasts
11. Confirm Poshmark listing is live at Poshmark.com
12. Confirm eBay listing is live in eBay Seller Hub

13. Sell the item manually on Poshmark (accept any offer or buy it yourself from another account)
14. In app → Sales → Mark as Sold (or confirm webhook/sync picks it up)
15. Check: inventory item status changed to "sold"
16. Check: eBay listing was automatically ended (if sync is implemented)

**What to check at each step:**
- [ ] Photo upload handles multiple files, shows previews
- [ ] Image analysis takes < 5 seconds
- [ ] Generated listing is coherent and accurate (not generic garbage)
- [ ] Price predictor shows a range, not $0 or NaN
- [ ] Cross-listing publish shows per-platform results (not just a spinner that disappears)
- [ ] Sold item appears in Sales with correct revenue/profit calculated
- [ ] Analytics dashboard numbers update after the sale

---

### E-3: Automation Flows

**Test Poshmark Closet Sharing:**
1. Automations → Create New Rule
2. Type: Closet Share
3. Schedule: Every 2 hours
4. Max shares per run: 50
5. Enable the rule
6. Click "Run Now" or trigger manually
7. Watch logs: `tail -f logs/app.log | grep -i poshmark`
8. Check `data/automation-audit.log` — should see share entries with timestamps

**What to check:**
- [ ] Rule creation form is clear and validates correctly
- [ ] "Run Now" button exists and triggers immediately
- [ ] Audit log entries appear with: timestamp, action, item URL, success/fail
- [ ] Error handling: if Poshmark is down, shows clear error not crash

**Test Auto-Offer Rule:**
1. Automations → Create Rule → Type: Auto-Offer
2. Conditions: offers below 75% of listing price
3. Action: auto-counter at 85% of listing price
4. Enable
5. From another Poshmark account (or ask a friend), send a low offer
6. Wait 60 seconds (taskWorker checks every 60 seconds)
7. Check Poshmark — counter-offer should have appeared automatically
8. Check app Offers page — offer should show status "countered"

---

### E-4: Offer Management

1. Receive an offer (use the test from E-3 above)
2. In app → Offers page
3. Find the offer — check: buyer name, offer amount, % of asking price, item thumbnail
4. Test manual Accept — confirm creates a Sale record
5. Test manual Decline — confirm offer moves to declined
6. Test manual Counter — confirm counter appears on Poshmark

**What to check:**
- [ ] Offers page loads with real data (not empty even when offers exist)
- [ ] WebSocket notification badge increments when offer arrives
- [ ] Toast notification fires for new offer
- [ ] Accept/Decline/Counter buttons all work
- [ ] Accepted offer creates a Sale automatically

---

### E-5: Analytics

After completing E-2 (at least 1 sale), check the Analytics dashboard.

1. Dashboard → check: revenue, profit, items sold
2. Analytics page → check: sales chart shows the test sale
3. Check platform breakdown: Poshmark vs eBay split
4. Check inventory turnover metrics
5. Check time period selector (7d / 30d / 90d) — all should work

**What to check:**
- [ ] Numbers match reality (1 sale = 1 sale shown)
- [ ] Profit calculation is correct (sale price minus cost price minus platform fee)
- [ ] Charts render without errors (check browser console for JS errors)
- [ ] Empty state for periods with no data (not broken/null)

---

### E-6: Notifications & WebSocket

1. Open the app in two browser tabs simultaneously
2. In Tab 1: trigger an action that generates a notification (receive an offer, make a sale)
3. In Tab 2: watch the bell icon — badge should increment without refreshing

**What to check:**
- [ ] WebSocket connects on load (check Network tab → WS connection shows `101 Switching Protocols`)
- [ ] Badge increments in real time
- [ ] Clicking bell shows notification list
- [ ] Mark as read works
- [ ] Notifications persist across refresh (stored in DB, not memory only)

---

### E-7: Mobile / Responsive

Test every flow above at 375px width (iPhone SE viewport):

```
Chrome DevTools → Device Toolbar → iPhone SE (375px)
```

**What to check:**
- [ ] Sidebar collapses to hamburger menu (test the toggle)
- [ ] Inventory table scrolls horizontally or stacks cards
- [ ] Cross-lister publish button is reachable without horizontal scroll
- [ ] Offer accept/decline buttons are large enough to tap
- [ ] Photo upload works on mobile (file picker opens)
- [ ] Modals don't overflow the viewport
- [ ] Dashboard charts resize correctly

---

### E-8: Fix Everything Found in E-1 through E-7

Make a list of every bug/issue found. Prioritize:
- **P0 (Blocker):** Can't complete the core workflow (E-2 flow broken)
- **P1 (High):** Feature doesn't work but workaround exists
- **P2 (Medium):** Visual/UX issue, not broken
- **P3 (Low):** Nice to have

Fix all P0 and P1 before Phase F. P2/P3 can be post-launch.

---

## PHASE F — Pre-Deployment Hardening
**Owner: Claude + You**
**Estimated time: 2 days**

---

### F-1: Secrets Audit

Search for any hardcoded credentials or keys in source code:

```bash
# Check for API keys
grep -rn "sk-" src/ --include="*.js" | grep -v ".test.js"
grep -rn "EBAY_CLIENT_SECRET" src/ --include="*.js"
grep -rn "anthropic" src/ --include="*.js" | grep -v "process.env" | grep -v "import"

# Check for hardcoded passwords
grep -rn "password" src/ --include="*.js" | grep -v "process.env" | grep -v "req.body" \
  | grep -v "hash" | grep -v "bcrypt" | grep -v "test"

# Check for hardcoded tokens
grep -rn "Bearer " src/ --include="*.js" | grep -v "Authorization"
grep -rn "mock_access_token" src/ --include="*.js"
```

None of these should return results that aren't test fixtures or env variable references.

Also check for `.env` not being ignored:
```bash
cat .gitignore | grep ".env"    # should see: .env
git status | grep ".env"         # should show nothing (not tracked)
```

---

### F-2: Dependency Security Audit

```bash
npm audit
```

Review output:
- **Critical/High:** Fix before launch
- **Moderate:** Fix if easy, otherwise document and schedule for post-launch
- **Low:** Document, fix post-launch

Common fix:
```bash
npm audit fix
# If auto-fix breaks things:
npm audit fix --dry-run   # see what would change
```

After audit fix, re-run test suite to confirm nothing broke:
```bash
bun run test:unit
```

---

### F-3: Run Full Test Suite with Production Settings

```bash
# Set production-like env
export OAUTH_MODE=production
export NODE_ENV=production

bun run test:unit
bun run test:e2e
```

Expected: 5,289 unit + 620 E2E still pass.

If E2E fails because tests hit mock OAuth endpoints:
- Check `playwright.config.js` for how OAuth is handled in tests
- E2E tests should use test fixtures, not real OAuth flows

---

### F-4: Docker Local Build Test

```bash
# Build the production image locally
docker compose build

# Start all services including production profile
docker compose --profile production up -d

# Wait 30 seconds for startup
sleep 30

# Verify health
curl http://localhost:3000/api/health/live
# Expected: {"status":"ok","timestamp":"..."}

curl http://localhost:3000/api/health/ready
# Expected: {"status":"ready","checks":{"database":"ok","redis":"ok"}}

curl http://localhost:3000/api/workers/health
# Expected: all 5 workers with recent lastRun timestamps

# Check nginx is proxying
curl http://localhost/api/health/live
# Expected: same as above (nginx → app)
```

If any check fails:
```bash
docker compose logs app          # app startup errors
docker compose logs nginx        # nginx config errors
docker compose logs redis        # redis connection errors
```

---

### F-5: SSL Certificate for Local Testing

Before shipping with real SSL, test that nginx can serve HTTPS:

**Option A: Self-signed cert (for local test only):**
```bash
mkdir -p nginx/ssl
openssl req -x509 -newkey rsa:4096 -keyout nginx/ssl/key.pem \
  -out nginx/ssl/cert.pem -days 365 -nodes \
  -subj "/CN=localhost"
```

Then test:
```bash
curl -k https://localhost/api/health/live
# -k ignores self-signed cert warning
```

**Option B: Real cert via Let's Encrypt (do this on the production server in Phase G)**
The nginx.conf already has the `/.well-known/acme-challenge/` path configured.

---

### F-6: Review `.claude/settings.json` Deny Rules

```bash
cat .claude/settings.json
```

Look for the `deny` list. Confirm:
- `db:drop*` commands are denied (they are per STATUS.md)
- No overly permissive rules that would let an AI agent delete production data
- Add: `docker compose down -v` to deny list (destroys volumes)

---

### F-7: Write RELEASE.md

Create a simple release document (Claude can help draft it):

```markdown
# VaultLister 3.0 — V1.0 Release

## What's Included
- Inventory management with AI listing generation (Claude Haiku)
- Image bank with AI image analysis (Claude Vision)
- Cross-listing to: Poshmark, eBay, Etsy
- Poshmark automation: closet sharing, follow-back, auto-offers
- Offer management with automation rules
- Sales tracking and analytics dashboard
- Vault Buddy AI assistant (Claude Sonnet)
- Chrome extension for product scraping

## Coming Soon
- Mercari, Depop, Grailed, Facebook Marketplace, Whatnot
- Shopify integration
- Mobile app

## Not in V1 (Removed)
- AR previews
- Blockchain verification
- Receipt parser
```

---

## PHASE G — Deployment
**Owner: You (server setup) + Claude (config assistance)**
**Estimated time: 1-2 days**

---

### G-1: Choose and Provision a Server

**Recommended: DigitalOcean Droplet**
- Size: Basic → Regular → $6/mo (1 vCPU, 1GB RAM, 25GB SSD)
- OS: Ubuntu 24.04 LTS
- Region: closest to you (e.g., SFO3 for US West)
- Add SSH key during setup

**Alternative: Hetzner Cloud (cheaper, European)**
- Size: CX22 (~€4/mo, 2 vCPU, 4GB RAM)
- Better specs for same price as DigitalOcean

**After provisioning:**
```bash
ssh root@your-server-ip

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Install Docker Compose plugin
apt install -y docker-compose-plugin

# Verify
docker --version
docker compose version

# Create app user (don't run as root)
useradd -m -s /bin/bash vaultlister
usermod -aG docker vaultlister
```

---

### G-2: Configure DNS

1. Buy a domain (Namecheap, Cloudflare, etc.) if you don't have one
2. In DNS settings, add an A record:
   - Name: `@` (root) or `app`
   - Value: your server IP
   - TTL: 300 (5 minutes for fast propagation)

Verify DNS propagation (wait up to 1 hour):
```bash
nslookup yourdomain.com
# Should return your server IP
```

---

### G-3: Deploy Application

On your server:
```bash
su - vaultlister

# Clone repo
git clone https://github.com/Vaultifacts/VaultLister-3.0.git
cd VaultLister-3.0

# Create .env from your local .env (copy contents manually)
nano .env
# Paste your full .env, update BASE_URL/CORS_ORIGINS to your real domain

# Install Playwright browsers on server
bunx playwright install chromium
bunx playwright install-deps chromium   # installs system deps

# Start services (without production profile first — no nginx yet)
docker compose up -d --build

# Verify app is running
curl http://localhost:3000/api/health/ready
```

---

### G-4: Obtain SSL Certificate (Let's Encrypt)

```bash
# Install certbot
apt install -y certbot

# Get certificate (stops temporarily running nginx if needed)
certbot certonly --standalone \
  -d yourdomain.com \
  -d www.yourdomain.com \
  --email your@email.com \
  --agree-tos \
  --no-eff-email

# Copy certs to nginx/ssl/
mkdir -p ~/VaultLister-3.0/nginx/ssl
cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ~/VaultLister-3.0/nginx/ssl/cert.pem
cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ~/VaultLister-3.0/nginx/ssl/key.pem
chmod 600 ~/VaultLister-3.0/nginx/ssl/key.pem
```

**Auto-renewal:**
```bash
# Add to crontab: renew cert every 3 months
crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet && cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /home/vaultlister/VaultLister-3.0/nginx/ssl/cert.pem && cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /home/vaultlister/VaultLister-3.0/nginx/ssl/key.pem && docker compose -f /home/vaultlister/VaultLister-3.0/docker-compose.yml exec nginx nginx -s reload
```

---

### G-5: Start Production Stack

```bash
cd ~/VaultLister-3.0

# Start with production profile (nginx + backup-scheduler included)
docker compose --profile production up -d

# Verify all containers running
docker compose ps
# Expected: app, redis, nginx, backup-scheduler all "Up" and "healthy"
```

---

### G-6: Verify Production Health Checks

```bash
# HTTP → HTTPS redirect
curl -I http://yourdomain.com
# Expected: 301 redirect to https://

# HTTPS health check
curl https://yourdomain.com/api/health/live
# Expected: {"status":"ok"}

curl https://yourdomain.com/api/health/ready
# Expected: {"status":"ready","checks":{"database":"ok","redis":"ok"}}

curl https://yourdomain.com/api/workers/health
# Expected: 5 workers with timestamps from within last 5 minutes

# WebSocket
# Open browser DevTools at https://yourdomain.com
# Network tab → WS → should see connection upgrade to 101
```

---

### G-7: Update OAuth Redirect URIs

With your real domain, update the redirect URIs in each marketplace developer portal:

- **eBay:** developer.ebay.com → Your App → Auth accepted redirect URIs
  Add: `https://yourdomain.com/api/oauth/callback/ebay`

- **Etsy:** etsy.com/developers → Your App → Callback URLs
  Add: `https://yourdomain.com/api/oauth/callback/etsy`

Also update in `.env`:
```env
BASE_URL=https://yourdomain.com
CORS_ORIGINS=https://yourdomain.com
EBAY_REDIRECT_URI=https://yourdomain.com/api/oauth/callback/ebay
```

Restart app:
```bash
docker compose restart app
```

---

### G-8: Run Smoke Tests on Production

1. Open `https://yourdomain.com` in a browser
2. Register a fresh account
3. Complete MFA setup
4. Connect Poshmark account
5. Add one inventory item
6. Publish to Poshmark
7. Confirm listing appears live on Poshmark.com

If anything fails, check logs:
```bash
docker compose logs app --tail=50 -f
docker compose logs nginx --tail=20
```

---

### G-9: Confirm Backup is Running

```bash
# Check backup scheduler logs
docker compose logs backup-scheduler --tail=20

# List backup files
ls -la ~/VaultLister-3.0/backups/

# Should see at least one .db.gz file within 24 hours
# Trigger manual backup to verify immediately:
docker compose --profile backup run --rm backup
ls -la ~/VaultLister-3.0/backups/
```

---

### G-10: Set Up Monitoring (Optional but Recommended)

**Option A: Free — UptimeRobot**
1. Sign up at uptimerobot.com (free tier: 50 monitors)
2. Add monitor: HTTPS, URL: `https://yourdomain.com/api/health/ready`
3. Alert email: your email
4. Check interval: 5 minutes

**Option B: Sentry (error tracking)**
```env
SENTRY_DSN=https://your-key@sentry.io/project-id
```
Sign up at sentry.io (free tier available), create project → copy DSN.

**Option C: Slack alerts (already in .env.example)**
```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx/yyy/zzz
```
If you use Slack, this gives you alerts when error rate or memory thresholds are hit.

---

## PHASE H — Soft Launch
**Owner: You**
**Estimated time: 1-2 weeks**

---

### H-1: Use It Daily (Week 1)

For every item you list this week, go through VaultLister instead of manually listing on Poshmark/eBay.

Daily routine to test:
1. **Morning:** Check automation ran overnight (closet sharing logs)
2. **When listing:** Add item → photo → AI generate → cross-list
3. **When offer arrives:** Handle via app (accept/decline/counter)
4. **When sale happens:** Confirm it appears in Sales automatically (or mark manually)
5. **Weekly:** Check Analytics for accuracy

---

### H-2: Friction Log

Keep a running list of everything that slows you down or frustrates you:
```
FRICTION LOG
2026-03-15: Had to scroll too far to find the Publish button on mobile
2026-03-15: AI description used wrong brand spelling — needs spell check
2026-03-16: Price predictor shows $0 for vintage items — needs fallback
```

At end of week: bring this list to Claude and fix P0/P1 items.

---

### H-3: Invite Beta Users (Week 2)

After 1 week of personal use with no P0 bugs:
1. Invite 1-2 trusted reseller friends
2. Give them the URL and a fresh account
3. Watch what they do — note where they get confused
4. First-time user confusion = missing onboarding or unclear UI

---

### H-4: Post-Launch Checklist

- [ ] eBay sandbox → switch to `EBAY_ENVIRONMENT=production`
- [ ] Update Chrome extension base URL to production domain (from D-2)
- [ ] Disable demo account (`DEMO_EMAIL`/`DEMO_PASSWORD`) in `.env` if not wanted
- [ ] Review analytics after 1 week — is data accurate?
- [ ] Confirm daily backups are running (check `/backups/` folder)
- [ ] Check worker health endpoint once per week

---

## QUICK REFERENCE: Complete .env Checklist

Before going live, every one of these should be set (not placeholder):

```
✅ Core:           NODE_ENV, PORT, JWT_SECRET, SESSION_SECRET, DATA_DIR
✅ Domain:         BASE_URL, CORS_ORIGINS, RP_ID, ORIGIN
✅ Database:       DB_PATH, BACKUP_DIR
✅ Redis:          REDIS_URL, REDIS_PASSWORD
✅ Email:          SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM
✅ AI:             ANTHROPIC_API_KEY
✅ Poshmark:       POSHMARK_USERNAME, POSHMARK_PASSWORD
✅ eBay:           EBAY_CLIENT_ID, EBAY_CLIENT_SECRET, EBAY_REDIRECT_URI, EBAY_ENVIRONMENT
✅ Etsy:           ETSY_CLIENT_ID
✅ OAuth mode:     OAUTH_MODE=production
✅ Features:       FEATURE_AI_LISTING=true, FEATURE_ADVANCED_ANALYTICS=true
⬜ Optional:       SENTRY_DSN, SLACK_WEBHOOK_URL, OPENAI_API_KEY, GROK_API_KEY
⬜ Cloud backup:   CLOUD_BACKUP_ENABLED, AWS_* (only if you want off-site backups)
```

---

## WHAT CLAUDE HANDLES vs. WHAT YOU HANDLE

| Task | Owner | Why |
|------|-------|-----|
| Install Playwright | You | Requires running commands locally |
| Set all `.env` variables | You | Requires your real credentials |
| Switch OAUTH_MODE | You | `.env` change |
| Register eBay/Etsy developer apps | You | Requires account access |
| Provision server | You | Requires payment + SSH access |
| DNS configuration | You | Requires domain registrar access |
| SSL certificate | You | Requires server terminal access |
| Wire listing-generator to Claude API | Claude | Code change |
| Wire image-analyzer to Claude Vision | Claude | Code change |
| Fix price predictor to use real data | Claude | Code change |
| Create Chrome extension icons | Claude | Asset generation |
| Update Chrome extension API URL | Claude | Code change |
| Mark stub platforms as "Coming Soon" | Claude | UI change |
| Fix any bugs found in Phase E walkthrough | Claude | Code changes |
| npm audit fixes | Claude | Dependency updates |
| Write RELEASE.md | Claude + You | Content requires your input |

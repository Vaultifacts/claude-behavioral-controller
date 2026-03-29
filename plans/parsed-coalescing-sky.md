# Cloudflare Exhaustive Audit — VaultLister 3.0

## Context
VaultLister 3.0 is live at `https://vaultlister.com` (Cloudflare → Railway). The app is a Vanilla JS SPA with:
- **Per-request CSP nonces** (`buildCSPWithNonce()` in `securityHeaders.js`) — Cloudflare MUST NOT cache or modify HTML
- **WebSocket** (`wss://vaultlister.com`) for real-time updates
- **Cloudflare R2** (`vaultlister-uploads` bucket) for image storage via S3-compatible API
- **Service Worker** (`public/sw.js` v4.8) with versioned chunk URLs
- **HSTS preload** (`max-age=31536000; includeSubDomains; preload`) set by the app
- **Rate limiting** in-app (30r/s API, 5r/s auth, 10/min AI)
- **Railway** provides valid SSL certificates (important for SSL mode)
- **Chrome extension** makes API calls to vaultlister.com
- **IP extraction** uses `X-Forwarded-For` (not `CF-Connecting-IP`) — potential issue to flag

**Goal:** Review every page/tab in the Cloudflare dashboard. For each setting, document current state and specific recommendation. Prioritize findings as CRITICAL / IMPORTANT / NICE-TO-HAVE.

---

## Execution Method
1. Use Chrome MCP browser automation (user is already logged into Cloudflare)
2. Call `tabs_context_mcp` to find existing Cloudflare tab or create new one
3. Navigate to vaultlister.com zone first, then account-level pages
4. For each section: read page text, note current value, compare against expected
5. Navigate sub-tabs explicitly (e.g., WAF has Custom Rules / Rate Limiting / Managed Rules as separate tabs)
6. Screenshot key pages where visual context helps (SSL mode, DNS records, cache rules)
7. Record findings inline per-section as I go
8. After all sections: run verification curl checks from terminal
9. Compile final prioritized report

**Execution order**: CRITICAL-impact sections first (SSL, Speed, Network, Scrape Shield, Caching), then IMPORTANT, then NICE-TO-HAVE. This ensures the most impactful findings surface early.

---

## Audit Checklist — Every Section

### PHASE 1: Account-Level

#### 1.1 Account Home
- Check plan tier (Free/Pro/Business/Enterprise)
- List all zones
- Check account members and their roles

#### 1.2 R2 Storage (Account Level)
- **Bucket: `vaultlister-uploads`**
  - Location/region
  - Objects count and storage used
  - Public access: should use custom domain (e.g., `images.vaultlister.com`) routed through Cloudflare CDN for performance + caching
  - **CORS policy**: MUST allow `https://vaultlister.com` origin with GET/PUT methods
  - Lifecycle rules: should auto-delete `images/*/temp/*` after 24h
  - R2 API tokens: verify scoped to this bucket only
- Other R2 buckets (if any)

#### 1.3 Account Security
- 2FA status (should be enabled)
- API tokens: audit scope and permissions (least privilege)
- Audit log: review recent entries for anomalies

#### 1.4 Notifications
- Should have alerts configured for:
  - DDoS attack detected
  - SSL certificate expiring
  - Origin health check failure (if configured)
  - Usage/billing alerts

#### 1.5 Billing
- Confirm plan tier and what features are available/locked
- Check for any unexpected charges

#### 1.6 Account Members
- List all members and roles (should be single admin for solo dev)
- Remove any stale/unused members

#### 1.7 Bulk Redirects (Account Level)
- Check for any account-level bulk redirect lists

#### 1.8 Workers & Pages (Account Level)
- List any deployed Workers or Pages projects
- Verify none are stale or conflicting with the zone

---

### PHASE 2: DNS

#### 2.1 DNS Records
For each record, check:
- **A/AAAA/CNAME for `vaultlister.com`**: Must point to Railway. Should be **proxied** (orange cloud) for CDN + DDoS protection
- **A/AAAA/CNAME for `www`**: Should redirect to bare domain (or have redirect rule)
- **CNAME for R2 custom domain** (if exists, e.g., `images.vaultlister.com`)
- **MX records**: Check alignment with Resend (email provider)
- **TXT records**: Must have:
  - **SPF**: `v=spf1 include:_spf.resend.com ~all` (Resend's SPF — verify against Resend's current docs)
  - **DKIM**: Resend DKIM record
  - **DMARC**: `_dmarc.vaultlister.com` TXT `v=DMARC1; p=quarantine; ...`
  - **Domain verification**: Google, Stripe, etc. if needed
- **CAA records**: Consider adding to restrict which CAs can issue certs
- Any stale/unused records to clean up

#### 2.2 DNSSEC
- **Recommended: ON** — prevents DNS spoofing
- Check if DS record is added at registrar

#### 2.3 Email Routing
- Check if Cloudflare Email Routing is configured
- If using Resend for sending, email routing may handle inbound forwarding
- Verify no conflict between Email Routing MX records and Resend's

#### 2.4 Email Security / DMARC Management
- Check Cloudflare's DMARC reporting dashboard (if enabled)
- Review any DMARC reports for spoofing attempts

#### 2.5 Analytics & Logs — DNS Tab
- Check DNS query volume and any anomalies

---

### PHASE 3: SSL/TLS

#### 3.1 SSL/TLS Overview
- **Encryption mode: MUST be "Full (Strict)"**
  - Railway provides valid SSL certs → Full (Strict) is safe and required
  - "Flexible" or "Full" would be insecure (MITM between CF and Railway)
  - **CRITICAL** if not Full (Strict)

#### 3.2 Edge Certificates
- **Always Use HTTPS**: MUST be ON (app requires HTTPS)
- **HTTP Strict Transport Security (HSTS)**:
  - Recommended: Enable with `max-age=31536000`, `includeSubDomains`, `preload`
  - Must match app's setting in `securityHeaders.js:141`
  - Note: App also sets HSTS header — both is fine (defense in depth)
- **Minimum TLS Version**: MUST be TLS 1.2 (TLS 1.0/1.1 have known vulnerabilities; 1.2 is the industry standard minimum)
- **Opportunistic Encryption**: ON (no downside)
- **TLS 1.3**: MUST be ON (performance + security)
- **Automatic HTTPS Rewrites**: ON (complements app's CSP `upgrade-insecure-requests`)
- **Certificate Transparency Monitoring**: ON (alerts if unauthorized cert issued)
- **Universal SSL**: Should be active and valid

#### 3.3 Origin Server
- **Origin Certificates**: Not needed (Railway manages origin SSL)
- **Authenticated Origin Pulls**: OFF (Railway doesn't support this by default)

#### 3.4 Client Certificates
- Not needed for this app (no mTLS requirement)

---

### PHASE 4: Security

#### 4.1 WAF — Custom Rules
- Check for any existing rules
- **Recommended rules to ADD:**
  - Block requests to `/.env`, `/.git`, `/wp-admin`, `/xmlrpc.php` (common attack paths)
  - Consider geo-blocking if app is region-specific

#### 4.2 WAF — Rate Limiting Rules
- Check existing Cloudflare rate limits
- **Recommendation**: Complement (don't duplicate) app-level rate limiting
  - App handles: 30r/s API, 5r/s auth, 10/min AI
  - Cloudflare should catch volumetric attacks BEFORE they reach Railway:
    - `/api/auth/*`: 20 requests/10 seconds per IP (broader than app's 5r/s)
    - `/api/*`: 100 requests/10 seconds per IP (backstop for DDoS)

#### 4.3 WAF — Managed Rules
- **Cloudflare Managed Ruleset**: Should be ON
  - Watch for false positives on:
    - JSON bodies with HTML content (listing descriptions)
    - Large POST bodies (image uploads, up to 10MB)
    - CSRF token headers
  - May need to create exception rules for specific paths
- **OWASP Core Ruleset**: ON if available on plan
  - Sensitivity: Medium (High may cause false positives for JSON API)

#### 4.4 Bots
- **Bot Fight Mode**: ON
  - **CAUTION**: Chrome extension makes programmatic API requests — may need to allowlist the extension's User-Agent or create a skip rule for authenticated API requests
  - Marketplace automation bots (Playwright) run server-side (Railway), not through Cloudflare, so no conflict
- **Super Bot Fight Mode**: Check availability per plan

#### 4.5 DDoS
- **HTTP DDoS Attack Protection**: ON (default), sensitivity: Medium
- **L3/L4 DDoS**: ON (default, can't disable)
- Review override rules if any

#### 4.6 Page Shield
- **Recommended: ON** — monitors for third-party script compromises
- Detects if injected scripts appear on pages

#### 4.7 Security Settings
- **Security Level**: Medium (default is fine; High challenges too many legitimate users)
- **Challenge Passage**: 30 minutes (default is fine)
- **Browser Integrity Check**: ON
  - Should not affect Chrome extension (it sends proper headers)
- **Privacy Pass**: ON (reduces CAPTCHA friction for Cloudflare-trusted users)

#### 4.8 Security — Analytics & Events
- Review recent security events (blocked requests, challenges)
- Check for patterns: repeated attacks on specific paths, credential stuffing attempts
- Note any false positives affecting legitimate traffic

#### 4.9 API Shield
- Check if configured (may not be available on Free plan)
- For future: could validate API schema at edge to block malformed requests

#### 4.10 Leaked Credential Detection
- Check if available and enabled
- Alerts when compromised credentials are used against login endpoints

#### 4.11 Interaction Concerns — CF Challenge Pages vs API Consumers
- **Key risk**: If Cloudflare issues a JS challenge or CAPTCHA to the Chrome extension or API consumers, they cannot solve it programmatically
- **Mitigation**: Ensure Bot Fight Mode / Security Level doesn't trigger challenges on `/api/*` paths when requests include valid `Authorization: Bearer` headers
- Check: Are there WAF exceptions for authenticated API traffic?

---

### PHASE 5: Speed / Performance

#### 5.1 Speed Optimization — Content
- **Auto Minify**:
  - **JavaScript**: OFF — could break SPA chunk loading and service worker
  - **CSS**: OFF — minor benefit, risk of breaking dynamic styles
  - **HTML**: **MUST be OFF** — would corrupt CSP nonces injected by `buildCSPWithNonce()`
  - **CRITICAL** if HTML minification is ON
- **Brotli**: ON (better compression than gzip, all modern browsers support it)
- **Rocket Loader**: **MUST be OFF**
  - Wraps all scripts in deferred loader → breaks SPA architecture
  - Conflicts with CSP nonces and `strict-dynamic`
  - **CRITICAL** if ON
- **Mirage**: OFF (only for Pro+ plans; rewrites image tags, could break SPA image rendering)
- **Polish**: OFF (image optimization — only for Pro+; R2 images served separately)
- **Early Hints**: ON — sends 103 Early Hints for preloading critical resources (free perf win)

#### 5.2 Speed — Observatory
- Review Core Web Vitals scores (LCP, FID/INP, CLS)
- Check CF's optimization recommendations
- Note any actionable suggestions for VaultLister

#### 5.3 Speed Optimization — Protocol
- **HTTP/2**: ON (should be default)
- **HTTP/3 (QUIC)**: ON (faster connections, better on mobile)
- **0-RTT Connection Resumption**: ON
  - Replay attack risk mitigated by CSRF protection in the app
  - Significant performance benefit for returning visitors

---

### PHASE 6: Caching

#### 6.1 Caching Configuration
- **Caching Level**: Standard (uses query string — correct since SW uses `?v=` versioning)
- **Browser Cache TTL**: "Respect Existing Headers"
  - App sets `Cache-Control: public, max-age=31536000, immutable` for static assets
  - App sets `Cache-Control: no-store, no-cache, must-revalidate` for API/HTML responses
  - Cloudflare must NOT override these with its own TTL
  - **IMPORTANT** if set to anything other than "Respect Existing Headers"
- **Always Online**: **OFF**
  - Shows cached page when origin is down — but cached HTML would have stale CSP nonces
  - SPA needs live API responses; stale pages create confusing UX
  - The service worker already provides offline fallback (`offline.html`)
- **Development Mode**: **OFF** in production (disables caching, minification — only for debugging)
- **Crawler Hints**: ON if available (helps search engines discover fresh content)

#### 6.2 Cache Rules (CRITICAL section)
- Must have rules to ensure:
  1. **Bypass cache for `/api/*`** — API responses are dynamic, authenticated, contain CSRF tokens
  2. **Bypass cache for HTML** — CSP nonces are per-request; cached HTML = shared nonces = security vulnerability
  3. **Bypass cache for `/sw.js`** — Service worker must always fetch fresh to enable updates (or short TTL)
  4. **Cache static assets** — `.js`, `.css`, `.png`, `.svg`, `.woff2` etc. with Edge TTL respecting origin headers
- If no cache rules exist → **CRITICAL finding** (Cloudflare may cache HTML by default with standard caching level)

**Specific cache rules to create (if missing):**

Note: Cloudflare Cache Rules evaluate on **request** fields only (not response headers like `content_type`). Rules must use URL path patterns.

Rule 1 — "Bypass API, SW, and non-static paths" (higher priority):
```
When: (http.request.uri.path starts with "/api/")
   or (http.request.uri.path eq "/sw.js")
   or (http.request.uri.path eq "/")
   or (http.request.uri.path eq "/index.html")
   or (http.request.uri.path eq "/offline.html")
   or (http.request.uri.path eq "/manifest.webmanifest")
Then: Cache eligibility = Bypass cache
```

Rule 2 — "Cache static assets" (lower priority):
```
When: (http.request.uri.path.extension in {"js" "css" "png" "jpg" "jpeg" "gif" "svg" "ico" "woff" "woff2" "ttf" "webp" "avif"})
Then: Cache eligibility = Eligible for cache
      Edge TTL = Use cache-control header if present, use default Cloudflare caching behavior if not
      Browser TTL = Respect origin
```

Note: Cloudflare's **default behavior** already does NOT cache HTML or JSON API responses — only known static extensions. But explicit rules are defense-in-depth: they make behavior visible, protect against CF default changes, and ensure `/sw.js` (which has `.js` extension) is excluded from caching.

**Interaction concerns for caching:**
- **Set-Cookie responses**: Cloudflare should NOT cache responses containing `Set-Cookie` headers (auth endpoints). Verify CF respects the `no-store` directive on these.
- **Vary header**: App may send `Vary: Accept-Encoding`. CF handles this correctly by default, but verify.
- **Compression**: Cloudflare compresses at the edge (Brotli/gzip). The app's nginx config also has gzip. Since Railway is the origin (not nginx), check whether Railway sends compressed responses — if so, CF should handle `Accept-Encoding` properly without double-compression.

#### 6.3 Tiered Cache
- **Enable Smart Tiered Cache** — reduces origin load by serving from upper-tier CF data centers
- Free on all plans

#### 6.4 Purge Cache
- Note: after each deployment, may need to purge cache for updated static assets
  - Or: use versioned filenames (the app already does this with `?v=d4d0be7e` query params)

---

### PHASE 7: Rules

#### 7.1 Page Rules (Legacy — being deprecated)
- Document any existing rules
- Recommend migrating to modern Cache Rules / Configuration Rules

#### 7.2 Configuration Rules
- Check for path-specific setting overrides

#### 7.3 Transform Rules
- **Managed Transforms**: Check if "Add visitor location headers" is enabled
  - Adds `CF-IPCountry` header — useful for geo-based analytics
- **Request Header Modifications**: Could add `True-Client-IP` header forwarding
- **Response Header Modifications**: Check for any header stripping/adding

#### 7.4 Redirect Rules
- Should have: `www.vaultlister.com` → `vaultlister.com` (301 redirect)
  - May already be handled by DNS CNAME + page rule
  - Verify this is in place

#### 7.5 Origin Rules
- Not needed unless Railway requires specific Host header

#### 7.6 Compression Rules
- Check if any custom compression rules exist
- Default Cloudflare compression (Brotli) should be sufficient

#### 7.7 Snippets
- Check for any active snippets (edge-injected JavaScript/HTML)
- **Risk**: Snippets modify responses at the edge — could conflict with CSP nonces
- Should be empty unless specifically configured

---

### PHASE 8: Network

#### 8.1 Network Settings
- **HTTP/2**: ON
- **HTTP/3**: ON
- **WebSockets**: **MUST be ON** — app uses `wss://vaultlister.com` for real-time updates
  - **CRITICAL** if OFF
  - Note: Free plan has 100-second idle timeout for WebSocket connections
- **gRPC**: OFF (not used)
- **0-RTT**: ON (covered in Speed)
- **IP Geolocation**: ON (adds `CF-IPCountry` header — useful for analytics)
- **Onion Routing**: ON (allows Tor users to access site via Cloudflare)
- **Pseudo IPv4**: OFF (not needed)
- **Network Error Logging**: ON if available
- **Max Upload Size**: Check plan limit (Free = 100MB, app allows 10MB max — fine)

---

### PHASE 9: Scrape Shield

#### 9.1 Email Address Obfuscation
- **MUST be OFF**
  - Modifies HTML to obfuscate email addresses with JavaScript
  - Will break SPA rendering — injects scripts that conflict with CSP nonces
  - **CRITICAL** if ON

#### 9.2 Server-Side Excludes
- **MUST be OFF**
  - Modifies HTML based on visitor trust score
  - Dangerous for SPA — can remove content, break JavaScript
  - **CRITICAL** if ON

#### 9.3 Hotlink Protection
- **OFF** (or ON with care)
  - If R2 images are served through Cloudflare (custom domain), hotlink protection could block marketplace sites from loading product images
  - Only enable if you want to prevent image theft and won't be embedding images on third-party marketplaces

---

### PHASE 10: Traffic

#### 10.1 Health Checks
- **Recommended: Create one** for `https://vaultlister.com/api/health`
  - Interval: 60 seconds
  - Expected response: 200 with `{"status":"healthy"}`
  - Notification on failure
  - Railway already has its own health check, but Cloudflare's is independent monitoring

#### 10.2 Load Balancing
- Not needed (single Railway origin)

#### 10.3 Waiting Room
- Not needed unless expecting traffic spikes (launch day, viral moment)

#### 10.4 Argo Smart Routing
- Check if enabled (paid add-on)
- Routes traffic through Cloudflare's fastest paths — can reduce latency by 30%+
- Nice-to-have if budget allows

---

### PHASE 11: Workers & Pages

#### 11.1 Workers Routes
- Check for any active workers
- **Future consideration**: Could use a Worker for:
  - Edge-side image resizing (instead of sharp on Railway)
  - A/B testing at edge
  - Custom cache logic

---

### PHASE 12: Additional Sections

#### 12.1 Web Analytics
- **Recommended: Enable** — privacy-focused, no cookies, free
- Supplements Sentry for performance monitoring

#### 12.2 Zaraz
- Check if configured
- Could manage Sentry/Stripe script loading at the edge for better performance

#### 12.3 Turnstile
- **Consider for future**: CAPTCHA alternative for registration/login
- Better UX than traditional CAPTCHA, integrates with Cloudflare

#### 12.4 Analytics & Logs — Main Page
- Review traffic analytics (requests, bandwidth, unique visitors)
- Check security analytics (threats blocked, bot scores)
- Check performance analytics (TTFB, cache hit ratio)
- Note any anomalies or trends

#### 12.5 Spectrum
- Not applicable (Spectrum is for non-HTTP TCP/UDP protocols)
- Confirm no Spectrum apps are configured for this zone

#### 12.6 Not Applicable / Explicitly Skipped Sections
These Cloudflare features are documented as not relevant to VaultLister:
- **D1 (Serverless DB)**: App uses Railway PostgreSQL
- **Stream**: No video hosting/streaming
- **Images (CF Images product)**: Using R2 directly, not CF Images
- **Calls**: No WebRTC/calling features
- **Custom Hostnames**: Enterprise feature, not needed
- **Load Balancing**: Single origin (Railway)
- **Spectrum**: HTTP-only app
- **Access / Zero Trust**: No internal-only endpoints requiring Zero Trust access
- **vaultlister-worker**: Internal Railway service (BullMQ + Playwright bots); no external domain, no Cloudflare DNS needed

---

## All Items by Priority

### CRITICAL (app breaks or security vulnerability if wrong)

| # | Section | Setting | Required Value | Why |
|---|---------|---------|---------------|-----|
| C1 | SSL/TLS 3.1 | Encryption Mode | Full (Strict) | Railway has valid SSL; anything else allows MITM |
| C2 | Speed 5.1 | Rocket Loader | OFF | Wraps scripts in deferred loader → breaks SPA + CSP nonces |
| C3 | Speed 5.1 | Auto Minify HTML | OFF | Corrupts per-request CSP nonces in HTML responses |
| C4 | Network 8.1 | WebSockets | ON | App requires `wss://` for real-time features |
| C5 | Scrape Shield 9.1 | Email Address Obfuscation | OFF | Injects JS into HTML that breaks SPA + CSP |
| C6 | Scrape Shield 9.2 | Server-Side Excludes | OFF | Strips HTML content based on trust score, breaks SPA |
| C7 | Caching 6.2 | Cache Rule: `/api/*` | Bypass cache | API responses are dynamic, authenticated, contain CSRF tokens |
| C8 | Caching 6.2 | Cache Rule: HTML responses | Bypass cache | CSP nonces are per-request; cached HTML = shared nonces |
| C9 | Caching 6.2 | Cache Rule: `/sw.js` | Bypass or short TTL | SW must fetch fresh to enable updates |
| C10 | Caching 6.1 | Always Online | OFF | Stale HTML = stale nonces = broken CSP security |
| C11 | SSL/TLS 3.2 | Always Use HTTPS | ON | App requires HTTPS; all auth tokens sent over TLS only |
| C12 | Caching 6.1 | Development Mode | OFF | Disables all caching/optimization; must be OFF in production |
| C13 | Rules 7.7 | Snippets | Empty / none active | Edge-injected JS/HTML would break CSP nonces |

### IMPORTANT (degraded security, performance, or reliability if wrong)

| # | Section | Setting | Required Value | Why |
|---|---------|---------|---------------|-----|
| I1 | Caching 6.1 | Browser Cache TTL | Respect Existing Headers | App sets proper Cache-Control; CF override breaks caching strategy |
| I2 | SSL/TLS 3.2 | Minimum TLS Version | 1.2 | TLS 1.0/1.1 have known vulnerabilities; 1.2 is industry minimum |
| I3 | SSL/TLS 3.2 | TLS 1.3 | ON | Performance + security improvement; no downside |
| I4 | SSL/TLS 3.2 | HSTS | max-age=31536000, includeSubDomains, preload | Must match app's `securityHeaders.js:141`; defense in depth |
| I5 | Speed 5.1 | Auto Minify JS | OFF | Could break SPA chunk loading and service worker |
| I6 | Speed 5.1 | Auto Minify CSS | OFF | Minor benefit vs risk of breaking dynamic styles |
| I7 | Speed 5.1 | Brotli | ON | Better compression than gzip; all modern browsers support |
| I8 | DNS 2.1 | Proxy status (orange cloud) | Proxied | Required for CDN, DDoS protection, WAF, caching |
| I9 | DNS 2.1 | SPF record | Present + correct for Resend | Prevents email spoofing from vaultlister.com |
| I10 | DNS 2.1 | DKIM record | Present + correct for Resend | Email authentication; deliverability |
| I11 | DNS 2.1 | DMARC record | `v=DMARC1; p=quarantine` minimum | Prevents domain abuse for phishing |
| I12 | DNS 2.2 | DNSSEC | ON (with DS at registrar) | Prevents DNS cache poisoning/spoofing |
| I13 | Security 4.1 | WAF Custom Rules | Block `/.env`, `/.git`, `/wp-admin`, `/xmlrpc.php` | Common attack paths; stops probing before it hits Railway |
| I14 | Security 4.3 | WAF Managed Rules | ON | Protects against common exploits (SQLi, XSS at edge) |
| I15 | Security 4.4 | Bot Fight Mode | ON | Blocks automated credential stuffing, scraping |
| I16 | Security 4.5 | HTTP DDoS Protection | ON, sensitivity Medium | Default protection against volumetric attacks |
| I17 | Security 4.7 | Browser Integrity Check | ON | Blocks requests with suspicious/missing headers |
| I18 | SSL/TLS 3.2 | Automatic HTTPS Rewrites | ON | Fixes mixed content; complements CSP upgrade-insecure-requests |
| I19 | SSL/TLS 3.2 | Certificate Transparency Monitoring | ON | Alerts if unauthorized cert issued for domain |
| I20 | Rules 7.4 | www → bare domain redirect | 301 redirect in place | Canonical URL; prevents duplicate content/cookies |
| I21 | R2 1.2 | CORS policy | Allow `https://vaultlister.com` + GET/PUT | Required for browser-based R2 image access |
| I22 | R2 1.2 | API token scope | Bucket-scoped only | Least privilege; limits blast radius if token leaked |
| I23 | Account 1.3 | 2FA | Enabled | Account compromise = full domain takeover |
| I24 | Caching 6.3 | Smart Tiered Cache | ON | Reduces origin load; free on all plans |
| I25 | Security 4.2 | Rate Limiting Rules | Add edge rate limits for `/api/auth/*` and `/api/*` | Stops volumetric attacks before they consume Railway resources |
| I26 | SSL/TLS 3.2 | Opportunistic Encryption | ON | No downside; allows HTTP/2 for more clients |
| I27 | SSL/TLS 3.2 | Universal SSL | Active + valid | Edge certificate must be valid for HTTPS to work |
| I28 | Security 4.11 | CF challenges vs API | WAF exception for authenticated `/api/*` | Chrome extension and API consumers can't solve JS challenges |
| I29 | Account 1.6 | Account Members | Audit — single admin for solo dev | Remove stale/unused members |

### NICE-TO-HAVE (optimization, future-proofing, best practice)

| # | Section | Setting | Recommended Value | Why |
|---|---------|---------|------------------|-----|
| N1 | Speed 5.1 | Early Hints | ON | 103 Early Hints preload critical resources; free perf win |
| N2 | Speed 5.2 | HTTP/3 (QUIC) | ON | Faster connections, especially on mobile/lossy networks |
| N3 | Speed 5.2 | 0-RTT Connection Resumption | ON | Faster TLS handshakes for returning visitors; CSRF mitigates replay risk |
| N4 | Network 8.1 | IP Geolocation | ON | Adds CF-IPCountry header; useful for analytics |
| N5 | Network 8.1 | Onion Routing | ON | Allows Tor users to access site via Cloudflare |
| N6 | Speed 5.1 | Mirage | OFF | Pro+ only; rewrites img tags, could break SPA |
| N7 | Speed 5.1 | Polish | OFF | Pro+ only; R2 images served separately |
| N8 | Network 8.1 | gRPC | OFF | Not used by app |
| N9 | Network 8.1 | Pseudo IPv4 | OFF | Not needed |
| N10 | Security 4.6 | Page Shield | ON | Monitors for third-party script compromises; early warning |
| N11 | Security 4.7 | Security Level | Medium | High challenges too many legitimate users |
| N12 | Security 4.7 | Challenge Passage | 30 minutes | Default is fine; balances security vs friction |
| N13 | Security 4.7 | Privacy Pass | ON | Reduces CAPTCHA friction for Cloudflare-trusted users |
| N14 | Traffic 10.1 | Health Check | Create for `/api/health` (60s interval) | Independent monitoring beyond Railway's built-in check |
| N15 | Analytics 12.1 | Web Analytics | Enable | Privacy-focused, no cookies, free; supplements Sentry |
| N16 | Rules 7.3 | Managed Transforms: Visitor Location | ON | Adds geo headers; useful for analytics |
| N17 | Rules 7.3 | Managed Transforms: True-Client-IP | ON | Reliable client IP forwarding to origin |
| N18 | Scrape Shield 9.3 | Hotlink Protection | OFF | Could block marketplace sites from loading product images |
| N19 | R2 1.2 | Lifecycle rules | Auto-delete `temp/*` after 24h | Prevents orphaned temp uploads from accumulating |
| N20 | R2 1.2 | Custom domain | `images.vaultlister.com` | CDN caching + cleaner URLs for R2-served images |
| N21 | Account 1.4 | Notifications | DDoS, SSL expiry, origin down, billing | Early warning for incidents |
| N22 | 12.2 | Zaraz | Evaluate | Could manage Sentry/Stripe at edge for better perf |
| N23 | 12.3 | Turnstile | Evaluate for future | Better CAPTCHA alternative for registration/login |
| N24 | DNS 2.1 | CAA records | Add `0 issue "letsencrypt.org"` (or CF's CA) | Restricts which CAs can issue certs for domain |
| N25 | Rules 7.1 | Page Rules (legacy) | Migrate to modern rules | Page Rules being deprecated; migrate to Cache/Config Rules |
| N26 | Workers 11.1 | Workers Routes | Audit any active | Ensure no stale/orphaned workers |
| N27 | Caching 6.1 | Caching Level | Standard | Uses query string in cache key; matches SW `?v=` versioning |
| N28 | Caching 6.1 | Crawler Hints | ON | Helps search engines discover fresh content |
| N29 | Traffic 10.4 | Argo Smart Routing | Evaluate (paid) | Reduces latency by routing through fastest CF paths |
| N30 | Security 4.9 | API Shield | Evaluate | Schema validation at edge; future hardening |
| N31 | Security 4.10 | Leaked Credential Detection | ON if available | Alerts when compromised credentials used on login |
| N32 | DNS 2.3 | Email Routing | Check for conflicts | Ensure no conflict between CF Email Routing and Resend MX |
| N33 | Account 1.7 | Bulk Redirects | Audit | Ensure no stale account-level redirects |
| N34 | Account 1.8 | Workers & Pages (account) | Audit | Ensure no stale Workers/Pages conflicting with zone |
| N35 | Rules 7.6 | Compression Rules | Check | Default CF compression should be sufficient |

### NOT APPLICABLE (confirmed skipped with reason)

| Section | Feature | Why Skipped |
|---------|---------|-------------|
| Spectrum | L4 TCP/UDP proxy | HTTP-only app; no non-HTTP protocols |
| D1 | Serverless database | App uses Railway PostgreSQL |
| Stream | Video hosting | No video features |
| Images | CF Images product | Using R2 directly for image storage |
| Calls | WebRTC | No calling features |
| Custom Hostnames | Enterprise multi-tenant | Single-tenant app |
| Load Balancing | Multi-origin | Single Railway origin |
| Access / Zero Trust | Internal access control | No internal-only endpoints |
| Client Certificates | mTLS | No mutual TLS requirement |
| Origin Certificates | CF-issued origin cert | Railway manages origin SSL |
| Authenticated Origin Pulls | mTLS to origin | Railway doesn't support this |

### Codebase Recommendations (flagged during audit, not Cloudflare settings)

| # | File | Current | Recommended | Priority |
|---|------|---------|-------------|----------|
| R1 | `server.js:1187` | Uses `X-Forwarded-For` only | Also check `CF-Connecting-IP` (Cloudflare-set, unforgeable by end users) | IMPORTANT |
| R2 | `.env` / `R2_PUBLIC_URL` | Plain R2 URL | Set up `images.vaultlister.com` custom domain via Cloudflare for CDN caching | NICE-TO-HAVE |

---

## Verification (run after reviewing all settings)

### Security Checks
1. `curl -sI https://vaultlister.com` — verify headers:
   - `Strict-Transport-Security` present (HSTS)
   - `Content-Security-Policy` present with nonce (CSP)
   - `CF-Ray` present (confirms Cloudflare proxy is active)
   - `Server: cloudflare` (confirms proxied mode)
   - No duplicate HSTS headers (one from CF, one from app)
2. `curl -sI http://vaultlister.com` — should 301 redirect to HTTPS
3. `curl -sI https://www.vaultlister.com` — should 301 redirect to bare domain
4. `curl -sI https://vaultlister.com/.env` — should be blocked by WAF (403) or return 404
5. `curl -sI https://vaultlister.com/.git/config` — should be blocked by WAF (403) or return 404

### Caching Checks
6. `curl -sI https://vaultlister.com/api/health` — verify:
   - `CF-Cache-Status: DYNAMIC` (not HIT/MISS — API must not be cached)
   - `Cache-Control: no-store` from origin is respected
7. `curl -sI https://vaultlister.com/core-bundle.js?v=d4d0be7e` — verify:
   - `CF-Cache-Status: HIT` or `MISS` (static assets should be cacheable)
   - `Cache-Control: public, max-age=31536000, immutable`
8. `curl -sI https://vaultlister.com/` — verify HTML response:
   - `CF-Cache-Status: DYNAMIC` or `BYPASS` (HTML must NOT be cached)
   - Contains CSP nonce in headers
9. `curl -sI https://vaultlister.com/sw.js` — verify:
   - `CF-Cache-Status: DYNAMIC` or `BYPASS` (SW must not be edge-cached)

### DNS Checks
10. `dig +short vaultlister.com` — verify resolves to Cloudflare IPs (proxied)
11. `dig TXT vaultlister.com` — verify SPF record present
12. `dig TXT _dmarc.vaultlister.com` — verify DMARC record present
13. `dig +dnssec vaultlister.com` — verify DNSSEC signatures present (if enabled)

### WebSocket Check
14. Browser devtools Network tab — navigate to app, filter WS, verify WebSocket connection established to `wss://vaultlister.com/ws`

### R2 Check
15. `curl -sI -H "Origin: https://vaultlister.com" [R2_PUBLIC_URL]/test` — verify CORS headers present (`Access-Control-Allow-Origin`)

### SSL Check
16. `curl -sI https://vaultlister.com -v 2>&1 | grep "SSL connection\|TLS"` — verify TLS 1.3 negotiated

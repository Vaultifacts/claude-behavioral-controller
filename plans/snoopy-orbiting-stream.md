# Plan: Wire Redis Into All Applicable Consumers

## Context

Redis infrastructure is fully in place (Docker container in docker-compose.yml, `ioredis` ^5.9.2 in package.json, `redis.js` service with full CRUD + in-memory fallback) but **zero consumers** actually use it. The server spams connection errors every ~4 seconds because Redis isn't running locally, and when it does run (in Docker), nothing talks to it anyway.

**Goal:** Wire Redis into every in-memory store that should use it, so the app is production-ready with no further Redis work needed. All wired consumers automatically fall back to in-memory when Redis is unavailable (dev mode), so nothing breaks.

---

## What Gets Wired (7 consumers)

### HIGH Priority (security-sensitive — loss on restart = vulnerability or broken auth flow)
| # | File | What | Key prefix | TTL |
|---|------|------|-----------|-----|
| 1 | `src/backend/middleware/rateLimiter.js` | Request counts + IP blocks | `rl:` / `rl:block:` | 1hr / 1hr |
| 2 | `src/backend/services/enhancedMFA.js` | WebAuthn challenge nonces | `mfa:challenge:` | 2min |
| 3 | `src/backend/routes/socialAuth.js` | OAuth CSRF state tokens | `oauth:state:` | 10min |
| 4 | `src/backend/server.js` | Idempotency cache | `idempotency:` | 5min |

### MEDIUM Priority (performance — loss on restart = cold cache, slower responses)
| # | File | What | Key prefix | TTL |
|---|------|------|-----------|-----|
| 5 | `src/backend/routes/analytics.js` | Analytics query cache | `cache:analytics:` | 5min |
| 6 | `src/backend/routes/barcode.js` | Barcode lookup cache | `cache:barcode:` | 24hr |
| 7 | `src/backend/routes/receiptParser.js` | Upload rate limiter | `rl:receipt:` | 1min |

### REMOVED from plan (verified reasons)
- **Rate limit dashboard stats** (`rateLimitDashboard.js`) — `trackRateLimitHit()` is exported but **never called** from any file. The stats Maps are always empty. Dead code.
- **Monitoring metrics** (`monitoring.js`) — CPU/memory are process-specific; comment says "in-memory for demo, use Redis in production" but the metrics (latency arrays, error lists) are process-bound
- **Feature flags cache** (`featureFlags.js`) — 1-min SQLite polling is fine for single server
- **Circuit breaker** (`circuitBreaker.js`) — resetting to CLOSED on restart is safe default
- **gzipCache** (`server.js:710`) — binary buffers, faster from memory
- **WebSocket connections** (`websocket.js`) — can't serialize WS objects
- **Apple JWKS cache** (`socialAuth.js:16`) — one HTTP call to re-fetch

---

## Files Modified (complete list)

### Production code (10 files)
| File | Change type |
|------|------------|
| `src/backend/services/redis.js` | Add `getJson`/`setJson`/`flushAll` helpers |
| `.env.example` | Add `REDIS_PASSWORD` documentation |
| `src/backend/services/enhancedMFA.js` | Replace `challenges` Map with Redis |
| `src/backend/routes/socialAuth.js` | Replace `stateTokens` Map with Redis |
| `src/backend/routes/receiptParser.js` | Replace `receiptUploadLimiter` Map with Redis |
| `src/backend/routes/barcode.js` | Replace `barcodeCache` Map with Redis |
| `src/backend/routes/analytics.js` | Replace `_analyticsCache` Map with Redis |
| `src/backend/server.js` | Replace `idempotencyCache` Map with Redis |
| `src/backend/middleware/rateLimiter.js` | Replace `requests`+`blocklist` Maps with Redis, make async |
| `src/backend/routes/auth.js` | Add `await` to 5 `applyRateLimit()` calls |

### Route files needing `await applyRateLimit()` (4 more files)
| File | Lines | Call count |
|------|-------|-----------|
| `src/backend/routes/extension.js` | 20 | 1 |
| `src/backend/routes/monitoring.js` | 229 | 1 |
| `src/backend/routes/roadmap.js` | 114 | 1 |
| `src/backend/routes/security.js` | 76, 126, 174, 274 | 4 |

### Test files (6 files)
| File | Change |
|------|--------|
| `src/tests/service-redis.test.js` | Add tests for `getJson`/`setJson`/`flushAll` |
| `src/tests/middleware-rateLimiter.test.js` | Add `await` to 15 method calls, `redis.flushAll()` in `beforeEach`, update `getStats`/`cleanup` tests |
| `src/tests/security-rate-limit.test.js` | Add `await` to ~30 `check()` calls + 6 `middleware(ctx)` calls, `redis.flushAll()` in 5 `beforeEach` blocks |
| `src/tests/middleware-shutdown.test.js` | Update shutdown test (no more `_cleanupInterval`) |
| `src/tests/service-enhancedMFA-unit.test.js` | Remove/update `cleanupChallenges` tests (lines 738-753) |
| `src/tests/arch-caching-etag.test.js` | Add `await` to 11 `check()` calls, remove `_cleanupInterval` refs, replace `limiter.requests.get()` + `entry.resetTime = 0` hack |

---

## Implementation Steps

### Step 1: Add `getJson`/`setJson` helpers to redis.js
**File:** `src/backend/services/redis.js`

Most consumers store objects, not strings. Add three methods after the existing `exists()` function — insert between line 218 (`}` closing `exists`) and line 220 (`/** Clean expired entries...`). Use `export` to match the existing pattern (`export async function get`, `export async function set`, etc.):
```js
export async function getJson(key) {
    const raw = await get(key);
    if (!raw) return null;
    try { return JSON.parse(raw); } catch { return null; }
}

export async function setJson(key, value, ttlSeconds = 3600) {
    return set(key, JSON.stringify(value), ttlSeconds);
}

export function flushAll() {
    memoryStore.clear();
    memoryExpiry.clear();
}
```
Add all three to the default export object at line 253: `getJson, setJson, flushAll`.

**Why `flushAll()` is needed:** In the old code, `new RateLimiter()` created fresh `this.requests` and `this.blocklist` Maps — each test got clean state via `beforeEach`. In the new code, all `RateLimiter` instances share the redis.js `memoryStore`. Without `flushAll()`, rate limit entries from test N would leak into test N+1 within the same file, causing test failures (e.g., `remaining` count would be wrong because the key already has hits from the previous test).

---

### Step 2: Add `REDIS_PASSWORD` to `.env.example`
**File:** `.env.example`

Both `docker-compose.yml` (line 84) and `docker-compose.staging.yml` (line 91) require `REDIS_PASSWORD` via `${REDIS_PASSWORD:?REDIS_PASSWORD must be set}`, but it's not documented. Add after line 91 (`# REDIS_URL=redis://:password@hostname:6379`), within the existing Redis section:
```
REDIS_PASSWORD=your-redis-password-here
```

---

### Step 3: Wire WebAuthn challenges (enhancedMFA.js)
**File:** `src/backend/services/enhancedMFA.js`

**Current state:** `challenges` Map at line 15. Used by 4 async methods + `cleanupChallenges()`.

**Import to add (after line 7):**
```js
import redis from './redis.js';
```

**Remove:**
- Lines 14-15: Comment `// Challenge store (in production, use Redis)` and `const challenges = new Map();` — we ARE now using Redis
- Lines 517-524: `cleanupChallenges()` method entirely
- Lines 66-67: Comment `// Clean old challenges` and `this.cleanupChallenges();` call inside `startRegistration()`

**Replace 8 Map operations:**

| Location | Old | New |
|----------|-----|-----|
| Line 60 (startRegistration) | `challenges.set(userId, { challenge, type: 'registration', timestamp: Date.now() })` | `await redis.setJson('mfa:challenge:' + userId, { challenge, type: 'registration', timestamp: Date.now() }, 120)` |
| Line 101 (completeRegistration) | `const stored = challenges.get(userId)` | `const stored = await redis.getJson('mfa:challenge:' + userId)` |
| Line 107 (completeRegistration) | `challenges.delete(userId)` | `await redis.del('mfa:challenge:' + userId)` |
| Line 111 (completeRegistration) | `challenges.delete(userId)` | `await redis.del('mfa:challenge:' + userId)` |
| Line 153 (startAuthentication) | `challenges.set(userId, { challenge, type: 'authentication', timestamp: Date.now() })` | `await redis.setJson('mfa:challenge:' + userId, { challenge, type: 'authentication', timestamp: Date.now() }, 120)` |
| Line 174 (completeAuthentication) | `const stored = challenges.get(userId)` | `const stored = await redis.getJson('mfa:challenge:' + userId)` |
| Line 180 (completeAuthentication — expired path) | `challenges.delete(userId)` | `await redis.del('mfa:challenge:' + userId)` |
| Line 184 (completeAuthentication) | `challenges.delete(userId)` | `await redis.del('mfa:challenge:' + userId)` |

**No production caller changes needed** — all 4 consuming methods are already async.

**Test impact:**
- `src/tests/service-enhancedMFA-unit.test.js` lines 741-753: Tests `cleanupChallenges()` directly. Since we're removing this method, these 2 tests (`does not throw when called directly`, `is called during startRegistration`) must be removed. The `startRegistration` test on line 746 will still work since `startRegistration` no longer calls `cleanupChallenges`.
- `src/tests/enhancedMFA-expanded.test.js`: Integration tests via HTTP — unaffected (Redis falls back to in-memory in tests)
- `src/tests/enhancedMFA.test.js`: Integration tests via HTTP — unaffected

---

### Step 4: Wire OAuth state tokens (socialAuth.js)
**File:** `src/backend/routes/socialAuth.js`

**Current state:** `stateTokens` Map at line 46. `generateStateToken()` (line 51, synchronous) and `verifyStateToken()` (line 73, synchronous) are module-level functions. NOTE: This is a DIFFERENT `generateStateToken` from the one in `utils/encryption.js` — the test `googleOAuth.test.js` mocks the encryption.js one, not this one.

**Import to add (after line 9):**
```js
import redis from '../services/redis.js';
```

**Remove:**
- Line 46: `const stateTokens = new Map();`
- Line 49: `const MAX_STATE_TOKENS = 10000;`

**Replace `generateStateToken()` (lines 51-70):**
```js
async function generateStateToken() {
    const state = crypto.randomBytes(32).toString('hex');
    await redis.setJson('oauth:state:' + state, { created: Date.now() }, 600);
    return state;
}
```
Removes: for-loop cleanup (lines 55-58), max-size check (lines 62-65) — Redis TTL handles both.

**Replace `verifyStateToken()` (lines 73-80):**
```js
async function verifyStateToken(state) {
    const tokenData = await redis.getJson('oauth:state:' + state);
    if (!tokenData) return false;
    await redis.del('oauth:state:' + state);
    return Date.now() - tokenData.created < 600000;
}
```

**Caller changes (4 sites, all inside async `socialAuthRouter`):**
| Line | Old | New |
|------|-----|-----|
| 144 | `const state = generateStateToken();` | `const state = await generateStateToken();` |
| 176 | `if (!verifyStateToken(state))` | `if (!(await verifyStateToken(state)))` |
| 280 | `const state = generateStateToken();` | `const state = await generateStateToken();` |
| 311 | `if (!verifyStateToken(state))` | `if (!(await verifyStateToken(state)))` |

**Test impact:**
- `src/tests/socialAuth.test.js`: Integration tests via HTTP — unaffected
- `src/tests/googleOAuth.test.js`: Mocks `utils/encryption.js` `generateStateToken`, NOT this file's function — unaffected
- `src/tests/service-encryption.test.js`: Tests `utils/encryption.js` — unaffected

---

### Step 5: Wire receipt upload limiter (receiptParser.js)
**File:** `src/backend/routes/receiptParser.js`

**Current state:** `receiptUploadLimiter` Map (line 12), cleanup interval (lines 16-24), `checkReceiptRateLimit()` sync function (lines 26-41). Called once at line 178.

**Import to add (after line 5):**
```js
import redis from '../services/redis.js';
```

**Remove:**
- Line 12: `const receiptUploadLimiter = new Map();`
- Lines 16-24: cleanup interval
- Lines 26-41: entire `checkReceiptRateLimit()` function

**Replace with:**
```js
async function checkReceiptRateLimit(userId) {
    const key = 'rl:receipt:' + userId;
    const count = await redis.incr(key);
    if (count === 1) await redis.expire(key, 60); // 1-minute window
    return count <= 5;
}
```
Note: `redis.incr()` returns a number in both Redis and in-memory fallback (verified at redis.js:160-163).

**Caller change (1 site):**
- Line 178: `if (!checkReceiptRateLimit(user.id))` → `if (!(await checkReceiptRateLimit(user.id)))`
  - Already inside async `receiptParserRouter` — just add `await`

**Test impact:** No tests exist for `checkReceiptRateLimit` or `receiptUploadLimiter`.

---

### Step 6: Wire barcode cache (barcode.js)
**File:** `src/backend/routes/barcode.js`

**Current state:** `barcodeCache` Map (line 7), `CACHE_TTL` (line 8), `MAX_CACHE_SIZE` (line 9), `cacheSet()` helper (lines 11-17). Read at line 28, write at lines 54, 67, 121.

**Import to add (after line 3):**
```js
import redis from '../services/redis.js';
```

**Remove:**
- Lines 7-17: `barcodeCache` Map, `CACHE_TTL`, `MAX_CACHE_SIZE`, `cacheSet()` function

**Replace reads (1 site):**
| Line | Old | New |
|------|-----|-----|
| 28-29 | `const cached = barcodeCache.get(barcode); if (cached && Date.now() - cached.timestamp < CACHE_TTL)` | `const cached = await redis.getJson('cache:barcode:' + barcode); if (cached)` |

Remove the timestamp check — Redis TTL handles expiry.

**Replace writes (3 sites):**
| Line | Old | New |
|------|-----|-----|
| 54 | `cacheSet(barcode, { data, timestamp: Date.now() })` | `await redis.setJson('cache:barcode:' + barcode, data, 86400)` |
| 67 | `cacheSet(barcode, { data: externalData, timestamp: Date.now() })` | `await redis.setJson('cache:barcode:' + barcode, externalData, 86400)` |
| 121 | `cacheSet(barcode, { data, timestamp: Date.now() })` | `await redis.setJson('cache:barcode:' + barcode, data, 86400)` |

Note: Store the data object directly (not `{ data, timestamp }`). The read also changes:

**Read-side data shape change (line 33):**
| Line | Old | New |
|------|-----|-----|
| 33 | `...cached.data,` | `...cached,` |

This is critical — without this change, `cached.data` would be `undefined` (since we now store the data directly, not wrapped in `{ data, timestamp }`).

**All sites are inside async `barcodeRouter`** — just add `await`.

**Test impact:** No tests exist for `barcodeCache` or `cacheSet`.

---

### Step 7: Wire analytics cache (analytics.js)
**File:** `src/backend/routes/analytics.js`

**Current state:** `_analyticsCache` Map (line 11), `ANALYTICS_CACHE_TTL_MS` (line 10), `MAX_ANALYTICS_CACHE_SIZE` (line 24), `_cacheKey()` (line 13), `_getCached()` (line 17), `_setCached()` (line 26), `invalidateAnalyticsCache()` (line 48 — exported but **never called** from any other file).

**Import to add (after line 5):**
```js
import redis from '../services/redis.js';
```

**Remove:**
- Lines 10-11: `ANALYTICS_CACHE_TTL_MS`, `_analyticsCache` Map
- Line 24: `MAX_ANALYTICS_CACHE_SIZE`

**Replace `_getCached()` (lines 17-22):**
```js
async function _getCached(key) {
    return await redis.getJson('cache:analytics:' + key);
}
```

**Replace `_setCached()` (lines 26-45):**
```js
async function _setCached(key, data) {
    await redis.setJson('cache:analytics:' + key, data, 300);
}
```
Removes all eviction logic (Redis TTL handles it).

**Replace `invalidateAnalyticsCache()` (lines 48-52):**
```js
export async function invalidateAnalyticsCache(userId) {
    // Redis doesn't support pattern-delete without SCAN.
    // With 5-minute TTL, stale entries expire naturally.
    // No-op for now; wire SCAN+DEL if needed later.
}
```
Note: This function is never called from production code — only exported. No callers to update.

**`_cacheKey()` (line 13):** Keep unchanged — still used to generate cache keys.

**Caller changes (4 sites inside async `analyticsRouter`):**
| Line | Old | New |
|------|-----|-----|
| 73 | `const _cached = _getCached(_ck)` | `const _cached = await _getCached(_ck)` |
| 166 | `_setCached(_ck, { stats })` | `await _setCached(_ck, { stats })` |
| 185 | `const _cached2 = _getCached(_ck2)` | `const _cached2 = await _getCached(_ck2)` |
| 243 | `_setCached(_ck2, { salesData, byPlatform, topItems })` | `await _setCached(_ck2, { salesData, byPlatform, topItems })` |

**Test impact:** No tests exist for `_getCached`, `_setCached`, or `invalidateAnalyticsCache`.

---

### Step 8: Wire idempotency cache (server.js)
**File:** `src/backend/server.js`

**Current state:** `idempotencyCache` Map (line 715), `IDEMPOTENCY_TTL_MS` (line 714), cleanup interval (lines 717-722). Read at line 1300, write at line 1375. Redis service already imported at line 91.

**Remove:**
- Line 714: `const IDEMPOTENCY_TTL_MS = 5 * 60 * 1000;`
- Line 715: `const idempotencyCache = new Map();`
- Lines 717-722: cleanup interval

**Replace read (line 1300-1301):**
Old:
```js
const cached = idempotencyCache.get(idempotencyKey);
if (cached && cached.expiresAt > Date.now()) {
```
New:
```js
const cached = await redisService.getJson('idempotency:' + idempotencyKey);
if (cached) {
```
Remove `expiresAt` check — Redis TTL handles it.

**Replace write (line 1375-1381):**
Old:
```js
idempotencyCache.set(idempotencyKey, {
    status: result.status || 200,
    data: result.data,
    headers: result.headers || {},
    expiresAt: Date.now() + IDEMPOTENCY_TTL_MS
});
```
New:
```js
await redisService.setJson('idempotency:' + idempotencyKey, {
    status: result.status || 200,
    data: result.data,
    headers: result.headers || {}
}, 300);
```
Remove `expiresAt` field — no longer needed.

**Both sites are inside the async request handler (`fetch()` callback)** — `await` is valid.

**Test impact:** No direct tests for `idempotencyCache`.

---

### Step 9: Wire rate limiter (rateLimiter.js) — HIGHEST RISK
**File:** `src/backend/middleware/rateLimiter.js`

**Current state:** `RateLimiter` class with synchronous `check()`, `block()`, `unblock()`, `getStats()`, `getTopOffenders()`, `cleanup()`, `stop()`. Uses `this.requests` Map (line 48) and `this.blocklist` Map (line 49). Cleanup interval at line 52.

#### 9a. Add import
After line 5:
```js
import redis from '../services/redis.js';
```

#### 9b. Modify constructor and add static property (lines 47-53)
Remove the `this.requests` Map, `this.blocklist` Map, and cleanup interval. Add `ENTRY_TTL` static property after the existing `static config`:
```js
// Add after the static config block (after line 91):
static ENTRY_TTL = Math.ceil(RateLimiter.config.blockDuration / 1000); // 3600s

constructor() {
    // Rate limit data now stored in Redis (or in-memory fallback via redis.js)
    // No local Maps or cleanup intervals needed
}
```
Note: `ENTRY_TTL` is defined as a static class property (like `config`), not inside the constructor. It evaluates once at class definition time.

#### 9c. Make `check()` async (lines 107-169)

**CRITICAL DESIGN NOTES (two bugs prevented):**

1. **Reference mutation write-back:** The original code mutates Map entries in-place via JavaScript references (`entry.count++` at line 137, `entry.violations++` at line 141). With Maps this "just works" because `entry` is a reference to the Map value. With Redis, `getJson()` returns a **deserialized copy** — mutations to the local variable do NOT propagate back to Redis. **Every mutation must be followed by an explicit `redis.setJson()` write-back before returning.**

2. **TTL must use `blockDuration` (3600s), NOT `windowMs`:** The original plan used `Math.ceil(config.windowMs / 1000)` as TTL (e.g., 60s for default). This causes the `violations` counter to be lost when the Redis key expires at window boundary. The 3-strike blocking mechanism (`entry.violations >= 3`) spans multiple windows — if violations reset every window, the user never gets blocked. **All entry keys use `Math.ceil(RateLimiter.config.blockDuration / 1000)` (3600s) as TTL** so violations accumulate across windows. This mirrors the original behavior where Map entries persist until the cleanup interval runs (every 5 minutes), not at window boundary.

3. **Race condition (acceptable):** Two concurrent requests for the same key could both read `count: 5`, both increment to 6, and both write back `count: 6` instead of `count: 7`. This is acceptable for rate limiting — it's a minor under-count that slightly favors the user. The original Map-based code had the same risk under concurrent async handlers in Bun's event loop. For truly atomic increments, we'd need Redis `MULTI/EXEC` or Lua scripts, which is overkill for rate limiting.

**Full replacement of `check()` method:**
```js
async check(key, limitType = 'default', ip = '') {
    const now = Date.now();
    const config = RateLimiter.config[limitType];

    // Check if blocked
    const blockedUntilStr = await redis.get('rl:block:' + key);
    if (blockedUntilStr) {
        const blockedUntil = Number(blockedUntilStr);
        if (now < blockedUntil) {
            const retryAfter = Math.ceil((blockedUntil - now) / 1000);
            return { allowed: false, retryAfter, blocked: true };
        } else {
            // Block expired — Redis TTL should handle this, but clean up just in case
            await redis.del('rl:block:' + key);
        }
    }

    // Get or create rate limit entry
    let entry = await redis.getJson('rl:' + key);

    if (!entry || now > entry.resetTime) {
        // New window — preserve violations from previous entry
        entry = {
            count: 0,
            resetTime: now + config.windowMs,
            violations: entry?.violations || 0
        };
        // Write new window entry immediately
        await redis.setJson('rl:' + key, entry, RateLimiter.ENTRY_TTL);
    }

    // Increment request count
    entry.count++;

    // Check if limit exceeded
    if (entry.count > config.maxRequests) {
        entry.violations++;

        // Block after repeated violations (3 strikes) — never ban loopback IPs
        if (entry.violations >= 3 && !isLoopbackIp(ip)) {
            const blockedUntil = now + RateLimiter.config.blockDuration;
            await redis.set('rl:block:' + key, String(blockedUntil), Math.ceil(RateLimiter.config.blockDuration / 1000));

            // Log security event
            this.logSecurityEvent('RATE_LIMIT_BLOCK', key, {
                violations: entry.violations,
                blockedUntil
            });
        }

        // WRITE-BACK: persist mutated entry (count + violations) to Redis
        await redis.setJson('rl:' + key, entry, RateLimiter.ENTRY_TTL);

        const retryAfter = Math.ceil((entry.resetTime - now) / 1000);
        return {
            allowed: false,
            retryAfter,
            blocked: false,
            remaining: 0
        };
    }

    // WRITE-BACK: persist mutated entry (count) to Redis
    await redis.setJson('rl:' + key, entry, RateLimiter.ENTRY_TTL);

    return {
        allowed: true,
        remaining: config.maxRequests - entry.count,
        resetTime: entry.resetTime
    };
}
```

**Key design decisions in the replacement:**
- `ENTRY_TTL` is a static class property = `blockDuration / 1000` = **3600 seconds** — entries live long enough for violations to accumulate across multiple 1-minute windows
- Two write-back sites: one in the "limit exceeded" branch (line with `entry.violations++`), one in the "allowed" branch (line with `entry.count++`) — covers both exit paths
- `entry?.violations || 0` preserved from original — when creating a new window, violations carry over from the previous entry if it still exists in Redis (guaranteed by 3600s TTL)
- Block check's `await redis.del()` is belt-and-suspenders — Redis TTL should auto-expire, but handles clock skew edge case

Note on `redis.get()` return type: Returns a string (or null). `blockedUntil` is stored as a timestamp number → must `String()` on write and `Number()` on read.

#### 9d. Make `block()` async (lines 236-239)
```js
async block(key, durationMs = RateLimiter.config.blockDuration) {
    const blockedUntil = Date.now() + durationMs;
    await redis.set('rl:block:' + key, String(blockedUntil), Math.ceil(durationMs / 1000));
    this.logSecurityEvent('MANUAL_BLOCK', key, { blockedUntil });
}
```

#### 9e. Make `unblock()` async (lines 245-248)
```js
async unblock(key) {
    await redis.del('rl:block:' + key);
    this.logSecurityEvent('MANUAL_UNBLOCK', key, {});
}
```

#### 9f. Handle `getStats()` and `getTopOffenders()` (lines 253-271)
These read from `this.requests` and `this.blocklist` Maps which we're removing. `rateLimiter.getStats()` is **NOT called from any production code** — only from `middleware-rateLimiter.test.js:86`.

Replace with no-op implementations:
```js
getStats() {
    // Stats now managed by Redis; return empty structure for backward compat
    return { totalTracked: 0, blocked: 0, topOffenders: [] };
}

getTopOffenders(limit = 10) {
    return [];
}
```

#### 9g. Handle `cleanup()` (lines 174-208)
No longer needed — Redis handles TTL. Replace with no-op:
```js
cleanup() {
    // No-op: Redis handles key expiration
}
```

#### 9h. Handle `stop()` (lines 228-231)
No cleanup interval to clear. Keep for backward compatibility (called by `stopRateLimiter()` → `server.js:1613`):
```js
stop() {
    // No-op: no local cleanup interval when using Redis
}
```

#### 9i. Update `createRateLimiter()` (lines 281-337)
The returned function calls `rateLimiter.check()` at line 315, which is now async. Make the returned function async:
```js
return async function rateLimitMiddleware(ctx) {
    // ... skip path checks unchanged ...
    const result = await rateLimiter.check(key, actualLimitType, ip);
    // ... rest unchanged ...
    return result;
};
```

#### 9j. Update `applyRateLimit()` (lines 343-368)
Make it async since `createRateLimiter()` now returns an async function:
```js
export async function applyRateLimit(ctx, limitType = 'auto') {
    if (isRateLimitBypassed()) return null;
    const limiter = createRateLimiter(limitType);
    const result = await limiter(ctx);
    // ... rest unchanged ...
}
```

#### 9k. Update `stopRateLimiter()` (lines 373-375)
Keep the export — it's called from `server.js:1613`. It calls `rateLimiter.stop()` which is now a no-op.

#### 9l. Remove `_cleanupInterval` references
The `_cleanupInterval` property no longer exists on the constructor. This breaks `middleware-shutdown.test.js` (see test section).

---

### Step 10: Add `await` to all `applyRateLimit()` callers

**13 call sites across 6 files** (all already in async functions):

**`src/backend/server.js` (1 call):**
| Line | Old | New |
|------|-----|-----|
| 1271 | `const rateLimitError = applyRateLimit(context, 'auto');` | `const rateLimitError = await applyRateLimit(context, 'auto');` |

**`src/backend/routes/auth.js` (5 calls):**
| Line | Old | New |
|------|-----|-----|
| 451 | `const demoRateError = applyRateLimit(ctx, 'auth');` | `const demoRateError = await applyRateLimit(ctx, 'auth');` |
| 495 | `const mfaRateError = applyRateLimit(ctx, 'auth');` | `const mfaRateError = await applyRateLimit(ctx, 'auth');` |
| 591 | `const refreshRateError = applyRateLimit(ctx, 'auth');` | `const refreshRateError = await applyRateLimit(ctx, 'auth');` |
| 860 | `const resetRateError = applyRateLimit(ctx, 'mutation');` | `const resetRateError = await applyRateLimit(ctx, 'mutation');` |
| 902 | `const resetRateError = applyRateLimit(ctx, 'mutation');` | `const resetRateError = await applyRateLimit(ctx, 'mutation');` |

**`src/backend/routes/extension.js` (1 call):**
| Line | Old | New |
|------|-----|-----|
| 20 | `const rateLimitError = applyRateLimit(ctx, 'api');` | `const rateLimitError = await applyRateLimit(ctx, 'api');` |

**`src/backend/routes/monitoring.js` (1 call):**
| Line | Old | New |
|------|-----|-----|
| 229 | `const rateLimitError = applyRateLimit(ctx, 'default');` | `const rateLimitError = await applyRateLimit(ctx, 'default');` |

**`src/backend/routes/roadmap.js` (1 call):**
| Line | Old | New |
|------|-----|-----|
| 114 | `const voteRateError = applyRateLimit(ctx, 'mutation');` | `const voteRateError = await applyRateLimit(ctx, 'mutation');` |

**`src/backend/routes/security.js` (4 calls):**
| Line | Old | New |
|------|-----|-----|
| 76 | `const verifyRateError = applyRateLimit(ctx, 'auth');` | `const verifyRateError = await applyRateLimit(ctx, 'auth');` |
| 126 | `const resetRateError = applyRateLimit(ctx, 'auth');` | `const resetRateError = await applyRateLimit(ctx, 'auth');` |
| 174 | `const resetRateError = applyRateLimit(ctx, 'auth');` | `const resetRateError = await applyRateLimit(ctx, 'auth');` |
| 274 | `const mfaRateError = applyRateLimit(ctx, 'auth');` | `const mfaRateError = await applyRateLimit(ctx, 'auth');` |

---

### Step 11: Update test files

#### 11a. `src/tests/service-redis.test.js`
Add tests for `getJson`/`setJson`/`flushAll`:
- Test JSON round-trip: `setJson('test', { foo: 'bar' }, 60)` then `getJson('test')` returns `{ foo: 'bar' }`
- Test `getJson` returns `null` for missing key
- Test `getJson` returns `null` for non-JSON string (graceful fallback)
- Test `setJson` with TTL works (value absent after expiry in memory)
- Test `flushAll` clears all keys: `set('k1', 'v1')`, `set('k2', 'v2')`, `flushAll()`, `get('k1')` returns `null`, `get('k2')` returns `null`

#### 11b. `src/tests/middleware-rateLimiter.test.js` (98 lines total)
**Critical: Add redis import and `flushAll()` to `beforeEach`:**
```js
const redis = (await import('../backend/services/redis.js')).default;
```
In `beforeEach` (line 10-12), add `redis.flushAll()` before creating the new instance:
```js
beforeEach(() => {
    redis.flushAll();
    limiter = new RateLimiter();
});
```
This ensures each test starts with clean Redis state, matching the old behavior where `new RateLimiter()` had fresh Maps.

All test callbacks become `async`. All method calls need `await`:

| Line | Old | New |
|------|-----|-----|
| 28 | `limiter.check('test-key', 'default')` | `await limiter.check('test-key', 'default')` |
| 34 | `limiter.check('test-key', 'default')` | `await limiter.check(...)` |
| 37 | `limiter.check('test-key', 'default')` | `await limiter.check(...)` |
| 45 | `limiter.check(key, 'auth')` (in loop) | `await limiter.check(...)` |
| 47 | `limiter.check(key, 'auth')` | `await limiter.check(...)` |
| 58 | `limiter.check(key, 'auth', ip)` (in loop) | `await limiter.check(...)` |
| 61 | `limiter.check(key, 'auth', ip)` | `await limiter.check(...)` |
| 68 | `limiter.block('bad-key', 60000)` | `await limiter.block(...)` |
| 69 | `limiter.check('bad-key', 'default')` | `await limiter.check(...)` |
| 74 | `limiter.block('bad-key', 60000)` | `await limiter.block(...)` |
| 75 | `limiter.unblock('bad-key')` | `await limiter.unblock(...)` |
| 76 | `limiter.check('bad-key', 'default')` | `await limiter.check(...)` |
| 84-85 | `limiter.check(...)` | `await limiter.check(...)` |
| 94 | `limiter.check('test', 'default')` | `await limiter.check(...)` |

**`getStats()` test (lines 82-90):** Currently checks `stats.totalTracked >= 2`. After our change, `getStats()` always returns `{ totalTracked: 0, blocked: 0, topOffenders: [] }`. Update test to check shape only:
```js
test('should return stats object', () => {
    const stats = limiter.getStats();
    expect(stats).toBeDefined();
    expect(typeof stats.totalTracked).toBe('number');
    expect(typeof stats.blocked).toBe('number');
    expect(Array.isArray(stats.topOffenders)).toBe(true);
});
```

**`cleanup()` test (lines 92-97):** Still a no-op, `expect(() => limiter.cleanup()).not.toThrow()` still passes. No change needed.

#### 11c. `src/tests/security-rate-limit.test.js` (393 lines total)
**Critical: Add redis import and `flushAll()` to ALL `beforeEach` blocks:**
This file has multiple describe blocks with their own `beforeEach` (lines 21, 90, 158, 256, 346). Each must call `redis.flushAll()` before `new RateLimiter()`.
```js
const redis = (await import('../backend/services/redis.js')).default;
```
Each `beforeEach`: `redis.flushAll(); limiter = new RateLimiter();`

Line 142 creates `const limiter2 = new RateLimiter()` inside a test. It uses unique key `ip:header-shape` and only checks type/range — no collision risk. No special handling needed.

All test callbacks become `async`. All `limiter.check()` calls need `await` (~30 sites).

Additionally, `createRateLimiter()` now returns an **async** function, so `middleware(ctx)` calls need `await`:
| Line | Old | New |
|------|-----|-----|
| 128 | `middleware(ctx);` | `await middleware(ctx);` |
| 190 | `middleware(ctx);` | `await middleware(ctx);` |
| 218 | `const result = middleware(ctx);` | `const result = await middleware(ctx);` |
| 304 | `const result = middleware(ctx);` | `const result = await middleware(ctx);` |
| 318 | `const result = middleware(ctx);` | `const result = await middleware(ctx);` |
| 332 | `const result = middleware(ctx);` | `const result = await middleware(ctx);` |

#### 11d. `src/tests/middleware-shutdown.test.js` (lines 9-22)
Currently tests:
- Line 12: `expect(rateLimiter._cleanupInterval).not.toBeNull();` — **WILL FAIL** because there's no more `_cleanupInterval`
- Line 17: `expect(rateLimiter._cleanupInterval).toBeNull();` — same

Replace with:
```js
describe('middleware shutdown — rateLimiter', () => {
    it('stop() does not throw', () => {
        expect(() => stopRateLimiter()).not.toThrow();
    });

    it('stop() is idempotent — calling twice does not throw', () => {
        expect(() => stopRateLimiter()).not.toThrow();
    });
});
```

#### 11e. `src/tests/arch-caching-etag.test.js` (lines 136-203)
This test creates its own `new RateLimiter()` and tests rate limiting behavior directly. Heavily impacted by async changes and removal of internal Maps.

**`_cleanupInterval` references (lines 141, 148) + test isolation:**
Remove `clearInterval(limiter._cleanupInterval)` from `beforeEach` and `afterAll`. Add redis import and `flushAll()`:
```js
const redis = (await import('../backend/services/redis.js')).default;
```
```js
beforeEach(() => {
    redis.flushAll();
    limiter = new RateLimiter();
});

afterAll(() => {
    // No cleanup needed — no local intervals
});
```

**All `limiter.check()` calls need `await` (11 sites):**
Lines 154, 161, 163, 170, 173, 181, 187, 194, 200. All test callbacks become `async`.

**`limiter.requests.get(key)` + `entry.resetTime = 0` hack (lines 183-184, 196-197):**
The test manually accesses the internal `requests` Map and resets `resetTime` to 0 to simulate window expiry. This won't work because:
1. `this.requests` Map no longer exists
2. Even with Redis, you can't mutate the entry in-place

**Replace the "3 violations" test (lines 177-202)** with a simplified version that uses Redis-compatible patterns:
```js
test('should block after 3 violations but never block loopback IPs', async () => {
    const key = 'ip:192.168.1.100';
    // Generate 3 violations: exceed limit, then wait for window to expire
    // Since ENTRY_TTL is 3600s in Redis, we manipulate the stored entry directly
    for (let v = 0; v < 3; v++) {
        for (let i = 0; i <= 100; i++) {
            await limiter.check(key, 'default', '192.168.1.100');
        }
        // Simulate window expiry by deleting the key so next check creates a new window
        // (violations persist because they're stored in the entry)
        // Actually, we need to manipulate the entry's resetTime.
        // In Redis fallback mode, we can re-write the entry with resetTime=0:
        const redis = (await import('../backend/services/redis.js')).default;
        const entry = await redis.getJson('rl:' + key);
        if (entry) {
            entry.resetTime = 0;
            await redis.setJson('rl:' + key, entry, 3600);
        }
    }

    const blocked = await limiter.check(key, 'default', '192.168.1.100');
    expect(blocked.blocked).toBe(true);

    // Loopback should never be permanently blocked
    const loopKey = 'ip:127.0.0.1';
    for (let v = 0; v < 3; v++) {
        for (let i = 0; i <= 100; i++) {
            await limiter.check(loopKey, 'default', '127.0.0.1');
        }
        const entry = await redis.getJson('rl:' + loopKey);
        if (entry) {
            entry.resetTime = 0;
            await redis.setJson('rl:' + loopKey, entry, 3600);
        }
    }

    const loopResult = await limiter.check(loopKey, 'default', '127.0.0.1');
    expect(loopResult.blocked).toBeFalsy();
});
```

Note: This test works because in test mode (`NODE_ENV=test`), Redis falls back to the in-memory store. The `redis.getJson`/`redis.setJson` calls manipulate the same in-memory data that `limiter.check()` uses.

---

#### 11f. `src/tests/service-enhancedMFA-unit.test.js` (lines 738-753)
Remove the entire `cleanupChallenges` section — comment header (lines 738-740) and describe block (lines 741-753, 2 tests):
- Line 742: `does not throw when called directly` — method no longer exists
- Line 746: `is called during startRegistration` — `startRegistration` no longer calls it

Delete lines 738-753 entirely (16 lines). The next section (`enhancedMFARouter` at line 755) shifts up.

---

## Implementation Order

| Order | Step | File(s) | Risk | Dependencies |
|-------|------|---------|------|-------------|
| 1 | Step 1 | `redis.js` | None | Foundation — all consumers need `getJson`/`setJson` |
| 2 | Step 2 | `.env.example` | None | None |
| 3 | Step 3 | `enhancedMFA.js` | Low | Step 1 |
| 4 | Step 4 | `socialAuth.js` | Low | Step 1 |
| 5 | Step 5 | `receiptParser.js` | Low | Step 1 |
| 6 | Step 6 | `barcode.js` | Low | Step 1 |
| 7 | Step 7 | `analytics.js` | Low | Step 1 |
| 8 | Step 8 | `server.js` (idempotency only) | Medium | Step 1 |
| 9 | Step 9+10 | `rateLimiter.js` + 6 route files | **High** | Step 1 |
| 10 | Step 11 | 6 test files | Medium | Steps 3, 9 |

Steps 3-7 are independent of each other and can be parallelized.
Step 9 is the riskiest — do last, test immediately.
Step 10 (tests) should be done alongside each respective production step.

---

## Verification

After ALL changes, run in this exact order:
```bash
# 1. Redis service tests (verify getJson/setJson work in fallback mode)
bun test src/tests/service-redis.test.js

# 2. Enhanced MFA tests (verify cleanupChallenges removal doesn't break)
bun test src/tests/service-enhancedMFA-unit.test.js
bun test src/tests/enhancedMFA-expanded.test.js

# 3. Rate limiter tests (most affected by async changes)
bun test src/tests/middleware-rateLimiter.test.js
bun test src/tests/security-rate-limit.test.js
bun test src/tests/arch-caching-etag.test.js

# 4. Shutdown test (verify no-op stop() works)
bun test src/tests/middleware-shutdown.test.js

# 5. Auth + security baseline (must stay at 58 pass / 0 fail)
bun test src/tests/auth.test.js src/tests/security.test.js

# 6. Full test suite
bun run test:all

# 7. Manual: start server, confirm no Redis log spam
REDIS_ENABLED=false bun run dev

# 8. Manual: docker-compose up, confirm:
#    - No log spam
#    - GET /api/health/ready shows redis: "ok"
#    - Rate limiting works (hit an endpoint 101 times in 1 minute)
```

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Rate limiter async conversion breaks a caller | **High** | All 13 call sites verified. All in async contexts. Run tests immediately after Step 9. |
| Missing `await` produces `[object Promise]` instead of data | **High** | Bun:test will show obvious failures. Grep for `Promise {` in test output. |
| Rate limiter mutations not persisted (reference vs. copy) | **High** | ADDRESSED: `check()` includes explicit `redis.setJson()` write-back after every mutation (`entry.count++`, `entry.violations++`) on both exit paths. See 9c design note #1. |
| Rate limiter violations lost across windows (wrong TTL) | **High** | ADDRESSED: All `rl:` entries use `ENTRY_TTL = blockDuration / 1000` (3600s), not `windowMs / 1000`. Violations persist across multiple 1-minute windows. See 9c design note #2. |
| Rate limiter race condition (concurrent requests) | Low | Acceptable: two concurrent requests for the same key may under-count by 1. Original Map-based code had the same risk. See 9c design note #3. |
| `getStats()` returning empty data breaks admin features | Low | `rateLimiter.getStats()` is NOT called from any production code — only 1 test. |
| Idempotency cache Redis latency on hot path | Low | Redis localhost is sub-millisecond. In-memory fallback is instant. |
| `cleanupChallenges` removal breaks MFA flow | Low | The method only cleaned expired challenges. Redis TTL handles this automatically. All MFA tests use the HTTP API which will work with in-memory fallback. |
| `createRateLimiter` async return breaks middleware chain | Medium | The returned function was sync, now async. All callers (`applyRateLimit`, tests) need `await`. Verified all 13 production callers + 6 test callers. |
| Test isolation broken (shared Redis memoryStore) | **High** | ADDRESSED: Added `flushAll()` to redis.js. All 3 rate limiter test files call `redis.flushAll()` in `beforeEach`. Without this, keys from test N leak into test N+1 causing wrong counts. |
| `middleware-shutdown.test.js` fails on missing `_cleanupInterval` | Low | Explicitly updating the test in Step 11d. |

**Safety net:** The in-memory fallback in `redis.js` means every consumer degrades gracefully if Redis goes down. No data loss — permanent data is in SQLite, only temporary/ephemeral state uses Redis.

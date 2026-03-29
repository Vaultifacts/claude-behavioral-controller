# Plan: Sentry Fixes — SDK repair + service creation

## Context
The Sentry audit revealed the SDK is completely silent (0 events in 14 days). Two root causes:
1. `monitoring.js:62` has `integrations: []` which strips all Node.js auto-instrumentation
2. `src/backend/services/sentry.js` doesn't exist but two test files import it (569 + 128 lines of tests define the exact API)

## Files to Modify
1. **CREATE** `src/backend/services/sentry.js` — lightweight Sentry wrapper using raw `fetch()`
2. **EDIT** `src/backend/services/monitoring.js` — fix SDK init (3 line changes)
3. **EDIT** `.env.example` — add `SENTRY_RELEASE` variable

## Step 1: Create `src/backend/services/sentry.js`

A custom Sentry client using raw `fetch()` to the Sentry Store API (NOT `@sentry/node`). This is independent from monitoring.js's SDK-based integration.

**Required exports** (defined by test assertions):
- `default` — `sentryService` object
- `sentryMiddleware` — named export (function)
- `sentryErrorHandler` — named export (function)

**`sentryService` properties:**
- `dsn` — reads `process.env.SENTRY_DSN` at module load
- `initialized` — boolean, starts `false`
- `_breadcrumbs` — starts `undefined`
- `_currentUser` — starts `null`
- `_lastStatus` — starts `undefined`

**`sentryService` methods:**
| Method | Disabled behavior | Notes |
|--------|------------------|-------|
| `init()` | logs "No DSN configured" via `logger.info`, does NOT set `initialized=true` | |
| `captureException(err, ctx?)` | returns `null`, logs via `logger.error('[Sentry]', err.message)` | test checks `c[1] === 'detailed error'` |
| `captureMessage(msg, level?, ctx?)` | returns `null`, logs via `logger.info` | |
| `setUser(user)` | returns `undefined` (no-op) | |
| `clearUser()` | sets `_currentUser = null` | always runs, even when disabled |
| `addBreadcrumb(crumb)` | returns `undefined`, does NOT push | cap at 100 when enabled |
| `startTransaction(name, op?)` | returns `{ finish: () => {} }` | |
| `_generateEventId()` | 32-char lowercase hex via `crypto.randomBytes(16).toString('hex')` | always works |
| `_parseStackTrace(stack)` | parses `at fn (path:line:col)`, skips `Error:` first line | always works |
| `_sendToSentry(event)` | if dsn falsy, returns without fetch | parses DSN for host/key/projectId |

**`_sendToSentry` DSN parsing:**
- DSN format: `https://{publicKey}@{host}/{projectId}`
- Endpoint: `https://{host}/api/{projectId}/store/`
- Headers: `Content-Type: application/json`, `X-Sentry-Auth` containing `sentry_key={publicKey}`
- On network error: catch + `logger.error`, don't throw
- On non-ok response: `logger.error('Failed to send event ...')`

**`sentryMiddleware(ctx)`:**
- Takes `{ method, path, headers, user? }`
- Returns `null` when disabled

**`sentryErrorHandler(error, ctx)`:**
- Scrubs headers: `authorization`, `cookie`, `x-csrf-token`
- Scrubs query params: `token`, `api_key`, `key`
- Includes `user.id` context when `ctx.user` present
- Calls `captureException` internally

**`IS_ENABLED`:** `!!process.env.SENTRY_DSN && process.env.NODE_ENV === 'production'`

**Import:** `import { logger } from '../shared/logger.js'` + `import crypto from 'crypto'`

## Step 2: Fix `monitoring.js` (3 changes)

File: `src/backend/services/monitoring.js`

1. **Line 63**: Remove `integrations: []` — let Sentry use all default Node.js integrations
2. **Line 62**: Change `tracesSampleRate: 0.1` to `tracesSampleRate: 1.0` (low traffic = need all traces)
3. **Line 61**: Add `release: process.env.SENTRY_RELEASE || undefined` to `Sentry.init()`

## Step 3: Update `.env.example`

Add after line 51 (`SENTRY_DSN=...`):
```
# Release identifier for Sentry (auto-set via CI, or use git SHA)
SENTRY_RELEASE=
```

## Verification

1. `bun test src/tests/service-sentry.test.js` — should pass all 20 tests
2. `bun test src/tests/service-sentry-unit.test.js` — should pass all 47 tests
3. `grep -n 'integrations' src/backend/services/monitoring.js` — confirm `integrations: []` is gone
4. `grep -n 'tracesSampleRate' src/backend/services/monitoring.js` — confirm `1.0`
5. `grep -n 'SENTRY_RELEASE' .env.example` — confirm added

## Out of scope (UI changes — manual)
- Enable inbound filters (browser-extensions, localhost, web-crawlers)
- Enable org data scrubber + defaults + IP scrubbing
- Set up 2FA on account
- Create alert rules
- Add uptime monitor

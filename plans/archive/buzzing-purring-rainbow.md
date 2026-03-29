# Plan: Smoke Test + Pre-launch + V1.1 Decision + Icon

## Context
All V1.0 MVP features are built, committed, and packaged. The installer exists at `release/Trading Buddy Setup 1.0.0.exe` (81 MB). This session runs a smoke test, audits the pre-launch checklist, makes a V1.1 decision, and attempts to get the branded Windows icon working.

## Current State (from exploration)
- `.env` exists — dev defaults set, `OPENCLAW_WEBHOOK_OUTBOUND` and `GITHUB_TOKEN` blank (both optional)
- Git remote: `https://github.com/Vaultifacts/trading-buddy-v2.git` ✓
- OpenClaw: has `[CONFIGURE]` placeholders — optional, not blocking
- Developer Mode: DISABLED (`AllowDevelopmentWithoutDevLicense=0` in HKLM registry)
- V1.1 screens not yet built: Market Monitor, Analytics Hub
- All V1.0 screens exist and 38/38 tests pass

---

---

## Item 1: Automated Engine Smoke Test

Start `python engine/api.py --port 8081 --broker offline` in background. Hit 8 REST endpoints via Python `urllib`. Kill engine. Report pass/fail per endpoint.

Endpoints:
1. `GET /health` → 200
2. `GET /api/v1/session` → 200 + JSON body
3. `GET /api/v1/strategies` → 200 + array
4. `GET /api/v1/account` → 200
5. `GET /api/v1/risk` → 200
6. `POST /api/v1/bot/start` → 200
7. `POST /api/v1/bot/stop` → 200
8. `POST /api/v1/backtest/run` (body: `{symbol:"SPY",strategy:"SMA+RSI",days:1,timeframe:"1Day"}`) → 200

**UI smoke test** — must be done manually by the user:
- `npm run dev` → verify window opens, all 7 nav items load without errors

---

## Item 2: Pre-launch Checklist

Report only — no code changes needed. All clear:
- `.env` dev defaults ✓, optional fields blank is fine
- Git remote configured ✓
- OpenClaw optional — user configures when they set up OpenClaw channel
- FAR-03 regulatory copy ✓ (done last session)

---

## Item 3: V1.1 Decision

**V1.0 complete — all 13 MVP features shipped.**

**V1.1 gaps visible in current nav** (screens not yet built):
- Market Monitor (watchlist, earnings, economic calendar)
- Analytics Hub (strategy performance breakdown, drawdown analysis)
- Plus: live broker support (IBKR/Questrade), Journal, PriceAlert system

**Decision: Start Market Monitor next** (user selected). After smoke test + icon, begin V1.1 Market Monitor implementation.

---

## Item 4: Windows Icon (Developer Mode)

Try enabling via PowerShell registry write:
```powershell
powershell.exe -Command "Set-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock' -Name AllowDevelopmentWithoutDevLicense -Value 1 -Type DWord"
```
This requires admin. Will likely fail without elevation.

If succeeds → re-run `npm run package:win`.
If fails → tell user: open PowerShell as Administrator and run the command above, then re-run `npm run package:win`. OR: Settings → Windows Update → For Developers → Developer Mode ON.

---

## Execution Order
1. Run engine smoke test (Python subprocess, no npm run dev)
2. Report pre-launch checklist (no edits)
3. Report V1.1 options, ask which feature to start next
4. Attempt Developer Mode registry write, conditionally re-run package:win
5. Append session summary to `audit-log.md`

## Files That May Be Edited
- `audit-log.md` — session summary appended
- No source files change in this session

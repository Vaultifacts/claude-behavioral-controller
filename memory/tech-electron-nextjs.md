---
name: Electron + Next.js Desktop Apps
description: Windows patterns for wrapping Next.js in Electron — splash screen, port management, EADDRINUSE handling
type: reference
last_reviewed: 2026-03-22
---

When wrapping a Next.js app in Electron on Windows, always follow this pattern:
- **Use `next build` + `next start`** (not `next dev`) — starts in ~2s vs 30s
- **Show window immediately** with a local splash HTML file (`electron/splash.html`), navigate to app once server is ready
- **VBS launcher must kill the port first**: run PowerShell to `Stop-Process` any PID on the port before launching
- **`isServerAlready()`** check before `startNextServer()` — reuse a running server instead of crashing with EADDRINUSE
- **Auto-retry on EADDRINUSE**: if stderr contains `EADDRINUSE`, kill port via PowerShell and restart
- **After any code change**: run `npm run build` once before the app will reflect the change (no hot-reload in production mode)

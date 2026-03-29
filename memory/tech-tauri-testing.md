---
name: Tauri / WebView2 Desktop App Testing
description: CDP-based testing for Tauri 2 apps on Windows — screenshots, JS execution, DOM inspection via remote debugging
type: reference
last_reviewed: 2026-03-22
---

When testing Tauri 2 desktop apps, use Chrome DevTools Protocol (CDP) via WebView2 remote debugging:
1. **Launch**: `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=9222" npx tauri dev`
2. **Discover**: `curl -s http://localhost:9222/json` → get `webSocketDebuggerUrl`
3. **Screenshot**: Python `websockets` + `Page.captureScreenshot` → save PNG, read with Read tool
4. **Execute JS**: `Runtime.evaluate` with `awaitPromise: true` to interact with the app
5. **Dependencies**: `python -m pip install websockets` (already installed globally)
- This works because Chrome extension can't access Tauri's WebView2 window
- CDP gives full control: screenshots, JS execution, DOM inspection, network monitoring
- Always use this approach for autonomous Tauri app testing instead of asking the user

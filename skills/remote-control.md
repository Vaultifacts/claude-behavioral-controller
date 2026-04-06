---
name: remote-control
description: Use when asked to connect a phone to this desktop session, access this session remotely, or set up mobile access via the Claude app.
---

## Remote Control — Connect Phone to This Session

### Step 1 — Register this environment

Run the built-in remote environment command:

```
/remote-env
```

This registers the current session and generates an environment ID. Note the output — it will show something like:
`Set default remote environment to DESKTOP-UCUI31D:C:\Users\Matt1:XXXX (env_XXXXXXXX)`

### Step 2 — Connect from the Claude app on your phone

1. Open the **Claude app** on your phone (iOS or Android)
2. Tap the **profile icon** or **settings gear** (top corner)
3. Look for **"Environments"**, **"Remote Environments"**, or a **computer/terminal icon**
4. Tap **Connect** next to your desktop environment name (`DESKTOP-UCUI31D`)
5. The app will link to this running session

> If you don't see your environment listed: pull to refresh, or sign out and back in on the phone. Both devices must be on the **same Anthropic account**.

### Step 3 — Verify connection

Once connected, send a test message from your phone:

```
echo "phone connected" && whoami && pwd
```

You should see output from this Windows machine, confirming the tunnel is live.

---

## Troubleshooting

**Environment not showing on phone:**
- Make sure `/remote-env` was run in THIS session (not a different terminal)
- Check you're logged into the same account on both devices
- Force-quit and reopen the Claude app on your phone
- Try the Claude web app at claude.ai instead of the native app

**Connection drops:**
- The desktop session must stay open — don't close this terminal window
- If the session expired, re-run `/remote-env` and reconnect from the phone

**"Option A doesn't work" fallback:**
If the Claude app environment picker is missing or broken, try:
1. Open **claude.ai** in your phone's mobile browser (Safari/Chrome)
2. Log in and start a new conversation
3. The remote environment selector appears in the web UI even when the native app does not show it

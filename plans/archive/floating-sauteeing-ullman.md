# Plan: Kill stale autopilot processes and rerun iteration 01

## Context
Previous autopilot runs (iter01–iter04) left log files in `tools/autopilot/logs/`. A stale PowerShell, node, or npm process may be holding `npm_test_iter01.txt` open, blocking a clean rerun. The script uses `Set-Content` (overwrite), so the file lock — not stale content — is the blocker.

## Steps

### 1. Check for stale processes
```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'powershell|pwsh|node|npm' -and
                 $_.CommandLine -match 'run-roundrobin|npm test|runbook:smoke' } |
  Select-Object ProcessId, Name, CommandLine
```

### 2. Kill any matching processes
```powershell
Get-CimInstance Win32_Process |
  Where-Object { $_.Name -match 'powershell|pwsh|node|npm' -and
                 $_.CommandLine -match 'run-roundrobin|npm test|runbook:smoke' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
```

### 3. Rerun the script (1 iteration, CodexOnly)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/autopilot/run-roundrobin.ps1 -Mode CodexOnly -MaxIterations 1
```

### 4. Show outputs
```powershell
Get-Content tools/autopilot/logs/npm_test_iter01.txt -Tail 100
Get-Content tools/autopilot/logs/runbook_smoke_iter01.txt -Tail 100
Get-Content tools/autopilot/logs/roundrobin_console_latest.txt -Tail 120
```

## Notes
- The script uses `Set-Content` (not `Add-Content`) for log files, so iter01 logs will be overwritten cleanly on a fresh run.
- `roundrobin_console_latest.txt` is written by whatever wrapper captures stdout of the ps1 script; if it doesn't exist after the run, we'll note that.
- No source files are modified — this is purely process cleanup + script execution.

## Verification
After the run, the three log files will be read and pasted verbatim to confirm the iteration completed.

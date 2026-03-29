# Startup Script: New Layout + Desktop Auto-Arrange Fix

## Context
User has changed their entire startup layout (removed notepad + cmd windows, now uses PowerShell
terminals and File Explorer), and desktop icons keep shuffling due to OneDrive sync triggering
Windows auto-arrange. The script needs to be updated to the new layout and add a fix that
disables auto-arrange every logon.

## File to modify
`C:\Scripts\startup_layout.ps1`

---

## Scanned New Layout

| App | X | Y | W | H | Note |
|-----|---|---|---|---|------|
| Chrome | -1 | 8 | 1390 | 1254 | Display 1 |
| Notion | 1388 | -1 | 1169 | 831 | Display 1 |
| Blitz | 112 | 554 | 1420 | 850 | Display 1 — revert to original |
| League of Legends | 1534 | 828 | 1024 | 576 | Display 1 — revert to original |
| PowerShell 1 | 2555 | 156 | 800 | 518 | D2 col1-top |
| PowerShell 2 | 2557 | 669 | 801 | 536 | D2 col1-bot |
| PowerShell 3 | 3339 | 156 | 800 | 518 | D2 col2-top |
| Task Manager | 3344 | 670 | 794 | 536 | D2 col2-bot |
| File Explorer | 4125 | 158 | 891 | 582 | D2 col3 — Project Terminal Documents |

*Excluded: Windows Terminal "Claude Code" — user opens that manually*

---

## Change 1: Cleanup — kill `powershell` instead of `cmd`, drop `notepad`

```powershell
Get-Process -Name "powershell" -ErrorAction SilentlyContinue |
    Where-Object { $_.Id -ne $PID } | Stop-Process -Force
```
Remove the `notepad` kill line (no notepad in new layout).
Keep the Display 2 wait block unchanged.

## Change 2: Remove Section 1 (NOTEPAD INSTANCES) entirely
All 7 notepad `Launch-And-Position` calls and their `Start-Sleep` lines — delete them.

## Change 3: Replace Section 2 (CMD → POWERSHELL, 7 windows → 3)

Rename section header to `# 2. POWERSHELL INSTANCES (3 terminals)`.

Update `Launch-Cmd` function: change `Start-Process "cmd.exe"` → `Start-Process "powershell.exe"`.
Rename function to `Launch-Shell`.

Replace the 7 `Launch-Cmd` calls with 3 `Launch-Shell` calls:
```powershell
$results["ps 1 (D2 col1-top)"] = Launch-Shell -X 2555 -Y 156 -Width 800 -Height 518 -Label "ps 1 (D2 col1-top)"
$results["ps 2 (D2 col1-bot)"] = Launch-Shell -X 2557 -Y 669 -Width 801 -Height 536 -Label "ps 2 (D2 col1-bot)"
$results["ps 3 (D2 col2-top)"] = Launch-Shell -X 3339 -Y 156 -Width 800 -Height 518 -Label "ps 3 (D2 col2-top)"
```

## Change 4: Task Manager — update position
`-X 3344 -Y 670 -Width 794 -Height 536`

## Change 5: Chrome — update position
`-X -1 -Y 8 -Width 1390 -Height 1254`

Keep the existing `--restore-last-session --profile-directory=Default` args and tab-by-tab opening.

## Change 6: Notion — update position
`-X 1388 -Y -1 -Width 1169 -Height 831`

## Change 7: Blitz — revert to original
`-X 112 -Y 554 -Width 1420 -Height 850`

## Change 8: League — revert to original
`-X 1534 -Y 828 -Width 1024 -Height 576` (both primary and fallback Position-Window calls)

## Change 9: Add File Explorer section (after Task Manager, before Chrome)
```powershell
# --------------------------------------------------
# 4. FILE EXPLORER (Project Terminal Documents)
# --------------------------------------------------
Log "--- Launching File Explorer ---"
Start-Process "explorer.exe" -ArgumentList "C:\Users\Matt1\OneDrive\Desktop\Project Terminal Documents"
$explorerHwnd = Find-WindowByTitle -TitlePattern "Project Terminal Documents" -MaxRetries 15 -SleepMs 1000
$results["File Explorer"] = Position-Window -Handle $explorerHwnd -X 4125 -Y 158 -Width 891 -Height 582 -Label "File Explorer"
Start-Sleep -Seconds 1
```
Re-number Chrome as 5, Notion as 6, Blitz as 7, League as 8.

## Change 10: Desktop auto-arrange fix — add helper function + call at end

Add this function to the `# HELPER FUNCTIONS` section (after `Position-Window`, before `Launch-And-Position`):
```powershell
function Disable-DesktopAutoArrange {
    Add-Type @"
using System;
using System.Runtime.InteropServices;
public class DesktopAA {
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string w);
    [DllImport("user32.dll")] public static extern IntPtr FindWindowEx(IntPtr p, IntPtr a, string c, string w);
    [DllImport("user32.dll")] public static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
    public const uint LVM_GETEXTENDEDLISTVIEWSTYLE = 0x1037;
    public const uint LVM_SETEXTENDEDLISTVIEWSTYLE = 0x1036;
    public const int LVS_EX_AUTOARRANGE = 0x100;
}
"@ -ErrorAction SilentlyContinue
    $progman  = [DesktopAA]::FindWindow("Progman", $null)
    $defView  = [DesktopAA]::FindWindowEx($progman, [IntPtr]::Zero, "SHELLDLL_DefView", $null)
    $listView = [DesktopAA]::FindWindowEx($defView, [IntPtr]::Zero, "SysListView32", $null)
    if ($listView -ne [IntPtr]::Zero) {
        $style = [DesktopAA]::SendMessage($listView, [DesktopAA]::LVM_GETEXTENDEDLISTVIEWSTYLE, [IntPtr]::Zero, [IntPtr]::Zero).ToInt32()
        if ($style -band [DesktopAA]::LVS_EX_AUTOARRANGE) {
            $newStyle = $style -band (-bnot [DesktopAA]::LVS_EX_AUTOARRANGE)
            [DesktopAA]::SendMessage($listView, [DesktopAA]::LVM_SETEXTENDEDLISTVIEWSTYLE,
                [IntPtr]::new([DesktopAA]::LVS_EX_AUTOARRANGE), [IntPtr]::new($newStyle)) | Out-Null
            Log "Desktop auto-arrange disabled" "SUCCESS"
        } else {
            Log "Desktop auto-arrange already off" "INFO"
        }
    } else {
        Log "Could not find desktop listview - skipping auto-arrange fix" "WARNING"
    }
}
```

Call it at the very END of the script, after the SUMMARY block:
```powershell
# --------------------------------------------------
# FIX: Disable desktop icon auto-arrange
# --------------------------------------------------
Log "--- Fixing desktop auto-arrange ---"
Disable-DesktopAutoArrange
```

---

## Verification
- Run script manually: `powershell -ExecutionPolicy Bypass -File C:\Scripts\startup_layout.ps1`
- Check `C:\Scripts\startup_log.txt` — should show 9 items, all OK except possibly League (slow to load)
- Confirm 3 PowerShell windows on Display 2 at correct positions
- Confirm File Explorer opens to Project Terminal Documents
- Move desktop icons around, reboot, confirm they stay in place
- Confirm Chrome opens with session intact (no logout)

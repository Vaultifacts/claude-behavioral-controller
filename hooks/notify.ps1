param(
    [Parameter(Mandatory)][string]$Title,
    [Parameter(Mandatory)][string]$Message,
    [ValidateSet('Info','Error')][string]$Level = 'Info',
    [int]$Duration = 4000
)

Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = if ($Level -eq 'Error') { [System.Drawing.SystemIcons]::Error } else { [System.Drawing.SystemIcons]::Information }
$n.Visible = $true
$tip = if ($Level -eq 'Error') { [System.Windows.Forms.ToolTipIcon]::Error } else { [System.Windows.Forms.ToolTipIcon]::Info }
$n.ShowBalloonTip($Duration, $Title, $Message, $tip)
Start-Sleep -Seconds ([math]::Ceiling($Duration / 1000) + 1)
$n.Dispose()

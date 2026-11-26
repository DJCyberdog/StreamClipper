$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$icon = Join-Path $root 'assets\StreamClipper.ico'
$ws = New-Object -ComObject WScript.Shell
$link = $ws.CreateShortcut((Join-Path $root 'StreamClipper.lnk'))
$link.TargetPath = Join-Path $root 'run_windows.bat'
$link.WorkingDirectory = $root
if (Test-Path -LiteralPath $icon -PathType Leaf) { $link.IconLocation = "$icon,0" }
$link.Save()
Write-Host 'StreamClipper.lnk erstellt. Nach einem Ordnerwechsel erneut ausfuehren.'

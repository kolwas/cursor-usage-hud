<#
Installs a Przepiorka (Usage HUD) shortcut into the current user's Startup
folder, so it launches automatically at login. Safe to re-run — it just
overwrites the shortcut.

Usage:
    .\.venv\Scripts\Activate.ps1   # optional, only needed to confirm the venv exists
    .\packaging\install-autostart-windows.ps1

Uninstall: delete the .lnk this prints, or run with -Remove.
#>
param(
    [switch]$Remove
)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Target = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
$Icon = Join-Path $RepoRoot "src\usage_hud\assets\przepiorka.ico"
$LnkPath = Join-Path ([Environment]::GetFolderPath('Startup')) "Przepiorka.lnk"

if ($Remove) {
    if (Test-Path $LnkPath) {
        Remove-Item $LnkPath -Force
        Write-Output "Removed $LnkPath"
    } else {
        Write-Output "No autostart shortcut found at $LnkPath"
    }
    exit 0
}

if (-not (Test-Path $Target)) {
    Write-Error "venv not found at $Target — run 'python -m venv .venv; .venv\Scripts\pip install -e .' first."
    exit 1
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($LnkPath)
$shortcut.TargetPath = $Target
$shortcut.Arguments = "-m usage_hud"
$shortcut.WorkingDirectory = $RepoRoot
if (Test-Path $Icon) {
    $shortcut.IconLocation = $Icon
}
$shortcut.Description = "Przepiorka - AI usage HUD"
$shortcut.WindowStyle = 7  # start minimized (no console flash)
$shortcut.Save()

Write-Output "Autostart shortcut written to: $LnkPath"
Write-Output "It will launch on your next login. To start it now: & '$Target' -m usage_hud"

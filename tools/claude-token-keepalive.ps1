<#
Keeps the Claude Code sign-in fresh so the HUD's live Claude usage keeps working.

Why: the HUD reads Claude Code's access token but never refreshes it (a refresh
from outside could sign Claude Code out). That token lives only a few hours, and
Claude Code renews it only when it is used. This script uses it: one tiny
request through the official `claude` CLI, which refreshes its own token as a
side effect. Run it from Task Scheduler every ~4 hours (see README).

It touches no credential file itself and prints nothing secret: the log keeps
only the time, the exit code and the first words of the reply.
#>
$ErrorActionPreference = 'Stop'
$stateDir = Join-Path $env:APPDATA 'usage-hud'
$workDir = Join-Path $stateDir 'keepalive'      # its own folder: no clutter in real projects
$logFile = Join-Path $stateDir 'keepalive.log'
New-Item -ItemType Directory -Force -Path $workDir | Out-Null

$claude = Join-Path $env:APPDATA 'npm\claude.cmd'
if (-not (Test-Path $claude)) {
    $cmd = Get-Command claude -ErrorAction SilentlyContinue
    if ($cmd) { $claude = $cmd.Source }
}

$started = Get-Date
try {
    Set-Location $workDir
    # haiku: the cheapest model; no session file is written.
    $reply = (& $claude -p 'ok' --model haiku --no-session-persistence 2>&1 | Out-String)
    $exit = $LASTEXITCODE
} catch {
    $reply = $_.Exception.GetType().Name
    $exit = -1
}
$seconds = [math]::Round(((Get-Date) - $started).TotalSeconds, 1)
$words = (($reply -replace '\s+', ' ').Trim())
if ($words.Length -gt 80) { $words = $words.Substring(0, 80) }
"{0} exit={1} {2}s {3}" -f $started.ToString('s'), $exit, $seconds, $words | Add-Content -Path $logFile

# keep the log short
$lines = Get-Content $logFile
if ($lines.Count -gt 200) { $lines | Select-Object -Last 100 | Set-Content $logFile }
exit $exit

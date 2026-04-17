# AI Holding Company — Register Windows Task Scheduler tasks
# Run once as Administrator (or as your user account).
# Creates two tasks:
#   1. BridgeStartup  — starts telegram_bridge.py at login, keeps it running
#   2. MorningBrief   — sends the morning brief at 07:00 every day

$RepoRoot   = Split-Path -Parent $MyInvocation.MyCommand.Definition
$StartScript = Join-Path $RepoRoot "start_bridge.ps1"
$ScriptsDir  = Join-Path $RepoRoot ".claude\worktrees\suspicious-davinci\scripts"
$EnvFile     = Join-Path $RepoRoot ".env.local"
$PwshExe     = "powershell.exe"

# Helper: build an env-loading + python command action
function New-EnvAction($pyArgs) {
    $cmd = @"
`$env:dummy = ''; Get-Content '$EnvFile' | ForEach-Object { if (`$_ -match '^\s*([^#][^=]+)=(.*)$') { [System.Environment]::SetEnvironmentVariable(`$matches[1].Trim(), `$matches[2].Trim(), 'Process') } }; Set-Location '$ScriptsDir'; python $pyArgs
"@
    return New-ScheduledTaskAction -Execute $PwshExe -Argument "-NonInteractive -WindowStyle Hidden -Command `"$cmd`""
}

# ── Task 1: Bridge always-on at login ────────────────────────────────────────
$bridgeAction  = New-EnvAction "telegram_bridge.py"
$bridgeTrigger = New-ScheduledTaskTrigger -AtLogOn
$bridgeSettings = New-ScheduledTaskSettingsSet `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName   "AIHolding-BridgeStartup" `
    -Action     $bridgeAction `
    -Trigger    $bridgeTrigger `
    -Settings   $bridgeSettings `
    -RunLevel   Limited `
    -Force

Write-Host "✅ Registered: AIHolding-BridgeStartup (runs at login)"

# ── Task 2: Morning brief at 07:00 daily ─────────────────────────────────────
$briefAction  = New-EnvAction "telegram_bridge.py --send-morning-brief"
$briefTrigger = New-ScheduledTaskTrigger -Daily -At "07:00"
$briefSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName   "AIHolding-MorningBrief" `
    -Action     $briefAction `
    -Trigger    $briefTrigger `
    -Settings   $briefSettings `
    -RunLevel   Limited `
    -Force

Write-Host "✅ Registered: AIHolding-MorningBrief (runs daily at 07:00)"
Write-Host ""
Write-Host "To verify: Get-ScheduledTask -TaskName 'AIHolding-*' | Format-Table TaskName, State"
Write-Host "To remove: Unregister-ScheduledTask -TaskName 'AIHolding-BridgeStartup' -Confirm:`$false"

# AI Holding Company - Register Windows Task Scheduler tasks
# Run once as your user account.
# Creates two tasks:
#   1. BridgeStartup  - waits for Ollama then starts aiogram_bridge.py at login
#   2. MorningBrief   - sends the morning brief at 07:00 every day

$RepoRoot    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$SafeScript  = Join-Path $RepoRoot "start_bridge_safe.ps1"
$ScriptsDir  = Join-Path $RepoRoot "scripts"
$EnvFile     = Join-Path $RepoRoot ".env"
$EnvLocalFile = Join-Path $RepoRoot ".env.local"
$PwshExe     = "powershell.exe"

# Task 1: Bridge always-on at login (waits for Ollama)
$bridgeAction = New-ScheduledTaskAction `
    -Execute  $PwshExe `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$SafeScript`""

$bridgeTrigger  = New-ScheduledTaskTrigger -AtLogOn
$bridgeSettings = New-ScheduledTaskSettingsSet `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 2) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew

Register-ScheduledTask `
    -TaskName   "AIHolding-BridgeStartup" `
    -Action     $bridgeAction `
    -Trigger    $bridgeTrigger `
    -Settings   $bridgeSettings `
    -RunLevel   Limited `
    -Force

Write-Host "[OK] Registered: AIHolding-BridgeStartup (waits for Ollama, then starts bridge at login)"

# Task 2: Morning brief at 07:00 daily
$briefCmd = @"
Get-Content '$EnvFile' | ForEach-Object { if (`$_ -match '^\s*([^#][^=]+)=(.*)$') { [System.Environment]::SetEnvironmentVariable(`$matches[1].Trim(), `$matches[2].Trim(), 'Process') } }; Get-Content '$EnvLocalFile' -ErrorAction SilentlyContinue | ForEach-Object { if (`$_ -match '^\s*([^#][^=]+)=(.*)$') { [System.Environment]::SetEnvironmentVariable(`$matches[1].Trim(), `$matches[2].Trim(), 'Process') } }; Set-Location '$ScriptsDir'; python aiogram_bridge.py --send-morning-brief
"@

$briefAction = New-ScheduledTaskAction `
    -Execute  $PwshExe `
    -Argument "-NonInteractive -WindowStyle Hidden -Command `"$briefCmd`""

$briefTrigger  = New-ScheduledTaskTrigger -Daily -At "07:00"
$briefSettings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask `
    -TaskName   "AIHolding-MorningBrief" `
    -Action     $briefAction `
    -Trigger    $briefTrigger `
    -Settings   $briefSettings `
    -RunLevel   Limited `
    -Force

Write-Host "[OK] Registered: AIHolding-MorningBrief (runs daily at 07:00)"
Write-Host ""
Write-Host "To verify: Get-ScheduledTask -TaskName 'AIHolding-*' | Format-Table TaskName, State"
Write-Host "To remove: Unregister-ScheduledTask -TaskName 'AIHolding-BridgeStartup' -Confirm:`$false"

# Run this once to register the bridge startup task.
# Right-click -> Run with PowerShell  OR  powershell -ExecutionPolicy Bypass -File .\register_bridge_task.ps1

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$Script   = Join-Path $RepoRoot "start_bridge.ps1"

$action = New-ScheduledTaskAction `
    -Execute  "powershell.exe" `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`""

$trigger  = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount     5 `
    -RestartInterval  (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -MultipleInstances IgnoreNew

$principal = New-ScheduledTaskPrincipal `
    -UserId   $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Limited

Register-ScheduledTask `
    -TaskName  "AIHolding-BridgeStartup" `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -Principal $principal `
    -Force

Write-Host "Registered AIHolding-BridgeStartup — bridge starts automatically at login."
Write-Host "To verify: Get-ScheduledTask -TaskName 'AIHolding-*' | Format-Table TaskName, State"

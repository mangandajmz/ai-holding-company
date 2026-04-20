# AI Holding Company - Start Telegram Bridge
# Loads .env first, then .env.local overrides, and starts the async polling bridge.
# Run from anywhere; paths are resolved relative to this script.

$RepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
$EnvFile = Join-Path $RepoRoot ".env"
$EnvLocalFile = Join-Path $RepoRoot ".env.local"
$BridgeScript = Join-Path $RepoRoot "scripts\aiogram_bridge.py"

function Import-EnvFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}

if (-not (Test-Path $EnvFile) -and -not (Test-Path $EnvLocalFile)) {
    Write-Error "Neither .env nor .env.local was found at $RepoRoot"
    exit 1
}

Import-EnvFile -Path $EnvFile
Import-EnvFile -Path $EnvLocalFile

Set-Location $RepoRoot
python $BridgeScript

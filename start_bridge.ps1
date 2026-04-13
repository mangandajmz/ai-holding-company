# AI Holding Company — Start Telegram Bridge
# Loads .env.local and starts the polling bridge.
# Run from anywhere; paths are resolved relative to this script.

$RepoRoot  = Split-Path -Parent $MyInvocation.MyCommand.Definition
$EnvFile   = Join-Path $RepoRoot ".env.local"
$ScriptsDir = Join-Path $RepoRoot ".claude\worktrees\suspicious-davinci\scripts"

# Load .env.local into the current process
if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
} else {
    Write-Error ".env.local not found at $EnvFile"
    exit 1
}

Set-Location $ScriptsDir
python telegram_bridge.py

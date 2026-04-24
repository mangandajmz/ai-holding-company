# AI Holding Company - Safe Startup with Ollama Detection
# Waits for Ollama to be ready before starting the Telegram bridge.
# Logs all steps to logs/startup_diagnostic.log for troubleshooting.

$RepoRoot    = Split-Path -Parent $MyInvocation.MyCommand.Definition
$BridgeScript = Join-Path $RepoRoot "scripts\aiogram_bridge.py"
$EnvFile     = Join-Path $RepoRoot ".env"
$EnvLocalFile = Join-Path $RepoRoot ".env.local"
$LogDir      = Join-Path $RepoRoot "logs"
$LogFile     = Join-Path $LogDir "startup_diagnostic.log"
$OllamaExe   = "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe"

$MaxWaitSeconds = 30

if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir | Out-Null
}

function Write-Log($msg) {
    $ts   = Get-Date -Format "HH:mm:ss"
    $line = "[$ts] $msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Import-EnvFile($Path) {
    if (-not (Test-Path $Path)) { return }
    Get-Content $Path | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Avoid duplicate Path/PATH entries that break Start-Process on Windows.
            if ($key -ieq 'PATH') { return }
            [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
        }
    }
}

Write-Log "=== Bridge startup initiated ==="
Write-Log "RepoRoot:     $RepoRoot"
Write-Log "BridgeScript: $BridgeScript"

# Load .env then .env.local (local overrides base)
if (-not (Test-Path $EnvFile) -and -not (Test-Path $EnvLocalFile)) {
    Write-Log "[ERR] Neither .env nor .env.local found at $RepoRoot - aborting"
    exit 1
}
Import-EnvFile -Path $EnvFile
Import-EnvFile -Path $EnvLocalFile
Write-Log "[OK] Environment loaded"

# Ensure Ollama serve is running
Write-Log "[...] Starting Ollama serve..."
if (Test-Path $OllamaExe) {
    Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
    Write-Log "[OK] Ollama serve launched (or already running)"
} else {
    Write-Log "[WARN] Ollama not found at $OllamaExe - skipping"
}

# Wait for Ollama API on port 11434
Write-Log "[...] Waiting for Ollama API on port 11434..."
$ollamaReady = $false
for ($i = 1; $i -le $MaxWaitSeconds; $i++) {
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $tcp.Connect("127.0.0.1", 11434)
        $tcp.Close()
        $ollamaReady = $true
        break
    } catch {
        Write-Log "[...] Port 11434 not yet open, waiting... ($i/$MaxWaitSeconds)"
        Start-Sleep -Seconds 1
    }
}

if (-not $ollamaReady) {
    Write-Log "[WARN] Ollama API not reachable after $MaxWaitSeconds seconds - starting bridge anyway"
} else {
    Write-Log "[OK] Ollama API is reachable on port 11434"
}

# Start the bridge
if (-not (Test-Path $BridgeScript)) {
    Write-Log "[ERR] Bridge script not found: $BridgeScript - aborting"
    exit 1
}

Set-Location $RepoRoot
Write-Log "[...] Starting aiogram_bridge.py..."

# Normalize process PATH key casing for Start-Process on Windows.
$canonicalPath = $env:Path
[System.Environment]::SetEnvironmentVariable('PATH', $null, 'Process')
[System.Environment]::SetEnvironmentVariable('Path', $canonicalPath, 'Process')

$bridge = Start-Process -FilePath "python" -ArgumentList "`"$BridgeScript`"" -PassThru -NoNewWindow
Write-Log "[OK] Bridge started (PID: $($bridge.Id))"
Write-Log "[OK] Startup complete"

$bridge.WaitForExit()
Write-Log "[WARN] Bridge process exited (PID: $($bridge.Id)) - task will restart if configured"

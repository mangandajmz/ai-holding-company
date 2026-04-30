# AI Holding Company - Phase 1 Runbook

This folder is the local command center for Phase 1:
- 1 Executive Assistant agent
- monitors trading bots and websites
- produces daily heartbeat brief
- accepts owner directives from chat through a local Telegram bridge

Preferred chat option for this workspace:
- [README_TELEGRAM_BRIDGE.md](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/README_TELEGRAM_BRIDGE.md)

## Canonical Source Map

- Telemetry truth: `reports/daily_brief_latest.json`
- Division truth: `reports/phase2_divisions_latest.json`
- CEO truth: `reports/phase3_holding_latest.json`
- Approval/work truth: `state/board_approval_decisions.json`
- Metric truth: `state/property_metric_feed.json`

Timestamped reports and markdown files are derived artifacts for history and human readout, not the canonical machine-readable state.

## 1) Confirm Local Prerequisites

```powershell
python --version
ollama --version
```

If Ollama was not installed yet, official Windows install command:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Pull required local models:

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
```

## 2) Install OpenClaw (Windows)

```powershell
iwr -useb https://openclaw.ai/install.ps1 | iex
```

Complete onboarding and install background daemon:

```powershell
openclaw onboard --install-daemon
```

## 3) Configure OpenClaw for This Workspace

Copy the Phase 1 template into your OpenClaw config path:

```powershell
$openclawDir = Join-Path $env:USERPROFILE ".openclaw"
New-Item -ItemType Directory -Force -Path $openclawDir | Out-Null
Copy-Item ".\\openclaw\\openclaw.phase1.template.json5" (Join-Path $openclawDir "openclaw.json") -Force
```

Set local provider environment variables:

```powershell
setx OLLAMA_API_KEY "ollama-local"
setx OLLAMA_BASE_URL "http://127.0.0.1:11434"
```

Use Telegram or Slack (choose one):

Telegram:
- Set `channels.telegram.enabled: true`
- Set `channels.telegram.botToken`
- Keep `channels.slack.enabled: false`

Slack:
- Set `channels.telegram.enabled: false`
- Set `channels.slack.enabled: true`
- Set `channels.slack.appToken` and `channels.slack.botToken`

Restart OpenClaw daemon after config edits:

```powershell
openclaw daemon restart
```

## 4) Install Phase 1 Python Dependency

```powershell
python -m pip install -r requirements.txt
```

## 5) Local Smoke Tests

Run each tool once:

```powershell
python scripts/tool_router.py read_bot_logs --bot polymarket --lines 50
python scripts/tool_router.py check_website --website freeghosttools
python scripts/tool_router.py run_trading_script --bot polymarket --command-key health
python scripts/tool_router.py run_trading_script --bot polymarket --command-key report
python scripts/tool_router.py run_trading_script --bot mt5_desk --command-key report
python scripts/tool_router.py daily_brief --force
```

If successful, your latest report is:
- `reports/daily_brief_latest.md`
- `reports/daily_brief_latest.json`

## Optional: Polymarket on VPS (read-only)

If your Polymarket bot runs on a VPS, follow:

- [VPS_READONLY_SETUP.md](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/VPS_READONLY_SETUP.md)

## 6) Trigger First Heartbeat Through OpenClaw

```powershell
openclaw system event --mode now --text "Run AI Holding Company morning heartbeat now."
```

Then check chat (Telegram/Slack) for the executive brief.

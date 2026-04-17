# AI Holding Company - Phase 2 Runbook

Phase 2 introduces hierarchical CrewAI divisions on top of the Phase 1 telemetry stack.

## 1) Install/upgrade dependencies

```powershell
cd "C:\Users\james\OneDrive\Documents\Manganda LTD\AI Models\ai-holding-company"
python -m pip install -r requirements.txt
```

## 2) Confirm CrewAI + Ollama model config

Edit [config/projects.yaml](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/config/projects.yaml):

- `phase2.crewai.ollama_model` (default: `ollama/llama3.1:8b`)
- `phase2.crewai.ollama_model` (default: `ollama/llama3.2:latest`)
- `phase2.crewai.ollama_base_url` (default: `http://127.0.0.1:11434`)
- `phase2.targets.*` scorecard thresholds (MT5 risk/freshness, Polymarket risk caps, website freshness/latency)

## 3) Run divisions locally

Run both divisions:

```powershell
python scripts/tool_router.py run_divisions --division all --force
```

Run only one division:

```powershell
python scripts/tool_router.py run_divisions --division trading --force
python scripts/tool_router.py run_divisions --division websites --force
```

## 4) Check outputs

- [reports/phase2_divisions_latest.md](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/reports/phase2_divisions_latest.md)
- [reports/phase2_divisions_latest.json](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/reports/phase2_divisions_latest.json)

You should see:
- Trading Bots Division manager brief
- Websites Division manager brief
- Engine per division (`crewai_hierarchical` when CrewAI is available)
- Deterministic KPI scorecards per division with:
  - goal
  - desired outcome
  - target vs actual
  - variance with `GREEN/AMBER/RED` status
  - corrective actions

## 5) Switch OpenClaw to Phase 2 template

```powershell
$openclawDir = Join-Path $env:USERPROFILE ".openclaw"
Copy-Item ".\\openclaw\\openclaw.phase2.template.json5" (Join-Path $openclawDir "openclaw.json") -Force
openclaw daemon restart
```

Then trigger now:

```powershell
openclaw system event --mode now --text "Run AI Holding Company division heartbeat now."
```

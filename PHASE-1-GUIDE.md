# AI Holding Company — Phase 1: Core Monitoring

**Goal:** Get a single "Executive Assistant" agent running locally with Ollama + OpenClaw, connected to Telegram, monitoring your trading bots and websites, and sending you daily briefs.

**Your Setup:** Windows 11, 16GB RAM, CPU-only (no GPU), Telegram, 1-3 bots (Forex, Gold, Polymarket — mix of VPS and desktop), 1-2 websites. You already track PNL, drawdown, win rate, and uptime.

**Estimated time:** 1-2 hours

---

## Step 1: Install Ollama (5 min)

Open PowerShell **as Administrator** and run:

```powershell
winget install Ollama.Ollama
```

Or download the installer from https://ollama.com/download/windows

After installation, restart your terminal, then pull a model. For 16GB RAM with CPU-only, **Mistral 7B** is the best balance of speed and quality:

```powershell
ollama pull mistral:7b-instruct-v0.3-q4_K_M
```

This downloads ~4.4GB. While it downloads, continue to Step 2.

**Test Ollama:**
```powershell
ollama run mistral:7b-instruct-v0.3-q4_K_M "Say hello, you are the Executive Assistant of AI Holding Company."
```

You should get a response in 5-15 seconds (CPU-only is slower but fine for scheduled tasks). Press Ctrl+D to exit.

**Verify the API is running:**
```powershell
curl http://localhost:11434/v1/models
```

You should see your model listed.

---

## Step 2: Install Docker Desktop (10 min)

OpenClaw runs in Docker. Download and install Docker Desktop for Windows:
https://www.docker.com/products/docker-desktop/

After installation:
1. Open Docker Desktop
2. Go to Settings → General → Enable "Use the WSL 2 based engine" (should be default)
3. Go to Settings → Resources → set Memory to at least 4GB
4. Click "Apply & Restart"

**Test Docker:**
```powershell
docker --version
docker run hello-world
```

---

## Step 3: Create Your Telegram Bot (5 min)

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Name it: `AI Holding Company`
4. Username: `aicapitalgroup_bot` (must end in `_bot`, must be unique)
5. BotFather gives you a **token** like `7123456789:AAH...` — save this!
6. Send `/setdescription` → select your bot → enter: `AI Holding Company Executive Assistant — Daily briefs, trading bot monitoring, website health checks.`

---

## Step 4: Set Up the Project (10 min)

Your project files are already created in the `ai-holding-company` folder. The structure is:

```
ai-holding-company/
├── HEARTBEAT.md          ← Agent's scheduled task instructions
├── SOUL.md               ← Company identity & personality
├── docker-compose.yml    ← Docker config for OpenClaw
├── config/
│   └── .env.example      ← Environment template
├── tools/
│   ├── read_bot_logs.py  ← Trading bot log reader
│   ├── check_website.py  ← Website uptime checker
│   └── system_status.py  ← Ollama/Docker health check
└── logs/                 ← Runtime logs go here
```

### 4a. Create your .env file

Copy the example and fill in your real values:

```powershell
cd C:\path\to\ai-holding-company\config
copy .env.example .env
```

Open `.env` in a text editor and fill in:
- `TELEGRAM_BOT_TOKEN` — the token from BotFather
- `FOREX_BOT_LOG` — actual path to your Forex bot's log file
- `GOLD_BOT_LOG` — actual path to your Gold bot's log file
- `VPS_HOST`, `VPS_USER`, `VPS_KEY_PATH` — SSH details for your Polymarket VPS
- `WEBSITE_1`, `WEBSITE_2` — your actual website URLs

### 4b. Edit the monitoring tools

Open `tools/read_bot_logs.py` and update the `BOT_CONFIG` dictionary (around line 15) with your actual file paths and SSH details. Every line marked `# <-- EDIT THIS` needs your real values.

Open `tools/check_website.py` and update the `WEBSITES` list (around line 15) with your actual URLs.

---

## Step 5: Install & Start OpenClaw (15 min)

### 5a. Clone OpenClaw

```powershell
cd C:\path\to\ai-holding-company
git clone https://github.com/openclaw/openclaw.git
```

### 5b. Configure OpenClaw to use Ollama

OpenClaw uses an OpenAI-compatible API endpoint. Since Ollama exposes one at `localhost:11434/v1`, we point OpenClaw there.

Make sure your `docker-compose.yml` is in the `ai-holding-company` folder (it already is) and that your `.env` file has:

```
OLLAMA_HOST=http://host.docker.internal:11434
OLLAMA_MODEL=mistral:7b-instruct-v0.3-q4_K_M
```

### 5c. Start everything

Make sure Ollama is running (it should auto-start on Windows), then:

```powershell
cd C:\path\to\ai-holding-company
docker compose up -d openclaw-gateway
```

### 5d. Pair with Telegram

```powershell
docker compose run --rm openclaw-gateway openclaw-cli channel add telegram
```

Follow the prompts — it will ask for your bot token and send a pairing code to your Telegram. Approve it:

```powershell
docker compose run --rm openclaw-gateway openclaw-cli pairing approve telegram <CODE>
```

Replace `<CODE>` with the code shown in your Telegram chat.

---

## Step 6: Test Everything (15 min)

### Test 1: Chat with your bot

Open Telegram, find your `AI Holding Company` bot, and send:

```
Hello, who are you?
```

You should get a response from the Mistral model running locally. If it works, Ollama → OpenClaw → Telegram pipeline is live.

### Test 2: Run monitoring tools manually

Open PowerShell and test each tool:

```powershell
# Test bot log reader
python tools\read_bot_logs.py

# Test website checker
python tools\check_website.py

# Test system status
python tools\system_status.py
```

Each should print a formatted report. Fix any path errors before continuing.

### Test 3: Ask for a brief via Telegram

Send this to your bot in Telegram:

```
Run the daily brief. Check all trading bots and websites and give me the full report.
```

The agent should use the HEARTBEAT.md instructions to compile and send you a structured brief.

### Test 4: Give a CEO directive

Send:

```
Check the Forex bot specifically. What was today's PNL?
```

The agent should execute the read_bot_logs tool for the Forex bot and reply with the data.

---

## Step 7: Enable Scheduled Heartbeat (5 min)

The heartbeat should run automatically. In the OpenClaw workspace, HEARTBEAT.md is already configured. To set the schedule:

In your Telegram chat with the bot, send:

```
Set up the heartbeat to run daily at 07:00 and 19:00.
```

Or configure it in the OpenClaw heartbeat config. Create/edit `heartbeat.yaml` in the workspace root:

```yaml
# ai-holding-company/heartbeat.yaml
heartbeat:
  every: "12h"
  target: "last"
  directPolicy: "allow"
  lightContext: true
  isolatedSession: true
  tasks:
    - name: morning-brief
      interval: "24h"
      start_time: "07:00"
      prompt: "Run the full daily brief as described in HEARTBEAT.md. Check all bots and websites."
    - name: evening-recap
      interval: "24h"
      start_time: "19:00"
      prompt: "Run the evening recap. Summarise today's trading performance and any website issues."
```

Restart the container to pick up the config:

```powershell
docker compose restart openclaw-gateway
```

---

## Troubleshooting

**Ollama is slow / timing out:**
- CPU-only on 16GB is workable but expect 5-15s per response
- Close RAM-heavy apps while running
- If too slow, try a smaller model: `ollama pull phi3:mini-4k-instruct-q4_K_M`

**Docker can't reach Ollama:**
- Make sure Ollama is running: `ollama list` should respond
- Check that `host.docker.internal` resolves: `docker run --rm alpine ping host.docker.internal`
- On some Windows setups, use your local IP instead: `OLLAMA_HOST=http://192.168.x.x:11434`

**Telegram bot not responding:**
- Verify the bot token in `.env` is correct
- Check container logs: `docker compose logs openclaw-gateway`
- Make sure you completed the pairing step

**Bot logs not found:**
- Double-check paths in `read_bot_logs.py` — Windows paths need raw strings or forward slashes
- For VPS bots, test SSH manually first: `ssh -i C:\Users\J\.ssh\id_rsa user@your-vps-ip "tail -5 /path/to/log"`

---

## What You Have After Phase 1

✅ Ollama running locally with Mistral 7B (no cloud, no API costs)
✅ OpenClaw connected to Telegram as your always-on interface
✅ Executive Assistant agent that monitors Forex, Gold, and Polymarket bots
✅ Website uptime and SSL monitoring
✅ Automated morning (07:00) and evening (19:00) briefs
✅ Ability to give directives via Telegram and get immediate reports
✅ SOUL.md defining company identity
✅ All data stays on your machine

---

## Next: Phase 2 — Multi-Agent Division Structure

When you're ready, Phase 2 will introduce CrewAI hierarchical crews with:
- **Trading Bots Division** (Manager + Monitor + Analyst + Executor agents)
- **Websites Division** (Manager + Ops agents)
- Structured inter-agent collaboration and reporting

Say **"Phase 1 complete — ready for Phase 2"** when everything above is working.

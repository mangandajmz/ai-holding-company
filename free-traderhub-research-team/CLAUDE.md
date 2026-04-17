# FreeTraderHub Research Team — Operator Prompt

Act first, explain after. Do not ask permission for obvious steps.

---

## Models

Two models are available. Switch by editing `config.py`:

| Model | Config value | Notes |
|---|---|---|
| Llama 3.2 (default) | `ollama/llama3.2:latest` | Better reasoning, slower |
| Llama 3.1 8B | `ollama/llama3.1:8b` | Faster, lighter, good for quick runs |

```python
# config.py — line to change
MODEL = "ollama/llama3.2:latest"   # ← change this value
```

---

## Environment Setup

Always activate the virtual environment before running anything:

```bash
# Mac / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

Confirm you are in the right environment:
```bash
which python   # should show venv/bin/python
pip list | grep crewai
```

---

## Task Playbook

### Run the weekly crew

1. Confirm Ollama is running: `ollama serve` (run in a separate terminal if needed).
2. Confirm the models are pulled: `ollama list` — you should see `llama3.2:latest`.
3. Activate venv (see above).
4. Drop this week's GSC CSV in `inputs/gsc_export.csv` if it is Friday.
5. Run: `python run_weekly.py`
6. Reports will appear in `reports/YYYY-MM-DD/`.

---

### Show today's brief and summarise it conversationally

```
Read reports/YYYY-MM-DD/00_executive_brief.md and give me a plain-English
summary in 5 bullet points. Then tell me the single most important thing
I should do today.
```

Replace `YYYY-MM-DD` with today's date.

---

### Review the blog post against the compliance checklist

```
Read reports/YYYY-MM-DD/04_content_drafts.md. Check it against the
compliance rules in CLAUDE.md: no forbidden phrases, disclaimer present
verbatim, no fabricated personal stories, minimum 700 words. Report any
failures and fix them inline.
```

---

### Improve or rewrite sections of the blog post

```
Read reports/YYYY-MM-DD/04_content_drafts.md. The introduction is too
generic. Rewrite it to open with a specific problem a retail forex trader
faces when sizing a position, then segue into how our Lot Size calculator
solves it. Keep the rest of the post unchanged.
```

---

### Fix social posts to match each platform tone

```
Read the social posts in reports/YYYY-MM-DD/04_content_drafts.md.
The Twitter/X post sounds too formal — make it punchy and conversational,
under 260 characters, no hashtag spam. The LinkedIn post needs to be more
professional and lead with a data point. The Reddit post must not sound
promotional at all — rewrite it as a helpful community comment.
```

---

### Tell me which Reddit threads to reply to

```
Read reports/YYYY-MM-DD/02_community_monitor.md. Pick the 3 threads most
worth engaging with this week. For each one give me: the thread URL, one
sentence explaining why it is worth replying to, and a suggested opening
line I can personalise (do NOT write the full reply for me).
```

---

### Switch between models

Edit `config.py`:
```python
# Faster model
MODEL = "ollama/llama3.1:8b"

# Back to default
MODEL = "ollama/llama3.2:latest"
```

Then re-run. No other changes needed.

---

### Schedule with cron (Mac and Linux)

Open crontab: `crontab -e`

Add a line to run every Monday at 08:00:
```
0 8 * * 1 cd /path/to/free-traderhub-research-team && /path/to/venv/bin/python run_weekly.py >> logs/cron.log 2>&1
```

Find your paths:
```bash
pwd                          # project path
which python                 # venv python path (after activating)
```

Create the logs folder first: `mkdir -p logs`

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `Connection refused` on port 11434 | Ollama not running | Run `ollama serve` in a terminal |
| `model not found` error | Model not pulled | `ollama pull llama3.2` or `ollama pull llama3.1:8b` |
| `ModuleNotFoundError` | Packages not installed / wrong venv | Activate venv, then `pip install -r requirements.txt` |
| Agent returns empty output | Model timed out or context overflow | Switch to `llama3.1:8b` for a faster run; check Ollama logs |
| Reddit 429 Too Many Requests | Rate limited | Wait 60 seconds and re-run; Reddit limits unauthenticated requests |
| ChromaDB error on startup | Stale vector store | Delete the `memory/` folder and re-run |

---

## Full Disclaimer (use verbatim)

> DISCLAIMER: This content is for educational purposes only and does not
> constitute financial advice. Trading forex, crypto, or any financial
> instrument involves significant risk of loss and may not be suitable for
> all investors. Past performance is not indicative of future results.
> Always consult a qualified financial professional before making any
> investment or trading decisions. FreeTraderHub is not a regulated
> financial entity and does not provide investment advice.

---

## Forbidden Phrases (never use in any published content)

- will make you money
- guaranteed
- always profitable
- buy now
- sell now
- expected return
- you should trade
- I recommend buying
- risk-free
- certain profit
- never lose
- cant lose / can't lose
- 100% accurate

---

## Site Context

| Field | Value |
|---|---|
| Site name | FreeTraderHub |
| URL | https://freetraderhub.com |
| What it is | Free forex and crypto trading calculator suite |
| Audience | Retail forex and crypto traders, beginner to intermediate |
| Calculators | Lot Size, Pip Value, Position Size, Risk/Reward, Compounding, Drawdown |
| Tone | Educational, helpful, jargon-light, no hype |
| Competitors | babypips.com/tools, myfxbook.com/forex-calculators, forexprofitcalculator.net |

---

*Act first, explain after. Do not ask permission for obvious steps.*

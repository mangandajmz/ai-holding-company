# FreeTraderHub Agentic Marketing Research Team

An autonomous, local-first marketing research crew for [FreeTraderHub](https://freetraderhub.com) — built with [CrewAI](https://github.com/joaomdmoura/crewAI) and [Ollama](https://ollama.ai). Runs entirely on your machine. No external API keys required.

Every Monday morning it researches the forex/crypto calculator market, monitors Reddit trading communities, analyses your Google Search Console data, writes compliant content drafts, and delivers an executive brief — all without leaving your computer.

---

## What it does

| Step | Agent | Output |
|---|---|---|
| Market research | Senior Market Researcher | Trends, competitor analysis, news headlines, keyword opportunities |
| Community monitoring | Community Intelligence Monitor | Reddit hot posts, pain points, 3 reply-worthy threads |
| Growth strategy | Growth Strategy Analyst | GSC analysis, content gaps, weekly action plan |
| Content drafting | Compliant Content Writer | Blog post ≥700 words, 3 social posts, email subject line |
| Executive brief | Marketing Research Team Lead | Summary of all findings + this week's priority actions |

---

## Available Models

| Model | config.py value | Best for |
|---|---|---|
| Llama 3.2 (default) | `ollama/llama3.2:latest` | Better reasoning, full weekly runs |
| Llama 3.1 8B | `ollama/llama3.1:8b` | Faster runs, lower RAM usage |

---

## Team Architecture

```
                  ┌─────────────────────────────────┐
                  │  Marketing Research Team Lead   │
                  │   (manager · hierarchical)       │
                  └────────────────┬────────────────┘
                                   │ delegates & quality-gates
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
┌─────────┴──────────┐  ┌─────────┴──────────┐  ┌─────────┴──────────┐
│  Senior Market     │  │ Community Intel     │  │ Growth Strategy    │
│  Researcher        │  │ Monitor             │  │ Analyst            │
│                    │  │                     │  │                    │
│ Tools:             │  │ Tools:              │  │ Tools:             │
│  DuckDuckGo        │  │  get_reddit_        │  │  read_gsc_csv      │
│  ScrapeWebsite     │  │  hot_posts          │  │                    │
│  get_finance_      │  │  scan_all_          │  │ Output:            │
│  headlines         │  │  subreddits         │  │  03_weekly_        │
│                    │  │                     │  │  strategy.md       │
│ Output:            │  │ Output:             │  └────────────────────┘
│  01_market_        │  │  02_community_      │
│  research.md       │  │  monitor.md         │
└────────────────────┘  └─────────────────────┘
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │ context passed to
                          ┌────────┴────────┐
                          │ Compliant        │
                          │ Content Writer   │
                          │                  │
                          │ Output:          │
                          │  04_content_     │
                          │  drafts.md       │
                          └──────────────────┘
                                   │
                          ┌────────┴────────┐
                          │  00_executive_  │
                          │  brief.md       │
                          └─────────────────┘
```

---

## Setup

> Assumes [Ollama](https://ollama.ai) is already installed.

### 1. Pull the models

```bash
ollama pull llama3.2
ollama pull llama3.1:8b
```

### 2. Clone / navigate to the project

```bash
cd free-traderhub-research-team
```

### 3. Create and activate a virtual environment

```bash
# Mac / Linux
python3 -m venv venv
source venv/bin/activate

# Windows
python -m venv venv
venv\Scripts\activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run

Make sure Ollama is running (`ollama serve` in a separate terminal if needed), then:

```bash
python run_weekly.py
```

Reports appear in `reports/YYYY-MM-DD/`.

---

## Using with Claude CLI

Open this project in Claude Code (`claude` in the project directory). CLAUDE.md is loaded automatically. Example commands:

```
Show me today's executive brief in 5 bullet points and tell me the one thing I must do today.
```

```
Review the blog post in today's reports folder against the compliance checklist and fix any issues.
```

```
Rewrite the Twitter/X post to be punchier and under 260 characters.
```

```
Which Reddit threads should I reply to this week? Give me a suggested opening line for each — not the full reply.
```

---

## Optional: Add GSC data

1. Export CSV from Google Search Console → Performance → Search results.
2. Rename to `gsc_export.csv`.
3. Drop in `inputs/`.
4. Run as normal.

Without the file the crew continues and the Analyst bases strategy on Reddit + research data. See `inputs/README.md` for full instructions.

---

## Optional: Schedule with cron (Mac / Linux)

```bash
crontab -e
```

Add (runs every Monday at 08:00):
```
0 8 * * 1 cd /path/to/free-traderhub-research-team && /path/to/venv/bin/python run_weekly.py >> logs/cron.log 2>&1
```

---

## Weekly Routine

| Day | Action |
|---|---|
| Monday | Run `python run_weekly.py`, read executive brief, reply to Reddit threads |
| Monday–Wednesday | Edit blog post (fill [EDITOR'S NOTE] tags), publish to site |
| Wednesday | Schedule social posts |
| Thursday | Send newsletter |
| Friday | Export GSC CSV → `inputs/gsc_export.csv` |

---

## Compliance Rules

Three things that must never change:

1. **Disclaimer** — must appear verbatim at the end of every published blog post.
2. **Forbidden phrases** — none of the 13 listed phrases may appear in any published content.
3. **No fabricated experience** — personal anecdotes must be flagged with `[EDITOR'S NOTE: ...]` tags, never invented by the AI.

### Pre-publish checklist

- [ ] Disclaimer present verbatim at end of post
- [ ] Zero forbidden phrases (search the doc)
- [ ] All [EDITOR'S NOTE] tags filled in or removed
- [ ] Internal links to relevant calculators added
- [ ] Word count ≥ 700
- [ ] Proofread for tone — educational, not salesy

---

## Project Structure

```
free-traderhub-research-team/
├── config.py                 # All configuration (models, site, feeds, limits)
├── crew.py                   # Agents, tasks, and crew assembly
├── run_weekly.py             # Entry point
├── requirements.txt
├── CLAUDE.md                 # Operator prompt for Claude CLI
├── README.md
├── .gitignore
├── tools/
│   ├── __init__.py
│   ├── reddit_reader.py      # Reddit public JSON API tools
│   ├── rss_reader.py         # RSS feed parser tool
│   └── gsc_reader.py         # Google Search Console CSV reader
├── inputs/
│   └── README.md             # GSC export instructions
├── reports/                  # Auto-created, gitignored
│   └── YYYY-MM-DD/
│       ├── 00_executive_brief.md
│       ├── 01_market_research.md
│       ├── 02_community_monitor.md
│       ├── 03_weekly_strategy.md
│       └── 04_content_drafts.md
└── memory/                   # CrewAI vector memory, gitignored
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `Connection refused` (port 11434) | Run `ollama serve` |
| `model not found` | `ollama pull llama3.2` |
| `ModuleNotFoundError` | Activate venv + `pip install -r requirements.txt` |
| Empty agent output | Switch to `llama3.1:8b`; check Ollama logs |
| Reddit 429 error | Wait 60 seconds and re-run |
| ChromaDB startup error | Delete `memory/` folder and re-run |

---

## Licence

For internal use by Manganda Ltd / FreeTraderHub. Not licensed for redistribution.

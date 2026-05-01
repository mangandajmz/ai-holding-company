# AI Holding Company — Handoff Context
**For any AI coding tool starting a new session.**
Read PLAN.md and CLAUDE.md completely before doing anything else.

---

## Current State (as of 2026-05-01)

| Item | Status |
|------|--------|
| PLAN.md version | 5.7 |
| Latest commit | see `git log --oneline -1` |
| Tests | 58/58 passing |
| Trading division | RED (Polymarket sync issue + MT5 health rc=1) |
| Websites division | RED (latency / uptime alerts) |
| Commercial division | GREEN |
| Content Studio | GREEN |
| Stage A | ✅ Complete |
| Stage B | ✅ Complete |
| Stage C | ✅ Complete |
| Stage D | ✅ Complete |
| Stage G | ✅ Complete (commit 1367323, Codex CLEAN) |
| Stage H | ✅ Complete (2026-05-01 — board_pack verified, 58 tests) |
| Stage I | ✅ Complete (Developer Tool, semantic memory, R9 proof) |
| Stage J | ✅ Complete (Content Studio light, brief-driven, CEO-gated) |
| Sprint 0 | ✅ Complete — Stage H closed, PLAN.md → v5.7 |
| Sprint 1 | 🔵 Active — orchestrator.py + event store + Telegram kill switch |

---

## Active Work Lane — Agentic Orchestrator

**Approved CEO plan:** `~/.gstack/projects/mangandajmz-ai-holding-company/ceo-plans/2026-04-30-agentic-holding-company.md`
**Engineering review:** `~/.gstack/projects/mangandajmz-ai-holding-company/eng-reviews/2026-04-30-orchestrator-sprint.md`

### Sprint 1 — orchestrator.py skeleton (ACTIVE)

Build a persistent event-driven orchestrator daemon. Key specs:

**Event store:** SQLite at `state/events.db` (stdlib sqlite3, atomic writes).
Schema:
```sql
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    division TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload TEXT,
    run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_division_ts ON events (division, ts);
```

**Reasoning cache:** `state/last_reasoning.json`
Fields: `generated_at_utc`, `division`, `event_id`, `diagnosis`, `recommended_action`, `confidence`
Brief shows `⚠️ STALE — reasoning from Xh ago` if cache age > 2h.

**Telegram send:** Import `TelegramBridge` as a class; call `send_message(text)` directly.
Do NOT spawn a subprocess or start the polling loop.

**Telegram kill switch:** Add `/orchestrator stop|start|status` to `handle_text()` dispatch
in `scripts/telegram_bridge.py`. Do NOT create a new bridge instance.

**PID file:** `state/orchestrator.pid`. Status check uses `psutil.pid_exists(pid)`.
Three states: RUNNING, CRASHED (stale PID), STOPPED (no PID file).

**Process supervision:** Windows Task Scheduler, 5-min restart-on-failure.
orchestrator.py must `sys.exit(1)` on fatal error.

**Permitted autonomous actions (no escalation):**
- Re-run a division health check
- Write report to `reports/`
- Update `state/` files
- Send informational Telegram message
- Log to `state/events.db`

**Escalation gates (Telegram alert + CEO decision):** R2, R3, R5

**Done when:**
- Orchestrator runs, emits events, reads them back
- Ollama diagnosis cached in `state/last_reasoning.json`
- `/orchestrator status` returns RUNNING via Telegram `--simulate-text`
- 58 + 8 = 66 tests passing

### Sprint 2 — Websites + Commercial wired (NEXT)
All 3 divisions emit events, orchestrator handles each. Done when: 66 + 4 = 70 tests.

### Sprint 3 — Morning brief one-pager + pinned health lights
Brief readable in <60s. Pinned message updated on every run. `state/pinned_health_msg.json`.

### Sprint 4 — Weekly retro (Sunday 20:00 Vancouver)
Windows Task Scheduler. UTC internally, America/Vancouver for display. Catch-up on missed boot.

### Sprint 5 — GitHub Issues cadence
RED division run → GH Issue. GREEN → close it. 24h dedup (same RED division within 24h = update, not create).

---

## Key Files

| File | Purpose |
|------|---------|
| PLAN.md | Master plan — read first, always |
| CLAUDE.md | Dev philosophy + Code Review Gate |
| scripts/orchestrator.py | Event-driven daemon (Sprint 1 — build this) |
| scripts/telegram_bridge.py | Telegram interface — add /orchestrator commands here |
| scripts/phase3_holding.py | CEO layer — board_pack mode (Stage H, complete) |
| scripts/phase2_crews.py | Division orchestration layer |
| scripts/tool_router.py | CLI entry point for all scripts |
| scripts/utils.py | Shared helpers — use existing, add none |
| config/projects.yaml | Central integration config |
| config/targets.yaml | KPI thresholds |
| state/events.db | SQLite event store (create in Sprint 1) |
| state/last_reasoning.json | Ollama reasoning cache |
| state/orchestrator.pid | PID file for daemon supervision |
| state/pinned_health_msg.json | Telegram pinned message_id (Sprint 3) |
| reports/stage_h_brief_1.json | First board_pack verification run |
| reports/stage_h_brief_2.json | Second board_pack verification run |

---

## Non-Negotiable Rules (summary — full list in PLAN.md §2)

- R1: All runtime inference via Ollama only. No cloud APIs.
- R2: MT5 and Polymarket bot source is read-only without CEO approval.
- R3: Website source read-only except with Developer Tool + CEO approval.
- R5: No cost commitment >$50 without CEO.
- R8: Code writes only inside ai-holding-company/. Never bot or website source without approval.
- R9: Two net-negative weeks → halt + review.
- R11: No OpenClaw. python-telegram-bot only. Telegram bridge is the sole automation interface.
- CLAUDE.md: shell=False always. shlex.split() on config strings. No overengineering.
- Code Review Gate: Style/Linting + Logic + Security after every sprint. Non-negotiable.

---

## Stage H Context (complete — do not re-implement)

Stage H is done. `_build_board_review()` returns 10-field Board Pack items.
`_validate_board_pack_item()` enforces MA gate (rationale + owner + measurement_plan required).
Dissent agent in `crews/holding_ceo.yaml` files one objection minimum per item.
Two consecutive board_pack runs saved: `reports/stage_h_brief_1.json`, `reports/stage_h_brief_2.json`.
58 tests passing — 11 new board_pack tests in `tests/test_board_pack.py`.

---

*HANDOFF.md — updated 2026-05-01 — regenerate this file at the end of each stage.*

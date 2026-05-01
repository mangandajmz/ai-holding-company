# AI Holding Company — Handoff Context
**For any AI coding tool starting a new session.**
Read PLAN.md and CLAUDE.md completely before doing anything else.

---

## Current State (as of 2026-05-01)

| Item | Status |
|------|--------|
| PLAN.md version | 5.8 |
| Latest commit | see `git log --oneline -1` |
| Tests | 100/100 passing |
| Trading division | RED (Polymarket sync issue + MT5 health rc=1) |
| Websites division | RED (latency / uptime alerts) |
| Commercial division | GREEN |
| Content Studio | GREEN |
| Stage A–D | ✅ Complete |
| Stage G | ✅ Complete (commit 1367323, Codex CLEAN) |
| Stage H | ✅ Complete (board_pack verified, 58 tests) |
| Stage I | ✅ Complete (Developer Tool, semantic memory, R9 proof) |
| Stage J | ✅ Complete (Content Studio light, brief-driven, CEO-gated) |
| Sprint 0 | ✅ Complete — Stage H closed, PLAN.md → v5.7 |
| Sprint 1 | ✅ Complete — orchestrator.py + event store + Telegram kill switch |
| Sprint 2 | ✅ Complete — all three divisions wired |
| Sprint 3 | ✅ Complete — morning brief + pinned health lights |
| Sprint 4 | ✅ Complete — weekly retro Sunday 20:00 Vancouver, catch-up |
| Sprint 5 | ✅ Complete — GitHub Issues cadence (RED→open, 24h dedup, GREEN→close) |

---

## Agentic Orchestrator — COMPLETE (Sprints 0-5)

**Approved CEO plan:** `~/.gstack/projects/mangandajmz-ai-holding-company/ceo-plans/2026-04-30-agentic-holding-company.md`
**Engineering review:** `~/.gstack/projects/mangandajmz-ai-holding-company/eng-reviews/2026-04-30-orchestrator-sprint.md`

All five sprints are done. The system is now fully agentic:
- `scripts/orchestrator.py` — daemon loop, SQLite events, Ollama reasoning, Telegram kill switch
- `scripts/telegram_bridge.py` — `/orchestrator stop|start|status`, pinned health lights, one-pager brief
- `scripts/weekly_retro.py` — Sunday 20:00 Vancouver, catch-up on boot, reports/retros/
- `scripts/github_issues.py` — RED→open issue, 24h dedup→comment, GREEN→close

### Task Scheduler entries needed (Windows)

| Task | Command | Schedule |
|------|---------|---------|
| Orchestrator | `python scripts/orchestrator.py` | At boot + every 5 min restart-on-failure |
| Morning brief | `python scripts/telegram_bridge.py --send-morning-brief` | Daily 08:00 America/Vancouver |
| Weekly retro | `python scripts/weekly_retro.py` | Sunday 20:00 America/Vancouver |

### GitHub Issues: one-time setup
Add `github_repo: "your-org/ai-holding-company"` to `config/projects.yaml` and run `gh auth login` on the host. Without `github_repo`, the cadence silently skips (action=none).

---

## Key Files

| File | Purpose |
|------|---------|
| PLAN.md | Master plan — read first, always |
| CLAUDE.md | Dev philosophy + Code Review Gate |
| scripts/orchestrator.py | Event-driven daemon — runs all three divisions every 5 min |
| scripts/telegram_bridge.py | Telegram interface — add /orchestrator commands here |
| scripts/phase3_holding.py | CEO layer — board_pack mode (Stage H, complete) |
| scripts/phase2_crews.py | Division orchestration layer |
| scripts/tool_router.py | CLI entry point for all scripts |
| scripts/utils.py | Shared helpers — use existing, add none |
| config/projects.yaml | Central integration config |
| config/targets.yaml | KPI thresholds |
| state/events.db | SQLite event store — all division events |
| state/last_reasoning.json | Ollama reasoning cache (stale after 2h) |
| state/orchestrator.pid | PID file for daemon supervision |
| state/pinned_health_msg.json | Telegram pinned message_id for health lights |
| state/retro_state.json | Last retro sent date (catch-up logic) |
| state/gh_issues.json | Open GH issue numbers per division |
| scripts/weekly_retro.py | Weekly retro generator (Sprint 4) |
| scripts/github_issues.py | GitHub Issues cadence (Sprint 5) |
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
100 tests passing — 11 board_pack + 15 orchestrator + 17 retro + 10 GH issues + others.

---

*HANDOFF.md — updated 2026-05-01 — Sprints 0-5 complete, v5.8.*

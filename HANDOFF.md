# AI Holding Company — Handoff Context
**For any AI coding tool starting a new session.**
Read PLAN.md and CLAUDE.md completely before doing anything else.

---

## Current State (auto-generated from live state at 2026-04-25T05:49:47.070133+00:00)

| Item | Status |
|------|--------|
| Latest commit | `962a105` |
| Latest commit timestamp | 2026-04-24T22:46:14-07:00 |
| Phase 2 report generated | 2026-04-25T05:49:47.043300+00:00 |
| Phase 3 mode | board_review |
| Company score | RED |
| Trading division | RED |
| Websites division | RED |
| Content Studio | GREEN |
| Commercial division | Not emitted by Phase 2 |
| Live divisions in Phase 2 | trading, websites, content_studio |
| Enabled tracked projects | content_studio (internal_division), mt5_desk (capital_risk), polymarket (capital_risk) |
| Bridge provider | telegram |

## Two Active Work Lanes

### Lane 1 — Holding Company Build (STAGE_H_PROMPTS.md)
Holding Board v2 + Board Pack upgrade. Five blocks in order:
- Block 1: `crews/holding_ceo.yaml` — add dissent_agent + dissent_task
- Block 2: `scripts/phase3_holding.py` — upgrade `_build_board_review()` to 10-field output
- Block 3: Add `board_pack` mode to `_run_ceo_brief()`, upgrade `_build_phase3_markdown()`, extend `_ALLOWED_PHASE3_SUBCOMMANDS`
- Block 4: Add `_validate_board_pack_item()` pure function + MA gate enforcement with ⚠️ Telegram prefix
- Block 5: 11 new tests + two GREEN board_pack runs saved as `stage_h_brief_1/2.json` + PLAN.md → v5.5

**Always run blocks in order. Codex review gate after every block. Gate definition is in CLAUDE.md.**

### Lane 2 — Property Fixes (STAGE_D_PROMPTS.md)
Website and config hygiene. Runs parallel to Lane 1 — does not block it.
- Block 1: projects.yaml path corrections (15 min)
- Block 2: Messaging conflicts — FreeGhostTools + FreeTraderHub (40 min)
- Block 3: Umami analytics on FreeGhostTools (40 min)
- Block 4: Polymarket SSH rc=255 diagnosis (30 min)
- Block 5: MT5 signal verification (15 min)

---

## How to Pick Up Mid-Lane

If a previous tool completed some blocks:
1. Check the success criteria in the prompt file for the last completed block.
2. Verify the criteria pass before starting the next block.
3. Never start a new block without confirming the previous one is clean.

---

## Key Files

| File | Purpose |
|------|---------|
| PLAN.md | Master plan — read first, always |
| CLAUDE.md | Development philosophy + Code Review Gate — read alongside PLAN.md |
| STAGE_H_PROMPTS.md | Claude Code prompts for Stage H (Lane 1) |
| STAGE_D_PROMPTS.md | Claude Code prompts for property fixes (Lane 2) |
| config/projects.yaml | Central integration config |
| config/targets.yaml | KPI thresholds |
| scripts/phase2_crews.py | Division orchestration layer |
| scripts/phase3_holding.py | CEO layer — Board Pack logic lives here |
| scripts/aiogram_bridge.py | Sole production Telegram bridge for commands, approvals, and scheduling |
| scripts/utils.py | Shared helpers — use existing ones, add none |
| crews/holding_ceo.yaml | CEO crew spec — Stage H Block 1 target |
| crews/commercial_division.yaml | Historical commercial crew spec — not a live Phase 3 lane unless Phase 2 emits it |
| reports/ | Generated output — do not edit manually |

---

## Non-Negotiable Rules (summary — full list in PLAN.md §2)

- R1: All runtime inference via Ollama only. No cloud APIs in the system.
- R2: MT5 and Polymarket bot source is read-only.
- R3: Website source read-only except with explicit CEO approval.
- R8: Code writes only inside ai-holding-company/. Never bot or website source without approval.
- R11: No OpenClaw. Telegram bridge is the sole automation interface.
- CLAUDE.md: No overengineering. No new helpers without removing a duplicate.
  shell=False always. No LLM arithmetic — Python only for financial calculations.
- CLAUDE.md Code Review Gate: Style/Linting + Logic + Security check after every block.
  Resolve ALL issues before moving to the next block. Non-negotiable.

---

## Stage H Context (read before touching phase3_holding.py)

Current `_build_board_review()` returns only 3 fields: `{priority, topic, decision}`.
Stage H upgrades it to 10 fields — the 8 Board Pack fields from PLAN.md §8
(rationale, expected_upside, effort_cost, confidence, owner, deadline, dissent,
measurement_plan) plus priority and topic for backward compat.

The dissent field is populated by the new `dissent_agent` in holding_ceo.yaml.
One objection minimum per Board Pack item — non-negotiable per PLAN.md §8.

MA gate (Block 4): if any board_pack item lacks rationale, owner, or measurement_plan,
`_validate_board_pack_item()` returns False and the Telegram message gets a ⚠️ prefix.

---

*HANDOFF.md — updated 2026-04-16 — regenerate this file at the end of each stage.*

## Efficiency LLM Exception

DeepSeek and `scripts/free_llm_client.py` are intentionally kept as opt-in
advisory tooling for development, review, research support, and summarisation.
They must not own board/memory truth, runtime scoring, trading, publishing,
owner chat autonomy, or unattended execution. Core company operations stay
Ollama-local unless a later CEO rule change says otherwise.

# Retrofit Plan Analysis

Date: 2026-05-09

This analysis validates the proposed 9-skill retrofit against the current `ai-holding-company` folder. I treated first-party docs, configs, scripts, crew specs, tests, and nested project runbooks as relevant. I treated virtualenvs, `.next`, caches, generated worktrees, raw logs, and generated reports as structure/cleanup signal rather than product source.

## Executive Synthesis

The repo already has a real operating shell: Telegram is the owner interface, `scripts/tool_router.py` is the command router, `scripts/phase2_crews.py` and `scripts/phase3_holding.py` produce division and CEO briefs, `scripts/company_loop.py` records file-first operating loops, `scripts/content_studio.py` handles CEO-gated drafts, `scripts/weekly_retro.py` runs a recurring retro, and `scripts/local_vector_memory.py` provides local vector memory.

The retrofit should not introduce a parallel agent platform. It should add a thin, opinionated skill layer on top of the existing command/router/report/state shape. The main mismatch is naming and packaging: the plan assumes slash-command skills, but the project currently uses Telegram bot commands, CLI subcommands, crew YAML, markdown runbooks, and local state files. Since Telegram is the sole automation interface, runtime command names should use Telegram-safe underscores, while markdown skill files can keep the plan's hyphenated names.

## Fits Cleanly

- Risk aggregate daily: `scripts/phase3_holding.py`, `crews/holding_ceo.yaml`, `config/targets.yaml`, `reports/phase3_holding_latest.*`, `scripts/aiogram_bridge.py` `/brief`, `/board`, `/approvals`.
  Current autonomy: mostly Auto for read-only brief generation; Approve for board items through `/approve`, `/deny`, `/assign`, `/start`, `/done`. This is the closest existing match to `/risk-aggregate-daily`.

- Portfolio retro weekly: `scripts/weekly_retro.py`, `tests/test_weekly_retro.py`, `state/retro_state.json`, `reports/retros/`.
  Current autonomy: Auto. It already has weekly scheduling/catch-up logic and Telegram send behavior, but only summarizes `state/events.db`; it does not yet pull every other skill output, commits, deploys, incidents, and decisions as the proposed skill requires.

- Content brief to draft: `scripts/content_studio.py`, `crews/content_studio.yaml`, `README_TELEGRAM_BRIDGE.md`, Telegram `/content`, `/content_status`, `/content_approve`, `/content_deny`, `artifacts/content_studio_drafts.jsonl`.
  Current autonomy: Approve for publication; Auto for draft creation once a brief is submitted. It already enforces `PENDING_CEO_APPROVAL` and blocks auto-publish.

- Holding-company approvals and guardrails: `scripts/aiogram_bridge.py`, `state/board_approval_decisions.json`, `docs/templates/approval_request.md`, `docs/LOOP_OPERATING_MODEL.md`, `kernel/work_items.py`.
  Current autonomy: Approve. This is not one of the 9 skills, but it is the substrate all 9 should reuse.

- Memory layer: `scripts/local_vector_memory.py`, `memory/`, `scripts/tool_router.py log_direction`, `scripts/tool_router.py memory_search`, Telegram `/memory`.
  Current autonomy: Auto for saving/searching local notes. This fits the gstack/g-brain intent, but it is a local JSONL/Ollama embedding store, not a full markdown skill memory system.

- Trading research foundation: `mt5-agentic-desk/tools/backtest_engine.py`, `mt5-agentic-desk/tools/backtest_tool.py`, `mt5-agentic-desk/tools/strategy_qualification_report.py`, `mt5-agentic-desk/tools/daily_operator_workflow.py`, `mt5-agentic-desk/docs/evidence-build-checklist-2026-05-04.md`, `mt5-agentic-desk/docs/adversarial-review-2026-05-04.md`.
  Current autonomy: Guardrail/Approve. The MT5 desk already separates research from trading and blocks active promotion without evidence. It is not yet exposed as a parent-level `/backtest-review` skill.

## Needs Adapting

- `/backtest-review` overlaps with MT5 adversarial review and qualification reports.
  Proposed change: create a parent-level skill spec and command wrapper that reads MT5 research/backtest artifacts and produces a standardized adversarial review record under `reports/skills/backtest-review/`. Do not move backtesting logic into the parent repo. Add pass-rate and changed-after-review counters so the `<40% pass unchanged` success metric is trackable.
  Candidate files: add `docs/skills/backtest-review.md`, add `scripts/skill_backtest_review.py`, wire `tool_router.py backtest_review`, optionally wire Telegram `/backtest_review`.
  Target autonomy: Guardrail.

- `/data-quality-daily` overlaps with `scripts/monitoring.py`, `scripts/phase2_crews.py` trading scorecards, and MT5 runtime/data health checks.
  Proposed change: adapt it into a pre-market data integrity skill that reads MT5 feed freshness, bar gaps, strategy library freshness, Polymarket remote sync age, and current config thresholds. The proposed vendor cross-check/corporate-actions scope does not fit current FX/Polymarket reality; make those explicit N/A checks until real equities/data vendors exist.
  Candidate files: add `docs/skills/data-quality-daily.md`, add `scripts/skill_data_quality_daily.py`, extend `config/targets.yaml` with only proven thresholds if needed.
  Target autonomy: Guardrail.

- `/content-brief-to-draft` overlaps with two systems: lightweight Content Studio in parent repo and the richer `free-traderhub-research-team` weekly crew.
  Proposed change: keep parent `scripts/content_studio.py` as the skill runtime for brief-in/draft-out. Treat `free-traderhub-research-team` as a weekly research source feeding briefs, not as the runtime command. Rename surface from generic `/content` to `/content_brief` if you want the skill name to be explicit, but keep `/content` as an alias for muscle memory.
  Target autonomy: Approve for publication; Auto for draft creation.

- `/analytics-weekly` overlaps with `scripts/fth_monitor.py`, `free-traderhub-research-team/run_weekly.py`, `docs/templates/weekly_business_scorecard.md`, and Phase 3 property department briefs.
  Proposed change: make it a weekly website analytics digest skill focused on FTH first: Umami/manual KPIs, GSC export summary, content production, email list, affiliate clicks/revenue, anomalies, and next decisions. Do not build generalized analytics until another website has real metrics.
  Candidate files: add `docs/skills/analytics-weekly.md`, add `scripts/skill_analytics_weekly.py`, have it read `state/property_metrics/freetraderhub/shared.json` and `free-traderhub-research-team/reports/*/00_executive_brief.md`.
  Target autonomy: Auto.

- `/portfolio-retro-weekly` fits `scripts/weekly_retro.py` but is too narrow.
  Proposed change: extend the retro collector to include latest skill reports from `reports/skills/`, board approval decisions, content draft decisions, company loops, GitHub issue cadence, and recent git commits/deploy notes where locally available. Keep the output short.
  Candidate files: edit `scripts/weekly_retro.py`, `tests/test_weekly_retro.py`, add `docs/skills/portfolio-retro-weekly.md`.
  Target autonomy: Auto.

- `/risk-aggregate-daily` fits Phase 3 but needs a skill identity.
  Proposed change: add a skill spec that defines the one-page cross-portfolio brief contract and maps it to `tool_router.py run_holding --mode heartbeat --force` plus board-pack escalation when RED/AMBER exists. Do not duplicate `phase3_holding.py`.
  Candidate files: add `docs/skills/risk-aggregate-daily.md`; optionally add a `tool_router.py risk_aggregate_daily` alias to existing `run_holding`.
  Target autonomy: Auto for the brief; Approve for actions created from it.

- `/pre-deploy-checklist` overlaps with website QA checklists, Developer Tool approvals, Polymarket live checklist, and MT5 promotion gates, but there is no single strategy-go-live guardrail.
  Proposed change: scope it specifically to trading strategy deployment, not generic code deploy. It should read MT5 strategy qualification, paper/watchlist evidence, data-quality status, broker/recon status when available, and return BLOCK/PASS-FOR-HUMAN-APPROVAL. It must never approve.
  Candidate files: add `docs/skills/pre-deploy-checklist.md`, add `scripts/skill_pre_deploy_checklist.py`.
  Target autonomy: Guardrail.

## Missing

Build priority given current state:

1. `/backtest-review` - P0. Most of the raw material exists in MT5; parent-level skill packaging and metrics are missing.
2. `/data-quality-daily` - P0. Current monitoring is health/freshness, not pre-market data integrity. This is the largest P0 trading reliability gap.
3. `/support-triage` - P0. No support inbox, ticket model, triage classifier, draft reply workflow, CSAT, or response-time tracking exists.
4. `/risk-aggregate-daily` skill wrapper - P0. Runtime exists; explicit skill contract, autonomy tag, and success metrics do not.
5. `/broker-reconcile` - P1. No internal blotter/broker/clearing three-way reconciliation model exists. Current trading logs are not a reconciliation ledger.
6. `/pre-deploy-checklist` - P1. Strategy promotion gates exist inside MT5, but no parent-level guardrail command exists.
7. `/analytics-weekly` - P1. Raw FTH metric and GSC/research pieces exist; the weekly anomaly digest does not.
8. `/content-brief-to-draft` skill wrapper - P1. Runtime exists; explicit skill contract and KPI tracking need tightening.
9. `/portfolio-retro-weekly` enhancement - P1. Scheduler exists; richer inputs and decision logging need adding.

## Redundant Or Out Of Scope

- `openclaw/`, `docker-compose.yml`, OpenClaw sections in `README_PHASE1.md`, `README_PHASE2.md`, `PHASE-1-GUIDE.md`, and `heartbeat.yaml`.
  Recommendation: archive or mark hard-deprecated in one place. Current rules prohibit OpenClaw, and these files can mislead the retrofit.

- `tools/system_status.py`.
  Recommendation: replace or archive after adding a Telegram/Ollama-only status check. It actively checks Docker/OpenClaw and conflicts with R11.

- `.claude/worktrees/*` and nested `.claude/worktrees` under projects.
  Recommendation: keep out of synthesis and consider cleanup/archive after confirming no active work is needed. They are cloned workspaces, not operating company source.

- `projects/ccba-prep-tool/`.
  Recommendation: out of scope for this 9-skill plan unless it becomes a managed website property in `config/projects.yaml`. It is a separate Next.js product with its own `.env.local`, Supabase, and worktrees; do not fold it into the trading/websites retrofit yet.

- Root-level product folders: `finance_web_page/`, `free-utility-tools/`, `free-traderhub-research-team/`, `mt5-agentic-desk/`, `polymarket-bot/`.
  Recommendation: not delete, but structurally they belong under `projects/` long term. Several docs already recommend this. Move only as an explicit migration because some are gitlinks/nested repos and config paths depend on current locations.

- Legacy root docs with stale paths or old snapshots, especially `RESUME.md` drift notes and old OpenClaw runbooks.
  Recommendation: keep for history, but create a `docs/archive/` bucket later so current operating instructions remain unambiguous.

## Naming And Structure Conflicts

- Telegram bot commands cannot safely use hyphens. The plan's names are good markdown skill filenames, but runtime commands should use underscores:
  - `/backtest_review`
  - `/data_quality_daily`
  - `/broker_reconcile`
  - `/pre_deploy_checklist`
  - `/support_triage`
  - `/content_brief_to_draft` or existing `/content`
  - `/analytics_weekly`
  - `/risk_aggregate_daily` or existing `/brief`
  - `/portfolio_retro_weekly`

- Existing command style is terse: `/brief`, `/board`, `/content`, `/work`, `/loop`. Better pattern: keep terse production aliases and add explicit skill aliases for clarity.

- There is no project `skills/` folder, no local `SKILL.md` project skills, and `.gstack/` only contains `no-test-bootstrap`. The existing "skill" equivalents are `crews/*.yaml`, `docs/*.md`, `scripts/tool_router.py` subcommands, Telegram handlers, and state/report files.

- `CLAUDE.md` mentions external slash skills like `/office-hours`, `/autoplan`, `/investigate`, `/review`, `/ship`, but those are not present in the project tree. Treat them as editor/tooling guidance, not as implemented project skills.

- Current docs explicitly warn not to create separate `agents/prompts/configs/skills` folders unless needed. For this retrofit, the least-disruptive structure is:
  - `docs/skills/<hyphenated-skill-name>.md` for skill contracts.
  - `scripts/skill_<underscore_name>.py` only when a real runtime is needed.
  - `scripts/tool_router.py <underscore_name>` as the CLI surface.
  - Telegram `/underscore_name` aliases only after CLI behavior is proven.

## Structural Assumptions That Do Not Match

- The plan assumes a flat slash-command skills layer. The repo currently has a Telegram-first operating layer plus CLI/router commands, not a flat skill system.

- The plan assumes all skills need new builds. Several are already partially implemented as operating routines: Content Studio, Phase 3 daily risk aggregation, weekly retro, memory, approval state, and MT5 evidence gates.

- The plan assumes trading strategy generation is hybrid. The MT5 desk already follows that principle: humans can suggest hypotheses, Research Mode backtests/promotes, Trading Mode only considers validated active library strategies.

- The plan assumes a general websites vertical. Current live operating focus is FreeTraderHub; FreeGhostTools is present but parked/maintenance, and CCBA is not wired into the holding-company config.

- The plan assumes memory/g-brain is missing. Local vector memory is present, but it is underused and not automatically attached to every skill output.

- The rollout says support triage goes live in weeks 3-4, but no support channel exists. That is only realistic if the first two weeks also define the ticket source and support state shape.

- The plan says broker reconciliation is P1. In this repo, it is lower practical leverage than data quality and pre-deploy guardrails until there is a canonical internal blotter and broker/clearing export.

## Recommended First-Week Action List

1. Create `docs/skills/README.md` documenting the project skill contract: owner, vertical, autonomy tag, inputs, outputs, success metrics, state/report paths, Telegram alias, and "never" rules.

2. Create `docs/skills/risk-aggregate-daily.md` mapping the skill to `python scripts/tool_router.py run_holding --mode heartbeat --force`, `reports/phase3_holding_latest.*`, and board approval escalation.

3. Create `docs/skills/backtest-review.md` defining the adversarial backtest review checklist, required MT5 artifacts, pass/block outputs, and metrics: pass unchanged rate, false-positive tracking, and reviewer time saved.

4. Create `docs/skills/data-quality-daily.md` defining the pre-market integrity checklist for current assets: MT5 bar freshness/gaps, strategy library freshness, Polymarket remote sync, report age, and explicit N/A placeholders for corp actions/vendor cross-checks.

5. Create `docs/skills/content-brief-to-draft.md` mapping the skill to existing `/content` and `scripts/content_studio.py`, with publication remaining CEO-gated.

6. Create `docs/skills/support-triage.md` as a shadow-mode spec only. Include the missing prerequisite: decide the ticket source before runtime build.

7. Create `docs/skills/analytics-weekly.md` mapping the first version to FreeTraderHub metrics, GSC/research reports, content output, email list, affiliate progress, and anomaly surfacing.

8. Create `docs/skills/portfolio-retro-weekly.md` mapping current `scripts/weekly_retro.py` behavior and listing required added sources: skill outputs, board decisions, content decisions, loops, commits, deploys, and incidents.

9. Create `docs/skills/pre-deploy-checklist.md` and `docs/skills/broker-reconcile.md` as P1 contracts only. Do not build runtime until P0 shadow reports are stable.

10. Edit `README_TELEGRAM_BRIDGE.md` to add a "Planned skill aliases" section with underscore-safe Telegram command names, clearly marked not implemented until wired.

11. Edit `docs/STRUCTURE_MAP.md` to add `docs/skills/` as the contract layer while keeping `crews/`, `scripts/`, `reports/`, `state/`, and `memory/` as runtime locations.

12. Edit `PLAN.md` forward-focus section to align the 90-day rollout with existing Phase 2/3/Content/Retro systems, and to state that P0 shadow mode writes reports only.

13. After docs are reviewed, implement only two P0 runtime aliases first: `risk_aggregate_daily` as a wrapper/alias to existing Phase 3, and `backtest_review` as a report wrapper over MT5 artifacts.

14. Run documentation review against AGENTS Code Review Gate: markdown clarity, no stale OpenClaw routing, no secret paths beyond existing documented local paths, and no new network or cloud assumptions.

## Bottom Line

The 9-skill plan fits the direction of the project, but it should be implemented as a thin skill-contract layer over the existing Telegram/CLI/report/state operating system. The cleanest first move is not a new framework; it is to standardize the nine skills as markdown contracts, tag autonomy explicitly, and wire only the P0 runtime gaps that already have data behind them.

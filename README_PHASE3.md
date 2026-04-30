# AI Holding Company - Phase 3 Runbook

Phase 3 adds a top-level CEO layer over division crews with company-wide scorecards and board review mode.

Live governance follows real Phase 2 output only. If a division does not appear in `reports/phase2_divisions_latest.json`, Phase 3 does not synthesize a live division lane for it. Commercial thinking can still appear inside property department notes, but there is no standalone commercial division unless Phase 2 emits one.

## Canonical Source Map

- Telemetry truth: `reports/daily_brief_latest.json`
- Division truth: `reports/phase2_divisions_latest.json`
- CEO truth: `reports/phase3_holding_latest.json`
- Approval/work truth: `state/board_approval_decisions.json`
- Metric truth: `state/property_metric_feed.json`

Phase 3 should read the latest JSON truth files above and treat timestamped report siblings as derived artifacts only.

## 1) New Phase 3 files

- [SOUL.md](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/SOUL.md)
- [config/targets.yaml](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/config/targets.yaml)
- [crews/holding_ceo.yaml](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/crews/holding_ceo.yaml)
- [scripts/phase3_holding.py](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/scripts/phase3_holding.py)

## 2) Confirm config links

Check [config/projects.yaml](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/config/projects.yaml):

- `phase3.enabled: true`
- `phase3.soul_file: SOUL.md`
- `phase3.targets_file: config/targets.yaml`
- `phase3.ceo.spec_file: crews/holding_ceo.yaml`
- `bridge.degraded_ops_mode: false` for normal operations

## 3) Run heartbeat mode

```powershell
cd "C:\Users\james\OneDrive\Documents\Manganda LTD\AI Models\ai-holding-company"
python scripts/tool_router.py run_holding --mode heartbeat --force
```

Outputs:
- `reports/phase3_holding_latest.md`
- `reports/phase3_holding_latest.json`

If `bridge.degraded_ops_mode: true`, Phase 3 still runs normally but adds a `DEGRADED OPS MODE`
banner to JSON/markdown output, blocks new capital-risk execute actions in the bridge, and
surfaces only RED board approvals while pausing content and lower-priority prompts.

Phase 3 now renders two distinct score views in the same report:

- `portfolio_health_score`: all active operated assets, including capital-at-risk bots
- `property_maturity_score`: promoted or fully instrumented properties only

Use the split to separate today's operating risk from longer-horizon property maturity.

## 4) Run board review mode

```powershell
python scripts/tool_router.py run_holding --mode board_review --force
```

Board review mode adds explicit approval items for Owner/CEO decisions.
Those approval items are generated from the company scorecard and the live Phase 2 divisions only.

## 5) Telegram test

```powershell
python scripts/aiogram_bridge.py --simulate-text "/brief"
python scripts/aiogram_bridge.py --simulate-text "/board review"
```

Live chat:
1. Send `/brief` in Telegram.
2. Run `python scripts/aiogram_bridge.py`.
3. Send `/board review` in the same chat while the bridge is running.

# AI Holding Company - Phase 3 Runbook

Phase 3 adds a top-level CEO layer over division crews with company-wide scorecards and board review mode.

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

## 3) Run heartbeat mode

```powershell
cd "C:\Users\james\OneDrive\Documents\Manganda LTD\AI Models\ai-holding-company"
python scripts/tool_router.py run_holding --mode heartbeat --force
```

Outputs:
- `reports/phase3_holding_latest.md`
- `reports/phase3_holding_latest.json`

## 4) Run board review mode

```powershell
python scripts/tool_router.py run_holding --mode board_review --force
```

Board review mode adds explicit approval items for Owner/CEO decisions.

## 5) Telegram test

```powershell
python scripts/telegram_bridge.py --simulate-text "/brief"
python scripts/telegram_bridge.py --simulate-text "/board review"
```

Live chat:
1. Send `/brief` in Telegram.
2. Run `python scripts/telegram_bridge.py --once`.
3. Send `/board review` and run `--once` again.


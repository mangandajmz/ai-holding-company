# Telegram Bridge Runbook (Local-Only, Minimal, Secure)

This bridge replaces OpenClaw with a thin local polling service.
It only runs allowlisted commands against your existing `scripts/tool_router.py`.

## 1) Configure bot token + owner IDs

Set environment variables in PowerShell:

```powershell
setx TELEGRAM_BOT_TOKEN "REPLACE_WITH_BOT_TOKEN"
setx TELEGRAM_OWNER_CHAT_ID "REPLACE_WITH_NUMERIC_CHAT_ID"
setx TELEGRAM_OWNER_USER_ID "REPLACE_WITH_NUMERIC_USER_ID"
```

Close and reopen terminal after `setx`.

If you do not know the numeric IDs yet:

1. Send `/start` to your bot in Telegram.
2. Run:

```powershell
python scripts/telegram_bridge.py --discover-ids
```

Then use returned `chat_id` and `user_id` in the `setx` commands above.

## 2) Confirm bridge is in Observer Mode

Check in [config/projects.yaml](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/config/projects.yaml):

- `bridge.observer_mode: true`

Observer mode blocks `/bot <id> execute ...`.

## 3) Local dry-run tests (no Telegram call)

```powershell
cd "C:\Users\james\OneDrive\Documents\Manganda LTD\AI Models\ai-holding-company"
python scripts/telegram_bridge.py --simulate-text "/help"
python scripts/telegram_bridge.py --simulate-text "/status"
python scripts/telegram_bridge.py --simulate-text "/bot mt5_desk report"
```

## 4) Telegram one-shot poll test

Send `/help` to your bot in Telegram, then run:

```powershell
python scripts/telegram_bridge.py --once
```

If configured correctly, you should receive a reply in Telegram.

## 5) Continuous bridge

```powershell
python scripts/telegram_bridge.py
```

## 6) Morning brief push test (manual trigger)

```powershell
python scripts/telegram_bridge.py --send-morning-brief
```

## 7) Allowed commands in chat

- `/status`
- `/brief` (Phase 3: runs CEO heartbeat; fallback Phase 2: division brief)
- `/board review` (Phase 3 board review pack with approval items)
- `/site <website_id>`
- `/bot <bot_id> health`
- `/bot <bot_id> report`
- `/bot <bot_id> logs [lines]`
- `/divisions [all|trading|websites]`
- `/note <text>`
- `/memory <query>`
- `/help`

## 8) Audit + state files

- `state/telegram_bridge_state.json`
- `state/bridge_audit.jsonl`

These stay local on your machine.

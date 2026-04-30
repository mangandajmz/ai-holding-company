# Telegram Bridge Runbook (Aiogram Production Bridge)

Use `scripts/aiogram_bridge.py` as the sole production Telegram bridge.
`scripts/telegram_bridge.py` is deprecated and exits immediately.

## 1) Configure bot token + owner IDs

Set environment variables in PowerShell:

```powershell
setx TELEGRAM_BOT_TOKEN "REPLACE_WITH_BOT_TOKEN"
setx TELEGRAM_OWNER_CHAT_ID "REPLACE_WITH_NUMERIC_CHAT_ID"
setx TELEGRAM_OWNER_USER_ID "REPLACE_WITH_NUMERIC_USER_ID"
setx TELEGRAM_BACKUP_CHAT_ID "OPTIONAL_NUMERIC_CHAT_ID"
setx TELEGRAM_BACKUP_USER_ID "OPTIONAL_NUMERIC_USER_ID"
```

Close and reopen terminal after `setx`.

Restart your terminal after `setx` so the bridge inherits the new values.

## 2) Confirm bridge is in Observer Mode

Check in [config/projects.yaml](C:/Users/james/OneDrive/Documents/Manganda%20LTD/AI%20Models/ai-holding-company/config/projects.yaml):

- `bridge.observer_mode: true`
- `bridge.backup_approver_policy.allowed_actions: ["view_status", "view_approvals"]` by default

Observer mode blocks `/bot <id> execute ...`.

Backup approver mode is opt-in. When `TELEGRAM_BACKUP_CHAT_ID` and/or `TELEGRAM_BACKUP_USER_ID`
are set, the backup identity can only run the action types listed in
`bridge.backup_approver_policy.allowed_actions`. The default policy is read-only:
`/status`, `/brief`, `/board review`, `/content_status`, and `/approvals`.

## 3) Local dry-run tests (no Telegram polling)

```powershell
cd "C:\Users\james\OneDrive\Documents\Manganda LTD\AI Models\ai-holding-company"
python scripts/aiogram_bridge.py --simulate-text "/help"
python scripts/aiogram_bridge.py --simulate-text "/status"
python scripts/aiogram_bridge.py --simulate-text "/bot mt5_desk report"
```

## 4) Continuous bridge

Start the production bridge:

```powershell
python scripts/aiogram_bridge.py
```

The Windows startup scripts and scheduled tasks in this repository already use
`aiogram_bridge.py` only.

## 5) Morning brief push test (manual trigger)

```powershell
python scripts/aiogram_bridge.py --send-morning-brief
```

## 6) Local board and approval checks

```powershell
python scripts/aiogram_bridge.py --simulate-text "/approvals"
python scripts/aiogram_bridge.py --simulate-text "/board review"
python scripts/aiogram_bridge.py --simulate-text "/content_status"
```

## 7) Allowed commands in chat

- `/status`
- `/brief` (Phase 3: runs CEO heartbeat; fallback Phase 2: division brief)
- `/board review` (Phase 3 board review pack with approval items)
- `/approvals`
- `/approve <board_approval_id>`
- `/deny <board_approval_id>`
- `/assign <board_approval_id>`
- `/start <board_approval_id>`
- `/done <board_approval_id> <completion_note>`
- `/site <website_id>`
- `/bot <bot_id> health`
- `/bot <bot_id> report`
- `/bot <bot_id> logs [lines]`
- `/bot <bot_id> execute`
- `/bot <bot_id> execute confirm`
- `/divisions [all|trading|websites]`
- `/content <brief text>`
- `/content_status`
- `/content_approve <draft_id>`
- `/content_deny <draft_id> [note]`
- `/develop <task_description>`
- `/develop_approve <approval_id>`
- `/develop_deny <approval_id>`
- `/develop_status`
- `/note <text>`
- `/memory <query>`
- `/help`

If backup approver IDs are configured, only the policy-allowed subset is available to that backup user.
Owner behavior is unchanged.

## 8) Audit + state files

- `logs/aiogram_bridge.log`
- `state/conversation_history.jsonl`
- `state/board_approval_decisions.json`

These stay local on your machine.

## 9) Content approval loop

Create a draft:

```powershell
python scripts/aiogram_bridge.py --simulate-text "/content Write an article about MT5 signal accuracy. Target audience: traders."
```

Review current draft buckets:

```powershell
python scripts/aiogram_bridge.py --simulate-text "/content_status"
```

Approve or deny a draft by ID:

```powershell
python scripts/aiogram_bridge.py --simulate-text "/content_approve <draft_id>"
python scripts/aiogram_bridge.py --simulate-text "/content_deny <draft_id> Needs tighter sourcing"
```

## 10) Board execution queue

Approve work through the board as usual, then progress the execution state explicitly:

```powershell
python scripts/aiogram_bridge.py --simulate-text "/approvals"
python scripts/aiogram_bridge.py --simulate-text "/assign <board_approval_id>"
python scripts/aiogram_bridge.py --simulate-text "/start <board_approval_id>"
python scripts/aiogram_bridge.py --simulate-text "/done <board_approval_id> Completed remediation and validation notes"
```

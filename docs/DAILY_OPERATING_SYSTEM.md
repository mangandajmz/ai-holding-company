# AI Capital Group Daily Operating System

This repo already contains the MVP operating system. Use the current structure
instead of creating a new `company_os/` tree until daily use proves that a move
would reduce friction.

## Current MVP

- Reports: `reports/`
- Approval state: `state/board_approval_decisions.json`
- Company memory: `memory/`
- Agent and division prompts: `crews/`
- Agent staff contracts: `docs/agents/`
- Skill contracts: `docs/skills/`
- Communication rules: `docs/communication/`
- Runtime config and KPI targets: `config/`
- Telegram bridge: `scripts/aiogram_bridge.py`
- Command router: `scripts/tool_router.py`
- CEO layer and board pack: `scripts/phase3_holding.py`

## Daily CEO Flow

1. Generate or receive the morning brief.

   ```powershell
   python scripts/aiogram_bridge.py --send-morning-brief
   ```

2. Refresh the local reports when you want a live view.

   ```powershell
   python scripts/tool_router.py daily_brief --force
   python scripts/tool_router.py run_divisions --division all --force
   python scripts/tool_router.py run_holding --mode board_pack --force
   ```

   For the weekly FreeTraderHub business refresh, update the manual dashboard
   numbers first, then run the monitor and holding heartbeat:

   ```powershell
   $env:FTH_EMAIL_LIST_SIZE="0"
   $env:FTH_AFFILIATE_CLICKS_7D="0"
   $env:FTH_FTMO_AFFILIATE_CLICKS_7D="0"
   $env:FTH_FUNDEDNEXT_AFFILIATE_CLICKS_7D="0"
   $env:FTH_AFFILIATE_USD_7D="0"
   $env:FTH_AFFILIATE_MRR_USD="0"
   $env:FTH_TOP_PARTNER=""
   python scripts/fth_monitor.py --dry-run
   python scripts/fth_monitor.py
   python scripts/tool_router.py run_holding --mode heartbeat --force
   ```

   Use real dashboard values from Umami, the email provider, FTMO, and
   FundedNext. Keep unknown values unset instead of guessing; the CEO report is
   more useful when unknowns remain visible.

3. Create or review company loops. This is the closed-loop operating backbone.

   ```powershell
   python scripts/tool_router.py loop status
   python scripts/tool_router.py loop new --goal "Improve FreeTraderHub calculator clarity" --type website_improvement --division websites
   ```

   Use loops for real work so each effort has a goal, evidence, review,
   approval, action, measurement, and result.

4. Read the latest artifacts.

   - `reports/daily_brief_latest.md`
   - `reports/phase2_divisions_latest.md`
   - `reports/phase3_holding_latest.md`
   - `reports/company_loops/company_loops_latest.md`

5. Review pending approvals.

   ```powershell
   python scripts/aiogram_bridge.py --simulate-text "/approvals"
   ```

6. Open a boardroom conversation when you want MD/division-style discussion.

   ```powershell
   python scripts/tool_router.py boardroom start --topic "Daily CEO review"
   python scripts/tool_router.py boardroom ask --division trading --question "What needs CEO attention?"
   python scripts/tool_router.py boardroom close --note "CEO decision or follow-up here."
   ```

   Telegram commands:

   - `/boardroom start [topic]`
   - `/boardroom ask <division> <question>`
   - `/boardroom status`
   - `/boardroom close [note]`

   Transcripts are written to `reports/boardroom/`.

7. Approve, deny, assign, start, or close work through Telegram.

   - `/approve <board_approval_id>`
   - `/deny <board_approval_id>`
   - `/assign <board_approval_id>`
   - `/start <board_approval_id>`
   - `/done <board_approval_id> <completion_note>`

8. Log important CEO direction into local memory.

   ```powershell
   python scripts/tool_router.py log_direction --text "Your CEO direction here."
   ```

9. Ask the company naturally once the Chief of Staff spine is wired.

   ```powershell
   python scripts/tool_router.py ask_company --question "What needs me today?"
   ```

   The expected behavior is conversational output grounded in `reports/`,
   `state/`, `memory/`, and `docs/decisions/`, with source paths available for
   consequential claims.

## Approval Rule

Anything involving trading action, money, publishing, deployment, external
communication, credentials, business commitments, or legal/tax-sensitive work
must remain `PENDING_CEO_APPROVAL` until the CEO explicitly approves it.

## MVP Boundary

For the next phase, prefer improving clarity over adding machinery:

- Do not add OpenClaw.
- Do not add new agents unless one existing role cannot reasonably cover the work.
- Do not make visible communication rigid by default; store structure
  underneath and keep owner interaction natural.
- Do not add trading execution.
- Do not add automatic publishing.
- Do not add credentials or secrets.
- Keep reports, approvals, and evidence readable in markdown or JSON.

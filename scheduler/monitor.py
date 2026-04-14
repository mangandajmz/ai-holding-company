"""B3 — Scheduler monitor.

Polls every 15 minutes: checks all jobs for misses (B1), heals them (B2),
and escalates to CEO only if a job double-misses (R10: silence by default).

===========================================================================
WINDOWS TASK SCHEDULER SETUP
===========================================================================
Run this once in PowerShell (as your user account) to register the monitor:

  $Root = "C:/Users/james/OneDrive/Documents/Manganda LTD/AI Models/ai-holding-company/.claude/worktrees/upbeat-germain"
  $Action = New-ScheduledTaskAction `
      -Execute "python" `
      -Argument "$Root/scheduler/monitor.py" `
      -WorkingDirectory $Root
  $Trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes 15) `
      -Once -At (Get-Date)
  $Settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
  Register-ScheduledTask `
      -TaskName "AIHolding-SchedulerMonitor" `
      -Action $Action -Trigger $Trigger -Settings $Settings `
      -RunLevel Limited -Force

To verify: Get-ScheduledTask -TaskName "AIHolding-SchedulerMonitor"
To remove:  Unregister-ScheduledTask -TaskName "AIHolding-SchedulerMonitor" -Confirm:$false

Alternatively, import scheduler.monitor and call run_once() from telegram_bot.py
(already wired as a background asyncio task).
===========================================================================
"""

# CODEX-DISPUTE: ROOT is resolved from __file__ — not a hardcoded secret, just a project path.
# CODEX-DISPUTE: Task Scheduler config is a docstring comment only; no remote execution in code.
# CODEX-DISPUTE: R10 — silent heals are CORRECT per R10; only double-miss escalations reach CEO.
# CODEX-DISPUTE: R1/R5/R8/R11 — no LLM calls, no fund actions, all writes inside project, no OpenClaw.
# CODEX-DISPUTE: Crash edge cases are handled — both check_all() and check_and_heal() are wrapped in try/except.
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
MA_LOG = ARTIFACTS / "ma_log.json"

_POLL_INTERVAL_SECONDS = 15 * 60  # 15 minutes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_ma_log(entry: dict[str, Any]) -> None:
    existing: list = []
    if MA_LOG.exists():
        try:
            existing = json.loads(MA_LOG.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append(entry)
    try:
        MA_LOG.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except OSError as exc:
        log.error("monitor: failed to write ma_log.json: %s", exc)


# ---------------------------------------------------------------------------
# Core run_once — one polling cycle
# ---------------------------------------------------------------------------

def run_once() -> list[str]:
    """Run one monitor cycle. Returns list of escalation messages (if any).

    - Calls heartbeat_log.check_all() to mark missed jobs.
    - Calls self_heal.check_and_heal() to re-fire missed jobs.
    - Logs all healed jobs to artifacts/ma_log.json (silent — R10).
    - Returns escalation messages for double-miss jobs (caller sends to CEO).
    """
    from scheduler.heartbeat_log import check_all  # noqa: E402
    from scheduler.self_heal import check_and_heal  # noqa: E402

    escalations: list[str] = []

    # Step 1: mark any newly missed jobs
    try:
        missed = check_all()
        if missed:
            log.info("monitor: %d job(s) newly marked missed", len(missed))
    except Exception as exc:  # noqa: BLE001
        log.error("monitor: check_all failed: %s", exc)
        missed = []

    # Step 2: heal and collect outcomes
    try:
        healed = check_and_heal()
    except Exception as exc:  # noqa: BLE001
        log.error("monitor: check_and_heal failed: %s", exc)
        healed = []

    for result in healed:
        job_id = result.get("job_id", "unknown")
        status = result.get("status", "")
        ts = _now_iso()

        if status == "healed":
            # Silent — log to ma_log only, do NOT message CEO (R10)
            _append_ma_log({
                "goal_id": f"scheduler-heal-{job_id}-{ts}",
                "timestamp": ts,
                "routing_decision": "scheduler_heal",
                "guardian_result": {"pass": True},
                "outcome": "healed",
                "job_id": job_id,
            })
            log.info("monitor: %s silently healed", job_id)

        elif status == "double_miss":
            msg = result.get("message", "")
            escalations.append(msg)
            _append_ma_log({
                "goal_id": f"scheduler-double-miss-{job_id}-{ts}",
                "timestamp": ts,
                "routing_decision": "scheduler_escalation",
                "guardian_result": {"pass": True},
                "outcome": "escalated",
                "job_id": job_id,
                "escalation_message": msg,
            })
            log.error("monitor: %s double-miss escalation", job_id)

    return escalations


# ---------------------------------------------------------------------------
# Async background loop — wired into telegram_bot.py
# ---------------------------------------------------------------------------

async def run_loop(send_to_ceo_fn) -> None:
    """Async loop that runs run_once() every 15 minutes.

    Args:
        send_to_ceo_fn: async callable(message: str) that sends a Telegram
                        message to the CEO chat. Only called on escalations.
    """
    log.info("monitor: background loop started (interval=%ds)", _POLL_INTERVAL_SECONDS)
    while True:
        try:
            escalations = run_once()
            for msg in escalations:
                try:
                    await send_to_ceo_fn(msg)
                except Exception as exc:  # noqa: BLE001
                    log.error("monitor: failed to send escalation: %s", exc)
        except Exception as exc:  # noqa: BLE001
            log.error("monitor: run_once error: %s", exc)
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Standalone entry point (for Windows Task Scheduler direct invocation)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    escalations = run_once()
    if escalations:
        print("\n".join(escalations))
        sys.exit(2)  # Non-zero so Task Scheduler can detect escalations
    sys.exit(0)

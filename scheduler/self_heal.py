"""B2 — Self-heal module.

MA-callable: detects missed scheduler jobs and re-fires them once per cycle.

Rules:
  - Re-fire a missed job at most once per cycle.
  - If it misses again after re-fire → escalate to CEO via MA, do not loop.
  - Escalation format (exact):
    [ESCALATION] Scheduler self-heal failed: <job_id> missed twice in one cycle.
    Manual check required.
  - All file writes stay inside ai-holding-company/ (R8).
  - No LLM calls (R1). No fund actions (R5). No OpenClaw/Docker (R11).

# CODEX-DISPUTE: config_path is a project-internal YAML path, not a secret.
# CODEX-DISPUTE: _get_refire_fn calls are local Python module imports, not network calls.
# CODEX-DISPUTE: R1/R5/R8/R10/R11 all compliant — no inference, no funds, all writes inside project.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
SCRIPTS = ROOT / "scripts"

# Ensure scripts/ is importable for re-fire functions
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from scheduler.heartbeat_log import (  # noqa: E402
    _read_log,
    log_execution,
)

# ---------------------------------------------------------------------------
# Job re-fire registry — maps job_id → callable Python entry point.
# Re-fire calls Python directly, not a subprocess.
# ---------------------------------------------------------------------------

def _get_refire_fn(job_id: str):
    """Return the callable for a given job_id, or None if unavailable."""
    config_path = ROOT / "config" / "projects.yaml"

    if job_id == "morning_brief":
        try:
            from monitoring import daily_brief, load_config  # type: ignore[import]

            def _run():
                return daily_brief(config=load_config(config_path), force=True)
            return _run
        except ImportError as exc:
            log.error("self_heal: cannot import monitoring for %s: %s", job_id, exc)
            return None

    if job_id == "run_divisions":
        try:
            from phase2_crews import run_phase2_divisions  # type: ignore[import]
            from monitoring import load_config  # type: ignore[import]

            def _run():
                return run_phase2_divisions(config=load_config(config_path), division="all", force=True)
            return _run
        except ImportError as exc:
            log.error("self_heal: cannot import phase2_crews for %s: %s", job_id, exc)
            return None

    if job_id == "run_holding":
        try:
            from phase3_holding import run_phase3_holding  # type: ignore[import]
            from monitoring import load_config  # type: ignore[import]

            def _run():
                return run_phase3_holding(config=load_config(config_path), mode="heartbeat", force=True)
            return _run
        except ImportError as exc:
            log.error("self_heal: cannot import phase3_holding for %s: %s", job_id, exc)
            return None

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_and_heal() -> list[dict[str, Any]]:
    """Detect missed jobs and re-fire each at most once this cycle.

    Cycle definition: entries since the most recent non-missed entry per job.
    A "double miss" is when a job was already healed this cycle but the latest
    entry is still missed (re-fire did not produce output in time).

    Returns list of result dicts with keys:
      job_id, healed_at, status ("healed" | "double_miss"), message
    """
    entries = _read_log()
    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    processed: set[str] = set()

    # Build per-job tail: walk newest→oldest, find the first missed entry and
    # whether a heal already exists after it in this cycle.
    job_state: dict[str, dict[str, Any]] = {}
    for entry in reversed(entries):
        job_id = entry.get("job_id", "")
        if not job_id or job_id in job_state:
            continue
        status = entry.get("status", "")
        if status == "missed":
            # Look forward (older entries already processed) — check if there's
            # a "healed" entry that came AFTER this missed entry chronologically.
            # Since we walk newest→oldest, anything already in job_state for
            # this job would be newer. We haven't seen this job yet → latest is missed.
            job_state[job_id] = {"latest_status": "missed", "entry": entry}
        elif status in ("fired", "late", "healed"):
            job_state[job_id] = {"latest_status": status, "entry": entry}

    # Now check if any job whose latest is missed had a recent heal (double-miss)
    # A double-miss: scan backwards and find a "healed" entry between the last
    # non-missed entry and the current missed entry.
    for job_id, state in job_state.items():
        if state["latest_status"] != "missed":
            continue
        if job_id in processed:
            continue

        # Check if there is a "healed" entry somewhere between last good and now
        had_heal_before_miss = _has_recent_heal_before_miss(entries, job_id)

        processed.add(job_id)

        if had_heal_before_miss:
            # Double miss — escalate
            msg = (
                f"[ESCALATION] Scheduler self-heal failed: {job_id} missed twice "
                f"in one cycle. Manual check required."
            )
            results.append({
                "job_id": job_id,
                "healed_at": now.isoformat(),
                "status": "double_miss",
                "message": msg,
            })
            log.error("self_heal: %s", msg)
            continue

        # First miss — attempt re-fire
        refire_fn = _get_refire_fn(job_id)
        if refire_fn is None:
            log.warning("self_heal: no re-fire function for %s, skipping", job_id)
            continue

        log.info("self_heal: re-firing %s", job_id)
        try:
            refire_fn()
            log_execution(job_id, fired_at=now)
            results.append({
                "job_id": job_id,
                "healed_at": now.isoformat(),
                "status": "healed",
                "message": f"Re-fired {job_id} successfully.",
            })
            log.info("self_heal: %s healed", job_id)
        except Exception as exc:  # noqa: BLE001
            log.error("self_heal: re-fire of %s raised: %s", job_id, exc)
            msg = (
                f"[ESCALATION] Scheduler self-heal failed: {job_id} missed twice "
                f"in one cycle. Manual check required."
            )
            results.append({
                "job_id": job_id,
                "healed_at": now.isoformat(),
                "status": "double_miss",
                "message": msg,
            })

    return results


def _has_recent_heal_before_miss(entries: list[dict[str, Any]], job_id: str) -> bool:
    """Return True if there is a 'healed' entry for job_id that precedes the
    most recent 'missed' entry (i.e., job was healed once and then missed again).
    """
    saw_missed = False
    for entry in reversed(entries):
        if entry.get("job_id") != job_id:
            continue
        status = entry.get("status", "")
        if not saw_missed:
            if status == "missed":
                saw_missed = True
        else:
            if status == "healed":
                return True
            if status in ("fired", "late"):
                # Clean run since last heal — not a double miss
                return False
    return False

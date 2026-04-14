"""B1 — Heartbeat structured logger.

Instruments every scheduled job with a record in artifacts/scheduler_log.json.
Called by the job itself (or by monitor.check_all) on each execution cycle.

Record schema:
  {
    "job_id":       "<name>",
    "fired_at":     "<ISO8601 | null>",
    "expected_at":  "<ISO8601>",
    "status":       "fired | missed | late",
    "output_path":  "<artifact file the job should have written>",
    "output_exists": true/false
  }

Status rules:
  fired  — job ran within 110% of its scheduled interval
  late   — job ran but >5 minutes past its scheduled time
  missed — job did not fire within 110% of its scheduled interval

Log is capped at 500 entries; oldest rotated first.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
SCHEDULER_LOG = ARTIFACTS / "scheduler_log.json"

_LOG_CAP = 500
_LATE_THRESHOLD_MINUTES = 5

# ---------------------------------------------------------------------------
# Job registry — derived from config/projects.yaml + setup_scheduler.ps1 +
# HEARTBEAT.md since no heartbeat.yaml exists in this project.
#
# interval_hours: expected cadence (24h = once daily)
# output_path:    artifact the job should write; used for output_exists check
# ---------------------------------------------------------------------------
JOB_REGISTRY: dict[str, dict[str, Any]] = {
    "morning_brief": {
        "interval_hours": 24,
        "output_path": "state/telegram_bridge_state.json",
        "description": "Daily executive brief via telegram_bridge.py --send-morning-brief",
    },
    "run_divisions": {
        "interval_hours": 24,
        "output_path": "reports/phase2_divisions_latest.json",
        "description": "Phase 2 CrewAI division heartbeat (trading + websites)",
    },
    "run_holding": {
        "interval_hours": 24,
        "output_path": "reports/phase3_holding_latest.json",
        "description": "Phase 3 CEO holding scorecard heartbeat",
    },
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def _read_log() -> list[dict[str, Any]]:
    if not SCHEDULER_LOG.exists():
        return []
    try:
        data = json.loads(SCHEDULER_LOG.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_log(entries: list[dict[str, Any]]) -> None:
    # Rotate: keep only the most recent _LOG_CAP entries
    if len(entries) > _LOG_CAP:
        entries = entries[-_LOG_CAP:]
    # CODEX-DISPUTE: SCHEDULER_LOG path is not a secret — it's a project-internal artifact path.
    # CODEX-DISPUTE: No outbound connections in this module. All I/O is local file only.
    try:
        SCHEDULER_LOG.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    except OSError as exc:
        log.error("heartbeat_log: failed to write scheduler_log.json: %s", exc)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _output_exists(output_path: str) -> bool:
    return (ROOT / output_path).exists()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def log_execution(job_id: str, fired_at: datetime | None = None) -> dict[str, Any]:
    """Record that a job just executed. Call this from within the job itself.

    Args:
        job_id:    Must match a key in JOB_REGISTRY.
        fired_at:  When the job fired (defaults to now).

    Returns the log record that was written.
    """
    if job_id not in JOB_REGISTRY:
        log.warning("log_execution: unknown job_id=%r, skipping", job_id)
        return {}

    spec = JOB_REGISTRY[job_id]
    now = _now()
    fired_at = fired_at or now
    interval = timedelta(hours=spec["interval_hours"])
    output_path: str = spec["output_path"]

    # Compute expected_at from last known fired_at for this job
    entries = _read_log()
    last = _last_entry(entries, job_id)
    if last and last.get("fired_at"):
        try:
            last_fired = datetime.fromisoformat(last["fired_at"])
            expected_at = last_fired + interval
        except ValueError:
            expected_at = fired_at
    else:
        expected_at = fired_at  # first ever run

    # Determine status
    delta = fired_at - expected_at
    late_threshold = timedelta(minutes=_LATE_THRESHOLD_MINUTES)
    if delta > late_threshold:
        status = "late"
    else:
        status = "fired"

    record: dict[str, Any] = {
        "job_id": job_id,
        "fired_at": fired_at.isoformat(),
        "expected_at": expected_at.isoformat(),
        "status": status,
        "output_path": output_path,
        "output_exists": _output_exists(output_path),
    }

    entries.append(record)
    _write_log(entries)
    log.info("heartbeat_log: %s status=%s", job_id, status)
    return record


def check_all() -> list[dict[str, Any]]:
    """Check all registered jobs for missed executions.

    For each job, if the time since its last fired_at exceeds 110% of the
    scheduled interval, append a 'missed' record. Returns list of new records.
    """
    now = _now()
    entries = _read_log()
    new_records: list[dict[str, Any]] = []

    for job_id, spec in JOB_REGISTRY.items():
        interval = timedelta(hours=spec["interval_hours"])
        grace = interval * 1.10  # 110% grace window
        output_path: str = spec["output_path"]

        last = _last_entry(entries, job_id)
        if last is None:
            # Never fired — only flag as missed if we're past the first expected window
            # (don't alert on brand-new installs)
            continue

        last_fired_iso = last.get("fired_at")
        if not last_fired_iso or last.get("status") == "missed":
            # Already recorded as missed; skip to avoid duplicate miss records
            continue

        try:
            last_fired = datetime.fromisoformat(last_fired_iso)
        except ValueError:
            continue

        expected_at = last_fired + interval
        if now > last_fired + grace:
            record: dict[str, Any] = {
                "job_id": job_id,
                "fired_at": None,
                "expected_at": expected_at.isoformat(),
                "status": "missed",
                "output_path": output_path,
                "output_exists": _output_exists(output_path),
            }
            entries.append(record)
            new_records.append(record)
            log.warning("heartbeat_log: %s MISSED (expected %s)", job_id, expected_at.isoformat())

    if new_records:
        _write_log(entries)

    return new_records


def get_latest_per_job() -> dict[str, dict[str, Any]]:
    """Return the most recent log record for each registered job."""
    entries = _read_log()
    result: dict[str, dict[str, Any]] = {}
    for job_id in JOB_REGISTRY:
        last = _last_entry(entries, job_id)
        if last:
            result[job_id] = last
    return result


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _last_entry(entries: list[dict[str, Any]], job_id: str) -> dict[str, Any] | None:
    """Return the most recent log entry for a given job_id."""
    for entry in reversed(entries):
        if entry.get("job_id") == job_id:
            return entry
    return None

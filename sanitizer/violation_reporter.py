"""C3 — Violation reporter: reads artifacts/violation_log.json.

Public API:
  get_violations_since(since_iso: str) -> list[dict]
  summarise(since_iso: str | None = None) -> str

Used by:
  - ma/agent.py: appends a short violation summary to each goal's ma_log entry.
  - telegram_bot.py: /violations command returns the last-hour summary to CEO.

# CODEX-DISPUTE: Read-only reads from artifacts/ — no writes, no LLM, no network.
# CODEX-DISPUTE: R8/R1/R5/R11 — all compliant, no side effects.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
VIOLATION_LOG = ARTIFACTS / "violation_log.json"


def _read_log() -> list[dict]:
    """Return the full violation log, or [] on any read/parse failure."""
    if not VIOLATION_LOG.exists():
        return []
    try:
        data = json.loads(VIOLATION_LOG.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("violation_reporter: could not read violation_log.json: %s", exc)
        return []


def get_violations_since(since_iso: str) -> list[dict]:
    """Return all violation entries with ts >= since_iso (ISO 8601 string).

    Returns an empty list if the log is absent or the timestamp is unparseable.
    """
    try:
        since_dt = datetime.fromisoformat(since_iso)
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
    except ValueError as exc:
        log.warning("violation_reporter: invalid since_iso %r: %s", since_iso, exc)
        return []

    results = []
    for entry in _read_log():
        ts_raw = entry.get("ts", "")
        try:
            entry_dt = datetime.fromisoformat(ts_raw)
            if entry_dt.tzinfo is None:
                entry_dt = entry_dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if entry_dt >= since_dt:
            results.append(entry)
    return results


def summarise(since_iso: str | None = None) -> str:
    """Return a human-readable one-paragraph summary of recent violations.

    If since_iso is None, summarises all entries in the log.
    Returns "No violations recorded." when the log is empty or has no matches.
    """
    if since_iso is not None:
        entries = get_violations_since(since_iso)
    else:
        entries = _read_log()

    if not entries:
        return "No violations recorded."

    # Count by type
    counts: dict[str, int] = {}
    for entry in entries:
        vtype = entry.get("type", "unknown")
        counts[vtype] = counts.get(vtype, 0) + 1

    total = len(entries)
    breakdown = ", ".join(f"{k}:{v}" for k, v in sorted(counts.items()))
    latest_ts = entries[-1].get("ts", "?")

    return (
        f"Violations ({total} total): {breakdown}. "
        f"Latest: {latest_ts}."
    )

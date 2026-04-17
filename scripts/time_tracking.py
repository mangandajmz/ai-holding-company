"""Time-saved tracking for CEO productivity proof and R9 guardrail checks."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_CHECKIN_FILE = ROOT / "artifacts" / "time_checkins.jsonl"


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _read_checkins() -> list[dict[str, Any]]:
    if not _CHECKIN_FILE.exists():
        return []

    rows: list[dict[str, Any]] = []
    with _CHECKIN_FILE.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def log_time_checkin(activity: str, hours_saved: float) -> dict[str, Any]:
    """Log a CEO time-saved activity check-in."""
    timestamp = _now_utc().isoformat()
    clean_activity = str(activity).strip()
    if not clean_activity:
        return {"ok": False, "status": "INVALID_ACTIVITY", "message": "Activity text is required."}

    try:
        saved = float(hours_saved)
    except (TypeError, ValueError):
        return {"ok": False, "status": "INVALID_HOURS", "message": "hours_saved must be numeric."}

    record = {
        "timestamp": timestamp,
        "activity": clean_activity,
        "hours_saved": saved,
    }
    _CHECKIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _CHECKIN_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")

    return {"ok": True, "timestamp": timestamp, "activity": clean_activity, "hours_saved": saved}


def get_time_saved_report(days: int = 14) -> dict[str, Any]:
    """Compute time-saved report over the last N days."""
    window_days = max(1, int(days))
    rows = _read_checkins()
    if not rows:
        return {
            "ok": True,
            "period_days": window_days,
            "total_hours_saved": 0.0,
            "daily_average": 0.0,
            "weekly_average": 0.0,
            "activities": [],
            "activity_count": 0,
            "meets_r9_threshold": False,
            "message": "No time check-ins yet (use time_checkin command).",
        }

    cutoff = _now_utc() - timedelta(days=window_days)
    filtered: list[dict[str, Any]] = []
    for row in rows:
        try:
            timestamp = datetime.fromisoformat(str(row.get("timestamp", "")))
        except ValueError:
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        if timestamp >= cutoff:
            filtered.append(row)

    if not filtered:
        return {
            "ok": True,
            "period_days": window_days,
            "total_hours_saved": 0.0,
            "daily_average": 0.0,
            "weekly_average": 0.0,
            "activities": [],
            "activity_count": 0,
            "meets_r9_threshold": False,
        }

    total_hours = sum(float(item.get("hours_saved", 0.0) or 0.0) for item in filtered)
    daily_avg = total_hours / float(window_days)
    weekly_avg = daily_avg * 7.0
    meets_threshold = weekly_avg >= 5.0

    return {
        "ok": True,
        "period_days": window_days,
        "total_hours_saved": round(total_hours, 1),
        "daily_average": round(daily_avg, 2),
        "weekly_average": round(weekly_avg, 2),
        "activities": filtered[-10:],
        "activity_count": len(filtered),
        "meets_r9_threshold": meets_threshold,
        "message": (
            f"Stage I proof: {weekly_avg:.1f} hours/week saved (R9 threshold: 5 hours/week)."
            if meets_threshold
            else f"Currently at {weekly_avg:.1f} hours/week (target: 5 hours/week)."
        ),
    }


def check_r9_guardrail(weeks: int = 2) -> dict[str, Any]:
    """Evaluate R9 stop-rule status from trailing time-saved data."""
    period_weeks = max(1, int(weeks))
    report = get_time_saved_report(days=period_weeks * 7)
    weekly_avg = float(report.get("weekly_average", 0.0) or 0.0)

    if weekly_avg >= 5.0:
        status = "GREEN"
        message = f"Time-saved guardrail healthy: {weekly_avg:.1f} hours/week (threshold: 5)."
    elif weekly_avg >= 2.5:
        status = "AMBER"
        message = f"Time-saved guardrail at risk: {weekly_avg:.1f} hours/week (target: 5)."
    else:
        status = "RED"
        message = f"R9 guardrail breached: {weekly_avg:.1f} hours/week (minimum: 5)."

    return {
        "ok": True,
        "status": status,
        "weekly_average_hours": round(weekly_avg, 2),
        "message": message,
    }


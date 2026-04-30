"""Shared utility functions for AI Holding Company scripts.

Single source of truth for helpers that were previously duplicated across
monitoring.py, phase2_crews.py, phase3_holding.py, project_reports.py,
aiogram_bridge.py, and local_vector_memory.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]


def now_utc_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a mapping: {path}")
    return data


def parse_float(value: Any) -> float | None:
    """Coerce a value to float, returning None if conversion fails."""
    if value is None:
        return None
    token = str(value).strip().replace(",", "")
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def fmt_money(value: Any) -> str:
    """Format a numeric value as a signed dollar amount (e.g. '+$1,234.56')."""
    parsed = parse_float(value)
    if parsed is None:
        return "n/a"
    return f"${parsed:+,.2f}"


def parse_iso_utc(value: Any) -> datetime | None:
    """Parse an ISO 8601 string into a UTC-aware datetime, or return None."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_polymarket_ts(value: Any) -> datetime | None:
    """Parse a Polymarket log timestamp string into a UTC-aware datetime."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def reports_dir(config: dict[str, Any]) -> Path:
    """Return (and create) the reports directory from config."""
    rel = str(config.get("paths", {}).get("reports_dir", "reports"))
    path = ROOT / rel
    path.mkdir(parents=True, exist_ok=True)
    return path

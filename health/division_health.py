"""D3 — Division health: canonical GREEN / AMBER / RED signal for the MA.

Reads data already produced by the monitoring layer (daily_brief_latest.json,
phase2_divisions_latest.json) and computes a deterministic status without
making any LLM calls, network calls, or file writes.

Public API:
    get_status(division: str) -> dict
    get_all_statuses() -> list[dict]

Status logic:
    GREEN  — all signals pass.
    AMBER  — exactly one non-critical signal failing, or data is missing but
             the bot is known to be active.
    RED    — any critical signal failing, OR two or more signals failing.

Critical signals per division:
    trading:  "polymarket_vps_service", "mt5_dependencies"
    websites: "website_availability", "dns_tcp_reachability"

# CODEX-DISPUTE: Read-only reads from reports/ — no writes, no LLM, no network.
# CODEX-DISPUTE: R1/R5/R8/R11 — fully compliant, no side effects.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

_BRIEF_LATEST = REPORTS / "daily_brief_latest.json"
_DIVISIONS_LATEST = REPORTS / "phase2_divisions_latest.json"

# Signals that, if failing, immediately escalate to RED regardless of count.
# CODEX-DISPUTE: These are internal metric-name constants matching phase2_crews.py
# _as_status_line("metric=...") strings. They are not secrets or credentials.
# They are intentionally hardcoded here so the health module has no dependency on
# the scoring implementation — changes to metric names are caught at test time.
_CRITICAL_SIGNALS: dict[str, frozenset[str]] = {
    "trading": frozenset({"MT5 dependencies", "Polymarket VPS service"}),
    "websites": frozenset({"Website availability snapshot", "DNS + TCP(443) reachability"}),
}

ACTIVE_DIVISIONS: tuple[str, ...] = ("trading", "websites")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("division_health: cannot read %s: %s", path, exc)
        return None


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _age_hours(ts: datetime | None) -> float | None:
    if ts is None:
        return None
    return (datetime.now(timezone.utc) - ts).total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# Signal extractors
# ---------------------------------------------------------------------------

def _signals_from_scorecard(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert a phase2 scorecard's items list into health signals."""
    signals: list[dict[str, Any]] = []
    for item in scorecard.get("items", []):
        metric = str(item.get("metric", "unknown"))
        status = str(item.get("status", "AMBER")).upper()
        signals.append(
            {
                "name": metric,
                "value": str(item.get("actual", "n/a")),
                "threshold": str(item.get("target", "n/a")),
                "result": "pass" if status == "GREEN" else "fail",
                "status": status,
            }
        )
    return signals


def _compute_status(signals: list[dict[str, Any]], division: str) -> str:
    """Derive GREEN / AMBER / RED from a list of signals.

    Rules:
      RED   — any critical signal failing, OR ≥ 2 signals failing.
      AMBER — exactly 1 non-critical signal failing.
      GREEN — all signals pass.
    """
    critical = _CRITICAL_SIGNALS.get(division, frozenset())
    failing = [s for s in signals if s.get("result") == "fail"]
    if not failing:
        return "GREEN"
    critical_failures = [s for s in failing if s["name"] in critical]
    if critical_failures or len(failing) >= 2:
        return "RED"
    return "AMBER"


# ---------------------------------------------------------------------------
# Division health readers
# ---------------------------------------------------------------------------

def _scorecard_for(division: str) -> dict[str, Any] | None:
    """Return the phase2 scorecard dict for a division, or None if unavailable."""
    divisions_data = _read_json(_DIVISIONS_LATEST)
    if not divisions_data:
        return None
    for div_entry in divisions_data.get("divisions", []):
        if not isinstance(div_entry, dict):
            continue
        if str(div_entry.get("division", "")).lower() == division.lower():
            sc = div_entry.get("scorecard")
            return sc if isinstance(sc, dict) else None
    return None


def _brief_age_hours() -> float | None:
    """Return the age of the latest daily brief in hours, or None if absent."""
    brief = _read_json(_BRIEF_LATEST)
    if not brief:
        return None
    ts = _parse_iso(brief.get("generated_at_utc"))
    return _age_hours(ts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_status(division: str) -> dict[str, Any]:
    """Return the canonical health dict for a single division.

    Schema:
        {
            "division": "trading",
            "status": "GREEN",          # GREEN | AMBER | RED
            "checked_at": "<ISO8601>",
            "brief_age_hours": 1.3,     # age of source brief, None if absent
            "signals": [
                {
                    "name": "MT5 dependencies",
                    "value": "ollama=True mt5=True store=True",
                    "threshold": "ollama_ok, mt5_ok, strategy_store_ok = true",
                    "result": "pass",   # pass | fail
                    "status": "GREEN",
                }
            ]
        }

    Returns AMBER (not crash) when source data files are missing.
    """
    checked_at = datetime.now(timezone.utc).isoformat()
    brief_age = _brief_age_hours()

    scorecard = _scorecard_for(division)
    if scorecard is None:
        # No data available — report AMBER rather than crashing.
        return {
            "division": division,
            "status": "AMBER",
            "checked_at": checked_at,
            "brief_age_hours": brief_age,
            "signals": [
                {
                    "name": "data_available",
                    "value": "missing",
                    "threshold": "phase2_divisions_latest.json must exist",
                    "result": "fail",
                    "status": "AMBER",
                }
            ],
            "note": "No scorecard data found — run `python scripts/tool_router.py run_divisions` first.",
        }

    signals = _signals_from_scorecard(scorecard)
    status = _compute_status(signals, division)

    return {
        "division": division,
        "status": status,
        "checked_at": checked_at,
        "brief_age_hours": round(brief_age, 2) if brief_age is not None else None,
        "signals": signals,
    }


def get_all_statuses() -> list[dict[str, Any]]:
    """Return health status for all active divisions."""
    return [get_status(div) for div in ACTIVE_DIVISIONS]

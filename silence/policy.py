"""Silence policy — controls when the system is allowed to send unsolicited messages.

R10: Silence by default. Only speak if:
  (a) There is an open item in artifacts/decision_queue.json, OR
  (b) A status colour changed since the last outbound message, OR
  (c) ≥7 days have elapsed since the last outbound message.

State tracked in artifacts/silence_state.json.
Every outbound message is logged with reason code and timestamp.
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

SILENCE_STATE_FILE = ARTIFACTS / "silence_state.json"
DECISION_QUEUE_FILE = ARTIFACTS / "decision_queue.json"

_SILENCE_DAYS = 7


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_state() -> dict[str, Any]:
    if not SILENCE_STATE_FILE.exists():
        return {"last_sent": None, "last_status": {}, "messages": []}
    try:
        data = json.loads(SILENCE_STATE_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"last_sent": None, "last_status": {}, "messages": []}
        data.setdefault("last_sent", None)
        data.setdefault("last_status", {})
        data.setdefault("messages", [])
        return data
    except (json.JSONDecodeError, OSError):
        return {"last_sent": None, "last_status": {}, "messages": []}


def _save_state(state: dict[str, Any]) -> None:
    SILENCE_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _load_queue() -> list:
    if not DECISION_QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(DECISION_QUEUE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def should_speak(reason: str, current_status: dict[str, Any] | None = None) -> bool:
    """Decide whether the system may send an unsolicited message.

    Args:
        reason: Short description of why the system wants to speak.
        current_status: Optional dict of {division: colour} for change detection.

    Returns True only under one of the three permitted conditions.
    """
    if not reason or not isinstance(reason, str):
        reason = "unspecified"
    state = _load_state()
    now = _now()

    # Condition (a): open decision queue item
    queue = _load_queue()
    if queue:
        _record_outbound(state, now, reason, "queue_open")
        return True

    # Condition (b): status colour changed since last message
    if current_status and isinstance(current_status, dict):
        last_status: dict = state.get("last_status", {})
        for division, colour in current_status.items():
            if last_status.get(division) != colour:
                _record_outbound(state, now, reason, "status_change")
                state["last_status"] = dict(current_status)
                _save_state(state)
                return True

    # Condition (c): ≥7 days since last outbound
    last_sent_iso: str | None = state.get("last_sent")
    if last_sent_iso is None:
        # Never sent — allow first message
        _record_outbound(state, now, reason, "first_message")
        return True

    try:
        last_sent_dt = datetime.fromisoformat(last_sent_iso)
    except ValueError:
        _record_outbound(state, now, reason, "state_parse_error")
        return True

    if (now - last_sent_dt) >= timedelta(days=_SILENCE_DAYS):
        _record_outbound(state, now, reason, "weekly_cadence")
        return True

    return False


def record_sent(reason: str, current_status: dict[str, Any] | None = None) -> None:
    """Record that an outbound message was sent (call after actually sending)."""
    state = _load_state()
    now = _now()
    if current_status:
        state["last_status"] = dict(current_status)
    _record_outbound(state, now, reason, "explicit_record")


def _record_outbound(
    state: dict[str, Any],
    ts: datetime,
    reason: str,
    code: str,
) -> None:
    """Append a log entry and update last_sent in state, then persist."""
    state["last_sent"] = ts.isoformat()
    messages: list = state.get("messages", [])
    messages.append({"ts": ts.isoformat(), "reason": reason, "code": code})
    state["messages"] = messages
    _save_state(state)

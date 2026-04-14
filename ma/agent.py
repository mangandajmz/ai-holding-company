"""Master Agent (MA) — routes Goal JSON through Guardian, escalation checks, and decision queue.

Flow for every goal received:
  1. Guardian compliance check → if fail, escalate to CEO via gateway and stop.
  2. Check 9 escalation rules → if triggered, send escalation and stop.
  3. Decision queue cap check (max 5 open items).
  4. Route goal → log result.

Returns a plain string reply for the Telegram bot to forward to the CEO.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from compliance.guardian import check as guardian_check

log = logging.getLogger(__name__)


def _violation_summary_since(since_iso: str) -> str:
    """Return a brief violation summary since since_iso, silently ignoring import errors."""
    try:
        from sanitizer.violation_reporter import summarise  # type: ignore[import]
        return summarise(since_iso)
    except Exception as exc:  # noqa: BLE001
        log.debug("ma: violation summary unavailable: %s", exc)
        return ""

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)

DECISION_QUEUE_FILE = ARTIFACTS / "decision_queue.json"
MA_LOG_FILE = ARTIFACTS / "ma_log.json"

_QUEUE_CAP = 5

# ---------------------------------------------------------------------------
# 9 Escalation rules (derived from PLAN §5 intent):
#   E1 — Unknown intent
#   E2 — Unknown division
#   E3 — High urgency monitor/report
#   E4 — Approve/reject with no open queue item
#   E5 — Approve/reject when queue is at cap
#   E6 — Any R5 guardian violation (fund action)
#   E7 — Any R1/R11 guardian violation (infra/model)
#   E8 — Research on unknown division
#   E9 — Queue cap reached on new non-approve goal
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_queue() -> list[dict[str, Any]]:
    if not DECISION_QUEUE_FILE.exists():
        return []
    try:
        data = json.loads(DECISION_QUEUE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_queue(queue: list[dict[str, Any]]) -> None:
    DECISION_QUEUE_FILE.write_text(json.dumps(queue, indent=2), encoding="utf-8")


def _append_log(entry: dict[str, Any]) -> None:
    existing: list = []
    if MA_LOG_FILE.exists():
        try:
            existing = json.loads(MA_LOG_FILE.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = []
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append(entry)
    MA_LOG_FILE.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _escalation_msg(reason: str, options: list[str], recommendation: str) -> str:
    opts = ", ".join(options)
    return f"[ESCALATION] Cannot classify: {reason}.\nOptions: {opts}.\nRecommendation: {recommendation}."


def _check_escalation(goal: dict[str, Any], queue: list[dict[str, Any]]) -> str | None:
    """Return escalation message string if any rule fires, else None."""
    intent: str = goal.get("intent", "unknown")
    division: str = goal.get("division", "unknown")
    urgency: str = goal.get("urgency", "unknown")

    # E1 — unknown intent
    if intent == "unknown":
        return _escalation_msg(
            "intent could not be classified",
            ["Clarify goal", "Ignore"],
            "Clarify goal",
        )

    # E2 — unknown division
    if division == "unknown" and intent not in ("status", "approve", "reject"):
        return _escalation_msg(
            "division could not be determined",
            ["Specify division", "Apply to all", "Ignore"],
            "Specify division",
        )

    # E3 — high urgency monitor/report
    if urgency == "high" and intent in ("monitor", "report"):
        return _escalation_msg(
            f"high-urgency {intent} request requires CEO confirmation",
            ["Proceed immediately", "Wait for next scheduled run", "Ignore"],
            "Proceed immediately",
        )

    # E4 — approve/reject with empty queue
    if intent in ("approve", "reject") and not queue:
        return _escalation_msg(
            "no pending decision items in queue",
            ["Confirm which item", "Ignore"],
            "Confirm which item",
        )

    # E5 — approve/reject when queue at cap
    if intent in ("approve", "reject") and len(queue) >= _QUEUE_CAP:
        return _escalation_msg(
            "decision queue is at capacity",
            ["Clear oldest item first", "Proceed anyway", "Ignore"],
            "Clear oldest item first",
        )

    # E8 — research on unknown division
    if intent == "research" and division == "unknown":
        return _escalation_msg(
            "research requested but no division specified",
            ["Specify division", "Apply to all divisions"],
            "Specify division",
        )

    return None


def handle_goal(goal: dict[str, Any]) -> str:
    """Process a Goal JSON dict. Returns a reply string for the CEO.

    All side effects (queue writes, log writes) are inside ai-holding-company/.
    No LLM calls in this module. No fund actions.
    """
    if not isinstance(goal, dict):
        return "[ERROR] Invalid goal: expected a dict"
    goal_id: str = str(goal.get("goal_id") or "unknown")
    intent: str = str(goal.get("intent") or "unknown")
    ts = _now_iso()

    guardian_result = guardian_check(goal)
    routing_decision = "pending"
    outcome = "pending"

    if not guardian_result.get("pass"):
        violated = guardian_result.get("violated_rules", [])
        reason = guardian_result.get("reason", "compliance failure")
        routing_decision = "escalated_guardian"
        outcome = "blocked"

        _append_log({
            "goal_id": goal_id,
            "timestamp": ts,
            "routing_decision": routing_decision,
            "guardian_result": guardian_result,
            "outcome": outcome,
        })

        return (
            f"[ESCALATION] Cannot classify: compliance block ({', '.join(violated)}).\n"
            f"Options: Revise request, Ignore.\n"
            f"Recommendation: Revise request.\n"
            f"Reason: {reason}"
        )

    # Load queue for escalation checks
    queue = _read_queue()

    # Check 9 escalation rules
    escalation = _check_escalation(goal, queue)
    if escalation:
        routing_decision = "escalated_rule"
        outcome = "escalated"

        # Add to decision queue if not already at cap
        if len(queue) < _QUEUE_CAP:
            queue.append({"goal_id": goal_id, "goal": goal, "queued_at": ts})
            _write_queue(queue)

        _append_log({
            "goal_id": goal_id,
            "timestamp": ts,
            "routing_decision": routing_decision,
            "guardian_result": guardian_result,
            "outcome": outcome,
        })
        return escalation

    # E9 — queue cap on non-approve/reject goal
    if intent not in ("approve", "reject") and len(queue) >= _QUEUE_CAP:
        routing_decision = "queue_cap"
        outcome = "blocked_cap"
        _append_log({
            "goal_id": goal_id,
            "timestamp": ts,
            "routing_decision": routing_decision,
            "guardian_result": guardian_result,
            "outcome": outcome,
        })
        return (
            "[ESCALATION] Cannot classify: decision queue is full (5 items).\n"
            "Options: Review open items, Clear resolved items.\n"
            "Recommendation: Review open items."
        )

    # Normal routing
    routing_decision = f"routed:{intent}"
    outcome = "routed"

    if intent in ("approve", "reject"):
        # Pop oldest queue item on approve/reject
        if queue:
            resolved = queue.pop(0)
            _write_queue(queue)
            reply = (
                f"Acknowledged: {intent.upper()} applied to goal {resolved['goal_id']}. "
                f"Queue now has {len(queue)} item(s)."
            )
        else:
            reply = f"Acknowledged: {intent.upper()} — no pending items in queue."
    elif intent == "status":
        reply = "Status request received. Running monitoring pipeline now..."
    elif intent == "monitor":
        reply = "Monitor request received. Scheduling division check..."
    elif intent == "report":
        reply = "Report request received. Generating briefing..."
    elif intent == "research":
        division = goal.get("division", "all")
        reply = f"Research request received for division: {division}."
    else:
        reply = f"Goal received (intent={intent}). Logged for processing."

    parsed_at: str = str(goal.get("parsed_at") or ts)
    violation_summary = _violation_summary_since(parsed_at)

    log_entry: dict[str, Any] = {
        "goal_id": goal_id,
        "timestamp": ts,
        "routing_decision": routing_decision,
        "guardian_result": guardian_result,
        "outcome": outcome,
    }
    if violation_summary and violation_summary != "No violations recorded.":
        log_entry["violation_summary"] = violation_summary

    _append_log(log_entry)

    return reply

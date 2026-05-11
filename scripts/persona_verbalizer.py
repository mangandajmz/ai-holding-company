"""Persona verbalization boundary.

This module is the future NanoClaw integration point. Today it provides a
deterministic fallback verbalizer so persona chat can move through a truth
packet contract without making model calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROLE_ANSWERS = {
    "chief-of-staff": (
        "I help you run the company day to day. I keep track of what needs your attention, "
        "what is blocked, what can wait, and which evidence supports each recommendation."
    ),
    "risk-officer": (
        "I protect the company from avoidable risk. I look for missing evidence, blocked "
        "guardrails, and decisions that should not move forward without approval."
    ),
    "quant-ops": (
        "I keep the trading operation honest. I watch data quality, backtest readiness, "
        "broker reconciliation, and anything that could make research or live trading unsafe."
    ),
    "growth-lead": (
        "I turn website evidence into growth priorities. I watch traffic, revenue, content "
        "performance, and anomalies that need a decision."
    ),
    "editorial-lead": (
        "I manage the content workflow. I help turn briefs into drafts, keep quality and SEO "
        "visible, and escalate anything that needs human publishing judgment."
    ),
    "engineering-ops": (
        "I keep the operating layer reliable. I watch incidents, deploy readiness, tests, and "
        "the parts of the system that could quietly stop working."
    ),
    "support-lead": (
        "I watch customer support once a real ticket source exists. I classify routine issues, "
        "surface exceptions, and keep unresolved customer pain visible."
    ),
    "finance-admin": (
        "I am deferred until reliable finance sources exist. Once wired, I will watch close, "
        "cost, cash, compliance, and admin follow-through."
    ),
}


def _clean_brief(brief: str) -> str:
    cleaned = brief.strip()
    for prefix in (
        "Backtest review is BLOCKED. ",
        "Portfolio retro is BLOCKED. ",
        "Support triage is BLOCKED. ",
        "The company is RED in the latest stored CEO report. ",
    ):
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix)
    return cleaned


def _approval_phrase(count: int) -> str:
    if count == 1:
        return "You have one approval waiting."
    if count > 1:
        return f"You have {count} approvals waiting."
    return ""


def _chief_status(packet: dict[str, Any]) -> str:
    parts: list[str] = ["Welcome back."]
    approvals = _approval_phrase(int(packet.get("approvals_count") or 0))
    if approvals:
        parts.append(approvals)
    evidence = packet.get("evidence", [])
    if evidence:
        lead = evidence[0]
        lead_brief = _clean_brief(str(lead.get("brief") or ""))
        if str(lead.get("status") or "").upper() == "GREEN":
            parts.append(lead_brief)
        else:
            parts.append(f"I would focus there first: {lead_brief}")
            if len(evidence) > 1:
                parts.append(f"There are {len(evidence)} current evidence items behind that.")
    if len(parts) == 1:
        return "I do not see a stored issue needing you right now."
    return " ".join(parts)


def _risk_status(packet: dict[str, Any]) -> str:
    evidence = packet.get("evidence", [])
    blocking = [item for item in evidence if item.get("status") in {"BLOCKED", "RED"}]
    if blocking:
        lead = blocking[0]
        return f"I object for now. I would not move it forward until this is resolved. {lead.get('brief')}"
    if evidence:
        return f"I do not see a hard block, but I would review this first: {evidence[0].get('brief')}"
    return "I do not see a stored risk objection in my current sources."


def deterministic_verbalize(packet: dict[str, Any]) -> dict[str, Any]:
    """Return a natural answer from a bounded truth packet without model calls."""

    persona = str(packet.get("persona") or "")
    intent = str(packet.get("intent") or "status")
    evidence = packet.get("evidence", [])
    if intent == "role":
        answer = ROLE_ANSWERS.get(persona, "I answer from the company records available to my role.")
    elif persona == "chief-of-staff":
        answer = _chief_status(packet)
    elif persona == "risk-officer":
        answer = _risk_status(packet)
    elif evidence:
        answer = f"{packet.get('display_name')} has current evidence: {evidence[0].get('brief')}"
    else:
        answer = str(packet.get("unknown_answer") or "I do not have current evidence to answer that yet.")
    return {
        "answer": answer,
        "unsupported_claims": [],
        "evidence_mode": "hidden" if evidence else "none",
        "confidence": "high" if packet.get("truth_state") == "known" or intent == "role" else "low",
        "provider": "deterministic_fallback",
        "no_model_calls": True,
    }


def verify_verbalizer_output(output: dict[str, Any]) -> dict[str, Any]:
    """Validate a verbalizer response before it can be used or compared."""

    unsupported = output.get("unsupported_claims", [])
    if isinstance(unsupported, list) and unsupported:
        return {"accepted": False, "reason": "unsupported_claims"}
    answer = str(output.get("answer") or "").strip()
    if not answer:
        return {"accepted": False, "reason": "empty_answer"}
    return {"accepted": True, "reason": "ok"}


def _read_jsonl_latest(path: Path, persona: str, intent: str) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        rows = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in reversed(rows):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("persona") == persona and payload.get("intent") == intent:
            return payload
    return {}


def _append_shadow_inbox(packet: dict[str, Any], config: dict[str, Any], root: Path) -> None:
    nanoclaw_cfg = config.get("nanoclaw", {}) if isinstance(config.get("nanoclaw", {}), dict) else {}
    if nanoclaw_cfg.get("mode") != "shadow":
        return
    inbox_path = str(nanoclaw_cfg.get("shadow_inbox_path") or "state/nanoclaw_shadow_inbox.jsonl")
    path = root / inbox_path
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "type": "nanoclaw_shadow_request",
        "packet_id": packet.get("packet_id"),
        "packet": packet,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def nanoclaw_shadow_verbalize(packet: dict[str, Any], config: dict[str, Any], root: Path) -> dict[str, Any]:
    """Read a future NanoClaw outbox record for shadow comparison only."""

    nanoclaw_cfg = config.get("nanoclaw", {}) if isinstance(config.get("nanoclaw", {}), dict) else {}
    if nanoclaw_cfg.get("mode") != "shadow":
        return {"provider": "nanoclaw_shadow", "enabled": False, "accepted": False, "reason": "disabled"}
    outbox_path = str(nanoclaw_cfg.get("shadow_outbox_path") or "").strip()
    if not outbox_path:
        return {"provider": "nanoclaw_shadow", "enabled": True, "accepted": False, "reason": "missing_outbox_path"}
    output = _read_jsonl_latest(root / outbox_path, persona=str(packet["persona"]), intent=str(packet["intent"]))
    if not output:
        return {"provider": "nanoclaw_shadow", "enabled": True, "accepted": False, "reason": "no_shadow_output"}
    if output.get("packet_id") != packet.get("packet_id"):
        return {"provider": "nanoclaw_shadow", "enabled": True, "accepted": False, "reason": "packet_id_mismatch"}
    verdict = verify_verbalizer_output(output)
    return {
        "provider": "nanoclaw_shadow",
        "enabled": True,
        "accepted": verdict["accepted"],
        "reason": verdict["reason"],
        "answer": str(output.get("answer") or ""),
        "confidence": str(output.get("confidence") or "unknown"),
        "unsupported_claims": output.get("unsupported_claims", []),
    }


def run_verbalizers(
    packet: dict[str, Any],
    config: dict[str, Any] | None = None,
    root: Path | str = ".",
) -> dict[str, Any]:
    """Run the live deterministic verbalizer plus optional NanoClaw shadow."""

    cfg = config if isinstance(config, dict) else {}
    _append_shadow_inbox(packet=packet, config=cfg, root=Path(root))
    primary = deterministic_verbalize(packet)
    shadow = nanoclaw_shadow_verbalize(packet=packet, config=cfg, root=Path(root))
    return {"primary": primary, "shadow": shadow}

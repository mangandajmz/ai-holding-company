"""Open-ended persona chat over local organization truth."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from persona_verbalizer import run_verbalizers


ROOT = Path(__file__).resolve().parents[1]
ISSUE_STATUSES = {"BLOCKED", "RED", "AMBER", "YELLOW"}
ROLE_PATTERNS = (
    "what do you do",
    "who are you",
    "what is your role",
    "your role",
    "how do you help",
)


@dataclass(frozen=True)
class PersonaSpec:
    slug: str
    display_name: str
    sources: tuple[str, ...]
    unknown_answer: str


PERSONAS: dict[str, PersonaSpec] = {
    "chief-of-staff": PersonaSpec(
        slug="chief-of-staff",
        display_name="Chief of Staff",
        sources=(
            "state/board_approval_decisions.json",
            "reports/phase3_holding_latest.json",
            "reports/skills/risk-aggregate-daily/latest.json",
            "reports/skills/portfolio-retro-weekly/latest.json",
            "reports/skills/backtest-review/latest.json",
            "reports/skills/support-triage/latest.json",
        ),
        unknown_answer="I do not have current company evidence to answer that yet.",
    ),
    "risk-officer": PersonaSpec(
        slug="risk-officer",
        display_name="Risk Officer",
        sources=(
            "reports/skills/backtest-review/latest.json",
            "reports/skills/data-quality-daily/latest.json",
            "reports/skills/pre-deploy-checklist/latest.json",
            "state/board_approval_decisions.json",
        ),
        unknown_answer="I do not have current risk evidence to answer that yet.",
    ),
    "quant-ops": PersonaSpec(
        slug="quant-ops",
        display_name="Quant Ops",
        sources=(
            "reports/skills/data-quality-daily/latest.json",
            "reports/skills/backtest-review/latest.json",
            "reports/skills/broker-reconcile/latest.json",
        ),
        unknown_answer="I do not have current Quant Ops evidence to answer that yet.",
    ),
    "growth-lead": PersonaSpec(
        slug="growth-lead",
        display_name="Growth Lead",
        sources=(
            "reports/phase2_divisions_latest.json",
            "reports/skills/analytics-weekly/latest.json",
            "reports/skills/portfolio-retro-weekly/latest.json",
        ),
        unknown_answer="I do not have current growth evidence to answer that yet.",
    ),
    "editorial-lead": PersonaSpec(
        slug="editorial-lead",
        display_name="Editorial Lead",
        sources=(
            "reports/skills/content-brief-to-draft/latest.json",
            "reports/skills/analytics-weekly/latest.json",
            "state/content_studio.json",
        ),
        unknown_answer="I do not have current editorial queue evidence to answer that yet.",
    ),
    "engineering-ops": PersonaSpec(
        slug="engineering-ops",
        display_name="Engineering/Ops",
        sources=(
            "reports/daily_brief_latest.json",
            "reports/phase2_divisions_latest.json",
            "reports/phase3_holding_latest.json",
            "reports/skills/portfolio-retro-weekly/latest.json",
        ),
        unknown_answer="I do not have current engineering or operations evidence to answer that yet.",
    ),
    "support-lead": PersonaSpec(
        slug="support-lead",
        display_name="Support Lead",
        sources=(
            "reports/skills/support-triage/latest.json",
            "state/support_tickets.json",
        ),
        unknown_answer="I do not have current support evidence to answer that yet.",
    ),
    "finance-admin": PersonaSpec(
        slug="finance-admin",
        display_name="Finance/Admin",
        sources=(
            "reports/skills/monthly-close-prep/latest.json",
            "reports/skills/infra-cost-review/latest.json",
            "reports/skills/compliance-monitor/latest.json",
        ),
        unknown_answer="Finance/Admin is deferred until reliable finance sources exist.",
    ),
}

ALIASES = {
    "chief": "chief-of-staff",
    "chief of staff": "chief-of-staff",
    "cos": "chief-of-staff",
    "risk": "risk-officer",
    "risk officer": "risk-officer",
    "quant": "quant-ops",
    "quant ops": "quant-ops",
    "growth": "growth-lead",
    "growth lead": "growth-lead",
    "editorial": "editorial-lead",
    "editor": "editorial-lead",
    "engineering": "engineering-ops",
    "ops": "engineering-ops",
    "support": "support-lead",
    "support lead": "support-lead",
    "finance": "finance-admin",
    "finance admin": "finance-admin",
}


def normalize_persona(value: str) -> str:
    cleaned = value.strip().lower().replace("_", "-")
    cleaned = cleaned.replace(" ", "-") if cleaned in PERSONAS else cleaned
    if cleaned in PERSONAS:
        return cleaned
    return ALIASES.get(value.strip().lower(), "chief-of-staff")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_sources(root: Path, spec: PersonaSpec) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    for rel_path in spec.sources:
        payload = _read_json(root / rel_path)
        if payload:
            loaded.append({"path": rel_path, "payload": payload})
    return loaded


def _status(payload: dict[str, Any]) -> str:
    return str(payload.get("status") or payload.get("company_scorecard", {}).get("status") or "UNKNOWN").upper()


def _brief(payload: dict[str, Any]) -> str:
    if payload.get("brief"):
        return str(payload.get("brief"))
    scorecard = payload.get("company_scorecard", {})
    if isinstance(scorecard, dict):
        risks = scorecard.get("risks", [])
        if isinstance(risks, list) and risks:
            return str(risks[0])
    return ""


def _approval_count(source_rows: list[dict[str, Any]]) -> int:
    for row in source_rows:
        if row["path"] != "state/board_approval_decisions.json":
            continue
        snapshot = row["payload"].get("board_snapshot", {})
        snapshot = snapshot if isinstance(snapshot, dict) else {}
        approvals = snapshot.get("approvals", [])
        return len(approvals) if isinstance(approvals, list) else 0
    return 0


def _issue_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for row in source_rows:
        payload = row["payload"]
        status = _status(payload)
        brief = _brief(payload)
        if status in ISSUE_STATUSES or brief:
            issues.append(
                {
                    "source": str(row["path"]),
                    "skill": str(payload.get("skill") or Path(str(row["path"])).parent.name),
                    "status": status,
                    "brief": brief,
                    "owner_need": str(payload.get("owner_need") or "none"),
                }
            )
    issues.sort(key=lambda item: (item["status"] != "BLOCKED", item["status"] != "RED", item["skill"]))
    return issues


def _owner_need(source_rows: list[dict[str, Any]], issues: list[dict[str, str]]) -> str:
    if _approval_count(source_rows) > 0:
        return "approve"
    if any(item.get("owner_need") == "approve" for item in issues):
        return "approve"
    return "none"


def classify_intent(message: str) -> str:
    """Classify broad persona-chat intent without a model call."""

    lowered = message.strip().lower()
    if any(pattern in lowered for pattern in ROLE_PATTERNS):
        return "role"
    if any(word in lowered for word in ("why", "evidence", "source", "prove", "show me")):
        return "evidence"
    if any(word in lowered for word in ("approve", "approval", "decision")):
        return "approval"
    if any(word in lowered for word in ("do", "fix", "execute", "send", "publish", "deploy")):
        return "action"
    return "status"


def build_truth_packet(persona: str, message: str, root: Path | str = ROOT) -> dict[str, Any]:
    """Build the bounded truth packet that a future NanoClaw layer may verbalize."""

    root_path = Path(root)
    slug = normalize_persona(persona)
    spec = PERSONAS[slug]
    rows = _load_sources(root_path, spec)
    issues = _issue_rows(rows)
    sources = [row["path"] for row in rows]
    truth_state = "known" if rows else "unknown"
    owner_need = _owner_need(rows, issues)
    packet = {
        "schema_version": "persona_truth_packet.v1",
        "persona": spec.slug,
        "display_name": spec.display_name,
        "intent": classify_intent(message),
        "user_message": message,
        "truth_state": truth_state,
        "owner_need": owner_need,
        "approvals_count": _approval_count(rows),
        "evidence": issues,
        "sources": sources,
        "unknowns": [] if rows else [spec.unknown_answer],
        "unknown_answer": spec.unknown_answer,
        "policy": {
            "allowed_claim_source": "truth_packet_only",
            "no_tool_calls": True,
            "no_file_reads": True,
            "no_writes": True,
        },
    }
    packet["packet_id"] = _packet_id(packet)
    return packet


def _packet_id(packet: dict[str, Any]) -> str:
    stable = {
        "schema_version": packet.get("schema_version"),
        "persona": packet.get("persona"),
        "intent": packet.get("intent"),
        "user_message": packet.get("user_message"),
        "evidence": packet.get("evidence", []),
        "sources": packet.get("sources", []),
    }
    encoded = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def answer_persona(
    persona: str,
    message: str,
    root: Path | str = ROOT,
    conversation_config: dict[str, Any] | None = None,
    full_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Answer free text as a persona using only allowed local truth sources."""

    packet = build_truth_packet(persona=persona, message=message, root=root)
    verbalizers = run_verbalizers(
        packet,
        config=conversation_config,
        root=root,
        full_config=full_config,
    )
    verbalized = verbalizers["primary"]
    return {
        "ok": True,
        "persona": packet["persona"],
        "display_name": packet["display_name"],
        "message": message,
        "answer": verbalized["answer"],
        "intent": packet["intent"],
        "truth_state": packet["truth_state"],
        "owner_need": packet["owner_need"],
        "sources": packet["sources"],
        "evidence": packet["evidence"],
        "truth_packet": packet,
        "verbalizer": {
            "provider": verbalized["provider"],
            "unsupported_claims": verbalized["unsupported_claims"],
            "evidence_mode": verbalized["evidence_mode"],
            "confidence": verbalized["confidence"],
        },
        "shadow_verbalizer": verbalizers["shadow"],
        "grounding_mode": "deterministic_local_truth",
        "no_model_calls": verbalized["no_model_calls"],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask a persona a free-text question over local org truth.")
    parser.add_argument("--persona", required=True, help="Persona name or slug.")
    parser.add_argument("--message", required=True, help="Free-text message.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    print(json.dumps(answer_persona(args.persona, args.message, root=Path(args.root)), indent=2))


if __name__ == "__main__":
    main()

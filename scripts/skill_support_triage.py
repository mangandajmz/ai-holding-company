"""Support triage shadow-mode runtime for local ticket intake."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from org_truth_retriever import ROOT


SKILL_NAME = "support-triage"
DEFAULT_SOURCE = Path("state") / "support_tickets.json"
ESCALATION_CATEGORIES = {"billing", "account", "legal"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _ticket_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("tickets", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _classify(subject: str, body: str) -> str:
    text = f"{subject} {body}".lower()
    if any(term in text for term in ("refund", "charge", "charged", "billing", "invoice", "payment")):
        return "billing"
    if any(term in text for term in ("login", "password", "account", "sign in", "signin")):
        return "account"
    if any(term in text for term in ("legal", "terms", "privacy", "compliance")):
        return "legal"
    if any(term in text for term in ("bug", "broken", "error", "wrong", "not working", "fail")):
        return "bug"
    if any(term in text for term in ("feature", "request", "add", "could you", "can you")):
        return "feature_request"
    return "general"


def _draft_reply(category: str) -> str:
    if category == "bug":
        return (
            "Thanks for flagging this. We are going to reproduce the issue, check the affected tool, "
            "and follow up once we have a fix or a clear workaround."
        )
    if category == "feature_request":
        return (
            "Thanks for the suggestion. We will review it against the current roadmap and look for "
            "evidence that other users need the same workflow."
        )
    if category == "general":
        return "Thanks for reaching out. We will review this and get back to you with the next useful step."
    return ""


def _triage_ticket(ticket: dict[str, Any]) -> dict[str, str]:
    subject = _clean_text(ticket.get("subject"))
    body = _clean_text(ticket.get("body"))
    ticket_id = _clean_text(ticket.get("id")) or "untracked"
    category = _classify(subject, body)
    escalation_reason = ""
    if category in ESCALATION_CATEGORIES:
        escalation_reason = "Billing, refund, legal, or account issue."
    return {
        "ticket_id": ticket_id,
        "subject": subject,
        "category": category,
        "draft_reply": _draft_reply(category),
        "escalation_reason": escalation_reason,
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Support Triage",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        f"Autonomy: {payload['autonomy']}",
        f"Owner need: {payload['owner_need']}",
        "",
        "## Brief",
        "",
        payload["brief"],
        "",
        "## Tickets",
        "",
    ]
    if not payload["tickets"]:
        lines.append("- No tickets triaged.")
    for ticket in payload["tickets"]:
        lines.append(f"- {ticket['ticket_id']}: {ticket['category']} - {ticket['subject']}")
        if ticket["escalation_reason"]:
            lines.append(f"  Escalation: {ticket['escalation_reason']}")
        elif ticket["draft_reply"]:
            lines.append(f"  Draft: {ticket['draft_reply']}")
    lines.extend(["", "## Sources", ""])
    for source in payload["sources"]:
        lines.append(f"- `{source}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_outputs(root_path: Path, payload: dict[str, Any], markdown_rel: Path, json_rel: Path) -> None:
    latest_md_rel = Path("reports") / "skills" / SKILL_NAME / "latest.md"
    latest_json_rel = Path("reports") / "skills" / SKILL_NAME / "latest.json"
    _write_markdown(root_path / markdown_rel, payload)
    _write_json(root_path / json_rel, payload)
    _write_markdown(root_path / latest_md_rel, payload)
    _write_json(root_path / latest_json_rel, payload)


def _base_payload(stamp: str) -> dict[str, Any]:
    markdown_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.md"
    json_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.json"
    return {
        "ok": True,
        "skill": SKILL_NAME,
        "autonomy": "Approve",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "markdown_path": str(markdown_rel).replace("\\", "/"),
        "json_path": str(json_rel).replace("\\", "/"),
    }


def run_support_triage(root: Path | str = ROOT) -> dict[str, Any]:
    """Write a local support-triage artifact from state/support_tickets.json."""

    root_path = Path(root)
    source_rel = DEFAULT_SOURCE
    source_path = root_path / source_rel
    stamp = _utc_stamp()
    payload = _base_payload(stamp)
    markdown_rel = Path(payload["markdown_path"])
    json_rel = Path(payload["json_path"])

    if not source_path.exists():
        payload.update(
            {
                "status": "BLOCKED",
                "owner_need": "none",
                "brief": "Support triage is BLOCKED. No local support ticket source found at state/support_tickets.json.",
                "metrics": {"ticket_count": 0, "draft_count": 0, "escalation_count": 0},
                "tickets": [],
                "sources": [],
            }
        )
        _write_outputs(root_path, payload, markdown_rel, json_rel)
        return payload

    triaged = [_triage_ticket(ticket) for ticket in _ticket_rows(_read_json(source_path))]
    draft_count = sum(1 for ticket in triaged if ticket["draft_reply"])
    escalation_count = sum(1 for ticket in triaged if ticket["escalation_reason"])
    if triaged:
        status = "AMBER"
        owner_need = "approve" if draft_count else "none"
        brief = (
            f"Support triage found {len(triaged)} ticket(s): {draft_count} draft(s) "
            f"and {escalation_count} escalation(s). Drafts require owner or CS lead approval."
        )
    else:
        status = "GREEN"
        owner_need = "none"
        brief = "Support triage is GREEN. The local ticket source exists and has no open tickets."

    payload.update(
        {
            "status": status,
            "owner_need": owner_need,
            "brief": brief,
            "metrics": {
                "ticket_count": len(triaged),
                "draft_count": draft_count,
                "escalation_count": escalation_count,
            },
            "tickets": triaged,
            "sources": [str(source_rel).replace("\\", "/")],
        }
    )
    _write_outputs(root_path, payload, markdown_rel, json_rel)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a support-triage shadow-mode artifact.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    print(json.dumps(run_support_triage(root=Path(args.root)), indent=2))


if __name__ == "__main__":
    main()

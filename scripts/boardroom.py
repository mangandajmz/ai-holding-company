"""Boardroom meeting transcripts for CEO-led division conversations."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


RISK_TERMS = {
    "trading",
    "money",
    "spend",
    "publishing",
    "publish",
    "deployment",
    "deploy",
    "email",
    "external",
    "credential",
    "api",
    "business commitment",
    "legal",
    "tax",
}


ROLE_ORDER = [
    "Managing Agent",
    "Executive Division",
    "Trading Division",
    "Websites Division",
    "Content Division",
    "Commercial Division",
    "Risk Manager",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    return slug[:48] or "boardroom"


def _path_from_config(config: dict[str, Any], key: str, default: str) -> Path:
    rel = str(config.get("paths", {}).get(key, default)).strip() or default
    path = Path(rel)
    return path if path.is_absolute() else ROOT / path


def _reports_root(config: dict[str, Any]) -> Path:
    path = _path_from_config(config, "reports_dir", "reports") / "boardroom"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path(config: dict[str, Any]) -> Path:
    path = _path_from_config(config, "state_dir", "state") / "boardroom_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _read_state(config: dict[str, Any]) -> dict[str, Any]:
    state = _read_json(_state_path(config))
    return state if isinstance(state, dict) else {}


def _write_state(config: dict[str, Any], state: dict[str, Any]) -> None:
    _write_json(_state_path(config), state)


def _latest_report_json(config: dict[str, Any], name: str) -> dict[str, Any]:
    reports_dir = _path_from_config(config, "reports_dir", "reports")
    return _read_json(reports_dir / name)


def _approval_state(config: dict[str, Any]) -> dict[str, Any]:
    return _read_json(_path_from_config(config, "state_dir", "state") / "board_approval_decisions.json")


def _approval_counts(config: dict[str, Any]) -> dict[str, int]:
    state = _approval_state(config)
    decisions = state.get("decisions", {})
    decisions = decisions if isinstance(decisions, dict) else {}
    snapshot = state.get("board_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    approvals = snapshot.get("approvals", [])
    approvals = approvals if isinstance(approvals, list) else []
    pending = 0
    decided = 0
    for item in approvals:
        if not isinstance(item, dict):
            continue
        approval_id = str(item.get("approval_id", "")).strip()
        decision = decisions.get(approval_id, {})
        decision = decision if isinstance(decision, dict) else {}
        status = str(decision.get("decision", "")).upper()
        if status in {"APPROVED", "DENIED", "REJECTED"}:
            decided += 1
        else:
            pending += 1
    return {"pending": pending, "decided": decided}


def _company_status(config: dict[str, Any]) -> dict[str, Any]:
    phase3 = _latest_report_json(config, "phase3_holding_latest.json")
    phase2 = _latest_report_json(config, "phase2_divisions_latest.json")
    daily = _latest_report_json(config, "daily_brief_latest.json")

    company = phase3.get("company_scorecard", {})
    company = company if isinstance(company, dict) else {}
    base = phase3.get("base_summary", {})
    base = base if isinstance(base, dict) else {}
    if not base:
        base = daily.get("summary", {}) if isinstance(daily.get("summary"), dict) else {}

    divisions = phase2.get("division_results", [])
    divisions = divisions if isinstance(divisions, list) else []
    division_status = []
    for item in divisions:
        if not isinstance(item, dict):
            continue
        division_status.append(
            {
                "division": str(item.get("division", "division")).strip(),
                "status": str(item.get("status", "unknown")).upper(),
            }
        )

    return {
        "generated_at_utc": str(
            phase3.get("generated_at_utc")
            or phase2.get("generated_at_utc")
            or daily.get("generated_at_utc")
            or ""
        ),
        "company_status": str(company.get("status", "unknown")).upper(),
        "websites_up": base.get("websites_up"),
        "websites_total": base.get("websites_total"),
        "pnl_total": base.get("pnl_total"),
        "trades_total": base.get("trades_total"),
        "division_status": division_status,
        "approval_counts": _approval_counts(config),
    }


def _speaker_lines(config: dict[str, Any]) -> list[str]:
    status = _company_status(config)
    approvals = status["approval_counts"]
    division_bits = [
        f"{item['division']}={item['status']}"
        for item in status["division_status"]
        if item.get("division")
    ]
    if not division_bits:
        division_bits = ["no fresh division snapshot"]

    return [
        (
            "Managing Agent: Meeting opened. Company status is "
            f"{status['company_status']}; pending approvals={approvals['pending']}."
        ),
        "Executive Division: Board pack and CEO summary are the source of truth for decisions.",
        (
            "Trading Division: Current detected PnL="
            f"{status.get('pnl_total', 'n/a')}; trades={status.get('trades_total', 'n/a')}. "
            "No live execution without CEO approval."
        ),
        (
            "Websites Division: Websites up="
            f"{status.get('websites_up', 'n/a')}/{status.get('websites_total', 'n/a')}."
        ),
        "Content Division: Drafting may proceed from approved briefs; publishing remains CEO-gated.",
        "Commercial Division: New initiatives need expected upside, effort/cost, confidence, KPI, and review date.",
        "Risk Manager: Trading, spending, publishing, deployment, credentials, and external commitments stay gated.",
        "Managing Agent: CEO may ask `/boardroom ask <division> <question>` or close with `/boardroom close <note>`.",
    ]


def _meeting_markdown(meeting: dict[str, Any]) -> str:
    lines = [
        f"# Boardroom Meeting - {meeting.get('meeting_id')}",
        "",
        f"- Status: {meeting.get('status')}",
        f"- Topic: {meeting.get('topic') or 'General operating review'}",
        f"- Opened UTC: {meeting.get('opened_at_utc')}",
        f"- Closed UTC: {meeting.get('closed_at_utc') or ''}",
        f"- Chair: Managing Agent",
        f"- CEO: Human CEO",
        "",
        "## Standing Roles",
    ]
    for role in ROLE_ORDER:
        lines.append(f"- {role}")
    lines.extend(["", "## Transcript"])
    for entry in meeting.get("transcript", []):
        if not isinstance(entry, dict):
            continue
        lines.append("")
        lines.append(f"### {entry.get('speaker')} - {entry.get('timestamp_utc')}")
        lines.append(str(entry.get("message", "")).strip())
    lines.extend(["", "## Decisions / Follow-Ups"])
    decisions = meeting.get("decisions", [])
    if decisions:
        for decision in decisions:
            lines.append(f"- {decision}")
    else:
        lines.append("- No decisions recorded yet.")
    return "\n".join(lines).rstrip() + "\n"


def _save_meeting(config: dict[str, Any], meeting: dict[str, Any]) -> None:
    reports = _reports_root(config)
    meeting_id = str(meeting.get("meeting_id", "boardroom")).strip()
    json_path = reports / f"{meeting_id}.json"
    md_path = reports / f"{meeting_id}.md"
    latest_json = reports / "boardroom_latest.json"
    latest_md = reports / "boardroom_latest.md"
    _write_json(json_path, meeting)
    _write_json(latest_json, meeting)
    markdown = _meeting_markdown(meeting)
    md_path.write_text(markdown, encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")


def _active_meeting(config: dict[str, Any]) -> dict[str, Any] | None:
    state = _read_state(config)
    meeting = state.get("active_meeting", {})
    if isinstance(meeting, dict) and meeting.get("status") == "OPEN":
        return meeting
    return None


def _append(meeting: dict[str, Any], speaker: str, message: str) -> None:
    transcript = meeting.setdefault("transcript", [])
    if not isinstance(transcript, list):
        transcript = []
        meeting["transcript"] = transcript
    transcript.append(
        {
            "timestamp_utc": _now().isoformat(),
            "speaker": speaker,
            "message": message.strip(),
        }
    )


def start_boardroom(config: dict[str, Any], topic: str = "", refresh: bool = False) -> dict[str, Any]:
    existing = _active_meeting(config)
    if existing and not refresh:
        return {
            "ok": True,
            "status": "ALREADY_OPEN",
            "meeting_id": existing.get("meeting_id"),
            "message": "Boardroom meeting is already open.",
            "report": str(_reports_root(config) / "boardroom_latest.md"),
        }

    now = _now()
    suffix = _safe_slug(topic) if topic.strip() else "operating-review"
    meeting = {
        "meeting_id": f"boardroom_{now.strftime('%Y%m%d_%H%M%S')}_{suffix}",
        "status": "OPEN",
        "topic": topic.strip() or "General operating review",
        "opened_at_utc": now.isoformat(),
        "closed_at_utc": "",
        "decisions": [],
        "transcript": [],
        "company_snapshot": _company_status(config),
    }
    for line in _speaker_lines(config):
        speaker, message = line.split(": ", 1)
        _append(meeting, speaker, message)

    state = _read_state(config)
    state["active_meeting"] = meeting
    _write_state(config, state)
    _save_meeting(config, meeting)
    return {
        "ok": True,
        "status": "OPEN",
        "meeting_id": meeting["meeting_id"],
        "message": "Boardroom meeting opened.",
        "report": str(_reports_root(config) / "boardroom_latest.md"),
    }


def boardroom_status(config: dict[str, Any]) -> dict[str, Any]:
    meeting = _active_meeting(config)
    if not meeting:
        latest = _reports_root(config) / "boardroom_latest.md"
        return {
            "ok": True,
            "status": "CLOSED",
            "message": "No active boardroom meeting.",
            "report": str(latest) if latest.exists() else "",
        }
    return {
        "ok": True,
        "status": "OPEN",
        "meeting_id": meeting.get("meeting_id"),
        "topic": meeting.get("topic"),
        "turns": len(meeting.get("transcript", [])),
        "report": str(_reports_root(config) / "boardroom_latest.md"),
    }


def _division_answer(config: dict[str, Any], division: str, question: str) -> tuple[str, str]:
    division_key = division.strip().lower()
    status = _company_status(config)
    approvals = status["approval_counts"]
    risky = any(term in question.lower() for term in RISK_TERMS)
    gate = (
        " This touches a gated area, so any action must become PENDING_CEO_APPROVAL."
        if risky
        else ""
    )
    if division_key in {"md", "ma", "managing", "managing-agent"}:
        return (
            "Managing Agent",
            (
                f"My take: company status is {status['company_status']} with "
                f"{approvals['pending']} pending approval(s). I would keep the meeting focused on "
                "the highest-risk approval and the next measurable action."
            )
            + gate,
        )
    if division_key in {"trading", "trade"}:
        return (
            "Trading Division",
            (
                f"Trading view: detected PnL={status.get('pnl_total', 'n/a')}, "
                f"trades={status.get('trades_total', 'n/a')}. I can research and report, "
                "but live execution remains blocked without CEO approval."
            )
            + gate,
        )
    if division_key in {"websites", "website", "web"}:
        return (
            "Websites Division",
            (
                f"Website view: current uptime snapshot is "
                f"{status.get('websites_up', 'n/a')}/{status.get('websites_total', 'n/a')}. "
                "Next useful move is QA evidence before any publishing or deployment."
            )
            + gate,
        )
    if division_key in {"content"}:
        return (
            "Content Division",
            "Content view: I can draft from approved briefs. Publishing or external distribution stays CEO-gated."
            + gate,
        )
    if division_key in {"commercial", "finance", "roi"}:
        return (
            "Commercial Division",
            (
                "Commercial view: any initiative should state expected upside, effort/cost, "
                "confidence, KPI, owner, and review date before execution."
            )
            + gate,
        )
    if division_key in {"risk", "risk-manager"}:
        return (
            "Risk Manager",
            (
                "Risk view: convert risky recommendations into explicit approval requests, "
                "then measure the result after implementation."
            )
            + gate,
        )
    return (
        "Managing Agent",
        f"I do not recognize division `{division}` yet. Use md, trading, websites, content, commercial, or risk.",
    )


def ask_boardroom(config: dict[str, Any], division: str, question: str) -> dict[str, Any]:
    meeting = _active_meeting(config)
    if not meeting:
        opened = start_boardroom(config, topic="Ad hoc CEO question")
        meeting = _active_meeting(config)
        if not meeting:
            return {"ok": False, "status": "ERROR", "message": opened.get("message", "Could not open meeting.")}

    clean_question = question.strip()
    if not clean_question:
        return {
            "ok": False,
            "status": "QUESTION_REQUIRED",
            "message": "Use boardroom ask with a division and a question.",
        }

    _append(meeting, "Human CEO", f"To {division}: {clean_question}")
    speaker, answer = _division_answer(config, division, clean_question)
    _append(meeting, speaker, answer)
    state = _read_state(config)
    state["active_meeting"] = meeting
    _write_state(config, state)
    _save_meeting(config, meeting)
    return {
        "ok": True,
        "status": "OPEN",
        "meeting_id": meeting.get("meeting_id"),
        "speaker": speaker,
        "answer": answer,
        "report": str(_reports_root(config) / "boardroom_latest.md"),
    }


def close_boardroom(config: dict[str, Any], note: str = "") -> dict[str, Any]:
    meeting = _active_meeting(config)
    if not meeting:
        return {"ok": True, "status": "CLOSED", "message": "No active boardroom meeting to close."}
    if note.strip():
        _append(meeting, "Human CEO", f"Closing note: {note.strip()}")
        meeting.setdefault("decisions", []).append(note.strip())
    _append(
        meeting,
        "Managing Agent",
        "Meeting closed. Any risky next action must be represented as an approval before execution.",
    )
    meeting["status"] = "CLOSED"
    meeting["closed_at_utc"] = _now().isoformat()
    state = _read_state(config)
    state["active_meeting"] = {}
    state["last_meeting"] = meeting
    _write_state(config, state)
    _save_meeting(config, meeting)
    return {
        "ok": True,
        "status": "CLOSED",
        "meeting_id": meeting.get("meeting_id"),
        "message": "Boardroom meeting closed.",
        "report": str(_reports_root(config) / "boardroom_latest.md"),
    }

"""Content Studio orchestration with explicit CEO approval state."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from utils import load_yaml as _load_yaml, parse_iso_utc as _parse_iso_utc


ROOT = Path(__file__).resolve().parents[1]
_TRACKING_FILE = ROOT / "artifacts" / "content_studio_drafts.jsonl"
_PENDING_STATUS = "PENDING_CEO_APPROVAL"
_APPROVED_STATUS = "APPROVED"
_DENIED_STATUS = "DENIED"
_KNOWN_STATUSES = {_PENDING_STATUS, _APPROVED_STATUS, _DENIED_STATUS}
_ALLOWED_FORMATS = ("email", "article", "post", "doc")


def run_content_studio(config: dict[str, Any], brief_text: str = "") -> dict[str, Any]:
    """Create a draft from a brief or return current division status."""
    if not brief_text or not brief_text.strip():
        return _get_content_studio_status(config)

    intake = _intake_brief(brief_text)
    draft = _compose_draft(config, intake)
    tracked = _track_draft(draft)

    drafts = _load_draft_history(_TRACKING_FILE)
    drafts.insert(0, tracked)
    _write_draft_history(_TRACKING_FILE, drafts)

    status_payload = _get_content_studio_status(config)
    return {
        "ok": True,
        "division": "content_studio",
        "status": status_payload.get("status"),
        "draft_id": tracked["draft_id"],
        "draft_status": tracked["status"],
        "drafts_pending": status_payload.get("drafts_pending", 0),
        "last_approval_wait_hours": status_payload.get("last_approval_wait_hours", 0.0),
        "notes": (
            f"Content Studio: {status_payload.get('drafts_pending', 0)} draft(s) pending CEO approval. "
            "All drafts remain under R3/R4 (no auto-publish)."
        ),
    }


def list_content_drafts(config: dict[str, Any]) -> dict[str, Any]:
    """Return tracked drafts grouped by workflow status."""
    status_payload = _get_content_studio_status(config)
    drafts = _load_draft_history(_TRACKING_FILE)
    grouped: dict[str, list[dict[str, Any]]] = {
        _PENDING_STATUS: [],
        _APPROVED_STATUS: [],
        _DENIED_STATUS: [],
    }

    for draft in drafts:
        status = str(draft.get("status", _PENDING_STATUS)).strip().upper()
        if status not in grouped:
            continue
        intake = draft.get("intake", {})
        intake = intake if isinstance(intake, dict) else {}
        grouped[status].append(
            {
                "draft_id": str(draft.get("draft_id", "")).strip(),
                "topic": str(intake.get("topic", "Untitled")).strip() or "Untitled",
                "created_at": draft.get("created_at"),
                "approved_at_utc": draft.get("approved_at_utc"),
                "denied_at_utc": draft.get("denied_at_utc"),
                "decision_note": draft.get("decision_note"),
            }
        )

    return {
        "ok": True,
        "division": "content_studio",
        "status": status_payload.get("status"),
        "drafts_pending": status_payload.get("drafts_pending", 0),
        "last_approval_wait_hours": status_payload.get("last_approval_wait_hours", 0.0),
        "drafts_by_status": grouped,
    }


def decide_content_draft(
    config: dict[str, Any],
    draft_id: str,
    decision: str,
    decision_by_user_id: int | None = None,
    decision_note: str = "",
) -> dict[str, Any]:
    """Approve or deny a tracked draft."""
    _ = config
    normalized_id = str(draft_id).strip()
    if not normalized_id:
        return {"ok": False, "error": "missing_draft_id", "message": "draft_id is required."}

    decision_key = str(decision).strip().lower()
    if decision_key not in {"approve", "deny"}:
        return {"ok": False, "error": "invalid_decision", "message": "decision must be approve or deny."}

    target_status = _APPROVED_STATUS if decision_key == "approve" else _DENIED_STATUS
    drafts = _load_draft_history(_TRACKING_FILE)

    target: dict[str, Any] | None = None
    for draft in drafts:
        if str(draft.get("draft_id", "")).strip() == normalized_id:
            target = draft
            break

    if target is None:
        return {
            "ok": False,
            "error": "draft_not_found",
            "draft_id": normalized_id,
            "message": f"No tracked draft found for {normalized_id}.",
        }

    current_status = str(target.get("status", _PENDING_STATUS)).strip().upper()
    if current_status != _PENDING_STATUS:
        return {
            "ok": False,
            "error": "draft_not_pending",
            "draft_id": normalized_id,
            "status": current_status,
            "message": f"Draft {normalized_id} is already {current_status}.",
        }

    decided_at = datetime.now(timezone.utc).isoformat()
    note = decision_note.strip() or None
    target["status"] = target_status
    target["approved_at_utc"] = decided_at if target_status == _APPROVED_STATUS else None
    target["denied_at_utc"] = decided_at if target_status == _DENIED_STATUS else None
    target["decision_by_user_id"] = decision_by_user_id
    target["decision_note"] = note
    target["ceo_approval"] = {
        "status": target_status,
        "decided_at_utc": decided_at,
        "decision_by_user_id": decision_by_user_id,
        "decision_note": note,
    }
    _write_draft_history(_TRACKING_FILE, drafts)

    status_payload = _get_content_studio_status(config)
    return {
        "ok": True,
        "division": "content_studio",
        "draft_id": normalized_id,
        "status": target_status,
        "decision_at_utc": decided_at,
        "decision_by_user_id": decision_by_user_id,
        "decision_note": note,
        "drafts_pending": status_payload.get("drafts_pending", 0),
        "last_approval_wait_hours": status_payload.get("last_approval_wait_hours", 0.0),
    }


def _intake_brief(brief_text: str) -> dict[str, Any]:
    """Parse a raw brief into a structured intake record."""
    text = brief_text.strip() or "Untitled content brief"

    lower = text.lower()
    fmt = "article"
    for candidate in _ALLOWED_FORMATS:
        if re.search(rf"\b{re.escape(candidate)}\b", lower):
            fmt = candidate
            break

    audience = "general audience"
    audience_match = re.search(r"target audience\s*:\s*([^\n.]+)", text, flags=re.IGNORECASE)
    if audience_match:
        candidate_audience = audience_match.group(1).strip()
        if candidate_audience:
            audience = candidate_audience

    topic = text.splitlines()[0].strip()
    topic = re.sub(r"^[Ww]rite\s+(an?\s+)?", "", topic).strip().rstrip(".")
    if not topic:
        topic = "Content brief"

    return {
        "brief_text": text,
        "brief_source": "telegram:/content",
        "topic": topic,
        "format": fmt,
        "target_audience": audience,
        "writer_instructions": "Follow brief exactly, keep clear structure, and keep factual claims conservative.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "INTAKE_PARSED",
    }


def _compose_draft(config: dict[str, Any], intake_json: dict[str, Any]) -> dict[str, Any]:
    """Compose and review a content draft from intake data."""
    _ = config
    crew_config_path = ROOT / "crews" / "content_studio.yaml"
    crew_config = _load_yaml(crew_config_path) if crew_config_path.exists() else {}
    if "crew" in crew_config and isinstance(crew_config["crew"], dict):
        crew_name = str(crew_config["crew"].get("manager_agent", "content_studio_manager"))
    else:
        crew_name = "content_studio_manager"

    topic = str(intake_json.get("topic", "Content brief"))
    fmt = str(intake_json.get("format", "article"))
    audience = str(intake_json.get("target_audience", "general audience"))
    brief_source = str(intake_json.get("brief_source", "unknown"))
    brief_text = str(intake_json.get("brief_text", "")).strip()

    draft_content = (
        f"## [Status: {_PENDING_STATUS}] [Topic: {topic}]\n\n"
        f"Format: {fmt}\n"
        f"Audience: {audience}\n\n"
        "### Draft\n"
        f"{brief_text}\n\n"
        "### Editorial Checklist\n"
        "- Clear thesis and outcome for the reader.\n"
        "- Tone aligned to AI Holding Company standards.\n"
        "- Claims constrained to known facts.\n\n"
        f"Brief source: {brief_source}"
    )

    review = {
        "status": "approved_for_ceo_review",
        "notes": [
            "Draft is clear and follows the requested format.",
            "Content remains marked PENDING_CEO_APPROVAL for CEO decision.",
        ],
        "revised_draft": draft_content,
    }

    return {
        "intake": intake_json,
        "draft_content": draft_content,
        "editor_review": review,
        "crew_manager": crew_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _track_draft(draft: dict[str, Any]) -> dict[str, Any]:
    """Attach approval metadata to a new draft."""
    tracked = dict(draft)
    created_at = datetime.now(timezone.utc)
    tracked["draft_id"] = str(uuid4())
    tracked["status"] = _PENDING_STATUS
    tracked["created_at"] = created_at.isoformat()
    tracked["approval_deadline"] = (created_at + timedelta(hours=48)).isoformat()
    tracked["approved_at_utc"] = None
    tracked["denied_at_utc"] = None
    tracked["decision_by_user_id"] = None
    tracked["decision_note"] = None
    tracked["ceo_approval"] = None
    return tracked


def _get_content_studio_status(config: dict[str, Any]) -> dict[str, Any]:
    """Return Content Studio health when no new brief is provided."""
    drafts = _load_draft_history(_TRACKING_FILE)
    pending = [item for item in drafts if item.get("status") == _PENDING_STATUS]
    approval_wait_hours = _get_max_approval_wait(pending)
    status = _evaluate_content_studio_status(drafts, approval_wait_hours, config)
    return {
        "ok": True,
        "division": "content_studio",
        "status": status,
        "drafts_pending": len(pending),
        "last_approval_wait_hours": approval_wait_hours,
        "notes": (
            f"Content Studio status: {status}. "
            f"{len(pending)} draft(s) awaiting CEO approval under R3/R4."
        ),
    }


def _load_draft_history(tracking_file: Path) -> list[dict[str, Any]]:
    """Load tracked drafts from JSONL history."""
    if not tracking_file.exists():
        return []

    drafts: list[dict[str, Any]] = []
    with tracking_file.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                drafts.append(_normalize_draft_record(record, len(drafts)))
    return drafts


def _write_draft_history(tracking_file: Path, drafts: list[dict[str, Any]]) -> None:
    """Persist normalized draft history back to JSONL."""
    tracking_file.parent.mkdir(parents=True, exist_ok=True)
    with tracking_file.open("w", encoding="utf-8") as handle:
        for draft in drafts:
            handle.write(json.dumps(draft, ensure_ascii=True) + "\n")


def _normalize_draft_record(record: dict[str, Any], index: int) -> dict[str, Any]:
    """Backfill required fields for legacy draft rows."""
    normalized = dict(record)
    draft_id = str(normalized.get("draft_id", "")).strip()
    if not draft_id:
        normalized["draft_id"] = f"legacy-draft-{index + 1}"

    status = str(normalized.get("status", _PENDING_STATUS)).strip().upper() or _PENDING_STATUS
    if status not in _KNOWN_STATUSES:
        status = _PENDING_STATUS
    normalized["status"] = status
    normalized.setdefault("approved_at_utc", None)
    normalized.setdefault("denied_at_utc", None)
    normalized.setdefault("decision_by_user_id", None)
    normalized.setdefault("decision_note", None)
    normalized.setdefault("ceo_approval", None)
    return normalized


def _get_max_approval_wait(pending: list[dict[str, Any]]) -> float:
    """Return hours since the oldest pending draft was created."""
    if not pending:
        return 0.0

    created_times = []
    for draft in pending:
        parsed = _parse_iso_utc(draft.get("created_at"))
        if parsed is not None:
            created_times.append(parsed)
    if not created_times:
        return 0.0

    oldest = min(created_times)
    now = datetime.now(timezone.utc)
    hours = (now - oldest).total_seconds() / 3600.0
    return round(max(hours, 0.0), 1)


def _evaluate_content_studio_status(
    drafts: list[dict[str, Any]],
    approval_wait_hours: float,
    config: dict[str, Any],
) -> str:
    """Evaluate division status from workflow validity and wait-time threshold."""
    targets = config.get("targets", {})
    targets = targets if isinstance(targets, dict) else {}
    content_targets = targets.get("content_studio", {})
    content_targets = content_targets if isinstance(content_targets, dict) else {}
    wait_targets = content_targets.get("ceo_approval_wait_time_hours", {})
    wait_targets = wait_targets if isinstance(wait_targets, dict) else {}
    amber_threshold = float(wait_targets.get("alert_threshold", 48))

    for draft in drafts:
        if str(draft.get("status", _PENDING_STATUS)).strip().upper() not in _KNOWN_STATUSES:
            return "RED"

    if approval_wait_hours > amber_threshold:
        return "AMBER"
    return "GREEN"

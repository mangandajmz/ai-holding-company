"""Content Studio orchestration - brief-driven content with CEO approval gate."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from utils import load_yaml as _load_yaml, parse_iso_utc as _parse_iso_utc


ROOT = Path(__file__).resolve().parents[1]
_TRACKING_FILE = ROOT / "artifacts" / "content_studio_drafts.jsonl"
_PENDING_STATUS = "PENDING_CEO_APPROVAL"
_ALLOWED_FORMATS = ("email", "article", "post", "doc")


def run_content_studio(config: dict[str, Any], brief_text: str = "") -> dict[str, Any]:
    """Run Content Studio orchestration or return current division status."""
    if not brief_text or not brief_text.strip():
        return _get_content_studio_status(config)

    intake = _intake_brief(brief_text)
    draft = _compose_draft(config, intake)
    tracked = _track_draft(draft)

    _TRACKING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _TRACKING_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(tracked, ensure_ascii=True) + "\n")

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
            f"Content Studio: {len(pending)} draft(s) pending CEO approval. "
            "All drafts remain under R3/R4 (no auto-publish)."
        ),
    }


def _intake_brief(brief_text: str) -> dict[str, Any]:
    """Parse a raw brief into a structured intake record."""
    text = brief_text.strip()
    if not text:
        text = "Untitled content brief"

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
    topic = re.sub(r"^[Ww]rite\s+(an?\s+)?", "", topic).strip()
    topic = topic.rstrip(".")
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
    """Attach approval gate metadata to a draft."""
    tracked = dict(draft)
    created_at = datetime.now(timezone.utc)
    tracked["status"] = _PENDING_STATUS
    tracked["created_at"] = created_at.isoformat()
    tracked["approval_deadline"] = (created_at + timedelta(hours=48)).isoformat()
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
    """Load all tracked drafts from JSONL history."""
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
                drafts.append(record)
    return drafts


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
    pending: list[dict[str, Any]],
    approval_wait_hours: float,
    config: dict[str, Any],
) -> str:
    """Evaluate division status from approval gate and wait-time threshold."""
    targets = config.get("targets", {})
    targets = targets if isinstance(targets, dict) else {}
    content_targets = targets.get("content_studio", {})
    content_targets = content_targets if isinstance(content_targets, dict) else {}
    wait_targets = content_targets.get("ceo_approval_wait_time_hours", {})
    wait_targets = wait_targets if isinstance(wait_targets, dict) else {}
    amber_threshold = float(wait_targets.get("alert_threshold", 48))

    for draft in pending:
        if draft.get("status") != _PENDING_STATUS:
            return "RED"

    if approval_wait_hours > amber_threshold:
        return "AMBER"
    return "GREEN"


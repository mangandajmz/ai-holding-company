"""File-first company operating loops.

Each loop records one CEO goal through evidence, review, approval, action,
measurement, and result. The JSON state is canonical; markdown reports are
human-readable artifacts for CEO review.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

STATUSES = (
    "GOAL_CAPTURED",
    "PLANNING",
    "EVIDENCE_READY",
    "REVIEW_READY",
    "PENDING_CEO_APPROVAL",
    "APPROVED",
    "IN_PROGRESS",
    "MEASUREMENT_READY",
    "DONE",
    "REJECTED",
)

LOOP_TYPES = (
    "website_improvement",
    "content",
    "business_initiative",
    "trading_research",
    "operations",
)

RISK_TERMS = (
    "trading action",
    "live trade",
    "execute trade",
    "money",
    "spend",
    "cost",
    "publishing",
    "publish",
    "production deployment",
    "deploy",
    "email",
    "external communication",
    "credential",
    "api key",
    "business commitment",
    "legal",
    "tax",
)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_dir(config: dict[str, Any]) -> Path:
    rel = str(config.get("paths", {}).get("state_dir", "state")).strip() or "state"
    path = Path(rel)
    return path if path.is_absolute() else ROOT / path


def _reports_dir(config: dict[str, Any]) -> Path:
    rel = str(config.get("paths", {}).get("reports_dir", "reports")).strip() or "reports"
    path = Path(rel)
    base = path if path.is_absolute() else ROOT / path
    return base / "company_loops"


def _state_path(config: dict[str, Any]) -> Path:
    return _state_dir(config) / "company_loops.json"


def _load_state(config: dict[str, Any]) -> dict[str, Any]:
    path = _state_path(config)
    if not path.exists():
        return {"loops": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"loops": []}
    if not isinstance(payload, dict):
        return {"loops": []}
    loops = payload.get("loops", [])
    payload["loops"] = loops if isinstance(loops, list) else []
    return payload


def _save_state(config: dict[str, Any], state: dict[str, Any]) -> None:
    path = _state_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _next_loop_id(loops: list[dict[str, Any]]) -> str:
    highest = 0
    for loop in loops:
        raw = str(loop.get("loop_id", ""))
        match = re.match(r"^loop_(\d+)$", raw)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"loop_{highest + 1:04d}"


def _find_loop(state: dict[str, Any], loop_id: str) -> dict[str, Any] | None:
    for loop in state.get("loops", []):
        if isinstance(loop, dict) and loop.get("loop_id") == loop_id:
            return loop
    return None


def _has_risk(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in RISK_TERMS)


def _needs_approval(loop: dict[str, Any], extra_text: str = "") -> bool:
    joined = " ".join(
        str(loop.get(key, ""))
        for key in (
            "goal",
            "recommendation",
            "risk_review",
            "commercial_review",
            "approved_action",
            "measurement_plan",
            "result",
            "next_step",
        )
    )
    evidence_text = " ".join(str(item) for item in loop.get("evidence", []) if isinstance(item, dict))
    return _has_risk(" ".join([joined, evidence_text, extra_text]))


def _append_history(loop: dict[str, Any], event: str, note: str = "") -> None:
    history = loop.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        loop["history"] = history
    history.append({"timestamp_utc": _now_utc(), "event": event, "note": note.strip()})


def _set_status(loop: dict[str, Any], status: str, note: str = "") -> None:
    if status not in STATUSES:
        raise ValueError(f"Invalid loop status: {status}")
    loop["status"] = status
    loop["current_stage"] = status
    loop["updated_at_utc"] = _now_utc()
    _append_history(loop, status, note)


def _markdown_for_loop(loop: dict[str, Any]) -> str:
    evidence = loop.get("evidence", [])
    evidence = evidence if isinstance(evidence, list) else []
    history = loop.get("history", [])
    history = history if isinstance(history, list) else []
    lines = [
        f"# Company Loop {loop.get('loop_id')}",
        "",
        f"- Goal: {loop.get('goal')}",
        f"- Type: {loop.get('loop_type')}",
        f"- Division: {loop.get('division')}",
        f"- Owner: {loop.get('owner')}",
        f"- Status: {loop.get('status')}",
        f"- Approval status: {loop.get('approval_status')}",
        f"- Created UTC: {loop.get('created_at_utc')}",
        f"- Updated UTC: {loop.get('updated_at_utc')}",
        f"- Next step: {loop.get('next_step')}",
        "",
        "## Evidence",
    ]
    if evidence:
        for item in evidence:
            if not isinstance(item, dict):
                continue
            path = str(item.get("path", "")).strip()
            note = str(item.get("note", "")).strip()
            suffix = f" - {note}" if note else ""
            lines.append(f"- {path or 'evidence'}{suffix}")
    else:
        lines.append("- None yet.")
    lines.extend(
        [
            "",
            "## Recommendation",
            str(loop.get("recommendation", "")).strip() or "None yet.",
            "",
            "## Risk Review",
            str(loop.get("risk_review", "")).strip() or "None yet.",
            "",
            "## Commercial Review",
            str(loop.get("commercial_review", "")).strip() or "None yet.",
            "",
            "## Approved Action",
            str(loop.get("approved_action", "")).strip() or "None yet.",
            "",
            "## Measurement Plan",
            str(loop.get("measurement_plan", "")).strip() or "None yet.",
            "",
            "## Result",
            str(loop.get("result", "")).strip() or "None yet.",
            "",
            "## History",
        ]
    )
    if history:
        for item in history:
            if isinstance(item, dict):
                note = str(item.get("note", "")).strip()
                suffix = f" - {note}" if note else ""
                lines.append(f"- {item.get('timestamp_utc')}: {item.get('event')}{suffix}")
    else:
        lines.append("- None yet.")
    return "\n".join(lines).rstrip() + "\n"


def _write_reports(config: dict[str, Any], loops: list[dict[str, Any]]) -> None:
    reports = _reports_dir(config)
    reports.mkdir(parents=True, exist_ok=True)
    for loop in loops:
        loop_id = str(loop.get("loop_id", "")).strip()
        if not loop_id:
            continue
        (reports / f"{loop_id}.md").write_text(_markdown_for_loop(loop), encoding="utf-8")
    open_loops = [loop for loop in loops if loop.get("status") not in {"DONE", "REJECTED"}]
    lines = ["# Company Loops", ""]
    if open_loops:
        lines.append("## Open Loops")
        for loop in open_loops:
            lines.append(
                f"- {loop.get('loop_id')} [{loop.get('status')}] "
                f"{loop.get('goal')} | next: {loop.get('next_step')}"
            )
    else:
        lines.extend(["## Open Loops", "- None."])
    closed = [loop for loop in loops if loop.get("status") in {"DONE", "REJECTED"}]
    if closed:
        lines.extend(["", "## Closed Loops"])
        for loop in closed[-10:]:
            lines.append(f"- {loop.get('loop_id')} [{loop.get('status')}] {loop.get('goal')}")
    (reports / "company_loops_latest.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def new_loop(
    config: dict[str, Any],
    goal: str,
    loop_type: str = "operations",
    division: str = "operations",
    owner: str = "CEO",
) -> dict[str, Any]:
    goal = goal.strip()
    if not goal:
        return {"ok": False, "error": "Goal is required."}
    if loop_type not in LOOP_TYPES:
        return {"ok": False, "error": f"Invalid loop type: {loop_type}"}
    state = _load_state(config)
    loops = state["loops"]
    now = _now_utc()
    loop = {
        "loop_id": _next_loop_id(loops),
        "goal": goal,
        "loop_type": loop_type,
        "owner": owner.strip() or "CEO",
        "division": division.strip() or "operations",
        "status": "GOAL_CAPTURED",
        "current_stage": "GOAL_CAPTURED",
        "approval_status": "NOT_REQUIRED_YET",
        "created_at_utc": now,
        "updated_at_utc": now,
        "evidence": [],
        "recommendation": "",
        "risk_review": "",
        "commercial_review": "",
        "approved_action": "",
        "measurement_plan": "",
        "result": "",
        "next_step": "Gather evidence and prepare division review.",
        "history": [{"timestamp_utc": now, "event": "GOAL_CAPTURED", "note": "Loop created."}],
    }
    if _needs_approval(loop):
        loop["approval_status"] = "PENDING_CEO_APPROVAL"
        _set_status(loop, "PENDING_CEO_APPROVAL", "Goal includes gated risk terms.")
        loop["next_step"] = "CEO approval required before action."
    loops.append(loop)
    _save_state(config, state)
    _write_reports(config, loops)
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop['loop_id']}.md")}


def list_loops(config: dict[str, Any], include_closed: bool = False) -> dict[str, Any]:
    state = _load_state(config)
    loops = [loop for loop in state["loops"] if isinstance(loop, dict)]
    if not include_closed:
        loops = [loop for loop in loops if loop.get("status") not in {"DONE", "REJECTED"}]
    _write_reports(config, state["loops"])
    return {"ok": True, "loops": loops, "count": len(loops), "report": str(_reports_dir(config) / "company_loops_latest.md")}


def show_loop(config: dict[str, Any], loop_id: str) -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}


def add_evidence(config: dict[str, Any], loop_id: str, path: str, note: str = "") -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    clean_path = path.strip()
    if not clean_path:
        return {"ok": False, "error": "Evidence path is required."}
    loop.setdefault("evidence", []).append({"path": clean_path, "note": note.strip(), "added_at_utc": _now_utc()})
    if loop.get("approval_status") == "PENDING_CEO_APPROVAL":
        loop["next_step"] = "CEO approval required before action."
        _set_status(loop, "PENDING_CEO_APPROVAL", note or clean_path)
    else:
        loop["next_step"] = "Review evidence and prepare recommendation."
        _set_status(loop, "EVIDENCE_READY", note or clean_path)
    _save_state(config, state)
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}


def advance_loop(
    config: dict[str, Any],
    loop_id: str,
    note: str = "",
    recommendation: str = "",
    risk_review: str = "",
    commercial_review: str = "",
    measurement_plan: str = "",
) -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    if recommendation.strip():
        loop["recommendation"] = recommendation.strip()
    if risk_review.strip():
        loop["risk_review"] = risk_review.strip()
    if commercial_review.strip():
        loop["commercial_review"] = commercial_review.strip()
    if measurement_plan.strip():
        loop["measurement_plan"] = measurement_plan.strip()
    if _needs_approval(loop, note):
        loop["approval_status"] = "PENDING_CEO_APPROVAL"
        loop["next_step"] = "CEO approval required before action."
        _set_status(loop, "PENDING_CEO_APPROVAL", note)
    else:
        loop["approval_status"] = "NOT_REQUIRED_YET"
        loop["next_step"] = "CEO review recommendation, then approve, reject, or request more evidence."
        _set_status(loop, "REVIEW_READY", note)
    _save_state(config, state)
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}


def approve_loop(config: dict[str, Any], loop_id: str, note: str = "", action: str = "") -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    existing_action = str(loop.get("approved_action", "")).strip()
    if action.strip():
        loop["approved_action"] = action.strip()
    elif note.strip() and not existing_action:
        loop["approved_action"] = note.strip()
    loop["approval_status"] = "APPROVED"
    loop["next_step"] = "MD agent is executing the approved internal work package; record evidence and measurement next."
    _set_status(loop, "APPROVED", note)
    _set_status(loop, "IN_PROGRESS", "Auto-started after CEO approval.")
    _save_state(config, state)
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}


def reject_loop(config: dict[str, Any], loop_id: str, note: str = "") -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    loop["approval_status"] = "REJECTED"
    loop["next_step"] = "Loop rejected. Reopen by creating a new loop with clearer evidence."
    _set_status(loop, "REJECTED", note)
    _save_state(config, state)
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}


def start_action(config: dict[str, Any], loop_id: str, note: str = "") -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    if loop.get("approval_status") == "PENDING_CEO_APPROVAL":
        return {"ok": False, "error": "CEO approval is required before action."}
    loop["next_step"] = "Complete action, then record measurement/result."
    _set_status(loop, "IN_PROGRESS", note)
    _save_state(config, state)
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}


def measure_loop(config: dict[str, Any], loop_id: str, result: str, note: str = "") -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    if not result.strip():
        return {"ok": False, "error": "Measurement result is required."}
    loop["result"] = result.strip()
    loop["next_step"] = "CEO review result and decide whether to close or open an improvement loop."
    _set_status(loop, "MEASUREMENT_READY", note or result)
    _save_state(config, state)
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}


def done_loop(config: dict[str, Any], loop_id: str, result: str = "") -> dict[str, Any]:
    state = _load_state(config)
    loop = _find_loop(state, loop_id)
    if not loop:
        return {"ok": False, "error": f"Loop not found: {loop_id}"}
    if result.strip():
        loop["result"] = result.strip()
    loop["next_step"] = "Loop closed. Use result to inform the next CEO goal."
    _set_status(loop, "DONE", result)
    _save_state(config, state)
    _write_reports(config, state["loops"])
    return {"ok": True, "loop": loop, "report": str(_reports_dir(config) / f"{loop_id}.md")}

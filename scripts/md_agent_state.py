"""MD Agent state: issue log and task log.

Issue log — tracks recurring anomalies with a day count so the CEO sees
"day 3 of MT5 stale" not just "MT5 stale" on each brief.

Task log — records CEO directions (log-only; execution tracking is Sprint 2).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ISSUE_LOG = ROOT / "state" / "md_issue_log.json"
DEFAULT_TASK_LOG = ROOT / "state" / "md_task_log.json"


# ── helpers ──────────────────────────────────────────────────────────────────


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime(_DATE_FMT)


def _days_since(iso: str) -> int:
    try:
        first = datetime.strptime(iso, _DATE_FMT).replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - first
        return max(0, delta.days)
    except (ValueError, TypeError):
        return 0


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


# ── issue log ─────────────────────────────────────────────────────────────────


def upsert_issue(
    key: str,
    description: str,
    log_path: Path = DEFAULT_ISSUE_LOG,
) -> dict[str, Any]:
    """Create or refresh an issue; return enriched record with day count."""
    records = _load(log_path)
    now = _now_utc()
    for rec in records:
        if rec.get("key") == key:
            if not rec.get("resolved", False):
                rec["last_seen"] = now
                rec["description"] = description
            else:
                # Issue was resolved but reappeared — re-open it.
                rec["resolved"] = False
                rec["first_seen"] = now
                rec["last_seen"] = now
                rec["description"] = description
            _save(log_path, records)
            rec["days"] = _days_since(rec["first_seen"])
            return rec
    new_rec: dict[str, Any] = {
        "key": key,
        "description": description,
        "first_seen": now,
        "last_seen": now,
        "resolved": False,
    }
    records.append(new_rec)
    _save(log_path, records)
    new_rec["days"] = 0
    return new_rec


def resolve_issue(key: str, log_path: Path = DEFAULT_ISSUE_LOG) -> bool:
    """Mark issue resolved. Returns True if the key was found."""
    records = _load(log_path)
    found = False
    for rec in records:
        if rec.get("key") == key and not rec.get("resolved", False):
            rec["resolved"] = True
            rec["resolved_at"] = _now_utc()
            found = True
    if found:
        _save(log_path, records)
    return found


def get_open_issues(log_path: Path = DEFAULT_ISSUE_LOG) -> list[dict[str, Any]]:
    """Return open issues sorted by age (oldest first), with day count added."""
    records = _load(log_path)
    open_issues = [r for r in records if not r.get("resolved", False)]
    for rec in open_issues:
        rec["days"] = _days_since(rec.get("first_seen", _now_utc()))
    return sorted(open_issues, key=lambda r: r.get("days", 0), reverse=True)


def prune_resolved(older_than_days: int = 7, log_path: Path = DEFAULT_ISSUE_LOG) -> int:
    """Remove resolved issues older than threshold. Returns count removed."""
    records = _load(log_path)
    before = len(records)
    cutoff = older_than_days * 86400
    now_ts = datetime.now(timezone.utc).timestamp()
    kept = []
    for rec in records:
        if not rec.get("resolved", False):
            kept.append(rec)
            continue
        resolved_at = rec.get("resolved_at", rec.get("last_seen", ""))
        try:
            ts = datetime.strptime(resolved_at, _DATE_FMT).replace(tzinfo=timezone.utc).timestamp()
            age = now_ts - ts
        except (ValueError, TypeError):
            kept.append(rec)
            continue
        if age < cutoff:
            kept.append(rec)
    _save(log_path, kept)
    return before - len(kept)


# ── task log ──────────────────────────────────────────────────────────────────


def log_task(
    command: str,
    source: str = "CEO",
    log_path: Path = DEFAULT_TASK_LOG,
) -> str:
    """Log a CEO direction as PENDING. Returns the task_id."""
    records = _load(log_path)
    task_id = f"task_{len(records) + 1:04d}"
    records.append(
        {
            "task_id": task_id,
            "command": command,
            "source": source,
            "status": "PENDING",
            "logged_at": _now_utc(),
            "updated_at": _now_utc(),
            "detail": None,
        }
    )
    _save(log_path, records)
    return task_id


def update_task(
    task_id: str,
    status: str,
    detail: str | None = None,
    log_path: Path = DEFAULT_TASK_LOG,
) -> bool:
    """Update task status. Returns True if task was found."""
    if status not in ("PENDING", "DONE", "FAILED"):
        raise ValueError(f"Invalid status: {status}")
    records = _load(log_path)
    for rec in records:
        if rec.get("task_id") == task_id:
            rec["status"] = status
            rec["updated_at"] = _now_utc()
            if detail is not None:
                rec["detail"] = detail
            _save(log_path, records)
            return True
    return False


def get_pending_tasks(log_path: Path = DEFAULT_TASK_LOG) -> list[dict[str, Any]]:
    """Return all PENDING tasks sorted by log time (oldest first)."""
    records = _load(log_path)
    return [r for r in records if r.get("status") == "PENDING"]


# ── initiative log ────────────────────────────────────────────────────────────

DEFAULT_INITIATIVE_LOG = ROOT / "state" / "md_initiative_log.json"

_INITIATIVE_STATUSES = ("PROPOSED", "APPROVED", "IN_PROGRESS", "DONE", "REJECTED")


def propose_initiative(
    title: str,
    problem: str,
    proposed_change: str,
    success_criteria: str,
    source: str = "md_agent",
    log_path: Path = DEFAULT_INITIATIVE_LOG,
) -> str:
    """Log a new initiative proposal. Returns initiative_id."""
    records = _load(log_path)
    init_id = f"init_{len(records) + 1:04d}"
    records.append(
        {
            "initiative_id": init_id,
            "title": title,
            "problem": problem,
            "proposed_change": proposed_change,
            "success_criteria": success_criteria,
            "source": source,
            "status": "PROPOSED",
            "proposed_at": _now_utc(),
            "updated_at": _now_utc(),
            "detail": None,
        }
    )
    _save(log_path, records)
    return init_id


def update_initiative(
    initiative_id: str,
    status: str,
    detail: str | None = None,
    log_path: Path = DEFAULT_INITIATIVE_LOG,
) -> bool:
    """Update initiative status. Returns True if found."""
    if status not in _INITIATIVE_STATUSES:
        raise ValueError(f"Invalid initiative status: {status}")
    records = _load(log_path)
    for rec in records:
        if rec.get("initiative_id") == initiative_id:
            rec["status"] = status
            rec["updated_at"] = _now_utc()
            if detail is not None:
                rec["detail"] = detail
            _save(log_path, records)
            return True
    return False


def get_proposed_initiatives(log_path: Path = DEFAULT_INITIATIVE_LOG) -> list[dict[str, Any]]:
    """Return all PROPOSED initiatives awaiting CEO approval."""
    return [r for r in _load(log_path) if r.get("status") == "PROPOSED"]


def get_initiative(
    initiative_id: str, log_path: Path = DEFAULT_INITIATIVE_LOG
) -> dict[str, Any] | None:
    """Return a specific initiative by ID, or None."""
    return next(
        (r for r in _load(log_path) if r.get("initiative_id") == initiative_id), None
    )


def format_initiative_for_telegram(rec: dict[str, Any]) -> str:
    """Format an initiative proposal for CEO review via Telegram."""
    init_id = rec.get("initiative_id", "?")
    slug = init_id.replace("init_", "")
    return (
        f"🔧 Initiative proposed\n"
        f"ID: {init_id}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Problem: {rec.get('problem', '?')}\n"
        f"Change:  {rec.get('proposed_change', '?')}\n"
        f"Done when: {rec.get('success_criteria', '?')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"→ /approve_init_{slug}  to queue for dev pipeline\n"
        f"→ /reject_init_{slug}   to discard"
    )

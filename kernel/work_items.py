from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .db import ROOT, utc_now


STATUSES = {
    "NEW",
    "READY_FOR_REVIEW",
    "PENDING_APPROVAL",
    "APPROVED",
    "IN_PROGRESS",
    "BLOCKED",
    "MEASUREMENT_READY",
    "DONE",
    "CANCELLED",
}

OPEN_STATUSES = STATUSES - {"DONE", "CANCELLED"}


def _new_id() -> str:
    return f"work_{uuid.uuid4().hex[:12]}"


def _loads(text: str, fallback: Any) -> Any:
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return fallback


def row_to_item(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    item["needs_approval"] = bool(item.get("needs_approval"))
    item["evidence"] = _loads(str(item.pop("evidence_json", "[]")), [])
    item["metadata"] = _loads(str(item.pop("metadata_json", "{}")), {})
    return item


def _record_event(
    conn: sqlite3.Connection,
    work_item_id: str,
    event_type: str,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str = "",
) -> None:
    conn.execute(
        """
        INSERT INTO work_events (work_item_id, event_type, from_status, to_status, note, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (work_item_id, event_type, from_status, to_status, note.strip(), utc_now()),
    )


def get_work_item(conn: sqlite3.Connection, work_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM work_items WHERE id = ?", (work_id,)).fetchone()
    return row_to_item(row)


def create_work_item(
    conn: sqlite3.Connection,
    *,
    title: str,
    work_type: str,
    source: str,
    status: str = "NEW",
    owner: str = "Unassigned",
    due_at: str | None = None,
    needs_approval: bool = False,
    approval_status: str | None = None,
    completion_signal: str | None = None,
    next_step: str | None = None,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], bool]:
    title = title.strip()
    source = source.strip()
    work_type = work_type.strip() or "task"
    status = status.strip().upper()
    if not title:
        raise ValueError("title is required")
    if not source:
        raise ValueError("source is required")
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status}")
    if idempotency_key:
        existing = conn.execute(
            "SELECT * FROM work_items WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()
        if existing is not None:
            return row_to_item(existing) or {}, False

    now = utc_now()
    work_id = _new_id()
    resolved_approval = approval_status or ("PENDING" if needs_approval else "NOT_REQUIRED")
    resolved_next = next_step or _default_next_step(status, bool(needs_approval))
    conn.execute(
        """
        INSERT INTO work_items (
            id, title, type, source, status, owner, due_at, needs_approval,
            approval_status, approved_at, completion_signal, next_step, evidence_json,
            result, idempotency_key, metadata_json, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, '[]', NULL, ?, ?, ?, ?)
        """,
        (
            work_id,
            title,
            work_type,
            source,
            status,
            owner.strip() or "Unassigned",
            due_at,
            1 if needs_approval else 0,
            resolved_approval,
            completion_signal,
            resolved_next,
            idempotency_key,
            json.dumps(metadata or {}, sort_keys=True),
            now,
            now,
        ),
    )
    _record_event(conn, work_id, "created", None, status, "Work item created.")
    conn.commit()
    return get_work_item(conn, work_id) or {}, True


def _default_next_step(status: str, needs_approval: bool) -> str:
    if status in {"READY_FOR_REVIEW", "PENDING_APPROVAL"} or needs_approval:
        return "CEO review required."
    if status == "APPROVED":
        return "Assign owner, due date, and completion signal before execution."
    if status == "IN_PROGRESS":
        return "Complete work and attach evidence."
    return "Clarify next step."


def approve_work_item(
    conn: sqlite3.Connection,
    work_id: str,
    *,
    owner: str,
    due_at: str,
    completion_signal: str,
    next_step: str | None = None,
) -> dict[str, Any]:
    item = get_work_item(conn, work_id)
    if item is None:
        raise ValueError(f"work item not found: {work_id}")
    owner = owner.strip()
    due_at = due_at.strip()
    completion_signal = completion_signal.strip()
    if not owner or not due_at or not completion_signal:
        raise ValueError("approval requires owner, due_at, and completion_signal")
    prior = str(item["status"])
    now = utc_now()
    conn.execute(
        """
        UPDATE work_items
        SET status = 'APPROVED',
            owner = ?,
            due_at = ?,
            approval_status = 'APPROVED',
            approved_at = ?,
            completion_signal = ?,
            next_step = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            owner,
            due_at,
            now,
            completion_signal,
            (next_step or "Start execution and attach evidence when complete.").strip(),
            now,
            work_id,
        ),
    )
    _record_event(conn, work_id, "approved", prior, "APPROVED", completion_signal)
    conn.commit()
    return get_work_item(conn, work_id) or {}


def start_work_item(conn: sqlite3.Connection, work_id: str, note: str = "") -> dict[str, Any]:
    item = get_work_item(conn, work_id)
    if item is None:
        raise ValueError(f"work item not found: {work_id}")
    if item["approval_status"] == "PENDING":
        raise ValueError("CEO approval is required before execution")
    prior = str(item["status"])
    now = utc_now()
    conn.execute(
        "UPDATE work_items SET status = 'IN_PROGRESS', next_step = ?, updated_at = ? WHERE id = ?",
        ("Complete work and attach evidence.", now, work_id),
    )
    _record_event(conn, work_id, "started", prior, "IN_PROGRESS", note)
    conn.commit()
    return get_work_item(conn, work_id) or {}


def block_work_item(conn: sqlite3.Connection, work_id: str, reason: str) -> dict[str, Any]:
    item = get_work_item(conn, work_id)
    if item is None:
        raise ValueError(f"work item not found: {work_id}")
    reason = reason.strip()
    if not reason:
        raise ValueError("blocked reason is required")
    prior = str(item["status"])
    now = utc_now()
    conn.execute(
        "UPDATE work_items SET status = 'BLOCKED', next_step = ?, updated_at = ? WHERE id = ?",
        (f"Blocked: {reason}", now, work_id),
    )
    _record_event(conn, work_id, "blocked", prior, "BLOCKED", reason)
    conn.commit()
    return get_work_item(conn, work_id) or {}


def done_work_item(
    conn: sqlite3.Connection,
    work_id: str,
    *,
    result: str,
    evidence: str,
) -> dict[str, Any]:
    item = get_work_item(conn, work_id)
    if item is None:
        raise ValueError(f"work item not found: {work_id}")
    result = result.strip()
    evidence = evidence.strip()
    if not result or not evidence:
        raise ValueError("done requires result and evidence")
    prior = str(item["status"])
    evidence_rows = item.get("evidence", [])
    evidence_rows = evidence_rows if isinstance(evidence_rows, list) else []
    evidence_rows.append({"summary": evidence, "captured_at": utc_now()})
    now = utc_now()
    conn.execute(
        """
        UPDATE work_items
        SET status = 'DONE',
            result = ?,
            evidence_json = ?,
            next_step = 'Closed.',
            updated_at = ?
        WHERE id = ?
        """,
        (result, json.dumps(evidence_rows, sort_keys=True), now, work_id),
    )
    _record_event(conn, work_id, "done", prior, "DONE", result)
    conn.commit()
    return get_work_item(conn, work_id) or {}


def list_work_items(
    conn: sqlite3.Connection,
    *,
    statuses: list[str] | None = None,
    include_closed: bool = False,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    clauses: list[str] = []
    if statuses:
        clean = [status.strip().upper() for status in statuses if status.strip()]
        placeholders = ",".join("?" for _ in clean)
        clauses.append(f"status IN ({placeholders})")
        params.extend(clean)
    elif not include_closed:
        placeholders = ",".join("?" for _ in sorted(OPEN_STATUSES))
        clauses.append(f"status IN ({placeholders})")
        params.extend(sorted(OPEN_STATUSES))
    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM work_items {where} ORDER BY due_at IS NULL, due_at, created_at",
        params,
    ).fetchall()
    return [item for row in rows if (item := row_to_item(row)) is not None]


def scan_ready_for_review_markdown(
    conn: sqlite3.Connection,
    *,
    root: str | Path,
) -> dict[str, Any]:
    root_path = Path(root)
    created = 0
    existing = 0
    skipped_dirs = {
        ".claude",
        ".git",
        ".gstack",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "artifacts",
        "logs",
        "memory",
        "node_modules",
        "reports",
        "state",
    }
    for path in root_path.rglob("*.md"):
        if any(part in skipped_dirs for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if not re.search(r"READY FOR MA REVIEW|READY FOR REVIEW", text, flags=re.I):
            continue
        rel = path.relative_to(root_path).as_posix()
        metadata = {
            "executor": "review_markdown_artifact",
            "path": rel,
            "scan_root": str(root_path),
        }
        try:
            metadata["repo_path"] = path.relative_to(ROOT).as_posix()
        except ValueError:
            pass
        item, was_created = create_work_item(
            conn,
            title=f"Review required: {path.stem}",
            work_type="review",
            source=f"markdown:{rel}",
            status="READY_FOR_REVIEW",
            owner="CEO",
            needs_approval=True,
            approval_status="PENDING",
            next_step="Review the artifact and approve, reject, or request changes.",
            idempotency_key=f"review:{rel}",
            metadata=metadata,
        )
        _ = item
        if was_created:
            created += 1
        else:
            existing += 1
    return {"ok": True, "created": created, "existing": existing}

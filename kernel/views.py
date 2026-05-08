from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from typing import Any

from .work_items import list_work_items


def _parse_utc(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def work_status(conn: sqlite3.Connection, *, now: datetime | None = None) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    items = list_work_items(conn)
    pending = [item for item in items if item["approval_status"] == "PENDING"]
    ready = [item for item in items if item["status"] == "READY_FOR_REVIEW"]
    approved = [item for item in items if item["status"] == "APPROVED"]
    in_progress = [item for item in items if item["status"] == "IN_PROGRESS"]
    blocked = [item for item in items if item["status"] == "BLOCKED"]
    measurement_ready = [item for item in items if item["status"] == "MEASUREMENT_READY"]
    overdue = [
        item
        for item in items
        if item.get("due_at")
        and item["status"] not in {"DONE", "CANCELLED"}
        and (_parse_utc(str(item["due_at"])) or current) < current
    ]
    return {
        "ok": True,
        "counts": {
            "open": len(items),
            "pending_approval": len(pending),
            "ready_for_review": len(ready),
            "approved": len(approved),
            "in_progress": len(in_progress),
            "blocked": len(blocked),
            "measurement_ready": len(measurement_ready),
            "overdue": len(overdue),
        },
        "decide": pending,
        "execute": approved + in_progress,
        "blocked": blocked,
        "measure": measurement_ready,
        "overdue": overdue,
    }


def render_status_text(status: dict[str, Any]) -> str:
    counts = status.get("counts", {})
    lines = [
        "Work Ledger",
        (
            f"- Open: {counts.get('open', 0)} | Decide: {counts.get('pending_approval', 0)} | "
            f"Execute: {counts.get('approved', 0) + counts.get('in_progress', 0)} | "
            f"Blocked: {counts.get('blocked', 0)} | Overdue: {counts.get('overdue', 0)}"
        ),
    ]
    sections = [
        ("Decide", status.get("decide", [])),
        ("Overdue", status.get("overdue", [])),
        ("Execute", status.get("execute", [])),
        ("Blocked", status.get("blocked", [])),
        ("Measure", status.get("measure", [])),
    ]
    for heading, items in sections:
        lines.append("")
        lines.append(heading)
        if not items:
            lines.append("- None")
            continue
        for item in items[:8]:
            lines.append(
                f"- {item.get('id')} [{item.get('status')}] {item.get('title')} "
                f"| owner={item.get('owner')} | due={item.get('due_at') or 'n/a'}"
            )
            lines.append(f"  Next: {item.get('next_step')}")
    return "\n".join(lines)

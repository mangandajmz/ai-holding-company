from __future__ import annotations

import sqlite3
from typing import Any

from .views import render_status_text, work_status
from .work_items import block_work_item, done_work_item, list_work_items, start_work_item


def run_next_work_item(conn: sqlite3.Connection) -> dict[str, Any]:
    approved = list_work_items(conn, statuses=["APPROVED"])
    if not approved:
        return {"ok": True, "ran": False, "message": "No approved work items are ready to run.", "item": None}

    item = approved[0]
    started = start_work_item(conn, str(item["id"]), note="Worker picked up approved work.")
    executor = str(started.get("metadata", {}).get("executor", "")).strip()
    if executor == "ledger_status_snapshot":
        status = work_status(conn)
        text = render_status_text(status)
        done = done_work_item(
            conn,
            str(started["id"]),
            result="Ledger status snapshot generated.",
            evidence=text,
        )
        return {
            "ok": True,
            "ran": True,
            "outcome": "done",
            "executor": executor,
            "item": done,
        }

    reason = (
        f"No automated executor is registered for type={started.get('type')} "
        f"source={started.get('source')}."
    )
    blocked = block_work_item(conn, str(started["id"]), reason)
    return {
        "ok": True,
        "ran": True,
        "outcome": "blocked",
        "executor": executor or None,
        "item": blocked,
        "reason": reason,
    }

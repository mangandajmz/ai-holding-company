from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from kernel.db import connect
from kernel.views import render_reminder_text, render_status_text, work_reminders, work_status
from kernel.work_items import (
    approve_work_item,
    create_work_item,
    done_work_item,
    scan_ready_for_review_markdown,
    start_work_item,
)


def _conn(tmp_path: Path):
    return connect(tmp_path / "work_ledger.db")


def test_ready_for_review_item_appears_in_decision_queue(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    try:
        item, created = create_work_item(
            conn,
            title="Review Stage L closure",
            work_type="review",
            source="markdown:stage.md",
            status="READY_FOR_REVIEW",
            owner="CEO",
            needs_approval=True,
        )

        status = work_status(conn)

        assert created is True
        assert item["approval_status"] == "PENDING"
        assert status["counts"]["pending_approval"] == 1
        assert status["decide"][0]["title"] == "Review Stage L closure"
    finally:
        conn.close()


def test_approval_requires_owner_due_date_and_completion_signal(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    try:
        item, _ = create_work_item(
            conn,
            title="Metric refresh",
            work_type="task",
            source="manual",
            needs_approval=True,
        )

        with pytest.raises(ValueError, match="owner, due_at, and completion_signal"):
            approve_work_item(
                conn,
                item["id"],
                owner="Commercial",
                due_at="",
                completion_signal="Updated metric source.",
            )

        approved = approve_work_item(
            conn,
            item["id"],
            owner="Commercial",
            due_at="2026-05-08T18:00:00+00:00",
            completion_signal="Updated metric source.",
        )

        assert approved["status"] == "APPROVED"
        assert approved["owner"] == "Commercial"
        assert approved["due_at"] == "2026-05-08T18:00:00+00:00"
        assert approved["completion_signal"] == "Updated metric source."
    finally:
        conn.close()


def test_approved_and_started_items_appear_in_execution_queue(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    try:
        item, _ = create_work_item(conn, title="Prepare FTMO draft", work_type="task", source="manual")
        approve_work_item(
            conn,
            item["id"],
            owner="Marketing",
            due_at="2026-05-08T20:00:00+00:00",
            completion_signal="Draft exists without publication.",
        )

        status = work_status(conn)
        assert status["counts"]["approved"] == 1
        assert status["execute"][0]["owner"] == "Marketing"

        start_work_item(conn, item["id"])
        started_status = work_status(conn)
        assert started_status["counts"]["in_progress"] == 1
        assert started_status["execute"][0]["status"] == "IN_PROGRESS"
    finally:
        conn.close()


def test_overdue_item_is_visible_in_status_text(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    try:
        item, _ = create_work_item(conn, title="Overdue work", work_type="task", source="manual")
        approve_work_item(
            conn,
            item["id"],
            owner="Holding",
            due_at="2026-05-01T12:00:00+00:00",
            completion_signal="Heartbeat rerun.",
        )

        status = work_status(conn, now=datetime(2026, 5, 8, tzinfo=timezone.utc))
        text = render_status_text(status)

        assert status["counts"]["overdue"] == 1
        assert "Overdue work" in text
        assert "Overdue" in text
    finally:
        conn.close()


def test_done_requires_result_and_evidence(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    try:
        item, _ = create_work_item(conn, title="Close with proof", work_type="task", source="manual")

        with pytest.raises(ValueError, match="result and evidence"):
            done_work_item(conn, item["id"], result="Complete", evidence="")

        done = done_work_item(
            conn,
            item["id"],
            result="Complete",
            evidence="reports/example.md confirms completion.",
        )

        assert done["status"] == "DONE"
        assert done["result"] == "Complete"
        assert done["evidence"][0]["summary"] == "reports/example.md confirms completion."
    finally:
        conn.close()


def test_markdown_review_scanner_creates_idempotent_work_items(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    try:
        closure = tmp_path / "finance_web_page" / "STAGE_L_L2.9_CLOSURE.md"
        closure.parent.mkdir()
        closure.write_text(
            "# Closure\n\n**Status:** READY FOR MA REVIEW - 2026-05-08\n",
            encoding="utf-8",
        )

        first = scan_ready_for_review_markdown(conn, root=tmp_path)
        second = scan_ready_for_review_markdown(conn, root=tmp_path)
        status = work_status(conn)

        assert first == {"ok": True, "created": 1, "existing": 0}
        assert second == {"ok": True, "created": 0, "existing": 1}
        assert status["counts"]["pending_approval"] == 1
        assert status["decide"][0]["source"] == "markdown:finance_web_page/STAGE_L_L2.9_CLOSURE.md"
    finally:
        conn.close()


def test_work_reminders_include_owner_action_items_once(tmp_path: Path) -> None:
    conn = _conn(tmp_path)
    try:
        review, _ = create_work_item(
            conn,
            title="Review Stage L closure",
            work_type="review",
            source="markdown:stage.md",
            status="READY_FOR_REVIEW",
            owner="CEO",
            needs_approval=True,
        )
        overdue, _ = create_work_item(conn, title="Overdue owner task", work_type="task", source="manual")
        approve_work_item(
            conn,
            overdue["id"],
            owner="CEO",
            due_at="2026-05-01T12:00:00+00:00",
            completion_signal="Decision recorded.",
        )

        reminders = work_reminders(conn, now=datetime(2026, 5, 8, tzinfo=timezone.utc))
        text = render_reminder_text(reminders)

        assert reminders["needs_attention"] is True
        assert reminders["count"] == 2
        assert {item["id"] for item in reminders["items"]} == {review["id"], overdue["id"]}
        assert "Needs approval" in text
        assert "Overdue" in text
    finally:
        conn.close()

"""Tests for Content Studio orchestration."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from content_studio import (  # noqa: E402
    _evaluate_content_studio_status,
    _get_max_approval_wait,
    _intake_brief,
    _load_draft_history,
    _track_draft,
    run_content_studio,
)


class TestContentStudioIntake:
    """Test brief intake parsing."""

    def test_intake_brief_parses_basic(self) -> None:
        brief = "Write a blog post about trading psychology"
        intake = _intake_brief(brief)
        assert "brief_text" in intake
        assert intake["status"] == "INTAKE_PARSED"
        assert "timestamp" in intake

    def test_intake_brief_preserves_text(self) -> None:
        brief = "Email to clients: Q2 performance update"
        intake = _intake_brief(brief)
        assert intake["brief_text"] == brief

    def test_intake_brief_detects_format(self) -> None:
        brief = "Format: email. Target audience: active traders."
        intake = _intake_brief(brief)
        assert intake["format"] == "email"


class TestContentStudioTracking:
    """Test draft tracking and PENDING_CEO_APPROVAL gate."""

    def test_track_draft_adds_pending_status(self) -> None:
        draft = {"draft_content": "Sample draft"}
        tracked = _track_draft(draft)
        assert tracked["status"] == "PENDING_CEO_APPROVAL"

    def test_track_draft_adds_timestamps(self) -> None:
        draft = {"draft_content": "Sample"}
        tracked = _track_draft(draft)
        assert "created_at" in tracked
        assert "approval_deadline" in tracked

    def test_track_draft_no_ceo_approval_until_reviewed(self) -> None:
        draft = {"draft_content": "Sample"}
        tracked = _track_draft(draft)
        assert tracked["ceo_approval"] is None


class TestContentStudioStatus:
    """Test division health status evaluation."""

    def test_status_green_when_no_pending(self) -> None:
        pending = []
        approval_wait = 0.0
        config = {"targets": {"content_studio": {"ceo_approval_wait_time_hours": {"alert_threshold": 48}}}}
        status = _evaluate_content_studio_status(pending, approval_wait, config)
        assert status == "GREEN"

    def test_status_amber_when_pending_exceeds_threshold(self) -> None:
        pending = [{"status": "PENDING_CEO_APPROVAL"}]
        approval_wait = 72.0
        config = {"targets": {"content_studio": {"ceo_approval_wait_time_hours": {"alert_threshold": 48}}}}
        status = _evaluate_content_studio_status(pending, approval_wait, config)
        assert status == "AMBER"

    def test_status_red_when_missing_pending_gate(self) -> None:
        pending = [{"status": "APPROVED_FOR_PUBLISH"}]
        approval_wait = 10.0
        config = {"targets": {"content_studio": {"ceo_approval_wait_time_hours": {"alert_threshold": 48}}}}
        status = _evaluate_content_studio_status(pending, approval_wait, config)
        assert status == "RED"

    def test_status_green_when_pending_within_sla(self) -> None:
        pending = [{"status": "PENDING_CEO_APPROVAL"}]
        approval_wait = 24.0
        config = {"targets": {"content_studio": {"ceo_approval_wait_time_hours": {"alert_threshold": 48}}}}
        status = _evaluate_content_studio_status(pending, approval_wait, config)
        assert status == "GREEN"

    def test_get_max_approval_wait_uses_oldest_pending(self) -> None:
        now = datetime.now(timezone.utc)
        pending = [
            {"status": "PENDING_CEO_APPROVAL", "created_at": (now - timedelta(hours=1)).isoformat()},
            {"status": "PENDING_CEO_APPROVAL", "created_at": (now - timedelta(hours=6)).isoformat()},
        ]
        wait_hours = _get_max_approval_wait(pending)
        assert wait_hours >= 5.9


class TestContentStudioOrchestration:
    """Test main orchestration function."""

    def test_run_content_studio_returns_dict(self, monkeypatch, tmp_path: Path) -> None:
        import content_studio

        tracking_file = tmp_path / "content_studio_drafts.jsonl"
        monkeypatch.setattr(content_studio, "_TRACKING_FILE", tracking_file)
        config = {"targets": {"content_studio": {"ceo_approval_wait_time_hours": {"alert_threshold": 48}}}}

        result = run_content_studio(config, brief_text="")
        assert isinstance(result, dict)
        assert result["division"] == "content_studio"
        assert result["status"] in {"GREEN", "AMBER", "RED"}
        assert "notes" in result

    def test_run_content_studio_tracks_pending_draft(self, monkeypatch, tmp_path: Path) -> None:
        import content_studio

        tracking_file = tmp_path / "content_studio_drafts.jsonl"
        monkeypatch.setattr(content_studio, "_TRACKING_FILE", tracking_file)
        config = {"targets": {"content_studio": {"ceo_approval_wait_time_hours": {"alert_threshold": 48}}}}

        result = run_content_studio(
            config,
            brief_text="Write an article about MT5 signal quality. Target audience: traders.",
        )
        assert result["status"] == "GREEN"
        assert result["drafts_pending"] == 1
        rows = _load_draft_history(tracking_file)
        assert len(rows) == 1
        assert rows[0]["status"] == "PENDING_CEO_APPROVAL"
        assert rows[0]["ceo_approval"] is None

    def test_load_draft_history_handles_invalid_jsonl_lines(self, tmp_path: Path) -> None:
        tracking_file = tmp_path / "content_studio_drafts.jsonl"
        tracking_file.write_text(
            "not-json\n"
            + json.dumps({"status": "PENDING_CEO_APPROVAL", "created_at": datetime.now(timezone.utc).isoformat()})
            + "\n",
            encoding="utf-8",
        )
        rows = _load_draft_history(tracking_file)
        assert len(rows) == 1
        assert rows[0]["status"] == "PENDING_CEO_APPROVAL"

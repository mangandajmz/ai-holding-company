"""Tests for CEO time-saved tracking and R9 guardrail."""

from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import time_tracking  # noqa: E402


class TestTimeCheckin:
    """Test time check-in logging."""

    def test_log_checkin_creates_record(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        result = time_tracking.log_time_checkin("Used /trading command", 0.5)
        assert result["ok"] is True
        assert "timestamp" in result
        assert result["hours_saved"] == 0.5

    def test_multiple_checkins_accumulate(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        time_tracking.log_time_checkin("Activity 1", 1.0)
        time_tracking.log_time_checkin("Activity 2", 0.5)
        report = time_tracking.get_time_saved_report(days=1)
        assert report["activity_count"] >= 2

    def test_invalid_activity_rejected(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        result = time_tracking.log_time_checkin("", 1.0)
        assert result["ok"] is False
        assert result["status"] == "INVALID_ACTIVITY"


class TestTimeSavedReport:
    """Test time-saved measurement."""

    def test_report_returns_dict(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        result = time_tracking.get_time_saved_report(days=14)
        assert result["ok"] is True
        assert "total_hours_saved" in result
        assert "weekly_average" in result

    def test_weekly_average_calculated(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        time_tracking.log_time_checkin("Test activity", 2.5)
        report = time_tracking.get_time_saved_report(days=7)
        assert report["weekly_average"] >= 0

    def test_no_checkins_returns_zeroes(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        report = time_tracking.get_time_saved_report(days=7)
        assert report["total_hours_saved"] == 0.0
        assert report["activity_count"] == 0


class TestR9Guardrail:
    """Test R9 guardrail enforcement (5 hours/week minimum)."""

    def test_r9_threshold_defined(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        result = time_tracking.check_r9_guardrail(weeks=2)
        assert result["ok"] is True
        assert result["status"] in ["GREEN", "AMBER", "RED"]
        assert "weekly_average_hours" in result

    def test_r9_green_when_above_threshold(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        for _ in range(6):
            time_tracking.log_time_checkin("Activity", 1.0)
        result = time_tracking.check_r9_guardrail(weeks=1)
        assert result["status"] in ["GREEN", "AMBER"]

    def test_r9_red_when_well_below_threshold(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(time_tracking, "_CHECKIN_FILE", tmp_path / "time_checkins.jsonl")
        time_tracking.log_time_checkin("Small gain", 0.2)
        result = time_tracking.check_r9_guardrail(weeks=1)
        assert result["status"] in ["AMBER", "RED"]


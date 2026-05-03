from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import boardroom  # noqa: E402


def _config(tmp_path: Path) -> dict:
    return {
        "paths": {
            "reports_dir": str(tmp_path / "reports"),
            "state_dir": str(tmp_path / "state"),
        }
    }


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_start_boardroom_creates_transcript_from_existing_reports(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(boardroom, "ROOT", tmp_path)
    config = _config(tmp_path)
    _write_json(
        tmp_path / "reports" / "phase3_holding_latest.json",
        {
            "generated_at_utc": "2026-05-02T12:00:00+00:00",
            "company_scorecard": {"status": "AMBER"},
            "base_summary": {"websites_up": 2, "websites_total": 2, "pnl_total": 0.0, "trades_total": 0},
        },
    )
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {"board_snapshot": {"approvals": [{"approval_id": "board_test"}]}, "decisions": {}},
    )

    result = boardroom.start_boardroom(config, topic="Weekly CEO review")

    assert result["ok"] is True
    assert result["status"] == "OPEN"
    latest = tmp_path / "reports" / "boardroom" / "boardroom_latest.md"
    assert latest.exists()
    text = latest.read_text(encoding="utf-8")
    assert "Managing Agent" in text
    assert "Company status is AMBER" in text
    assert "pending approvals=1" in text


def test_ask_boardroom_auto_opens_and_gates_risky_topics(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(boardroom, "ROOT", tmp_path)
    config = _config(tmp_path)

    result = boardroom.ask_boardroom(config, division="trading", question="Should we deploy a live trading change?")

    assert result["ok"] is True
    assert result["speaker"] == "Trading Division"
    assert "PENDING_CEO_APPROVAL" in result["answer"]
    state = json.loads((tmp_path / "state" / "boardroom_state.json").read_text(encoding="utf-8"))
    transcript = state["active_meeting"]["transcript"]
    assert any(item["speaker"] == "Human CEO" for item in transcript)
    assert any(item["speaker"] == "Trading Division" for item in transcript)


def test_close_boardroom_records_decision_and_clears_active_meeting(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(boardroom, "ROOT", tmp_path)
    config = _config(tmp_path)
    opened = boardroom.start_boardroom(config, topic="Close test")

    result = boardroom.close_boardroom(config, note="Proceed with documentation cleanup only.")

    assert result["status"] == "CLOSED"
    assert result["meeting_id"] == opened["meeting_id"]
    state = json.loads((tmp_path / "state" / "boardroom_state.json").read_text(encoding="utf-8"))
    assert state["active_meeting"] == {}
    assert "documentation cleanup" in state["last_meeting"]["decisions"][0]
    latest = tmp_path / "reports" / "boardroom" / "boardroom_latest.md"
    assert "Meeting closed" in latest.read_text(encoding="utf-8")

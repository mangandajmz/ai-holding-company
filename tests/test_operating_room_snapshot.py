from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from operating_room_snapshot import build_operating_room_snapshot  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_operating_room_snapshot_has_four_read_only_views(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "RED",
            "owner_need": "approve",
            "brief": "The company is RED.",
        },
    )
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {
            "board_snapshot": {
                "approvals": [
                    {
                        "approval_id": "board_1",
                        "topic": "Company KPI",
                        "priority": "RED",
                        "decision": "Focus execution.",
                    }
                ]
            }
        },
    )
    memory_path = tmp_path / "memory" / "vector_store.jsonl"
    memory_path.parent.mkdir(parents=True, exist_ok=True)
    memory_path.write_text(
        json.dumps({"text": "Owner prefers deterministic openings.", "metadata": {"type": "decision"}}) + "\n",
        encoding="utf-8",
    )

    snapshot = build_operating_room_snapshot(root=tmp_path)

    assert snapshot["ok"] is True
    assert set(snapshot["views"]) == {"today", "approvals", "memory", "personas"}
    assert snapshot["views"]["today"]["status"] == "RED"
    assert snapshot["views"]["approvals"]["pending_count"] == 1
    assert snapshot["views"]["memory"]["sample_count"] == 1
    assert snapshot["views"]["personas"]["personas"][0]["name"] == "Chief of Staff"
    assert (tmp_path / "operating-room" / "snapshot.json").exists()


def test_build_operating_room_snapshot_is_honest_when_sources_are_missing(tmp_path: Path) -> None:
    snapshot = build_operating_room_snapshot(root=tmp_path)

    assert snapshot["views"]["today"]["status"] == "UNKNOWN"
    assert snapshot["views"]["today"]["items"][0]["status"] == "UNKNOWN"
    assert snapshot["views"]["approvals"]["pending_count"] == 0
    assert snapshot["views"]["memory"]["sample_count"] == 0

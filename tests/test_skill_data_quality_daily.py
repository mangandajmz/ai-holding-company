from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from skill_data_quality_daily import run_data_quality_daily  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_data_quality_daily_reports_green_for_current_mt5_evidence(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "mt5-agentic-desk" / "logs" / "evidence" / "daily_summary_2026-05-09.json",
        {"date": "2026-05-09", "total_decisions": 3},
    )

    result = run_data_quality_daily(root=tmp_path, as_of=date(2026, 5, 9))

    assert result["ok"] is True
    assert result["status"] == "GREEN"
    assert result["checks"][0]["name"] == "MT5 evidence freshness"
    assert result["checks"][0]["status"] == "GREEN"
    assert (tmp_path / result["markdown_path"]).exists()


def test_run_data_quality_daily_blocks_when_mt5_evidence_missing(tmp_path: Path) -> None:
    result = run_data_quality_daily(root=tmp_path, as_of=date(2026, 5, 9))

    assert result["status"] == "BLOCKED"
    assert result["owner_need"] == "none"
    assert "No MT5 daily evidence summary found" in result["brief"]

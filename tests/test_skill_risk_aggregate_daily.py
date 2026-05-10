from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from skill_risk_aggregate_daily import run_risk_aggregate_daily  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_risk_aggregate_daily_writes_natural_brief_and_sidecar(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "phase3_holding_latest.json",
        {
            "generated_at_utc": "2026-05-09T12:00:00+00:00",
            "company_scorecard": {
                "status": "RED",
                "risks": ["Forecast attainment is RED."],
                "actions": ["Prioritize monetization levers."],
            },
        },
    )
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {
            "board_snapshot": {
                "approvals": [
                    {
                        "approval_id": "board_forecast",
                        "topic": "Company KPI: Forecast attainment",
                        "decision": "Run monetization recovery.",
                    }
                ]
            }
        },
    )

    result = run_risk_aggregate_daily(root=tmp_path)

    assert result["ok"] is True
    assert result["status"] == "RED"
    assert "You have one real decision today" in result["brief"]
    assert result["owner_need"] == "approve"
    markdown_path = tmp_path / result["markdown_path"]
    json_path = tmp_path / result["json_path"]
    assert markdown_path.exists()
    assert json_path.exists()
    assert "Forecast attainment is RED" in markdown_path.read_text(encoding="utf-8")
    sidecar = json.loads(json_path.read_text(encoding="utf-8"))
    assert sidecar["owner_need"] == "approve"
    assert sidecar["sources"] == result["sources"]

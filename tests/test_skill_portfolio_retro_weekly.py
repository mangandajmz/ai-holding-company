from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from skill_portfolio_retro_weekly import run_portfolio_retro_weekly  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_portfolio_retro_weekly_blocks_without_skill_outputs(tmp_path: Path) -> None:
    result = run_portfolio_retro_weekly(root=tmp_path)

    assert result["ok"] is True
    assert result["status"] == "BLOCKED"
    assert result["owner_need"] == "none"
    assert "No skill outputs found" in result["brief"]
    assert (tmp_path / result["markdown_path"]).exists()


def test_run_portfolio_retro_weekly_aggregates_skill_outputs_and_decisions(tmp_path: Path) -> None:
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
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "skill": "backtest-review",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Backtest review is BLOCKED.",
        },
    )
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {
            "board_snapshot": {"approvals": [{"approval_id": "board_1"}]},
            "decisions": {"board_old": {"decision": "APPROVED"}},
        },
    )

    result = run_portfolio_retro_weekly(root=tmp_path)

    assert result["status"] == "BLOCKED"
    assert result["owner_need"] == "approve"
    assert result["metrics"]["skill_outputs_count"] == 2
    assert result["metrics"]["pending_approvals_count"] == 1
    assert result["metrics"]["decisions_logged_count"] == 1
    assert result["metrics"]["unresolved_issues_count"] == 2
    assert result["open_issues"][0]["skill"] == "backtest-review"

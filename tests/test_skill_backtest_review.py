from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from skill_backtest_review import run_backtest_review  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_backtest_review_blocks_current_weak_mt5_evidence(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "mt5-agentic-desk" / "logs" / "research" / "research_20260508_170002.json",
        {
            "summary": {
                "selected_for_review": 8,
                "approved": 0,
                "rejected": 7,
            },
            "validation": {
                "with_out_of_sample": 0,
                "with_walk_forward": 0,
            },
            "review_results": [
                {"decision": "APPROVE_BLOCKED"},
                {"decision": "REJECT"},
            ],
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "data-quality-daily" / "latest.json",
        {"status": "GREEN", "brief": "Trading data quality is green."},
    )

    result = run_backtest_review(root=tmp_path)

    assert result["ok"] is True
    assert result["status"] == "BLOCKED"
    assert result["autonomy"] == "Guardrail"
    assert result["owner_need"] == "none"
    assert result["metrics"]["approved_count"] == 0
    assert result["metrics"]["pass_unchanged_rate_pct"] == 0.0
    assert "approved 0" in result["brief"]
    assert "out-of-sample" in result["brief"]
    assert (tmp_path / result["markdown_path"]).exists()


def test_run_backtest_review_requires_local_research_artifact(tmp_path: Path) -> None:
    result = run_backtest_review(root=tmp_path)

    assert result["status"] == "BLOCKED"
    assert result["owner_need"] == "none"
    assert "No MT5 research artifact found" in result["brief"]


def test_run_backtest_review_can_pass_only_for_owner_approval(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "mt5-agentic-desk" / "logs" / "research" / "research_20260508_170002.json",
        {
            "summary": {
                "selected_for_review": 4,
                "approved": 1,
                "rejected": 2,
            },
            "validation": {
                "with_out_of_sample": 2,
                "with_walk_forward": 1,
            },
            "review_results": [
                {"decision": "APPROVE"},
                {"decision": "REJECT"},
                {"decision": "REJECT"},
            ],
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "data-quality-daily" / "latest.json",
        {"status": "GREEN", "brief": "Trading data quality is green."},
    )

    result = run_backtest_review(root=tmp_path)

    assert result["status"] == "PASS_FOR_OWNER_APPROVAL"
    assert result["owner_need"] == "approve"
    assert result["metrics"]["pass_unchanged_rate_pct"] == 25.0
    assert "cannot approve live or forward trading" in result["required_next_action"]

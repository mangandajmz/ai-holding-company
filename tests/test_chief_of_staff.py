from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from chief_of_staff import answer_company_question, render_company_answer  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_answer_company_question_summarizes_owner_needs_naturally(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "phase3_holding_latest.json",
        {
            "generated_at_utc": "2026-05-09T12:00:00+00:00",
            "company_scorecard": {
                "status": "RED",
                "risks": ["Forecast attainment is RED."],
                "actions": ["Prioritize monetization levers."],
            },
            "base_summary": {"websites_up": 2, "websites_total": 2, "pnl_total": 0.0, "trades_total": 0},
        },
    )
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {
            "board_snapshot": {
                "approvals": [
                    {
                        "approval_id": "board_test",
                        "topic": "Company KPI: Forecast attainment",
                        "decision": "Run monetization recovery.",
                        "owner": "holding",
                        "priority": "RED",
                    }
                ]
            },
            "decisions": {},
        },
    )

    response = answer_company_question("What needs me today?", root=tmp_path)

    assert "You have one real decision today" in response["answer"]
    assert "one approval" in response["answer"].lower()
    assert "Forecast attainment" in response["answer"]
    assert response["owner_need"] == "approve"
    assert "reports/phase3_holding_latest.json" in response["sources"]


def test_answer_company_question_handles_trading_status_from_truth(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "phase2_divisions_latest.json",
        {
            "generated_at_utc": "2026-05-09T12:00:00+00:00",
            "divisions": [
                {
                    "division": "trading",
                    "status": "yellow",
                    "scorecard": {
                        "status": "AMBER",
                        "items": [
                            {
                                "metric": "MT5 cycle freshness",
                                "status": "AMBER",
                                "actual": "4h",
                                "target": "<= 180m",
                                "action": "Verify runtime events are advancing.",
                            }
                        ],
                    },
                }
            ],
        },
    )

    response = answer_company_question("Why is trading yellow?", root=tmp_path)

    assert "Trading is AMBER" in response["answer"]
    assert "MT5 cycle freshness" in response["answer"]
    assert "Verify runtime events are advancing" in response["answer"]
    assert response["truth_state"] == "known"


def test_answer_company_question_uses_data_quality_skill_for_trading_readiness(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "data-quality-daily" / "latest.json",
        {
            "status": "BLOCKED",
            "brief": "Trading data quality is BLOCKED. No MT5 daily evidence summary found.",
            "checks": [],
        },
    )

    response = answer_company_question("Why is trading yellow?", root=tmp_path)

    assert "Trading data-quality readiness is BLOCKED" in response["answer"]
    assert "No MT5 daily evidence summary found" in response["answer"]


def test_answer_company_question_uses_backtest_review_for_forward_test_questions(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "status": "BLOCKED",
            "brief": "Backtest review is BLOCKED. No reviewed candidate is approved.",
            "required_next_action": "Do not move any reviewed strategy to forward-test.",
        },
    )

    response = answer_company_question("Can the strategy move to forward-test?", root=tmp_path)

    assert "Backtest review is BLOCKED" in response["answer"]
    assert "Do not move any reviewed strategy" in response["answer"]
    assert response["owner_need"] == "none"


def test_answer_company_question_uses_support_triage_for_support_questions(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "support-triage" / "latest.json",
        {
            "status": "AMBER",
            "brief": "Support triage found 2 ticket(s): 1 draft(s) and 1 escalation(s).",
        },
    )

    response = answer_company_question("What is happening in support?", root=tmp_path)

    assert "Support triage is AMBER" in response["answer"]
    assert "2 ticket" in response["answer"]
    assert response["owner_need"] == "approve"


def test_answer_company_question_refuses_missing_truth(tmp_path: Path) -> None:
    response = answer_company_question("What needs me today?", root=tmp_path)

    assert "I do not have current company evidence" in response["answer"]
    assert response["truth_state"] == "unknown"
    assert response["owner_need"] == "refresh"


def test_answer_company_question_shows_evidence_when_requested(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "phase3_holding_latest.json",
        {
            "generated_at_utc": "2026-05-09T12:00:00+00:00",
            "company_scorecard": {"status": "GREEN", "risks": [], "actions": []},
        },
    )

    response = answer_company_question("Show evidence for what needs me today", root=tmp_path)

    assert "Evidence:" in response["answer"]
    assert "reports/phase3_holding_latest.json" in response["answer"]


def test_render_company_answer_is_conversational_not_json(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "phase3_holding_latest.json",
        {
            "generated_at_utc": "2026-05-09T12:00:00+00:00",
            "company_scorecard": {
                "status": "AMBER",
                "risks": ["Growth is below target."],
                "actions": ["Review weekly analytics."],
            },
        },
    )

    response = answer_company_question("What needs me today?", root=tmp_path)
    text = render_company_answer(response)

    assert text.startswith("You")
    assert '"ok"' not in text
    assert "Sources:" not in text

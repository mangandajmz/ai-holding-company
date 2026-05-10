from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from org_truth_retriever import collect_truth_bundle  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_collect_truth_bundle_loads_company_status_and_approvals(tmp_path: Path) -> None:
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

    bundle = collect_truth_bundle(tmp_path)

    assert bundle.company_status == "RED"
    assert bundle.company_risks == ["Forecast attainment is RED."]
    assert bundle.pending_approvals[0]["approval_id"] == "board_test"
    assert any(source.path == "reports/phase3_holding_latest.json" for source in bundle.sources)


def test_collect_truth_bundle_returns_unknowns_when_reports_are_missing(tmp_path: Path) -> None:
    bundle = collect_truth_bundle(tmp_path)

    assert bundle.company_status == "UNKNOWN"
    assert bundle.truth_state == "unknown"
    assert bundle.pending_approvals == []
    assert bundle.company_risks == []


def test_collect_truth_bundle_extracts_trading_scorecard(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "phase2_divisions_latest.json",
        {
            "generated_at_utc": "2026-05-09T12:00:00+00:00",
            "divisions": [
                {
                    "division": "trading",
                    "status": "amber",
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
                        "actions": ["Verify runtime events are advancing."],
                    },
                }
            ],
        },
    )

    bundle = collect_truth_bundle(tmp_path)

    assert bundle.trading_status == "AMBER"
    assert bundle.trading_issues[0]["metric"] == "MT5 cycle freshness"
    assert bundle.trading_actions == ["Verify runtime events are advancing."]


def test_collect_truth_bundle_loads_data_quality_skill_output(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "data-quality-daily" / "latest.json",
        {
            "status": "BLOCKED",
            "brief": "Trading data quality is BLOCKED. No MT5 daily evidence summary found.",
            "checks": [],
        },
    )

    bundle = collect_truth_bundle(tmp_path)

    assert bundle.data_quality_status == "BLOCKED"
    assert "No MT5 daily evidence summary found" in bundle.data_quality_brief
    assert "reports/skills/data-quality-daily/latest.json" in bundle.source_paths()


def test_collect_truth_bundle_loads_backtest_review_skill_output(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "status": "BLOCKED",
            "brief": "Backtest review is BLOCKED. No reviewed candidate is approved.",
        },
    )

    bundle = collect_truth_bundle(tmp_path)

    assert bundle.backtest_review_status == "BLOCKED"
    assert "No reviewed candidate is approved" in bundle.backtest_review_brief
    assert "reports/skills/backtest-review/latest.json" in bundle.source_paths()


def test_collect_truth_bundle_loads_support_triage_skill_output(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "support-triage" / "latest.json",
        {
            "status": "BLOCKED",
            "brief": "Support triage is BLOCKED. No local support ticket source found.",
        },
    )

    bundle = collect_truth_bundle(tmp_path)

    assert bundle.support_triage_status == "BLOCKED"
    assert "No local support ticket source found" in bundle.support_triage_brief
    assert "reports/skills/support-triage/latest.json" in bundle.source_paths()

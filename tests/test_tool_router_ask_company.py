from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_tool_router_ask_company_returns_truth_grounded_answer(tmp_path: Path) -> None:
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

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "ask_company",
            "--question",
            "What needs me today?",
            "--root",
            str(tmp_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert "company is AMBER" in payload["answer"]
    assert "reports/phase3_holding_latest.json" in payload["sources"]


def test_tool_router_ask_company_defaults_to_conversational_text(tmp_path: Path) -> None:
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

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "ask_company",
            "--question",
            "What needs me today?",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    assert completed.stdout.startswith("You")
    assert '"ok"' not in completed.stdout


def test_tool_router_persona_chat_answers_free_text(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "skill": "backtest-review",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Backtest review is BLOCKED. No out-of-sample evidence.",
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "persona_chat",
            "--persona",
            "risk",
            "--message",
            "Can this strategy move forward?",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["persona"] == "risk-officer"
    assert payload["no_model_calls"] is True
    assert payload["truth_packet"]["policy"]["allowed_claim_source"] == "truth_packet_only"
    assert payload["verbalizer"]["provider"] == "deterministic_fallback"
    assert "I object" in payload["answer"]
    assert "reports/skills/backtest-review/latest.json" in payload["sources"]


def test_tool_router_nanoclaw_shadow_write_consumes_local_inbox(tmp_path: Path) -> None:
    inbox_path = tmp_path / "state" / "nanoclaw_shadow_inbox.jsonl"
    inbox_path.parent.mkdir(parents=True, exist_ok=True)
    inbox_path.write_text(
        json.dumps(
            {
                "type": "nanoclaw_shadow_request",
                "packet_id": "packet_1",
                "packet": {
                    "packet_id": "packet_1",
                    "persona": "chief-of-staff",
                    "intent": "role",
                    "evidence": [],
                    "unknowns": [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "nanoclaw_shadow_write",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["packet_id"] == "packet_1"
    assert (tmp_path / "state" / "nanoclaw_shadow_outbox.jsonl").exists()


def test_tool_router_risk_aggregate_daily_writes_skill_artifacts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "phase3_holding_latest.json",
        {
            "generated_at_utc": "2026-05-09T12:00:00+00:00",
            "company_scorecard": {
                "status": "GREEN",
                "risks": [],
                "actions": [],
            },
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "risk_aggregate_daily",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["skill"] == "risk-aggregate-daily"
    assert (tmp_path / payload["markdown_path"]).exists()


def test_tool_router_data_quality_daily_writes_skill_artifacts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "mt5-agentic-desk" / "logs" / "evidence" / "daily_summary_2026-05-09.json",
        {"date": "2026-05-09", "total_decisions": 3},
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "data_quality_daily",
            "--root",
            str(tmp_path),
            "--as-of",
            "2026-05-09",
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["skill"] == "data-quality-daily"
    assert payload["status"] == "GREEN"
    assert (tmp_path / payload["markdown_path"]).exists()


def test_tool_router_backtest_review_writes_skill_artifacts(tmp_path: Path) -> None:
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
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "data-quality-daily" / "latest.json",
        {"status": "GREEN", "brief": "Trading data quality is green."},
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "backtest_review",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["skill"] == "backtest-review"
    assert payload["status"] == "BLOCKED"
    assert (tmp_path / payload["markdown_path"]).exists()


def test_tool_router_support_triage_writes_skill_artifacts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "state" / "support_tickets.json",
        {
            "tickets": [
                {
                    "id": "ticket_feature",
                    "subject": "Feature request",
                    "body": "Can you add MyForexFunds rules?",
                }
            ]
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "support_triage",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["skill"] == "support-triage"
    assert payload["status"] == "AMBER"
    assert (tmp_path / payload["markdown_path"]).exists()


def test_tool_router_portfolio_retro_weekly_writes_skill_artifacts(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "GREEN",
            "owner_need": "none",
            "brief": "Company is green.",
        },
    )

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/tool_router.py",
            "portfolio_retro_weekly",
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["skill"] == "portfolio-retro-weekly"
    assert payload["status"] == "GREEN"
    assert (tmp_path / payload["markdown_path"]).exists()

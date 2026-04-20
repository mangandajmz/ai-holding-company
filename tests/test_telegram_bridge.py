from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from telegram_bridge import TelegramBridge  # noqa: E402


def test_authorized_rejects_missing_user_id_when_user_allowlist_configured() -> None:
    bridge = TelegramBridge.__new__(TelegramBridge)
    bridge.allowed_chat_ids = set()
    bridge.allowed_user_ids = {12345}

    assert bridge._authorized(chat_id=999, user_id=None) is False


def test_authorized_accepts_matching_chat_and_user() -> None:
    bridge = TelegramBridge.__new__(TelegramBridge)
    bridge.allowed_chat_ids = {777}
    bridge.allowed_user_ids = {12345}

    assert bridge._authorized(chat_id=777, user_id=12345) is True


def _build_bridge() -> TelegramBridge:
    bridge = TelegramBridge.__new__(TelegramBridge)
    bridge.allowed_chat_ids = set()
    bridge.allowed_user_ids = set()
    bridge.bot_ids = {"mt5_desk", "polymarket"}
    bridge.website_ids = {"freeghosttools", "freetraderhub_research"}
    bridge.phase3_enabled = True
    bridge.config = {
        "trading_bots": [
            {"id": "mt5_desk", "name": "MT5 Agentic Trading Desk"},
            {"id": "polymarket", "name": "Polymarket Copy Trading Bot"},
        ],
        "websites": [
            {"id": "freeghosttools", "name": "Free Ghost Tools"},
            {"id": "freetraderhub_research", "name": "FreeTraderHub Research Team"},
        ],
    }
    bridge._load_latest_daily_brief = lambda: {
        "summary": {
            "pnl_total": -7.5,
            "trades_total": 0,
            "error_lines_total": 11,
            "websites_up": 3,
            "websites_total": 3,
        },
        "bots": [
            {
                "id": "mt5_desk",
                "name": "MT5 Agentic Trading Desk",
                "status": "attention",
                "pnl_total": 0.0,
                "trades_total": 0,
                "error_lines_total": 6,
                "health_command": {"ok": True, "return_code": 0},
                "report_payload": {"headline": "0/0 trading cycles complete in 24h; no-trade cycles=0."},
            },
            {
                "id": "polymarket",
                "name": "Polymarket Copy Trading Bot",
                "status": "attention",
                "pnl_total": -7.5,
                "trades_total": 0,
                "error_lines_total": 5,
            },
        ],
        "websites": [
            {"id": "freeghosttools", "name": "Free Ghost Tools", "ok": True, "status_code": 200, "latency_ms": 190, "probe_mode": "system_proxy"},
        ],
        "alerts": [
            "mt5_desk: report flagged attention state.",
            "polymarket: remote sync issue - 2 required remote file(s) failed to sync.",
        ],
    }

    def _report_loader(filename: str) -> dict[str, Any] | None:
        reports: dict[str, dict[str, Any]] = {
            "phase2_divisions_latest.json": {
                "divisions": [
                    {
                        "division": "trading",
                        "status": "red",
                        "scorecard": {
                            "status": "RED",
                            "items": [
                                {
                                    "metric": "MT5 cycle freshness",
                                    "actual": "3.7d",
                                    "target": "<= 180m",
                                    "status": "RED",
                                },
                                {
                                    "metric": "Polymarket data freshness",
                                    "actual": "n/a",
                                    "target": "<= 72h",
                                    "status": "AMBER",
                                },
                            ],
                            "actions": [
                                "Restart MT5 scheduler and verify trading/research cycles resume.",
                                "Verify polymarket remote sync and confirm settlement timestamps are being written.",
                            ],
                        },
                    },
                    {
                        "division": "websites",
                        "status": "amber",
                        "scorecard": {
                            "status": "AMBER",
                            "items": [
                                {
                                    "metric": "Research brief freshness",
                                    "actual": "n/a",
                                    "target": "<= 8d",
                                    "status": "AMBER",
                                }
                            ],
                            "actions": ["Run weekly research pipeline."],
                        },
                    },
                ]
            },
            "phase3_holding_latest.json": {
                "company_scorecard": {
                    "status": "RED",
                    "items": [
                        {
                            "metric": "Division GREEN ratio",
                            "actual": "33.3%",
                            "target": ">= 67%",
                            "status": "RED",
                        }
                    ],
                },
                "base_summary": {"pnl_total": -7.5, "trades_total": 0},
                "base_alerts": ["mt5_desk stale"],
            },
        }
        return reports.get(filename)

    bridge._load_latest_report_json = _report_loader
    bridge._run_tool_router = lambda args: {"ok": True, "payload": {"ok": True}, "args": args}
    return bridge


def test_freetext_trading_question_returns_structured_answer() -> None:
    bridge = _build_bridge()

    response = bridge._answer_freetext("What's the status of trading?")

    assert "Trading status: RED" in response
    assert "Main issues:" in response
    assert "[context]" not in response
    assert "Restart MT5 scheduler" in response


def test_freetext_bot_question_matches_normalized_name() -> None:
    bridge = _build_bridge()

    response = bridge._answer_freetext("What's happening with mt5 desk?")

    assert "MT5 Agentic Trading Desk status: ATTENTION" in response
    assert "Latest report: 0/0 trading cycles complete in 24h; no-trade cycles=0." in response
    assert "[context]" not in response


def test_freetext_commercial_question_returns_clear_message_when_not_available() -> None:
    bridge = _build_bridge()
    bridge._load_latest_report_json = lambda _filename: None

    response = bridge._answer_freetext("/commercial")

    assert "Commercial status is not wired cleanly into the chat bridge yet." in response
    assert "[context]" not in response


def test_freetext_direction_is_logged_cleanly() -> None:
    bridge = _build_bridge()
    calls: list[list[str]] = []

    def _run_tool_router(args: list[str]) -> dict[str, Any]:
        calls.append(args)
        return {"ok": True, "payload": {"ok": True}}

    bridge._run_tool_router = _run_tool_router

    response = bridge._answer_freetext("Focus on trading first and ignore website issues for now")

    assert "Direction logged." in response
    assert calls == [["log_direction", "--text", "Focus on trading first and ignore website issues for now", "--source", "telegram_freetext"]]


def test_handle_text_ceo_alias_returns_company_summary() -> None:
    bridge = _build_bridge()

    response = bridge.handle_text("CEO")

    assert "Company status: RED" in response
    assert "Priority issues:" in response
    assert "Division GREEN ratio" in response


def test_handle_text_daily_brief_alias_returns_company_summary() -> None:
    bridge = _build_bridge()

    response = bridge.handle_text("daily_brief")

    assert "Company status: RED" in response
    assert "PnL: $-7.50" in response

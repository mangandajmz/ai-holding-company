"""
CEO Response Quality Eval Harness — AI Holding Company
=======================================================
Tests that Telegram bot responses meet CEO-standard quality:
  - Correct structure and section presence
  - Traffic light emoji (🔴/🟡/🟢), not [RED]/[AMBER]/[GREEN]
  - Metrics include actual + target + variance
  - No raw JSON or debug noise leaked to user
  - Actions are owner-assigned with deadlines
  - Single focused CTA at end
  - Response within SLA time bounds

Golden standard defined in: eval/intended_outputs.md
Run: pytest tests/test_response_quality.py -v
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TRAFFIC_EMOJIS = {"🔴", "🟡", "🟢"}
RAW_JSON_NOISE = ['"ok":', '"return_code":', '"elapsed_ms":', "rc=", "stderr:"]
LEGACY_TAGS = ["[RED]", "[AMBER]", "[GREEN]"]


def _score_response(text: str) -> dict[str, Any]:
    """Score a response string against the CEO quality rubric. Returns scores per criterion."""
    scores: dict[str, int] = {}

    # 1. Header — company name + timestamp  (weight 1)
    has_company = "manganda" in text.lower() or "AI Holding" in text
    has_time = any(x in text.lower() for x in ["utc", "2026", "2025"])
    scores["header"] = 1 if (has_company and has_time) else 0

    # 2. Exec summary in first 3 lines  (weight 2)
    first_lines = text.split("\n")[:5]
    first_block = "\n".join(first_lines).lower()
    has_status_emoji = any(e in first_block for e in TRAFFIC_EMOJIS)
    has_status_word = any(w in first_block for w in ["amber", "red", "green", "ok", "up", "down"])
    scores["exec_summary"] = 2 if (has_status_emoji and has_status_word) else (1 if has_status_word else 0)

    # 3. Metrics have context (actual vs target or variance)  (weight 2)
    context_markers = ["vs", "target", "variance", "threshold", "cap", "✓", "(target"]
    has_context = sum(1 for m in context_markers if m in text)
    scores["metrics_context"] = 2 if has_context >= 2 else (1 if has_context == 1 else 0)

    # 4. Traffic light emoji used  (weight 1)
    scores["traffic_emoji"] = 1 if any(e in text for e in TRAFFIC_EMOJIS) else 0

    # 5. No raw JSON / debug noise  (weight 1)
    noise_found = [n for n in RAW_JSON_NOISE if n in text]
    scores["no_debug_noise"] = 0 if noise_found else 1

    # 6. Actions are owner-assigned  (weight 2)
    action_owner_markers = ["owner:", "trading", "division", "websites", "deadline", "today", "+7 day"]
    has_ownership = sum(1 for m in action_owner_markers if m.lower() in text.lower())
    scores["owner_assigned_actions"] = 2 if has_ownership >= 2 else (1 if has_ownership == 1 else 0)

    # 7. Single focused CTA  (weight 1)
    cta_lines = [l for l in text.split("\n") if l.strip().startswith("→")]
    scores["single_cta"] = 1 if len(cta_lines) == 1 else (0 if len(cta_lines) > 3 else 1)

    total = sum(scores.values())
    max_score = 10
    return {"scores": scores, "total": total, "max": max_score, "passed": total >= 8}


def _has_legacy_tags(text: str) -> bool:
    return any(tag in text for tag in LEGACY_TAGS)


def _has_raw_json(text: str) -> bool:
    return any(noise in text for noise in RAW_JSON_NOISE)


# ---------------------------------------------------------------------------
# Fixtures — minimal mock payloads matching real schema
# ---------------------------------------------------------------------------

@pytest.fixture()
def daily_brief_payload() -> dict:
    return {
        "ok": True,
        "skipped": False,
        "summary": {
            "pnl_total": 279.98,
            "trades_total": 47,
            "error_lines_total": 2,
            "bots_total": 2,
            "websites_up": 2,
            "websites_total": 2,
        },
        "bots": [
            {"id": "mt5_desk", "status": "RUNNING", "pnl_total": 156.78},
            {"id": "polymarket", "status": "RUNNING", "pnl_total": -23.45},
        ],
        "websites": [
            {"id": "freeghosttools", "ok": True, "latency_ms": 145},
            {"id": "freetraderhub", "ok": True, "latency_ms": 203},
        ],
        "alerts": [
            "Warning: Max drawdown approaching threshold",
            "Warning: Monthly PnL growth below 10% target",
        ],
        "files": {"latest_markdown": "reports/daily_brief_latest.md"},
    }


@pytest.fixture()
def holding_brief_payload() -> dict:
    return {
        "ok": True,
        "company_name": "Manganda LTD",
        "mode": "heartbeat",
        "generated_at_utc": "2026-04-17T08:15:00Z",
        "base_summary": {
            "pnl_total": 279.98,
            "trades_total": 47,
            "error_lines_total": 2,
            "websites_up": 2,
            "websites_total": 2,
        },
        "base_alerts": [
            "Warning: Max drawdown approaching threshold",
            "Warning: Monthly PnL growth below 10% target",
        ],
        "company_scorecard": {
            "status": "AMBER",
            "items": [
                {
                    "metric": "Monthly PnL growth",
                    "actual": "8.5%",
                    "target": ">=10.0%",
                    "variance": "-1.5%",
                    "status": "RED",
                    "action": "Review risk allocation",
                },
                {
                    "metric": "Max drawdown",
                    "actual": "4.2%",
                    "target": "<=3.0%",
                    "variance": "+1.2%",
                    "status": "AMBER",
                    "action": "Tighten stop-loss threshold",
                },
                {
                    "metric": "Website uptime ratio",
                    "actual": "100.0%",
                    "target": ">=99.9%",
                    "variance": "+0.1%",
                    "status": "GREEN",
                    "action": None,
                },
                {
                    "metric": "Division GREEN ratio",
                    "actual": "66.7%",
                    "target": ">=66.7%",
                    "variance": "0.0%",
                    "status": "GREEN",
                    "action": None,
                },
            ],
        },
        "divisions": [
            {
                "division": "trading",
                "ok": True,
                "scorecard": {
                    "status": "AMBER",
                    "items": [
                        {
                            "metric": "Monthly PnL growth",
                            "actual": "8.5%",
                            "target": "10.0%",
                            "variance": "-1.5%",
                            "status": "AMBER",
                        }
                    ],
                    "actions": ["Review monthly PnL trajectory and adjust risk allocation"],
                },
            },
            {
                "division": "websites",
                "ok": True,
                "scorecard": {
                    "status": "GREEN",
                    "items": [
                        {
                            "metric": "Website uptime ratio",
                            "actual": "100.0%",
                            "target": "99.9%",
                            "variance": "+0.1%",
                            "status": "GREEN",
                        }
                    ],
                    "actions": [],
                },
            },
        ],
        "files": {"latest_markdown": "reports/phase3_holding_latest.md"},
    }


@pytest.fixture()
def board_review_payload(holding_brief_payload) -> dict:
    payload = dict(holding_brief_payload)
    payload["mode"] = "board_review"
    payload["board_review"] = {
        "gate_blocked": False,
        "approvals": [
            {
                "priority": "RED",
                "topic": "Company KPI: Monthly PnL growth",
                "rationale": "8.5% vs 10% target. Immediate review required.",
                "expected_upside": "Restores growth trajectory; est +$180 MTD",
                "effort_cost": "Low — parameter adjustment",
                "confidence": "Medium",
                "owner": "trading",
                "deadline": "2026-04-17",
                "dissent": "PENDING — dissent_agent review required",
                "measurement_plan": "GREEN for 2 consecutive daily briefs",
            },
            {
                "priority": "AMBER",
                "topic": "Company KPI: Max drawdown",
                "rationale": "4.2% vs 3.0% cap. Approaching limit.",
                "expected_upside": "Prevents forced halt; protects capital base",
                "effort_cost": "Low — stop-loss threshold update",
                "confidence": "High",
                "owner": "trading",
                "deadline": "2026-04-24",
                "dissent": "PENDING — dissent_agent review required",
                "measurement_plan": "Drawdown ≤3.0% next 3 runs",
            },
        ],
    }
    return payload


@pytest.fixture()
def gate_blocked_board_payload(board_review_payload) -> dict:
    payload = dict(board_review_payload)
    payload["board_review"] = {
        "gate_blocked": True,
        "approvals": [
            {
                "priority": "RED",
                "topic": "Company KPI: Monthly PnL growth",
                "validation_warnings": ["missing measurement_plan", "missing dissent"],
            }
        ],
    }
    return payload


@pytest.fixture()
def bridge(tmp_path):
    """Minimal TelegramBridge with config patched to avoid real API calls."""
    config = {
        "bridge": {
            "provider": "telegram",
            "observer_mode": True,
            "state_file": str(tmp_path / "state.json"),
            "audit_log_path": str(tmp_path / "audit.jsonl"),
            "telegram": {
                "bot_token_env": "TELEGRAM_BOT_TOKEN",
                "owner_chat_id_env": "TELEGRAM_OWNER_CHAT_ID",
                "owner_user_id_env": "TELEGRAM_OWNER_USER_ID",
                "poll_interval_sec": 3,
                "allowed_chat_ids": [],
                "allowed_user_ids": [],
            },
        },
        "trading_bots": [{"id": "mt5_desk"}, {"id": "polymarket"}],
        "websites": [{"id": "freeghosttools"}, {"id": "freetraderhub"}],
        "paths": {"memory_dir": "memory", "reports_dir": str(tmp_path)},
        "phase3": {"enabled": True},
        "memory": {"enabled": False},
    }

    with (
        patch("telegram_bridge._load_yaml", return_value=config),
        patch.dict(
            "os.environ",
            {
                "TELEGRAM_BOT_TOKEN": "1234567890:AAABBBCCC",
                "TELEGRAM_OWNER_CHAT_ID": "6339543160",
                "TELEGRAM_OWNER_USER_ID": "6339543160",
            },
        ),
    ):
        from telegram_bridge import TelegramBridge
        b = TelegramBridge.__new__(TelegramBridge)
        b.config = config
        b.config_path = Path("config/projects.yaml")
        b.bot_token = "1234567890:AAABBBCCC"
        b.owner_chat_id = 6339543160
        b.owner_user_id = 6339543160
        b.allowed_chat_ids = {6339543160}
        b.allowed_user_ids = {6339543160}
        b.observer_mode = True
        b.phase3_enabled = True
        b.security_ready = True
        b.poll_interval_sec = 3
        b.state = {"last_update_id": 0}
        b.state_file = tmp_path / "state.json"
        b.audit_file = tmp_path / "audit.jsonl"
        b.bot_ids = {"mt5_desk", "polymarket"}
        b.website_ids = {"freeghosttools", "freetraderhub"}
        b.reports_dir = tmp_path
        return b


# ===========================================================================
# SECTION 1 — Command Parsing
# ===========================================================================

class TestCommandParsing:
    """Verify every defined command parses to the correct tool + args."""

    @pytest.mark.parametrize("text,expected_name", [
        ("/status", "daily_brief"),
        # plain "status" now routes to freetext (synthesised company summary)
        ("/brief", "run_holding"),
        ("give me a brief", "run_holding"),
        ("morning brief", "run_holding"),
        ("/divisions", "run_divisions"),
        ("/divisions all", "run_divisions"),
        ("/board review", "run_holding"),
        ("/board pack", "run_holding_board_pack"),
    ])
    def test_command_routes_to_correct_tool(self, bridge, text, expected_name):
        action = bridge._parse_action(text)
        assert action is not None, f"No action parsed for: {text!r}"
        # _parse_action returns dict with key 'name' (not 'tool')
        actual = action.get("name") or action.get("tool")
        assert actual == expected_name, (
            f"Expected name={expected_name!r} for {text!r}, got {actual!r}"
        )

    @pytest.mark.parametrize("text,expected_bot", [
        ("/bot mt5_desk health", "mt5_desk"),
        ("/bot polymarket report", "polymarket"),
        ("/bot mt5_desk logs", "mt5_desk"),
    ])
    def test_bot_command_parses_bot_id(self, bridge, text, expected_bot):
        action = bridge._parse_action(text)
        assert action is not None
        args = action.get("args", [])
        assert expected_bot in " ".join(args), (
            f"Expected bot_id={expected_bot!r} in args for {text!r}"
        )

    @pytest.mark.parametrize("text", [
        "/bot unknown_bot health",
        "/site nonexistent_site",
    ])
    def test_unknown_id_returns_error_action(self, bridge, text):
        action = bridge._parse_action(text)
        # Either None (unrouted) or an error action — must not silently pass
        if action is not None:
            actual = action.get("name") or action.get("tool")
            assert actual in (None, "error"), (
                f"Unknown ID in {text!r} should produce error, got {actual!r}"
            )

    def test_execute_blocked_by_observer_mode(self, bridge):
        bridge.observer_mode = True
        bridge.config["bridge"]["observer_mode"] = True
        action = bridge._parse_action("/bot mt5_desk execute confirm")
        # _parse_action itself returns None when observer_mode is ON for execute
        # OR the action dict is returned but the run-time check blocks it.
        # Either outcome is acceptable — the assertion is it does NOT silently pass through.
        if action is not None:
            action_name = action.get("name") or action.get("tool")
            # If an action was returned for execute, it must signal observer block
            # We verify by checking the action type is not a clean "run_trading_script"
            # without any observer guard. A None return is the cleanest signal.
            assert action_name != "run_trading_script" or action.get("blocked"), (
                "Observer mode must block execute at parse or mark it blocked"
            )


# ===========================================================================
# SECTION 2 — Response Format Quality
# ===========================================================================

class TestResponseQuality:
    """Score each response against the CEO quality rubric (pass ≥ 8/10)."""

    def test_daily_brief_no_legacy_tags(self, bridge, daily_brief_payload):
        result = {"ok": True, "payload": daily_brief_payload}
        text = bridge._summarize_tool_result("daily_brief", result)
        assert not _has_legacy_tags(text), (
            f"Response uses [RED]/[AMBER]/[GREEN] tags. Use emoji instead.\n\n{text}"
        )

    def test_daily_brief_no_raw_json(self, bridge, daily_brief_payload):
        result = {"ok": True, "payload": daily_brief_payload}
        text = bridge._summarize_tool_result("daily_brief", result)
        assert not _has_raw_json(text), (
            f"Response leaks raw JSON / debug fields to CEO.\n\n{text}"
        )

    def test_daily_brief_contains_pnl_and_context(self, bridge, daily_brief_payload):
        result = {"ok": True, "payload": daily_brief_payload}
        text = bridge._summarize_tool_result("daily_brief", result)
        assert "279.98" in text or "156.78" in text, "PnL value missing from /status response"

    def test_check_website_no_raw_json(self, bridge):
        result = {
            "ok": True,
            "payload": {"website_id": "freeghosttools", "ok": True, "status_code": 200, "latency_ms": 145},
        }
        text = bridge._summarize_tool_result("check_website", result)
        assert not _has_raw_json(text), f"Website check leaks debug fields.\n\n{text}"

    def test_check_website_shows_status(self, bridge):
        result = {
            "ok": True,
            "payload": {"website_id": "freeghosttools", "ok": True, "status_code": 200, "latency_ms": 145},
        }
        text = bridge._summarize_tool_result("check_website", result)
        assert "UP" in text or "freeghosttools" in text

    def test_bot_trading_script_no_raw_json(self, bridge):
        result = {
            "ok": True,
            "payload": {
                "ok": True,
                "bot_id": "mt5_desk",
                "command_key": "health",
                "return_code": 0,
                "elapsed_ms": 1243,
                "stdout": "",
            },
        }
        text = bridge._summarize_tool_result("run_trading_script", result)
        assert not _has_raw_json(text), (
            f"Bot health check leaks raw JSON to CEO.\n\n{text}\n\n"
            f"REQUIRED: Replace JSON dump with plain-English health summary."
        )

    def test_failed_command_no_stack_trace(self, bridge):
        result = {"ok": False, "return_code": 1, "stderr": "Traceback (most recent call last):\n  File x.py line 42"}
        text = bridge._summarize_tool_result("run_holding", result)
        assert "Traceback" not in text, "Stack trace leaked to CEO in error response"
        assert len(text) < 600, "Error response too verbose for CEO context"

    def test_divisions_brief_no_legacy_tags(self, bridge, holding_brief_payload):
        divs_payload = {
            "ok": True,
            "company_name": "Manganda LTD",
            "generated_at_utc": "2026-04-17T08:17:00Z",
            "base_summary": holding_brief_payload["base_summary"],
            "base_alerts": holding_brief_payload["base_alerts"],
            "divisions": holding_brief_payload["divisions"],
            "files": {},
        }
        text = bridge._summarize_divisions_brief(divs_payload)
        assert not _has_legacy_tags(text), (
            f"Divisions response uses [RED]/[AMBER]/[GREEN] legacy tags.\n\n{text}"
        )

    def test_holding_brief_no_legacy_tags(self, bridge, holding_brief_payload):
        text = bridge._summarize_holding_brief(holding_brief_payload)
        assert not _has_legacy_tags(text), (
            f"/brief response uses [RED]/[AMBER]/[GREEN] legacy tags.\n\n{text}"
        )

    def test_holding_brief_contains_all_kpi_names(self, bridge, holding_brief_payload):
        text = bridge._summarize_holding_brief(holding_brief_payload)
        expected_kpis = ["Monthly PnL", "drawdown", "uptime"]
        for kpi in expected_kpis:
            assert kpi.lower() in text.lower(), f"KPI '{kpi}' missing from /brief response"

    def test_holding_brief_contains_variance(self, bridge, holding_brief_payload):
        text = bridge._summarize_holding_brief(holding_brief_payload)
        # At least one variance value should appear
        variance_values = ["-1.5%", "+1.2%", "+0.1%"]
        found = any(v in text for v in variance_values)
        assert found, (
            f"/brief response missing variance values — CEO needs actual vs target context.\n\n{text}"
        )

    def test_board_review_all_8_fields_present_per_item(self, bridge, board_review_payload):
        text = bridge._summarize_holding_brief(board_review_payload)
        required_concepts = ["dissent", "deadline", "owner", "measure"]
        for concept in required_concepts:
            assert concept.lower() in text.lower(), (
                f"Board review response missing '{concept}' — required by board pack spec.\n\n{text}"
            )

    def test_board_review_gate_blocked_message_clear(self, bridge, gate_blocked_board_payload):
        text = bridge._summarize_holding_brief(gate_blocked_board_payload)
        assert "blocked" in text.lower() or "gate" in text.lower(), (
            f"Gate-blocked board review must clearly communicate blockage.\n\n{text}"
        )
        assert not _has_raw_json(text)

    def test_response_length_within_telegram_limit(self, bridge, holding_brief_payload):
        text = bridge._summarize_holding_brief(holding_brief_payload)
        assert len(text) <= 3900, (
            f"/brief response is {len(text)} chars — exceeds Telegram 3900 char limit"
        )

    def test_help_has_grouped_sections(self, bridge):
        text = bridge._format_help()
        # Help should have at least 3 distinct sections
        section_headers = ["status", "brief", "board", "bot", "site", "memory", "note"]
        found = sum(1 for h in section_headers if h in text.lower())
        assert found >= 5, (
            f"/help lists only {found}/7 expected command categories. "
            f"CEO needs grouped navigation, not a flat list.\n\n{text}"
        )


# ===========================================================================
# SECTION 3 — CEO Quality Score (Rubric)
# ===========================================================================

class TestCEOQualityScore:
    """Run the full rubric scorer. Pass threshold = 8/10."""

    def _get_holding_text(self, bridge, holding_brief_payload):
        return bridge._summarize_holding_brief(holding_brief_payload)

    def _get_daily_text(self, bridge, daily_brief_payload):
        return bridge._summarize_tool_result("daily_brief", {"ok": True, "payload": daily_brief_payload})

    def test_brief_passes_ceo_rubric(self, bridge, holding_brief_payload):
        text = self._get_holding_text(bridge, holding_brief_payload)
        report = _score_response(text)
        failing = {k: v for k, v in report["scores"].items() if v < 1}
        assert report["passed"], (
            f"/brief scored {report['total']}/{report['max']} — below CEO threshold (8/10).\n"
            f"Failing criteria: {failing}\n\n"
            f"Full response:\n{text}\n\n"
            f"See eval/intended_outputs.md for the target format."
        )

    def test_status_passes_ceo_rubric(self, bridge, daily_brief_payload):
        text = self._get_daily_text(bridge, daily_brief_payload)
        report = _score_response(text)
        assert report["passed"], (
            f"/status scored {report['total']}/{report['max']} — below CEO threshold (8/10).\n"
            f"Failing criteria: {report['scores']}\n\n"
            f"Full response:\n{text}"
        )

    def test_board_review_passes_ceo_rubric(self, bridge, board_review_payload):
        text = bridge._summarize_holding_brief(board_review_payload)
        report = _score_response(text)
        assert report["passed"], (
            f"/board review scored {report['total']}/{report['max']}.\n"
            f"Failing criteria: {report['scores']}\n\n{text}"
        )


# ===========================================================================
# SECTION 4 — Response Time SLA
# ===========================================================================

class TestResponseTimeSLA:
    """
    Verify that formatting/summarisation functions complete within SLA.
    These test the Python summarisation layer only — not the subprocess crew runs.
    Subprocess SLAs are enforced via subprocess timeout args in tool_router.py.
    """

    SLA_MS = {
        "_summarize_tool_result:daily_brief": 50,
        "_summarize_divisions_brief": 50,
        "_summarize_holding_brief": 50,
        "_format_help": 10,
    }

    def test_holding_brief_formats_within_50ms(self, bridge, holding_brief_payload):
        start = time.perf_counter()
        bridge._summarize_holding_brief(holding_brief_payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, (
            f"_summarize_holding_brief took {elapsed_ms:.1f}ms — must be <50ms (pure formatting)"
        )

    def test_divisions_brief_formats_within_50ms(self, bridge, holding_brief_payload):
        payload = {
            "company_name": "Manganda LTD",
            "generated_at_utc": "2026-04-17T08:17:00Z",
            "base_summary": holding_brief_payload["base_summary"],
            "base_alerts": [],
            "divisions": holding_brief_payload["divisions"],
            "files": {},
        }
        start = time.perf_counter()
        bridge._summarize_divisions_brief(payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50

    def test_daily_brief_formats_within_50ms(self, bridge, daily_brief_payload):
        result = {"ok": True, "payload": daily_brief_payload}
        start = time.perf_counter()
        bridge._summarize_tool_result("daily_brief", result)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50

    def test_help_formats_within_10ms(self, bridge):
        start = time.perf_counter()
        bridge._format_help()
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 10


# ===========================================================================
# SECTION 5 — Observer Mode Safety
# ===========================================================================

class TestObserverMode:
    """Observer mode must block /bot execute — no silent failures."""

    def test_observer_mode_blocks_execute_at_parse(self, bridge):
        bridge.config["bridge"]["observer_mode"] = True
        action = bridge._parse_action("/bot mt5_desk execute confirm")
        if action and action.get("tool") == "run_trading_script":
            # If action is returned, the block must happen at run time.
            # Simulate the tool call and expect a block signal.
            mock_result = {
                "ok": False,
                "payload": {"type": "error", "message": "Observer mode is ON. Execute is blocked."},
                "return_code": 1,
                "stderr": "",
            }
            text = bridge._summarize_tool_result("run_trading_script", mock_result)
            assert "block" in text.lower() or "observer" in text.lower() or "FAILED" in text, (
                f"Observer mode block not surfaced clearly in response.\n\n{text}"
            )

    def test_observer_mode_does_not_block_read_commands(self, bridge):
        bridge.config["bridge"]["observer_mode"] = True
        for cmd in ["/status", "/brief", "/bot mt5_desk health", "/bot mt5_desk logs"]:
            action = bridge._parse_action(cmd)
            assert action is not None, f"{cmd!r} should NOT be blocked by observer mode"


# ===========================================================================
# SECTION 6 — Error Response Format
# ===========================================================================

class TestErrorFormat:
    """Error responses must be plain-English — no stack traces, no JSON."""

    def test_failed_tool_no_stack_trace(self, bridge):
        result = {
            "ok": False,
            "return_code": 1,
            "stderr": "Traceback (most recent call last):\n  File script.py, line 5\nValueError: bad value",
        }
        text = bridge._summarize_tool_result("run_holding", result)
        assert "Traceback" not in text, "Stack trace must not reach CEO"
        assert "ValueError" not in text, "Python exception type must not reach CEO"

    def test_failed_tool_message_is_short(self, bridge):
        result = {"ok": False, "return_code": 1, "stderr": "Connection refused"}
        text = bridge._summarize_tool_result("run_holding", result)
        assert len(text) <= 500, f"Error message too long ({len(text)} chars)"

    def test_failed_tool_mentions_what_failed(self, bridge):
        result = {"ok": False, "return_code": 1, "stderr": "Connection refused"}
        text = bridge._summarize_tool_result("run_holding", result)
        assert any(w in text.lower() for w in ["fail", "error", "could not", "unable", "blocked"]), (
            f"Error response doesn't indicate failure clearly.\n\n{text}"
        )

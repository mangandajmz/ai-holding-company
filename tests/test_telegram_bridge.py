"""
Telegram bridge UX tests — AI Holding Company
==============================================
Tests authentication, intent detection, and structured freetext responses.
Run: python -m pytest tests/test_telegram_bridge.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def bridge(tmp_path):
    """TelegramBridge instance with no real API calls, memory disabled."""
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


# ---------------------------------------------------------------------------
# Fixtures — sample report payloads
# ---------------------------------------------------------------------------

@pytest.fixture()
def phase2_divisions_report():
    return {
        "ok": True,
        "divisions": [
            {
                "division": "trading",
                "ok": True,
                "scorecard": {
                    "status": "AMBER",
                    "items": [
                        {"metric": "Monthly PnL growth", "actual": "8.5%", "target": "10.0%", "status": "AMBER"},
                        {"metric": "Win rate", "actual": "62%", "target": "55%", "status": "GREEN"},
                    ],
                    "actions": ["Review risk allocation", "Tighten drawdown cap"],
                },
            },
            {
                "division": "websites",
                "ok": True,
                "scorecard": {
                    "status": "GREEN",
                    "items": [
                        {"metric": "Uptime ratio", "actual": "100%", "target": "99.9%", "status": "GREEN"},
                    ],
                    "actions": [],
                },
            },
        ],
    }


@pytest.fixture()
def phase3_holding_report():
    return {
        "ok": True,
        "company_name": "Manganda LTD",
        "mode": "heartbeat",
        "generated_at_utc": "2026-04-17T08:00:00Z",
        "base_summary": {"pnl_total": 279.98, "trades_total": 47},
        "base_alerts": ["Max drawdown approaching threshold"],
        "company_scorecard": {
            "status": "AMBER",
            "items": [
                {"metric": "Monthly PnL growth", "actual": "8.5%", "target": "10.0%", "status": "AMBER"},
                {"metric": "Website uptime", "actual": "100%", "target": "99.9%", "status": "GREEN"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# 1. Auth: missing user ID rejected when allowlist exists
# ---------------------------------------------------------------------------

def test_auth_rejects_unknown_user_id(bridge):
    """When user allowlist is set, a user_id not in the list must be rejected."""
    bridge.allowed_user_ids = {6339543160}  # only owner allowed
    bridge.allowed_chat_ids = {6339543160}

    # A valid chat_id but wrong user_id
    result = bridge._authorized(chat_id=6339543160, user_id=9999999)
    assert result is False, "Unknown user_id must be rejected when allowlist is configured"


# ---------------------------------------------------------------------------
# 2. Auth: matching chat + user is accepted
# ---------------------------------------------------------------------------

def test_auth_accepts_matching_chat_and_user(bridge):
    """Both chat_id and user_id in their respective allowlists → authorised."""
    bridge.allowed_chat_ids = {6339543160}
    bridge.allowed_user_ids = {6339543160}

    result = bridge._authorized(chat_id=6339543160, user_id=6339543160)
    assert result is True, "Owner chat+user must be accepted"


# ---------------------------------------------------------------------------
# 3. Free-text trading question — structured answer, no [context]
# ---------------------------------------------------------------------------

def test_trading_question_structured_no_context(bridge, tmp_path, phase2_divisions_report):
    """Trading question reads cached Phase 2 report and returns structured answer."""
    report_path = tmp_path / "phase2_divisions_latest.json"
    report_path.write_text(json.dumps(phase2_divisions_report), encoding="utf-8")

    text = bridge._answer_freetext("how is trading doing?")

    assert "[context]" not in text, "Must not emit raw [context] header"
    assert "Trading status" in text, "Must include 'Trading status:' line"
    assert "AMBER" in text or "GREEN" in text or "RED" in text, "Must include a status value"


# ---------------------------------------------------------------------------
# 4. Free-text bot question — resolves "mt5 desk" → "mt5_desk"
# ---------------------------------------------------------------------------

def test_bot_question_resolves_friendly_name(bridge):
    """'mt5 desk' (spaced) must resolve to the 'mt5_desk' bot ID."""
    fake_result = {
        "ok": True,
        "return_code": 0,
        "payload": {"bot_id": "mt5_desk", "command_key": "health", "ok": True},
    }
    with patch.object(bridge, "_run_tool_router", return_value=fake_result) as mock_run:
        text = bridge._answer_freetext("how is mt5 desk doing?")

    assert "[context]" not in text
    # Should have called health on mt5_desk
    mock_run.assert_called_once()
    args_used = mock_run.call_args[0][0]
    assert "mt5_desk" in args_used, f"Expected mt5_desk in tool args, got {args_used}"
    assert "Mt5 Desk status" in text or "mt5_desk" in text.lower() or "Mt5" in text


# ---------------------------------------------------------------------------
# 5. /commercial returns clear fallback, no [context]
# ---------------------------------------------------------------------------

def test_commercial_returns_fallback_no_context(bridge):
    """/commercial and 'commercial' must return a clear fallback, not a memory dump."""
    for input_text in ("/commercial", "commercial"):
        text = bridge._answer_freetext(input_text)
        assert "[context]" not in text, f"[context] must not appear for input: {input_text!r}"
        assert "commercial" in text.lower(), "Response should mention commercial"
        assert len(text) < 400, "Fallback should be concise"


# ---------------------------------------------------------------------------
# 6. Free-text direction gets logged, returns clean confirmation
# ---------------------------------------------------------------------------

def test_direction_gets_logged_cleanly(bridge):
    """An imperative direction must be logged via log_direction and confirmed."""
    logged: list[list[str]] = []

    def fake_tool_router(args, timeout_sec=300):
        logged.append(args)
        return {"ok": True, "return_code": 0, "payload": {"ok": True}, "stdout": "", "stderr": ""}

    with patch.object(bridge, "_run_tool_router", side_effect=fake_tool_router):
        response = bridge._answer_freetext("Focus on trading first and ignore website issues for now")

    assert "[context]" not in response
    assert "logged" in response.lower() or "direction" in response.lower(), (
        f"Response should confirm the direction was logged, got: {response!r}"
    )
    # Verify log_direction was called
    assert any("log_direction" in args for args in logged), (
        f"log_direction was not called. Tool calls: {logged}"
    )


# ---------------------------------------------------------------------------
# 7. "CEO" returns company summary
# ---------------------------------------------------------------------------

def test_ceo_returns_company_summary(bridge, tmp_path, phase3_holding_report):
    """Typing 'CEO' should return a synthesised company status summary."""
    report_path = tmp_path / "phase3_holding_latest.json"
    report_path.write_text(json.dumps(phase3_holding_report), encoding="utf-8")

    text = bridge._answer_freetext("CEO")

    assert "[context]" not in text
    assert "Company status" in text, f"Expected 'Company status' in response, got:\n{text}"
    assert "PnL" in text or "Trades" in text, "Company summary must include financial metrics"


# ---------------------------------------------------------------------------
# 8. "daily_brief" returns company summary
# ---------------------------------------------------------------------------

def test_daily_brief_text_returns_company_summary(bridge, tmp_path, phase3_holding_report):
    """Typing 'daily_brief' (without slash) should return a company summary, not raw tool output."""
    report_path = tmp_path / "phase3_holding_latest.json"
    report_path.write_text(json.dumps(phase3_holding_report), encoding="utf-8")

    # Via handle_text — verify _parse_action routes it to freetext
    action = bridge._parse_action("daily_brief")
    assert action.get("type") == "freetext", (
        f"'daily_brief' should route to freetext, got type={action.get('type')!r}"
    )

    text = bridge._answer_freetext("daily_brief")

    assert "[context]" not in text
    assert "Company status" in text, f"Expected company summary, got:\n{text}"


# ---------------------------------------------------------------------------
# Bonus: _detect_intent sanity checks
# ---------------------------------------------------------------------------

class TestDetectIntent:
    def test_commercial_detected(self, bridge):
        assert bridge._detect_intent("commercial") == "commercial"
        assert bridge._detect_intent("/commercial") == "commercial"

    def test_direction_detected(self, bridge):
        intent = bridge._detect_intent("focus on trading first and ignore website issues for now")
        assert intent == "direction"

    def test_question_not_direction(self, bridge):
        intent = bridge._detect_intent("how is trading doing?")
        assert intent != "direction"

    def test_bot_entity_resolved(self, bridge):
        intent = bridge._detect_intent("how is mt5 desk doing?")
        assert intent == "bot:mt5_desk", f"Expected bot:mt5_desk, got {intent!r}"

    def test_site_entity_resolved(self, bridge):
        intent = bridge._detect_intent("is freeghosttools up?")
        assert intent == "site:freeghosttools", f"Expected site:freeghosttools, got {intent!r}"

    def test_trading_question(self, bridge):
        assert bridge._detect_intent("what is our pnl today?") == "trading"

    def test_company_question(self, bridge):
        intent = bridge._detect_intent("ceo")
        assert intent == "company", f"Expected company, got {intent!r}"

    def test_status_maps_to_company(self, bridge):
        intent = bridge._detect_intent("status")
        assert intent == "company"


# ---------------------------------------------------------------------------
# Bonus: _resolve_entity_id fuzzy matching
# ---------------------------------------------------------------------------

class TestResolveEntityId:
    def test_exact_match(self, bridge):
        assert bridge._resolve_entity_id("mt5_desk health", bridge.bot_ids) == "mt5_desk"

    def test_space_separated(self, bridge):
        assert bridge._resolve_entity_id("how is mt5 desk doing", bridge.bot_ids) == "mt5_desk"

    def test_no_match(self, bridge):
        assert bridge._resolve_entity_id("polymarket is great", bridge.website_ids) is None

    def test_site_match(self, bridge):
        assert bridge._resolve_entity_id("check freeghosttools", bridge.website_ids) == "freeghosttools"

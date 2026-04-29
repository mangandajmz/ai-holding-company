"""Sprint 1 MD Agent tests — watchdog, day-count, brief format, task-track.

Run: python -m pytest tests/test_sprint1_md_agent.py -q
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_issue_log(tmp_path):
    return tmp_path / "md_issue_log.json"


@pytest.fixture()
def tmp_task_log(tmp_path):
    return tmp_path / "md_task_log.json"


@pytest.fixture()
def bridge(tmp_path):
    """Minimal TelegramBridge with no API calls, using tmp state."""
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
        "websites": [{"id": "freetraderhub"}],
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
        b.website_ids = {"freetraderhub"}
        b.reports_dir = tmp_path
        return b


# ---------------------------------------------------------------------------
# 1. Scheduler watchdog
# ---------------------------------------------------------------------------


def test_watchdog_no_baseline(bridge):
    """Watchdog returns None when there is no prior brief timestamp — don't false-alarm."""
    bridge.state = {"last_update_id": 0}
    result = bridge._check_scheduler_watchdog()
    assert result is None


def test_watchdog_recent_brief_no_alert(bridge):
    """Watchdog returns None when brief was sent within the last 25 hours."""
    recent = (datetime.now(timezone.utc) - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bridge.state = {"last_update_id": 0, "last_morning_brief_utc": recent}
    result = bridge._check_scheduler_watchdog()
    assert result is None


def test_watchdog_stale_brief_returns_warning(bridge):
    """Watchdog returns a warning string when brief is > 25 hours old."""
    stale = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bridge.state = {"last_update_id": 0, "last_morning_brief_utc": stale}
    result = bridge._check_scheduler_watchdog()
    assert result is not None
    assert "watchdog" in result.lower()
    assert "30h" in result or "scheduler" in result.lower()


# ---------------------------------------------------------------------------
# 2. md_agent_state day count
# ---------------------------------------------------------------------------


def test_upsert_issue_creates_new(tmp_issue_log):
    import md_agent_state as mds

    rec = mds.upsert_issue("poly_stale", "Polymarket data 72h old", log_path=tmp_issue_log)
    assert rec["key"] == "poly_stale"
    assert rec["resolved"] is False
    assert rec["days"] == 0  # first upsert is day 0


def test_upsert_issue_increments_day_count(tmp_issue_log, tmp_path):
    import md_agent_state as mds

    # Seed the log with a first_seen 3 days ago
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    log_path = tmp_path / "issue_log.json"
    log_path.write_text(
        json.dumps(
            [
                {
                    "key": "mt5_cycle",
                    "description": "MT5 cycle stale",
                    "first_seen": three_days_ago,
                    "last_seen": three_days_ago,
                    "resolved": False,
                }
            ]
        ),
        encoding="utf-8",
    )
    rec = mds.upsert_issue("mt5_cycle", "MT5 cycle stale", log_path=log_path)
    assert rec["days"] == 3


def test_resolve_issue_marks_done(tmp_issue_log):
    import md_agent_state as mds

    mds.upsert_issue("fth_stale", "FTH brief stale", log_path=tmp_issue_log)
    found = mds.resolve_issue("fth_stale", log_path=tmp_issue_log)
    assert found is True
    open_issues = mds.get_open_issues(log_path=tmp_issue_log)
    assert not any(i["key"] == "fth_stale" for i in open_issues)


def test_prune_resolved_removes_old(tmp_issue_log):
    import md_agent_state as mds

    mds.upsert_issue("old_issue", "old", log_path=tmp_issue_log)
    mds.resolve_issue("old_issue", log_path=tmp_issue_log)
    # Manually backdate resolved_at
    records = json.loads(tmp_issue_log.read_text())
    for r in records:
        if r["key"] == "old_issue":
            old_ts = (datetime.now(timezone.utc) - timedelta(days=10)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            r["resolved_at"] = old_ts
    tmp_issue_log.write_text(json.dumps(records))
    pruned = mds.prune_resolved(older_than_days=7, log_path=tmp_issue_log)
    assert pruned == 1
    assert not tmp_issue_log.read_text().strip() or json.loads(tmp_issue_log.read_text()) == []


# ---------------------------------------------------------------------------
# 3. Brief format — one screen, correct structure
# ---------------------------------------------------------------------------

_RED_DIV = {
    "division": "trading",
    "scorecard": {
        "status": "RED",
        "items": [
            {
                "metric": "MT5 cycle freshness",
                "actual": "13.0d",
                "target": "<= 3h",
                "variance": "+13d",
                "status": "RED",
                "action": "Restart MT5 cycle and verify log activity.",
            }
        ],
    },
}

_GREEN_DIV = {
    "division": "websites",
    "scorecard": {
        "status": "GREEN",
        "items": [
            {
                "metric": "Website snapshot uptime",
                "actual": "100%",
                "target": ">= 100%",
                "variance": "0%",
                "status": "GREEN",
                "action": "",
            }
        ],
    },
}

_SAMPLE_PAYLOAD = {
    "company_name": "AI Holding Co",
    "generated_at_utc": "2026-04-28T08:00:00Z",
    "mode": "heartbeat",
    "company_scorecard": {"status": "RED", "items": []},
    "divisions": [_RED_DIV, _GREEN_DIV],
    "ceo_engine": "fallback_local_rules",
}


def test_brief_fits_telegram_limit(bridge, tmp_path):
    """Brief must be < 4096 characters."""
    with patch("md_agent_state.upsert_issue", return_value={"key": "x", "days": 2, "resolved": False}), \
         patch("md_agent_state.resolve_issue"):
        text = bridge._summarize_holding_brief(_SAMPLE_PAYLOAD)
    assert len(text) < 4096, f"Brief too long: {len(text)} chars"


def test_brief_contains_division_emojis(bridge):
    """Brief must contain status emojis for each division."""
    with patch("md_agent_state.upsert_issue", return_value={"key": "x", "days": 0, "resolved": False}), \
         patch("md_agent_state.resolve_issue"):
        text = bridge._summarize_holding_brief(_SAMPLE_PAYLOAD)
    assert "🔴" in text or "🟡" in text or "🟢" in text


def test_brief_contains_approve_command(bridge):
    """Brief must contain a /approve_* command when there's a decision item."""
    with patch("md_agent_state.upsert_issue", return_value={"key": "x", "days": 3, "resolved": False}), \
         patch("md_agent_state.resolve_issue"):
        text = bridge._summarize_holding_brief(_SAMPLE_PAYLOAD)
    assert "/approve_" in text
    assert "/skip" in text


def test_brief_shows_engine_tag(bridge):
    """Brief must show [det] or [ai] engine tag."""
    with patch("md_agent_state.upsert_issue", return_value={"key": "x", "days": 0, "resolved": False}), \
         patch("md_agent_state.resolve_issue"):
        text = bridge._summarize_holding_brief(_SAMPLE_PAYLOAD)
    assert "[det]" in text or "[ai]" in text


# ---------------------------------------------------------------------------
# 4. Task-and-track log
# ---------------------------------------------------------------------------


def test_log_task_creates_pending(tmp_task_log):
    import md_agent_state as mds

    task_id = mds.log_task("approve_fth_run", log_path=tmp_task_log)
    assert task_id.startswith("task_")
    pending = mds.get_pending_tasks(log_path=tmp_task_log)
    assert len(pending) == 1
    assert pending[0]["status"] == "PENDING"
    assert pending[0]["command"] == "approve_fth_run"


def test_update_task_marks_done(tmp_task_log):
    import md_agent_state as mds

    task_id = mds.log_task("approve_mt5_investigate", log_path=tmp_task_log)
    found = mds.update_task(task_id, "DONE", detail="Completed by operator", log_path=tmp_task_log)
    assert found is True
    pending = mds.get_pending_tasks(log_path=tmp_task_log)
    assert not pending  # no longer PENDING


def test_approve_command_logs_task(bridge, tmp_path):
    """Sending /approve_fth_run via handle_text logs a PENDING task."""
    tmp_task_log = tmp_path / "md_task_log.json"
    with patch("md_agent_state.log_task", return_value="task_0001") as mock_log, \
         patch("md_agent_state.resolve_issue"):
        response = bridge.handle_text("/approve_fth_run")
    mock_log.assert_called_once()
    call_kwargs = mock_log.call_args
    assert "fth_run" in call_kwargs[1].get("command", "") or "fth_run" in str(call_kwargs)
    assert "task_0001" in response or "Task logged" in response


def test_skip_command_responds(bridge):
    """Sending /skip returns an acknowledgement without error."""
    with patch("md_agent_state.log_task", return_value="task_0002"):
        response = bridge.handle_text("/skip")
    assert "skip" in response.lower() or "logged" in response.lower()

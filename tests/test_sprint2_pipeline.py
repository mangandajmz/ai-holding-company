"""Sprint 2 tests — wiki, initiative, dev pipeline gate, DeepSeek client.

Run: python -m pytest tests/test_sprint2_pipeline.py -q
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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_wiki(tmp_path):
    return tmp_path / "wiki.md"


@pytest.fixture()
def tmp_pending(tmp_path):
    return tmp_path / "wiki_pending.json"


@pytest.fixture()
def tmp_init_log(tmp_path):
    return tmp_path / "initiative_log.json"


@pytest.fixture()
def bridge(tmp_path):
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
        "trading_bots": [{"id": "mt5_desk"}],
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
        b.bot_ids = {"mt5_desk"}
        b.website_ids = {"freetraderhub"}
        b.reports_dir = tmp_path
        return b


# ---------------------------------------------------------------------------
# 1. DeepSeek client
# ---------------------------------------------------------------------------


def test_deepseek_client_raises_without_key():
    from deepseek_client import DeepSeekClient

    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY"):
            DeepSeekClient(api_key="")


def test_deepseek_is_configured_false_without_key():
    from deepseek_client import is_configured

    with patch.dict("os.environ", {"DEEPSEEK_API_KEY": ""}, clear=False):
        assert is_configured() is False


def test_deepseek_is_configured_true_with_key():
    from deepseek_client import is_configured

    with patch.dict("os.environ", {"DEEPSEEK_API_KEY": "sk-test-123"}):
        assert is_configured() is True


def test_deepseek_chat_calls_api(tmp_path):
    from deepseek_client import DeepSeekClient

    mock_response = json.dumps({
        "choices": [{"message": {"content": "Hello from DeepSeek"}}]
    }).encode()

    with patch("deepseek_client.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value.read = lambda: mock_response

        client = DeepSeekClient(api_key="sk-test-123")
        result = client.complete("Say hello")

    assert result == "Hello from DeepSeek"


# ---------------------------------------------------------------------------
# 2. Wiki system
# ---------------------------------------------------------------------------


def test_propose_entry_creates_pending(tmp_pending):
    import wiki

    slug = wiki.propose_entry(
        "Polymarket filter issue heuristic",
        "When Poly 0 trades 3d+, check market filter first not VPS.",
        pending_path=tmp_pending,
    )
    assert slug == "polymarket_filter_issue_heuris"
    pending = json.loads(tmp_pending.read_text())
    assert len(pending) == 1
    assert pending[0]["slug"] == slug


def test_approve_entry_writes_wiki(tmp_pending, tmp_wiki):
    import wiki

    wiki.propose_entry(
        "MT5 cycle heuristic",
        "MT5 cycle >3h usually means strategy store lock.",
        pending_path=tmp_pending,
    )
    slug = "mt5_cycle_heuristic"

    found = wiki.approve_entry(slug, wiki_path=tmp_wiki, pending_path=tmp_pending)

    assert found is True
    assert tmp_wiki.exists()
    content = tmp_wiki.read_text()
    assert "MT5 cycle heuristic" in content
    # Entry removed from pending
    remaining = json.loads(tmp_pending.read_text())
    assert not any(e["slug"] == slug for e in remaining)


def test_reject_entry_removes_from_pending(tmp_pending):
    import wiki

    wiki.propose_entry("test entry", "body", pending_path=tmp_pending)
    slug = "test_entry"
    found = wiki.reject_entry(slug, pending_path=tmp_pending)
    assert found is True
    assert json.loads(tmp_pending.read_text()) == []


def test_wiki_approve_command_via_bridge(bridge):
    with patch("wiki.approve_entry", return_value=True) as mock_approve:
        response = bridge.handle_text("/approve_wiki_poly_filter")
    mock_approve.assert_called_once_with("poly_filter")
    assert "approved" in response.lower()


def test_wiki_reject_command_via_bridge(bridge):
    with patch("wiki.reject_entry", return_value=True):
        response = bridge.handle_text("/reject_wiki_poly_filter")
    assert "discard" in response.lower() or "discarded" in response.lower()


# ---------------------------------------------------------------------------
# 3. Initiative proposals
# ---------------------------------------------------------------------------


def test_propose_initiative_creates_record(tmp_init_log):
    import md_agent_state as mds

    init_id = mds.propose_initiative(
        title="Add FTH auto-trigger",
        problem="FTH pipeline hasn't run in 30+ days three times this month",
        proposed_change="Add threshold in targets.yaml and trigger in monitoring.py",
        success_criteria="FTH pipeline triggers automatically when research age > 14d",
        log_path=tmp_init_log,
    )
    assert init_id.startswith("init_")
    proposed = mds.get_proposed_initiatives(log_path=tmp_init_log)
    assert len(proposed) == 1
    assert proposed[0]["status"] == "PROPOSED"


def test_approve_initiative_updates_status(tmp_init_log):
    import md_agent_state as mds

    init_id = mds.propose_initiative(
        title="Test initiative",
        problem="problem",
        proposed_change="change",
        success_criteria="criteria",
        log_path=tmp_init_log,
    )
    found = mds.update_initiative(init_id, "APPROVED", log_path=tmp_init_log)
    assert found is True
    proposed = mds.get_proposed_initiatives(log_path=tmp_init_log)
    assert not proposed  # no longer PROPOSED


def test_init_approve_command_via_bridge(bridge):
    with patch("md_agent_state.update_initiative", return_value=True) as mock_update:
        response = bridge.handle_text("/approve_init_0001")
    mock_update.assert_called_once_with("init_0001", "APPROVED", detail="CEO approved via Telegram")
    assert "approved" in response.lower()
    assert "dev pipeline" in response.lower()


def test_init_reject_command_via_bridge(bridge):
    with patch("md_agent_state.update_initiative", return_value=True):
        response = bridge.handle_text("/reject_init_0001")
    assert "rejected" in response.lower()


# ---------------------------------------------------------------------------
# 4. Dev pipeline gate (merge approval)
# ---------------------------------------------------------------------------


def test_merge_approve_command_calls_merge(bridge):
    with patch("dev_pipeline.merge_initiative", return_value=(True, "Initiative init_0001 merged successfully.")):
        response = bridge.handle_text("/approve_merge_0001")
    assert "merged" in response.lower() or "✅" in response


def test_merge_reject_command_updates_initiative(bridge):
    with patch("md_agent_state.update_initiative", return_value=True) as mock_update:
        response = bridge.handle_text("/reject_merge_0001")
    mock_update.assert_called_with("init_0001", "REJECTED", detail="CEO rejected merge")
    assert "rejected" in response.lower()


def test_pipeline_aborts_without_deepseek_key(tmp_init_log):
    """Pipeline returns ERROR outcome when DEEPSEEK_API_KEY is missing."""
    import md_agent_state as mds
    import dev_pipeline

    init_id = mds.propose_initiative(
        "Test", "problem", "change", "criteria", log_path=tmp_init_log
    )
    mds.update_initiative(init_id, "APPROVED", log_path=tmp_init_log)

    with (
        patch("dev_pipeline.ROOT", ROOT),
        patch("deepseek_client.os.getenv", return_value=""),
        patch("md_agent_state.DEFAULT_INITIATIVE_LOG", tmp_init_log),
        patch("md_agent_state.get_initiative", return_value={
            "initiative_id": init_id, "status": "APPROVED",
            "title": "Test", "problem": "p", "proposed_change": "c", "success_criteria": "s"
        }),
        patch("dev_pipeline._create_worktree", side_effect=RuntimeError("no worktree in test")),
    ):
        result = dev_pipeline.run_pipeline(init_id)

    assert result["outcome"] == "ERROR"

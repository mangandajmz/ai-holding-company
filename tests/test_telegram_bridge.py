from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import aiogram_bridge  # noqa: E402
import telegram_bridge  # noqa: E402


def test_deprecated_telegram_bridge_exits_with_message(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc_info:
        telegram_bridge.main()

    assert exc_info.value.code == 1
    assert "scripts/telegram_bridge.py is deprecated" in capsys.readouterr().err


def test_aiogram_runtime_rejects_missing_user_id_when_user_allowlist_configured() -> None:
    runtime = aiogram_bridge.AiogramBridgeRuntime.__new__(aiogram_bridge.AiogramBridgeRuntime)
    runtime.security_ready = True
    runtime.allowed_chat_ids = set()
    runtime.allowed_user_ids = {12345}

    assert runtime.is_authorized(chat_id=999, user_id=None) is False


def test_aiogram_runtime_accepts_matching_chat_and_user() -> None:
    runtime = aiogram_bridge.AiogramBridgeRuntime.__new__(aiogram_bridge.AiogramBridgeRuntime)
    runtime.security_ready = True
    runtime.allowed_chat_ids = {777}
    runtime.allowed_user_ids = {12345}

    assert runtime.is_authorized(chat_id=777, user_id=12345) is True


def test_backup_identity_is_limited_to_policy_actions() -> None:
    runtime = aiogram_bridge.AiogramBridgeRuntime.__new__(aiogram_bridge.AiogramBridgeRuntime)
    runtime.owner_chat_id = 777
    runtime.owner_user_id = 12345
    runtime.backup_chat_id = 888
    runtime.backup_user_id = 54321
    runtime.backup_allowed_actions = {"view_status", "view_approvals"}

    assert runtime.action_allowed("view_status", chat_id=888, user_id=54321) is True
    assert runtime.action_allowed("bot_execute", chat_id=888, user_id=54321) is False
    assert runtime.action_allowed("bot_execute", chat_id=777, user_id=12345) is True

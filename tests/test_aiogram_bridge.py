from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import aiogram_bridge  # noqa: E402


class _DummyRuntime:
    def __init__(self, phase3_payload: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = {}
        self.phase3_enabled = True
        self.observer_mode = True
        self.hermes_enabled = False
        self.hermes_base_url = "http://127.0.0.1:9000"
        self.hermes_health_path = "/health"
        self.hermes_chat_path = "/chat"
        self.hermes_timeout_sec = 30
        self.hermes_use_for_general_chat = False
        self.hermes_api_key = ""
        self.chat_model = "llama3.1:8b"
        self.bot_ids = {"mt5_desk", "polymarket"}
        self.website_ids = {"freeghosttools"}
        self._phase3_payload = phase3_payload or {}

    def is_authorized(self, chat_id: int | None, user_id: int | None) -> bool:
        return True

    def latest_daily_brief(self) -> dict[str, Any] | None:
        return None

    def latest_phase2(self) -> dict[str, Any] | None:
        return None

    def latest_phase3(self) -> dict[str, Any] | None:
        return self._phase3_payload


def test_natural_status_query_uses_phase3_snapshot_without_live_router(monkeypatch) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "generated_at_utc": "2026-04-24T03:05:00Z",
            "company_scorecard": {
                "status": "RED",
                "items": [{"metric": "Division GREEN ratio", "status": "RED", "actual": "33%", "target": ">=67%"}],
            },
            "base_summary": {"pnl_total": -7.5, "trades_total": 0, "websites_up": 3, "websites_total": 3},
        }
    )
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("status snapshot path should not call tool_router")

    async def _never(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("conversational layer should not run for deterministic status query")

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    monkeypatch.setattr(aiogram_bridge, "_generate_conversational_response", _never)

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="where are we now?"))
    assert "CEO Business Brief (Quick)" in reply
    assert "Portfolio Health" in reply
    assert "- Status: RED" in reply
    assert "Scope: promoted properties only (0 tracked: none)" in reply
    assert "- Headline: Promoted portfolio is off-plan; stabilization is required before expansion." in reply
    assert "Decision Required Now" in reply
    assert "- No approval blockers at this time." in reply
    assert "Primary Focus This Week" in reply
    assert "- No immediate decision items." in reply
    assert "- Execution on-plan: 0/0 (0.0%)" in reply
    assert "Updated: 2026-04-24T03:05:00Z UTC" in reply
    assert "Freshness:" in reply
    assert "- /status for full CEO business brief" in reply


def test_natural_status_query_handles_extra_spacing(monkeypatch) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
            "company_scorecard": {"status": "RED", "items": []},
            "base_summary": {"pnl_total": -7.5, "trades_total": 0, "websites_up": 3, "websites_total": 3},
            "property_pnl_blocks": [],
            "property_department_briefs": [],
            "revamp_queue": [],
        }
    )
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _never(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("conversational layer should not run for spacing variants of status query")

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_generate_conversational_response", _never)

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="where are we  now"))
    assert "CEO Business Brief (Quick)" in reply
    assert "Updated: 2026-04-24T03:23:46.025328+00:00 UTC" in reply


def test_status_query_handles_wher_typo(monkeypatch) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
            "company_scorecard": {"status": "AMBER", "items": []},
            "property_pnl_blocks": [],
            "property_department_briefs": [],
            "revamp_queue": [],
        }
    )
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="wher are we now?"))
    assert "CEO Business Brief (Quick)" in reply


def test_slash_status_returns_full_decision_report(monkeypatch) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
            "company_scorecard": {"status": "AMBER", "items": []},
            "base_summary": {"pnl_total": -7.5, "trades_total": 0, "websites_up": 3, "websites_total": 3},
            "property_pnl_blocks": [],
            "property_department_briefs": [],
            "revamp_queue": [],
        }
    )
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="/status"))
    assert "CEO Business Brief - Promoted Portfolio" in reply
    assert "- Snapshot freshness:" in reply
    assert "1) Executive Summary" in reply
    assert "2) Decisions Required" in reply
    assert "Command Center" in reply


def test_hermes_status_command_disabled(monkeypatch) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="/hermes_status"))
    assert "Hermes integration is currently disabled." in reply


def test_hermes_status_command_enabled(monkeypatch) -> None:
    runtime = _DummyRuntime()
    runtime.hermes_enabled = True
    runtime.hermes_use_for_general_chat = True
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _health() -> tuple[bool, str]:
        return True, "ok"

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_check_hermes_health", _health)
    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="/hermes_status"))
    assert "Hermes runtime status" in reply
    assert "- Health: UP" in reply


def test_conversational_response_prefers_hermes_when_enabled(monkeypatch) -> None:
    runtime = _DummyRuntime()
    runtime.hermes_enabled = True
    runtime.hermes_use_for_general_chat = True
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _hermes(*args: Any, **kwargs: Any) -> str:
        return "Hermes says: execute recovery plan."

    async def _ollama(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("Ollama should not run when Hermes returns a reply")

    monkeypatch.setattr(aiogram_bridge, "_call_hermes_chat", _hermes)
    monkeypatch.setattr(aiogram_bridge, "_call_ollama", _ollama)

    reply = asyncio.run(
        aiogram_bridge._generate_conversational_response(
            user_msg="md whats your take",
            context={"recent_history": [], "semantic_history": []},
            division_data={"context_lines": ["Company snapshot: PnL $-7.50"]},
        )
    )
    assert reply == "Hermes says: execute recovery plan."


def test_natural_approvals_query_returns_board_and_developer_items(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        assert sub_args == ["run_holding", "--mode", "board_review"]
        return {
            "ok": True,
            "payload": {
                "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
                "board_review": {
                    "approvals": [
                        {
                            "approval_id": "board_01_mt5_cycle",
                            "priority": "RED",
                            "topic": "Trading KPI: MT5 cycle freshness",
                            "decision": "Restart scheduler and verify cadence",
                            "owner": "trading",
                        }
                    ]
                }
            },
        }

    import developer_tool

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    monkeypatch.setattr(
        developer_tool,
        "run_developer_tool",
        lambda config, task, approval_id, action: {
            "pending": [{"approval_id": "dev_123", "task": "Patch status handling"}]
        }
        if action == "status"
        else {},
    )

    reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(
            user_id=1,
            chat_id=1,
            text="I want a list of all items that need approval",
        )
    )
    assert "Owner approvals snapshot" in reply
    assert "Board approvals pending:" in reply
    assert "board_01_mt5_cycle" in reply
    assert "Owner: Trading Lead" in reply
    assert "Tap the Approve/Reject buttons below each item" in reply
    assert "Developer approvals (1):" in reply
    assert "dev_123" in reply


def test_natural_approvals_query_uses_decision_fallback_when_missing(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        assert sub_args == ["run_holding", "--mode", "board_review"]
        return {
            "ok": True,
            "payload": {
                "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
                "board_review": {
                    "approvals": [
                        {
                            "approval_id": "board_99_example",
                            "priority": "AMBER",
                            "topic": "Company KPI: Property forecast attainment",
                            "decision": None,
                            "owner": "holding",
                        }
                    ]
                },
            },
        }

    import developer_tool

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    monkeypatch.setattr(developer_tool, "run_developer_tool", lambda *args: {"pending": []})

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="/approvals"))
    assert "Snapshot freshness:" in reply
    assert "board_99_example" in reply
    assert "Approval means prioritize monetization actions to improve forecast attainment." in reply


def test_approve_without_id_lists_top_pending_ids(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        assert sub_args == ["run_holding", "--mode", "board_review"]
        return {
            "ok": True,
            "payload": {
                "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
                "board_review": {
                    "approvals": [
                        {
                            "approval_id": "board_one",
                            "priority": "RED",
                            "topic": "Company KPI: Property blocks on-plan ratio",
                            "decision": "Focus execution.",
                            "owner": "holding",
                        }
                    ]
                },
            },
        }

    import developer_tool

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    monkeypatch.setattr(developer_tool, "run_developer_tool", lambda *args: {"pending": []})

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="/approve"))
    assert "Approval ID required." in reply
    assert "Top pending board IDs:" in reply
    assert "board_one" in reply


def test_management_take_query_is_snapshot_grounded(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
            "company_scorecard": {
                "status": "AMBER",
                "items": [
                    {"metric": "Property blocks on-plan ratio", "status": "RED"},
                ],
            },
            "property_pnl_blocks": [
                {"property_name": "freetraderhub", "status": {"value": "AMBER"}},
            ],
            "property_department_briefs": [],
            "revamp_queue": [],
        }
    )
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        assert sub_args == ["run_holding", "--mode", "board_review"]
        return {"ok": True, "payload": {"generated_at_utc": "2026-04-24T03:23:46.025328+00:00", "board_review": {"approvals": []}}}

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="Md whats your take"))
    assert "Executive Take" in reply
    assert "Primary pressure point: Property blocks on-plan ratio." in reply
    assert "Delivery owner now: Owner/CEO." in reply


def test_status_report_resolves_owner_labels(monkeypatch) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
            "company_scorecard": {
                "status": "AMBER",
                "items": [
                    {
                        "metric": "Property blocks on-plan ratio",
                        "status": "RED",
                        "actual": "0.0%",
                        "target": ">= 100%",
                        "action": "Focus execution on RED/AMBER properties before adding new initiatives.",
                    }
                ],
            },
            "property_pnl_blocks": [
                {
                    "property_id": "freetraderhub",
                    "property_name": "freetraderhub",
                    "status": {"value": "AMBER"},
                }
            ],
            "property_department_briefs": [],
            "revamp_queue": [],
        }
    )
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="/status"))
    assert "Owner/Timing: Owner/CEO | next heartbeat" in reply


def test_board_approve_and_deny_commands_update_state(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        assert sub_args == ["run_holding", "--mode", "board_review"]
        return {
            "ok": True,
            "payload": {
                "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
                "board_review": {
                    "approvals": [
                        {
                            "approval_id": "board_prop_blocks",
                            "priority": "RED",
                            "topic": "Company KPI: Property blocks on-plan ratio",
                            "decision": "Focus execution on RED/AMBER properties before adding new initiatives.",
                            "owner": "holding",
                        }
                    ]
                },
            },
        }

    import developer_tool

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    monkeypatch.setattr(developer_tool, "run_developer_tool", lambda *args: {"pending": []})

    approve_reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approve board_prop_blocks")
    )
    assert "marked APPROVED" in approve_reply

    approvals_reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approvals"))
    assert "Board approvals pending: none." in approvals_reply
    assert "Board decisions logged:" in approvals_reply
    assert "[APPROVED]" in approvals_reply

    deny_reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/deny board_prop_blocks")
    )
    assert "marked DENIED" in deny_reply


def test_approve_all_command_marks_pending_items(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        assert sub_args == ["run_holding", "--mode", "board_review"]
        return {
            "ok": True,
            "payload": {
                "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
                "board_review": {
                    "approvals": [
                        {
                            "approval_id": "board_prop_blocks",
                            "priority": "RED",
                            "topic": "Company KPI: Property blocks on-plan ratio",
                            "decision": "Focus execution.",
                            "owner": "holding",
                        },
                        {
                            "approval_id": "board_alert_count",
                            "priority": "RED",
                            "topic": "Company KPI: Alert count per heartbeat",
                            "decision": "Fix root causes.",
                            "owner": "holding",
                        },
                    ]
                },
            },
        }

    import developer_tool

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    monkeypatch.setattr(developer_tool, "run_developer_tool", lambda *args: {"pending": []})

    approve_all_reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approve_all")
    )
    assert "Batch APPROVED:" in approve_all_reply
    assert "requested 2" in approve_all_reply
    assert "updated 2" in approve_all_reply

    approvals_reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approvals"))
    assert "Board approvals pending: none." in approvals_reply
    assert "Board decisions logged:" in approvals_reply
    assert "[APPROVED]" in approvals_reply


def test_approve_selected_command_uses_user_selection(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime()
    state_path = tmp_path / "board_approval_decisions.json"
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", state_path)

    state_path.write_text(
        (
            '{"decisions": {}, "board_snapshot": {}, '
            '"selection_by_user": {"11": ["board_alert_count"]}}'
        ),
        encoding="utf-8",
    )

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        assert sub_args == ["run_holding", "--mode", "board_review"]
        return {
            "ok": True,
            "payload": {
                "generated_at_utc": "2026-04-24T03:23:46.025328+00:00",
                "board_review": {
                    "approvals": [
                        {
                            "approval_id": "board_prop_blocks",
                            "priority": "RED",
                            "topic": "Company KPI: Property blocks on-plan ratio",
                            "decision": "Focus execution.",
                            "owner": "holding",
                        },
                        {
                            "approval_id": "board_alert_count",
                            "priority": "RED",
                            "topic": "Company KPI: Alert count per heartbeat",
                            "decision": "Fix root causes.",
                            "owner": "holding",
                        },
                    ]
                },
            },
        }

    import developer_tool

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)
    monkeypatch.setattr(developer_tool, "run_developer_tool", lambda *args: {"pending": []})

    approve_selected_reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approve_selected")
    )
    assert "Batch APPROVED:" in approve_selected_reply
    assert "requested 1" in approve_selected_reply

    approvals_reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approvals"))
    assert "board_prop_blocks" in approvals_reply
    assert "board_alert_count" in approvals_reply
    assert "[APPROVED] Company KPI: Alert count per heartbeat" in approvals_reply


def test_natural_mt5_restart_research_query_runs_checks_without_fake_restart(monkeypatch) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    calls: list[list[str]] = []

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {"ok": True, "payload": {"ok": True}}

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(
            user_id=1,
            chat_id=1,
            text="Restart mt5 scheduler and run research",
        )
    )
    assert calls == [
        ["run_trading_script", "--bot", "mt5_desk", "--command-key", "health"],
        ["run_trading_script", "--bot", "mt5_desk", "--command-key", "report"],
    ]
    assert "no scheduler restart was executed" in reply.lower()


def test_natural_marketing_query_uses_phase3_department_payload(monkeypatch) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "property_department_briefs": [
                {
                    "property_id": "freetraderhub",
                    "property_name": "FreeTraderHub",
                    "departments": {
                        "marketing": {
                            "status": "AMBER",
                            "headline": "sessions below green target",
                            "proposal": "tighten demand capture on highest-intent pages",
                        }
                    },
                }
            ]
        }
    )
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _never(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("conversational layer should not run for deterministic marketing query")

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_generate_conversational_response", _never)

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="How is marketing?"))
    assert "Marketing status by operating property:" in reply
    assert "FreeTraderHub: [AMBER]" in reply

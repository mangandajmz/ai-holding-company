from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import aiogram_bridge  # noqa: E402


def _write_bridge_config(
    path: Path,
    allowed_chat_ids: list[int] | None = None,
    allowed_user_ids: list[int] | None = None,
) -> None:
    allowed_chat_ids = allowed_chat_ids or []
    allowed_user_ids = allowed_user_ids or []
    path.write_text(
        "\n".join(
            [
                "bridge:",
                "  observer_mode: true",
                "  telegram:",
                "    bot_token_env: TELEGRAM_BOT_TOKEN",
                "    owner_chat_id_env: TELEGRAM_OWNER_CHAT_ID",
                "    owner_user_id_env: TELEGRAM_OWNER_USER_ID",
                f"    allowed_chat_ids: {allowed_chat_ids}",
                f"    allowed_user_ids: {allowed_user_ids}",
                "memory:",
                "  ollama_base_url: http://127.0.0.1:11434",
                "  embedding_model: nomic-embed-text",
            ]
        ),
        encoding="utf-8",
    )


def test_allowlisted_non_owner_is_not_allowed_privileged_action(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_OWNER_USER_ID", raising=False)
    monkeypatch.setattr(aiogram_bridge, "load_dotenv", lambda *args, **kwargs: None)
    config_path = tmp_path / "projects.yaml"
    _write_bridge_config(config_path, allowed_chat_ids=[100], allowed_user_ids=[200])

    runtime = aiogram_bridge.AiogramBridgeRuntime(config_path=config_path)

    assert runtime.is_authorized(chat_id=100, user_id=200) is True
    assert runtime.action_allowed("board_approval_decision", chat_id=100, user_id=200) is False


def test_chat_only_allowlist_requires_private_chat_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_OWNER_USER_ID", raising=False)
    monkeypatch.setattr(aiogram_bridge, "load_dotenv", lambda *args, **kwargs: None)
    config_path = tmp_path / "projects.yaml"
    _write_bridge_config(config_path, allowed_chat_ids=[100])

    runtime = aiogram_bridge.AiogramBridgeRuntime(config_path=config_path)

    assert runtime.is_authorized(chat_id=100, user_id=100) is True
    assert runtime.is_authorized(chat_id=100, user_id=200) is False


def test_dev_pipeline_commands_have_restricted_action_types() -> None:
    assert aiogram_bridge._command_action_type("/approve_merge_1234") == "develop_merge"
    assert aiogram_bridge._command_action_type("/reject_merge_1234") == "develop_merge"
    assert aiogram_bridge._command_action_type("/approve_init_1234") == "develop_decision"
    assert aiogram_bridge._command_action_type("/boardroom ask trading status") == "view_status"
    assert aiogram_bridge._command_action_type("/loop new improve reporting") == "view_status"
    assert aiogram_bridge._command_action_type("/work") == "view_status"
    assert aiogram_bridge._command_action_type("/work scan_reviews") == "view_status"


def test_loop_command_routes_to_tool_router(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {
            "ok": True,
            "payload": {
                "ok": True,
                "loop": {
                    "loop_id": "loop_0001",
                    "goal": "Improve reporting",
                    "status": "GOAL_CAPTURED",
                    "approval_status": "NOT_REQUIRED_YET",
                    "next_step": "Gather evidence.",
                },
                "report": "reports/company_loops/loop_0001.md",
            },
        }

    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    reply = asyncio.run(aiogram_bridge._handle_loop_command("/loop new Improve reporting"))

    assert calls == [["loop", "new", "--goal", "Improve reporting"]]
    assert "Loop `loop_0001` is GOAL_CAPTURED" in reply
    assert "Gather evidence" in reply


def test_work_command_routes_to_tool_router(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {
            "ok": True,
            "payload": {
                "ok": True,
                "counts": {"open": 1, "pending_approval": 1, "approved": 0, "in_progress": 0},
                "text": "Work Ledger\n- Open: 1 | Decide: 1 | Execute: 0",
            },
        }

    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    reply = asyncio.run(aiogram_bridge._handle_work_command("/work"))

    assert calls == [["work", "status"]]
    assert "Work Ledger" in reply
    assert "Decide: 1" in reply


def test_work_reminders_command_routes_to_tool_router(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {
            "ok": True,
            "payload": {
                "ok": True,
                "needs_attention": True,
                "count": 1,
                "text": "Work reminders: 1 item(s) need owner attention.",
            },
        }

    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    reply = asyncio.run(aiogram_bridge._handle_work_command("/work reminders"))

    assert calls == [["work", "reminders"]]
    assert "need owner attention" in reply


def test_work_scan_reviews_routes_to_tool_router(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {
            "ok": True,
            "payload": {
                "ok": True,
                "created": 2,
                "existing": 1,
                "text": "Work Ledger\n- Open: 3 | Decide: 2 | Execute: 0",
            },
        }

    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    reply = asyncio.run(aiogram_bridge._handle_work_command("/work scan_reviews"))

    assert calls == [["work", "scan_reviews"]]
    assert "Review scan complete: created 2, existing 1." in reply
    assert "Work Ledger" in reply


def test_work_approve_command_requires_owner_due_and_signal(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {
            "ok": True,
            "payload": {
                "ok": True,
                "item": {
                    "id": "work_123",
                    "title": "Review closure",
                    "status": "APPROVED",
                    "owner": "MA",
                    "due_at": "2026-05-08T18:00:00+00:00",
                    "completion_signal": "Signed review note exists.",
                    "next_step": "Start execution.",
                    "evidence": [],
                },
            },
        }

    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    reply = asyncio.run(
        aiogram_bridge._handle_work_command(
            "/work approve work_123 | MA | 2026-05-08T18:00:00+00:00 | Signed review note exists."
        )
    )

    assert calls == [
        [
            "work",
            "approve",
            "--work-id",
            "work_123",
            "--owner",
            "MA",
            "--due-at",
            "2026-05-08T18:00:00+00:00",
            "--completion-signal",
            "Signed review note exists.",
        ]
    ]
    assert "Approved: `work_123` [APPROVED]" in reply
    assert "Owner: MA" in reply


def test_work_done_command_requires_result_and_evidence(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {
            "ok": True,
            "payload": {
                "ok": True,
                "item": {
                    "id": "work_123",
                    "title": "Review closure",
                    "status": "DONE",
                    "owner": "MA",
                    "due_at": "2026-05-08T18:00:00+00:00",
                    "completion_signal": "Signed review note exists.",
                    "next_step": "Closed.",
                    "evidence": [{"summary": "reports/review.md"}],
                },
            },
        }

    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    reply = asyncio.run(
        aiogram_bridge._handle_work_command("/work done work_123 | Review accepted | reports/review.md")
    )

    assert calls == [
        [
            "work",
            "done",
            "--work-id",
            "work_123",
            "--result",
            "Review accepted",
            "--evidence",
            "reports/review.md",
        ]
    ]
    assert "Closed: `work_123` [DONE]" in reply
    assert "Evidence: 1" in reply


def test_work_start_and_block_commands_route_to_tool_router(monkeypatch) -> None:
    calls: list[list[str]] = []

    async def _run_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        calls.append(sub_args)
        return {
            "ok": True,
            "payload": {
                "ok": True,
                "item": {
                    "id": sub_args[3],
                    "title": "Review closure",
                    "status": "IN_PROGRESS" if sub_args[1] == "start" else "BLOCKED",
                    "owner": "MA",
                    "due_at": "2026-05-08T18:00:00+00:00",
                    "completion_signal": "Signed review note exists.",
                    "next_step": "Complete work." if sub_args[1] == "start" else "Blocked: waiting on credentials",
                    "evidence": [],
                },
            },
        }

    monkeypatch.setattr(aiogram_bridge, "_run_tool_router", _run_router)

    start_reply = asyncio.run(aiogram_bridge._handle_work_command("/work start work_123 review started"))
    block_reply = asyncio.run(aiogram_bridge._handle_work_command("/work block work_123 waiting on credentials"))

    assert calls == [
        ["work", "start", "--work-id", "work_123", "--note", "review started"],
        ["work", "block", "--work-id", "work_123", "--reason", "waiting on credentials"],
    ]
    assert "Started: `work_123` [IN_PROGRESS]" in start_reply
    assert "Blocked: `work_123` [BLOCKED]" in block_reply


def test_simulate_text_requires_explicit_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_OWNER_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_OWNER_USER_ID", raising=False)
    monkeypatch.setattr(aiogram_bridge, "load_dotenv", lambda *args, **kwargs: None)
    config_path = tmp_path / "projects.yaml"
    _write_bridge_config(config_path, allowed_chat_ids=[1])
    monkeypatch.setattr(sys, "argv", ["aiogram_bridge.py", "--config", str(config_path), "--simulate-text", "/status"])

    with pytest.raises(RuntimeError, match="requires explicit"):
        asyncio.run(aiogram_bridge.main())


class _DummyRuntime:
    def __init__(self, phase3_payload: dict[str, Any] | None = None) -> None:
        self.config: dict[str, Any] = {}
        self.phase3_enabled = True
        self.observer_mode = True
        self.degraded_ops_mode = False
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

    def is_owner_identity(self, chat_id: int | None, user_id: int | None) -> bool:
        return True

    def is_backup_identity(self, chat_id: int | None, user_id: int | None) -> bool:
        return False

    def action_allowed(self, action_type: str, chat_id: int | None, user_id: int | None) -> bool:
        return True

    def permission_denied_message(self, action_type: str) -> str:
        return "denied"

    def latest_daily_brief(self) -> dict[str, Any] | None:
        return None

    def latest_phase2(self) -> dict[str, Any] | None:
        return None

    def latest_phase3(self) -> dict[str, Any] | None:
        return self._phase3_payload


def test_natural_status_query_uses_phase3_snapshot_without_live_router(monkeypatch, tmp_path) -> None:
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
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")

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
    assert "- Operational health: RED" in reply
    assert "Scope: promoted properties only (0 tracked: none)" in reply
    assert "- Headline: Promoted portfolio is off-plan; stabilization is required before expansion." in reply
    assert "Decision Required Now" in reply
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
        aiogram_bridge,
        "_pending_company_loop_approvals",
        lambda: [
            {
                "loop_id": "loop_0002",
                "goal": "Get FreeTraderHub its first measurable affiliate conversion signal",
                "owner": "CEO / Marketing / Websites / Commercial",
                "approval_status": "PENDING_CEO_APPROVAL",
                "status": "PENDING_CEO_APPROVAL",
            }
        ],
    )
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
            text="Approvals",
        )
    )
    assert "Owner Approvals" in reply
    assert "Needs decision: 3" in reply
    assert "Board Decisions" in reply
    assert "board_01_mt5_cycle" in reply
    assert "Owner: Trading Lead" in reply
    assert "Developer Approvals (1)" in reply
    assert "dev_123" in reply
    assert "Company Loops (1)" in reply
    assert "loop_0002" in reply
    assert "/loop approve loop_0002" in reply


def test_approvals_command_is_case_insensitive() -> None:
    assert aiogram_bridge._command_action_type("/Approvals") == "view_approvals"


def test_dashboard_command_is_view_only() -> None:
    assert aiogram_bridge._command_action_type("/dashboard") == "view_status"


def test_dashboard_command_returns_compact_ceo_card(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime(
        phase3_payload={
            "generated_at_utc": "2026-05-03T16:00:00+00:00",
            "company_scorecard": {
                "status": "AMBER",
                "items": [
                    {
                        "metric": "Property forecast attainment",
                        "status": "RED",
                    }
                ],
            },
            "property_pnl_blocks": [
                {
                    "property_id": "freetraderhub",
                    "property_name": "FreeTraderHub",
                    "status": {"value": "GREEN", "pct_to_forecast_mrr": 4.1},
                    "revenue": {"total_mrr_usd": 0},
                    "top_movers": {"biggest_risk": "first conversion signal not proven"},
                }
            ],
            "board_review": {
                "approvals": [
                    {
                        "approval_id": "board_fth_forecast",
                        "priority": "RED",
                        "topic": "Company KPI: Property forecast attainment",
                        "decision": "Prioritize monetization.",
                        "owner": "holding",
                    }
                ]
            },
        }
    )
    source = tmp_path / "state" / "property_metrics" / "freetraderhub" / "shared.json"
    source.parent.mkdir(parents=True)
    source.write_text(
        json.dumps(
            {
                "tracking": {
                    "audience": {"sessions_7d": 12, "email_list_size": 3},
                    "revenue": {
                        "affiliate_clicks": {"ftmo_7d": 1, "fundednext_7d": 0},
                        "total_mrr_usd": 0,
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "ROOT", tmp_path)
    monkeypatch.setattr(aiogram_bridge, "_pending_company_loop_approvals", lambda: [])

    reply = asyncio.run(aiogram_bridge._handle_dashboard_command())

    assert "AI Capital Group Dashboard" in reply
    assert "Portfolio" in reply
    assert "- Operational health: GREEN" in reply
    assert "- Commercial health: RED" in reply
    assert "FreeTraderHub" in reply
    assert "- Traffic 7d: 12 sessions" in reply
    assert "- Email list: 3" in reply
    assert "- Affiliate clicks 7d: FTMO 1 | FundedNext 0" in reply
    assert "CEO Actions" in reply
    assert "- Pending approvals: 1" in reply
    assert "board_fth_forecast" in reply
    assert "/approvals for decisions" in reply


def test_greeting_returns_fast_deterministic_reply(monkeypatch) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _never(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("greetings should not retrieve context")

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_retrieve_context", _never)

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="Hi"))

    assert "I am online" in reply
    assert "Approvals" in reply


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
    assert "Data:" in reply
    assert "board_99_example" in reply
    assert "Revenue/forecast visibility is weak" in reply


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
    assert "Operational health:" in reply
    assert "Commercial health:" in reply
    assert "Primary pressure point: Property blocks on-plan ratio." in reply
    assert "Delivery owner now: Owner/CEO." in reply


def test_chat_check_does_not_return_executive_take(monkeypatch) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    async def _never(*args: Any, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("chat checks should not retrieve context")

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_retrieve_context", _never)

    reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="can you chat?"))

    assert "Yes. I can chat" in reply
    assert "Executive Take" not in reply


def test_approved_work_query_returns_execution_status(monkeypatch, tmp_path) -> None:
    runtime = _DummyRuntime()
    monkeypatch.setattr(aiogram_bridge, "RUNTIME", runtime)
    monkeypatch.setattr(aiogram_bridge, "BOARD_APPROVAL_STATE_FILE", tmp_path / "board_approval_decisions.json")
    aiogram_bridge._persist_board_approval_state(
        {
            "decisions": {},
            "board_snapshot": {},
            "selection_by_user": {},
            "execution_by_approval": {
                "board_one": {
                    "status": "APPROVED",
                    "topic": "Company KPI: Property forecast attainment",
                    "owner": "holding",
                    "decision": "Increase monetization focus.",
                    "due_at_utc": "2026-05-06T00:00:00+00:00",
                }
            },
        }
    )

    async def _save(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(aiogram_bridge, "_save_conversation", _save)
    monkeypatch.setattr(aiogram_bridge, "_pending_company_loop_approvals", lambda: [])

    reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(user_id=1, chat_id=1, text="I approved an initiative where is it at?")
    )

    assert "Approved Work Status" in reply
    assert "Awaiting execution: 1" in reply
    assert "board_one" in reply
    assert "/assign board_one" in reply


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
    assert "Board approval approved" in approve_reply

    approvals_reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approvals"))
    assert "None pending." in approvals_reply
    assert "Recently Decided" in approvals_reply
    assert "[APPROVED]" in approvals_reply

    deny_reply, _ = asyncio.run(
        aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/deny board_prop_blocks")
    )
    assert "Board approval denied" in deny_reply


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
    assert "Batch approved recorded" in approve_all_reply
    assert "Requested: 2" in approve_all_reply
    assert "Updated: 2" in approve_all_reply

    approvals_reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approvals"))
    assert "None pending." in approvals_reply
    assert "Recently Decided" in approvals_reply
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
    assert "Batch approved recorded" in approve_selected_reply
    assert "Requested: 1" in approve_selected_reply

    approvals_reply, _ = asyncio.run(aiogram_bridge.process_text_message(user_id=11, chat_id=1, text="/approvals"))
    assert "board_prop_blocks" in approvals_reply
    assert "board_alert_count" in approvals_reply
    assert "[APPROVED]" in approvals_reply
    assert "Company KPI: Alert count per heartbeat" in approvals_reply


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

"""Command router used by the Telegram bridge and chat directives."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from monitoring import check_website, daily_brief, load_config, read_bot_logs, run_trading_script


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _emit(payload: dict) -> None:
    print(json.dumps(payload, indent=2))


def _load(config_path: str | None) -> dict:
    if config_path:
        return load_config(config_path)
    return load_config(ROOT / "config" / "projects.yaml")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI Holding Company tool router (Phase 1 + Phase 2 + Phase 3).")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to projects.yaml (defaults to config/projects.yaml).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    logs = sub.add_parser("read_bot_logs", help="Read latest logs for a configured bot.")
    logs.add_argument("--bot", required=True, help="Bot ID from config/projects.yaml.")
    logs.add_argument("--lines", type=int, default=120, help="Tail lines for text logs.")

    run_cmd = sub.add_parser("run_trading_script", help="Run bot command (health/report/execute).")
    run_cmd.add_argument("--bot", required=True, help="Bot ID from config/projects.yaml.")
    run_cmd.add_argument("--command-key", default="health", help="Command key under bot.commands.")
    run_cmd.add_argument("--extra-args", default="", help="Optional extra args appended to command.")
    run_cmd.add_argument("--timeout-sec", type=int, default=120, help="Subprocess timeout.")

    site = sub.add_parser("check_website", help="Check website status and latency.")
    site.add_argument("--website", required=True, help="Website ID from config/projects.yaml.")

    brief = sub.add_parser("daily_brief", help="Generate the morning executive heartbeat.")
    brief.add_argument("--force", action="store_true", help="Force brief even if already sent today.")

    divisions = sub.add_parser("run_divisions", help="Run Phase 2 CrewAI division orchestration.")
    divisions.add_argument(
        "--division",
        default="all",
        choices=["all", "trading", "websites", "content_studio"],
        help="Division scope: all, trading, websites, or content_studio.",
    )
    divisions.add_argument("--force", action="store_true", help="Force a fresh base brief before running divisions.")

    holding = sub.add_parser("run_holding", help="Run Phase 3 holding-company CEO orchestration.")
    holding.add_argument(
        "--mode",
        default="heartbeat",
        choices=["heartbeat", "board_review", "board_pack"],
        help="Holding mode: heartbeat (daily), board_review (deeper review), or board_pack (v2 with dissent).",
    )
    holding.add_argument("--force", action="store_true", help="Force a fresh base brief before running holding mode.")

    boardroom = sub.add_parser("boardroom", help="Run a CEO boardroom meeting transcript.")
    boardroom.add_argument(
        "action",
        choices=["start", "status", "ask", "close"],
        help="Boardroom action.",
    )
    boardroom.add_argument("--topic", default="", help="Meeting topic for start.")
    boardroom.add_argument("--division", default="md", help="Division to ask.")
    boardroom.add_argument("--question", default="", help="Question for boardroom ask.")
    boardroom.add_argument("--note", default="", help="Closing decision or follow-up note.")
    boardroom.add_argument("--refresh", action="store_true", help="Open a fresh meeting even if one is active.")

    loop = sub.add_parser("loop", help="Manage file-first company operating loops.")
    loop_sub = loop.add_subparsers(dest="loop_action", required=True)

    loop_new = loop_sub.add_parser("new", help="Create a company loop from a CEO goal.")
    loop_new.add_argument("--goal", required=True, help="CEO goal for the loop.")
    loop_new.add_argument("--type", default="operations", help="Loop type.")
    loop_new.add_argument("--division", default="operations", help="Owning division.")
    loop_new.add_argument("--owner", default="CEO", help="Loop owner.")

    loop_status = loop_sub.add_parser("status", help="List open company loops.")
    loop_status.add_argument("--include-closed", action="store_true", help="Include DONE/REJECTED loops.")

    loop_show = loop_sub.add_parser("show", help="Show one company loop.")
    loop_show.add_argument("--loop-id", required=True, help="Loop id.")

    loop_evidence = loop_sub.add_parser("evidence", help="Attach evidence to a company loop.")
    loop_evidence.add_argument("--loop-id", required=True, help="Loop id.")
    loop_evidence.add_argument("--path", required=True, help="Evidence path or artifact reference.")
    loop_evidence.add_argument("--note", default="", help="Evidence note.")

    loop_advance = loop_sub.add_parser("advance", help="Advance a loop to review or approval.")
    loop_advance.add_argument("--loop-id", required=True, help="Loop id.")
    loop_advance.add_argument("--note", default="", help="Advance note.")
    loop_advance.add_argument("--recommendation", default="", help="Recommendation text.")
    loop_advance.add_argument("--risk-review", default="", help="Risk review text.")
    loop_advance.add_argument("--commercial-review", default="", help="Commercial review text.")
    loop_advance.add_argument("--measurement-plan", default="", help="Measurement plan.")

    loop_approve = loop_sub.add_parser("approve", help="Approve a company loop action.")
    loop_approve.add_argument("--loop-id", required=True, help="Loop id.")
    loop_approve.add_argument("--note", default="", help="Approval note.")
    loop_approve.add_argument("--action", default="", help="Approved action.")

    loop_reject = loop_sub.add_parser("reject", help="Reject a company loop.")
    loop_reject.add_argument("--loop-id", required=True, help="Loop id.")
    loop_reject.add_argument("--note", default="", help="Rejection note.")

    loop_start = loop_sub.add_parser("start", help="Mark approved loop action in progress.")
    loop_start.add_argument("--loop-id", required=True, help="Loop id.")
    loop_start.add_argument("--note", default="", help="Start note.")

    loop_measure = loop_sub.add_parser("measure", help="Record measurement result.")
    loop_measure.add_argument("--loop-id", required=True, help="Loop id.")
    loop_measure.add_argument("--result", required=True, help="Measurement result.")
    loop_measure.add_argument("--note", default="", help="Measurement note.")

    loop_done = loop_sub.add_parser("done", help="Close a company loop.")
    loop_done.add_argument("--loop-id", required=True, help="Loop id.")
    loop_done.add_argument("--result", default="", help="Final result.")

    work = sub.add_parser("work", help="Show the minimal work ledger.")
    work.add_argument("--db", default=None, help="Optional work ledger DB path.")
    work_sub = work.add_subparsers(dest="work_action", required=True)
    work_sub.add_parser("status", help="Show work ledger status.")
    work_show = work_sub.add_parser("show", help="Show one work item.")
    work_show.add_argument("--work-id", required=True, help="Work item id.")
    work_scan = work_sub.add_parser("scan_reviews", help="Scan review markdown into the work ledger.")
    work_scan.add_argument(
        "--root",
        default=str(ROOT / "finance_web_page"),
        help="Root directory to scan for READY FOR MA REVIEW markdown.",
    )
    work_approve = work_sub.add_parser("approve", help="Approve work with execution fields.")
    work_approve.add_argument("--work-id", required=True, help="Work item id.")
    work_approve.add_argument("--owner", required=True, help="Owner accountable for execution.")
    work_approve.add_argument("--due-at", required=True, help="Expected completion time.")
    work_approve.add_argument("--completion-signal", required=True, help="Evidence needed to close the work.")
    work_approve.add_argument("--next-step", default="", help="Optional next execution step.")
    work_start = work_sub.add_parser("start", help="Mark approved work in progress.")
    work_start.add_argument("--work-id", required=True, help="Work item id.")
    work_start.add_argument("--note", default="", help="Optional start note.")
    work_block = work_sub.add_parser("block", help="Mark work blocked.")
    work_block.add_argument("--work-id", required=True, help="Work item id.")
    work_block.add_argument("--reason", required=True, help="Reason the work is blocked.")
    work_done = work_sub.add_parser("done", help="Close work with result and evidence.")
    work_done.add_argument("--work-id", required=True, help="Work item id.")
    work_done.add_argument("--result", required=True, help="Final result.")
    work_done.add_argument("--evidence", required=True, help="Evidence proving the result.")

    mem_add = sub.add_parser("log_direction", help="Persist owner directive into vector memory.")
    mem_add.add_argument("--text", required=True, help="Directive text to persist.")
    mem_add.add_argument("--source", default="owner_chat", help="Source label for metadata.")

    mem_search = sub.add_parser("memory_search", help="Query local vector memory.")
    mem_search.add_argument("--query", required=True, help="Memory query text.")
    mem_search.add_argument("--top-k", type=int, default=5, help="Number of matches.")

    develop = sub.add_parser("develop", help="Submit Developer Tool task for CEO-gated code generation.")
    develop.add_argument("--task", required=True, help="Plain-English development task.")

    develop_approve = sub.add_parser("develop_approve", help="Approve a pending Developer Tool submission.")
    develop_approve.add_argument("--approval-id", required=True, help="Approval ID from /develop response.")

    develop_deny = sub.add_parser("develop_deny", help="Deny a pending Developer Tool submission.")
    develop_deny.add_argument("--approval-id", required=True, help="Approval ID from /develop response.")

    sub.add_parser("develop_status", help="List pending Developer Tool approvals.")

    content = sub.add_parser("content_create", help="Create a Content Studio draft from a brief.")
    content.add_argument("--brief-text", required=True, help="Brief text for the content draft.")

    sub.add_parser("content_status", help="List tracked Content Studio drafts by status.")

    content_approve = sub.add_parser("content_approve", help="Approve a pending Content Studio draft.")
    content_approve.add_argument("--draft-id", required=True, help="Draft ID returned by Content Studio.")
    content_approve.add_argument("--decision-by-user-id", type=int, default=None, help="User ID approving the draft.")
    content_approve.add_argument("--decision-note", default="", help="Optional approval note.")

    content_deny = sub.add_parser("content_deny", help="Deny a pending Content Studio draft.")
    content_deny.add_argument("--draft-id", required=True, help="Draft ID returned by Content Studio.")
    content_deny.add_argument("--decision-by-user-id", type=int, default=None, help="User ID denying the draft.")
    content_deny.add_argument("--decision-note", default="", help="Optional denial note.")

    time_cmd = sub.add_parser("time_checkin", help="Log CEO time saved (Stage I tracking).")
    time_cmd.add_argument("--activity", required=True, help="What activity saved time.")
    time_cmd.add_argument("--hours", type=float, required=True, help="Hours saved.")

    time_report = sub.add_parser("time_report", help="Get time-saved report and R9 status.")
    time_report.add_argument("--days", type=int, default=14, help="Lookback window in days.")
    return parser


def _memory_add(config: dict, text: str, source: str) -> dict:
    from local_vector_memory import LocalVectorMemory  # pylint: disable=import-outside-toplevel

    memory_dir = ROOT / config.get("paths", {}).get("memory_dir", "memory")
    memory_dir.mkdir(parents=True, exist_ok=True)
    mem_cfg = config.get("memory", {})
    store = LocalVectorMemory(
        data_path=memory_dir / "vector_store.jsonl",
        ollama_base_url=str(mem_cfg.get("ollama_base_url", "http://127.0.0.1:11434")),
        embedding_model=str(mem_cfg.get("embedding_model", "nomic-embed-text")),
    )
    item = store.add(text=text, metadata={"type": "owner_direction", "source": source})
    return {"ok": True, "stored": item.to_dict()}


def _memory_search(config: dict, query: str, top_k: int) -> dict:
    from local_vector_memory import LocalVectorMemory  # pylint: disable=import-outside-toplevel

    memory_dir = ROOT / config.get("paths", {}).get("memory_dir", "memory")
    memory_dir.mkdir(parents=True, exist_ok=True)
    mem_cfg = config.get("memory", {})
    store = LocalVectorMemory(
        data_path=memory_dir / "vector_store.jsonl",
        ollama_base_url=str(mem_cfg.get("ollama_base_url", "http://127.0.0.1:11434")),
        embedding_model=str(mem_cfg.get("embedding_model", "nomic-embed-text")),
    )
    return {"ok": True, "query": query, "results": store.search(query=query, top_k=top_k)}


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = _load(args.config)

    if args.command == "read_bot_logs":
        _emit(read_bot_logs(config=config, bot_id=args.bot, lines=args.lines))
        return

    if args.command == "run_trading_script":
        _emit(
            run_trading_script(
                config=config,
                bot_id=args.bot,
                command_key=args.command_key,
                extra_args=args.extra_args,
                timeout_sec=args.timeout_sec,
            )
        )
        return

    if args.command == "check_website":
        _emit(check_website(config=config, site_id=args.website))
        return

    if args.command == "daily_brief":
        _emit(daily_brief(config=config, force=args.force))
        return

    if args.command == "run_divisions":
        from phase2_crews import run_phase2_divisions  # pylint: disable=import-outside-toplevel

        _emit(run_phase2_divisions(config=config, division=args.division, force=args.force))
        return

    if args.command == "run_holding":
        from phase3_holding import run_phase3_holding  # pylint: disable=import-outside-toplevel

        _emit(run_phase3_holding(config=config, mode=args.mode, force=args.force))
        return

    if args.command == "boardroom":
        from boardroom import ask_boardroom, boardroom_status, close_boardroom, start_boardroom

        if args.action == "start":
            _emit(start_boardroom(config=config, topic=args.topic, refresh=args.refresh))
            return
        if args.action == "status":
            _emit(boardroom_status(config=config))
            return
        if args.action == "ask":
            _emit(ask_boardroom(config=config, division=args.division, question=args.question))
            return
        if args.action == "close":
            _emit(close_boardroom(config=config, note=args.note))
            return

    if args.command == "loop":
        from company_loop import (
            add_evidence,
            advance_loop,
            approve_loop,
            done_loop,
            list_loops,
            measure_loop,
            new_loop,
            reject_loop,
            show_loop,
            start_action,
        )

        if args.loop_action == "new":
            _emit(
                new_loop(
                    config=config,
                    goal=args.goal,
                    loop_type=args.type,
                    division=args.division,
                    owner=args.owner,
                )
            )
            return
        if args.loop_action == "status":
            _emit(list_loops(config=config, include_closed=args.include_closed))
            return
        if args.loop_action == "show":
            _emit(show_loop(config=config, loop_id=args.loop_id))
            return
        if args.loop_action == "evidence":
            _emit(add_evidence(config=config, loop_id=args.loop_id, path=args.path, note=args.note))
            return
        if args.loop_action == "advance":
            _emit(
                advance_loop(
                    config=config,
                    loop_id=args.loop_id,
                    note=args.note,
                    recommendation=args.recommendation,
                    risk_review=args.risk_review,
                    commercial_review=args.commercial_review,
                    measurement_plan=args.measurement_plan,
                )
            )
            return
        if args.loop_action == "approve":
            _emit(approve_loop(config=config, loop_id=args.loop_id, note=args.note, action=args.action))
            return
        if args.loop_action == "reject":
            _emit(reject_loop(config=config, loop_id=args.loop_id, note=args.note))
            return
        if args.loop_action == "start":
            _emit(start_action(config=config, loop_id=args.loop_id, note=args.note))
            return
        if args.loop_action == "measure":
            _emit(measure_loop(config=config, loop_id=args.loop_id, result=args.result, note=args.note))
            return
        if args.loop_action == "done":
            _emit(done_loop(config=config, loop_id=args.loop_id, result=args.result))
            return

    if args.command == "work":
        from kernel.db import connect  # pylint: disable=import-outside-toplevel
        from kernel.views import render_status_text, work_status  # pylint: disable=import-outside-toplevel
        from kernel.work_items import (  # pylint: disable=import-outside-toplevel
            approve_work_item,
            block_work_item,
            done_work_item,
            get_work_item,
            scan_ready_for_review_markdown,
            start_work_item,
        )

        conn = connect(args.db)
        try:
            try:
                if args.work_action == "status":
                    status = work_status(conn)
                    status["text"] = render_status_text(status)
                    _emit(status)
                    return
                if args.work_action == "show":
                    item = get_work_item(conn, args.work_id)
                    _emit({"ok": item is not None, "item": item, "error": None if item else "work item not found"})
                    return
                if args.work_action == "scan_reviews":
                    result = scan_ready_for_review_markdown(conn, root=args.root)
                    status = work_status(conn)
                    result["status"] = status
                    result["text"] = render_status_text(status)
                    _emit(result)
                    return
                if args.work_action == "approve":
                    item = approve_work_item(
                        conn,
                        args.work_id,
                        owner=args.owner,
                        due_at=args.due_at,
                        completion_signal=args.completion_signal,
                        next_step=args.next_step.strip() or None,
                    )
                    _emit({"ok": True, "item": item})
                    return
                if args.work_action == "start":
                    _emit({"ok": True, "item": start_work_item(conn, args.work_id, note=args.note)})
                    return
                if args.work_action == "block":
                    _emit({"ok": True, "item": block_work_item(conn, args.work_id, args.reason)})
                    return
                if args.work_action == "done":
                    item = done_work_item(
                        conn,
                        args.work_id,
                        result=args.result,
                        evidence=args.evidence,
                    )
                    _emit({"ok": True, "item": item})
                    return
            except ValueError as exc:
                status = work_status(conn)
                _emit({"ok": False, "error": str(exc), "status": status, "text": render_status_text(status)})
                return
        finally:
            conn.close()

    if args.command == "log_direction":
        _emit(_memory_add(config=config, text=args.text, source=args.source))
        return

    if args.command == "memory_search":
        _emit(_memory_search(config=config, query=args.query, top_k=args.top_k))
        return

    if args.command == "develop":
        from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

        _emit(run_developer_tool(config=config, task=args.task, action="submit"))
        return

    if args.command == "develop_approve":
        from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

        _emit(run_developer_tool(config=config, approval_id=args.approval_id, action="approve"))
        return

    if args.command == "develop_deny":
        from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

        _emit(run_developer_tool(config=config, approval_id=args.approval_id, action="deny"))
        return

    if args.command == "develop_status":
        from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

        _emit(run_developer_tool(config=config, action="status"))
        return

    if args.command == "content_create":
        from content_studio import run_content_studio  # pylint: disable=import-outside-toplevel

        _emit(run_content_studio(config=config, brief_text=args.brief_text))
        return

    if args.command == "content_status":
        from content_studio import list_content_drafts  # pylint: disable=import-outside-toplevel

        _emit(list_content_drafts(config=config))
        return

    if args.command == "content_approve":
        from content_studio import decide_content_draft  # pylint: disable=import-outside-toplevel

        _emit(
            decide_content_draft(
                config=config,
                draft_id=args.draft_id,
                decision="approve",
                decision_by_user_id=args.decision_by_user_id,
                decision_note=args.decision_note,
            )
        )
        return

    if args.command == "content_deny":
        from content_studio import decide_content_draft  # pylint: disable=import-outside-toplevel

        _emit(
            decide_content_draft(
                config=config,
                draft_id=args.draft_id,
                decision="deny",
                decision_by_user_id=args.decision_by_user_id,
                decision_note=args.decision_note,
            )
        )
        return

    if args.command == "time_checkin":
        from time_tracking import log_time_checkin  # pylint: disable=import-outside-toplevel

        _emit(log_time_checkin(activity=args.activity, hours_saved=args.hours))
        return

    if args.command == "time_report":
        from time_tracking import check_r9_guardrail, get_time_saved_report  # pylint: disable=import-outside-toplevel

        report = get_time_saved_report(days=args.days)
        guard = check_r9_guardrail(weeks=max(1, args.days // 7))
        _emit({"ok": True, "report": report, "r9_guardrail": guard})
        return


if __name__ == "__main__":
    main()

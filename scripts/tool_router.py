"""Command router for Telegram-initiated directives and scheduled heartbeat jobs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from monitoring import check_website, daily_brief, load_config, read_bot_logs, run_trading_script


ROOT = Path(__file__).resolve().parents[1]


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
        choices=["all", "trading", "websites"],
        help="Division scope: all, trading, or websites.",
    )
    divisions.add_argument("--force", action="store_true", help="Force a fresh base brief before running divisions.")

    holding = sub.add_parser("run_holding", help="Run Phase 3 holding-company CEO orchestration.")
    holding.add_argument(
        "--mode",
        default="heartbeat",
        choices=["heartbeat", "board_review", "board_pack"],
        help="Holding mode: heartbeat (daily), board_review (deeper review), or board_pack (full Board Pack).",
    )
    holding.add_argument("--force", action="store_true", help="Force a fresh base brief before running holding mode.")

    commercial = sub.add_parser("run_commercial", help="Run Commercial Division: PNL roll-up, risk check, and brief.")
    commercial.add_argument("--force", action="store_true", help="Force a fresh base brief before running commercial.")

    score = sub.add_parser("score_initiative", help="Score a single initiative via Board Pack criteria (Commercial Analyst).")
    score.add_argument("--text", required=True, help="Initiative description to score.")

    mem_add = sub.add_parser("log_direction", help="Persist owner directive into vector memory.")
    mem_add.add_argument("--text", required=True, help="Directive text to persist.")
    mem_add.add_argument("--source", default="owner_chat", help="Source label for metadata.")

    mem_search = sub.add_parser("memory_search", help="Query local vector memory.")
    mem_search.add_argument("--query", required=True, help="Memory query text.")
    mem_search.add_argument("--top-k", type=int, default=5, help="Number of matches.")
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

    if args.command == "run_commercial":
        from commercial import run_commercial_division  # pylint: disable=import-outside-toplevel

        _emit(run_commercial_division(config=config, force=args.force))
        return

    if args.command == "score_initiative":
        from commercial import score_initiative  # pylint: disable=import-outside-toplevel

        _emit(score_initiative(initiative_text=args.text, config=config))
        return

    if args.command == "log_direction":
        _emit(_memory_add(config=config, text=args.text, source=args.source))
        return

    if args.command == "memory_search":
        _emit(_memory_search(config=config, query=args.query, top_k=args.top_k))
        return


if __name__ == "__main__":
    main()

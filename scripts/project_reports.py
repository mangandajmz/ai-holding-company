"""Rich local report wrappers for external project repos."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from utils import now_utc_iso as _now_utc, parse_float as _parse_float, parse_iso_utc as _parse_iso_utc, parse_polymarket_ts as _parse_polymarket_ts


def _tail_lines(path: Path, count: int = 120) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-max(1, count) :]


def _load_latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists() or not directory.is_dir():
        return None
    matches = list(directory.glob(pattern))
    if not matches:
        return None
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists() or not path.is_file():
        return {}
    output: dict[str, str] = {}
    try:
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            output[key.strip()] = value.strip().strip("\"'")
    except OSError:
        return {}
    return output


def _load_polymarket_state_db_path(repo: Path) -> tuple[Path, list[str]]:
    candidates: list[str] = [str(repo / "bot_state.db")]
    env_values = _load_env_file(repo / ".env")
    state_db = env_values.get("STATE_DB_PATH")
    if state_db:
        expanded = os.path.expandvars(state_db)
        state_path = Path(expanded)
        if not state_path.is_absolute():
            state_path = repo / state_path
        candidates.append(str(state_path))

    for candidate in candidates:
        candidate_path = Path(candidate)
        if candidate_path.exists():
            return candidate_path, candidates
    return Path(candidates[0]), candidates


def _scan_polymarket_csv(path: Path, starting_bankroll: float = 300.0) -> dict[str, Any]:
    rows = 0
    wins = 0
    losses = 0
    open_count = 0
    pnl_total = 0.0
    latest_ts = None
    equity = starting_bankroll
    peak_equity = starting_bankroll
    max_drawdown_usd = 0.0
    max_drawdown_pct = 0.0

    if not path.exists():
        return {
            "rows": 0,
            "wins": 0,
            "losses": 0,
            "open": 0,
            "pnl_total": 0.0,
            "latest_timestamp": None,
            "starting_bankroll": round(starting_bankroll, 4),
            "estimated_bankroll_current": round(starting_bankroll, 4),
            "max_drawdown_usd_total": 0.0,
            "max_drawdown_pct_total": 0.0,
        }

    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows += 1
                status = str(row.get("status", "")).strip().upper()
                if status == "WIN":
                    wins += 1
                elif status == "LOSS":
                    losses += 1
                else:
                    open_count += 1
                pnl = _parse_float(row.get("resolved_pnl"))
                if pnl is not None:
                    pnl_total += pnl
                    if status in ("WIN", "LOSS"):
                        equity += pnl
                        if equity > peak_equity:
                            peak_equity = equity
                        drawdown_usd = max(0.0, peak_equity - equity)
                        max_drawdown_usd = max(max_drawdown_usd, drawdown_usd)
                        if peak_equity > 0:
                            drawdown_pct = (drawdown_usd / peak_equity) * 100.0
                            max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)
                ts = row.get("timestamp")
                if ts:
                    latest_ts = ts
    except OSError:
        pass

    return {
        "rows": rows,
        "wins": wins,
        "losses": losses,
        "open": open_count,
        "pnl_total": round(pnl_total, 4),
        "latest_timestamp": latest_ts,
        "starting_bankroll": round(starting_bankroll, 4),
        "estimated_bankroll_current": round(equity, 4),
        "max_drawdown_usd_total": round(max_drawdown_usd, 4),
        "max_drawdown_pct_total": round(max_drawdown_pct, 4),
    }


def report_mt5(repo: Path) -> dict[str, Any]:
    runtime_log = repo / "logs" / "runtime" / "runtime.log"
    runtime_events = repo / "logs" / "runtime" / "runtime_events.jsonl"
    runtime_tail = _tail_lines(runtime_log, 120)

    last_cycle_line = ""
    for line in reversed(runtime_tail):
        if "cycle_completed" in line:
            last_cycle_line = line
            break

    events: list[dict[str, Any]] = []
    try:
        for line in runtime_events.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
    except OSError:
        events = []

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)

    trading_cycles_24h = 0
    trading_complete_24h = 0
    trading_no_trade_24h = 0
    research_cycles_24h = 0
    research_complete_24h = 0
    last_no_trade_reason = None
    last_health_snapshot: dict[str, Any] = {}
    last_cycle_completed_brief: dict[str, Any] = {}
    trading_durations: list[float] = []

    for event in events:
        timestamp = _parse_iso_utc(str(event.get("timestamp", "")))
        details = event.get("details", {}) if isinstance(event.get("details"), dict) else {}
        event_name = str(event.get("event", ""))

        if event_name == "cycle_started":
            health = details.get("health")
            if isinstance(health, dict):
                last_health_snapshot = health

        if event_name != "cycle_completed":
            continue

        result = details.get("result", {}) if isinstance(details.get("result"), dict) else {}
        cycle = str(details.get("cycle", result.get("cycle", "")))
        last_cycle_completed_brief = {
            "timestamp": event.get("timestamp"),
            "cycle": cycle,
            "status": result.get("status"),
            "mode": result.get("mode"),
            "reason": result.get("reason"),
            "duration_s": details.get("duration_s"),
        }
        if not timestamp or timestamp < cutoff:
            continue

        if cycle.startswith("trading"):
            trading_cycles_24h += 1
            if str(result.get("status")) == "complete":
                trading_complete_24h += 1
            if str(result.get("mode", "")) == "no_trade":
                trading_no_trade_24h += 1
                last_no_trade_reason = result.get("reason")
            duration = _parse_float(str(details.get("duration_s", "")))
            if duration is not None:
                trading_durations.append(duration)

        if cycle.startswith("research"):
            research_cycles_24h += 1
            if str(result.get("status")) == "complete":
                research_complete_24h += 1

    avg_trading_cycle_seconds = (
        round(sum(trading_durations) / len(trading_durations), 2) if trading_durations else None
    )

    latest_research_json = _load_latest_file(repo / "logs" / "research", "research_*.json")
    research_summary: dict[str, Any] = {}
    if latest_research_json:
        try:
            payload = json.loads(latest_research_json.read_text(encoding="utf-8"))
            summary = payload.get("summary", {})
            if isinstance(summary, dict):
                research_summary = {
                    "tested": summary.get("tested"),
                    "passed_backtest": summary.get("passed_backtest"),
                    "active_total": summary.get("active_total"),
                    "best_active_strategy": summary.get("best_active_strategy"),
                    "best_active_pf": summary.get("best_active_pf"),
                }
        except (OSError, json.JSONDecodeError, TypeError):
            research_summary = {}

    status = "ok"
    if not runtime_tail:
        status = "attention"
    elif "status 'complete'" not in last_cycle_line:
        status = "attention"

    checks = last_health_snapshot.get("checks", {}) if isinstance(last_health_snapshot.get("checks"), dict) else {}
    ollama_check = checks.get("ollama", {}) if isinstance(checks.get("ollama"), dict) else {}
    mt5_check = checks.get("mt5", {}) if isinstance(checks.get("mt5"), dict) else {}
    store_check = checks.get("strategy_store", {}) if isinstance(checks.get("strategy_store"), dict) else {}

    headline = (
        f"{trading_complete_24h}/{trading_cycles_24h} trading cycles complete in 24h; "
        f"no-trade cycles={trading_no_trade_24h}."
    )

    return {
        "ok": status == "ok",
        "status": status,
        "generated_at_utc": _now_utc(),
        "headline": headline,
        "repo": str(repo),
        "runtime_log": str(runtime_log),
        "runtime_events": str(runtime_events),
        "last_cycle_line": last_cycle_line,
        "trading_cycles_24h": trading_cycles_24h,
        "trading_complete_24h": trading_complete_24h,
        "trading_no_trade_24h": trading_no_trade_24h,
        "research_cycles_24h": research_cycles_24h,
        "research_complete_24h": research_complete_24h,
        "avg_trading_cycle_seconds": avg_trading_cycle_seconds,
        "last_no_trade_reason": last_no_trade_reason,
        "health_checks": {
            "ollama_ok": bool(ollama_check.get("ok")) if ollama_check else None,
            "mt5_ok": bool(mt5_check.get("ok")) if mt5_check else None,
            "strategy_store_ok": bool(store_check.get("ok")) if store_check else None,
            "strategy_store_active": store_check.get("active"),
            "strategy_store_pending_review": store_check.get("pending_review"),
            "strategy_store_best_pf": store_check.get("best_pf"),
            "mt5_server": mt5_check.get("server"),
            "mt5_login": mt5_check.get("login"),
        },
        "last_cycle_completed": last_cycle_completed_brief,
        "latest_research_json": str(latest_research_json) if latest_research_json else None,
        "research_summary": research_summary,
        "trade_events_24h": trading_cycles_24h,
    }


def report_polymarket(repo: Path) -> dict[str, Any]:
    log_path = repo / "bot.log"
    csv_path = repo / "paper_trades.csv"
    db_path, db_candidates = _load_polymarket_state_db_path(repo)

    lines = _tail_lines(log_path, 2500)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)
    ts_pattern = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC)\s+-\s+(.*)$")
    pnl_pattern = re.compile(r"pnl=([+-]?\d+(?:\.\d+)?)", flags=re.IGNORECASE)

    warns_24h = 0
    scale_events_24h = 0
    hybrid_sync_events_24h = 0
    resolved_pnls: list[float] = []
    wins = 0
    losses = 0
    latest_resolved_line = None

    for line in lines:
        message = line
        parsed_ts = None
        ts_match = ts_pattern.match(line)
        if ts_match:
            parsed_ts = _parse_polymarket_ts(ts_match.group(1))
            message = ts_match.group(2)

        in_window = parsed_ts is None or parsed_ts >= cutoff
        if not in_window:
            continue

        lower = message.lower()
        if "[warn]" in lower or "error" in lower or "exception" in lower:
            warns_24h += 1
        if "scale up available" in lower:
            scale_events_24h += 1
        if "[hybrid]" in lower and "synced" in lower:
            hybrid_sync_events_24h += 1

        pnl_match = pnl_pattern.search(message)
        if pnl_match:
            value = _parse_float(pnl_match.group(1))
            if value is not None:
                resolved_pnls.append(value)
                latest_resolved_line = line

        if "→ WIN" in message or "-> WIN" in message or "â†’ WIN" in message:
            wins += 1
        if "→ LOSS" in message or "-> LOSS" in message or "â†’ LOSS" in message:
            losses += 1

    # STARTING_BANKROLL is read from the local .env when available (local runs only).
    # On remote-sync paths, the .env is NOT synced; fall back to the default.
    env_values = _load_env_file(repo / ".env")
    starting_bankroll = _parse_float(env_values.get("STARTING_BANKROLL")) or 300.0
    csv_summary = _scan_polymarket_csv(csv_path, starting_bankroll=starting_bankroll)
    resolved_count = len(resolved_pnls)
    win_rate_24h = round((wins / resolved_count) * 100.0, 2) if resolved_count else None
    net_pnl_24h = round(sum(resolved_pnls), 4)
    gross_win_pnl_24h = round(sum(value for value in resolved_pnls if value > 0), 4)
    gross_loss_pnl_24h = round(sum(value for value in resolved_pnls if value < 0), 4)

    status = "ok"
    notes: list[str] = []
    if not db_path.exists():
        status = "attention"
        notes.append("State DB missing at configured paths; health_check.py may fail until bot writes DB.")
    if warns_24h > 0:
        status = "attention"
        notes.append(f"{warns_24h} warning/error line(s) found in bot.log over last 24h.")
    if resolved_count == 0:
        notes.append("No resolved trades detected in last 24h log window.")

    headline = (
        f"resolved_24h={resolved_count}, win_rate_24h={win_rate_24h if win_rate_24h is not None else 'n/a'}%, "
        f"net_pnl_24h={net_pnl_24h:+.2f}, warns_24h={warns_24h}."
    )

    return {
        "ok": status == "ok",
        "status": status,
        "generated_at_utc": _now_utc(),
        "headline": headline,
        "repo": str(repo),
        "state_db_path": str(db_path),
        "state_db_candidates": db_candidates,
        "db_exists": db_path.exists(),
        "csv_rows": csv_summary["rows"],
        "csv_pnl_total": csv_summary["pnl_total"],
        "csv_wins": csv_summary["wins"],
        "csv_losses": csv_summary["losses"],
        "csv_open": csv_summary["open"],
        "csv_latest_timestamp": csv_summary["latest_timestamp"],
        "starting_bankroll": csv_summary.get("starting_bankroll"),
        "estimated_bankroll_current": csv_summary.get("estimated_bankroll_current"),
        "max_drawdown_usd_total": csv_summary.get("max_drawdown_usd_total"),
        "max_drawdown_pct_total": csv_summary.get("max_drawdown_pct_total"),
        "recent_resolved_count_24h": resolved_count,
        "recent_wins_24h": wins,
        "recent_losses_24h": losses,
        "win_rate_24h": win_rate_24h,
        "net_pnl_24h": net_pnl_24h,
        "gross_win_pnl_24h": gross_win_pnl_24h,
        "gross_loss_pnl_24h": gross_loss_pnl_24h,
        "warning_lines_24h": warns_24h,
        "scale_events_24h": scale_events_24h,
        "hybrid_sync_events_24h": hybrid_sync_events_24h,
        "latest_resolved_line": latest_resolved_line,
        "notes": notes,
        "last_log_lines": lines[-12:],
        "trade_events_24h": resolved_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Rich project report wrapper.")
    parser.add_argument("project", choices=["mt5", "polymarket"], help="Project report type.")
    parser.add_argument("--repo", default=".", help="Project repository path.")
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if args.project == "mt5":
        print(json.dumps(report_mt5(repo), indent=2))
        return
    print(json.dumps(report_polymarket(repo), indent=2))


if __name__ == "__main__":
    main()

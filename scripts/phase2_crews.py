"""Phase 2 multi-division orchestration using CrewAI hierarchical crews."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from monitoring import ROOT, daily_brief


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:  # noqa: D401
        return "{" + key + "}"


def _render_template(template: str, values: dict[str, str]) -> str:
    return template.format_map(_SafeDict(values))


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"YAML mapping expected: {path}")
    return loaded


def _phase2_cfg(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("phase2", {})
    return value if isinstance(value, dict) else {}


def _load_shared_targets(config: dict[str, Any]) -> dict[str, Any]:
    phase3_cfg = config.get("phase3", {})
    phase3_cfg = phase3_cfg if isinstance(phase3_cfg, dict) else {}
    targets_rel = str(phase3_cfg.get("targets_file", "config/targets.yaml")).strip()
    if not targets_rel:
        return {}
    targets_path = ROOT / targets_rel if not Path(targets_rel).is_absolute() else Path(targets_rel)
    if not targets_path.exists():
        return {}
    try:
        loaded = _load_yaml(targets_path)
    except Exception:  # noqa: BLE001
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _reports_dir(config: dict[str, Any]) -> Path:
    rel = str(config.get("paths", {}).get("reports_dir", "reports"))
    path = ROOT / rel
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_latest_brief_payload(config: dict[str, Any]) -> dict[str, Any]:
    latest = _reports_dir(config) / "daily_brief_latest.json"
    if not latest.exists():
        raise FileNotFoundError(f"Missing latest brief payload: {latest}")
    with latest.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Latest brief payload must be a JSON object.")
    return payload


def _ensure_brief_payload(config: dict[str, Any], force: bool) -> tuple[dict[str, Any], str]:
    fresh = daily_brief(config=config, force=force)
    if not fresh.get("skipped"):
        return fresh, "fresh"
    return _load_latest_brief_payload(config=config), "cached_latest"


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    token = str(value).strip().replace(",", "")
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _parse_iso_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_polymarket_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    token = str(value).strip().replace(",", "")
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _fmt_num(value: Any, digits: int = 2) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:.{digits}f}"


def _fmt_money(value: Any) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return "n/a"
    return f"${parsed:+,.2f}"


def _fmt_pct(value: Any, digits: int = 1) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:.{digits}f}%"


def _fmt_age_minutes(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 60:
        return f"{int(round(value))}m"
    hours = value / 60.0
    if hours < 48:
        return f"{hours:.1f}h"
    days = hours / 24.0
    return f"{days:.1f}d"


def _status_worst(statuses: list[str]) -> str:
    if "RED" in statuses:
        return "RED"
    if "AMBER" in statuses:
        return "AMBER"
    return "GREEN"


def _as_status_line(metric: str, target: str, actual: str, variance: str, status: str, action: str) -> dict[str, str]:
    return {
        "metric": metric,
        "target": target,
        "actual": actual,
        "variance": variance,
        "status": status,
        "action": action,
    }


_ALLOWED_TOOL_ROUTER_SUBCOMMANDS: dict[str, dict[str, Any]] = {
    "daily_brief": {"required": set(), "allowed_flags": {"--force", "--config"}},
    "run_divisions": {"required": set(), "allowed_flags": {"--division", "--force", "--config"}},
    "run_holding": {"required": {"--mode"}, "allowed_flags": {"--mode", "--force", "--config"}},
    "read_bot_logs": {"required": {"--bot"}, "allowed_flags": {"--bot", "--lines", "--config"}},
    "check_website": {"required": {"--website"}, "allowed_flags": {"--website", "--config"}},
    "run_trading_script": {
        "required": {"--bot", "--command-key"},
        "allowed_flags": {"--bot", "--command-key", "--extra-args", "--timeout-sec", "--config"},
    },
    "log_direction": {"required": {"--text"}, "allowed_flags": {"--text", "--source", "--config"}},
    "memory_search": {"required": {"--query"}, "allowed_flags": {"--query", "--top-k", "--config"}},
}


def _is_allowlisted_tool_router_command(command: str) -> bool:
    tokens = command.strip().split()
    if len(tokens) < 3:
        return False
    if tokens[0].lower() != "python":
        return False

    router_token = tokens[1].replace("\\", "/").lower()
    if not (router_token == "scripts/tool_router.py" or router_token.endswith("/scripts/tool_router.py")):
        return False

    subcommand = tokens[2]
    spec = _ALLOWED_TOOL_ROUTER_SUBCOMMANDS.get(subcommand)
    if spec is None:
        return False

    required = set(spec.get("required", set()))
    allowed_flags = set(spec.get("allowed_flags", set()))
    seen_flags: set[str] = set()
    for token in tokens[3:]:
        if not token.startswith("--"):
            continue
        if token not in allowed_flags:
            return False
        seen_flags.add(token)
    return required.issubset(seen_flags)


def _sanitize_model_output(text: str) -> tuple[str, bool]:
    cleaned = text.strip()
    markers = [
        "Here is the markdown report:",
        "Here is the markdown analysis:",
        "Here is the markdown analysis report:",
    ]
    for marker in markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker, 1)[1].strip()

    blocked = False

    def _replace_inline_command(match: re.Match[str]) -> str:
        nonlocal blocked
        candidate = match.group(1).strip()
        if candidate.lower().startswith("python "):
            if _is_allowlisted_tool_router_command(candidate):
                return f"`{candidate}`"
            blocked = True
            return "`[blocked command removed]`"
        return match.group(0)

    cleaned = re.sub(r"`([^`\n]+)`", _replace_inline_command, cleaned)
    safe_lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.lower().startswith("python "):
            if _is_allowlisted_tool_router_command(stripped):
                safe_lines.append(line)
            else:
                blocked = True
            continue
        safe_lines.append(line)

    return "\n".join(safe_lines).strip(), blocked


def _score_trading(brief_payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    shared_targets = _load_shared_targets(config)
    phase2_targets = _phase2_cfg(config).get("targets", {})
    phase2_targets = phase2_targets if isinstance(phase2_targets, dict) else {}
    trading_targets = shared_targets.get("trading", {})
    if not isinstance(trading_targets, dict):
        trading_targets = phase2_targets.get("trading", {})
    trading_targets = trading_targets if isinstance(trading_targets, dict) else {}
    mt5_targets = trading_targets.get("mt5", {})
    mt5_targets = mt5_targets if isinstance(mt5_targets, dict) else {}
    mt5_window = mt5_targets.get("monitor_window_utc", {})
    mt5_window = mt5_window if isinstance(mt5_window, dict) else {}
    poly_targets = trading_targets.get("polymarket", {})
    poly_targets = poly_targets if isinstance(poly_targets, dict) else {}

    max_cycle_age_min = _to_float(mt5_targets.get("max_cycle_age_minutes")) or 180.0
    min_active_strats = _to_int(mt5_targets.get("min_active_strategies")) or 1
    required_pf = _to_float(mt5_targets.get("min_best_pf")) or 1.3
    window_start = _to_int(mt5_window.get("start_hour"))
    window_end = _to_int(mt5_window.get("end_hour"))
    run_weekends = bool(mt5_window.get("run_weekends", False))
    daily_loss_cap = _to_float(poly_targets.get("daily_loss_cap_usd")) or 60.0
    max_warn_24h = _to_int(poly_targets.get("max_warning_lines_24h")) or 2
    max_open_positions = _to_int(poly_targets.get("max_open_positions")) or 12
    max_trade_age_h = _to_float(poly_targets.get("max_trade_data_age_hours")) or 72.0
    min_resolved_24h = _to_int(poly_targets.get("min_resolved_trades_24h")) or 1

    bots = brief_payload.get("bots", [])
    bots = bots if isinstance(bots, list) else []
    mt5_bot = next((b for b in bots if isinstance(b, dict) and str(b.get("id")) == "mt5_desk"), None)
    poly_bot = next((b for b in bots if isinstance(b, dict) and str(b.get("id")) == "polymarket"), None)
    remote_sync = brief_payload.get("remote_sync", {})
    remote_sync = remote_sync if isinstance(remote_sync, dict) else {}
    remote_bots = remote_sync.get("bots", [])
    remote_bots = remote_bots if isinstance(remote_bots, list) else []
    poly_remote = next((b for b in remote_bots if isinstance(b, dict) and str(b.get("bot_id")) == "polymarket"), None)

    generated_at = _parse_iso_utc(brief_payload.get("generated_at_utc")) or datetime.now(timezone.utc)
    items: list[dict[str, str]] = []
    risks: list[str] = []
    actions: list[str] = []

    mt5_report = mt5_bot.get("report_payload", {}) if isinstance(mt5_bot, dict) else {}
    mt5_report = mt5_report if isinstance(mt5_report, dict) else {}
    mt5_checks = mt5_report.get("health_checks", {})
    mt5_checks = mt5_checks if isinstance(mt5_checks, dict) else {}
    mt5_deps_ok = all(bool(mt5_checks.get(key)) for key in ["ollama_ok", "mt5_ok", "strategy_store_ok"])
    dep_status = "GREEN" if mt5_deps_ok else "RED"
    dep_variance = "all dependencies healthy" if mt5_deps_ok else "dependency failure detected"
    items.append(
        _as_status_line(
            metric="MT5 dependencies",
            target="ollama_ok, mt5_ok, strategy_store_ok = true",
            actual=(
                f"ollama={mt5_checks.get('ollama_ok')} "
                f"mt5={mt5_checks.get('mt5_ok')} "
                f"store={mt5_checks.get('strategy_store_ok')}"
            ),
            variance=dep_variance,
            status=dep_status,
            action="Run `python scripts/tool_router.py run_trading_script --bot mt5_desk --command-key health` and inspect failed dependency.",
        )
    )
    if dep_status == "RED":
        risks.append("MT5 dependency health is failing.")
        actions.append("Fix MT5/Ollama/strategy-store health before enabling execution.")

    active_strats = _to_int(mt5_checks.get("strategy_store_active"))
    active_status = "GREEN" if (active_strats is not None and active_strats >= min_active_strats) else "RED"
    items.append(
        _as_status_line(
            metric="Active validated strategies",
            target=f">= {min_active_strats}",
            actual=str(active_strats) if active_strats is not None else "n/a",
            variance=(
                f"{active_strats - min_active_strats:+d}" if active_strats is not None else "missing"
            ),
            status=active_status,
            action="Run MT5 research cycle and promote validated candidates if active strategy count is low.",
        )
    )
    if active_status == "RED":
        risks.append("MT5 active strategy library is below minimum target.")
        actions.append("Schedule research cycle and review pending strategies for promotion.")

    best_pf = _to_float(mt5_checks.get("strategy_store_best_pf"))
    if best_pf is None:
        pf_status = "AMBER"
        pf_variance = "missing"
    elif best_pf >= required_pf:
        pf_status = "GREEN"
        pf_variance = f"{best_pf - required_pf:+.2f}"
    elif best_pf >= required_pf - 0.2:
        pf_status = "AMBER"
        pf_variance = f"{best_pf - required_pf:+.2f}"
    else:
        pf_status = "RED"
        pf_variance = f"{best_pf - required_pf:+.2f}"
    items.append(
        _as_status_line(
            metric="Best active strategy PF",
            target=f">= {required_pf:.2f}",
            actual=_fmt_num(best_pf, 2),
            variance=pf_variance,
            status=pf_status,
            action="If PF drops, pause weakest strategy and run research/backtest refresh.",
        )
    )
    if pf_status != "GREEN":
        risks.append("MT5 best active profit factor is near or below target.")

    last_cycle = mt5_report.get("last_cycle_completed", {})
    last_cycle = last_cycle if isinstance(last_cycle, dict) else {}
    mt5_last_ts = _parse_iso_utc(last_cycle.get("timestamp"))
    cycle_age_min = ((generated_at - mt5_last_ts).total_seconds() / 60.0) if mt5_last_ts else None
    within_hours = True
    if window_start is not None and window_end is not None:
        current_hour = generated_at.hour
        if window_start <= window_end:
            within_hours = window_start <= current_hour < window_end
        else:
            within_hours = current_hour >= window_start or current_hour < window_end
    if not run_weekends and generated_at.weekday() >= 5:
        within_hours = False
    if cycle_age_min is None:
        cycle_status = "RED"
        cycle_variance = "missing"
    elif cycle_age_min <= max_cycle_age_min:
        cycle_status = "GREEN"
        cycle_variance = f"{cycle_age_min - max_cycle_age_min:+.0f}m"
    elif not within_hours and cycle_age_min <= max_cycle_age_min * 12:
        cycle_status = "AMBER"
        cycle_variance = f"{cycle_age_min - max_cycle_age_min:+.0f}m (outside scheduled window)"
    elif cycle_age_min <= max_cycle_age_min * 2:
        cycle_status = "AMBER"
        cycle_variance = f"{cycle_age_min - max_cycle_age_min:+.0f}m"
    else:
        cycle_status = "RED"
        cycle_variance = f"{cycle_age_min - max_cycle_age_min:+.0f}m"
    items.append(
        _as_status_line(
            metric="MT5 cycle freshness",
            target=f"last cycle age <= {int(max_cycle_age_min)}m",
            actual=_fmt_age_minutes(cycle_age_min),
            variance=cycle_variance,
            status=cycle_status,
            action="If stale, restart scheduler and verify `logs/runtime/runtime_events.jsonl` is advancing.",
        )
    )
    if cycle_status == "RED":
        risks.append("MT5 scheduler appears stale for the expected operating cadence.")
        actions.append("Restart MT5 scheduler and verify trading/research cycles resume.")

    poly_service_stdout = ""
    service_rc = None
    if isinstance(poly_remote, dict):
        service = poly_remote.get("service_check", {})
        service = service if isinstance(service, dict) else {}
        poly_service_stdout = str(service.get("stdout", "")).strip().lower()
        service_rc = _to_int(service.get("return_code"))

    service_ok = "active" in poly_service_stdout
    service_inactive = any(token in poly_service_stdout for token in ["inactive", "failed", "deactivating"])
    if service_ok:
        service_status = "GREEN"
        service_variance = "active"
    elif service_inactive and service_rc is not None and service_rc != 0:
        service_status = "RED"
        service_variance = "inactive"
    else:
        service_status = "AMBER"
        service_variance = "status not confirmed"
    items.append(
        _as_status_line(
            metric="Polymarket VPS service",
            target="systemd status = active",
            actual=poly_service_stdout or "unknown",
            variance=service_variance,
            status=service_status,
            action="Run `ssh ... systemctl status polymarket-bot` and restart service if inactive.",
        )
    )
    if service_status == "RED":
        risks.append("Polymarket bot service is not confirmed active.")
        actions.append("Restore polymarket-bot systemd service health on VPS.")

    poly_report = poly_bot.get("report_payload", {}) if isinstance(poly_bot, dict) else {}
    poly_report = poly_report if isinstance(poly_report, dict) else {}
    net_pnl_24h = _to_float(poly_report.get("net_pnl_24h"))
    if net_pnl_24h is None:
        pnl_status = "AMBER"
        pnl_variance = "missing"
    elif net_pnl_24h >= -daily_loss_cap:
        pnl_status = "GREEN"
        pnl_variance = f"{net_pnl_24h + daily_loss_cap:+.2f} vs loss cap buffer"
    else:
        pnl_status = "RED"
        pnl_variance = f"{net_pnl_24h + daily_loss_cap:+.2f} below cap"
    items.append(
        _as_status_line(
            metric="Polymarket 24h net PnL vs daily loss cap",
            target=f">= -${daily_loss_cap:.2f}",
            actual=_fmt_money(net_pnl_24h),
            variance=pnl_variance,
            status=pnl_status,
            action="If RED, reduce BASE_BET/MAX_BET and pause new entries pending root-cause review.",
        )
    )
    if pnl_status == "RED":
        risks.append("Polymarket 24h losses exceeded configured daily loss cap.")
        actions.append("Reduce position sizing and enforce stricter entry filters immediately.")

    warn_24h = _to_int(poly_report.get("warning_lines_24h"))
    if warn_24h is None:
        warn_status = "AMBER"
        warn_variance = "missing"
    elif warn_24h <= max_warn_24h:
        warn_status = "GREEN"
        warn_variance = f"{warn_24h - max_warn_24h:+d}"
    elif warn_24h <= max_warn_24h + 3:
        warn_status = "AMBER"
        warn_variance = f"{warn_24h - max_warn_24h:+d}"
    else:
        warn_status = "RED"
        warn_variance = f"{warn_24h - max_warn_24h:+d}"
    items.append(
        _as_status_line(
            metric="Polymarket warning/error lines (24h)",
            target=f"<= {max_warn_24h}",
            actual=str(warn_24h) if warn_24h is not None else "n/a",
            variance=warn_variance,
            status=warn_status,
            action="Inspect bot.log warning cluster and patch root causes before scaling risk.",
        )
    )
    if warn_status != "GREEN":
        risks.append("Polymarket warning volume is elevated or missing.")

    csv_open = _to_int(poly_report.get("csv_open"))
    if csv_open is None:
        open_status = "AMBER"
        open_variance = "missing"
    elif csv_open <= max_open_positions:
        open_status = "GREEN"
        open_variance = f"{csv_open - max_open_positions:+d}"
    elif csv_open <= max_open_positions + 5:
        open_status = "AMBER"
        open_variance = f"{csv_open - max_open_positions:+d}"
    else:
        open_status = "RED"
        open_variance = f"{csv_open - max_open_positions:+d}"
    items.append(
        _as_status_line(
            metric="Polymarket open positions",
            target=f"<= {max_open_positions}",
            actual=str(csv_open) if csv_open is not None else "n/a",
            variance=open_variance,
            status=open_status,
            action="If open exposure is high, tighten entry gating and let resolution loop de-risk.",
        )
    )

    csv_latest_ts = _parse_polymarket_ts(poly_report.get("csv_latest_timestamp"))
    trade_age_h = ((generated_at - csv_latest_ts).total_seconds() / 3600.0) if csv_latest_ts else None
    if trade_age_h is None:
        age_status = "AMBER"
        age_variance = "missing"
    elif trade_age_h <= max_trade_age_h:
        age_status = "GREEN"
        age_variance = f"{trade_age_h - max_trade_age_h:+.1f}h"
    elif trade_age_h <= max_trade_age_h * 1.5:
        age_status = "AMBER"
        age_variance = f"{trade_age_h - max_trade_age_h:+.1f}h"
    else:
        age_status = "RED"
        age_variance = f"{trade_age_h - max_trade_age_h:+.1f}h"
    items.append(
        _as_status_line(
            metric="Polymarket latest resolved-trade data age",
            target=f"<= {max_trade_age_h:.0f}h",
            actual=_fmt_age_minutes(trade_age_h * 60.0 if trade_age_h is not None else None),
            variance=age_variance,
            status=age_status,
            action="If stale, verify remote sync and confirm resolution loop is recording settlements.",
        )
    )

    resolved_24h = _to_int(poly_report.get("recent_resolved_count_24h"))
    if resolved_24h is None:
        resolved_status = "AMBER"
        resolved_variance = "missing"
    elif resolved_24h >= min_resolved_24h:
        resolved_status = "GREEN"
        resolved_variance = f"{resolved_24h - min_resolved_24h:+d}"
    else:
        resolved_status = "AMBER"
        resolved_variance = f"{resolved_24h - min_resolved_24h:+d}"
    items.append(
        _as_status_line(
            metric="Polymarket resolved trades in 24h",
            target=f">= {min_resolved_24h}",
            actual=str(resolved_24h) if resolved_24h is not None else "n/a",
            variance=resolved_variance,
            status=resolved_status,
            action="If persistently low, review market-selection filters and watchlist coverage.",
        )
    )

    statuses = [item["status"] for item in items]
    summary_status = _status_worst(statuses)
    if not actions:
        actions.append("No urgent corrective actions required; keep monitoring cadence.")
    return {
        "goal": "Run conservative, safety-first trading operations with validated strategy execution and enforced risk caps.",
        "desired_outcome": (
            "MT5 dependency health remains green, strategy quality stays above minimum PF, "
            "and Polymarket risk controls (loss cap/exposure/warnings) stay within configured bounds."
        ),
        "status": summary_status,
        "items": items,
        "risks": risks[:5],
        "actions": actions[:5],
    }


def _score_websites(brief_payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    shared_targets = _load_shared_targets(config)
    phase2_targets = _phase2_cfg(config).get("targets", {})
    phase2_targets = phase2_targets if isinstance(phase2_targets, dict) else {}
    websites_targets = shared_targets.get("websites", {})
    if not isinstance(websites_targets, dict):
        websites_targets = phase2_targets.get("websites", {})
    websites_targets = websites_targets if isinstance(websites_targets, dict) else {}

    min_uptime_ratio = _to_float(websites_targets.get("snapshot_uptime_ratio_min")) or 1.0
    max_latency_ms = _to_float(websites_targets.get("max_latency_ms")) or 500.0
    max_sitemap_age_days = _to_float(websites_targets.get("max_sitemap_age_days")) or 14.0
    max_research_age_days = _to_float(websites_targets.get("max_research_report_age_days")) or 8.0

    generated_at = _parse_iso_utc(brief_payload.get("generated_at_utc")) or datetime.now(timezone.utc)
    websites = brief_payload.get("websites", [])
    websites = websites if isinstance(websites, list) else []
    items: list[dict[str, str]] = []
    risks: list[str] = []
    actions: list[str] = []

    total = len([w for w in websites if isinstance(w, dict)])
    up = len([w for w in websites if isinstance(w, dict) and bool(w.get("ok"))])
    ratio = (up / total) if total else None
    if ratio is None:
        uptime_status = "RED"
        uptime_variance = "missing"
    elif ratio >= min_uptime_ratio:
        uptime_status = "GREEN"
        uptime_variance = f"{ratio - min_uptime_ratio:+.2f}"
    elif ratio >= max(0.5, min_uptime_ratio - 0.25):
        uptime_status = "AMBER"
        uptime_variance = f"{ratio - min_uptime_ratio:+.2f}"
    else:
        uptime_status = "RED"
        uptime_variance = f"{ratio - min_uptime_ratio:+.2f}"
    items.append(
        _as_status_line(
            metric="Website availability snapshot",
            target=f">= {min_uptime_ratio*100:.0f}% ({'all sites up' if min_uptime_ratio >= 1 else 'uptime target'})",
            actual=(f"{ratio*100:.0f}% ({up}/{total})" if ratio is not None else "n/a"),
            variance=uptime_variance,
            status=uptime_status,
            action="For any DOWN site, run `/site <id>` and verify DNS/TCP and deployment logs.",
        )
    )
    if uptime_status != "GREEN":
        risks.append("One or more managed websites are down in the current snapshot.")
        actions.append("Prioritize incident triage for down sites before content/feature work.")

    latencies = [_to_float(w.get("latency_ms")) for w in websites if isinstance(w, dict)]
    latencies = [v for v in latencies if v is not None]
    max_latency = max(latencies) if latencies else None
    if max_latency is None:
        latency_status = "AMBER"
        latency_variance = "missing"
    elif max_latency <= max_latency_ms:
        latency_status = "GREEN"
        latency_variance = f"{max_latency - max_latency_ms:+.0f}ms"
    elif max_latency <= max_latency_ms * 1.5:
        latency_status = "AMBER"
        latency_variance = f"{max_latency - max_latency_ms:+.0f}ms"
    else:
        latency_status = "RED"
        latency_variance = f"{max_latency - max_latency_ms:+.0f}ms"
    items.append(
        _as_status_line(
            metric="Website latency ceiling (snapshot max)",
            target=f"<= {int(max_latency_ms)}ms",
            actual=(f"{max_latency:.0f}ms" if max_latency is not None else "n/a"),
            variance=latency_variance,
            status=latency_status,
            action="If AMBER/RED, profile origin response and CDN/cache behavior for the slowest site.",
        )
    )
    if latency_status == "RED":
        risks.append("Website latency is materially above target.")

    dns_tcp_all = True
    for site in websites:
        if not isinstance(site, dict):
            continue
        network = site.get("network_diag", {})
        network = network if isinstance(network, dict) else {}
        if not bool(network.get("dns_ok")) or not bool(network.get("tcp_443_ok")):
            dns_tcp_all = False
            break
    dns_status = "GREEN" if dns_tcp_all else "RED"
    items.append(
        _as_status_line(
            metric="DNS + TCP(443) reachability",
            target="all managed domains dns_ok=true and tcp_443_ok=true",
            actual="all healthy" if dns_tcp_all else "one or more failing",
            variance="0 failures" if dns_tcp_all else ">=1 failure",
            status=dns_status,
            action="Fix DNS/edge/network path issues before app-level debugging.",
        )
    )
    if dns_status == "RED":
        risks.append("Network reachability issue detected for at least one website.")
        actions.append("Escalate DNS/TCP remediation for impacted domain.")

    freeghost = next((w for w in websites if isinstance(w, dict) and str(w.get("id")) == "freeghosttools"), None)
    freeghost_age_days = None
    if isinstance(freeghost, dict):
        lastmod = freeghost.get("local_diag", {})
        lastmod = lastmod if isinstance(lastmod, dict) else {}
        lastmod_text = lastmod.get("sitemap_latest_lastmod")
        parsed = _parse_iso_utc(lastmod_text)
        if parsed is None and lastmod_text:
            try:
                parsed = datetime.strptime(str(lastmod_text), "%Y-%m-%d").replace(tzinfo=timezone.utc)
            except ValueError:
                parsed = None
        if parsed is not None:
            freeghost_age_days = (generated_at - parsed).total_seconds() / 86400.0
    if freeghost_age_days is None:
        ghost_status = "AMBER"
        ghost_variance = "missing"
    elif freeghost_age_days <= max_sitemap_age_days:
        ghost_status = "GREEN"
        ghost_variance = f"{freeghost_age_days - max_sitemap_age_days:+.1f}d"
    elif freeghost_age_days <= max_sitemap_age_days * 1.5:
        ghost_status = "AMBER"
        ghost_variance = f"{freeghost_age_days - max_sitemap_age_days:+.1f}d"
    else:
        ghost_status = "RED"
        ghost_variance = f"{freeghost_age_days - max_sitemap_age_days:+.1f}d"
    items.append(
        _as_status_line(
            metric="FreeGhostTools sitemap freshness",
            target=f"latest sitemap lastmod age <= {max_sitemap_age_days:.0f}d",
            actual=_fmt_age_minutes((freeghost_age_days * 24 * 60) if freeghost_age_days is not None else None),
            variance=ghost_variance,
            status=ghost_status,
            action="If stale, refresh sitemap/deploy pipeline so content updates are indexed promptly.",
        )
    )
    if ghost_status == "RED":
        risks.append("FreeGhostTools sitemap metadata is stale.")

    fth = next((w for w in websites if isinstance(w, dict) and str(w.get("id")) == "freetraderhub"), None)
    report_age_days = None
    if isinstance(fth, dict):
        diag = fth.get("local_diag", {})
        diag = diag if isinstance(diag, dict) else {}
        latest_mtime = _parse_iso_utc(diag.get("local_reports_latest_mtime_utc"))
        if latest_mtime is not None:
            report_age_days = (generated_at - latest_mtime).total_seconds() / 86400.0
    if report_age_days is None:
        report_status = "AMBER"
        report_variance = "missing"
    elif report_age_days <= max_research_age_days:
        report_status = "GREEN"
        report_variance = f"{report_age_days - max_research_age_days:+.1f}d"
    elif report_age_days <= max_research_age_days * 2:
        report_status = "AMBER"
        report_variance = f"{report_age_days - max_research_age_days:+.1f}d"
    else:
        report_status = "RED"
        report_variance = f"{report_age_days - max_research_age_days:+.1f}d"
    items.append(
        _as_status_line(
            metric="FreeTraderHub research brief freshness",
            target=f"latest executive brief age <= {max_research_age_days:.0f}d (weekly cadence)",
            actual=_fmt_age_minutes((report_age_days * 24 * 60) if report_age_days is not None else None),
            variance=report_variance,
            status=report_status,
            action="If stale, run free-traderhub weekly crew and publish fresh brief/output package.",
        )
    )
    if report_status != "GREEN":
        risks.append("FreeTraderHub research reports are stale relative to weekly operating cadence.")
        actions.append("Run `free-traderhub-research-team` weekly pipeline to refresh strategy/content signals.")

    statuses = [item["status"] for item in items]
    summary_status = _status_worst(statuses)
    if not actions:
        actions.append("No urgent website corrective actions required; maintain daily heartbeat checks.")
    return {
        "goal": "Keep managed web properties reachable, fast, and operationally fresh for growth workflows.",
        "desired_outcome": (
            "All sites remain up with healthy latency/network diagnostics, while sitemap and research outputs "
            "stay fresh enough to support traffic and decision workflows."
        ),
        "status": summary_status,
        "items": items,
        "risks": risks[:5],
        "actions": actions[:5],
    }


def _build_division_scorecard(division: str, brief_payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    if division == "trading":
        return _score_trading(brief_payload=brief_payload, config=config)
    return _score_websites(brief_payload=brief_payload, config=config)


def _compact_trading_bots(brief_payload: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for bot in brief_payload.get("bots", []):
        if not isinstance(bot, dict):
            continue
        report = bot.get("report_payload", {})
        report = report if isinstance(report, dict) else {}
        output.append(
            {
                "id": bot.get("id"),
                "name": bot.get("name"),
                "status": bot.get("status"),
                "data_source": bot.get("data_source"),
                "pnl_total": bot.get("pnl_total"),
                "trades_total": bot.get("trades_total"),
                "error_lines_total": bot.get("error_lines_total"),
                "report_status": report.get("status"),
                "report_headline": report.get("headline"),
                "trade_events_24h": report.get("trade_events_24h"),
                "recent_resolved_count_24h": report.get("recent_resolved_count_24h"),
                "win_rate_24h": report.get("win_rate_24h"),
                "net_pnl_24h": report.get("net_pnl_24h"),
                "warning_lines_24h": report.get("warning_lines_24h"),
                "csv_rows": report.get("csv_rows"),
                "csv_latest_timestamp": report.get("csv_latest_timestamp"),
            }
        )
    return output


def _compact_websites(brief_payload: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for site in brief_payload.get("websites", []):
        if not isinstance(site, dict):
            continue
        network = site.get("network_diag", {})
        network = network if isinstance(network, dict) else {}
        local_diag = site.get("local_diag", {})
        local_diag = local_diag if isinstance(local_diag, dict) else {}
        output.append(
            {
                "id": site.get("id"),
                "name": site.get("name"),
                "url": site.get("url"),
                "ok": site.get("ok"),
                "status_code": site.get("status_code"),
                "latency_ms": site.get("latency_ms"),
                "probe_mode": site.get("probe_mode"),
                "reason": site.get("reason"),
                "dns_ok": network.get("dns_ok"),
                "tcp_443_ok": network.get("tcp_443_ok"),
                "local_project_exists": local_diag.get("local_project_exists"),
                "sitemap_latest_lastmod": local_diag.get("sitemap_latest_lastmod"),
                "local_reports_latest_mtime_utc": local_diag.get("local_reports_latest_mtime_utc"),
            }
        )
    return output


def _build_inputs(brief_payload: dict[str, Any], division: str) -> dict[str, str]:
    summary = brief_payload.get("summary", {})
    summary = summary if isinstance(summary, dict) else {}
    alerts = brief_payload.get("alerts", [])
    alerts = alerts if isinstance(alerts, list) else []

    inputs: dict[str, str] = {
        "company_name": str(brief_payload.get("company_name", "AI Holding Company")),
        "generated_at_utc": str(brief_payload.get("generated_at_utc", _now_utc_iso())),
        "summary_json": json.dumps(summary, indent=2),
        "alerts_json": json.dumps(alerts, indent=2),
    }
    if division == "trading":
        inputs["bots_json"] = json.dumps(_compact_trading_bots(brief_payload), indent=2)
    if division == "websites":
        inputs["websites_json"] = json.dumps(_compact_websites(brief_payload), indent=2)
    return inputs


def _build_llm(config: dict[str, Any]) -> tuple[Any | None, str | None]:
    phase2 = _phase2_cfg(config)
    crew_cfg = phase2.get("crewai", {})
    crew_cfg = crew_cfg if isinstance(crew_cfg, dict) else {}
    model = str(crew_cfg.get("ollama_model", "ollama/llama3.2:latest"))
    base_url = str(crew_cfg.get("ollama_base_url", "http://127.0.0.1:11434"))
    temperature = _coerce_float(crew_cfg.get("temperature"))
    if temperature is None:
        temperature = 0.1

    storage_dir = ROOT / "state" / "crewai"
    storage_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CREWAI_STORAGE_DIR"] = str(storage_dir)
    os.environ["CREWAI_HOME"] = str(storage_dir)
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["CREWAI_TRACING_ENABLED"] = "false"
    os.environ["OTEL_SDK_DISABLED"] = "true"

    try:
        from crewai import LLM  # pylint: disable=import-outside-toplevel
    except Exception as exc:  # noqa: BLE001
        return None, f"CrewAI import failed: {exc}"

    try:
        return LLM(model=model, base_url=base_url, temperature=temperature), None
    except Exception as exc:  # noqa: BLE001
        return None, f"CrewAI LLM init failed: {exc}"


def _fallback_division_report(division: str, brief_payload: dict[str, Any]) -> str:
    if division == "trading":
        bots = _compact_trading_bots(brief_payload)
        lines = ["Division Status: AMBER"]
        lines.append("Top Items:")
        for bot in bots:
            lines.append(
                f"- {bot.get('id')}: status={bot.get('status')} pnl_total={bot.get('pnl_total')} "
                f"trades={bot.get('trades_total')} errors={bot.get('error_lines_total')}"
            )
        lines.append("Owner Approvals Needed:")
        lines.append("- Confirm whether to tune Polymarket risk and data-window logic from 24h to rolling session metrics.")
        return "\n".join(lines)

    sites = _compact_websites(brief_payload)
    lines = ["Division Status: GREEN"]
    lines.append("Top Items:")
    for site in sites:
        lines.append(
            f"- {site.get('id')}: ok={site.get('ok')} status={site.get('status_code')} "
            f"latency_ms={site.get('latency_ms')} probe={site.get('probe_mode')}"
        )
    lines.append("Owner Approvals Needed:")
    lines.append("- Approve website latency threshold changes only if business SLA changes.")
    return "\n".join(lines)


def _run_division_crew(
    config: dict[str, Any],
    brief_payload: dict[str, Any],
    division: str,
    llm: Any | None,
) -> dict[str, Any]:
    scorecard = _build_division_scorecard(division=division, brief_payload=brief_payload, config=config)
    phase2 = _phase2_cfg(config)
    division_cfg = phase2.get("divisions", {})
    division_cfg = division_cfg if isinstance(division_cfg, dict) else {}
    selected = division_cfg.get(division, {})
    selected = selected if isinstance(selected, dict) else {}
    spec_file = str(selected.get("spec_file", "")).strip()
    if not spec_file:
        default = "crews/trading_bots_division.yaml" if division == "trading" else "crews/websites_division.yaml"
        spec_file = default
    spec_path = ROOT / spec_file

    if llm is None:
        fallback = _fallback_division_report(division=division, brief_payload=brief_payload)
        return {
            "division": division,
            "ok": True,
            "engine": "fallback_local_rules",
            "status": scorecard.get("status", "attention").lower(),
            "spec_file": str(spec_path),
            "final_output": fallback,
            "task_outputs": [],
            "scorecard": scorecard,
            "warnings": ["CrewAI unavailable, used local fallback report."],
        }

    spec = _load_yaml(spec_path)
    inputs = _build_inputs(brief_payload=brief_payload, division=division)
    crew_cfg = _phase2_cfg(config).get("crewai", {})
    crew_cfg = crew_cfg if isinstance(crew_cfg, dict) else {}
    agent_max_iter = int(crew_cfg.get("agent_max_iter", 2))

    from crewai import Agent, Crew, Process, Task  # pylint: disable=import-outside-toplevel

    agents_map: dict[str, Agent] = {}
    manager_key = str(spec.get("manager_agent", "")).strip()
    for raw_agent in spec.get("agents", []):
        if not isinstance(raw_agent, dict):
            continue
        key = str(raw_agent.get("key", "")).strip()
        if not key:
            continue
        role = _render_template(str(raw_agent.get("role", key)), inputs)
        goal = _render_template(str(raw_agent.get("goal", "")), inputs)
        backstory = _render_template(str(raw_agent.get("backstory", "")), inputs)
        agent = Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            llm=llm,
            allow_delegation=bool(raw_agent.get("allow_delegation", False)),
            max_iter=agent_max_iter,
            verbose=bool(raw_agent.get("verbose", False)),
        )
        agents_map[key] = agent

    if manager_key not in agents_map:
        raise ValueError(f"Manager agent '{manager_key}' missing in spec: {spec_path}")

    ordered_tasks: list[Task] = []
    tasks_by_key: dict[str, Task] = {}
    for raw_task in spec.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        task_key = str(raw_task.get("key", "")).strip()
        agent_key = str(raw_task.get("agent", "")).strip()
        if not task_key or agent_key not in agents_map:
            continue
        context_refs = raw_task.get("context", [])
        context_refs = context_refs if isinstance(context_refs, list) else []
        context_tasks = [tasks_by_key[item] for item in context_refs if item in tasks_by_key]
        description = _render_template(str(raw_task.get("description", "")), inputs)
        expected_output = _render_template(str(raw_task.get("expected_output", "")), inputs)
        task = Task(
            description=description,
            expected_output=expected_output,
            agent=agents_map[agent_key],
            context=context_tasks,
        )
        ordered_tasks.append(task)
        tasks_by_key[task_key] = task

    worker_agents = [agent for key, agent in agents_map.items() if key != manager_key]
    crew = Crew(
        agents=worker_agents,
        tasks=ordered_tasks,
        process=Process.hierarchical,
        manager_agent=agents_map[manager_key],
        verbose=bool(spec.get("verbose", False)),
    )

    kickoff_result = crew.kickoff()

    task_outputs = []
    blocked_command_detected = False
    for raw_task in spec.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        task_key = str(raw_task.get("key", "")).strip()
        task_obj = tasks_by_key.get(task_key)
        output_text = ""
        if task_obj is not None:
            output_value = getattr(task_obj, "output", None)
            output_text = str(output_value) if output_value is not None else ""
        cleaned_output, blocked = _sanitize_model_output(output_text)
        if blocked:
            blocked_command_detected = True
        task_outputs.append({"task": task_key, "output": cleaned_output})

    final_output, final_blocked = _sanitize_model_output(str(kickoff_result))
    blocked_command_detected = blocked_command_detected or final_blocked
    joined_outputs = "\n".join([final_output] + [str(item.get("output", "")) for item in task_outputs])
    tool_call_markers = [
        "delegate_work_to_coworker",
        "ask_question_to_coworker",
        '"name": "delegate_work_to_coworker"',
        '"name": "ask_question_to_coworker"',
    ]
    fallback_warning = None
    if any(marker in joined_outputs for marker in tool_call_markers):
        final_output = _fallback_division_report(division=division, brief_payload=brief_payload)
        task_outputs = []
        fallback_warning = "CrewAI output was tool-call scaffolding; replaced with local manager summary."
    elif blocked_command_detected:
        final_output = _fallback_division_report(division=division, brief_payload=brief_payload)
        task_outputs = []
        fallback_warning = "CrewAI output contained non-allowlisted command suggestions; replaced with local manager summary."

    return {
        "division": division,
        "ok": True,
        "engine": "crewai_hierarchical",
        "status": scorecard.get("status", "ok").lower(),
        "spec_file": str(spec_path),
        "final_output": final_output,
        "task_outputs": task_outputs,
        "scorecard": scorecard,
        "warnings": [fallback_warning] if fallback_warning else [],
    }


def _build_phase2_markdown(payload: dict[str, Any]) -> str:
    def _score_line(item: dict[str, Any]) -> str:
        return (
            f"- [{item.get('status')}] {item.get('metric')}: "
            f"actual={item.get('actual')} | target={item.get('target')} | variance={item.get('variance')}"
        )

    lines: list[str] = []
    lines.append(f"# {payload['company_name']} - Division Heartbeat (Phase 2)")
    lines.append("")
    lines.append(f"- Generated (UTC): {payload['generated_at_utc']}")
    lines.append(f"- Source brief mode: {payload['source_brief_mode']}")
    lines.append(f"- Divisions executed: {', '.join(payload['divisions_ran'])}")
    lines.append("")
    lines.append("## Summary")
    summary = payload.get("base_summary", {})
    summary = summary if isinstance(summary, dict) else {}
    lines.append(f"- Bot PnL total: {summary.get('pnl_total')}")
    lines.append(f"- Bot trades total: {summary.get('trades_total')}")
    lines.append(f"- Websites up: {summary.get('websites_up')}/{summary.get('websites_total')}")
    lines.append(f"- Alerts in base brief: {len(payload.get('base_alerts', []))}")

    for division in payload.get("divisions", []):
        if not isinstance(division, dict):
            continue
        lines.append("")
        lines.append(f"## {division.get('division').title()} Division")
        lines.append(f"- Engine: {division.get('engine')}")
        lines.append(f"- Status: {division.get('status')}")
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        if scorecard:
            lines.append(f"- Goal: {scorecard.get('goal')}")
            lines.append(f"- Desired Outcome: {scorecard.get('desired_outcome')}")
            lines.append(f"- Scorecard Status: {scorecard.get('status')}")
            lines.append("")
            lines.append("### KPI Scorecard")
            items = scorecard.get("items", [])
            items = items if isinstance(items, list) else []
            if not items:
                lines.append("- None")
            else:
                for item in items:
                    if isinstance(item, dict):
                        lines.append(_score_line(item))
            risks = scorecard.get("risks", [])
            risks = risks if isinstance(risks, list) else []
            lines.append("")
            lines.append("### Key Risks")
            if not risks:
                lines.append("- None")
            else:
                for risk in risks:
                    lines.append(f"- {risk}")
            actions = scorecard.get("actions", [])
            actions = actions if isinstance(actions, list) else []
            lines.append("")
            lines.append("### Corrective Actions")
            if not actions:
                lines.append("- None")
            else:
                for action in actions:
                    lines.append(f"- {action}")
        for warning in division.get("warnings", []):
            lines.append(f"- Warning: {warning}")
        lines.append("")
        lines.append("### AI Division Narrative")
        lines.append("")
        lines.append(str(division.get("final_output", "")).strip())

    lines.append("")
    lines.append("## Owner Command Reminder")
    lines.append("- Run `python scripts/tool_router.py run_divisions --division all --force` for a fresh multi-division report.")
    return "\n".join(lines).strip() + "\n"


def _persist_phase2_report(config: dict[str, Any], payload: dict[str, Any], markdown: str) -> dict[str, str]:
    reports_dir = _reports_dir(config)
    phase2 = _phase2_cfg(config)
    reports_cfg = phase2.get("reports", {})
    reports_cfg = reports_cfg if isinstance(reports_cfg, dict) else {}

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = reports_dir / f"phase2_divisions_{stamp}.md"
    json_path = reports_dir / f"phase2_divisions_{stamp}.json"

    latest_md_rel = str(reports_cfg.get("markdown_latest", "reports/phase2_divisions_latest.md"))
    latest_json_rel = str(reports_cfg.get("json_latest", "reports/phase2_divisions_latest.json"))
    latest_md = ROOT / latest_md_rel
    latest_json = ROOT / latest_json_rel
    latest_md.parent.mkdir(parents=True, exist_ok=True)
    latest_json.parent.mkdir(parents=True, exist_ok=True)

    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return {
        "markdown": str(md_path),
        "json": str(json_path),
        "latest_markdown": str(latest_md),
        "latest_json": str(latest_json),
    }


def run_phase2_divisions(config: dict[str, Any], division: str = "all", force: bool = False) -> dict[str, Any]:
    phase2 = _phase2_cfg(config)
    if phase2.get("enabled", True) is False:
        return {"ok": False, "error": "phase2_disabled", "message": "Phase 2 is disabled in config.projects.yaml"}

    if division not in {"all", "trading", "websites"}:
        return {"ok": False, "error": "invalid_division", "message": "division must be one of: all, trading, websites"}

    brief_payload, source_mode = _ensure_brief_payload(config=config, force=force)
    llm, llm_error = _build_llm(config=config)

    divisions_to_run = ["trading", "websites"] if division == "all" else [division]
    division_payloads: list[dict[str, Any]] = []
    warnings: list[str] = []
    if llm_error:
        warnings.append(llm_error)

    for division_id in divisions_to_run:
        try:
            result = _run_division_crew(
                config=config,
                brief_payload=brief_payload,
                division=division_id,
                llm=llm,
            )
        except Exception as exc:  # noqa: BLE001
            result = {
                "division": division_id,
                "ok": False,
                "engine": "crewai_hierarchical",
                "status": "error",
                "spec_file": "",
                "final_output": "",
                "task_outputs": [],
                "warnings": [f"Crew execution failed: {exc}"],
            }
        division_payloads.append(result)

    payload = {
        "ok": all(bool(item.get("ok")) for item in division_payloads),
        "company_name": str(brief_payload.get("company_name", "AI Holding Company")),
        "generated_at_utc": _now_utc_iso(),
        "source_brief_mode": source_mode,
        "divisions_ran": divisions_to_run,
        "base_summary": brief_payload.get("summary", {}),
        "base_alerts": brief_payload.get("alerts", []),
        "base_bots": brief_payload.get("bots", []),
        "base_websites": brief_payload.get("websites", []),
        "warnings": warnings,
        "divisions": division_payloads,
    }
    markdown = _build_phase2_markdown(payload)
    payload["files"] = _persist_phase2_report(config=config, payload=payload, markdown=markdown)
    if isinstance(brief_payload, dict) and isinstance(brief_payload.get("files"), dict):
        payload["base_brief_files"] = brief_payload.get("files")
    return payload

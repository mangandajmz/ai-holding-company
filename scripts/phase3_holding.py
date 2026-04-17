"""Phase 3 holding-company orchestration (CEO layer + board scorecards)."""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from monitoring import ROOT
from phase2_crews import run_phase2_divisions
from utils import fmt_money as _fmt_money, load_yaml as _load_yaml, now_utc_iso as _now_utc_iso, parse_float as _to_float


def _phase3_cfg(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("phase3", {})
    return value if isinstance(value, dict) else {}


def _reports_dir(config: dict[str, Any]) -> Path:
    from utils import reports_dir  # pylint: disable=import-outside-toplevel
    return reports_dir(config)


def _to_int(value: Any) -> int | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _fmt_pct(value: Any, digits: int = 2) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:.{digits}f}%"


def _fmt_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _status_worst(statuses: list[str]) -> str:
    normalized = [str(status).upper() for status in statuses]
    if "RED" in normalized:
        return "RED"
    if "AMBER" in normalized:
        return "AMBER"
    return "GREEN"


def _status_from_min(actual: float | None, target_min: float, amber_min: float) -> tuple[str, str]:
    if actual is None:
        return "AMBER", "missing"
    if actual >= target_min:
        return "GREEN", f"{actual - target_min:+.2f}"
    if actual >= amber_min:
        return "AMBER", f"{actual - target_min:+.2f}"
    return "RED", f"{actual - target_min:+.2f}"


def _status_from_max(actual: float | None, target_max: float, amber_max: float) -> tuple[str, str]:
    if actual is None:
        return "AMBER", "missing"
    if actual <= target_max:
        return "GREEN", f"{actual - target_max:+.2f}"
    if actual <= amber_max:
        return "AMBER", f"{actual - target_max:+.2f}"
    return "RED", f"{actual - target_max:+.2f}"


def _load_targets(config: dict[str, Any]) -> dict[str, Any]:
    phase3 = _phase3_cfg(config)
    targets_rel = str(phase3.get("targets_file", "config/targets.yaml")).strip()
    targets_path = ROOT / targets_rel if not Path(targets_rel).is_absolute() else Path(targets_rel)
    if targets_path.exists():
        try:
            return _load_yaml(targets_path)
        except Exception as exc:  # noqa: BLE001
            logging.warning("Failed to load targets file %s: %s", targets_path, exc, exc_info=True)
    fallback = config.get("phase2", {}).get("targets", {})
    return fallback if isinstance(fallback, dict) else {}


def _load_soul(config: dict[str, Any]) -> str:
    phase3 = _phase3_cfg(config)
    soul_rel = str(phase3.get("soul_file", "SOUL.md")).strip()
    soul_path = ROOT / soul_rel if not Path(soul_rel).is_absolute() else Path(soul_rel)
    if soul_path.exists():
        try:
            return soul_path.read_text(encoding="utf-8").strip()
        except OSError:
            return ""
    return ""


def _baseline_path(config: dict[str, Any]) -> Path:
    phase3 = _phase3_cfg(config)
    rel = str(phase3.get("baseline_state_file", "state/phase3_company_baseline.json")).strip()
    path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_baseline(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"months": {}}
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"months": {}}
    return loaded if isinstance(loaded, dict) else {"months": {}}


def _persist_baseline(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _compute_monthly_growth(
    config: dict[str, Any],
    generated_at: datetime,
    pnl_total: float | None,
) -> dict[str, Any]:
    baseline_file = _baseline_path(config)
    baseline = _load_baseline(baseline_file)
    months = baseline.get("months", {})
    months = months if isinstance(months, dict) else {}
    month_key = generated_at.strftime("%Y-%m")
    month_rec = months.get(month_key, {})
    month_rec = month_rec if isinstance(month_rec, dict) else {}

    start_pnl = _to_float(month_rec.get("start_pnl"))
    if start_pnl is None and pnl_total is not None:
        start_pnl = pnl_total
        month_rec = {
            "start_pnl": start_pnl,
            "start_at_utc": generated_at.isoformat(),
        }
        months[month_key] = month_rec
        baseline["months"] = months
        _persist_baseline(baseline_file, baseline)

    growth_pct = None
    if start_pnl is not None and pnl_total is not None:
        denominator = abs(start_pnl) if abs(start_pnl) > 1e-9 else None
        if denominator:
            growth_pct = ((pnl_total - start_pnl) / denominator) * 100.0

    return {
        "month_key": month_key,
        "start_pnl": start_pnl,
        "current_pnl": pnl_total,
        "growth_pct": growth_pct,
        "baseline_file": str(baseline_file),
    }


def _collect_drawdown_pct(phase2_payload: dict[str, Any]) -> float | None:
    drawdowns: list[float] = []
    for bot in phase2_payload.get("base_bots", []):
        if not isinstance(bot, dict):
            continue
        report_payload = bot.get("report_payload", {})
        report_payload = report_payload if isinstance(report_payload, dict) else {}
        for key in [
            "max_drawdown_pct_total",
            "max_drawdown_pct_24h",
            "max_drawdown_pct",
            "drawdown_pct",
            "drawdown",
        ]:
            value = _to_float(report_payload.get(key))
            if value is not None:
                drawdowns.append(abs(value))
        for log in bot.get("log_report", {}).get("logs", []):
            if not isinstance(log, dict):
                continue
            value = _to_float(log.get("drawdown_last"))
            if value is not None:
                drawdowns.append(abs(value))
    if not drawdowns:
        return None
    return max(drawdowns)


def _score_company(
    config: dict[str, Any],
    phase2_payload: dict[str, Any],
    targets: dict[str, Any],
) -> dict[str, Any]:
    company_targets = targets.get("company", {})
    company_targets = company_targets if isinstance(company_targets, dict) else {}
    summary = phase2_payload.get("base_summary", {})
    summary = summary if isinstance(summary, dict) else {}
    divisions = phase2_payload.get("divisions", [])
    divisions = divisions if isinstance(divisions, list) else []
    alerts = phase2_payload.get("base_alerts", [])
    alerts = alerts if isinstance(alerts, list) else []
    warnings = phase2_payload.get("warnings", [])
    warnings = warnings if isinstance(warnings, list) else []
    generated = datetime.fromisoformat(
        str(phase2_payload.get("generated_at_utc", _now_utc_iso())).replace("Z", "+00:00")
    )
    if generated.tzinfo is None:
        generated = generated.replace(tzinfo=timezone.utc)
    else:
        generated = generated.astimezone(timezone.utc)

    pnl_total = _to_float(summary.get("pnl_total"))
    monthly_growth_meta = _compute_monthly_growth(config=config, generated_at=generated, pnl_total=pnl_total)
    growth_cfg = company_targets.get("monthly_pnl_growth_pct", {})
    growth_cfg = growth_cfg if isinstance(growth_cfg, dict) else {}
    growth_target = _to_float(growth_cfg.get("target_min")) or 10.0
    growth_amber = _to_float(growth_cfg.get("amber_min")) or 0.0
    growth_actual = _to_float(monthly_growth_meta.get("growth_pct"))
    growth_status, growth_variance = _status_from_min(growth_actual, growth_target, growth_amber)

    drawdown_cfg = company_targets.get("max_drawdown_pct", {})
    drawdown_cfg = drawdown_cfg if isinstance(drawdown_cfg, dict) else {}
    dd_target = _to_float(drawdown_cfg.get("target_max")) or 3.0
    dd_amber = _to_float(drawdown_cfg.get("amber_max")) or 5.0
    drawdown_actual = _collect_drawdown_pct(phase2_payload)
    dd_status, dd_variance = _status_from_max(drawdown_actual, dd_target, dd_amber)

    websites_total = max(_to_int(summary.get("websites_total")) or 0, 0)
    websites_up = max(_to_int(summary.get("websites_up")) or 0, 0)
    uptime_ratio = (websites_up / websites_total) if websites_total else None
    uptime_cfg = company_targets.get("website_uptime_ratio", {})
    uptime_cfg = uptime_cfg if isinstance(uptime_cfg, dict) else {}
    uptime_target = _to_float(uptime_cfg.get("target_min")) or 0.999
    uptime_amber = _to_float(uptime_cfg.get("amber_min")) or 0.99
    uptime_status, uptime_variance = _status_from_min(uptime_ratio, uptime_target, uptime_amber)

    green_divisions = 0
    for division in divisions:
        if not isinstance(division, dict):
            continue
        status = str(division.get("status", "")).upper()
        if status == "GREEN":
            green_divisions += 1
    division_ratio = (green_divisions / len(divisions)) if divisions else None
    div_cfg = company_targets.get("division_green_ratio", {})
    div_cfg = div_cfg if isinstance(div_cfg, dict) else {}
    div_target = _to_float(div_cfg.get("target_min")) or 0.67
    div_amber = _to_float(div_cfg.get("amber_min")) or 0.50
    div_status, div_variance = _status_from_min(division_ratio, div_target, div_amber)

    alert_cfg = company_targets.get("max_alerts_per_heartbeat", {})
    alert_cfg = alert_cfg if isinstance(alert_cfg, dict) else {}
    alert_target = _to_float(alert_cfg.get("target_max")) or 0.0
    alert_amber = _to_float(alert_cfg.get("amber_max")) or 2.0
    alert_actual = float(len(alerts) + len(warnings))
    alert_status, alert_variance = _status_from_max(alert_actual, alert_target, alert_amber)

    items = [
        {
            "metric": "Monthly PnL growth",
            "target": f">= {growth_target:.1f}%",
            "actual": _fmt_pct(growth_actual, 2),
            "variance": growth_variance if growth_actual is not None else "baseline collecting",
            "status": growth_status,
            "action": "Review monthly PnL trajectory and adjust risk/strategy allocation if growth is off target.",
        },
        {
            "metric": "Max drawdown",
            "target": f"<= {dd_target:.1f}%",
            "actual": _fmt_pct(drawdown_actual, 2),
            "variance": dd_variance,
            "status": dd_status,
            "action": "If drawdown exceeds tolerance, reduce exposure and tighten per-trade risk limits.",
        },
        {
            "metric": "Website uptime ratio (snapshot)",
            "target": f">= {uptime_target*100:.2f}%",
            "actual": _fmt_ratio(uptime_ratio),
            "variance": uptime_variance,
            "status": uptime_status,
            "action": "Escalate any downtime before non-critical roadmap work.",
        },
        {
            "metric": "Division GREEN ratio",
            "target": f">= {div_target*100:.0f}%",
            "actual": _fmt_ratio(division_ratio),
            "variance": div_variance,
            "status": div_status,
            "action": "Address weakest division scorecards first to restore portfolio-wide health.",
        },
        {
            "metric": "Alert count per heartbeat",
            "target": f"<= {int(alert_target)}",
            "actual": str(int(alert_actual)),
            "variance": alert_variance,
            "status": alert_status,
            "action": "Reduce recurrent alerts by fixing root causes, not by suppressing checks.",
        },
    ]

    risks: list[str] = []
    actions: list[str] = []
    for item in items:
        if item["status"] == "RED":
            risks.append(f"{item['metric']} is RED ({item['actual']} vs target {item['target']}).")
            actions.append(item["action"])
        elif item["status"] == "AMBER":
            risks.append(f"{item['metric']} is AMBER ({item['actual']} vs target {item['target']}).")
            actions.append(item["action"])

    # Include commercial division health if present in the divisions list.
    for division in divisions:
        if not isinstance(division, dict):
            continue
        if str(division.get("division", "")).lower() == "commercial":
            comm_status = str(division.get("status", "")).upper()
            if comm_status and comm_status != "GREEN":
                items.append({
                    "metric": "commercial_health",
                    "target": "GREEN",
                    "actual": comm_status,
                    "variance": f"Commercial division is {comm_status}",
                    "status": comm_status,
                    "action": "Review commercial risk check and finance report.",
                })

    if not actions:
        actions.append("Company-level KPIs are within target range; continue current operating cadence.")

    status = _status_worst([item["status"] for item in items])
    return {
        "goal": "Maximize resilient, compounding performance across divisions while protecting downside risk.",
        "desired_outcome": (
            "Company-wide growth stays positive, drawdowns remain controlled, website reliability remains high, "
            "and most divisions operate in GREEN status."
        ),
        "status": status,
        "items": items,
        "risks": risks[:6],
        "actions": actions[:6],
        "meta": monthly_growth_meta,
    }


def _build_llm(config: dict[str, Any]) -> tuple[Any | None, str | None]:
    phase3 = _phase3_cfg(config)
    ceo_cfg = phase3.get("ceo", {})
    ceo_cfg = ceo_cfg if isinstance(ceo_cfg, dict) else {}
    phase2_cfg = config.get("phase2", {})
    phase2_cfg = phase2_cfg if isinstance(phase2_cfg, dict) else {}
    crew_cfg = phase2_cfg.get("crewai", {})
    crew_cfg = crew_cfg if isinstance(crew_cfg, dict) else {}

    model = str(ceo_cfg.get("ollama_model", crew_cfg.get("ollama_model", "ollama/llama3.2:latest")))
    base_url = str(ceo_cfg.get("ollama_base_url", crew_cfg.get("ollama_base_url", "http://127.0.0.1:11434")))
    temperature = _to_float(ceo_cfg.get("temperature"))
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


def _fallback_ceo_brief(
    mode: str,
    company_scorecard: dict[str, Any],
    divisions: list[dict[str, Any]],
) -> str:
    lines = ["### CEO Summary"]
    lines.append(f"- Company status: {company_scorecard.get('status')}")
    lines.append(f"- Mode: {mode}")
    lines.append("")
    lines.append("### Priority Risks")
    risks = company_scorecard.get("risks", [])
    risks = risks if isinstance(risks, list) else []
    if not risks:
        company_items = company_scorecard.get("items", [])
        company_items = company_items if isinstance(company_items, list) else []
        for item in company_items:
            if not isinstance(item, dict):
                continue
            item_status = str(item.get("status", "")).upper()
            if item_status == "GREEN":
                continue
            risks.append(f"{item.get('metric')} is {item_status} ({item.get('actual')} vs target {item.get('target')}).")
            if len(risks) >= 5:
                break
    if not risks:
        lines.append("- No material risks currently flagged.")
    else:
        for risk in risks[:5]:
            lines.append(f"- {risk}")
    lines.append("")
    lines.append("### Required Owner Approvals")
    approvals: list[str] = []
    company_items = company_scorecard.get("items", [])
    company_items = company_items if isinstance(company_items, list) else []
    for item in company_items:
        if not isinstance(item, dict):
            continue
        item_status = str(item.get("status", "")).upper()
        if item_status == "GREEN":
            continue
        action = str(item.get("action", "")).strip()
        if action and action not in approvals:
            approvals.append(action)
    for division in divisions:
        if not isinstance(division, dict):
            continue
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        score_items = scorecard.get("items", [])
        score_items = score_items if isinstance(score_items, list) else []
        for item in score_items:
            if not isinstance(item, dict):
                continue
            item_status = str(item.get("status", "")).upper()
            if item_status == "GREEN":
                continue
            action = str(item.get("action", "")).strip()
            if action and action not in approvals:
                approvals.append(action)
    if not approvals:
        lines.append("- No explicit approvals pending; continue monitoring cadence.")
    else:
        for action in approvals[:5]:
            lines.append(f"- {action}")
    lines.append("")
    lines.append("### Corrective Plays")
    lines.append("- 48h: Execute highest-priority AMBER/RED action items and re-run holding heartbeat.")
    lines.append("- 7d: Validate trend improvement and retune targets if needed.")
    return "\n".join(lines)


_ALLOWED_PHASE3_SUBCOMMANDS: dict[str, dict[str, Any]] = {
    "daily_brief": {"required": set(), "allowed_flags": {"--force", "--config"}},
    "run_divisions": {"required": set(), "allowed_flags": {"--division", "--force", "--config"}},
    "run_holding": {"required": {"--mode"}, "allowed_flags": {"--mode", "--force", "--config"}},
    "run_holding_board_pack": {"required": set(), "allowed_flags": {"--force", "--config"}},
    "read_bot_logs": {"required": {"--bot"}, "allowed_flags": {"--bot", "--lines", "--config"}},
    "check_website": {"required": {"--website"}, "allowed_flags": {"--website", "--config"}},
    "run_trading_script": {
        "required": {"--bot", "--command-key"},
        "allowed_flags": {"--bot", "--command-key", "--extra-args", "--timeout-sec", "--config"},
    },
}


def _is_allowlisted_tool_router_command(command: str) -> bool:
    raw = command.strip().strip("`")
    try:
        tokens = shlex.split(raw, posix=False)
    except ValueError:
        tokens = raw.split()
    if len(tokens) < 3:
        return False
    if tokens[0].lower() not in {"python", "python3", "py"}:
        return False

    router_token = tokens[1].strip("\"'").replace("\\", "/").lower()
    while router_token.startswith("./"):
        router_token = router_token[2:]
    if not (router_token == "scripts/tool_router.py" or router_token.endswith("/scripts/tool_router.py")):
        return False

    subcommand = tokens[2].strip("\"'")
    spec = _ALLOWED_PHASE3_SUBCOMMANDS.get(subcommand)
    if spec is None:
        return False

    required = set(spec.get("required", set()))
    allowed_flags = set(spec.get("allowed_flags", set()))
    seen_flags: set[str] = set()
    for token in tokens[3:]:
        if not token.startswith("--"):
            continue
        flag = token.split("=", 1)[0]
        if flag not in allowed_flags:
            return False
        seen_flags.add(flag)
    return required.issubset(seen_flags)


def _sanitize_ceo_output(text: str) -> tuple[str, bool]:
    cleaned = text.strip()
    blocked = False

    def _replace_inline_command(match: re.Match[str]) -> str:
        nonlocal blocked
        candidate = match.group(1).strip()
        if candidate.lower().startswith(("python ", "python3 ", "py ")):
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
        candidate = stripped
        if candidate.startswith("- "):
            candidate = candidate[2:].strip()
        if candidate.startswith("* "):
            candidate = candidate[2:].strip()
        if candidate.lower().startswith(("python ", "python3 ", "py ")):
            if _is_allowlisted_tool_router_command(candidate):
                safe_lines.append(line)
            else:
                blocked = True
            continue
        safe_lines.append(line)

    return "\n".join(safe_lines).strip(), blocked


def _run_ceo_brief(
    config: dict[str, Any],
    llm: Any | None,
    mode: str,
    soul_text: str,
    company_scorecard: dict[str, Any],
    phase2_payload: dict[str, Any],
) -> dict[str, Any]:
    phase3 = _phase3_cfg(config)
    ceo_cfg = phase3.get("ceo", {})
    ceo_cfg = ceo_cfg if isinstance(ceo_cfg, dict) else {}
    spec_rel = str(ceo_cfg.get("spec_file", "crews/holding_ceo.yaml")).strip()
    spec_path = ROOT / spec_rel if not Path(spec_rel).is_absolute() else Path(spec_rel)
    divisions = phase2_payload.get("divisions", [])
    divisions = divisions if isinstance(divisions, list) else []

    if llm is None:
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CrewAI unavailable; using deterministic CEO fallback.",
        }

    try:
        spec = _load_yaml(spec_path)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": f"CEO spec load failed ({exc}); using fallback.",
        }

    try:
        from crewai import Agent, Crew, Process, Task  # pylint: disable=import-outside-toplevel
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": f"CrewAI runtime unavailable ({exc}); using fallback.",
        }

    agents_map: dict[str, Agent] = {}
    for raw_agent in spec.get("agents", []):
        if not isinstance(raw_agent, dict):
            continue
        key = str(raw_agent.get("key", "")).strip()
        if not key:
            continue
        agents_map[key] = Agent(
            role=str(raw_agent.get("role", key)),
            goal=str(raw_agent.get("goal", "")),
            backstory=str(raw_agent.get("backstory", "")),
            llm=llm,
            allow_delegation=bool(raw_agent.get("allow_delegation", False)),
            max_iter=int(ceo_cfg.get("agent_max_iter", 1)),
            verbose=bool(spec.get("verbose", False)),
        )

    task_spec = None
    for raw_task in spec.get("tasks", []):
        if isinstance(raw_task, dict):
            task_spec = raw_task
            break
    if not isinstance(task_spec, dict):
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CEO spec missing task definition; using fallback.",
        }

    agent_key = str(task_spec.get("agent", "")).strip()
    if agent_key not in agents_map:
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CEO task agent missing; using fallback.",
        }

    values = {
        "soul_text": soul_text[:4000],
        "holding_mode": mode,
        "company_scorecard_json": json.dumps(company_scorecard, indent=2),
        "division_scorecards_json": json.dumps(
            [item.get("scorecard", {}) for item in divisions if isinstance(item, dict)],
            indent=2,
        ),
        "divisions_json": json.dumps(divisions, indent=2),
        "base_summary_json": json.dumps(phase2_payload.get("base_summary", {}), indent=2),
    }

    description = str(task_spec.get("description", ""))
    for key, value in values.items():
        description = description.replace("{" + key + "}", value)
    expected_output = str(task_spec.get("expected_output", ""))

    task = Task(
        description=description,
        expected_output=expected_output,
        agent=agents_map[agent_key],
    )

    crew = Crew(
        agents=list(agents_map.values()),
        tasks=[task],
        process=Process.sequential,
        verbose=bool(spec.get("verbose", False)),
    )

    kickoff = str(crew.kickoff()).strip()
    if "delegate_work_to_coworker" in kickoff or "ask_question_to_coworker" in kickoff:
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CEO output was tool scaffolding; replaced with fallback.",
        }
    cleaned_output, blocked = _sanitize_ceo_output(kickoff)
    if "polymath" in cleaned_output.lower():
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CEO output failed safety validation; replaced with deterministic fallback.",
        }
    if not cleaned_output.strip():
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CEO output became empty after command sanitization; replaced with deterministic fallback.",
        }
    return {
        "ok": True,
        "engine": "crewai_ceo",
        "brief_markdown": cleaned_output,
        "warning": "CEO output contained non-allowlisted commands; blocked command lines were removed." if blocked else None,
    }


def _build_board_review(
    company_scorecard: dict[str, Any],
    divisions: list[dict[str, Any]],
    commercial_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Board Pack with 8 required fields per PLAN.md §8.

    Returns dict with 'approvals' list, 'gate_blocked' key, and 'notes'.
    """
    approvals: list[dict[str, Any]] = []
    rank = {"RED": 0, "AMBER": 1, "GREEN": 2}
    today = datetime.now(timezone.utc).date().isoformat()

    def _make_item(
        status: str,
        topic: str,
        action: str,
        owner: str,
        metric: str | None = None,
    ) -> dict[str, Any]:
        deadline = today if status == "RED" else "+7d"
        return {
            "priority": status,
            "topic": topic,
            "rationale": (
                f"KPI '{metric or topic}' is {status} (target not met). "
                f"Immediate review required."
            ),
            "expected_upside": f"Restores '{metric or topic}' to target",
            "effort_cost": "n/a",
            "confidence": "Medium — derived from telemetry; LLM scoring not yet applied",
            "owner": owner,
            "deadline": deadline,
            "dissent": "PENDING — dissent_agent review required",
            "measurement_plan": (
                f"Monitor '{metric or topic}' in next daily brief. "
                "GREEN for 2 consecutive runs."
            ),
        }

    for item in sorted(
        company_scorecard.get("items", []),
        key=lambda x: rank.get(str(x.get("status", "")).upper(), 3),
    ):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).upper()
        if status == "GREEN":
            continue
        metric = str(item.get("metric", "unknown"))
        approvals.append(
            _make_item(
                status=status,
                topic=f"Company KPI: {metric}",
                action=str(item.get("action", "")),
                owner="holding",
                metric=metric,
            )
        )

    for division in divisions:
        if not isinstance(division, dict):
            continue
        div_name = str(division.get("division", "unknown"))
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        for item in sorted(
            scorecard.get("items", []),
            key=lambda x: rank.get(str(x.get("status", "")).upper(), 3),
        ):
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", "")).upper()
            if status == "GREEN":
                continue
            metric = str(item.get("metric", "unknown"))
            approvals.append(
                _make_item(
                    status=status,
                    topic=f"{div_name.title()} KPI: {metric}",
                    action=str(item.get("action", "")),
                    owner=div_name,
                    metric=metric,
                )
            )

    if commercial_result and isinstance(commercial_result, dict):
        comm_status = str(commercial_result.get("status", "GREEN")).upper()
        if comm_status != "GREEN":
            risk = commercial_result.get("risk", {})
            risk = risk if isinstance(risk, dict) else {}
            exposure_flags = risk.get("exposure_flags", [])
            exposure_label = exposure_flags[0] if exposure_flags else "Commercial risk detected"
            risk_verdict = str(risk.get("risk_verdict", comm_status))
            approvals.append({
                "priority": comm_status,
                "topic": f"Commercial: {exposure_label}",
                "rationale": risk_verdict,
                "expected_upside": "Risk reduction and financial health improvement",
                "effort_cost": "n/a",
                "confidence": "Medium — derived from risk check module",
                "owner": "commercial",
                "deadline": today if comm_status == "RED" else "+7d",
                "dissent": "PENDING — dissent_agent review required",
                "measurement_plan": "Re-run commercial risk check. GREEN for 1 run.",
            })

    return {
        "approvals": approvals[:10],
        "gate_blocked": False,
        "notes": "Approve, defer, or reject each item explicitly to keep accountability clear.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _validate_board_pack_item(item: dict[str, Any]) -> list[str]:
    """Return list of missing field names for a Board Pack item.

    Per PLAN.md §8: rationale, expected_upside, effort_cost, confidence, owner,
    deadline, dissent, measurement_plan must all be present and non-empty.
    Empty list means item is valid.
    """
    required = [
        "rationale", "expected_upside", "effort_cost", "confidence",
        "owner", "deadline", "dissent", "measurement_plan",
    ]
    missing = []
    for field in required:
        value_str = str(item.get(field, "")).strip()
        if field in ("effort_cost", "expected_upside") and value_str == "n/a":
            continue
        if field == "dissent" and "unavailable" in value_str.lower():
            continue
        # PENDING placeholder counts as missing (dissent agent must have run).
        if field == "dissent" and value_str.startswith("PENDING"):
            missing.append(field)
            continue
        if not value_str or value_str == "n/a":
            missing.append(field)
    return missing


def _build_phase3_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# {payload.get('company_name')} - CEO Heartbeat (Phase 3)")
    lines.append("")
    lines.append(f"- Generated (UTC): {payload.get('generated_at_utc')}")
    lines.append(f"- Mode: {payload.get('mode')}")
    lines.append(f"- Source brief mode: {payload.get('source_brief_mode')}")
    lines.append("")

    company = payload.get("company_scorecard", {})
    company = company if isinstance(company, dict) else {}
    lines.append("## Company Scorecard")
    lines.append(f"- Goal: {company.get('goal')}")
    lines.append(f"- Desired Outcome: {company.get('desired_outcome')}")
    lines.append(f"- Status: {company.get('status')}")
    for item in company.get("items", []):
        if isinstance(item, dict):
            lines.append(
                f"- [{item.get('status')}] {item.get('metric')}: "
                f"actual={item.get('actual')} | target={item.get('target')} | variance={item.get('variance')}"
            )
    lines.append("")
    lines.append("### Corrective Actions")
    for action in company.get("actions", []):
        lines.append(f"- {action}")

    lines.append("")
    lines.append("## Division Scorecards")
    for division in payload.get("divisions", []):
        if not isinstance(division, dict):
            continue
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        lines.append(f"- {str(division.get('division')).title()}: status={scorecard.get('status')}")
        ranked_items = sorted(
            [item for item in scorecard.get("items", []) if isinstance(item, dict)],
            key=lambda x: {"RED": 0, "AMBER": 1, "GREEN": 2}.get(str(x.get("status", "")).upper(), 3),
        )
        for item in ranked_items[:3]:
            lines.append(
                f"  [{item.get('status')}] {item.get('metric')} -> "
                f"actual={item.get('actual')} target={item.get('target')}"
            )

    lines.append("")
    lines.append("## CEO Office Brief")
    lines.append(
        _fallback_ceo_brief(
            mode=str(payload.get("mode", "heartbeat")),
            company_scorecard=company,
            divisions=payload.get("divisions", []) if isinstance(payload.get("divisions"), list) else [],
        ).strip()
    )

    if payload.get("mode") in ("board_review", "board_pack"):
        board = payload.get("board_review", {})
        board = board if isinstance(board, dict) else {}
        mode_label = "Board Pack" if payload.get("mode") == "board_pack" else "Board Review"
        lines.append("")
        lines.append(f"## {mode_label}")
        if board.get("gate_blocked"):
            lines.append("**MA GATE: Board Pack contains incomplete items — CEO review blocked.**")
        approvals = board.get("approvals", [])
        approvals = approvals if isinstance(approvals, list) else []
        if not approvals:
            lines.append("- No pending approvals.")
        else:
            for item in approvals:
                if not isinstance(item, dict):
                    continue
                lines.append(f"\n### [{item.get('priority')}] {item.get('topic')}")
                lines.append(f"- **Rationale:** {item.get('rationale', 'n/a')}")
                lines.append(f"- **Upside:** {item.get('expected_upside', 'n/a')}")
                lines.append(f"- **Effort/Cost:** {item.get('effort_cost', 'n/a')}")
                lines.append(f"- **Confidence:** {item.get('confidence', 'n/a')}")
                lines.append(f"- **Owner:** {item.get('owner', 'n/a')}")
                lines.append(f"- **Deadline:** {item.get('deadline', 'n/a')}")
                lines.append(f"- **Dissent:** {item.get('dissent', 'n/a')}")
                lines.append(f"- **Measurement:** {item.get('measurement_plan', 'n/a')}")
                if item.get("validation_warnings"):
                    lines.append(f"- **Missing fields:** {', '.join(item['validation_warnings'])}")
        lines.append(f"\nNotes: {board.get('notes')}")

    lines.append("")
    lines.append("## Owner Command Reminder")
    lines.append("- `python scripts/tool_router.py run_holding --mode heartbeat --force`")
    lines.append("- `python scripts/tool_router.py run_holding --mode board_review --force`")
    lines.append("- `python scripts/tool_router.py run_holding_board_pack --force`")
    return "\n".join(lines).strip() + "\n"


def _run_dissent_task(
    config: dict[str, Any],
    llm: Any | None,
    spec: dict[str, Any],
    approvals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Run the dissent_task against board approvals. Returns list of {item, objection} dicts.

    Returns empty list on any failure (graceful — dissent is advisory, not blocking).
    """
    if llm is None or not approvals:
        return []

    try:
        from crewai import Agent, Crew, Process, Task  # pylint: disable=import-outside-toplevel
    except Exception:  # noqa: BLE001
        return []

    try:
        dissent_agent_spec = next(
            (a for a in spec.get("agents", []) if isinstance(a, dict) and a.get("key") == "dissent_agent"),
            None,
        )
        dissent_task_spec = next(
            (t for t in spec.get("tasks", []) if isinstance(t, dict) and t.get("key") == "dissent_task"),
            None,
        )
        if not dissent_agent_spec or not dissent_task_spec:
            return []

        phase3_cfg = config.get("phase3", {}) or {}
        ceo_cfg = phase3_cfg.get("ceo", {}) or {}

        agent = Agent(
            role=str(dissent_agent_spec.get("role", "Dissent Officer")),
            goal=str(dissent_agent_spec.get("goal", "")),
            backstory=str(dissent_agent_spec.get("backstory", "")),
            llm=llm,
            allow_delegation=False,
            max_iter=int(ceo_cfg.get("agent_max_iter", 1)),
            verbose=bool(spec.get("verbose", False)),
        )

        board_pack_json = json.dumps(
            [{"topic": a.get("topic"), "rationale": a.get("rationale")} for a in approvals],
            indent=2,
        )
        description = str(dissent_task_spec.get("description", "")).replace(
            "{board_pack_json}", board_pack_json
        )
        task = Task(
            description=description,
            expected_output=str(dissent_task_spec.get("expected_output", "")),
            agent=agent,
        )
        crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
        raw_output = str(crew.kickoff()).strip()

        # Extract JSON from output (may be wrapped in prose)
        json_match = re.search(r"\[.*\]", raw_output, re.DOTALL)
        if not json_match:
            return []
        return json.loads(json_match.group(0))
    except Exception:  # noqa: BLE001
        return []


def _persist_phase3_reports(config: dict[str, Any], payload: dict[str, Any], markdown: str) -> dict[str, str]:
    reports_dir = _reports_dir(config)
    phase3 = _phase3_cfg(config)
    reports_cfg = phase3.get("reports", {})
    reports_cfg = reports_cfg if isinstance(reports_cfg, dict) else {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_path = reports_dir / f"phase3_holding_{stamp}.md"
    json_path = reports_dir / f"phase3_holding_{stamp}.json"

    latest_md_rel = str(reports_cfg.get("markdown_latest", "reports/phase3_holding_latest.md"))
    latest_json_rel = str(reports_cfg.get("json_latest", "reports/phase3_holding_latest.json"))
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


def run_phase3_holding(config: dict[str, Any], mode: str = "heartbeat", force: bool = False) -> dict[str, Any]:
    phase3 = _phase3_cfg(config)
    if phase3.get("enabled", True) is False:
        return {"ok": False, "error": "phase3_disabled", "message": "Phase 3 is disabled in config/projects.yaml"}
    if mode not in {"heartbeat", "board_review", "board_pack"}:
        return {"ok": False, "error": "invalid_mode", "message": "mode must be heartbeat, board_review, or board_pack"}

    phase2_payload = run_phase2_divisions(config=config, division="all", force=force)
    if not isinstance(phase2_payload, dict) or not phase2_payload.get("ok", False):
        return {
            "ok": False,
            "error": "phase2_dependency_failed",
            "message": "Phase 3 requires successful phase2 division execution.",
            "phase2": phase2_payload,
        }

    targets = _load_targets(config)
    soul_text = _load_soul(config)
    company_scorecard = _score_company(config=config, phase2_payload=phase2_payload, targets=targets)
    llm, llm_warning = _build_llm(config=config)
    ceo_result = _run_ceo_brief(
        config=config,
        llm=llm,
        mode=mode,
        soul_text=soul_text,
        company_scorecard=company_scorecard,
        phase2_payload=phase2_payload,
    )

    divisions = phase2_payload.get("divisions", [])
    divisions = divisions if isinstance(divisions, list) else []
    payload: dict[str, Any] = {
        "ok": True,
        "company_name": str(phase2_payload.get("company_name", config.get("company", {}).get("name", "AI Holding Company"))),
        "generated_at_utc": _now_utc_iso(),
        "mode": mode,
        "source_brief_mode": phase2_payload.get("source_brief_mode"),
        "targets_file": str((_phase3_cfg(config).get("targets_file") or "config/targets.yaml")),
        "soul_file": str((_phase3_cfg(config).get("soul_file") or "SOUL.md")),
        "base_summary": phase2_payload.get("base_summary", {}),
        "base_alerts": phase2_payload.get("base_alerts", []),
        "warnings": [warning for warning in [llm_warning, ceo_result.get("warning")] if warning],
        "company_scorecard": company_scorecard,
        "divisions": divisions,
        "ceo_engine": ceo_result.get("engine"),
        "ceo_brief_markdown": ceo_result.get("brief_markdown", ""),
        "phase2_files": phase2_payload.get("files", {}),
        "phase2_payload_ref": phase2_payload.get("files", {}).get("latest_json"),
    }

    if mode in ("board_review", "board_pack"):
        # Try to include commercial result if the module is available.
        commercial_result: dict[str, Any] | None = None
        try:
            from commercial import run_commercial_division  # pylint: disable=import-outside-toplevel
            commercial_result = run_commercial_division(config=config, force=force)
        except ImportError:
            pass  # commercial module not yet on this branch — graceful skip
        except Exception:  # noqa: BLE001
            pass

        board_review = _build_board_review(
            company_scorecard=company_scorecard,
            divisions=divisions,
            commercial_result=commercial_result,
        )

        if mode == "board_pack":
            # Load the CEO spec to get the dissent task definition.
            ceo_cfg = phase3.get("ceo", {}) or {}
            spec_rel = str(ceo_cfg.get("spec_file", "crews/holding_ceo.yaml")).strip()
            spec_path = ROOT / spec_rel if not Path(spec_rel).is_absolute() else Path(spec_rel)
            try:
                spec = _load_yaml(spec_path)
            except Exception:  # noqa: BLE001
                spec = {}

            dissent_items = _run_dissent_task(
                config=config,
                llm=llm,
                spec=spec,
                approvals=board_review.get("approvals", []),
            )

            # Merge dissent objections back into approvals by topic.
            for approval in board_review["approvals"]:
                for dissent in dissent_items:
                    if isinstance(dissent, dict) and dissent.get("item") == approval.get("topic"):
                        approval["dissent"] = str(dissent.get("objection", approval["dissent"]))
                        break

            # Validate completeness and set gate flag.
            gate_blocked = False
            for approval in board_review["approvals"]:
                missing = _validate_board_pack_item(approval)
                if missing:
                    approval["validation_warnings"] = missing
                    gate_blocked = True
            board_review["gate_blocked"] = gate_blocked

        payload["board_review"] = board_review

    markdown = _build_phase3_markdown(payload)
    payload["files"] = _persist_phase3_reports(config=config, payload=payload, markdown=markdown)
    return payload

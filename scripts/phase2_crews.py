"""Phase 2 multi-division orchestration using CrewAI hierarchical crews."""

from __future__ import annotations

import json
import os
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
            "status": "attention",
            "spec_file": str(spec_path),
            "final_output": fallback,
            "task_outputs": [],
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

    def _sanitize_output(text: str) -> str:
        cleaned = text.strip()
        markers = [
            "Here is the markdown report:",
            "Here is the markdown analysis:",
            "Here is the markdown analysis report:",
        ]
        for marker in markers:
            if marker in cleaned:
                cleaned = cleaned.split(marker, 1)[1].strip()
        return cleaned

    task_outputs = []
    for raw_task in spec.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        task_key = str(raw_task.get("key", "")).strip()
        task_obj = tasks_by_key.get(task_key)
        output_text = ""
        if task_obj is not None:
            output_value = getattr(task_obj, "output", None)
            output_text = str(output_value) if output_value is not None else ""
        task_outputs.append({"task": task_key, "output": _sanitize_output(output_text)})

    final_output = _sanitize_output(str(kickoff_result))
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

    return {
        "division": division,
        "ok": True,
        "engine": "crewai_hierarchical",
        "status": "ok",
        "spec_file": str(spec_path),
        "final_output": final_output,
        "task_outputs": task_outputs,
        "warnings": [fallback_warning] if fallback_warning else [],
    }


def _build_phase2_markdown(payload: dict[str, Any]) -> str:
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
        for warning in division.get("warnings", []):
            lines.append(f"- Warning: {warning}")
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
        "warnings": warnings,
        "divisions": division_payloads,
    }
    markdown = _build_phase2_markdown(payload)
    payload["files"] = _persist_phase2_report(config=config, payload=payload, markdown=markdown)
    if isinstance(brief_payload, dict) and isinstance(brief_payload.get("files"), dict):
        payload["base_brief_files"] = brief_payload.get("files")
    return payload

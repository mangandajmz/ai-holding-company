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
from urllib.parse import urlparse

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


def _clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "n/a", "na"}:
        return None
    return text


def _fmt_pct(value: Any, digits: int = 2) -> str:
    parsed = _to_float(value)
    if parsed is None:
        return "n/a"
    return f"{parsed:.{digits}f}%"


def _fmt_ratio(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100:.1f}%"


def _fmt_optional_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}%"


def _fmt_optional_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    return _fmt_money(value)


def _property_charters(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("property_charters", {})
    return value if isinstance(value, dict) else {}


def _property_metric_feed_path(config: dict[str, Any]) -> Path:
    phase3 = _phase3_cfg(config)
    rel = str(phase3.get("property_metric_feed_file", "state/property_metric_feed.json")).strip()
    path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _property_metric_memory_path(config: dict[str, Any]) -> Path:
    phase3 = _phase3_cfg(config)
    rel = str(phase3.get("property_metric_memory_file", "state/property_metric_memory.json")).strip()
    path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_json_mapping(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _persist_json_mapping(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _merge_non_null(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if value is None:
            continue
        prior = merged.get(key)
        if isinstance(prior, dict) and isinstance(value, dict):
            merged[key] = _merge_non_null(prior, value)
        else:
            merged[key] = value
    return merged


def _extract_tracking_payload(entry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        return {}
    if "tracking" in entry and isinstance(entry.get("tracking"), dict):
        tracking = entry.get("tracking", {})
        return tracking
    # Allow direct payload shape in feed/memory files.
    return entry


def _has_meaningful_metric(payload: Any) -> bool:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).strip().lower() in {
                "updated_at_utc",
                "generated_at_utc",
                "last_updated_utc",
                "drafts_pending",
            }:
                continue
            if _has_meaningful_metric(value):
                return True
        return False
    if isinstance(payload, list):
        return any(_has_meaningful_metric(item) for item in payload)
    if payload is None:
        return False
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return False
        return text.lower() not in {"none", "null", "n/a", "na"}
    return True


def _parse_utc_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _age_days_from_iso(value: Any, generated_at: datetime) -> float | None:
    parsed = _parse_utc_datetime(value)
    if parsed is None:
        return None
    age_seconds = (generated_at - parsed).total_seconds()
    if age_seconds < 0:
        return 0.0
    return age_seconds / 86400.0


def _property_metrics_sources_dir(config: dict[str, Any]) -> Path:
    phase3 = _phase3_cfg(config)
    rel = str(phase3.get("property_metric_sources_dir", "state/property_metrics")).strip()
    return ROOT / rel if not Path(rel).is_absolute() else Path(rel)


def _load_property_metric_sources(
    config: dict[str, Any],
    property_id: str,
    raw_entry: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    merged: dict[str, Any] = {}
    used_files: list[str] = []
    sources: list[Path] = []

    base_dir = _property_metrics_sources_dir(config) / property_id
    for filename in ["shared.json", "finance.json", "marketing.json", "product.json", "operations.json"]:
        sources.append(base_dir / filename)

    explicit = raw_entry.get("metric_sources", [])
    explicit = explicit if isinstance(explicit, list) else []
    for value in explicit:
        text = str(value).strip()
        if not text:
            continue
        source_path = ROOT / text if not Path(text).is_absolute() else Path(text)
        sources.append(source_path)

    for path in sources:
        if not path.exists():
            continue
        payload = _load_json_mapping(path)
        extracted: dict[str, Any] = {}
        properties = payload.get("properties", {})
        properties = properties if isinstance(properties, dict) else {}
        if property_id in properties and isinstance(properties.get(property_id), dict):
            extracted = _extract_tracking_payload(properties[property_id])
        elif property_id in payload and isinstance(payload.get(property_id), dict):
            extracted = _extract_tracking_payload(payload[property_id])
        else:
            extracted = _extract_tracking_payload(payload)

        if extracted:
            merged = _merge_non_null(merged, extracted)
            used_files.append(str(path))

    return merged, used_files


def _r12_counter_path(config: dict[str, Any]) -> Path:
    phase3 = _phase3_cfg(config)
    rel = str(phase3.get("r12_counter_state_file", "state/r12_property_counters.json")).strip()
    path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_r12_counters(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _persist_r12_counters(path: Path, counters: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counters, indent=2), encoding="utf-8")


def _week_key(generated_at: datetime) -> str:
    iso = generated_at.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _resolve_property_website_id(property_id: str, charter_entry: dict[str, Any]) -> str | None:
    tracking = charter_entry.get("tracking", {})
    tracking = tracking if isinstance(tracking, dict) else {}
    website_id = str(tracking.get("website_id", "")).strip()
    if website_id:
        return website_id
    defaults = {
        "freetraderhub": "freetraderhub_website",
        "freeghosttools": "freeghosttools",
    }
    return defaults.get(property_id)


def _resolve_property_research_id(property_id: str, charter_entry: dict[str, Any]) -> str | None:
    tracking = charter_entry.get("tracking", {})
    tracking = tracking if isinstance(tracking, dict) else {}
    research_id = str(tracking.get("research_website_id", "")).strip()
    if research_id:
        return research_id
    defaults = {
        "freetraderhub": "freetraderhub_research",
    }
    return defaults.get(property_id)


def _latest_content_drafts_pending(phase2_payload: dict[str, Any]) -> int | None:
    for division in phase2_payload.get("divisions", []):
        if not isinstance(division, dict):
            continue
        if str(division.get("division", "")).strip().lower() != "content_studio":
            continue
        return _to_int(division.get("drafts_pending"))
    return None


def _website_snapshot_by_id(phase2_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for website in phase2_payload.get("base_websites", []):
        if not isinstance(website, dict):
            continue
        website_id = str(website.get("id", "")).strip()
        if website_id:
            output[website_id] = website
    return output


def _build_property_metric_feed_from_phase2(
    config: dict[str, Any],
    phase2_payload: dict[str, Any],
    generated_at: datetime,
) -> dict[str, Any]:
    charters = _property_charters(config)
    website_snapshots = _website_snapshot_by_id(phase2_payload)
    drafts_pending = _latest_content_drafts_pending(phase2_payload)
    output: dict[str, Any] = {}

    for property_id, raw_entry in charters.items():
        if not isinstance(raw_entry, dict):
            continue
        if raw_entry.get("active", True) is False:
            continue
        charter = raw_entry.get("charter", {})
        charter = charter if isinstance(charter, dict) else {}
        charter_version = str(charter.get("version", "")).strip().lower()
        if charter_version.startswith("v0-stub"):
            continue

        tracking: dict[str, Any] = {}
        pipeline: dict[str, Any] = {}
        ops: dict[str, Any] = {}
        movers: dict[str, Any] = {}

        if drafts_pending is not None:
            pipeline["drafts_pending"] = drafts_pending

        website_id = _resolve_property_website_id(property_id, raw_entry)
        website_snapshot = website_snapshots.get(website_id or "")
        website_snapshot = website_snapshot if isinstance(website_snapshot, dict) else {}
        local_diag = website_snapshot.get("local_diag", {})
        local_diag = local_diag if isinstance(local_diag, dict) else {}
        sitemap_lastmod = _clean_optional_text(local_diag.get("sitemap_latest_lastmod"))
        sitemap_age_days = _age_days_from_iso(sitemap_lastmod, generated_at) if sitemap_lastmod else None
        if sitemap_age_days is not None:
            pipeline["sitemap_lastmod_age_days"] = round(sitemap_age_days, 2)
            if sitemap_age_days > 14.0:
                movers["biggest_risk"] = "sitemap freshness stale"

        research_id = _resolve_property_research_id(property_id, raw_entry)
        research_snapshot = website_snapshots.get(research_id or "")
        research_snapshot = research_snapshot if isinstance(research_snapshot, dict) else {}
        research_local_diag = research_snapshot.get("local_diag", {})
        research_local_diag = research_local_diag if isinstance(research_local_diag, dict) else {}
        research_mtime = _clean_optional_text(research_local_diag.get("local_reports_latest_mtime_utc"))
        research_age_days = _age_days_from_iso(research_mtime, generated_at) if research_mtime else None
        if research_age_days is not None:
            ops["research_brief_age_days"] = round(research_age_days, 2)
            if research_age_days > 8.0 and "biggest_risk" not in movers:
                movers["biggest_risk"] = "research brief stale"

        if pipeline:
            tracking["pipeline"] = pipeline
        if ops:
            tracking["ops"] = ops
        if movers:
            tracking["movers"] = movers
        if not tracking:
            continue

        output[property_id] = {
            "updated_at_utc": _now_utc_iso(),
            "source": "phase2_system_telemetry",
            "tracking": tracking,
        }

    return output


def _refresh_property_metric_feed_from_phase2(
    config: dict[str, Any],
    phase2_payload: dict[str, Any],
    generated_at: datetime,
) -> str:
    feed_path = _property_metric_feed_path(config)
    existing = _load_json_mapping(feed_path)
    existing_properties = existing.get("properties", existing)
    existing_properties = existing_properties if isinstance(existing_properties, dict) else {}
    merged_properties: dict[str, Any] = dict(existing_properties)

    produced = _build_property_metric_feed_from_phase2(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=generated_at,
    )
    for property_id, produced_entry in produced.items():
        if not isinstance(produced_entry, dict):
            continue
        prior_entry = merged_properties.get(property_id, {})
        prior_entry = prior_entry if isinstance(prior_entry, dict) else {}
        prior_tracking = _extract_tracking_payload(prior_entry)
        produced_tracking = _extract_tracking_payload(produced_entry)
        merged_tracking = _merge_non_null(prior_tracking, produced_tracking)
        merged_entry = dict(prior_entry)
        merged_entry["tracking"] = merged_tracking
        merged_entry["updated_at_utc"] = _now_utc_iso()
        merged_entry["source"] = "phase2_system_telemetry"
        merged_properties[property_id] = merged_entry

    payload = {
        "generated_at_utc": generated_at.isoformat(),
        "producer": "phase3_holding",
        "properties": merged_properties,
    }
    _persist_json_mapping(feed_path, payload)
    return str(feed_path)


def _update_r12_counter(
    config: dict[str, Any],
    property_id: str,
    value_delta: float | None,
    generated_at: datetime,
) -> dict[str, Any]:
    counter_path = _r12_counter_path(config)
    counters = _load_r12_counters(counter_path)
    record = counters.get(property_id, {})
    record = record if isinstance(record, dict) else {}

    counter = max(_to_int(record.get("consecutive_negative_weeks")) or 0, 0)
    current_week = _week_key(generated_at)
    last_week = str(record.get("last_week_key", ""))

    if value_delta is not None and current_week != last_week:
        counter = counter + 1 if value_delta < 0 else 0
        record["consecutive_negative_weeks"] = counter
        record["last_week_key"] = current_week
        record["last_value_delta_usd"] = value_delta
        record["updated_at_utc"] = _now_utc_iso()
        counters[property_id] = record
        _persist_r12_counters(counter_path, counters)

    return {
        "counter": counter,
        "threshold": 4,
        "halt_active": counter >= 4,
        "state_file": str(counter_path),
    }


def _build_property_pnl_blocks(
    config: dict[str, Any],
    phase2_payload: dict[str, Any],
    generated_at: datetime,
) -> list[dict[str, Any]]:
    charters = _property_charters(config)
    if not charters:
        return []

    websites_cfg = (
        config.get("phase2", {}).get("targets", {}).get("websites", {})
        if isinstance(config.get("phase2", {}), dict)
        else {}
    )
    websites_cfg = websites_cfg if isinstance(websites_cfg, dict) else {}
    latency_target = _to_float(websites_cfg.get("max_latency_ms")) or 500.0

    feed_path = _property_metric_feed_path(config)
    feed_payload = _load_json_mapping(feed_path)
    feed_properties = feed_payload.get("properties", feed_payload)
    feed_properties = feed_properties if isinstance(feed_properties, dict) else {}

    memory_path = _property_metric_memory_path(config)
    memory_payload = _load_json_mapping(memory_path)
    memory_properties = memory_payload.get("properties", memory_payload)
    memory_properties = memory_properties if isinstance(memory_properties, dict) else {}
    updated_memory_properties: dict[str, Any] = dict(memory_properties)

    website_snapshots = _website_snapshot_by_id(phase2_payload)
    content_drafts = _latest_content_drafts_pending(phase2_payload)
    output: list[dict[str, Any]] = []

    for property_id, raw_entry in charters.items():
        if not isinstance(raw_entry, dict):
            continue
        if raw_entry.get("active", True) is False:
            continue
        charter = raw_entry.get("charter", {})
        charter = charter if isinstance(charter, dict) else {}

        wedge = str(charter.get("wedge", "")).strip()
        property_type = str(charter.get("property_type", "")).strip() or "unknown"
        phase = str(charter.get("phase", "")).strip() or "unknown"
        formula = str(charter.get("r12_formula_version", "")).strip() or "n/a"
        internal_rate = _to_float(charter.get("internal_rate_usd_hr"))
        charter_version = str(charter.get("version", "")).strip() or "n/a"
        if charter_version.lower().startswith("v0-stub"):
            continue

        feed_entry = feed_properties.get(property_id, {})
        feed_entry = feed_entry if isinstance(feed_entry, dict) else {}
        memory_entry = memory_properties.get(property_id, {})
        memory_entry = memory_entry if isinstance(memory_entry, dict) else {}
        source_tracking, source_files_used = _load_property_metric_sources(
            config=config,
            property_id=property_id,
            raw_entry=raw_entry,
        )

        tracking = _extract_tracking_payload(raw_entry)
        tracking = _merge_non_null(tracking, _extract_tracking_payload(memory_entry))
        tracking = _merge_non_null(tracking, source_tracking)
        tracking = _merge_non_null(tracking, _extract_tracking_payload(feed_entry))

        audience = tracking.get("audience", {})
        audience = audience if isinstance(audience, dict) else {}
        revenue = tracking.get("revenue", {})
        revenue = revenue if isinstance(revenue, dict) else {}
        pipeline = tracking.get("pipeline", {})
        pipeline = pipeline if isinstance(pipeline, dict) else {}
        movers = tracking.get("movers", {})
        movers = movers if isinstance(movers, dict) else {}
        targets = tracking.get("targets", {})
        targets = targets if isinstance(targets, dict) else {}
        ops = tracking.get("ops", {})
        ops = ops if isinstance(ops, dict) else {}

        sessions_7d = _to_int(audience.get("sessions_7d"))
        waft_7d = _to_int(audience.get("waft_7d"))
        returning_rate_pct = _to_float(audience.get("returning_user_rate_pct"))
        tool_completion_rate_pct = _to_float(audience.get("tool_completion_rate_pct"))

        affiliate_usd_7d = _to_float(revenue.get("affiliate_usd_7d"))
        ad_usd_7d = _to_float(revenue.get("ad_usd_7d"))
        subscription_mrr_usd = _to_float(revenue.get("subscription_mrr_usd"))
        total_mrr_usd = _to_float(revenue.get("total_mrr_usd"))
        gross_margin_pct = _to_float(revenue.get("gross_margin_pct"))
        top_partner = _clean_optional_text(revenue.get("top_partner"))

        drafts_pending = _to_int(pipeline.get("drafts_pending"))
        if drafts_pending is None and property_id == "freetraderhub":
            drafts_pending = content_drafts
        pages_indexed_7d = _to_int(pipeline.get("pages_indexed_7d"))
        backlinks_dr30_7d = _to_int(pipeline.get("backlinks_dr30_7d"))
        backlinks_dr30_total = _to_int(pipeline.get("backlinks_dr30_total"))
        sitemap_lastmod_age_days = _to_float(pipeline.get("sitemap_lastmod_age_days"))
        active_campaign = _clean_optional_text(pipeline.get("active_campaign"))
        top_revenue_line = _clean_optional_text(movers.get("top_revenue_line"))
        top_growth_lever = _clean_optional_text(movers.get("top_growth_lever"))
        biggest_risk = _clean_optional_text(movers.get("biggest_risk"))

        website_id = _resolve_property_website_id(property_id, raw_entry)
        website_snapshot = website_snapshots.get(website_id or "", {})
        website_latency_ms = _to_float(website_snapshot.get("latency_ms")) if isinstance(website_snapshot, dict) else None

        hours_invested_7d = _to_float(ops.get("hours_invested_7d"))
        direct_costs_usd_7d = _to_float(ops.get("direct_costs_usd_7d"))
        quantified_value_usd_7d = _to_float(ops.get("quantified_value_usd_7d"))
        research_brief_age_days = _to_float(ops.get("research_brief_age_days"))
        value_delta_usd = None
        if (
            hours_invested_7d is not None
            and direct_costs_usd_7d is not None
            and quantified_value_usd_7d is not None
            and internal_rate is not None
        ):
            value_delta_usd = quantified_value_usd_7d - (hours_invested_7d * internal_rate) - direct_costs_usd_7d

        r12 = _update_r12_counter(
            config=config,
            property_id=property_id,
            value_delta=value_delta_usd,
            generated_at=generated_at,
        )

        feed_present = _has_meaningful_metric(_extract_tracking_payload(feed_entry))
        memory_present = _has_meaningful_metric(_extract_tracking_payload(memory_entry))
        source_present = _has_meaningful_metric(source_tracking)

        status = "GREEN"
        reasons: list[str] = []
        if r12.get("halt_active"):
            status = "RED"
            reasons.append("R12 halt active")
        elif value_delta_usd is not None and value_delta_usd < 0:
            status = "AMBER"
            reasons.append("net-negative weekly value delta")
        elif all(
            metric is None
            for metric in [affiliate_usd_7d, ad_usd_7d, subscription_mrr_usd, total_mrr_usd]
        ):
            status = "AMBER"
            if (
                not feed_present
                and not memory_present
                and not source_present
            ):
                reasons.append("revenue feed missing (state/property_metric_feed.json or state/property_metrics/*)")
            else:
                reasons.append("revenue feed missing")

        if website_latency_ms is not None and website_latency_ms > latency_target and status == "GREEN":
            status = "AMBER"
            reasons.append("website latency above target")
        if research_brief_age_days is not None and research_brief_age_days > 8.0 and status == "GREEN":
            status = "AMBER"
            reasons.append("research brief stale")

        forecast_target_mrr_usd = _to_float(targets.get("day90_mrr_usd"))
        pct_to_forecast = None
        if total_mrr_usd is not None and forecast_target_mrr_usd not in (None, 0):
            pct_to_forecast = (total_mrr_usd / forecast_target_mrr_usd) * 100.0

        tracking_snapshot = {
            "audience": {
                "sessions_7d": sessions_7d,
                "waft_7d": waft_7d,
                "returning_user_rate_pct": returning_rate_pct,
                "tool_completion_rate_pct": tool_completion_rate_pct,
            },
            "revenue": {
                "affiliate_usd_7d": affiliate_usd_7d,
                "ad_usd_7d": ad_usd_7d,
                "subscription_mrr_usd": subscription_mrr_usd,
                "total_mrr_usd": total_mrr_usd,
                "gross_margin_pct": gross_margin_pct,
                "top_partner": top_partner,
            },
            "pipeline": {
                "pages_indexed_7d": pages_indexed_7d,
                "backlinks_dr30_7d": backlinks_dr30_7d,
                "backlinks_dr30_total": backlinks_dr30_total,
                "sitemap_lastmod_age_days": sitemap_lastmod_age_days,
                "active_campaign": active_campaign,
            },
            "movers": {
                "top_revenue_line": top_revenue_line,
                "top_growth_lever": top_growth_lever,
                "biggest_risk": biggest_risk,
            },
            "targets": {
                "day90_mrr_usd": forecast_target_mrr_usd,
            },
            "ops": {
                "hours_invested_7d": hours_invested_7d,
                "direct_costs_usd_7d": direct_costs_usd_7d,
                "quantified_value_usd_7d": quantified_value_usd_7d,
                "research_brief_age_days": research_brief_age_days,
            },
        }
        existing_memory_tracking = _extract_tracking_payload(memory_entry)
        merged_memory_tracking = _merge_non_null(existing_memory_tracking, tracking_snapshot)
        updated_memory_entry = dict(memory_entry)
        updated_memory_entry["tracking"] = merged_memory_tracking
        updated_memory_entry["updated_at_utc"] = _now_utc_iso()
        updated_memory_properties[property_id] = updated_memory_entry

        block = {
            "property_id": property_id,
            "property_name": str(raw_entry.get("name", property_id)).strip() or property_id,
            "product_wordmark": str(raw_entry.get("product_wordmark", "")).strip() or None,
            "phase": phase,
            "property_type": property_type,
            "charter_version": charter_version,
            "wedge": wedge,
            "formula": formula,
            "audience": {
                "sessions_7d": sessions_7d,
                "waft_7d": waft_7d,
                "returning_user_rate_pct": returning_rate_pct,
                "tool_completion_rate_pct": tool_completion_rate_pct,
            },
            "revenue": {
                "affiliate_usd_7d": affiliate_usd_7d,
                "ad_usd_7d": ad_usd_7d,
                "subscription_mrr_usd": subscription_mrr_usd,
                "total_mrr_usd": total_mrr_usd,
                "gross_margin_pct": gross_margin_pct,
                "top_partner": top_partner,
            },
            "pipeline": {
                "drafts_pending": drafts_pending,
                "pages_indexed_7d": pages_indexed_7d,
                "backlinks_dr30_7d": backlinks_dr30_7d,
                "backlinks_dr30_total": backlinks_dr30_total,
                "sitemap_lastmod_age_days": sitemap_lastmod_age_days,
                "active_campaign": active_campaign,
            },
            "top_movers": {
                "top_revenue_line": top_revenue_line,
                "top_growth_lever": top_growth_lever,
                "biggest_risk": biggest_risk,
            },
            "operations": {
                "hours_invested_7d": hours_invested_7d,
                "direct_costs_usd_7d": direct_costs_usd_7d,
                "quantified_value_usd_7d": quantified_value_usd_7d,
                "research_brief_age_days": research_brief_age_days,
                "value_delta_usd": value_delta_usd,
            },
            "website_observability": {
                "website_id": website_id,
                "latency_ms": website_latency_ms,
                "latency_target_ms": latency_target,
            },
            "status": {
                "value": status,
                "reason": "; ".join(reasons) if reasons else "on plan",
                "pct_to_forecast_mrr": pct_to_forecast,
                "forecast_target_mrr_usd": forecast_target_mrr_usd,
            },
            "r12": r12,
            "ingestion": {
                "feed_file": str(feed_path),
                "memory_file": str(memory_path),
                "feed_present": feed_present,
                "memory_present": _has_meaningful_metric(existing_memory_tracking),
                "source_files_used": source_files_used,
                "source_present": source_present,
                "feed_updated_at_utc": str(feed_entry.get("updated_at_utc", "")) or None,
                "memory_updated_at_utc": str(memory_entry.get("updated_at_utc", "")) or None,
            },
        }
        output.append(block)

    _persist_json_mapping(memory_path, {"properties": updated_memory_properties})
    return output


def _render_property_pnl_blocks_markdown(blocks: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = ["## Property P&L Blocks"]
    if not blocks:
        lines.append("- No active property charter blocks available.")
        return lines

    for block in blocks:
        name = str(block.get("property_name", "n/a"))
        wordmark = str(block.get("product_wordmark", "")).strip()
        phase = str(block.get("phase", "n/a"))
        formula = str(block.get("formula", "n/a"))
        heading = f"### {name}" + (f" ({wordmark})" if wordmark else "")
        lines.append(heading)
        lines.append(f"- Phase: {phase} | Formula: {formula}")

        audience = block.get("audience", {})
        audience = audience if isinstance(audience, dict) else {}
        lines.append(
            "- Audience: sessions_7d={sessions} | waft_7d={waft} | returning_rate={returning} | tool_completion={completion}".format(
                sessions=audience.get("sessions_7d", "n/a"),
                waft=audience.get("waft_7d", "n/a"),
                returning=_fmt_optional_pct(_to_float(audience.get("returning_user_rate_pct"))),
                completion=_fmt_optional_pct(_to_float(audience.get("tool_completion_rate_pct"))),
            )
        )

        revenue = block.get("revenue", {})
        revenue = revenue if isinstance(revenue, dict) else {}
        lines.append(
            "- Revenue: affiliate_7d={affiliate} | ad_7d={ad} | sub_mrr={sub} | total_mrr={total} | gross_margin={margin} | top_partner={partner}".format(
                affiliate=_fmt_optional_money(_to_float(revenue.get("affiliate_usd_7d"))),
                ad=_fmt_optional_money(_to_float(revenue.get("ad_usd_7d"))),
                sub=_fmt_optional_money(_to_float(revenue.get("subscription_mrr_usd"))),
                total=_fmt_optional_money(_to_float(revenue.get("total_mrr_usd"))),
                margin=_fmt_optional_pct(_to_float(revenue.get("gross_margin_pct"))),
                partner=(revenue.get("top_partner") or "n/a"),
            )
        )

        pipeline = block.get("pipeline", {})
        pipeline = pipeline if isinstance(pipeline, dict) else {}
        lines.append(
            "- Pipeline: drafts_pending={drafts} | pages_indexed_7d={indexed} | backlinks_dr30_7d={bl7} | backlinks_dr30_total={blt} | sitemap_age_days={sitemap_age} | campaign={campaign}".format(
                drafts=pipeline.get("drafts_pending", "n/a"),
                indexed=pipeline.get("pages_indexed_7d", "n/a"),
                bl7=pipeline.get("backlinks_dr30_7d", "n/a"),
                blt=pipeline.get("backlinks_dr30_total", "n/a"),
                sitemap_age=pipeline.get("sitemap_lastmod_age_days", "n/a"),
                campaign=(pipeline.get("active_campaign") or "n/a"),
            )
        )

        movers = block.get("top_movers", {})
        movers = movers if isinstance(movers, dict) else {}
        lines.append(
            "- Top Movers: revenue_line={rev} | growth_lever={grow} | risk={risk}".format(
                rev=(movers.get("top_revenue_line") or "n/a"),
                grow=(movers.get("top_growth_lever") or "n/a"),
                risk=(movers.get("biggest_risk") or "n/a"),
            )
        )

        operations = block.get("operations", {})
        operations = operations if isinstance(operations, dict) else {}
        lines.append(f"- Value Delta (7d): {_fmt_optional_money(_to_float(operations.get('value_delta_usd')))}")

        status = block.get("status", {})
        status = status if isinstance(status, dict) else {}
        pct_to_forecast = _to_float(status.get("pct_to_forecast_mrr"))
        lines.append(
            "- Status: {status} ({reason}) | vs_forecast={forecast}".format(
                status=status.get("value", "n/a"),
                reason=status.get("reason", "n/a"),
                forecast=f"{pct_to_forecast:.1f}%" if pct_to_forecast is not None else "n/a",
            )
        )

        r12 = block.get("r12", {})
        r12 = r12 if isinstance(r12, dict) else {}
        lines.append(f"- R12 Counter: {r12.get('counter', 0)}/{r12.get('threshold', 4)}")

    return lines


def _status_to_score(status: str) -> int:
    normalized = str(status).upper()
    if normalized == "GREEN":
        return 100
    if normalized == "AMBER":
        return 60
    return 20


def _property_kpi_history_path(config: dict[str, Any]) -> Path:
    phase3 = _phase3_cfg(config)
    rel = str(phase3.get("property_kpi_history_file", "state/property_kpi_history.jsonl")).strip()
    path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _property_brief_targets(config: dict[str, Any]) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "finance": {
            "forecast_green_pct": 100.0,
            "forecast_amber_pct": 70.0,
            "gross_margin_green_pct": 60.0,
            "gross_margin_amber_pct": 40.0,
        },
        "marketing": {
            "sessions_green_7d": 1000.0,
            "sessions_amber_7d": 300.0,
            "waft_green_7d": 200.0,
            "waft_amber_7d": 75.0,
            "returning_green_pct": 20.0,
            "returning_amber_pct": 10.0,
        },
        "product": {
            "completion_green_pct": 60.0,
            "completion_amber_pct": 40.0,
            "latency_green_factor": 1.0,
            "latency_amber_factor": 1.5,
        },
        "operations": {
            "drafts_green_max": 6.0,
            "drafts_amber_max": 15.0,
            "pages_indexed_green_7d": 5.0,
            "pages_indexed_amber_7d": 1.0,
        },
    }
    phase3 = _phase3_cfg(config)
    overrides = phase3.get("property_brief_targets", {})
    overrides = overrides if isinstance(overrides, dict) else {}
    merged: dict[str, Any] = {}
    for dept_key, base in defaults.items():
        base_dict = base if isinstance(base, dict) else {}
        override_value = overrides.get(dept_key, {})
        override_dict = override_value if isinstance(override_value, dict) else {}
        merged[dept_key] = {**base_dict, **override_dict}
    return merged


def _build_property_department_briefs(
    config: dict[str, Any],
    property_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets = _property_brief_targets(config)
    output: list[dict[str, Any]] = []

    for block in property_blocks:
        if not isinstance(block, dict):
            continue

        audience = block.get("audience", {})
        audience = audience if isinstance(audience, dict) else {}
        revenue = block.get("revenue", {})
        revenue = revenue if isinstance(revenue, dict) else {}
        pipeline = block.get("pipeline", {})
        pipeline = pipeline if isinstance(pipeline, dict) else {}
        operations = block.get("operations", {})
        operations = operations if isinstance(operations, dict) else {}
        status = block.get("status", {})
        status = status if isinstance(status, dict) else {}
        observability = block.get("website_observability", {})
        observability = observability if isinstance(observability, dict) else {}
        r12 = block.get("r12", {})
        r12 = r12 if isinstance(r12, dict) else {}
        ingestion = block.get("ingestion", {})
        ingestion = ingestion if isinstance(ingestion, dict) else {}
        feed_present = bool(ingestion.get("feed_present"))
        memory_present = bool(ingestion.get("memory_present"))
        source_present = bool(ingestion.get("source_present"))

        value_delta = _to_float(operations.get("value_delta_usd"))
        total_mrr = _to_float(revenue.get("total_mrr_usd"))
        gross_margin = _to_float(revenue.get("gross_margin_pct"))
        forecast_pct = _to_float(status.get("pct_to_forecast_mrr"))
        sessions_7d = _to_float(audience.get("sessions_7d"))
        waft_7d = _to_float(audience.get("waft_7d"))
        returning_rate = _to_float(audience.get("returning_user_rate_pct"))
        completion_rate = _to_float(audience.get("tool_completion_rate_pct"))
        backlinks_7d = _to_float(pipeline.get("backlinks_dr30_7d"))
        drafts_pending = _to_float(pipeline.get("drafts_pending"))
        pages_indexed = _to_float(pipeline.get("pages_indexed_7d"))
        sitemap_age_days = _to_float(pipeline.get("sitemap_lastmod_age_days"))
        latency_ms = _to_float(observability.get("latency_ms"))
        latency_target = _to_float(observability.get("latency_target_ms"))
        research_brief_age_days = _to_float(operations.get("research_brief_age_days"))
        r12_counter = _to_int(r12.get("counter")) or 0
        r12_halt = bool(r12.get("halt_active"))

        finance_cfg = targets.get("finance", {})
        finance_cfg = finance_cfg if isinstance(finance_cfg, dict) else {}
        finance_status = "GREEN"
        finance_signals: list[str] = []
        if r12_halt:
            finance_status = _status_worst([finance_status, "RED"])
            finance_signals.append("R12 halt active")
        if value_delta is None:
            finance_status = _status_worst([finance_status, "AMBER"])
            finance_signals.append("value delta missing")
        elif value_delta < 0:
            finance_status = _status_worst([finance_status, "AMBER"])
            finance_signals.append("negative value delta")
        if forecast_pct is None:
            finance_status = _status_worst([finance_status, "AMBER"])
            finance_signals.append("forecast attainment missing")
        else:
            if forecast_pct < (_to_float(finance_cfg.get("forecast_amber_pct")) or 70.0):
                finance_status = _status_worst([finance_status, "RED"])
                finance_signals.append("forecast attainment below amber floor")
            elif forecast_pct < (_to_float(finance_cfg.get("forecast_green_pct")) or 100.0):
                finance_status = _status_worst([finance_status, "AMBER"])
                finance_signals.append("forecast attainment below green target")
        if gross_margin is not None:
            if gross_margin < (_to_float(finance_cfg.get("gross_margin_amber_pct")) or 40.0):
                finance_status = _status_worst([finance_status, "RED"])
                finance_signals.append("gross margin below amber floor")
            elif gross_margin < (_to_float(finance_cfg.get("gross_margin_green_pct")) or 60.0):
                finance_status = _status_worst([finance_status, "AMBER"])
                finance_signals.append("gross margin below green target")
        if not feed_present and not memory_present and not source_present:
            finance_signals.append("automated metric feed not populated yet")
        finance_proposal = (
            "Freeze non-core spend and run a 7-day monetization recovery plan tied to the strongest revenue line."
            if finance_status == "RED"
            else "Shift effort toward highest-yield revenue channels and improve forecast attainment."
            if finance_status == "AMBER"
            else "Reinvest incremental margin into the top-performing growth channel while protecting unit economics."
        )

        marketing_cfg = targets.get("marketing", {})
        marketing_cfg = marketing_cfg if isinstance(marketing_cfg, dict) else {}
        marketing_status = "GREEN"
        marketing_signals: list[str] = []
        if sessions_7d is None or waft_7d is None:
            marketing_status = _status_worst([marketing_status, "AMBER"])
            marketing_signals.append("traffic quality inputs missing")
        else:
            if sessions_7d < (_to_float(marketing_cfg.get("sessions_amber_7d")) or 300.0):
                marketing_status = _status_worst([marketing_status, "RED"])
                marketing_signals.append("sessions below amber floor")
            elif sessions_7d < (_to_float(marketing_cfg.get("sessions_green_7d")) or 1000.0):
                marketing_status = _status_worst([marketing_status, "AMBER"])
                marketing_signals.append("sessions below green target")
            if waft_7d < (_to_float(marketing_cfg.get("waft_amber_7d")) or 75.0):
                marketing_status = _status_worst([marketing_status, "RED"])
                marketing_signals.append("WAFT below amber floor")
            elif waft_7d < (_to_float(marketing_cfg.get("waft_green_7d")) or 200.0):
                marketing_status = _status_worst([marketing_status, "AMBER"])
                marketing_signals.append("WAFT below green target")
        if returning_rate is not None:
            if returning_rate < (_to_float(marketing_cfg.get("returning_amber_pct")) or 10.0):
                marketing_status = _status_worst([marketing_status, "RED"])
                marketing_signals.append("returning rate below amber floor")
            elif returning_rate < (_to_float(marketing_cfg.get("returning_green_pct")) or 20.0):
                marketing_status = _status_worst([marketing_status, "AMBER"])
                marketing_signals.append("returning rate below green target")
        if backlinks_7d is not None and backlinks_7d <= 0:
            marketing_status = _status_worst([marketing_status, "AMBER"])
            marketing_signals.append("no new backlinks this cycle")
        if not feed_present and not memory_present and not source_present:
            marketing_signals.append("automated metric feed not populated yet")
        marketing_proposal = (
            "Launch a focused acquisition sprint for the top-converting tool and pause low-intent channels."
            if marketing_status == "RED"
            else "Tighten campaign targeting around high-intent cohorts and improve returning-user loops."
            if marketing_status == "AMBER"
            else "Scale proven campaigns and expand partner distribution tied to best-performing pages."
        )

        product_cfg = targets.get("product", {})
        product_cfg = product_cfg if isinstance(product_cfg, dict) else {}
        product_status = "GREEN"
        product_signals: list[str] = []
        if completion_rate is None:
            product_status = _status_worst([product_status, "AMBER"])
            product_signals.append("tool completion missing")
        else:
            if completion_rate < (_to_float(product_cfg.get("completion_amber_pct")) or 40.0):
                product_status = _status_worst([product_status, "RED"])
                product_signals.append("tool completion below amber floor")
            elif completion_rate < (_to_float(product_cfg.get("completion_green_pct")) or 60.0):
                product_status = _status_worst([product_status, "AMBER"])
                product_signals.append("tool completion below green target")
        if latency_ms is not None and latency_target is not None:
            if latency_ms > latency_target * (_to_float(product_cfg.get("latency_amber_factor")) or 1.5):
                product_status = _status_worst([product_status, "RED"])
                product_signals.append("latency materially above target")
            elif latency_ms > latency_target * (_to_float(product_cfg.get("latency_green_factor")) or 1.0):
                product_status = _status_worst([product_status, "AMBER"])
                product_signals.append("latency above target")
        if not feed_present and not memory_present and not source_present:
            product_signals.append("automated metric feed not populated yet")
        product_proposal = (
            "Prioritize core tool UX fixes and performance remediation before shipping new features."
            if product_status == "RED"
            else "Run focused experiments on onboarding/friction points to raise completion and retention."
            if product_status == "AMBER"
            else "Expand high-performing workflows and test adjacent wedge features with strict KPI gates."
        )

        operations_cfg = targets.get("operations", {})
        operations_cfg = operations_cfg if isinstance(operations_cfg, dict) else {}
        operations_status = "GREEN"
        operations_signals: list[str] = []
        if drafts_pending is not None:
            if drafts_pending > (_to_float(operations_cfg.get("drafts_amber_max")) or 15.0):
                operations_status = _status_worst([operations_status, "RED"])
                operations_signals.append("content backlog above amber limit")
            elif drafts_pending > (_to_float(operations_cfg.get("drafts_green_max")) or 6.0):
                operations_status = _status_worst([operations_status, "AMBER"])
                operations_signals.append("content backlog above green limit")
        if pages_indexed is not None:
            if pages_indexed < (_to_float(operations_cfg.get("pages_indexed_amber_7d")) or 1.0):
                operations_status = _status_worst([operations_status, "RED"])
                operations_signals.append("pages indexed below amber floor")
            elif pages_indexed < (_to_float(operations_cfg.get("pages_indexed_green_7d")) or 5.0):
                operations_status = _status_worst([operations_status, "AMBER"])
                operations_signals.append("pages indexed below green target")
        elif sitemap_age_days is not None:
            if sitemap_age_days > 14.0:
                operations_status = _status_worst([operations_status, "RED"])
                operations_signals.append("sitemap freshness stale")
            elif sitemap_age_days > 7.0:
                operations_status = _status_worst([operations_status, "AMBER"])
                operations_signals.append("sitemap freshness drifting")
        if research_brief_age_days is not None:
            if research_brief_age_days > 14.0:
                operations_status = _status_worst([operations_status, "RED"])
                operations_signals.append("research brief stale")
            elif research_brief_age_days > 8.0:
                operations_status = _status_worst([operations_status, "AMBER"])
                operations_signals.append("research brief aging past target")
        if value_delta is not None and value_delta < 0:
            operations_status = _status_worst([operations_status, "AMBER"])
            operations_signals.append("execution cost/value mix under target")
        operations_proposal = (
            "Re-sequence weekly workload to clear bottlenecks and align output strictly to wedge-critical deliverables."
            if operations_status == "RED"
            else "Tighten weekly capacity allocation to close backlog and indexing gaps."
            if operations_status == "AMBER"
            else "Maintain cadence and increase throughput only where value delta remains positive."
        )

        departments = {
            "finance": {
                "audience": "Finance + Commercial",
                "status": finance_status,
                "score": _status_to_score(finance_status),
                "headline": (
                    f"value_delta={_fmt_optional_money(value_delta)} | total_mrr={_fmt_optional_money(total_mrr)} "
                    f"| forecast={_fmt_optional_pct(forecast_pct)}"
                ),
                "signals": finance_signals or ["on plan"],
                "proposal": finance_proposal,
            },
            "marketing": {
                "audience": "Marketing + Growth",
                "status": marketing_status,
                "score": _status_to_score(marketing_status),
                "headline": (
                    f"sessions_7d={sessions_7d if sessions_7d is not None else 'n/a'} | "
                    f"waft_7d={waft_7d if waft_7d is not None else 'n/a'} | "
                    f"returning_rate={_fmt_optional_pct(returning_rate)}"
                ),
                "signals": marketing_signals or ["on plan"],
                "proposal": marketing_proposal,
            },
            "product": {
                "audience": "Product + UX",
                "status": product_status,
                "score": _status_to_score(product_status),
                "headline": (
                    f"completion={_fmt_optional_pct(completion_rate)} | "
                    f"latency_ms={latency_ms if latency_ms is not None else 'n/a'}"
                ),
                "signals": product_signals or ["on plan"],
                "proposal": product_proposal,
            },
            "operations": {
                "audience": "Operations + Content Studio",
                "status": operations_status,
                "score": _status_to_score(operations_status),
                "headline": (
                    f"drafts_pending={drafts_pending if drafts_pending is not None else 'n/a'} | "
                    f"pages_indexed_7d={pages_indexed if pages_indexed is not None else 'n/a'} | "
                    f"research_age_days={research_brief_age_days if research_brief_age_days is not None else 'n/a'}"
                ),
                "signals": operations_signals or ["on plan"],
                "proposal": operations_proposal,
            },
        }

        dept_statuses = [str(entry.get("status", "")).upper() for entry in departments.values()]
        md_status = _status_worst(dept_statuses)
        md_score = int(round(sum(int(entry.get("score", 0)) for entry in departments.values()) / max(len(departments), 1)))
        md_focus: list[str] = []
        for dept_name, entry in departments.items():
            if str(entry.get("status", "")).upper() == "GREEN":
                continue
            md_focus.append(f"{dept_name.title()}: {entry.get('proposal')}")
        if not md_focus:
            md_focus.append("Keep current execution model and scale only proven growth levers.")
        md_direction = (
            "Stabilize weak functions first; no expansion until core KPI floors recover."
            if md_status == "RED"
            else "Resolve amber bottlenecks and concentrate resources on highest-yield levers."
            if md_status == "AMBER"
            else "Scale validated channels and compound value while guarding wedge discipline."
        )

        output.append(
            {
                "property_id": block.get("property_id"),
                "property_name": block.get("property_name"),
                "product_wordmark": block.get("product_wordmark"),
                "departments": departments,
                "md_overall": {
                    "audience": "Managing Director / Holding Board",
                    "status": md_status,
                    "score": md_score,
                    "headline": f"cross-functional status={md_status} | weighted_score={md_score}/100",
                    "strategic_direction": md_direction,
                    "focus_next_7d": md_focus[:4],
                },
                "metrics": {
                    "value_delta_usd": value_delta,
                    "forecast_attainment_pct": forecast_pct,
                    "total_mrr_usd": total_mrr,
                    "r12_counter": r12_counter,
                    "r12_halt_active": r12_halt,
                    "sitemap_lastmod_age_days": sitemap_age_days,
                    "research_brief_age_days": research_brief_age_days,
                },
            }
        )

    return output


def _render_property_department_briefs_markdown(briefs: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = ["## Property Department Briefs"]
    if not briefs:
        lines.append("- No departmental property briefs available.")
        return lines

    for brief in briefs:
        if not isinstance(brief, dict):
            continue
        name = str(brief.get("property_name", "n/a"))
        wordmark = str(brief.get("product_wordmark", "")).strip()
        lines.append(f"### {name}" + (f" ({wordmark})" if wordmark else ""))
        departments = brief.get("departments", {})
        departments = departments if isinstance(departments, dict) else {}
        for dept_name in ["finance", "marketing", "product", "operations"]:
            entry = departments.get(dept_name, {})
            entry = entry if isinstance(entry, dict) else {}
            signals = entry.get("signals", [])
            signals = signals if isinstance(signals, list) else []
            signal_text = "; ".join(str(item).strip() for item in signals if str(item).strip()) or "n/a"
            lines.append(
                "- {dept}: [{status}] score={score}/100 | audience={audience} | {headline} | signals={signals} | proposal={proposal}".format(
                    dept=dept_name.title(),
                    status=entry.get("status", "n/a"),
                    score=entry.get("score", "n/a"),
                    audience=entry.get("audience", "n/a"),
                    headline=entry.get("headline", "n/a"),
                    signals=signal_text,
                    proposal=entry.get("proposal", "n/a"),
                )
            )

        md = brief.get("md_overall", {})
        md = md if isinstance(md, dict) else {}
        focus = md.get("focus_next_7d", [])
        focus = focus if isinstance(focus, list) else []
        focus_text = "; ".join(str(item).strip() for item in focus if str(item).strip()) or "n/a"
        lines.append(
            "- MD Overall: [{status}] score={score}/100 | audience={audience} | direction={direction} | focus_next_7d={focus}".format(
                status=md.get("status", "n/a"),
                score=md.get("score", "n/a"),
                audience=md.get("audience", "n/a"),
                direction=md.get("strategic_direction", "n/a"),
                focus=focus_text,
            )
        )

    return lines


def _append_property_kpi_history(
    config: dict[str, Any],
    generated_at: datetime,
    briefs: list[dict[str, Any]],
) -> str:
    history_path = _property_kpi_history_path(config)
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        for brief in briefs:
            if not isinstance(brief, dict):
                continue
            departments = brief.get("departments", {})
            departments = departments if isinstance(departments, dict) else {}
            metrics = brief.get("metrics", {})
            metrics = metrics if isinstance(metrics, dict) else {}
            md = brief.get("md_overall", {})
            md = md if isinstance(md, dict) else {}

            record = {
                "generated_at_utc": generated_at.isoformat(),
                "property_id": brief.get("property_id"),
                "property_name": brief.get("property_name"),
                "md_status": md.get("status"),
                "md_score": md.get("score"),
                "department_statuses": {
                    "finance": departments.get("finance", {}).get("status") if isinstance(departments.get("finance"), dict) else None,
                    "marketing": departments.get("marketing", {}).get("status") if isinstance(departments.get("marketing"), dict) else None,
                    "product": departments.get("product", {}).get("status") if isinstance(departments.get("product"), dict) else None,
                    "operations": departments.get("operations", {}).get("status") if isinstance(departments.get("operations"), dict) else None,
                },
                "department_scores": {
                    "finance": departments.get("finance", {}).get("score") if isinstance(departments.get("finance"), dict) else None,
                    "marketing": departments.get("marketing", {}).get("score") if isinstance(departments.get("marketing"), dict) else None,
                    "product": departments.get("product", {}).get("score") if isinstance(departments.get("product"), dict) else None,
                    "operations": departments.get("operations", {}).get("score") if isinstance(departments.get("operations"), dict) else None,
                },
                "metrics": metrics,
            }
            handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    return str(history_path)


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
    property_pnl_blocks: list[dict[str, Any]] | None = None,
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

    property_blocks = property_pnl_blocks if isinstance(property_pnl_blocks, list) else []
    property_types = {
        str(block.get("property_type", "")).strip().lower()
        for block in property_blocks
        if isinstance(block, dict)
    }
    property_types.discard("")
    use_legacy_scope = not property_types

    green_divisions = 0
    commercial_status: str | None = None
    for division in divisions:
        if not isinstance(division, dict):
            continue
        division_name = str(division.get("division", "")).strip().lower()
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        status = str(division.get("status", scorecard.get("status", ""))).upper()
        if division_name == "commercial" and status in {"GREEN", "AMBER", "RED"}:
            commercial_status = status
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

    items: list[dict[str, Any]] = []

    if use_legacy_scope or "trading_bot" in property_types:
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

        items.append(
            {
                "metric": "Monthly PnL growth",
                "target": f">= {growth_target:.1f}%",
                "actual": _fmt_pct(growth_actual, 2),
                "variance": growth_variance if growth_actual is not None else "baseline collecting",
                "status": growth_status,
                "action": "Review monthly PnL trajectory and adjust risk/strategy allocation if growth is off target.",
            }
        )
        items.append(
            {
                "metric": "Max drawdown",
                "target": f"<= {dd_target:.1f}%",
                "actual": _fmt_pct(drawdown_actual, 2),
                "variance": dd_variance,
                "status": dd_status,
                "action": "If drawdown exceeds tolerance, reduce exposure and tighten per-trade risk limits.",
            }
        )
    else:
        monthly_growth_meta = {"mode": "skipped_non_trading_scope"}

    if use_legacy_scope or "website" in property_types:
        websites_total = max(_to_int(summary.get("websites_total")) or 0, 0)
        websites_up = max(_to_int(summary.get("websites_up")) or 0, 0)
        uptime_ratio = (websites_up / websites_total) if websites_total else None
        uptime_cfg = company_targets.get("website_uptime_ratio", {})
        uptime_cfg = uptime_cfg if isinstance(uptime_cfg, dict) else {}
        uptime_target = _to_float(uptime_cfg.get("target_min")) or 0.999
        uptime_amber = _to_float(uptime_cfg.get("amber_min")) or 0.99
        uptime_status, uptime_variance = _status_from_min(uptime_ratio, uptime_target, uptime_amber)
        items.append(
            {
                "metric": "Website uptime ratio (snapshot)",
                "target": f">= {uptime_target*100:.2f}%",
                "actual": _fmt_ratio(uptime_ratio),
                "variance": uptime_variance,
                "status": uptime_status,
                "action": "Escalate any downtime before non-critical roadmap work.",
            }
        )

    if property_blocks:
        blocks_green = 0
        forecast_pct_values: list[float] = []
        value_deltas: list[float] = []

        for block in property_blocks:
            if not isinstance(block, dict):
                continue
            status_payload = block.get("status", {})
            status_payload = status_payload if isinstance(status_payload, dict) else {}
            if str(status_payload.get("value", "")).upper() == "GREEN":
                blocks_green += 1

            forecast_pct = _to_float(status_payload.get("pct_to_forecast_mrr"))
            if forecast_pct is not None:
                forecast_pct_values.append(forecast_pct)

            operations = block.get("operations", {})
            operations = operations if isinstance(operations, dict) else {}
            value_delta = _to_float(operations.get("value_delta_usd"))
            if value_delta is not None:
                value_deltas.append(value_delta)

        block_ratio = (blocks_green / len(property_blocks)) if property_blocks else None
        block_ratio_cfg = company_targets.get("property_blocks_green_ratio", {})
        block_ratio_cfg = block_ratio_cfg if isinstance(block_ratio_cfg, dict) else {}
        block_ratio_target = _to_float(block_ratio_cfg.get("target_min")) or 1.0
        block_ratio_amber = _to_float(block_ratio_cfg.get("amber_min")) or 0.67
        block_ratio_status, block_ratio_variance = _status_from_min(block_ratio, block_ratio_target, block_ratio_amber)
        items.append(
            {
                "metric": "Property blocks on-plan ratio",
                "target": f">= {block_ratio_target*100:.0f}%",
                "actual": _fmt_ratio(block_ratio),
                "variance": block_ratio_variance,
                "status": block_ratio_status,
                "action": "Focus execution on RED/AMBER properties before adding new initiatives.",
            }
        )

        forecast_avg = (sum(forecast_pct_values) / len(forecast_pct_values)) if forecast_pct_values else None
        forecast_cfg = company_targets.get("property_forecast_attainment_pct", {})
        forecast_cfg = forecast_cfg if isinstance(forecast_cfg, dict) else {}
        forecast_target = _to_float(forecast_cfg.get("target_min")) or 100.0
        forecast_amber = _to_float(forecast_cfg.get("amber_min")) or 70.0
        forecast_status, forecast_variance = _status_from_min(forecast_avg, forecast_target, forecast_amber)
        items.append(
            {
                "metric": "Property forecast attainment",
                "target": f">= {forecast_target:.0f}%",
                "actual": _fmt_pct(forecast_avg, 1),
                "variance": forecast_variance,
                "status": forecast_status,
                "action": "Prioritize monetization levers that increase MRR progress to 90-day targets.",
            }
        )

        value_delta_total = sum(value_deltas) if value_deltas else None
        value_delta_cfg = company_targets.get("property_value_delta_usd_7d", {})
        value_delta_cfg = value_delta_cfg if isinstance(value_delta_cfg, dict) else {}
        value_delta_target = _to_float(value_delta_cfg.get("target_min")) or 0.0
        value_delta_amber = _to_float(value_delta_cfg.get("amber_min")) or -500.0
        value_delta_status, value_delta_variance = _status_from_min(value_delta_total, value_delta_target, value_delta_amber)
        items.append(
            {
                "metric": "Property value delta (7d)",
                "target": f">= {_fmt_money(value_delta_target)}",
                "actual": _fmt_optional_money(value_delta_total),
                "variance": value_delta_variance,
                "status": value_delta_status,
                "action": "If net-negative, rebalance effort/cost against proven revenue and value drivers immediately.",
            }
        )

    items.append(
        {
            "metric": "Division GREEN ratio",
            "target": f">= {div_target*100:.0f}%",
            "actual": _fmt_ratio(division_ratio),
            "variance": div_variance,
            "status": div_status,
            "action": "Address weakest division scorecards first to restore portfolio-wide health.",
        }
    )
    items.append(
        {
            "metric": "Alert count per heartbeat",
            "target": f"<= {int(alert_target)}",
            "actual": str(int(alert_actual)),
            "variance": alert_variance,
            "status": alert_status,
            "action": "Reduce recurrent alerts by fixing root causes, not by suppressing checks.",
        }
    )
    if commercial_status in {"RED", "AMBER"}:
        commercial_variance = "-2 levels from GREEN" if commercial_status == "RED" else "-1 level from GREEN"
        items.append(
            {
                "metric": "commercial_health",
                "target": "GREEN",
                "actual": commercial_status,
                "variance": commercial_variance,
                "status": commercial_status,
                "action": "Review Commercial risk verdict and exposure flags; restore GREEN before new initiatives.",
            }
        )

    risks: list[str] = []
    actions: list[str] = []
    for item in items:
        if item["status"] == "RED":
            risks.append(f"{item['metric']} is RED ({item['actual']} vs target {item['target']}).")
            actions.append(item["action"])
        elif item["status"] == "AMBER":
            risks.append(f"{item['metric']} is AMBER ({item['actual']} vs target {item['target']}).")
            actions.append(item["action"])

    if not actions:
        actions.append("Company-level KPIs are within target range; continue current operating cadence.")

    status_inputs = [str(item.get("status", "")).upper() for item in items]
    if commercial_status in {"GREEN", "AMBER", "RED"}:
        status_inputs.append(commercial_status)
    status = _status_worst(status_inputs)
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

    if not model.strip().lower().startswith("ollama/"):
        return None, f"Non-local LLM model blocked by R1: {model}"
    parsed = urlparse(base_url)
    host = (parsed.hostname or "").strip().lower()
    if host not in {"127.0.0.1", "localhost", "host.docker.internal"}:
        return None, f"Non-local Ollama base URL blocked by R1: {base_url}"
    openai_base = f"{base_url.rstrip('/')}/v1"

    storage_dir = ROOT / "state" / "crewai"
    storage_dir.mkdir(parents=True, exist_ok=True)
    os.environ["CREWAI_STORAGE_DIR"] = str(storage_dir)
    os.environ["CREWAI_HOME"] = str(storage_dir)
    os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
    os.environ["CREWAI_TRACING_ENABLED"] = "false"
    os.environ["OTEL_SDK_DISABLED"] = "true"
    # Force OpenAI-compatible clients to local Ollama endpoint (R1).
    os.environ["OPENAI_API_KEY"] = "ollama-local"
    os.environ["OPENAI_BASE_URL"] = openai_base
    os.environ["OPENAI_API_BASE"] = openai_base
    os.environ["OLLAMA_BASE_URL"] = base_url
    for cloud_env in ["ANTHROPIC_API_KEY", "GROQ_API_KEY", "GOOGLE_API_KEY", "MISTRAL_API_KEY", "TOGETHER_API_KEY"]:
        os.environ.pop(cloud_env, None)

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

    tail = tokens[2:]
    subcommand = ""
    arg_tokens: list[str] = []
    index = 0
    while index < len(tail):
        token = tail[index]
        if not token.startswith("--"):
            subcommand = token.strip("\"'")
            arg_tokens = tail[index + 1 :]
            break
        flag = token.split("=", 1)[0]
        if flag != "--config":
            return False
        if "=" not in token:
            if index + 1 >= len(tail):
                return False
            index += 2
            continue
        index += 1
    if not subcommand:
        return False
    spec = _ALLOWED_PHASE3_SUBCOMMANDS.get(subcommand)
    if spec is None:
        return False

    required = set(spec.get("required", set()))
    allowed_flags = set(spec.get("allowed_flags", set()))
    seen_flags: set[str] = set()
    for token in arg_tokens:
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
    board_review: dict[str, Any] | None = None,
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

    ceo_task_spec = None
    dissent_task_spec = None
    for raw_task in spec.get("tasks", []):
        if not isinstance(raw_task, dict):
            continue
        task_key = str(raw_task.get("key", "")).strip()
        if ceo_task_spec is None:
            ceo_task_spec = raw_task
        if task_key == "ceo_board_task":
            ceo_task_spec = raw_task
        if task_key == "dissent_task":
            dissent_task_spec = raw_task
    if not isinstance(ceo_task_spec, dict):
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CEO spec missing task definition; using fallback.",
        }

    agent_key = str(ceo_task_spec.get("agent", "")).strip()
    if agent_key not in agents_map:
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": "CEO task agent missing; using fallback.",
        }

    board = board_review if isinstance(board_review, dict) else {}
    board_items = board.get("approvals", [])
    board_items = [item for item in board_items if isinstance(item, dict)]

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
        "board_pack_json": json.dumps(board_items, indent=2),
    }

    description = str(ceo_task_spec.get("description", ""))
    for key, value in values.items():
        description = description.replace("{" + key + "}", value)
    expected_output = str(ceo_task_spec.get("expected_output", ""))

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

    try:
        kickoff = str(crew.kickoff()).strip()
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": True,
            "engine": "fallback_local_rules",
            "brief_markdown": _fallback_ceo_brief(mode=mode, company_scorecard=company_scorecard, divisions=divisions),
            "warning": f"CEO Crew execution failed ({exc}); using deterministic fallback.",
        }
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

    warning_text = "CEO output contained non-allowlisted commands; blocked command lines were removed." if blocked else None
    if mode == "board_pack" and board_items:
        dissent_unavailable = "Dissent agent unavailable - manual review required"
        try:
            if not isinstance(dissent_task_spec, dict):
                raise ValueError("dissent_task missing in holding_ceo.yaml")
            dissent_agent_key = str(dissent_task_spec.get("agent", "")).strip()
            if dissent_agent_key not in agents_map:
                raise ValueError("dissent_task agent missing")

            dissent_description = str(dissent_task_spec.get("description", ""))
            for key, value in values.items():
                dissent_description = dissent_description.replace("{" + key + "}", value)
            dissent_expected_output = str(dissent_task_spec.get("expected_output", ""))
            dissent_task = Task(
                description=dissent_description,
                expected_output=dissent_expected_output,
                agent=agents_map[dissent_agent_key],
            )
            dissent_crew = Crew(
                agents=list(agents_map.values()),
                tasks=[dissent_task],
                process=Process.sequential,
                verbose=bool(spec.get("verbose", False)),
            )
            dissent_raw = str(dissent_crew.kickoff()).strip()
            dissent_cleaned, _ = _sanitize_ceo_output(dissent_raw)
            dissent_payload = dissent_cleaned.strip()
            if dissent_payload.startswith("```"):
                dissent_payload = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", dissent_payload)
                if dissent_payload.endswith("```"):
                    dissent_payload = dissent_payload[:-3].strip()

            try:
                dissent_items = json.loads(dissent_payload)
            except json.JSONDecodeError:
                start = dissent_payload.find("[")
                end = dissent_payload.rfind("]")
                if start == -1 or end <= start:
                    raise
                dissent_items = json.loads(dissent_payload[start : end + 1])

            if not isinstance(dissent_items, list):
                raise ValueError("dissent_task output is not a JSON list")

            objections_by_topic: dict[str, str] = {}
            for entry in dissent_items:
                if not isinstance(entry, dict):
                    continue
                topic_key = str(entry.get("item", "")).strip().lower()
                objection = str(entry.get("objection", "")).strip()
                if topic_key and objection:
                    objections_by_topic[topic_key] = objection

            for approval in board_items:
                topic = str(approval.get("topic", "")).strip()
                topic_key = topic.lower()
                if topic_key in objections_by_topic:
                    approval["dissent"] = objections_by_topic[topic_key]
                else:
                    logging.warning("Dissent topic mismatch for board item: %s", topic)
        except Exception as exc:  # noqa: BLE001
            for approval in board_items:
                approval["dissent"] = dissent_unavailable
            dissent_warning = f"Dissent merge failed ({exc}); set manual-review fallback."
            warning_text = f"{warning_text} | {dissent_warning}" if warning_text else dissent_warning
        if any(not _validate_board_pack_item(item) for item in board_items):
            cleaned_output = f"⚠️ INCOMPLETE BOARD PACK — {cleaned_output}"

    return {
        "ok": True,
        "engine": "crewai_ceo",
        "brief_markdown": cleaned_output,
        "warning": warning_text,
    }


def _build_board_review(
    company_scorecard: dict[str, Any],
    divisions: list[dict[str, Any]],
    commercial_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    approvals: list[dict[str, Any]] = []
    rank = {"RED": 0, "AMBER": 1, "GREEN": 2}
    red_deadline = datetime.now(timezone.utc).date().isoformat()

    company_items = [item for item in company_scorecard.get("items", []) if isinstance(item, dict)]
    for item in sorted(company_items, key=lambda x: rank.get(str(x.get("status", "")).upper(), 3)):
        status = str(item.get("status", "")).upper()
        if status == "GREEN":
            continue
        metric = str(item.get("metric", "n/a"))
        actual = str(item.get("actual", "n/a"))
        target = str(item.get("target", "n/a"))
        action = str(item.get("action", "")).strip()
        action_suffix = action if action else "Immediate review required."
        approvals.append(
            {
                "rationale": f"KPI {metric} is {status} (actual={actual}, target={target}). {action_suffix}",
                "expected_upside": f"Restores {metric} to target ({target})",
                "effort_cost": "n/a",
                "confidence": "Medium - derived from telemetry; LLM scoring not yet applied",
                "owner": "holding",
                "deadline": red_deadline if status == "RED" else "+7d",
                "dissent": "PENDING - dissent_agent review required",
                "measurement_plan": f"Monitor {metric} in next daily brief. GREEN for 2 consecutive runs.",
                "priority": status,
                "topic": f"Company KPI: {metric}",
            }
        )

    for division in divisions:
        if not isinstance(division, dict):
            continue
        division_name = str(division.get("division", "holding")).strip() or "holding"
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        division_items = [item for item in scorecard.get("items", []) if isinstance(item, dict)]
        for item in sorted(
            division_items,
            key=lambda x: rank.get(str(x.get("status", "")).upper(), 3),
        ):
            status = str(item.get("status", "")).upper()
            if status == "GREEN":
                continue
            metric = str(item.get("metric", "n/a"))
            actual = str(item.get("actual", "n/a"))
            target = str(item.get("target", "n/a"))
            action = str(item.get("action", "")).strip()
            action_suffix = action if action else "Immediate review required."
            approvals.append(
                {
                    "rationale": f"KPI {metric} is {status} (actual={actual}, target={target}). {action_suffix}",
                    "expected_upside": f"Restores {metric} to target ({target})",
                    "effort_cost": "n/a",
                    "confidence": "Medium - derived from telemetry; LLM scoring not yet applied",
                    "owner": division_name.lower(),
                    "deadline": red_deadline if status == "RED" else "+7d",
                    "dissent": "PENDING - dissent_agent review required",
                    "measurement_plan": f"Monitor {metric} in next daily brief. GREEN for 2 consecutive runs.",
                    "priority": status,
                    "topic": f"{division_name.title()} KPI: {metric}",
                }
            )

    if isinstance(commercial_result, dict):
        commercial_status = str(commercial_result.get("status", "")).upper()
        if commercial_status and commercial_status != "GREEN":
            risk = commercial_result.get("risk", {})
            risk = risk if isinstance(risk, dict) else {}
            exposure_flags = risk.get("exposure_flags", [])
            first_flag = ""
            if isinstance(exposure_flags, list):
                for flag in exposure_flags:
                    if isinstance(flag, str) and flag.strip():
                        first_flag = flag.strip()
                        break
            topic_tail = first_flag if first_flag else "Commercial risk check"
            rationale = str(risk.get("risk_verdict", "")).strip() or "n/a"
            approvals.append(
                {
                    "rationale": rationale,
                    "expected_upside": "",
                    "effort_cost": "n/a",
                    "confidence": "",
                    "owner": "commercial",
                    "deadline": red_deadline if commercial_status == "RED" else "+7d",
                    "dissent": "PENDING - dissent_agent review required",
                    "measurement_plan": "",
                    "priority": commercial_status,
                    "topic": f"Commercial: {topic_tail}",
                }
            )

    return {
        "approvals": approvals[:10],
        "notes": "Approve, defer, or reject each item explicitly to keep accountability clear.",
    }


def _validate_board_pack_item(item: dict[str, Any]) -> bool:
    rationale = str(item.get("rationale", "")).strip()
    owner = str(item.get("owner", "")).strip()
    measurement_plan = str(item.get("measurement_plan", "")).strip()
    return bool(rationale and owner and measurement_plan)


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

    property_blocks_raw = payload.get("property_pnl_blocks", [])
    property_blocks = (
        [block for block in property_blocks_raw if isinstance(block, dict)]
        if isinstance(property_blocks_raw, list)
        else []
    )
    lines.append("")
    lines.extend(_render_property_pnl_blocks_markdown(property_blocks))
    department_briefs_raw = payload.get("property_department_briefs", [])
    department_briefs = (
        [brief for brief in department_briefs_raw if isinstance(brief, dict)]
        if isinstance(department_briefs_raw, list)
        else []
    )
    lines.append("")
    lines.extend(_render_property_department_briefs_markdown(department_briefs))

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

    if payload.get("mode") in {"board_review", "board_pack"}:
        board = payload.get("board_review", {})
        board = board if isinstance(board, dict) else {}
        lines.append("")
        lines.append("## Board Pack")
        approvals = board.get("approvals", [])
        approvals = approvals if isinstance(approvals, list) else []
        if not approvals:
            lines.append("- No pending approvals.")
        else:
            for item in approvals:
                if not isinstance(item, dict):
                    continue
                lines.append(f"### [{item.get('priority') or 'n/a'}] {item.get('topic') or 'n/a'}")
                lines.append(f"- **Rationale:** {item.get('rationale') or 'n/a'}")
                lines.append(f"- **Upside:** {item.get('expected_upside') or 'n/a'}")
                lines.append(f"- **Effort/Cost:** {item.get('effort_cost') or 'n/a'}")
                lines.append(f"- **Confidence:** {item.get('confidence') or 'n/a'}")
                lines.append(f"- **Owner:** {item.get('owner') or 'n/a'}")
                lines.append(f"- **Deadline:** {item.get('deadline') or 'n/a'}")
                lines.append(f"- **Dissent:** {item.get('dissent') or 'n/a'}")
                lines.append(f"- **Measurement:** {item.get('measurement_plan') or 'n/a'}")
        lines.append(f"- Notes: {board.get('notes')}")

    lines.append("")
    lines.append("## Owner Command Reminder")
    lines.append("- `python scripts/tool_router.py run_holding --mode heartbeat --force`")
    lines.append("- `python scripts/tool_router.py run_holding --mode board_review --force`")
    lines.append("- `python scripts/tool_router.py run_holding --mode board_pack --force`")
    return "\n".join(lines).strip() + "\n"


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

    divisions = phase2_payload.get("divisions", [])
    divisions = divisions if isinstance(divisions, list) else []
    commercial_result: dict[str, Any] | None = None
    for division in divisions:
        if not isinstance(division, dict):
            continue
        if str(division.get("division", "")).strip().lower() != "commercial":
            continue
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        final_output = division.get("final_output", {})
        final_output = final_output if isinstance(final_output, dict) else {}
        risk = final_output.get("risk", {})
        risk = risk if isinstance(risk, dict) else {}
        commercial_result = {
            "status": str(division.get("status", scorecard.get("status", ""))).upper(),
            "risk": risk,
        }
        break

    targets = _load_targets(config)
    soul_text = _load_soul(config)
    generated_at = datetime.now(timezone.utc)
    feed_refresh_warning: str | None = None
    try:
        _refresh_property_metric_feed_from_phase2(
            config=config,
            phase2_payload=phase2_payload,
            generated_at=generated_at,
        )
    except OSError as exc:
        feed_refresh_warning = f"Property metric feed refresh failed: {exc}"
    property_pnl_blocks = _build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=generated_at,
    )
    property_department_briefs = _build_property_department_briefs(
        config=config,
        property_blocks=property_pnl_blocks,
    )
    kpi_history_file = ""
    history_warning: str | None = None
    try:
        kpi_history_file = _append_property_kpi_history(
            config=config,
            generated_at=generated_at,
            briefs=property_department_briefs,
        )
    except OSError as exc:
        history_warning = f"Property KPI history write failed: {exc}"
    company_scorecard = _score_company(
        config=config,
        phase2_payload=phase2_payload,
        targets=targets,
        property_pnl_blocks=property_pnl_blocks,
    )

    board_review: dict[str, Any] | None = None
    if mode in {"board_review", "board_pack"}:
        board_review = _build_board_review(
            company_scorecard=company_scorecard,
            divisions=divisions,
            commercial_result=commercial_result,
        )

    llm, llm_warning = _build_llm(config=config)
    ceo_result = _run_ceo_brief(
        config=config,
        llm=llm,
        mode=mode,
        soul_text=soul_text,
        company_scorecard=company_scorecard,
        phase2_payload=phase2_payload,
        board_review=board_review,
    )

    if mode == "board_pack" and isinstance(board_review, dict):
        approvals = board_review.get("approvals", [])
        approvals = approvals if isinstance(approvals, list) else []
        if ceo_result.get("engine") != "crewai_ceo":
            for item in approvals:
                if isinstance(item, dict):
                    item["dissent"] = "Dissent agent unavailable - manual review required"

    payload: dict[str, Any] = {
        "ok": True,
        "company_name": str(phase2_payload.get("company_name", config.get("company", {}).get("name", "AI Holding Company"))),
        "generated_at_utc": generated_at.isoformat(),
        "mode": mode,
        "source_brief_mode": phase2_payload.get("source_brief_mode"),
        "targets_file": str((_phase3_cfg(config).get("targets_file") or "config/targets.yaml")),
        "soul_file": str((_phase3_cfg(config).get("soul_file") or "SOUL.md")),
        "base_summary": phase2_payload.get("base_summary", {}),
        "base_alerts": phase2_payload.get("base_alerts", []),
        "warnings": [
            warning
            for warning in [llm_warning, ceo_result.get("warning"), history_warning, feed_refresh_warning]
            if warning
        ],
        "company_scorecard": company_scorecard,
        "property_pnl_blocks": property_pnl_blocks,
        "property_department_briefs": property_department_briefs,
        "property_kpi_history_file": kpi_history_file,
        "divisions": divisions,
        "ceo_engine": ceo_result.get("engine"),
        "ceo_brief_markdown": ceo_result.get("brief_markdown", ""),
        "phase2_files": phase2_payload.get("files", {}),
        "phase2_payload_ref": phase2_payload.get("files", {}).get("latest_json"),
    }

    if mode in {"board_review", "board_pack"}:
        payload["board_review"] = board_review if isinstance(board_review, dict) else {"approvals": [], "notes": ""}

    markdown = _build_phase3_markdown(payload)
    payload["files"] = _persist_phase3_reports(config=config, payload=payload, markdown=markdown)
    return payload

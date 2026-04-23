from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import phase3_holding  # noqa: E402


def _base_config(tmp_path: Path) -> dict:
    return {
        "phase2": {"targets": {"websites": {"max_latency_ms": 500}}},
        "phase3": {"r12_counter_state_file": str(tmp_path / "r12_property_counters.json")},
        "property_charters": {
            "freetraderhub": {
                "name": "FreeTraderHub",
                "product_wordmark": "PROP COCKPIT",
                "charter": {
                    "version": "v1",
                    "wedge": "prop-firm calculators",
                    "property_type": "tool_led_media",
                    "phase": "A",
                    "internal_rate_usd_hr": 35,
                    "r12_formula_version": "v1",
                },
                "tracking": {
                    "audience": {
                        "sessions_7d": 1200,
                        "waft_7d": 250,
                        "returning_user_rate_pct": 18.5,
                        "tool_completion_rate_pct": 62.3,
                    },
                    "revenue": {
                        "affiliate_usd_7d": 300,
                        "ad_usd_7d": 50,
                        "subscription_mrr_usd": 100,
                        "total_mrr_usd": 450,
                        "gross_margin_pct": 70,
                        "top_partner": "FTMO",
                    },
                    "pipeline": {
                        "pages_indexed_7d": 8,
                        "backlinks_dr30_7d": 2,
                        "backlinks_dr30_total": 30,
                        "active_campaign": "spring_push",
                    },
                    "movers": {
                        "top_revenue_line": "position_size_tool",
                        "top_growth_lever": "seo",
                        "biggest_risk": "ranking volatility",
                    },
                    "targets": {"day90_mrr_usd": 900},
                    "ops": {
                        "hours_invested_7d": 5,
                        "direct_costs_usd_7d": 20,
                        "quantified_value_usd_7d": 400,
                    },
                },
            }
        },
    }


def _base_phase2_payload() -> dict:
    return {
        "ok": True,
        "company_name": "AI Holding Company",
        "source_brief_mode": "phase2_fallback",
        "base_summary": {},
        "base_alerts": [],
        "base_websites": [{"id": "freetraderhub_website", "latency_ms": 320}],
        "divisions": [{"division": "content_studio", "drafts_pending": 6, "scorecard": {"status": "GREEN", "items": []}}],
        "files": {"latest_json": "reports/phase2_latest.json"},
    }


def test_build_property_pnl_blocks_calculates_value_and_fallback_drafts(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    phase2_payload = _base_phase2_payload()
    generated_at = datetime(2026, 4, 20, tzinfo=timezone.utc)

    blocks = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=generated_at,
    )

    assert len(blocks) == 1
    block = blocks[0]
    assert block["property_id"] == "freetraderhub"
    assert block["pipeline"]["drafts_pending"] == 6
    assert block["operations"]["value_delta_usd"] == pytest.approx(205.0)
    assert block["status"]["value"] == "GREEN"
    assert block["status"]["pct_to_forecast_mrr"] == pytest.approx(50.0)
    assert block["r12"]["counter"] == 0
    assert (tmp_path / "r12_property_counters.json").exists()


def test_update_r12_counter_increments_weekly_and_halts_at_threshold(tmp_path: Path) -> None:
    config = {"phase3": {"r12_counter_state_file": str(tmp_path / "r12.json")}}
    start = datetime(2026, 4, 20, tzinfo=timezone.utc)

    first = phase3_holding._update_r12_counter(config, "freetraderhub", -10.0, start)
    same_week = phase3_holding._update_r12_counter(config, "freetraderhub", -20.0, start + timedelta(days=2))
    second_week = phase3_holding._update_r12_counter(config, "freetraderhub", -30.0, start + timedelta(days=8))
    third_week = phase3_holding._update_r12_counter(config, "freetraderhub", -40.0, start + timedelta(days=15))
    fourth_week = phase3_holding._update_r12_counter(config, "freetraderhub", -50.0, start + timedelta(days=22))

    assert first["counter"] == 1
    assert same_week["counter"] == 1
    assert second_week["counter"] == 2
    assert third_week["counter"] == 3
    assert fourth_week["counter"] == 4
    assert fourth_week["halt_active"] is True


def test_build_phase3_markdown_renders_property_blocks_section() -> None:
    payload = {
        "company_name": "AI Holding Company",
        "generated_at_utc": "2026-04-22T00:00:00+00:00",
        "mode": "heartbeat",
        "source_brief_mode": "phase2_fallback",
        "company_scorecard": {
            "goal": "Goal",
            "desired_outcome": "Outcome",
            "status": "GREEN",
            "items": [],
            "actions": [],
        },
        "property_pnl_blocks": [
            {
                "property_name": "FreeTraderHub",
                "product_wordmark": "PROP COCKPIT",
                "phase": "A",
                "formula": "v1",
                "audience": {"sessions_7d": 1200, "waft_7d": 250, "returning_user_rate_pct": 18.5, "tool_completion_rate_pct": 62.3},
                "revenue": {"affiliate_usd_7d": 300, "ad_usd_7d": 50, "subscription_mrr_usd": 100, "total_mrr_usd": 450, "gross_margin_pct": 70, "top_partner": "FTMO"},
                "pipeline": {"drafts_pending": 6, "pages_indexed_7d": 8, "backlinks_dr30_7d": 2, "backlinks_dr30_total": 30, "active_campaign": "spring_push"},
                "top_movers": {"top_revenue_line": "position_size_tool", "top_growth_lever": "seo", "biggest_risk": "ranking volatility"},
                "operations": {"value_delta_usd": 205.0},
                "status": {"value": "GREEN", "reason": "on plan", "pct_to_forecast_mrr": 50.0},
                "r12": {"counter": 0, "threshold": 4},
            }
        ],
        "divisions": [],
    }

    markdown = phase3_holding._build_phase3_markdown(payload)

    assert "## Property P&L Blocks" in markdown
    assert "### FreeTraderHub (PROP COCKPIT)" in markdown
    assert "Value Delta (7d): $+205.00" in markdown
    assert "R12 Counter: 0/4" in markdown


def test_run_phase3_holding_includes_property_pnl_blocks_and_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    phase2_payload = _base_phase2_payload()
    captured: dict[str, str] = {}

    monkeypatch.setattr(phase3_holding, "run_phase2_divisions", lambda config, division, force: phase2_payload)
    monkeypatch.setattr(phase3_holding, "_load_targets", lambda config: {})
    monkeypatch.setattr(
        phase3_holding,
        "_score_company",
        lambda config, phase2_payload, targets: {"goal": "Goal", "desired_outcome": "Outcome", "status": "GREEN", "items": [], "actions": []},
    )
    monkeypatch.setattr(phase3_holding, "_load_soul", lambda config: "")
    monkeypatch.setattr(phase3_holding, "_build_llm", lambda config: (None, None))
    monkeypatch.setattr(
        phase3_holding,
        "_run_ceo_brief",
        lambda **kwargs: {"ok": True, "engine": "fallback_local_rules", "brief_markdown": "fallback", "warning": None},
    )

    def _fake_persist(config: dict, payload: dict, markdown: str) -> dict[str, str]:
        captured["markdown"] = markdown
        return {
            "markdown": str(tmp_path / "phase3_holding.md"),
            "json": str(tmp_path / "phase3_holding.json"),
            "latest_markdown": str(tmp_path / "phase3_holding_latest.md"),
            "latest_json": str(tmp_path / "phase3_holding_latest.json"),
        }

    monkeypatch.setattr(phase3_holding, "_persist_phase3_reports", _fake_persist)

    result = phase3_holding.run_phase3_holding(config=config, mode="heartbeat", force=False)

    assert result["ok"] is True
    assert len(result["property_pnl_blocks"]) == 1
    assert result["property_pnl_blocks"][0]["property_id"] == "freetraderhub"
    assert "## Property P&L Blocks" in captured["markdown"]

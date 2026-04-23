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
        "phase3": {
            "r12_counter_state_file": str(tmp_path / "r12_property_counters.json"),
            "property_metric_feed_file": str(tmp_path / "property_metric_feed.json"),
            "property_metric_sources_dir": str(tmp_path / "property_metrics"),
            "property_metric_memory_file": str(tmp_path / "property_metric_memory.json"),
            "property_kpi_history_file": str(tmp_path / "property_kpi_history.jsonl"),
        },
        "property_charters": {
            "freetraderhub": {
                "name": "FreeTraderHub",
                "product_wordmark": "PROP COCKPIT",
                "charter": {
                    "version": "v1",
                    "wedge": "prop-firm calculators",
                    "property_type": "website",
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


def test_build_property_pnl_blocks_skips_stub_or_inactive_charters(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["property_charters"]["stub_prop"] = {
        "charter": {"version": "v0-stub", "property_type": "website"},
    }
    config["property_charters"]["inactive_prop"] = {
        "active": False,
        "charter": {"version": "v1", "property_type": "website"},
    }
    phase2_payload = _base_phase2_payload()

    blocks = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 20, tzinfo=timezone.utc),
    )
    ids = {str(block.get("property_id")) for block in blocks if isinstance(block, dict)}

    assert "freetraderhub" in ids
    assert "stub_prop" not in ids
    assert "inactive_prop" not in ids


def test_build_property_pnl_blocks_ingests_auto_metric_feed(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    feed_path = tmp_path / "property_metric_feed.json"
    feed_path.write_text(
        """
{
  "properties": {
    "freetraderhub": {
      "updated_at_utc": "2026-04-22T00:00:00+00:00",
      "tracking": {
        "audience": {"sessions_7d": 2100, "waft_7d": 420, "returning_user_rate_pct": 27.5, "tool_completion_rate_pct": 68.2},
        "revenue": {"total_mrr_usd": 920, "affiliate_usd_7d": 330, "ad_usd_7d": 75, "gross_margin_pct": 72.0},
        "pipeline": {"pages_indexed_7d": 11, "backlinks_dr30_7d": 4, "active_campaign": "ftmo_q2"},
        "ops": {"hours_invested_7d": 6, "direct_costs_usd_7d": 20, "quantified_value_usd_7d": 500}
      }
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    phase2_payload = _base_phase2_payload()

    blocks = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    assert len(blocks) == 1
    block = blocks[0]
    assert block["audience"]["sessions_7d"] == 2100
    assert block["revenue"]["total_mrr_usd"] == pytest.approx(920.0)
    assert block["pipeline"]["active_campaign"] == "ftmo_q2"
    assert block["operations"]["value_delta_usd"] == pytest.approx(270.0)
    assert block["status"]["pct_to_forecast_mrr"] == pytest.approx((920.0 / 900.0) * 100.0)
    assert block["ingestion"]["feed_present"] is True

    memory_payload = (tmp_path / "property_metric_memory.json").read_text(encoding="utf-8")
    assert "freetraderhub" in memory_payload


def test_build_property_pnl_blocks_uses_memory_when_feed_missing(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    memory_path = tmp_path / "property_metric_memory.json"
    memory_path.write_text(
        """
{
  "properties": {
    "freetraderhub": {
      "updated_at_utc": "2026-04-21T00:00:00+00:00",
      "tracking": {
        "audience": {"sessions_7d": 1400, "waft_7d": 310},
        "revenue": {"total_mrr_usd": 510, "gross_margin_pct": 61.0}
      }
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    phase2_payload = _base_phase2_payload()

    blocks = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    block = blocks[0]

    assert block["audience"]["sessions_7d"] == 1400
    assert block["revenue"]["total_mrr_usd"] == pytest.approx(510.0)
    assert block["ingestion"]["feed_present"] is False
    assert block["ingestion"]["memory_present"] is True


def test_build_property_pnl_blocks_does_not_mark_null_only_memory_as_ingested(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["property_charters"]["freetraderhub"]["tracking"] = {}
    phase2_payload = _base_phase2_payload()

    first = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    assert first[0]["status"]["reason"] == "revenue feed missing (state/property_metric_feed.json or state/property_metrics/*)"

    second = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 23, tzinfo=timezone.utc),
    )
    block = second[0]
    assert block["ingestion"]["feed_present"] is False
    assert block["ingestion"]["memory_present"] is False
    assert block["status"]["reason"] == "revenue feed missing (state/property_metric_feed.json or state/property_metrics/*)"

    briefs = phase3_holding._build_property_department_briefs(config=config, property_blocks=second)
    finance_signals = briefs[0]["departments"]["finance"]["signals"]
    assert "automated metric feed not populated yet" in finance_signals


def test_build_property_pnl_blocks_ingests_department_source_files(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    sources_dir = tmp_path / "property_metrics" / "freetraderhub"
    sources_dir.mkdir(parents=True, exist_ok=True)
    (sources_dir / "marketing.json").write_text(
        """
{
  "audience": {"sessions_7d": 3300, "waft_7d": 710, "returning_user_rate_pct": 31.2},
  "pipeline": {"backlinks_dr30_7d": 6}
}
""".strip(),
        encoding="utf-8",
    )
    (sources_dir / "finance.json").write_text(
        """
{
  "revenue": {"total_mrr_usd": 980, "affiliate_usd_7d": 430, "gross_margin_pct": 73.5},
  "ops": {"hours_invested_7d": 4, "direct_costs_usd_7d": 30, "quantified_value_usd_7d": 520}
}
""".strip(),
        encoding="utf-8",
    )
    phase2_payload = _base_phase2_payload()

    blocks = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    block = blocks[0]

    assert block["audience"]["sessions_7d"] == 3300
    assert block["revenue"]["total_mrr_usd"] == pytest.approx(980.0)
    assert block["pipeline"]["backlinks_dr30_7d"] == 6
    assert block["operations"]["value_delta_usd"] == pytest.approx(350.0)
    assert block["ingestion"]["source_present"] is True
    assert len(block["ingestion"]["source_files_used"]) >= 2


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
        "property_department_briefs": [
            {
                "property_name": "FreeTraderHub",
                "product_wordmark": "PROP COCKPIT",
                "departments": {
                    "finance": {
                        "status": "GREEN",
                        "score": 100,
                        "audience": "Finance + Commercial",
                        "headline": "value_delta=$+205.00",
                        "signals": ["on plan"],
                        "proposal": "Reinvest winners.",
                    },
                    "marketing": {
                        "status": "AMBER",
                        "score": 60,
                        "audience": "Marketing + Growth",
                        "headline": "sessions_7d=1200",
                        "signals": ["WAFT below green target"],
                        "proposal": "Improve targeting.",
                    },
                    "product": {
                        "status": "GREEN",
                        "score": 100,
                        "audience": "Product + UX",
                        "headline": "completion=62.3%",
                        "signals": ["on plan"],
                        "proposal": "Scale flows.",
                    },
                    "operations": {
                        "status": "GREEN",
                        "score": 100,
                        "audience": "Operations + Content Studio",
                        "headline": "drafts_pending=6",
                        "signals": ["on plan"],
                        "proposal": "Keep cadence.",
                    },
                },
                "md_overall": {
                    "status": "AMBER",
                    "score": 90,
                    "audience": "Managing Director / Holding Board",
                    "strategic_direction": "Resolve amber bottlenecks and concentrate resources on highest-yield levers.",
                    "focus_next_7d": ["Marketing: Improve targeting."],
                },
            }
        ],
        "divisions": [],
    }

    markdown = phase3_holding._build_phase3_markdown(payload)

    assert "## Property P&L Blocks" in markdown
    assert "### FreeTraderHub (PROP COCKPIT)" in markdown
    assert "Value Delta (7d): $+205.00" in markdown
    assert "R12 Counter: 0/4" in markdown
    assert "## Property Department Briefs" in markdown
    assert "Finance: [GREEN]" in markdown
    assert "MD Overall: [AMBER]" in markdown


def test_score_company_uses_property_scoped_kpis_for_website_only(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    config["phase3"]["baseline_state_file"] = str(tmp_path / "phase3_company_baseline.json")
    phase2_payload = _base_phase2_payload()
    phase2_payload["generated_at_utc"] = "2026-04-22T00:00:00+00:00"
    phase2_payload["base_summary"] = {"pnl_total": 100.0, "websites_total": 1, "websites_up": 1}
    phase2_payload["warnings"] = []
    phase2_payload["base_alerts"] = []
    phase2_payload["bots"] = [{"report_payload": {"max_drawdown_pct": 99.0}}]

    blocks = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )
    scorecard = phase3_holding._score_company(
        config=config,
        phase2_payload=phase2_payload,
        targets={},
        property_pnl_blocks=blocks,
    )
    metrics = [str(item.get("metric")) for item in scorecard.get("items", []) if isinstance(item, dict)]

    assert "Max drawdown" not in metrics
    assert "Monthly PnL growth" not in metrics
    assert "Property value delta (7d)" in metrics
    assert "Property forecast attainment" in metrics


def test_build_property_department_briefs_exposes_audience_scored_views(tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    phase2_payload = _base_phase2_payload()
    blocks = phase3_holding._build_property_pnl_blocks(
        config=config,
        phase2_payload=phase2_payload,
        generated_at=datetime(2026, 4, 22, tzinfo=timezone.utc),
    )

    briefs = phase3_holding._build_property_department_briefs(config=config, property_blocks=blocks)

    assert len(briefs) == 1
    brief = briefs[0]
    departments = brief["departments"]
    assert departments["finance"]["audience"] == "Finance + Commercial"
    assert departments["marketing"]["audience"] == "Marketing + Growth"
    assert departments["product"]["audience"] == "Product + UX"
    assert departments["operations"]["audience"] == "Operations + Content Studio"
    assert 0 <= int(brief["md_overall"]["score"]) <= 100
    assert brief["md_overall"]["audience"] == "Managing Director / Holding Board"


def test_run_phase3_holding_includes_property_pnl_blocks_and_markdown(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = _base_config(tmp_path)
    phase2_payload = _base_phase2_payload()
    captured: dict[str, str] = {}

    monkeypatch.setattr(phase3_holding, "run_phase2_divisions", lambda config, division, force: phase2_payload)
    monkeypatch.setattr(phase3_holding, "_load_targets", lambda config: {})
    monkeypatch.setattr(
        phase3_holding,
        "_score_company",
        lambda **kwargs: {"goal": "Goal", "desired_outcome": "Outcome", "status": "GREEN", "items": [], "actions": []},
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
    assert len(result["property_department_briefs"]) == 1
    assert result["property_department_briefs"][0]["property_id"] == "freetraderhub"
    assert Path(result["property_kpi_history_file"]).exists()
    assert "## Property P&L Blocks" in captured["markdown"]
    assert "## Property Department Briefs" in captured["markdown"]

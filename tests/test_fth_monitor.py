import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import fth_monitor  # noqa: E402


def test_collect_fth_kpis_reads_manual_affiliate_values(monkeypatch):
    monkeypatch.delenv("UMAMI_BASE_URL", raising=False)
    monkeypatch.delenv("UMAMI_WEBSITE_ID", raising=False)
    monkeypatch.setenv("FTH_EMAIL_LIST_SIZE", "41")
    monkeypatch.setenv("FTH_AFFILIATE_CLICKS_7D", "18")
    monkeypatch.setenv("FTH_FTMO_AFFILIATE_CLICKS_7D", "11")
    monkeypatch.setenv("FTH_FUNDEDNEXT_AFFILIATE_CLICKS_7D", "7")
    monkeypatch.setenv("FTH_AFFILIATE_USD_7D", "22.50")
    monkeypatch.setenv("FTH_AFFILIATE_MRR_USD", "90")
    monkeypatch.setenv("FTH_TOP_PARTNER", "FTMO")

    kpis = fth_monitor.collect_fth_kpis(days=7)

    assert kpis["sessions_7d"] is None
    assert kpis["email_list_size"] == 41
    assert kpis["affiliate_clicks_7d"] == 18
    assert kpis["ftmo_affiliate_clicks_7d"] == 11
    assert kpis["fundednext_affiliate_clicks_7d"] == 7
    assert kpis["affiliate_usd_7d"] == 22.5
    assert kpis["affiliate_mrr_usd"] == 90.0
    assert kpis["top_partner"] == "FTMO"


def test_ingest_merges_manual_values_into_shared_metric_source(tmp_path, monkeypatch):
    source_dir = tmp_path / "state" / "property_metrics" / "freetraderhub"
    source_dir.mkdir(parents=True)
    source = source_dir / "shared.json"
    source.write_text(
        json.dumps(
            {
                "tracking": {
                    "audience": {"sessions_7d": 10},
                    "revenue": {"total_mrr_usd": 150.0},
                    "movers": {"biggest_risk": "manual feed"},
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(fth_monitor, "ROOT", tmp_path)

    result = fth_monitor._ingest(
        {
            "sessions_7d": 25,
            "email_list_size": 41,
            "affiliate_clicks_7d": 18,
            "ftmo_affiliate_clicks_7d": 11,
            "fundednext_affiliate_clicks_7d": 7,
            "affiliate_usd_7d": 22.5,
            "affiliate_mrr_usd": 90.0,
            "top_partner": "FTMO",
        },
        tmp_path / "config" / "projects.yaml",
    )

    payload = json.loads(source.read_text(encoding="utf-8"))

    assert result["ok"] is True
    assert payload["tracking"]["audience"]["sessions_7d"] == 25
    assert payload["tracking"]["audience"]["email_list_size"] == 41
    assert payload["tracking"]["revenue"]["total_mrr_usd"] == 150.0
    assert payload["tracking"]["revenue"]["affiliate_usd_7d"] == 22.5
    assert payload["tracking"]["revenue"]["affiliate_mrr_usd"] == 90.0
    assert payload["tracking"]["revenue"]["top_partner"] == "FTMO"
    assert payload["tracking"]["revenue"]["affiliate_clicks"] == {
        "total_7d": 18,
        "ftmo_7d": 11,
        "fundednext_7d": 7,
    }
    assert payload["tracking"]["movers"]["biggest_risk"] == "manual feed"
    assert payload["source"] == "fth_monitor_manual_and_umami"

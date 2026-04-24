from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import phase2_crews  # noqa: E402


def test_score_websites_scopes_to_operating_properties_only() -> None:
    config = {
        "property_charters": {
            "freetraderhub": {
                "charter": {"version": "v1", "property_type": "website"},
            },
            "freeghosttools": {
                "charter": {"version": "v0-stub", "property_type": "website"},
            },
        },
        "phase2": {
            "targets": {
                "websites": {
                    "snapshot_uptime_ratio_min": 1.0,
                    "max_latency_ms": 500,
                    "max_sitemap_age_days": 14,
                    "max_research_report_age_days": 8,
                }
            }
        },
    }
    brief_payload = {
        "generated_at_utc": "2026-04-24T00:00:00+00:00",
        "websites": [
            {
                "id": "freeghosttools",
                "ok": True,
                "latency_ms": 200,
                "network_diag": {"dns_ok": True, "tcp_443_ok": True},
                "local_diag": {"sitemap_latest_lastmod": "2026-01-01T00:00:00+00:00"},
            },
            {
                "id": "freetraderhub_website",
                "ok": True,
                "latency_ms": 210,
                "network_diag": {"dns_ok": True, "tcp_443_ok": True},
                "local_diag": {},
            },
            {
                "id": "freetraderhub_research",
                "ok": True,
                "latency_ms": 230,
                "network_diag": {"dns_ok": True, "tcp_443_ok": True},
                "local_diag": {"local_reports_latest_mtime_utc": "2026-04-22T00:00:00+00:00"},
            },
        ],
    }

    scorecard = phase2_crews._score_websites(brief_payload=brief_payload, config=config)
    metrics = [str(item.get("metric")) for item in scorecard.get("items", []) if isinstance(item, dict)]

    assert "FreeGhostTools sitemap freshness" not in metrics
    assert "FreeTraderHub research brief freshness" in metrics
    assert scorecard.get("status") == "GREEN"


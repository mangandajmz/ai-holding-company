"""FreeTraderHub revenue & traffic KPI monitor.

Pulls live metrics from:
  - Umami Analytics (visitor counts)
  - Loops (email list size)

Writes actuals into state/property_metric_feed.json via
phase3_holding.ingest_property_metric_values.

Required env vars (all optional — missing vars → None for that metric):
  UMAMI_BASE_URL      e.g. https://analytics.umami.is  (no trailing slash)
  UMAMI_API_KEY       Bearer token from Umami Settings → API Keys
  UMAMI_WEBSITE_ID    UUID shown in Umami website settings
  LOOPS_API_KEY       API key from Loops Settings → API

Usage:
  python scripts/fth_monitor.py            # fetch + ingest + print summary
  python scripts/fth_monitor.py --dry-run  # fetch only, print, no write
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib import error, request
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LOGGER = logging.getLogger("fth_monitor")


# ---------------------------------------------------------------------------
# Umami helpers
# ---------------------------------------------------------------------------

def _umami_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }


def fetch_umami_stats(
    base_url: str,
    api_key: str,
    website_id: str,
    days: int = 30,
    timeout_sec: int = 15,
) -> dict[str, int | None]:
    """Return visitor/pageview counts for the last *days* days.

    Returns dict with keys: visitors, pageviews, visits, bounces.
    Any key is None if the API call fails.
    """
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - days * 86_400 * 1000
    params = urlencode({"startAt": start_ms, "endAt": end_ms})
    url = f"{base_url.rstrip('/')}/api/websites/{website_id}/stats?{params}"
    headers = _umami_headers(api_key)
    try:
        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("Umami stats fetch failed: %s", exc)
        return {"visitors": None, "pageviews": None, "visits": None, "bounces": None}

    def _val(key: str) -> int | None:
        item = data.get(key)
        if isinstance(item, dict):
            v = item.get("value")
        else:
            v = item
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    return {
        "visitors": _val("visitors"),
        "pageviews": _val("pageviews"),
        "visits": _val("visits"),
        "bounces": _val("bounces"),
    }


# ---------------------------------------------------------------------------
# Loops helpers
# ---------------------------------------------------------------------------

def fetch_loops_list_size(
    api_key: str,
    timeout_sec: int = 15,
) -> int | None:
    """Return total subscriber count from Loops.

    Loops v1 /contacts endpoint returns an array; we read the X-Total-Count
    header if present, otherwise count the first page (max 100 results).
    For lists under 100 this is exact; for larger lists it's a lower bound
    until Loops exposes a direct count endpoint.
    """
    url = "https://app.loops.so/api/v1/contacts"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }
    try:
        req = request.Request(url, headers=headers)
        with request.urlopen(req, timeout=timeout_sec) as resp:
            raw_total = resp.headers.get("X-Total-Count") or resp.headers.get("x-total-count")
            body = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("Loops fetch failed: %s", exc)
        return None

    if raw_total is not None:
        try:
            return int(raw_total)
        except (TypeError, ValueError):
            pass

    # Fall back to counting what we received
    if isinstance(body, list):
        return len(body)
    # Some Loops endpoints wrap in {"contacts": [...]}
    if isinstance(body, dict):
        contacts = body.get("contacts") or body.get("data") or []
        if isinstance(contacts, list):
            return len(contacts)

    return None


# ---------------------------------------------------------------------------
# Main collection entry point
# ---------------------------------------------------------------------------

def collect_fth_kpis(days: int = 30) -> dict[str, object]:
    """Collect all FTH KPIs from configured APIs.

    Returns a flat dict suitable for ingest_property_metric_values.
    Keys with None values indicate the API was not configured or failed.
    """
    kpis: dict[str, object] = {}

    # --- Umami ---
    umami_base = os.environ.get("UMAMI_BASE_URL", "").strip()
    umami_key = os.environ.get("UMAMI_API_KEY", "").strip()
    umami_site = os.environ.get("UMAMI_WEBSITE_ID", "").strip()

    if umami_base and umami_key and umami_site:
        LOGGER.info("Fetching Umami stats for website %s (last %d days)…", umami_site, days)
        umami = fetch_umami_stats(umami_base, umami_key, umami_site, days=days)
        kpis["sessions_30d"] = umami.get("visits")
        kpis["visitors_30d"] = umami.get("visitors")
        kpis["pageviews_30d"] = umami.get("pageviews")
        # Map visits to sessions_7d proxy (will be accurate once 7d endpoint is added)
        # For now expose 30d figure — morning brief will label it correctly.
    else:
        LOGGER.info("Umami not configured (UMAMI_BASE_URL / UMAMI_API_KEY / UMAMI_WEBSITE_ID missing).")
        kpis["sessions_30d"] = None
        kpis["visitors_30d"] = None
        kpis["pageviews_30d"] = None

    # --- Loops ---
    loops_key = os.environ.get("LOOPS_API_KEY", "").strip()

    if loops_key:
        LOGGER.info("Fetching Loops email list size…")
        kpis["email_list_size"] = fetch_loops_list_size(loops_key)
    else:
        LOGGER.info("Loops not configured (LOOPS_API_KEY missing).")
        kpis["email_list_size"] = None

    return kpis


def _ingest(kpis: dict[str, object], config_path: Path) -> dict[str, object]:
    """Write KPIs into property_metric_feed.json via phase3_holding."""
    try:
        from phase3_holding import ingest_property_metric_values  # noqa: PLC0415
        from monitoring import load_config  # noqa: PLC0415
    except ImportError as exc:
        return {"ok": False, "error": str(exc)}

    config = load_config(config_path)
    result = ingest_property_metric_values(
        config=config,
        property_slug="freetraderhub",
        metric_values=kpis,
        source="fth_monitor_live",
    )
    return result if isinstance(result, dict) else {"ok": True}


def build_brief_line(kpis: dict[str, object]) -> str:
    """Return a one-line FTH KPI summary for the morning brief.

    Example:
      📊 FTH — 1,240 visitors/30d | 38 email subs | MRR $0
    """
    parts = []

    visitors = kpis.get("visitors_30d")
    if visitors is not None:
        parts.append(f"{visitors:,} visitors/30d")

    email = kpis.get("email_list_size")
    if email is not None:
        parts.append(f"{email} email subs")

    if not parts:
        parts.append("no live data yet — configure UMAMI_BASE_URL + LOOPS_API_KEY")

    return "📊 FTH — " + " | ".join(parts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> None:
    # Ensure UTF-8 output on Windows so emoji don't crash the console
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="FreeTraderHub KPI monitor.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and print but do not write to feed.")
    parser.add_argument("--days", type=int, default=30, help="Lookback window for Umami (default: 30).")
    parser.add_argument("--config", default=str(ROOT / "config" / "projects.yaml"), help="Path to projects.yaml.")
    args = parser.parse_args()

    # Load .env if present (for local runs outside Task Scheduler)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

    kpis = collect_fth_kpis(days=args.days)

    print("\n=== FTH KPIs ===")
    for k, v in kpis.items():
        print(f"  {k}: {v}")
    print()
    print(build_brief_line(kpis))
    print()

    if not args.dry_run:
        result = _ingest(kpis, Path(args.config))
        if result.get("ok") is False:
            print(f"⚠ Ingest failed: {result.get('error')}")
        else:
            print("✓ Written to property_metric_feed.json")
    else:
        print("(dry-run — not written)")


if __name__ == "__main__":
    _main()

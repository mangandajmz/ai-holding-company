"""FreeTraderHub revenue & traffic KPI monitor.

Pulls live metrics from:
  - Umami Analytics (visitor counts) — automatic via API
  - Email list size — manual env var (Loops has no count API)

Writes actuals into state/property_metric_feed.json via
phase3_holding.ingest_property_metric_values.

Umami auth — two options (first one found wins):
  Option A — username/password (works for Cloud and self-hosted):
    UMAMI_BASE_URL   e.g. https://analytics.umami.is
    UMAMI_USERNAME   your Umami login email/username
    UMAMI_PASSWORD   your Umami login password
    UMAMI_WEBSITE_ID UUID shown in Umami website settings

  Option B — static API key (Umami Cloud paid plans only):
    UMAMI_BASE_URL
    UMAMI_API_KEY    static token from Umami Settings → API Keys
    UMAMI_WEBSITE_ID

Email list (Loops has no bulk-count API — update manually):
  FTH_EMAIL_LIST_SIZE   current subscriber count from Loops dashboard
                        Update this number whenever you check Loops.

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

def _umami_get_token(
    base_url: str,
    username: str,
    password: str,
    timeout_sec: int = 15,
) -> str | None:
    """Exchange username+password for a Bearer token via POST /api/auth/login."""
    url = f"{base_url.rstrip('/')}/api/auth/login"
    payload = json.dumps({"username": username, "password": password}).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        token = data.get("token")
        return str(token) if token else None
    except (error.URLError, json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("Umami login failed: %s", exc)
        return None


def _umami_resolve_token(base_url: str, timeout_sec: int = 15) -> str | None:
    """Return a valid Bearer token using whichever auth method is configured.

    Priority:
      1. UMAMI_API_KEY  — static key (Cloud paid plans)
      2. UMAMI_USERNAME + UMAMI_PASSWORD — login exchange (all plans)
    """
    static_key = os.environ.get("UMAMI_API_KEY", "").strip()
    if static_key and not static_key.startswith("REPLACE_"):
        return static_key

    username = os.environ.get("UMAMI_USERNAME", "").strip()
    password = os.environ.get("UMAMI_PASSWORD", "").strip()
    if username and password:
        LOGGER.info("Umami: authenticating with username/password…")
        return _umami_get_token(base_url, username, password, timeout_sec=timeout_sec)

    return None


def fetch_umami_stats(
    base_url: str,
    token: str,
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
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
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
    umami_site = os.environ.get("UMAMI_WEBSITE_ID", "").strip()

    if umami_base and umami_site and not umami_site.startswith("REPLACE_"):
        token = _umami_resolve_token(umami_base)
        if token:
            LOGGER.info("Fetching Umami stats for website %s (last %d days)…", umami_site, days)
            umami = fetch_umami_stats(umami_base, token, umami_site, days=days)
            kpis["sessions_30d"] = umami.get("visits")
            kpis["visitors_30d"] = umami.get("visitors")
            kpis["pageviews_30d"] = umami.get("pageviews")
        else:
            LOGGER.warning("Umami: could not obtain token — check UMAMI_USERNAME/UMAMI_PASSWORD or UMAMI_API_KEY.")
            kpis["sessions_30d"] = None
            kpis["visitors_30d"] = None
            kpis["pageviews_30d"] = None
    else:
        LOGGER.info("Umami not configured (set UMAMI_BASE_URL + UMAMI_WEBSITE_ID + credentials).")
        kpis["sessions_30d"] = None
        kpis["visitors_30d"] = None
        kpis["pageviews_30d"] = None

    # --- Email list size (manual — Loops has no bulk-count API) ---
    # Update FTH_EMAIL_LIST_SIZE in .env whenever you check the Loops dashboard.
    raw_list_size = os.environ.get("FTH_EMAIL_LIST_SIZE", "").strip()
    if raw_list_size and not raw_list_size.startswith("REPLACE_"):
        try:
            kpis["email_list_size"] = int(raw_list_size)
            LOGGER.info("Email list size from env: %s", kpis["email_list_size"])
        except ValueError:
            LOGGER.warning("FTH_EMAIL_LIST_SIZE is not a valid integer: %s", raw_list_size)
            kpis["email_list_size"] = None
    else:
        LOGGER.info("Email list size not set — add FTH_EMAIL_LIST_SIZE=<count> to .env.")
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

"""FreeTraderHub revenue & traffic KPI monitor.

Pulls live metrics from:
  - Umami Analytics (visitor counts) — automatic via API
  - Email list size — manual env var (Loops has no count API)
  - Affiliate dashboard values — manual env vars until partner APIs are justified

Writes actuals into state/property_metrics/freetraderhub/shared.json, which
Phase 3 already ingests into state/property_metric_feed.json during heartbeats.

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

Affiliate dashboards (manual weekly refresh):
  FTH_AFFILIATE_CLICKS_7D             total affiliate clicks
  FTH_FTMO_AFFILIATE_CLICKS_7D        FTMO affiliate clicks
  FTH_FUNDEDNEXT_AFFILIATE_CLICKS_7D  FundedNext affiliate clicks
  FTH_AFFILIATE_USD_7D                affiliate commission earned this week
  FTH_AFFILIATE_MRR_USD               affiliate monthly run-rate estimate
  FTH_TOP_PARTNER                     top partner by clicks/revenue

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

def _read_int_env(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw or raw.startswith("REPLACE_"):
        return None
    try:
        return int(raw)
    except ValueError:
        LOGGER.warning("%s is not a valid integer: %s", name, raw)
        return None


def _read_float_env(name: str) -> float | None:
    raw = os.environ.get(name, "").strip()
    if not raw or raw.startswith("REPLACE_"):
        return None
    try:
        return float(raw)
    except ValueError:
        LOGGER.warning("%s is not a valid number: %s", name, raw)
        return None


def collect_fth_kpis(days: int = 7) -> dict[str, object]:
    """Collect all FTH KPIs from configured APIs.

    Returns a flat dict suitable for the local FTH metric source writer.
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
            kpis[f"sessions_{days}d"] = umami.get("visits")
            kpis[f"visitors_{days}d"] = umami.get("visitors")
            kpis[f"pageviews_{days}d"] = umami.get("pageviews")
        else:
            LOGGER.warning("Umami: could not obtain token — check UMAMI_USERNAME/UMAMI_PASSWORD or UMAMI_API_KEY.")
            kpis[f"sessions_{days}d"] = None
            kpis[f"visitors_{days}d"] = None
            kpis[f"pageviews_{days}d"] = None
    else:
        LOGGER.info("Umami not configured (set UMAMI_BASE_URL + UMAMI_WEBSITE_ID + credentials).")
        kpis[f"sessions_{days}d"] = None
        kpis[f"visitors_{days}d"] = None
        kpis[f"pageviews_{days}d"] = None

    # --- Email list size (manual — Loops has no bulk-count API) ---
    # Update FTH_EMAIL_LIST_SIZE in .env whenever you check the Loops dashboard.
    kpis["email_list_size"] = _read_int_env("FTH_EMAIL_LIST_SIZE")
    if kpis["email_list_size"] is None:
        LOGGER.info("Email list size not set — add FTH_EMAIL_LIST_SIZE=<count> to .env.")
    else:
        LOGGER.info("Email list size from env: %s", kpis["email_list_size"])

    # --- Affiliate dashboards (manual until partner APIs are worth wiring) ---
    kpis["affiliate_clicks_7d"] = _read_int_env("FTH_AFFILIATE_CLICKS_7D")
    kpis["ftmo_affiliate_clicks_7d"] = _read_int_env("FTH_FTMO_AFFILIATE_CLICKS_7D")
    kpis["fundednext_affiliate_clicks_7d"] = _read_int_env("FTH_FUNDEDNEXT_AFFILIATE_CLICKS_7D")
    kpis["affiliate_usd_7d"] = _read_float_env("FTH_AFFILIATE_USD_7D")
    kpis["affiliate_mrr_usd"] = _read_float_env("FTH_AFFILIATE_MRR_USD")
    top_partner = os.environ.get("FTH_TOP_PARTNER", "").strip()
    kpis["top_partner"] = top_partner if top_partner and not top_partner.startswith("REPLACE_") else None

    return kpis


def _ingest(kpis: dict[str, object], config_path: Path) -> dict[str, object]:
    """Write KPIs into the FTH source JSON consumed by Phase 3."""
    _ = config_path
    source_path = ROOT / "state" / "property_metrics" / "freetraderhub" / "shared.json"
    source_path.parent.mkdir(parents=True, exist_ok=True)

    if source_path.exists():
        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload = {}
    else:
        payload = {}

    tracking = payload.setdefault("tracking", {})
    audience = tracking.setdefault("audience", {})
    revenue = tracking.setdefault("revenue", {})
    movers = tracking.setdefault("movers", {})

    for key in ["sessions_7d", "visitors_7d", "pageviews_7d", "email_list_size"]:
        if kpis.get(key) is not None:
            audience[key] = kpis[key]

    for key in ["affiliate_usd_7d", "affiliate_mrr_usd"]:
        if kpis.get(key) is not None:
            revenue[key] = kpis[key]

    if kpis.get("top_partner") is not None:
        revenue["top_partner"] = kpis["top_partner"]

    affiliate_clicks = {
        "total_7d": kpis.get("affiliate_clicks_7d"),
        "ftmo_7d": kpis.get("ftmo_affiliate_clicks_7d"),
        "fundednext_7d": kpis.get("fundednext_affiliate_clicks_7d"),
    }
    revenue["affiliate_clicks"] = {
        key: value for key, value in affiliate_clicks.items() if value is not None
    } or revenue.get("affiliate_clicks", {})

    if any(value is not None for value in affiliate_clicks.values()):
        movers["top_growth_lever"] = (
            "Affiliate links are live; measure clicks by firm and convert the best-performing CTA into the next growth test."
        )

    payload["updated_at_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    payload["source"] = "fth_monitor_manual_and_umami"
    source_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(source_path)}


def build_brief_line(kpis: dict[str, object]) -> str:
    """Return a one-line FTH KPI summary for the morning brief.

    Example:
      📊 FTH — 1,240 visits/7d | 38 email subs | affiliate $12
    """
    parts = []

    sessions = kpis.get("sessions_7d")
    if sessions is not None:
        parts.append(f"{sessions:,} visits/7d")

    email = kpis.get("email_list_size")
    if email is not None:
        parts.append(f"{email} email subs")

    affiliate = kpis.get("affiliate_usd_7d")
    if affiliate is not None:
        parts.append(f"affiliate ${float(affiliate):,.2f}/7d")

    if not parts:
        parts.append("no live data yet — configure Umami and manual KPI env vars")

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
    parser.add_argument("--days", type=int, default=7, help="Lookback window for Umami (default: 7).")
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
            print(f"✓ Written to {result.get('path', 'FTH metric source')}")
    else:
        print("(dry-run — not written)")


if __name__ == "__main__":
    _main()

"""Prop firm rule change monitor.

Scrapes FTMO, FundedNext, and The5ers rule/challenge pages daily.
Diffs HTML content against yesterday's snapshot.
When changes are detected, sends a Telegram alert with a plain-English
summary generated via the free LLM routing client.

Snapshots stored in: state/rule_snapshots/
Schedule via Task Scheduler to run daily (recommended: 06:00 before morning brief).

Usage:
  python scripts/prop_rule_monitor.py           # check all firms
  python scripts/prop_rule_monitor.py --dry-run # diff only, no Telegram alert
  python scripts/prop_rule_monitor.py --firm ftmo  # single firm
  python scripts/prop_rule_monitor.py --force   # alert even if no changes (test)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request
from urllib.request import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

LOGGER = logging.getLogger("prop_rule_monitor")
SNAPSHOTS_DIR = ROOT / "state" / "rule_snapshots"

# ---------------------------------------------------------------------------
# Firm definitions — pages that contain rules/challenge conditions
# ---------------------------------------------------------------------------

FIRMS: dict[str, dict[str, Any]] = {
    "ftmo": {
        "name": "FTMO",
        "pages": [
            {
                "label": "Trading Objectives",
                "url": "https://ftmo.com/en/trading-objectives/",
            },
            {
                "label": "FAQ Rules",
                "url": "https://ftmo.com/en/faq/",
            },
        ],
    },
    "fundednext": {
        "name": "FundedNext",
        "pages": [
            {
                "label": "Help Centre Rules",
                "url": "https://help.fundednext.com/en/",
            },
            {
                "label": "Futures Program",
                "url": "https://fundednext.com/futures",
            },
        ],
    },
    "the5ers": {
        "name": "The5ers",
        "pages": [
            {
                "label": "Hyper Growth Program",
                "url": "https://the5ers.com/hyper-growth/",
            },
            {
                "label": "High Stakes Program",
                "url": "https://the5ers.com/high-stakes/",
            },
            {
                "label": "Help Centre",
                "url": "https://help.the5ers.com",
            },
        ],
    },
}

from typing import Any  # noqa: E402 (after FIRMS so it's importable above)


# ---------------------------------------------------------------------------
# Snapshot helpers
# ---------------------------------------------------------------------------

def _snapshot_path(firm_id: str, label: str) -> Path:
    safe_label = re.sub(r"[^\w]", "_", label.lower())
    return SNAPSHOTS_DIR / f"{firm_id}_{safe_label}.json"


def _load_snapshot(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_snapshot(path: Path, data: dict[str, Any]) -> None:
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Page fetching + normalisation
# ---------------------------------------------------------------------------

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch_page(url: str, timeout: int = 20) -> str | None:
    """Fetch a page and return normalised text content."""
    try:
        req = Request(url, headers=_HEADERS)
        with request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except (error.URLError, OSError) as exc:
        LOGGER.warning("Fetch failed for %s: %s", url, exc)
        return None

    # Strip scripts, styles, nav, footer — keep rule-relevant text
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<nav[^>]*>.*?</nav>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Diff helpers
# ---------------------------------------------------------------------------

def _extract_changed_sentences(old: str, new: str, context: int = 2) -> list[str]:
    """Return sentences that appear in new but not old (additions/changes)."""
    old_sentences = set(re.split(r"(?<=[.!?])\s+", old))
    new_sentences = re.split(r"(?<=[.!?])\s+", new)

    changed = []
    for i, sent in enumerate(new_sentences):
        sent_stripped = sent.strip()
        if len(sent_stripped) < 20:
            continue
        if sent_stripped not in old_sentences:
            # Include surrounding context
            start = max(0, i - context)
            end = min(len(new_sentences), i + context + 1)
            snippet = " ".join(s.strip() for s in new_sentences[start:end] if s.strip())
            if snippet not in changed:
                changed.append(snippet[:400])

    return changed[:10]  # cap at 10 snippets to avoid huge alerts


def _summarise_changes(firm_name: str, page_label: str, snippets: list[str]) -> str:
    """Use free LLM to produce plain-English summary of detected changes."""
    try:
        from free_llm_client import quick  # noqa: PLC0415
    except ImportError:
        return f"Rule page changed ({len(snippets)} section(s) differ from last snapshot)."

    snippet_text = "\n\n".join(f"- {s}" for s in snippets[:5])
    prompt = (
        f"You are a prop firm rule analyst. The following text snippets were detected "
        f"as NEW or CHANGED on the {firm_name} '{page_label}' page compared to "
        f"yesterday's snapshot. Write a 2-3 sentence plain-English summary for a "
        f"trader explaining what appears to have changed and what they should check. "
        f"Be specific if the snippet mentions numbers (drawdown %, profit targets, "
        f"fees). If the change looks cosmetic (navigation, ads, dates), say so.\n\n"
        f"Changed snippets:\n{snippet_text}"
    )
    try:
        return quick(prompt, task="summarise", max_tokens=200)
    except RuntimeError as exc:
        LOGGER.warning("LLM summarise failed: %s", exc)
        return f"Rule page changed ({len(snippets)} section(s) differ). Check {firm_name} {page_label} manually."


# ---------------------------------------------------------------------------
# Telegram alert
# ---------------------------------------------------------------------------

def _send_telegram_alert(message: str) -> bool:
    """Send alert via Telegram bot. Returns True on success."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "").strip()

    if not bot_token or not chat_id:
        LOGGER.warning("Telegram not configured — alert not sent.")
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "HTML"}).encode("utf-8")
    req = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        return result.get("ok", False)
    except (error.URLError, json.JSONDecodeError, OSError) as exc:
        LOGGER.warning("Telegram send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Main check logic
# ---------------------------------------------------------------------------

def check_firm(firm_id: str, dry_run: bool = False, force: bool = False) -> list[dict[str, Any]]:
    """Check one firm for rule changes. Returns list of change dicts."""
    firm = FIRMS[firm_id]
    changes_found: list[dict[str, Any]] = []

    for page in firm["pages"]:
        label = page["label"]
        url = page["url"]
        snap_path = _snapshot_path(firm_id, label)
        old_snap = _load_snapshot(snap_path)

        LOGGER.info("Checking %s — %s (%s)", firm["name"], label, url)
        new_text = _fetch_page(url)

        if new_text is None:
            LOGGER.warning("Could not fetch %s %s — skipping", firm["name"], label)
            continue

        new_hash = _content_hash(new_text)
        old_hash = old_snap.get("hash", "")
        old_text = old_snap.get("text", "")

        changed = (new_hash != old_hash) or force

        # Always update snapshot
        if not dry_run:
            _save_snapshot(snap_path, {
                "hash": new_hash,
                "text": new_text,
                "url": url,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "firm": firm["name"],
                "label": label,
            })

        if changed and old_hash:
            snippets = _extract_changed_sentences(old_text, new_text)
            summary = _summarise_changes(firm["name"], label, snippets) if snippets else (
                "Page hash changed but no specific sentence differences detected — possibly formatting/ads change."
            )
            changes_found.append({
                "firm": firm["name"],
                "firm_id": firm_id,
                "label": label,
                "url": url,
                "summary": summary,
                "snippet_count": len(snippets),
                "old_hash": old_hash,
                "new_hash": new_hash,
            })
            LOGGER.info("CHANGE DETECTED: %s %s", firm["name"], label)
        elif not old_hash:
            LOGGER.info("First snapshot saved for %s %s", firm["name"], label)
        else:
            LOGGER.info("No change: %s %s", firm["name"], label)

        time.sleep(2)  # be polite to the servers

    return changes_found


def check_all_firms(
    firm_ids: list[str] | None = None,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Check all firms (or a subset). Returns summary dict."""
    targets = firm_ids or list(FIRMS.keys())
    all_changes: list[dict[str, Any]] = []

    for firm_id in targets:
        if firm_id not in FIRMS:
            LOGGER.warning("Unknown firm id: %s", firm_id)
            continue
        changes = check_firm(firm_id, dry_run=dry_run, force=force)
        all_changes.extend(changes)

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "firms_checked": targets,
        "changes": all_changes,
        "change_count": len(all_changes),
    }


def build_alert_message(result: dict[str, Any]) -> str:
    """Format Telegram alert for detected changes."""
    changes = result["changes"]
    if not changes:
        return ""

    lines = [f"⚠️ <b>Prop Firm Rule Change Detected</b>"]
    lines.append(f"Checked: {result['checked_at'][:10]}\n")

    for ch in changes:
        lines.append(f"🏢 <b>{ch['firm']}</b> — {ch['label']}")
        lines.append(f"🔗 {ch['url']}")
        lines.append(f"📝 {ch['summary']}")
        lines.append("")

    lines.append("→ Review changes and update the FTH rule library if confirmed.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    parser = argparse.ArgumentParser(description="Prop firm rule change monitor.")
    parser.add_argument("--dry-run", action="store_true", help="Diff only — do not save snapshots or send alerts.")
    parser.add_argument("--force", action="store_true", help="Send alert even if no changes (for testing).")
    parser.add_argument("--firm", default="", help="Check a single firm: ftmo, fundednext, the5ers")
    args = parser.parse_args()

    # Load .env
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

    firm_ids = [args.firm] if args.firm else None
    result = check_all_firms(firm_ids=firm_ids, dry_run=args.dry_run, force=args.force)

    print(f"\n=== Rule Monitor Results ===")
    print(f"Firms checked: {', '.join(result['firms_checked'])}")
    print(f"Changes found: {result['change_count']}")

    if result["changes"]:
        for ch in result["changes"]:
            print(f"\n  [{ch['firm']}] {ch['label']}")
            print(f"  {ch['summary']}")

        alert_msg = build_alert_message(result)
        if not args.dry_run:
            sent = _send_telegram_alert(alert_msg)
            print(f"\nTelegram alert sent: {sent}")
        else:
            print(f"\n--- Alert preview (dry-run) ---")
            print(alert_msg)
    else:
        print("No rule changes detected.")


if __name__ == "__main__":
    _main()

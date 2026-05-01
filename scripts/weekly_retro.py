"""Weekly retro generator for AI Holding Company.

Fires Sunday 20:00 America/Vancouver (caught up on next boot if missed).
Summarises the week's division events from state/events.db, formats a
retro report, and sends it to the owner via Telegram.

Usage (called by Windows Task Scheduler):
    python scripts/weekly_retro.py
    python scripts/weekly_retro.py --force     # skip Sunday check, run now
    python scripts/weekly_retro.py --dry-run   # print to stdout, no Telegram

Scheduler note:
    Task Scheduler trigger: Weekly, Sunday, 20:00 local time.
    Action: python scripts/weekly_retro.py
    Missed run detection: the script records last_retro_date in
    state/retro_state.json. On boot, if today >= next_due_date and not yet
    sent this week, the retro runs as a catch-up.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from utils import load_yaml as _load_yaml, now_utc_iso as _utc_now  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [weekly_retro] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("weekly_retro")

DEFAULT_CONFIG = ROOT / "config" / "projects.yaml"
RETRO_STATE_FILE = ROOT / "state" / "retro_state.json"
RETRO_REPORTS_DIR = ROOT / "reports" / "retros"

VANCOUVER_TZ = ZoneInfo("America/Vancouver")
RETRO_WEEKDAY = 6   # Sunday (Monday=0)
RETRO_HOUR = 20


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _load_retro_state() -> dict:
    if not RETRO_STATE_FILE.exists():
        return {}
    try:
        return json.loads(RETRO_STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_retro_state(state: dict) -> None:
    RETRO_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    RETRO_STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _last_sunday(ref: date) -> date:
    """Return the most recent Sunday (or today if today is Sunday)."""
    days_since_sunday = ref.weekday() - RETRO_WEEKDAY
    if days_since_sunday < 0:
        days_since_sunday += 7
    return ref - timedelta(days=days_since_sunday)


def should_run_retro(force: bool = False) -> bool:
    """Return True if the retro should fire now."""
    if force:
        return True
    now_van = datetime.now(VANCOUVER_TZ)
    today = now_van.date()
    current_hour = now_van.hour

    # Must be Sunday at or after 20:00, OR a catch-up scenario
    state = _load_retro_state()
    last_sent_str = state.get("last_retro_date")
    last_sent = date.fromisoformat(last_sent_str) if last_sent_str else None

    # Scheduled: Sunday on or after 20:00
    if today.weekday() == RETRO_WEEKDAY and current_hour >= RETRO_HOUR:
        last_due = _last_sunday(today)
        if last_sent is None or last_sent < last_due:
            return True

    # Catch-up: any day, if last Sunday's retro was not sent
    last_due = _last_sunday(today)
    if last_sent is None or last_sent < last_due:
        return True

    return False


# ---------------------------------------------------------------------------
# Event aggregation from SQLite
# ---------------------------------------------------------------------------

def _collect_week_events() -> list[dict]:
    """Return events from the last 7 days. Returns [] if no DB yet."""
    try:
        import sqlite3  # noqa: PLC0415
        db_path = ROOT / "state" / "events.db"
        if not db_path.exists():
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        conn = sqlite3.connect(str(db_path), timeout=10)
        try:
            rows = conn.execute(
                "SELECT id, ts, division, event_type, severity, payload "
                "FROM events WHERE ts >= ? ORDER BY ts ASC",
                (cutoff,),
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "id": r[0], "ts": r[1], "division": r[2],
                "event_type": r[3], "severity": r[4],
                "payload": json.loads(r[5] or "{}"),
            }
            for r in rows
        ]
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Could not read events.db: %s", exc)
        return []


def _summarise_events(events: list[dict]) -> dict:
    """Aggregate events into retro stats."""
    total = len(events)
    by_division: dict[str, list] = defaultdict(list)
    by_severity: dict[str, int] = defaultdict(int)

    for ev in events:
        by_division[ev["division"]].append(ev)
        by_severity[ev["severity"]] += 1

    division_summaries: dict[str, dict] = {}
    for division, evs in by_division.items():
        red_count = sum(1 for e in evs if e["severity"] == "critical")
        resolved = 0  # count critical → info transitions (simple heuristic)
        severities_by_time = [e["severity"] for e in evs]
        for i in range(1, len(severities_by_time)):
            if severities_by_time[i - 1] == "critical" and severities_by_time[i] == "info":
                resolved += 1
        division_summaries[division] = {
            "total": len(evs),
            "critical": red_count,
            "resolved": resolved,
            "last_severity": evs[-1]["severity"] if evs else "unknown",
        }

    return {
        "total_events": total,
        "by_severity": dict(by_severity),
        "division_summaries": division_summaries,
    }


# ---------------------------------------------------------------------------
# Retro report formatting
# ---------------------------------------------------------------------------

def _format_retro(stats: dict, week_start: date, week_end: date) -> str:
    """Format the retro as a human-readable Telegram message."""
    total = stats.get("total_events", 0)
    by_sev = stats.get("by_severity", {})
    divs = stats.get("division_summaries", {})

    critical_count = by_sev.get("critical", 0)
    warn_count = by_sev.get("warn", 0)
    info_count = by_sev.get("info", 0)

    header = (
        f"📋 Weekly Retro\n"
        f"Week: {week_start.isoformat()} → {week_end.isoformat()}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    event_summary = (
        f"🔢 Events this week: {total}\n"
        f"  🔴 Critical: {critical_count}  🟡 Warn: {warn_count}  🟢 Info: {info_count}\n"
    )

    div_lines: list[str] = []
    for division, summary in sorted(divs.items()):
        last_sev = str(summary.get("last_severity", "?")).upper()
        icon = "🔴" if last_sev == "CRITICAL" else ("🟡" if last_sev == "WARN" else "🟢")
        resolved = summary.get("resolved", 0)
        resolved_note = f" (+{resolved} resolved)" if resolved else ""
        div_lines.append(
            f"  {icon} {division.title()}: {summary.get('critical', 0)} RED events{resolved_note}"
        )

    divs_block = "📊 Division breakdown:\n" + "\n".join(div_lines) if div_lines else ""

    open_issues = ""
    if critical_count > 0:
        open_issues = f"\n⚠️ {critical_count} critical event(s) this week — review RED divisions."

    footer = "\n💬 /brief | /board review | /orchestrator status"

    parts = [header, event_summary]
    if divs_block:
        parts.append(divs_block)
    if open_issues:
        parts.append(open_issues)
    parts.append(footer)

    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_retro(config: dict, dry_run: bool = False) -> str:
    """Generate and optionally send the weekly retro. Returns the retro text."""
    now_van = datetime.now(VANCOUVER_TZ)
    today = now_van.date()
    week_end = today
    week_start = today - timedelta(days=7)

    events = _collect_week_events()
    stats = _summarise_events(events)
    retro_text = _format_retro(stats, week_start=week_start, week_end=week_end)

    # Save to reports/retros/
    RETRO_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    retro_file = RETRO_REPORTS_DIR / f"retro_{today.isoformat()}.txt"
    retro_file.write_text(retro_text, encoding="utf-8")
    logger.info("Retro saved: %s", retro_file)

    if not dry_run:
        try:
            from telegram_bridge import TelegramBridge  # pylint: disable=import-outside-toplevel
            bridge = TelegramBridge(config_path=Path(config.get("_config_path") or DEFAULT_CONFIG))
            if bridge.security_ready and bridge.owner_chat_id:
                bridge.send_message(chat_id=bridge.owner_chat_id, text=retro_text)
                logger.info("Retro sent to Telegram.")
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("Telegram send failed: %s", exc)

    # Record last send date
    state = _load_retro_state()
    state["last_retro_date"] = today.isoformat()
    state["last_retro_utc"] = _utc_now()
    _save_retro_state(state)

    return retro_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate and send weekly retro.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to projects.yaml.")
    parser.add_argument("--force", action="store_true", help="Run regardless of day/time.")
    parser.add_argument("--dry-run", action="store_true", help="Print to stdout, skip Telegram.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = _load_yaml(Path(args.config))
    config["_config_path"] = str(args.config)

    if not should_run_retro(force=args.force):
        logger.info("Retro not due yet. Use --force to override.")
        print(json.dumps({"ok": True, "action": "skipped", "reason": "not_due"}))
        return

    retro_text = run_retro(config=config, dry_run=args.dry_run)
    if args.dry_run:
        sys.stdout.buffer.write((retro_text + "\n").encode("utf-8"))
    else:
        print(json.dumps({"ok": True, "action": "sent", "chars": len(retro_text)}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Fatal: %s", exc)
        sys.exit(1)

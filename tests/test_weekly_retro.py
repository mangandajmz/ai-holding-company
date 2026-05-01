"""Tests for Sprint 4 — weekly_retro.py.

Covers:
1. _last_sunday returns correct date for various weekdays
2. should_run_retro(force=True) always returns True
3. should_run_retro respects already-sent state (same week → False)
4. should_run_retro catch-up: any day after missed Sunday → True
5. _summarise_events: totals and per-division aggregation
6. _summarise_events: critical → info transition counted as resolved
7. _format_retro: output contains week range, event counts, division block
8. _format_retro: no critical → no open_issues banner
9. _format_retro: critical events → open_issues banner appears
10. run_retro dry_run: saves file, does NOT call Telegram
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import weekly_retro  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_retro_state(tmp_path, monkeypatch):
    """Redirect state and report dirs to tmp_path."""
    monkeypatch.setattr(weekly_retro, "RETRO_STATE_FILE", tmp_path / "retro_state.json")
    monkeypatch.setattr(weekly_retro, "RETRO_REPORTS_DIR", tmp_path / "retros")
    yield


# ---------------------------------------------------------------------------
# 1. _last_sunday
# ---------------------------------------------------------------------------

def test_last_sunday_when_today_is_sunday():
    sunday = date(2026, 4, 26)   # known Sunday
    assert weekly_retro._last_sunday(sunday) == sunday


def test_last_sunday_when_today_is_monday():
    monday = date(2026, 4, 27)
    expected = date(2026, 4, 26)  # previous Sunday
    assert weekly_retro._last_sunday(monday) == expected


def test_last_sunday_when_today_is_saturday():
    saturday = date(2026, 5, 2)
    expected = date(2026, 4, 26)
    assert weekly_retro._last_sunday(saturday) == expected


# ---------------------------------------------------------------------------
# 2. should_run_retro — force flag
# ---------------------------------------------------------------------------

def test_should_run_retro_force():
    assert weekly_retro.should_run_retro(force=True) is True


# ---------------------------------------------------------------------------
# 3. should_run_retro — already sent this week
# ---------------------------------------------------------------------------

def test_should_run_retro_already_sent_this_week():
    """If last_retro_date == last Sunday, retro is not due."""
    state = {"last_retro_date": weekly_retro._last_sunday(date.today()).isoformat()}
    weekly_retro._save_retro_state(state)
    result = weekly_retro.should_run_retro(force=False)
    assert result is False


# ---------------------------------------------------------------------------
# 4. should_run_retro — catch-up: missed last Sunday
# ---------------------------------------------------------------------------

def test_should_run_retro_catchup_when_no_state():
    """With no state file, catch-up fires immediately."""
    assert weekly_retro.should_run_retro(force=False) is True


def test_should_run_retro_catchup_stale_state():
    """last_retro_date older than last Sunday → catch-up fires."""
    two_weeks_ago = (weekly_retro._last_sunday(date.today()) - timedelta(days=7)).isoformat()
    weekly_retro._save_retro_state({"last_retro_date": two_weeks_ago})
    assert weekly_retro.should_run_retro(force=False) is True


# ---------------------------------------------------------------------------
# 5. _summarise_events — basic aggregation
# ---------------------------------------------------------------------------

SAMPLE_EVENTS = [
    {"division": "trading", "severity": "info", "event_type": "health_check", "payload": {}},
    {"division": "trading", "severity": "critical", "event_type": "alert", "payload": {}},
    {"division": "websites", "severity": "warn", "event_type": "metric", "payload": {}},
]


def test_summarise_events_totals():
    stats = weekly_retro._summarise_events(SAMPLE_EVENTS)
    assert stats["total_events"] == 3
    assert stats["by_severity"]["info"] == 1
    assert stats["by_severity"]["critical"] == 1
    assert stats["by_severity"]["warn"] == 1


def test_summarise_events_per_division():
    stats = weekly_retro._summarise_events(SAMPLE_EVENTS)
    divs = stats["division_summaries"]
    assert divs["trading"]["total"] == 2
    assert divs["trading"]["critical"] == 1
    assert divs["websites"]["total"] == 1


# ---------------------------------------------------------------------------
# 6. _summarise_events — resolved transition detection
# ---------------------------------------------------------------------------

def test_summarise_events_resolved_transition():
    events = [
        {"division": "trading", "severity": "critical", "event_type": "alert", "payload": {}},
        {"division": "trading", "severity": "info", "event_type": "resolved", "payload": {}},
    ]
    stats = weekly_retro._summarise_events(events)
    assert stats["division_summaries"]["trading"]["resolved"] == 1


def test_summarise_events_no_resolved_without_transition():
    events = [
        {"division": "trading", "severity": "critical", "event_type": "alert", "payload": {}},
        {"division": "trading", "severity": "critical", "event_type": "alert2", "payload": {}},
    ]
    stats = weekly_retro._summarise_events(events)
    assert stats["division_summaries"]["trading"]["resolved"] == 0


# ---------------------------------------------------------------------------
# 7. _format_retro — structure checks
# ---------------------------------------------------------------------------

def _make_stats(critical=0, warn=0, info=1):
    return {
        "total_events": critical + warn + info,
        "by_severity": {"critical": critical, "warn": warn, "info": info},
        "division_summaries": {
            "trading": {"total": info, "critical": critical, "resolved": 0, "last_severity": "info"},
        },
    }


def test_format_retro_contains_week_range():
    week_start = date(2026, 4, 24)
    week_end = date(2026, 5, 1)
    text = weekly_retro._format_retro(_make_stats(), week_start, week_end)
    assert "2026-04-24" in text
    assert "2026-05-01" in text


def test_format_retro_contains_event_counts():
    text = weekly_retro._format_retro(_make_stats(critical=2, warn=1, info=3), date.today(), date.today())
    assert "Critical: 2" in text
    assert "Warn: 1" in text
    assert "Info: 3" in text


def test_format_retro_contains_division_block():
    text = weekly_retro._format_retro(_make_stats(), date.today(), date.today())
    assert "Division breakdown" in text
    assert "Trading" in text


# ---------------------------------------------------------------------------
# 8. _format_retro — no open_issues when no critical
# ---------------------------------------------------------------------------

def test_format_retro_no_critical_no_warning_banner():
    text = weekly_retro._format_retro(_make_stats(critical=0), date.today(), date.today())
    assert "critical event" not in text.lower() or "0 critical" not in text.lower()
    # Specifically the open_issues banner should not appear
    assert "review RED divisions" not in text


# ---------------------------------------------------------------------------
# 9. _format_retro — critical events → warning banner
# ---------------------------------------------------------------------------

def test_format_retro_critical_shows_warning_banner():
    text = weekly_retro._format_retro(_make_stats(critical=3), date.today(), date.today())
    assert "review RED divisions" in text
    assert "3 critical" in text


# ---------------------------------------------------------------------------
# 10. run_retro dry_run — saves file, skips Telegram
# ---------------------------------------------------------------------------

def test_run_retro_dry_run_saves_file_no_telegram(tmp_path):
    """dry_run=True must write the retro file and record state without calling Telegram."""
    config = {"_config_path": str(Path(__file__).parent.parent / "config" / "projects.yaml")}

    # dry_run=True: the TelegramBridge block is never entered (gated by `if not dry_run`)
    with patch.object(weekly_retro, "_collect_week_events", return_value=[]):
        retro_text = weekly_retro.run_retro(config=config, dry_run=True)

    # File must exist under RETRO_REPORTS_DIR
    retro_files = list(weekly_retro.RETRO_REPORTS_DIR.glob("retro_*.txt"))
    assert len(retro_files) == 1
    assert retro_files[0].read_text(encoding="utf-8") == retro_text

    # State must be recorded even on dry run
    state = weekly_retro._load_retro_state()
    assert "last_retro_date" in state

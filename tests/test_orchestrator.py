"""Tests for Sprint 1 — orchestrator.py core functionality.

Covers:
1. Event insert + readback (SQLite)
2. Event schema validation (invalid severity rejected)
3. Severity routing (critical → escalation flag path)
4. PID file write
5. Stale PID detection → CRASHED status
6. Reasoning cache write
7. Reasoning cache stale detection (age > 2h)
8. Telegram /orchestrator parse_action routing
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import orchestrator  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    """Redirect all state paths to a tmp_path so tests don't touch real state/."""
    monkeypatch.setattr(orchestrator, "STATE_DIR", tmp_path)
    monkeypatch.setattr(orchestrator, "EVENTS_DB", tmp_path / "events.db")
    monkeypatch.setattr(orchestrator, "REASONING_CACHE", tmp_path / "last_reasoning.json")
    monkeypatch.setattr(orchestrator, "PID_FILE", tmp_path / "orchestrator.pid")
    monkeypatch.setattr(orchestrator, "STOP_FLAG", tmp_path / "orchestrator.stop")
    yield


# ---------------------------------------------------------------------------
# 1. Event insert + readback
# ---------------------------------------------------------------------------

def test_emit_and_read_event():
    event_id = orchestrator.emit_event(
        division="trading",
        event_type="health_check",
        severity="info",
        payload={"status": "GREEN"},
        run_id="run-001",
    )
    assert event_id > 0, "emit_event must return a positive row id"
    events = orchestrator.read_events(limit=10)
    assert len(events) >= 1
    latest = events[0]
    assert latest["division"] == "trading"
    assert latest["event_type"] == "health_check"
    assert latest["severity"] == "info"
    assert latest["payload"]["status"] == "GREEN"
    assert latest["run_id"] == "run-001"


# ---------------------------------------------------------------------------
# 2. Schema validation — invalid severity rejected
# ---------------------------------------------------------------------------

def test_emit_event_invalid_severity_raises():
    with pytest.raises(ValueError, match="Invalid severity"):
        orchestrator.emit_event(
            division="trading",
            event_type="health_check",
            severity="unknown_level",
        )


# ---------------------------------------------------------------------------
# 3. Severity routing — critical events get written with correct severity
# ---------------------------------------------------------------------------

def test_emit_critical_severity_stored():
    orchestrator.emit_event("trading", "alert_triggered", "critical", {"alert": "bot down"})
    events = orchestrator.read_events(severity="critical", limit=5)
    assert len(events) >= 1
    assert events[0]["severity"] == "critical"


# ---------------------------------------------------------------------------
# 4. PID file write
# ---------------------------------------------------------------------------

def test_pid_file_written():
    orchestrator.write_pid()
    pid_file = orchestrator.PID_FILE
    assert pid_file.exists(), "PID file must be written"
    pid_content = int(pid_file.read_text().strip())
    assert pid_content == os.getpid()


# ---------------------------------------------------------------------------
# 5. Stale PID → CRASHED status
# ---------------------------------------------------------------------------

def test_stale_pid_returns_crashed(tmp_path):
    # Write a PID that doesn't exist (use a large impossible PID)
    orchestrator.PID_FILE.write_text("999999999", encoding="utf-8")
    status = orchestrator.get_orchestrator_status()
    assert status == "CRASHED", f"Expected CRASHED for dead PID, got {status!r}"


def test_no_pid_file_returns_stopped():
    # No PID file written
    status = orchestrator.get_orchestrator_status()
    assert status == "STOPPED"


# ---------------------------------------------------------------------------
# 6. Reasoning cache write
# ---------------------------------------------------------------------------

def test_write_reasoning_cache():
    orchestrator.write_reasoning_cache(
        division="trading",
        event_id=42,
        diagnosis="Bot heartbeat is stale",
        recommended_action="Re-run health check",
        confidence="high",
    )
    cache = orchestrator.read_reasoning_cache()
    assert cache["division"] == "trading"
    assert cache["event_id"] == 42
    assert cache["diagnosis"] == "Bot heartbeat is stale"
    assert cache["recommended_action"] == "Re-run health check"
    assert cache["confidence"] == "high"
    assert "generated_at_utc" in cache


# ---------------------------------------------------------------------------
# 7. Reasoning cache stale detection
# ---------------------------------------------------------------------------

def test_reasoning_cache_fresh_not_stale():
    orchestrator.write_reasoning_cache("trading", 1, "d", "a", "low")
    cache = orchestrator.read_reasoning_cache()
    assert orchestrator.reasoning_cache_is_stale(cache) is False


def test_reasoning_cache_old_is_stale(tmp_path):
    # Write a cache with a timestamp 3 hours ago
    old_ts = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    payload = {
        "generated_at_utc": old_ts,
        "division": "trading",
        "event_id": 1,
        "diagnosis": "old",
        "recommended_action": "old",
        "confidence": "low",
    }
    orchestrator.REASONING_CACHE.write_text(json.dumps(payload), encoding="utf-8")
    cache = orchestrator.read_reasoning_cache()
    assert orchestrator.reasoning_cache_is_stale(cache) is True


def test_empty_cache_is_stale():
    assert orchestrator.reasoning_cache_is_stale({}) is True


# ---------------------------------------------------------------------------
# 8. Telegram /orchestrator parse_action routing
# ---------------------------------------------------------------------------

def test_telegram_parse_orchestrator_status():
    """_parse_action must return orchestrator type for /orchestrator status."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "fake:token")
    os.environ.setdefault("TELEGRAM_OWNER_CHAT_ID", "123456")
    from telegram_bridge import TelegramBridge  # pylint: disable=import-outside-toplevel
    bridge = TelegramBridge(config_path=Path(__file__).parent.parent / "config" / "projects.yaml")
    for subcmd in ("status", "stop", "start"):
        action = bridge._parse_action(f"/orchestrator {subcmd}")
        assert action["type"] == "orchestrator", f"Expected orchestrator type for subcmd={subcmd!r}"
        assert action["subcmd"] == subcmd


# ---------------------------------------------------------------------------
# Sprint 2 — all three divisions emit and are queryable
# ---------------------------------------------------------------------------

def test_emit_events_all_three_divisions():
    """Trading, websites, and commercial must all be able to emit events."""
    for division in ("trading", "websites", "commercial"):
        eid = orchestrator.emit_event(division, "health_check", "info", {"division": division})
        assert eid > 0, f"emit_event failed for division={division!r}"

    for division in ("trading", "websites", "commercial"):
        events = orchestrator.read_events(division=division, limit=5)
        assert len(events) >= 1, f"No events found for division={division!r}"
        assert all(e["division"] == division for e in events)


def test_read_events_filters_by_division():
    """read_events(division=X) must return only division X events."""
    orchestrator.emit_event("trading", "health_check", "info")
    orchestrator.emit_event("websites", "health_check", "warn")
    orchestrator.emit_event("commercial", "health_check", "info")

    trading_events = orchestrator.read_events(division="trading", limit=10)
    assert all(e["division"] == "trading" for e in trading_events)

    websites_events = orchestrator.read_events(division="websites", limit=10)
    assert all(e["division"] == "websites" for e in websites_events)


def test_read_events_mixed_severity():
    """read_events must return events with correct severity values."""
    orchestrator.emit_event("trading", "alert_triggered", "critical")
    orchestrator.emit_event("websites", "metric_changed", "warn")
    orchestrator.emit_event("commercial", "task_completed", "info")

    critical = orchestrator.read_events(severity="critical", limit=10)
    assert all(e["severity"] == "critical" for e in critical)

    info = orchestrator.read_events(severity="info", limit=10)
    assert all(e["severity"] == "info" for e in info)


def test_emit_event_returns_sequential_ids():
    """Consecutive emits must return monotonically increasing row IDs."""
    ids = [
        orchestrator.emit_event("trading", "health_check", "info")
        for _ in range(3)
    ]
    assert ids == sorted(ids), f"Event IDs not sequential: {ids}"
    assert len(set(ids)) == 3, f"Duplicate event IDs: {ids}"

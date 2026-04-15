"""D3 health module tests — 4 cases.

Run with: python tests/test_health.py

Cases:
  1. All GREEN — scorecard with all passing items → status=GREEN
  2. One AMBER signal (non-critical) → status=AMBER
  3. RED threshold breach (critical signal failing) → status=RED
  4. Missing data file → AMBER (not crash)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from health.division_health import _compute_status, _signals_from_scorecard, get_status

# ---------------------------------------------------------------------------
# Helper — build a minimal scorecard dict
# ---------------------------------------------------------------------------

def _make_scorecard(items: list[dict]) -> dict:
    return {"items": items}


def _make_item(metric: str, status: str, actual: str = "ok", target: str = "target") -> dict:
    return {
        "metric": metric,
        "status": status,
        "actual": actual,
        "target": target,
        "variance": "0",
        "action": "",
    }


# ---------------------------------------------------------------------------
# Test 1 — All GREEN
# ---------------------------------------------------------------------------

def test_all_green() -> None:
    scorecard = _make_scorecard([
        _make_item("MT5 dependencies", "GREEN"),
        _make_item("Active validated strategies", "GREEN"),
        _make_item("Polymarket VPS service", "GREEN"),
        _make_item("Polymarket latest resolved-trade data age", "GREEN"),
        _make_item("Polymarket resolved trades in 24h", "GREEN"),
    ])
    signals = _signals_from_scorecard(scorecard)
    status = _compute_status(signals, "trading")
    assert status == "GREEN", f"Expected GREEN, got {status}"
    assert all(s["result"] == "pass" for s in signals), "All signals should pass"
    print("PASS: test_all_green")


# ---------------------------------------------------------------------------
# Test 2 — One AMBER non-critical signal → overall AMBER
# ---------------------------------------------------------------------------

def test_one_amber_signal() -> None:
    scorecard = _make_scorecard([
        _make_item("MT5 dependencies", "GREEN"),
        _make_item("Active validated strategies", "GREEN"),
        _make_item("Polymarket VPS service", "GREEN"),
        _make_item("Best active strategy PF", "AMBER", actual="1.25", target=">= 1.30"),
        _make_item("Polymarket resolved trades in 24h", "GREEN"),
    ])
    signals = _signals_from_scorecard(scorecard)
    status = _compute_status(signals, "trading")
    assert status == "AMBER", f"Expected AMBER (1 non-critical fail), got {status}"
    failing = [s for s in signals if s["result"] == "fail"]
    assert len(failing) == 1
    print("PASS: test_one_amber_signal")


# ---------------------------------------------------------------------------
# Test 3 — Critical signal failing → RED
# ---------------------------------------------------------------------------

def test_critical_signal_red() -> None:
    scorecard = _make_scorecard([
        _make_item("MT5 dependencies", "RED", actual="mt5=False"),
        _make_item("Active validated strategies", "GREEN"),
        _make_item("Polymarket VPS service", "GREEN"),
        _make_item("Polymarket resolved trades in 24h", "GREEN"),
    ])
    signals = _signals_from_scorecard(scorecard)
    status = _compute_status(signals, "trading")
    assert status == "RED", f"Expected RED (critical fail), got {status}"
    print("PASS: test_critical_signal_red")


# ---------------------------------------------------------------------------
# Test 4 — Missing data file → AMBER (not crash)
# ---------------------------------------------------------------------------

def test_missing_data_file_returns_amber() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        # Patch REPORTS to an empty temp dir (no JSON files)
        with patch("health.division_health.REPORTS", tmp_path), \
             patch("health.division_health._BRIEF_LATEST", tmp_path / "daily_brief_latest.json"), \
             patch("health.division_health._DIVISIONS_LATEST", tmp_path / "phase2_divisions_latest.json"):
            result = get_status("trading")
    assert result["status"] == "AMBER", (
        f"Expected AMBER when data files missing, got {result['status']}"
    )
    assert result["division"] == "trading"
    assert any(s["result"] == "fail" for s in result["signals"])
    print("PASS: test_missing_data_file_returns_amber")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_all_green,
        test_one_amber_signal,
        test_critical_signal_red,
        test_missing_data_file_returns_amber,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as exc:
            print(f"FAIL: {t.__name__} — {exc}")
            import traceback
            traceback.print_exc()
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests PASSED")

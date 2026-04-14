"""Self-heal tests — 3 cases.

Run with: python tests/test_self_heal.py

Cases:
  1. No missed jobs  → run_once() returns [], nothing logged to CEO
  2. One missed job  → heals silently, no escalation returned
  3. Job misses twice → run_once() returns escalation string
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Patch artifact paths to use temp dirs so tests don't pollute real state
# ---------------------------------------------------------------------------

import scheduler.heartbeat_log as hbl
import scheduler.self_heal as sh
import scheduler.monitor as mon


def _make_temp_artifacts(tmp: Path) -> None:
    """Point all module-level paths at a temp directory."""
    artifacts = tmp / "artifacts"
    artifacts.mkdir()
    hbl.ARTIFACTS = artifacts
    hbl.SCHEDULER_LOG = artifacts / "scheduler_log.json"
    sh.ARTIFACTS = artifacts
    mon.ARTIFACTS = artifacts
    mon.MA_LOG = artifacts / "ma_log.json"


def _write_log(tmp: Path, entries: list) -> None:
    (tmp / "artifacts" / "scheduler_log.json").write_text(
        json.dumps(entries, indent=2), encoding="utf-8"
    )


def _read_ma_log(tmp: Path) -> list:
    p = tmp / "artifacts" / "ma_log.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Case 1: No missed jobs — silent
# ---------------------------------------------------------------------------

def test_no_missed_jobs_silent():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _make_temp_artifacts(tmp)

        # Log has only fired entries — nothing missed
        now = datetime.now(timezone.utc)
        entries = [
            {
                "job_id": "morning_brief",
                "fired_at": (now - timedelta(hours=1)).isoformat(),
                "expected_at": (now - timedelta(hours=1)).isoformat(),
                "status": "fired",
                "output_path": "state/telegram_bridge_state.json",
                "output_exists": False,
            }
        ]
        _write_log(tmp, entries)

        escalations = mon.run_once()
        assert escalations == [], f"Expected no escalations, got: {escalations}"

        ma_log = _read_ma_log(tmp)
        assert ma_log == [], f"Expected empty ma_log, got: {ma_log}"

    print("PASS: test_no_missed_jobs_silent")


# ---------------------------------------------------------------------------
# Case 2: One missed job → heals silently, no escalation
# ---------------------------------------------------------------------------

def test_one_missed_job_heals_silently():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _make_temp_artifacts(tmp)

        now = datetime.now(timezone.utc)
        # morning_brief was fired 26h ago — now missed (24h interval × 110% = 26.4h)
        entries = [
            {
                "job_id": "morning_brief",
                "fired_at": (now - timedelta(hours=27)).isoformat(),
                "expected_at": (now - timedelta(hours=27)).isoformat(),
                "status": "fired",
                "output_path": "state/telegram_bridge_state.json",
                "output_exists": False,
            },
            {
                "job_id": "morning_brief",
                "fired_at": None,
                "expected_at": (now - timedelta(hours=3)).isoformat(),
                "status": "missed",
                "output_path": "state/telegram_bridge_state.json",
                "output_exists": False,
            },
        ]
        _write_log(tmp, entries)

        # Patch re-fire function to succeed without doing anything real
        fake_refire = MagicMock(return_value={"ok": True})
        with patch.object(sh, "_get_refire_fn", return_value=fake_refire):
            escalations = mon.run_once()

        assert escalations == [], f"Expected no escalations, got: {escalations}"
        fake_refire.assert_called_once()

        # ma_log should have a silent heal entry
        ma_log = _read_ma_log(tmp)
        assert len(ma_log) == 1, f"Expected 1 ma_log entry, got {len(ma_log)}"
        assert ma_log[0]["outcome"] == "healed"
        assert ma_log[0]["job_id"] == "morning_brief"

    print("PASS: test_one_missed_job_heals_silently")


# ---------------------------------------------------------------------------
# Case 3: Job misses twice → escalation message returned
# ---------------------------------------------------------------------------

def test_double_miss_escalates():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        _make_temp_artifacts(tmp)

        now = datetime.now(timezone.utc)
        # Sequence: fired → missed → healed → missed again (double miss)
        entries = [
            {
                "job_id": "run_divisions",
                "fired_at": (now - timedelta(hours=50)).isoformat(),
                "expected_at": (now - timedelta(hours=50)).isoformat(),
                "status": "fired",
                "output_path": "reports/phase2_divisions_latest.json",
                "output_exists": False,
            },
            {
                "job_id": "run_divisions",
                "fired_at": None,
                "expected_at": (now - timedelta(hours=26)).isoformat(),
                "status": "missed",
                "output_path": "reports/phase2_divisions_latest.json",
                "output_exists": False,
            },
            {
                "job_id": "run_divisions",
                "fired_at": (now - timedelta(hours=25)).isoformat(),
                "expected_at": (now - timedelta(hours=26)).isoformat(),
                "status": "healed",
                "output_path": "reports/phase2_divisions_latest.json",
                "output_exists": False,
            },
            {
                "job_id": "run_divisions",
                "fired_at": None,
                "expected_at": (now - timedelta(hours=1)).isoformat(),
                "status": "missed",
                "output_path": "reports/phase2_divisions_latest.json",
                "output_exists": False,
            },
        ]
        _write_log(tmp, entries)

        escalations = mon.run_once()

        assert len(escalations) == 1, f"Expected 1 escalation, got: {escalations}"
        assert "run_divisions" in escalations[0]
        assert "missed twice" in escalations[0]
        assert escalations[0].startswith("[ESCALATION]")

        # ma_log should have the escalation entry
        ma_log = _read_ma_log(tmp)
        assert any(e.get("outcome") == "escalated" for e in ma_log), \
            f"Expected escalated entry in ma_log: {ma_log}"

    print("PASS: test_double_miss_escalates")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_no_missed_jobs_silent,
        test_one_missed_job_heals_silently,
        test_double_miss_escalates,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as exc:
            print(f"FAIL: {t.__name__} — {exc}")
            import traceback; traceback.print_exc()
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests PASSED")

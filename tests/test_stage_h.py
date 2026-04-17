"""Stage H tests: Board Pack 8-field format, validation gate, dissent placeholder."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from phase3_holding import _build_board_review, _validate_board_pack_item

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_COMPLETE_ITEM = {
    "rationale": "KPI is RED — immediate review required.",
    "expected_upside": "Restores metric to target",
    "effort_cost": "n/a",
    "confidence": "Medium — derived from telemetry",
    "owner": "trading",
    "deadline": "2026-04-17",
    "dissent": "No significant downside identified",
    "measurement_plan": "Monitor in next daily brief. GREEN for 2 runs.",
}

_AMBER_SCORECARD: dict = {
    "items": [
        {
            "metric": "Max drawdown",
            "status": "AMBER",
            "action": "Reduce exposure.",
        }
    ],
    "status": "AMBER",
}

_RED_SCORECARD: dict = {
    "items": [
        {
            "metric": "Monthly PnL growth",
            "status": "RED",
            "action": "Review allocation.",
        }
    ],
    "status": "RED",
}


# ---------------------------------------------------------------------------
# _build_board_review: structure
# ---------------------------------------------------------------------------


def test_board_pack_item_has_all_fields():
    """_build_board_review() output items contain all 10 expected keys."""
    result = _build_board_review(_RED_SCORECARD, [])
    assert result["approvals"], "Expected at least one approval item"
    item = result["approvals"][0]
    for key in [
        "rationale", "expected_upside", "effort_cost", "confidence",
        "owner", "deadline", "dissent", "measurement_plan", "priority", "topic",
    ]:
        assert key in item, f"Missing key: {key}"


def test_board_pack_dissent_placeholder():
    """dissent field is 'PENDING...' when dissent_agent has not run."""
    result = _build_board_review(_RED_SCORECARD, [])
    item = result["approvals"][0]
    assert "PENDING" in item.get("dissent", ""), "Expected PENDING placeholder in dissent"


def test_board_pack_gate_blocked_false_by_default():
    """gate_blocked is False in the raw _build_board_review() output."""
    result = _build_board_review(_RED_SCORECARD, [])
    assert result.get("gate_blocked") is False


def test_board_pack_commercial_included():
    """When commercial_result status=AMBER, an item appears with owner='commercial'."""
    commercial_result = {
        "status": "AMBER",
        "risk": {
            "risk_verdict": "AMBER",
            "exposure_flags": ["drawdown_elevated"],
        },
    }
    result = _build_board_review({}, [], commercial_result=commercial_result)
    owners = [item.get("owner") for item in result["approvals"]]
    assert "commercial" in owners, "Expected commercial owner in approvals"


def test_board_pack_commercial_green_excluded():
    """When commercial_result status=GREEN, no commercial item is added."""
    commercial_result = {"status": "GREEN", "risk": {"risk_verdict": "GREEN", "exposure_flags": []}}
    result = _build_board_review({}, [], commercial_result=commercial_result)
    owners = [item.get("owner") for item in result["approvals"]]
    assert "commercial" not in owners


def test_board_pack_commercial_none_safe():
    """_build_board_review(..., commercial_result=None) does not raise."""
    result = _build_board_review({}, [], commercial_result=None)
    assert result is not None
    assert "approvals" in result


def test_board_pack_green_items_excluded():
    """GREEN scorecard items are not added to approvals."""
    green_scorecard = {
        "items": [{"metric": "uptime", "status": "GREEN", "action": "ok"}]
    }
    result = _build_board_review(green_scorecard, [])
    assert result["approvals"] == []


def test_board_pack_max_10_items():
    """Approvals list is capped at 10 items."""
    scorecard = {
        "items": [
            {"metric": f"metric_{i}", "status": "RED", "action": "fix it"}
            for i in range(20)
        ]
    }
    result = _build_board_review(scorecard, [])
    assert len(result["approvals"]) <= 10


def test_board_pack_red_deadline_is_today():
    """RED items get today's ISO date as deadline (not +7d)."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date().isoformat()
    result = _build_board_review(_RED_SCORECARD, [])
    item = result["approvals"][0]
    assert item["deadline"] == today


def test_board_pack_amber_deadline_is_plus7d():
    """AMBER items get '+7d' as deadline."""
    result = _build_board_review(_AMBER_SCORECARD, [])
    item = result["approvals"][0]
    assert item["deadline"] == "+7d"


# ---------------------------------------------------------------------------
# _validate_board_pack_item
# ---------------------------------------------------------------------------


def test_validate_full_item_passes():
    """_validate_board_pack_item() returns [] for a fully populated item."""
    assert _validate_board_pack_item(_COMPLETE_ITEM) == []


def test_validate_missing_dissent_flagged():
    """Item without dissent field returns ['dissent'] in missing list."""
    item = {k: v for k, v in _COMPLETE_ITEM.items() if k != "dissent"}
    missing = _validate_board_pack_item(item)
    assert "dissent" in missing


def test_validate_pending_dissent_flagged():
    """'PENDING — dissent_agent review required' counts as missing dissent."""
    item = dict(_COMPLETE_ITEM)
    item["dissent"] = "PENDING — dissent_agent review required"
    missing = _validate_board_pack_item(item)
    assert "dissent" in missing


def test_validate_na_allowed_for_effort_cost():
    """'n/a' in effort_cost does NOT appear in missing list."""
    item = dict(_COMPLETE_ITEM)
    item["effort_cost"] = "n/a"
    missing = _validate_board_pack_item(item)
    assert "effort_cost" not in missing


def test_validate_na_allowed_for_expected_upside():
    """'n/a' in expected_upside does NOT appear in missing list."""
    item = dict(_COMPLETE_ITEM)
    item["expected_upside"] = "n/a"
    missing = _validate_board_pack_item(item)
    assert "expected_upside" not in missing


def test_validate_unavailable_dissent_not_flagged():
    """'Dissent agent unavailable...' is accepted as a valid dissent value."""
    item = dict(_COMPLETE_ITEM)
    item["dissent"] = "Dissent agent unavailable — manual review required"
    missing = _validate_board_pack_item(item)
    assert "dissent" not in missing


def test_validate_missing_owner_flagged():
    """Item without owner returns ['owner'] in missing list."""
    item = {k: v for k, v in _COMPLETE_ITEM.items() if k != "owner"}
    missing = _validate_board_pack_item(item)
    assert "owner" in missing


def test_validate_empty_rationale_flagged():
    """Empty string rationale is flagged."""
    item = dict(_COMPLETE_ITEM)
    item["rationale"] = ""
    missing = _validate_board_pack_item(item)
    assert "rationale" in missing

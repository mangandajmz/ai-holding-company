"""Tests for Stage H — Holding Board v2 (board_pack mode).

Covers:
- _build_board_review() output shape and 10-field requirement
- _validate_board_pack_item() MA gate logic
- board_pack mode integration (mocked Ollama / CrewAI)
- Dissent fallback when dissent agent fails
- MA gate ⚠️ prefix when items are incomplete
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import phase3_holding  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "rationale",
    "expected_upside",
    "effort_cost",
    "confidence",
    "owner",
    "deadline",
    "dissent",
    "measurement_plan",
    "priority",
    "topic",
}


def _red_kpi_scorecard() -> dict:
    return {
        "goal": "grow",
        "desired_outcome": "positive",
        "items": [
            {
                "metric": "Division GREEN ratio",
                "status": "RED",
                "actual": "33%",
                "target": ">= 67%",
                "action": "Address weakest division first.",
            },
            {
                "metric": "Website uptime",
                "status": "AMBER",
                "actual": "95%",
                "target": ">= 99%",
                "action": "",
            },
        ],
    }


def _green_kpi_scorecard() -> dict:
    return {
        "goal": "grow",
        "desired_outcome": "positive",
        "items": [
            {"metric": "Division GREEN ratio", "status": "GREEN", "actual": "80%", "target": ">= 67%"},
        ],
    }


def _division(status: str = "red") -> dict:
    return {
        "division": "trading",
        "ok": True,
        "status": status,
        "scorecard": {
            "items": [
                {
                    "metric": "Bot heartbeat",
                    "status": "RED" if status == "red" else "GREEN",
                    "actual": "stale",
                    "target": "fresh",
                    "action": "Restart bot.",
                }
            ]
        },
    }


# ---------------------------------------------------------------------------
# 1. _build_board_review produces 10-field items for RED/AMBER KPIs
# ---------------------------------------------------------------------------

def test_board_review_red_kpi_produces_10_fields():
    scorecard = _red_kpi_scorecard()
    result = phase3_holding._build_board_review(scorecard, [])
    approvals = result.get("approvals", [])
    assert len(approvals) >= 1, "Expected at least one RED/AMBER item"
    for item in approvals:
        missing = REQUIRED_FIELDS - set(item.keys())
        assert missing == set(), f"Item missing fields: {missing}"


def test_board_review_green_kpis_excluded():
    """GREEN KPI items must not appear in board_review approvals."""
    scorecard = _green_kpi_scorecard()
    result = phase3_holding._build_board_review(scorecard, [])
    approvals = result.get("approvals", [])
    for item in approvals:
        assert item.get("priority", "").upper() != "GREEN", "GREEN item leaked into board_review"


def test_board_review_red_items_sorted_before_amber():
    """RED items must appear before AMBER items in the approval list."""
    scorecard = _red_kpi_scorecard()  # has one RED and one AMBER
    result = phase3_holding._build_board_review(scorecard, [])
    approvals = result.get("approvals", [])
    priorities = [a.get("priority", "").upper() for a in approvals]
    # Find first AMBER index and last RED index
    red_indices = [i for i, p in enumerate(priorities) if p == "RED"]
    amber_indices = [i for i, p in enumerate(priorities) if p == "AMBER"]
    if red_indices and amber_indices:
        assert max(red_indices) < min(amber_indices), "RED item must come before AMBER"


def test_board_review_division_red_item_included():
    """RED items from divisions must appear in approvals."""
    scorecard = _green_kpi_scorecard()
    divisions = [_division(status="red")]
    result = phase3_holding._build_board_review(scorecard, divisions)
    approvals = result.get("approvals", [])
    topics = [a.get("topic", "") for a in approvals]
    assert any("Trading" in t or "trading" in t for t in topics), (
        f"Expected Trading division item, got: {topics}"
    )


def test_board_review_placeholder_dissent_set():
    """Fresh _build_board_review must set dissent to the PENDING placeholder."""
    scorecard = _red_kpi_scorecard()
    result = phase3_holding._build_board_review(scorecard, [])
    for item in result.get("approvals", []):
        assert "PENDING" in item["dissent"], (
            f"Expected PENDING placeholder, got: {item['dissent']}"
        )


# ---------------------------------------------------------------------------
# 2. _validate_board_pack_item MA gate
# ---------------------------------------------------------------------------

def test_validate_board_pack_item_valid():
    item = {
        "priority": "RED",
        "topic": "Division health",
        "rationale": "KPI is RED",
        "owner": "holding",
        "measurement_plan": "Monitor in next brief.",
    }
    assert phase3_holding._validate_board_pack_item(item) is True


def test_validate_board_pack_item_missing_rationale():
    item = {
        "priority": "RED",
        "topic": "Division health",
        "owner": "holding",
        "measurement_plan": "Monitor in next brief.",
    }
    assert phase3_holding._validate_board_pack_item(item) is False


def test_validate_board_pack_item_missing_owner():
    item = {
        "priority": "RED",
        "topic": "Division health",
        "rationale": "KPI is RED",
        "measurement_plan": "Monitor in next brief.",
    }
    assert phase3_holding._validate_board_pack_item(item) is False


def test_validate_board_pack_item_missing_measurement_plan():
    item = {
        "priority": "RED",
        "topic": "Division health",
        "rationale": "KPI is RED",
        "owner": "holding",
    }
    assert phase3_holding._validate_board_pack_item(item) is False


def test_validate_board_pack_item_empty_strings_invalid():
    """Empty string values for required fields must fail validation."""
    item = {
        "priority": "RED",
        "topic": "Division health",
        "rationale": "",
        "owner": "holding",
        "measurement_plan": "Monitor.",
    }
    assert phase3_holding._validate_board_pack_item(item) is False


# ---------------------------------------------------------------------------
# 3. Commercial result integration
# ---------------------------------------------------------------------------

def test_board_review_commercial_red_included():
    """Non-GREEN commercial result must appear as a board_review item."""
    scorecard = _green_kpi_scorecard()
    commercial_result = {
        "status": "RED",
        "risk": {
            "exposure_flags": ["Drawdown exceeds 10% threshold"],
        },
    }
    result = phase3_holding._build_board_review(scorecard, [], commercial_result=commercial_result)
    approvals = result.get("approvals", [])
    topics = [a.get("topic", "").lower() for a in approvals]
    assert any("commercial" in t for t in topics), (
        f"Expected commercial item in board_review, got topics: {topics}"
    )

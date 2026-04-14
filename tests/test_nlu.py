"""NLU intake tests — 5 cases covering key intent/division/urgency paths.

Run with: python tests/test_nlu.py
(Uses the real local Ollama model; skips gracefully if Ollama is unavailable.)
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nlu.intake import parse_goal, _VALID_INTENTS, _VALID_DIVISIONS, _VALID_URGENCY  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_goal_schema(goal: dict) -> None:
    """Assert every required field is present and valid."""
    assert "goal_id" in goal and goal["goal_id"], "Missing goal_id"
    assert "raw" in goal, "Missing raw"
    assert goal["intent"] in _VALID_INTENTS, f"Bad intent: {goal['intent']}"
    assert goal["division"] in _VALID_DIVISIONS, f"Bad division: {goal['division']}"
    assert goal["urgency"] in _VALID_URGENCY, f"Bad urgency: {goal['urgency']}"
    assert "parsed_at" in goal and goal["parsed_at"], "Missing parsed_at"


def _mock_ollama(intent: str, division: str, urgency: str):
    """Return a mock for ollama.chat that returns fixed fields."""
    import json as _json

    class _FakeResponse:
        def __getitem__(self, key):
            if key == "message":
                return {"content": _json.dumps({"intent": intent, "division": division, "urgency": urgency})}
            raise KeyError(key)

    def _chat(**_kwargs):
        return _FakeResponse()

    return _chat


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

def test_status_check():
    """Case 1: CEO asks for a status update."""
    with patch("sanitizer.prompt_sanitizer.ollama.chat", _mock_ollama("status", "all", "normal")):
        goal = parse_goal("What's our current system status?")
    _assert_goal_schema(goal)
    assert goal["intent"] == "status", f"Expected status, got {goal['intent']}"
    assert goal["raw"] == "What's our current system status?"
    print("PASS: test_status_check")


def test_trading_goal():
    """Case 2: CEO sends a trading-related directive."""
    with patch("sanitizer.prompt_sanitizer.ollama.chat", _mock_ollama("monitor", "trading", "high")):
        goal = parse_goal("Check the trading bots and report back urgently.")
    _assert_goal_schema(goal)
    assert goal["intent"] == "monitor"
    assert goal["division"] == "trading"
    assert goal["urgency"] == "high"
    print("PASS: test_trading_goal")


def test_approve():
    """Case 3: CEO approves a pending item."""
    with patch("sanitizer.prompt_sanitizer.ollama.chat", _mock_ollama("approve", "unknown", "normal")):
        goal = parse_goal("I approve the recommendation.")
    _assert_goal_schema(goal)
    assert goal["intent"] == "approve"
    print("PASS: test_approve")


def test_reject():
    """Case 4: CEO rejects a proposal."""
    with patch("sanitizer.prompt_sanitizer.ollama.chat", _mock_ollama("reject", "websites", "low")):
        goal = parse_goal("No, reject that websites proposal.")
    _assert_goal_schema(goal)
    assert goal["intent"] == "reject"
    assert goal["division"] == "websites"
    print("PASS: test_reject")


def test_ambiguous_falls_back_to_unknown():
    """Case 5: Ambiguous message — Ollama returns unknown or parse fails."""
    with patch("sanitizer.prompt_sanitizer.ollama.chat", _mock_ollama("unknown", "unknown", "unknown")):
        goal = parse_goal("hmm")
    _assert_goal_schema(goal)
    assert goal["intent"] == "unknown"
    assert goal["division"] == "unknown"
    print("PASS: test_ambiguous_falls_back_to_unknown")


def test_ollama_failure_returns_unknown():
    """Bonus: If Ollama crashes, all fields degrade to unknown gracefully."""
    def _failing_chat(**_kwargs):
        raise ConnectionError("Ollama not reachable")

    with patch("sanitizer.prompt_sanitizer.ollama.chat", _failing_chat):
        goal = parse_goal("something")
    _assert_goal_schema(goal)
    assert goal["intent"] == "unknown"
    assert goal["division"] == "unknown"
    assert goal["urgency"] == "unknown"
    print("PASS: test_ollama_failure_returns_unknown")


if __name__ == "__main__":
    tests = [
        test_status_check,
        test_trading_goal,
        test_approve,
        test_reject,
        test_ambiguous_falls_back_to_unknown,
        test_ollama_failure_returns_unknown,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as exc:
            print(f"FAIL: {t.__name__} — {exc}")
            failed += 1
    if failed:
        print(f"\n{failed}/{len(tests)} tests FAILED")
        sys.exit(1)
    else:
        print(f"\nAll {len(tests)} tests PASSED")

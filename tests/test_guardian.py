"""Guardian compliance tests — every rule, pass and fail.

Run with: python tests/test_guardian.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compliance.guardian import check  # noqa: E402


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _assert_pass(result: dict) -> None:
    assert result.get("pass") is True, f"Expected pass but got: {result}"


def _assert_fail(result: dict, rule: str) -> None:
    assert result.get("pass") is False, f"Expected fail for {rule} but got pass"
    assert rule in result.get("violated_rules", []), (
        f"Expected {rule} in violated_rules, got: {result.get('violated_rules')}"
    )


# ---------------------------------------------------------------------------
# R1 — Non-Ollama model names
# ---------------------------------------------------------------------------

def test_r1_pass_ollama_model():
    result = check({"model": "llama3.2:latest", "raw": "status check"})
    _assert_pass(result)
    print("PASS: test_r1_pass_ollama_model")


def test_r1_fail_openai():
    result = check({"model": "openai", "raw": "use gpt-4"})
    _assert_fail(result, "R1")
    print("PASS: test_r1_fail_openai")


def test_r1_fail_anthropic():
    result = check({"raw": "call anthropic for this"})
    _assert_fail(result, "R1")
    print("PASS: test_r1_fail_anthropic")


def test_r1_fail_grok():
    result = check({"raw": "use grok to analyse"})
    _assert_fail(result, "R1")
    print("PASS: test_r1_fail_grok")


def test_r1_fail_gemini():
    result = check({"raw": "query gemini"})
    _assert_fail(result, "R1")
    print("PASS: test_r1_fail_gemini")


def test_r1_fail_claude_api():
    result = check({"raw": "use claude-api endpoint"})
    _assert_fail(result, "R1")
    print("PASS: test_r1_fail_claude_api")


# ---------------------------------------------------------------------------
# R5 — Fund/money/trade actions
# ---------------------------------------------------------------------------

def test_r5_pass_safe_goal():
    result = check({"intent": "status", "division": "trading", "raw": "what is the trading status?"})
    _assert_pass(result)
    print("PASS: test_r5_pass_safe_goal")


def test_r5_fail_transfer_funds():
    result = check({"raw": "transfer funds to account 123"})
    _assert_fail(result, "R5")
    print("PASS: test_r5_fail_transfer_funds")


def test_r5_fail_withdraw():
    result = check({"raw": "withdraw 500 from the pot"})
    _assert_fail(result, "R5")
    print("PASS: test_r5_fail_withdraw")


def test_r5_fail_execute_trade():
    result = check({"raw": "execute trade on AAPL"})
    _assert_fail(result, "R5")
    print("PASS: test_r5_fail_execute_trade")


def test_r5_fail_deposit():
    result = check({"raw": "deposit funds into the reserve"})
    _assert_fail(result, "R5")
    print("PASS: test_r5_fail_deposit")


# ---------------------------------------------------------------------------
# R8 — File paths outside ai-holding-company/
# ---------------------------------------------------------------------------

def test_r8_pass_inside_project():
    result = check({"path": "ai-holding-company/reports/latest.json"})
    _assert_pass(result)
    print("PASS: test_r8_pass_inside_project")


def test_r8_fail_path_traversal():
    result = check({"path": "../../etc/passwd"})
    _assert_fail(result, "R8")
    print("PASS: test_r8_fail_path_traversal")


def test_r8_fail_absolute_outside():
    result = check({"path": "C:/Windows/System32/secret.txt"})
    _assert_fail(result, "R8")
    print("PASS: test_r8_fail_absolute_outside")


# ---------------------------------------------------------------------------
# R11 — Forbidden infrastructure
# ---------------------------------------------------------------------------

def test_r11_pass_no_infra():
    result = check({"raw": "show me the monitoring report"})
    _assert_pass(result)
    print("PASS: test_r11_pass_no_infra")


def test_r11_fail_openclaw():
    result = check({"raw": "use openclaw to schedule this"})
    _assert_fail(result, "R11")
    print("PASS: test_r11_fail_openclaw")


def test_r11_fail_docker_compose():
    result = check({"raw": "run docker-compose up"})
    _assert_fail(result, "R11")
    print("PASS: test_r11_fail_docker_compose")


def test_r11_fail_rabbitmq():
    result = check({"raw": "send to rabbitmq queue"})
    _assert_fail(result, "R11")
    print("PASS: test_r11_fail_rabbitmq")


def test_r11_fail_redis_gateway():
    result = check({"raw": "push to redis-gateway"})
    _assert_fail(result, "R11")
    print("PASS: test_r11_fail_redis_gateway")


# ---------------------------------------------------------------------------
# Multiple violations
# ---------------------------------------------------------------------------

def test_multi_violation():
    result = check({"model": "openai", "raw": "transfer funds via rabbitmq"})
    assert result.get("pass") is False
    rules = result.get("violated_rules", [])
    assert "R1" in rules, f"Expected R1 in {rules}"
    assert "R5" in rules, f"Expected R5 in {rules}"
    assert "R11" in rules, f"Expected R11 in {rules}"
    print("PASS: test_multi_violation")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_dict_passes():
    result = check({})
    _assert_pass(result)
    print("PASS: test_empty_dict_passes")


def test_non_dict_fails_gracefully():
    result = check("not a dict")  # type: ignore[arg-type]
    assert result.get("pass") is False
    print("PASS: test_non_dict_fails_gracefully")


if __name__ == "__main__":
    tests = [
        test_r1_pass_ollama_model,
        test_r1_fail_openai,
        test_r1_fail_anthropic,
        test_r1_fail_grok,
        test_r1_fail_gemini,
        test_r1_fail_claude_api,
        test_r5_pass_safe_goal,
        test_r5_fail_transfer_funds,
        test_r5_fail_withdraw,
        test_r5_fail_execute_trade,
        test_r5_fail_deposit,
        test_r8_pass_inside_project,
        test_r8_fail_path_traversal,
        test_r8_fail_absolute_outside,
        test_r11_pass_no_infra,
        test_r11_fail_openclaw,
        test_r11_fail_docker_compose,
        test_r11_fail_rabbitmq,
        test_r11_fail_redis_gateway,
        test_multi_violation,
        test_empty_dict_passes,
        test_non_dict_fails_gracefully,
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

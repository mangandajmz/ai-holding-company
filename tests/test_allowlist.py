"""Allowlist tests — 9 cases.

Run with: python tests/test_allowlist.py

Cases:
  File write:
    1. Path inside project root → allowed
    2. Path outside project root → blocked
    3. Traversal attempt via ../ → blocked

  Tool call:
    4. Known allowed tool → allowed
    5. Unknown tool → blocked

  Network call:
    6. localhost URL → allowed
    7. api.telegram.org URL → allowed
    8. External URL (openai.com) → blocked
    9. External URL (arbitrary HTTPS) → blocked
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sanitizer.tool_allowlist import check_file_write, check_network_call, check_tool_call


# ---------------------------------------------------------------------------
# File write tests
# ---------------------------------------------------------------------------

def test_file_write_inside_project():
    ok, reason = check_file_write(ROOT / "artifacts" / "some_output.json")
    assert ok, f"Expected allowed, got blocked: {reason}"
    assert reason == ""
    print("PASS: test_file_write_inside_project")


def test_file_write_outside_project():
    ok, reason = check_file_write("C:/Users/james/Desktop/secrets.txt")
    assert not ok, "Expected blocked, got allowed"
    assert "write_outside_project" in reason
    print("PASS: test_file_write_outside_project")


def test_file_write_traversal_blocked():
    # Attempt to escape via path traversal
    traversal = ROOT / "artifacts" / ".." / ".." / ".." / "Desktop" / "x.txt"
    ok, reason = check_file_write(traversal)
    assert not ok, f"Expected blocked, got allowed (resolved: {Path(traversal).resolve()})"
    assert "write_outside_project" in reason
    print("PASS: test_file_write_traversal_blocked")


# ---------------------------------------------------------------------------
# Tool call tests
# ---------------------------------------------------------------------------

def test_tool_call_allowed():
    ok, reason = check_tool_call("nlu.intake.parse_goal")
    assert ok, f"Expected allowed, got blocked: {reason}"
    print("PASS: test_tool_call_allowed")


def test_tool_call_blocked():
    ok, reason = check_tool_call("some.unknown.external_tool")
    assert not ok, "Expected blocked, got allowed"
    assert "tool_not_allowlisted" in reason
    print("PASS: test_tool_call_blocked")


# ---------------------------------------------------------------------------
# Network call tests
# ---------------------------------------------------------------------------

def test_network_localhost_allowed():
    ok, reason = check_network_call("http://localhost:11434/api/embeddings")
    assert ok, f"Expected allowed, got blocked: {reason}"
    print("PASS: test_network_localhost_allowed")


def test_network_127_allowed():
    ok, reason = check_network_call("http://127.0.0.1:11434/api/chat")
    assert ok, f"Expected allowed, got blocked: {reason}"
    print("PASS: test_network_127_allowed")


def test_network_telegram_allowed():
    ok, reason = check_network_call("https://api.telegram.org/bot123/sendMessage")
    assert ok, f"Expected allowed, got blocked: {reason}"
    print("PASS: test_network_telegram_allowed")


def test_network_external_blocked():
    ok, reason = check_network_call("https://api.openai.com/v1/chat/completions")
    assert not ok, "Expected blocked, got allowed"
    assert "network_call_blocked" in reason
    print("PASS: test_network_external_blocked")


def test_network_arbitrary_https_blocked():
    ok, reason = check_network_call("https://example.com/data")
    assert not ok, "Expected blocked, got allowed"
    assert "network_call_blocked" in reason
    print("PASS: test_network_arbitrary_https_blocked")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_file_write_inside_project,
        test_file_write_outside_project,
        test_file_write_traversal_blocked,
        test_tool_call_allowed,
        test_tool_call_blocked,
        test_network_localhost_allowed,
        test_network_127_allowed,
        test_network_telegram_allowed,
        test_network_external_blocked,
        test_network_arbitrary_https_blocked,
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

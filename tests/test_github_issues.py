"""Tests for Sprint 5 — github_issues.py cadence logic.

Covers:
1. RED with no prior state → opens a new issue
2. RED within 24h of existing open issue → comments, no new issue
3. RED after 24h of existing open issue → opens fresh issue
4. GREEN with open issue → closes it
5. GREEN with no open issue → action=none
6. WARN with open issue → closes it (same as GREEN)
7. process_division_health: no github_repo in config → action=none
8. process_division_health: gh failure → action=error, no raise
9. State persisted after open: issue_number recorded
10. State persisted after close: state="closed" recorded
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import github_issues  # noqa: E402


REPO = "testorg/ai-holding-company"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_gh_state(tmp_path, monkeypatch):
    """Redirect GH_ISSUES_STATE to tmp_path so tests don't touch real state."""
    monkeypatch.setattr(github_issues, "GH_ISSUES_STATE", tmp_path / "gh_issues.json")
    yield


def _fake_gh_create(issue_number: int):
    """Return a mock CompletedProcess that mimics `gh issue create` output."""
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.stdout = f"https://github.com/{REPO}/issues/{issue_number}\n"
    mock.returncode = 0
    return mock


def _fake_gh_ok():
    mock = MagicMock(spec=subprocess.CompletedProcess)
    mock.stdout = ""
    mock.returncode = 0
    return mock


# ---------------------------------------------------------------------------
# 1. RED, no prior state → opens new issue
# ---------------------------------------------------------------------------

def test_red_no_prior_state_opens_issue():
    with patch.object(github_issues, "_gh", return_value=_fake_gh_create(42)) as mock_gh:
        result = github_issues.handle_division_result("trading", "critical", "bot down", REPO)

    assert result["action"] == "opened"
    assert result["issue_number"] == 42
    # _gh called once (issue create)
    mock_gh.assert_called_once()
    args = mock_gh.call_args[0][0]
    assert args[0] == "issue" and args[1] == "create"


# ---------------------------------------------------------------------------
# 2. RED within 24h of open issue → comment only
# ---------------------------------------------------------------------------

def test_red_within_24h_comments_on_existing():
    now = datetime.now(timezone.utc)
    state = {
        "trading": {
            "issue_number": 10,
            "created_at": (now - timedelta(hours=1)).isoformat(),
            "state": "open",
            "repo": REPO,
        }
    }
    github_issues._save_state(state)

    comment_response = _fake_gh_ok()
    with patch.object(github_issues, "_gh", return_value=comment_response) as mock_gh:
        result = github_issues.handle_division_result("trading", "critical", "still down", REPO)

    assert result["action"] == "commented"
    assert result["issue_number"] == 10
    args = mock_gh.call_args[0][0]
    assert args[0] == "issue" and args[1] == "comment"


# ---------------------------------------------------------------------------
# 3. RED after 24h of open issue → opens fresh issue
# ---------------------------------------------------------------------------

def test_red_after_24h_opens_fresh_issue():
    now = datetime.now(timezone.utc)
    state = {
        "trading": {
            "issue_number": 10,
            "created_at": (now - timedelta(hours=25)).isoformat(),
            "state": "open",
            "repo": REPO,
        }
    }
    github_issues._save_state(state)

    with patch.object(github_issues, "_gh", return_value=_fake_gh_create(99)) as mock_gh:
        result = github_issues.handle_division_result("trading", "critical", "down again", REPO)

    assert result["action"] == "opened"
    assert result["issue_number"] == 99
    args = mock_gh.call_args[0][0]
    assert args[0] == "issue" and args[1] == "create"


# ---------------------------------------------------------------------------
# 4. GREEN with open issue → closes it
# ---------------------------------------------------------------------------

def test_green_with_open_issue_closes_it():
    state = {
        "trading": {
            "issue_number": 55,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": "open",
            "repo": REPO,
        }
    }
    github_issues._save_state(state)

    with patch.object(github_issues, "_gh", return_value=_fake_gh_ok()) as mock_gh:
        result = github_issues.handle_division_result("trading", "info", "all good", REPO)

    assert result["action"] == "closed"
    assert result["issue_number"] == 55
    args = mock_gh.call_args[0][0]
    assert args[0] == "issue" and args[1] == "close"


# ---------------------------------------------------------------------------
# 5. GREEN with no open issue → none
# ---------------------------------------------------------------------------

def test_green_no_issue_is_noop():
    with patch.object(github_issues, "_gh") as mock_gh:
        result = github_issues.handle_division_result("trading", "info", "fine", REPO)

    assert result["action"] == "none"
    assert result["issue_number"] is None
    mock_gh.assert_not_called()


# ---------------------------------------------------------------------------
# 6. WARN with open issue → closes it
# ---------------------------------------------------------------------------

def test_warn_closes_open_issue():
    state = {
        "websites": {
            "issue_number": 7,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": "open",
            "repo": REPO,
        }
    }
    github_issues._save_state(state)

    with patch.object(github_issues, "_gh", return_value=_fake_gh_ok()):
        result = github_issues.handle_division_result("websites", "warn", "recovering", REPO)

    assert result["action"] == "closed"
    assert result["issue_number"] == 7


# ---------------------------------------------------------------------------
# 7. process_division_health: no github_repo → none
# ---------------------------------------------------------------------------

def test_process_no_repo_is_noop():
    health = {"division": "trading", "severity": "critical", "summary": "bad"}
    with patch.object(github_issues, "_gh") as mock_gh:
        result = github_issues.process_division_health(health, config={})

    assert result["action"] == "none"
    mock_gh.assert_not_called()


# ---------------------------------------------------------------------------
# 8. process_division_health: gh failure → action=error, no exception raised
# ---------------------------------------------------------------------------

def test_process_gh_failure_returns_error_action():
    health = {"division": "trading", "severity": "critical", "summary": "crash"}

    with patch.object(github_issues, "_gh", side_effect=subprocess.CalledProcessError(1, "gh")):
        result = github_issues.process_division_health(health, config={"github_repo": REPO})

    assert result["action"] == "error"
    assert "error" in result


# ---------------------------------------------------------------------------
# 9. State persisted after open
# ---------------------------------------------------------------------------

def test_state_persisted_after_open():
    with patch.object(github_issues, "_gh", return_value=_fake_gh_create(77)):
        github_issues.handle_division_result("commercial", "critical", "down", REPO)

    state = github_issues._load_state()
    assert "commercial" in state
    assert state["commercial"]["issue_number"] == 77
    assert state["commercial"]["state"] == "open"


# ---------------------------------------------------------------------------
# 10. State persisted after close
# ---------------------------------------------------------------------------

def test_state_persisted_after_close():
    state = {
        "commercial": {
            "issue_number": 77,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": "open",
            "repo": REPO,
        }
    }
    github_issues._save_state(state)

    with patch.object(github_issues, "_gh", return_value=_fake_gh_ok()):
        github_issues.handle_division_result("commercial", "info", "recovered", REPO)

    state = github_issues._load_state()
    assert state["commercial"]["state"] == "closed"
    assert "closed_at" in state["commercial"]

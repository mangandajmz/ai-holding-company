"""GitHub Issues cadence for AI Holding Company.

RED division event  → open a GH Issue (dedup: comment on existing if <24 h old).
GREEN/WARN division → close the open Issue for that division, if any.

Requires: `gh` CLI installed and `gh auth login` completed on the host.
Repo is read from config["github_repo"] (e.g. "org/ai-holding-company").

State tracked in state/gh_issues.json:
    {
        "trading": {
            "issue_number": 42,
            "created_at": "2026-05-01T12:00:00+00:00",
            "state": "open",       # "open" | "closed"
            "repo": "org/repo"
        },
        ...
    }

Usage:
    from github_issues import handle_division_result
    result = handle_division_result(
        division="trading",
        severity="critical",
        summary="Bot heartbeat stale for 45 min",
        repo="myorg/ai-holding-company",
    )
    # result: {"action": "opened"|"commented"|"closed"|"none", "issue_number": int | None}
"""
from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GH_ISSUES_STATE = ROOT / "state" / "gh_issues.json"
DEDUP_HOURS = 24

logger = logging.getLogger("github_issues")


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_state() -> dict:
    if not GH_ISSUES_STATE.exists():
        return {}
    try:
        return json.loads(GH_ISSUES_STATE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(state: dict) -> None:
    GH_ISSUES_STATE.parent.mkdir(parents=True, exist_ok=True)
    GH_ISSUES_STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# GitHub CLI wrappers — shell=False always
# ---------------------------------------------------------------------------

def _gh(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a `gh` subcommand. Raises CalledProcessError on non-zero exit."""
    cmd = ["gh"] + args
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=check,
        shell=False,  # R8: shell=False always
    )


def open_issue(division: str, title: str, body: str, repo: str) -> int:
    """Create a GitHub issue. Returns the issue number."""
    result = _gh(
        ["issue", "create", "--repo", repo, "--title", title, "--body", body]
    )
    # gh issue create prints the issue URL on stdout, e.g.:
    # https://github.com/org/repo/issues/42
    url = result.stdout.strip()
    try:
        issue_number = int(url.rstrip("/").rsplit("/", 1)[-1])
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"Could not parse issue number from gh output: {url!r}") from exc
    logger.info("Opened issue #%d for division %s", issue_number, division)
    return issue_number


def add_comment(issue_number: int, body: str, repo: str) -> None:
    """Add a comment to an existing issue."""
    _gh(["issue", "comment", str(issue_number), "--repo", repo, "--body", body])
    logger.info("Commented on issue #%d", issue_number)


def close_issue(issue_number: int, repo: str) -> None:
    """Close an open issue."""
    _gh(["issue", "close", str(issue_number), "--repo", repo])
    logger.info("Closed issue #%d", issue_number)


# ---------------------------------------------------------------------------
# Main cadence logic
# ---------------------------------------------------------------------------

def handle_division_result(
    division: str,
    severity: str,
    summary: str,
    repo: str,
) -> dict:
    """Apply the RED/GREEN issue cadence for one division health result.

    Args:
        division:  Division name, e.g. "trading".
        severity:  "critical" | "warn" | "info".
        summary:   Short human-readable description of the current state.
        repo:      GitHub repo in "owner/name" format.

    Returns:
        dict with keys:
            action       — "opened" | "commented" | "closed" | "none"
            issue_number — int if an issue was touched, else None
    """
    state = _load_state()
    entry: dict | None = state.get(division)
    now = datetime.now(timezone.utc)

    if severity == "critical":
        if entry and entry.get("state") == "open":
            # 24-hour dedup: comment on the existing issue instead of creating a new one
            try:
                created_at = datetime.fromisoformat(entry["created_at"])
            except (KeyError, ValueError):
                created_at = now - timedelta(hours=DEDUP_HOURS + 1)  # treat as old

            if now - created_at < timedelta(hours=DEDUP_HOURS):
                comment_body = (
                    f"🔴 Still RED at {now.isoformat(timespec='seconds')}\n\n{summary}"
                )
                add_comment(entry["issue_number"], comment_body, repo)
                return {"action": "commented", "issue_number": entry["issue_number"]}

            # Existing issue is too old; fall through and open a fresh one.

        title = f"[RED] {division.title()} division alert"
        body = (
            f"Division `{division}` entered a **critical** state.\n\n"
            f"{summary}\n\n"
            f"Detected: {now.isoformat(timespec='seconds')}"
        )
        issue_number = open_issue(division, title, body, repo)
        state[division] = {
            "issue_number": issue_number,
            "created_at": now.isoformat(),
            "state": "open",
            "repo": repo,
        }
        _save_state(state)
        return {"action": "opened", "issue_number": issue_number}

    # Non-critical: close the division's open issue if one exists
    if entry and entry.get("state") == "open":
        close_issue(entry["issue_number"], repo)
        state[division]["state"] = "closed"
        state[division]["closed_at"] = now.isoformat()
        _save_state(state)
        return {"action": "closed", "issue_number": entry["issue_number"]}

    return {"action": "none", "issue_number": None}


# ---------------------------------------------------------------------------
# Orchestrator integration helper
# ---------------------------------------------------------------------------

def process_division_health(health_result: dict, config: dict) -> dict:
    """Called by orchestrator after each division health run.

    Args:
        health_result: dict returned by _run_division_health(), must have
                       "division" and "severity" keys.
        config:        Top-level config dict; must have "github_repo" key.

    Returns:
        issue cadence result dict from handle_division_result().
    """
    # Support both flat {"github_repo": "..."} and nested {"company": {"github_repo": "..."}}
    repo = config.get("github_repo") or config.get("company", {}).get("github_repo", "")
    if not repo:
        logger.debug("github_repo not configured; skipping issue cadence.")
        return {"action": "none", "issue_number": None}

    division = health_result.get("division", "unknown")
    severity = health_result.get("severity", "info")
    summary = health_result.get("summary", "No summary available.")

    try:
        result = handle_division_result(division, severity, summary, repo)
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("GitHub Issues cadence failed for %s: %s", division, exc)
        result = {"action": "error", "issue_number": None, "error": str(exc)}

    return result

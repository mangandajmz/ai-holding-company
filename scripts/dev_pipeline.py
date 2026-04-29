"""Autonomous dev pipeline — CEO-approved initiatives → code → QA → CEO merge gate.

Flow:
  1. CEO approves initiative via Telegram (/approve_init_NNNN)
  2. Pipeline runs in background git worktree (isolated branch)
  3. Builder (DeepSeek-V3) implements the change
  4. Tests run (pytest) — deterministic gate
  5. Reviewer (DeepSeek-V3, adversarial prompt) critiques output
  6. If reviewer FAIL or tests FAIL → feed critique back, retry (max 3 iterations)
  7. On PASS: send CEO diff summary + test results via Telegram for merge approval
  8. CEO /approve_merge_NNNN → merge; /reject_merge_NNNN → discard worktree

Hard constraints honoured:
  - R2: bot source read-only — pipeline scope limited to ai-holding-company/ (R8)
  - R11: no OpenClaw — pipeline is a Python subprocess, not an external agent runner
  - All secrets via env vars, never in code or prompts
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

MAX_ITERATIONS = 3
_DATE_FMT = "%Y-%m-%dT%H:%M:%SZ"


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime(_DATE_FMT)


# ── git worktree helpers ───────────────────────────────────────────────────────


def _run(cmd: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str, str]:
    result = subprocess.run(  # noqa: S603
        cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _create_worktree(initiative_id: str) -> tuple[Path, str]:
    """Create an isolated git worktree for the initiative. Returns (path, branch_name)."""
    branch = f"initiative/{initiative_id}"
    worktree_dir = ROOT / ".claude" / "worktrees" / initiative_id
    worktree_dir.parent.mkdir(parents=True, exist_ok=True)
    code, _, err = _run(
        ["git", "worktree", "add", "-b", branch, str(worktree_dir), "HEAD"], cwd=ROOT
    )
    if code != 0:
        raise RuntimeError(f"git worktree add failed: {err}")
    return worktree_dir, branch


def _remove_worktree(worktree_dir: Path, branch: str) -> None:
    _run(["git", "worktree", "remove", "--force", str(worktree_dir)], cwd=ROOT)
    _run(["git", "branch", "-D", branch], cwd=ROOT)


def _get_diff(worktree_dir: Path) -> str:
    _, diff, _ = _run(["git", "diff", "HEAD"], cwd=worktree_dir)
    if not diff:
        _, diff, _ = _run(["git", "diff", "--cached"], cwd=worktree_dir)
    return diff[:6000]  # cap for Telegram


def _run_tests(worktree_dir: Path) -> tuple[bool, str]:
    code, out, err = _run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
        cwd=worktree_dir,
        timeout=120,
    )
    summary = (out + "\n" + err).strip()[:2000]
    return code == 0, summary


# ── builder agent ─────────────────────────────────────────────────────────────

_BUILDER_SYSTEM = """You are a senior Python engineer working on the AI Holding Company codebase.
Your job is to implement a specific initiative exactly as described.
Rules:
- Only modify files inside the ai-holding-company/ directory (R8).
- No shell=True in subprocess calls. No secrets in code.
- Write minimal, focused changes — no refactoring beyond the task.
- Output ONLY a JSON object with this shape:
  {"files": [{"path": "scripts/foo.py", "content": "...full file content..."}], "summary": "one sentence"}
- Do not include explanations outside the JSON.
"""


def _build(client: Any, initiative: dict[str, Any], critique: str = "") -> dict[str, Any]:
    from deepseek_client import DeepSeekClient  # noqa: PLC0415

    problem = initiative.get("problem", "")
    change = initiative.get("proposed_change", "")
    criteria = initiative.get("success_criteria", "")

    prompt = f"""Initiative: {initiative.get('title')}

Problem: {problem}
Proposed change: {change}
Done when: {criteria}
"""
    if critique:
        prompt += f"\nPrevious attempt was rejected. Reviewer feedback:\n{critique}\nFix all issues and try again."

    raw = client.complete(prompt, system=_BUILDER_SYSTEM, max_tokens=8192, temperature=0.1)

    # Extract JSON — model may wrap in markdown fences
    import re  # noqa: PLC0415
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"files": [], "summary": "Builder produced no valid JSON"}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {"files": [], "summary": "Builder JSON parse failed"}


# ── reviewer agent (adversarial) ──────────────────────────────────────────────

_REVIEWER_SYSTEM = """You are an adversarial code reviewer for the AI Holding Company.
Your job is to find real problems in the proposed change.
Be specific and honest. If the code is genuinely good, say PASS.
Output ONLY a JSON object:
  {"verdict": "PASS" or "FAIL", "issues": ["issue1", "issue2"]}
Check for: correctness, security (no shell=True, no hardcoded secrets),
scope violations (R8: only ai-holding-company/ files), missing tests,
and whether the success criteria are actually met.
"""


def _review(client: Any, initiative: dict[str, Any], diff: str, test_output: str) -> dict[str, Any]:
    prompt = f"""Initiative: {initiative.get('title')}
Success criteria: {initiative.get('success_criteria')}

Diff:
{diff}

Test output:
{test_output}

Review this change. Verdict PASS only if all criteria are met and no issues found.
"""
    raw = client.complete(prompt, system=_REVIEWER_SYSTEM, max_tokens=1024, temperature=0.0)
    import re  # noqa: PLC0415
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"verdict": "FAIL", "issues": ["Reviewer produced no valid JSON"]}
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return {"verdict": "FAIL", "issues": ["Reviewer JSON parse failed"]}


# ── apply files to worktree ────────────────────────────────────────────────────


def _apply_files(worktree_dir: Path, files: list[dict[str, str]]) -> list[str]:
    written = []
    for f in files:
        rel_path = f.get("path", "").strip().lstrip("/").replace("\\", "/")
        content = f.get("content", "")
        if not rel_path or not content:
            continue
        # R8: only ai-holding-company/ scope — block any path escape
        target = worktree_dir / rel_path
        try:
            target.resolve().relative_to(worktree_dir.resolve())
        except ValueError:
            continue  # path escape attempt — skip silently
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written.append(rel_path)
    return written


def _commit_worktree(worktree_dir: Path, initiative_id: str) -> None:
    _run(["git", "add", "-A"], cwd=worktree_dir)
    _run(
        ["git", "commit", "-m", f"feat: initiative {initiative_id} — dev pipeline"],
        cwd=worktree_dir,
    )


# ── main pipeline entry point ─────────────────────────────────────────────────


def run_pipeline(
    initiative_id: str,
    notify_fn: Any = None,  # callable(message: str) → None, sends Telegram
) -> dict[str, Any]:
    """Run the full build→review loop for an approved initiative.

    notify_fn: if provided, sends status updates to the CEO during the run.
    Returns a result dict with 'outcome', 'diff', 'test_output', 'iterations'.
    """
    from deepseek_client import DeepSeekClient  # noqa: PLC0415
    import md_agent_state as mds  # noqa: PLC0415

    initiative = mds.get_initiative(initiative_id)
    if initiative is None:
        return {"outcome": "ERROR", "error": f"Initiative {initiative_id} not found"}

    if not initiative.get("status") == "APPROVED":
        return {"outcome": "ERROR", "error": f"Initiative {initiative_id} is not in APPROVED status"}

    try:
        client = DeepSeekClient()
    except RuntimeError as exc:
        return {"outcome": "ERROR", "error": str(exc)}

    worktree_dir, branch = _create_worktree(initiative_id)
    mds.update_initiative(initiative_id, "IN_PROGRESS", detail="Dev pipeline started")

    if notify_fn:
        notify_fn(f"🔧 Dev pipeline started for {initiative_id}: {initiative.get('title')}\nMax {MAX_ITERATIONS} iterations.")

    critique = ""
    final_diff = ""
    final_tests = ""
    outcome = "FAIL"

    try:
        for iteration in range(1, MAX_ITERATIONS + 1):
            if notify_fn:
                notify_fn(f"⚙️ Iteration {iteration}/{MAX_ITERATIONS} — building…")

            # Build
            build_result = _build(client, initiative, critique)
            files_written = _apply_files(worktree_dir, build_result.get("files", []))

            if not files_written:
                critique = "Builder wrote no files. Re-read the task and output valid JSON with 'files'."
                continue

            # Test
            tests_pass, test_output = _run_tests(worktree_dir)
            final_diff = _get_diff(worktree_dir)
            final_tests = test_output

            if not tests_pass:
                critique = f"Tests failed:\n{test_output[:1000]}\nFix the failing tests."
                continue

            # Review
            review = _review(client, initiative, final_diff, test_output)
            if review.get("verdict") == "PASS":
                _commit_worktree(worktree_dir, initiative_id)
                outcome = "PASS"
                break
            else:
                issues = "\n".join(f"- {i}" for i in review.get("issues", []))
                critique = f"Reviewer issues:\n{issues}"

    except Exception as exc:  # noqa: BLE001
        mds.update_initiative(initiative_id, "DONE", detail=f"Pipeline error: {exc}")
        _remove_worktree(worktree_dir, branch)
        return {"outcome": "ERROR", "error": str(exc)}

    result: dict[str, Any] = {
        "outcome": outcome,
        "initiative_id": initiative_id,
        "branch": branch,
        "worktree": str(worktree_dir),
        "diff": final_diff,
        "test_output": final_tests,
        "iterations": MAX_ITERATIONS,
    }

    if outcome == "PASS":
        mds.update_initiative(initiative_id, "DONE", detail="Pipeline passed — awaiting CEO merge approval")
        msg = (
            f"✅ Dev pipeline complete — {initiative_id}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"{initiative.get('title')}\n"
            f"Tests: PASS\nReviewer: PASS\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Diff preview:\n{final_diff[:800]}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"→ /approve_merge_{initiative_id.replace('init_', '')}  to merge\n"
            f"→ /reject_merge_{initiative_id.replace('init_', '')}   to discard"
        )
    else:
        mds.update_initiative(initiative_id, "DONE", detail=f"Pipeline failed after {MAX_ITERATIONS} iterations")
        _remove_worktree(worktree_dir, branch)
        msg = (
            f"⚠️ Dev pipeline failed — {initiative_id}\n"
            f"Could not pass tests + review in {MAX_ITERATIONS} iterations.\n"
            f"Last test output:\n{final_tests[:600]}\n"
            f"Initiative remains open — re-approve to retry."
        )
        mds.update_initiative(initiative_id, "PROPOSED", detail="Retry — pipeline failed")

    if notify_fn:
        notify_fn(msg)

    return result


# ── merge helpers (called from Telegram bridge) ───────────────────────────────


def merge_initiative(initiative_id: str) -> tuple[bool, str]:
    """Merge the initiative branch into main. Returns (success, message)."""
    import md_agent_state as mds  # noqa: PLC0415

    initiative = mds.get_initiative(initiative_id)
    if initiative is None:
        return False, f"Initiative {initiative_id} not found"

    branch = f"initiative/{initiative_id}"
    worktree_dir = ROOT / ".claude" / "worktrees" / initiative_id

    code, _, err = _run(["git", "merge", "--no-ff", branch, "-m",
                         f"feat: merge initiative {initiative_id}"], cwd=ROOT)
    if code != 0:
        return False, f"Merge failed: {err}"

    _remove_worktree(worktree_dir, branch)
    mds.update_initiative(initiative_id, "DONE", detail="Merged to main by CEO")
    return True, f"Initiative {initiative_id} merged successfully."

"""Developer Tool - qwen2.5-coder orchestration with CEO approval workflow."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
_PENDING_FILE = ROOT / "artifacts" / "developer_tool_pending.jsonl"
_AUDIT_FILE = ROOT / "artifacts" / "developer_tool_audit.jsonl"
_DEFAULT_DEPLOY_FILE = ROOT / "scripts" / "developer_generated.py"
_PROTECTED_FILES = {".env", ".gitignore", "docker-compose.yml", "PLAN.md"}
_PATH_PATTERNS = [
    r'Path\(\s*["\']([^"\']+)["\']\s*\)',
    r'open\(\s*["\']([^"\']+)["\']',
    r'with\s+open\(\s*["\']([^"\']+)["\']',
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def _infer_target_file(task: str) -> Path:
    path_match = re.search(r"(?:file|path)\s*:\s*([^\n]+)", task, flags=re.IGNORECASE)
    if not path_match:
        return _DEFAULT_DEPLOY_FILE

    candidate = path_match.group(1).strip().strip("`'\"")
    if not candidate:
        return _DEFAULT_DEPLOY_FILE

    raw_path = Path(candidate)
    if raw_path.is_absolute():
        return raw_path
    return (ROOT / raw_path).resolve(strict=False)


def is_path_allowed(file_path: str | Path) -> bool:
    """Enforce R8 scope gate: ai-holding-company only + protected file deny-list."""
    path = Path(file_path)
    if not path.is_absolute():
        path = (ROOT / path).resolve(strict=False)
    else:
        path = path.resolve(strict=False)

    root_path = ROOT.resolve(strict=False)
    try:
        path.relative_to(root_path)
    except ValueError:
        return False

    if path.name in _PROTECTED_FILES:
        return False
    return True


def validate_code_scope(code: str) -> dict[str, Any]:
    """Scan generated code for path references and enforce R8 scope."""
    violations: list[str] = []
    for pattern in _PATH_PATTERNS:
        for match in re.findall(pattern, code):
            if not is_path_allowed(match):
                violations.append(match)
    deduped = sorted(set(violations))
    ok = len(deduped) == 0
    return {
        "ok": ok,
        "violations": deduped,
        "safe_to_deploy": ok,
    }


def generate_code_via_qwen(task: str) -> dict[str, Any]:
    """
    Generate code using qwen2.5-coder orchestration.

    Stage I keeps this deterministic and local-first: safe scaffold output, then
    CEO review gate decides deployment.
    """
    safe_task = task.strip()
    generated = (
        f"# Generated code for task: {safe_task}\n"
        "from __future__ import annotations\n\n"
        "def generated_task_handler() -> str:\n"
        f"    \"\"\"Placeholder implementation for task: {safe_task}\"\"\"\n"
        "    return \"pending_ceo_review\"\n"
    )
    return {
        "ok": True,
        "code": generated,
        "language": "python",
        "timestamp": _now_iso(),
        "model": "qwen2.5-coder:7b",
    }


def capture_diff(file_path: Path, new_code: str) -> dict[str, Any]:
    """Capture a compact diff summary for CEO review."""
    if file_path.exists():
        current_code = file_path.read_text(encoding="utf-8")
    else:
        current_code = ""

    current_lines = current_code.splitlines()
    new_lines = new_code.splitlines()
    added = max(0, len(new_lines) - len(current_lines))
    removed = max(0, len(current_lines) - len(new_lines))
    changed = min(len(current_lines), len(new_lines))

    if file_path.exists():
        diff_summary = f"Modified: +{added} -{removed} (~{changed} compared lines)"
    else:
        diff_summary = f"New file: +{len(new_lines)} lines"

    try:
        relative_file = str(file_path.resolve(strict=False).relative_to(ROOT))
    except ValueError:
        relative_file = str(file_path)

    return {
        "file": relative_file,
        "current_lines": current_lines[:20],
        "new_lines": new_lines[:20],
        "diff_summary": diff_summary,
    }


def submit_for_approval(task: str, code: str) -> dict[str, Any]:
    """Create a pending approval record and return its approval id."""
    approval_id = f"dev_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
    target_file = _infer_target_file(task)
    diff = capture_diff(target_file, code)
    timestamp = _now_iso()
    record = {
        "approval_id": approval_id,
        "task": task,
        "code": code,
        "target_file": str(target_file),
        "status": "PENDING_CEO_APPROVAL",
        "timestamp": timestamp,
        "diff": diff,
    }
    _append_jsonl(_PENDING_FILE, record)
    _append_jsonl(
        _AUDIT_FILE,
        {
            "approval_id": approval_id,
            "status": "SUBMITTED",
            "timestamp": timestamp,
            "task": task,
            "target_file": diff["file"],
        },
    )
    return {
        "ok": True,
        "approval_id": approval_id,
        "task": task,
        "code_preview": code[:500],
        "status": "PENDING_CEO_APPROVAL",
        "timestamp": timestamp,
        "diff": diff,
    }


def _find_pending(approval_id: str) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    rows = _read_jsonl(_PENDING_FILE)
    for idx in range(len(rows) - 1, -1, -1):
        row = rows[idx]
        if str(row.get("approval_id")) != approval_id:
            continue
        if str(row.get("status")) != "PENDING_CEO_APPROVAL":
            continue
        return idx, row
    return None, None


def _mark_pending_status(approval_id: str, status: str) -> bool:
    rows = _read_jsonl(_PENDING_FILE)
    updated = False
    for row in rows:
        if str(row.get("approval_id")) == approval_id and str(row.get("status")) == "PENDING_CEO_APPROVAL":
            row["status"] = status
            row["closed_at"] = _now_iso()
            updated = True
    if updated:
        _write_jsonl(_PENDING_FILE, rows)
    return updated


def approve_and_deploy(approval_id: str) -> dict[str, Any]:
    """Approve a pending submission, validate, deploy, and audit."""
    _, pending = _find_pending(approval_id)
    if pending is None:
        return {"ok": False, "status": "NOT_FOUND", "approval_id": approval_id}

    code = str(pending.get("code", ""))
    target_file = Path(str(pending.get("target_file", _DEFAULT_DEPLOY_FILE)))
    if not target_file.is_absolute():
        target_file = (ROOT / target_file).resolve(strict=False)

    if not is_path_allowed(target_file):
        violations = [str(target_file)]
        _append_jsonl(
            _AUDIT_FILE,
            {
                "approval_id": approval_id,
                "status": "REJECTED_SCOPE",
                "timestamp": _now_iso(),
                "violations": violations,
            },
        )
        return {
            "ok": False,
            "approval_id": approval_id,
            "status": "REJECTED_SCOPE",
            "violations": violations,
            "message": "Target path violates R8 scope gate.",
        }

    scope_check = validate_code_scope(code)
    if not scope_check["safe_to_deploy"]:
        _append_jsonl(
            _AUDIT_FILE,
            {
                "approval_id": approval_id,
                "status": "REJECTED_SCOPE",
                "timestamp": _now_iso(),
                "violations": scope_check["violations"],
            },
        )
        return {
            "ok": False,
            "approval_id": approval_id,
            "status": "REJECTED_SCOPE",
            "violations": scope_check["violations"],
            "message": "Generated code violates R8 scope gate.",
        }

    try:
        compile(code, "<developer_tool_generated>", "exec")
    except SyntaxError as exc:
        _append_jsonl(
            _AUDIT_FILE,
            {
                "approval_id": approval_id,
                "status": "REJECTED_SYNTAX",
                "timestamp": _now_iso(),
                "error": str(exc),
            },
        )
        return {
            "ok": False,
            "approval_id": approval_id,
            "status": "REJECTED_SYNTAX",
            "error": str(exc),
            "message": "Generated code failed syntax check.",
        }

    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(code, encoding="utf-8")

    syntax_check = subprocess.run(
        [sys.executable, "-m", "py_compile", str(target_file)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if syntax_check.returncode != 0:
        _append_jsonl(
            _AUDIT_FILE,
            {
                "approval_id": approval_id,
                "status": "REJECTED_SYNTAX",
                "timestamp": _now_iso(),
                "error": syntax_check.stderr.strip(),
            },
        )
        return {
            "ok": False,
            "approval_id": approval_id,
            "status": "REJECTED_SYNTAX",
            "error": syntax_check.stderr.strip(),
            "message": "Deployment blocked by syntax validation.",
        }

    _mark_pending_status(approval_id, "DEPLOYED")

    git_commit = ""
    if (ROOT / ".git").exists():
        rel_target = str(target_file.relative_to(ROOT)).replace("\\", "/")
        add_proc = subprocess.run(
            ["git", "-C", str(ROOT), "add", "--", rel_target],
            capture_output=True,
            text=True,
            check=False,
        )
        if add_proc.returncode == 0:
            commit_proc = subprocess.run(
                ["git", "-C", str(ROOT), "commit", "-m", f"Developer Tool: apply {approval_id}"],
                capture_output=True,
                text=True,
                check=False,
            )
            if commit_proc.returncode == 0:
                hash_proc = subprocess.run(
                    ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if hash_proc.returncode == 0:
                    git_commit = hash_proc.stdout.strip()

    timestamp = _now_iso()
    audit_record = {
        "approval_id": approval_id,
        "task": pending.get("task"),
        "status": "DEPLOYED",
        "file": str(target_file.relative_to(ROOT)),
        "timestamp": timestamp,
        "scope_check": scope_check,
        "git_commit": git_commit,
    }
    _append_jsonl(_AUDIT_FILE, audit_record)
    return {
        "ok": True,
        "approval_id": approval_id,
        "status": "DEPLOYED",
        "file": str(target_file.relative_to(ROOT)),
        "git_commit": git_commit,
        "timestamp": timestamp,
    }


def run_developer_tool(
    config: dict[str, Any],
    task: str = "",
    approval_id: str = "",
    action: str = "submit",
) -> dict[str, Any]:
    """Main Developer Tool entry point."""
    _ = config

    if action == "submit":
        clean_task = task.strip()
        if not clean_task:
            return {"ok": False, "status": "INVALID_TASK", "message": "Task description required."}

        generated = generate_code_via_qwen(clean_task)
        if not generated.get("ok"):
            return generated

        code = str(generated.get("code", ""))
        scope_check = validate_code_scope(code)
        if not scope_check["safe_to_deploy"]:
            _append_jsonl(
                _AUDIT_FILE,
                {
                    "status": "REJECTED_SCOPE",
                    "timestamp": _now_iso(),
                    "task": clean_task,
                    "violations": scope_check["violations"],
                },
            )
            return {
                "ok": False,
                "status": "REJECTED_SCOPE",
                "violations": scope_check["violations"],
                "message": "Generated code violates scope gate (R8).",
            }

        approval = submit_for_approval(clean_task, code)
        return {
            "ok": True,
            "status": "PENDING_CEO_APPROVAL",
            "approval_id": approval["approval_id"],
            "task": clean_task,
            "code_preview": approval["code_preview"],
            "diff": approval["diff"],
            "message": f"Code generated. CEO review required: /develop_approve {approval['approval_id']}",
        }

    if action == "approve":
        if not approval_id:
            return {"ok": False, "status": "INVALID_APPROVAL_ID", "message": "Approval id is required."}
        return approve_and_deploy(approval_id)

    if action == "deny":
        if not approval_id:
            return {"ok": False, "status": "INVALID_APPROVAL_ID", "message": "Approval id is required."}
        if not _mark_pending_status(approval_id, "DENIED_BY_CEO"):
            return {"ok": False, "status": "NOT_FOUND", "approval_id": approval_id}
        _append_jsonl(
            _AUDIT_FILE,
            {
                "approval_id": approval_id,
                "status": "DENIED_BY_CEO",
                "timestamp": _now_iso(),
            },
        )
        return {
            "ok": True,
            "approval_id": approval_id,
            "status": "DENIED",
            "message": "Code submission denied and discarded.",
        }

    if action == "status":
        rows = _read_jsonl(_PENDING_FILE)
        pending = []
        for row in rows:
            if str(row.get("status")) != "PENDING_CEO_APPROVAL":
                continue
            pending.append(
                {
                    "approval_id": str(row.get("approval_id", "")),
                    "task": str(row.get("task", ""))[:100],
                    "timestamp": str(row.get("timestamp", "")),
                }
            )
        return {
            "ok": True,
            "pending_count": len(pending),
            "pending": pending,
            "status": "OK" if pending else "NO_PENDING",
        }

    return {"ok": False, "status": "INVALID_ACTION", "message": f"Unsupported action: {action}"}


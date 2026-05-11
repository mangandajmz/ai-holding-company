from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .db import ROOT
from .views import render_status_text, work_status
from .work_items import block_work_item, done_work_item, list_work_items, start_work_item


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
    except ValueError:
        return False
    return True


def _resolve_review_markdown_path(item: dict[str, Any]) -> Path | None:
    metadata = item.get("metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    repo_path = str(metadata.get("repo_path", "")).strip()
    if repo_path:
        candidate = (ROOT / repo_path).resolve()
        if candidate.suffix.lower() == ".md" and _is_relative_to(candidate, ROOT.resolve()) and candidate.exists():
            return candidate

    scan_root = str(metadata.get("scan_root", "")).strip()
    rel_path = str(metadata.get("path", "")).strip()
    if scan_root and rel_path:
        root = Path(scan_root).resolve()
        candidate = (root / rel_path).resolve()
        if candidate.suffix.lower() == ".md" and _is_relative_to(candidate, root) and candidate.exists():
            return candidate
    return None


def _review_markdown_summary(path: Path, text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    heading = next((line.lstrip("#").strip() for line in lines if line.startswith("#")), path.stem)
    status = next((line for line in lines if "status" in line.lower()), "Status: not found")
    checked = sum(1 for line in lines if line.startswith("- [x]") or line.startswith("- [X]"))
    unchecked = sum(1 for line in lines if line.startswith("- [ ]"))
    substantive = [
        line
        for line in lines
        if line
        and not line.startswith("#")
        and not line.startswith("- [")
        and "READY FOR MA REVIEW" not in line.upper()
        and "READY FOR REVIEW" not in line.upper()
    ]
    excerpts = substantive[:5]
    summary_lines = [
        f"Review artifact summarized: {path.name}",
        f"Heading: {heading}",
        status,
        f"Checklist: {checked} checked, {unchecked} open",
    ]
    if excerpts:
        summary_lines.append("Key lines:")
        summary_lines.extend(f"- {line[:220]}" for line in excerpts)
    return "\n".join(summary_lines)


def run_next_work_item(conn: sqlite3.Connection) -> dict[str, Any]:
    approved = list_work_items(conn, statuses=["APPROVED"])
    if not approved:
        return {"ok": True, "ran": False, "message": "No approved work items are ready to run.", "item": None}

    item = approved[0]
    started = start_work_item(conn, str(item["id"]), note="Worker picked up approved work.")
    executor = str(started.get("metadata", {}).get("executor", "")).strip()
    if executor == "ledger_status_snapshot":
        status = work_status(conn)
        text = render_status_text(status)
        done = done_work_item(
            conn,
            str(started["id"]),
            result="Ledger status snapshot generated.",
            evidence=text,
        )
        return {
            "ok": True,
            "ran": True,
            "outcome": "done",
            "executor": executor,
            "item": done,
        }

    if executor == "review_markdown_artifact":
        path = _resolve_review_markdown_path(started)
        if path is None:
            reason = "Review markdown artifact path is missing, unsafe, or no longer exists."
            blocked = block_work_item(conn, str(started["id"]), reason)
            return {
                "ok": True,
                "ran": True,
                "outcome": "blocked",
                "executor": executor,
                "item": blocked,
                "reason": reason,
            }
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            reason = f"Review markdown artifact could not be read: {exc}"
            blocked = block_work_item(conn, str(started["id"]), reason)
            return {
                "ok": True,
                "ran": True,
                "outcome": "blocked",
                "executor": executor,
                "item": blocked,
                "reason": reason,
            }
        evidence = _review_markdown_summary(path, text)
        done = done_work_item(
            conn,
            str(started["id"]),
            result="Review artifact summarized for owner decision record.",
            evidence=evidence,
        )
        return {
            "ok": True,
            "ran": True,
            "outcome": "done",
            "executor": executor,
            "item": done,
        }

    reason = (
        f"No automated executor is registered for type={started.get('type')} "
        f"source={started.get('source')}."
    )
    blocked = block_work_item(conn, str(started["id"]), reason)
    return {
        "ok": True,
        "ran": True,
        "outcome": "blocked",
        "executor": executor or None,
        "item": blocked,
        "reason": reason,
    }

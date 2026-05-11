"""Portfolio retro weekly skill wrapper built from stored local artifacts."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from org_truth_retriever import ROOT


SKILL_NAME = "portfolio-retro-weekly"
ISSUE_STATUSES = {"AMBER", "BLOCKED", "RED", "YELLOW"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _rel(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _latest_skill_outputs(root: Path) -> list[dict[str, Any]]:
    skills_dir = root / "reports" / "skills"
    if not skills_dir.exists():
        return []
    outputs: list[dict[str, Any]] = []
    for path in sorted(skills_dir.glob("*/latest.json")):
        if path.parent.name == SKILL_NAME:
            continue
        payload = _read_json(path)
        if not payload:
            continue
        skill = str(payload.get("skill") or path.parent.name).strip()
        status = str(payload.get("status") or "UNKNOWN").upper()
        outputs.append(
            {
                "skill": skill,
                "status": status,
                "owner_need": str(payload.get("owner_need") or "none").strip(),
                "brief": str(payload.get("brief") or "").strip(),
                "source": _rel(root, path),
            }
        )
    return outputs


def _approval_metrics(root: Path) -> tuple[int, int, str]:
    path = root / "state" / "board_approval_decisions.json"
    payload = _read_json(path)
    if not payload:
        return 0, 0, ""
    snapshot = payload.get("board_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    approvals = snapshot.get("approvals", [])
    decisions = payload.get("decisions", {})
    pending_count = len(approvals) if isinstance(approvals, list) else 0
    decisions_count = len(decisions) if isinstance(decisions, dict) else 0
    return pending_count, decisions_count, _rel(root, path)


def _open_issues(skill_outputs: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues = [item for item in skill_outputs if item["status"] in ISSUE_STATUSES]
    issues.sort(key=lambda item: (item["status"] != "BLOCKED", item["skill"]))
    return [
        {
            "skill": str(item["skill"]),
            "status": str(item["status"]),
            "brief": str(item["brief"]),
            "source": str(item["source"]),
        }
        for item in issues
    ]


def _overall_status(skill_outputs: list[dict[str, Any]]) -> str:
    if not skill_outputs:
        return "BLOCKED"
    statuses = {str(item["status"]).upper() for item in skill_outputs}
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "RED" in statuses:
        return "RED"
    if statuses.intersection({"AMBER", "YELLOW"}):
        return "AMBER"
    return "GREEN"


def _owner_need(skill_outputs: list[dict[str, Any]], pending_approvals_count: int) -> str:
    if pending_approvals_count > 0:
        return "approve"
    if any(str(item.get("owner_need", "")).lower() == "approve" for item in skill_outputs):
        return "approve"
    return "none"


def _brief(status: str, skill_outputs: list[dict[str, Any]], open_issues: list[dict[str, str]]) -> str:
    if not skill_outputs:
        return "Portfolio retro is BLOCKED. No skill outputs found under reports/skills/."
    if open_issues:
        first = open_issues[0]
        return (
            f"Portfolio retro is {status}. {len(open_issues)} unresolved issue(s) remain, "
            f"led by {first['skill']}: {first['brief']}"
        )
    return f"Portfolio retro is GREEN. {len(skill_outputs)} skill output(s) are current and no unresolved issues were found."


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Portfolio Retro Weekly",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        f"Owner need: {payload['owner_need']}",
        "",
        "## Brief",
        "",
        payload["brief"],
        "",
        "## Skill Outputs",
        "",
    ]
    for item in payload["skill_outputs"]:
        lines.append(f"- {item['skill']}: {item['status']} - {item['brief']}")
    if not payload["skill_outputs"]:
        lines.append("- No skill outputs found.")
    lines.extend(["", "## Open Issues", ""])
    for item in payload["open_issues"]:
        lines.append(f"- {item['skill']}: {item['status']} - {item['brief']}")
    if not payload["open_issues"]:
        lines.append("- No open issues found.")
    lines.extend(["", "## Metrics", ""])
    for key, value in payload["metrics"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Sources", ""])
    for source in payload["sources"]:
        lines.append(f"- `{source}`")
    if not payload["sources"]:
        lines.append("- No current sources found.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_portfolio_retro_weekly(root: Path | str = ROOT) -> dict[str, Any]:
    """Write a weekly retro artifact from current local skill outputs."""

    root_path = Path(root)
    skill_outputs = _latest_skill_outputs(root_path)
    pending_approvals_count, decisions_logged_count, approvals_source = _approval_metrics(root_path)
    issues = _open_issues(skill_outputs)
    status = _overall_status(skill_outputs)
    stamp = _utc_stamp()
    markdown_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.md"
    json_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.json"
    latest_md_rel = Path("reports") / "skills" / SKILL_NAME / "latest.md"
    latest_json_rel = Path("reports") / "skills" / SKILL_NAME / "latest.json"
    sources = [item["source"] for item in skill_outputs]
    if approvals_source:
        sources.append(approvals_source)

    payload: dict[str, Any] = {
        "ok": True,
        "skill": SKILL_NAME,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "owner_need": _owner_need(skill_outputs, pending_approvals_count),
        "brief": _brief(status, skill_outputs, issues),
        "skill_outputs": skill_outputs,
        "open_issues": issues,
        "metrics": {
            "skill_outputs_count": len(skill_outputs),
            "unresolved_issues_count": len(issues),
            "pending_approvals_count": pending_approvals_count,
            "decisions_logged_count": decisions_logged_count,
        },
        "sources": sources,
        "markdown_path": str(markdown_rel).replace("\\", "/"),
        "json_path": str(json_rel).replace("\\", "/"),
    }
    _write_markdown(root_path / markdown_rel, payload)
    _write_json(root_path / json_rel, payload)
    _write_markdown(root_path / latest_md_rel, payload)
    _write_json(root_path / latest_json_rel, payload)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate portfolio retro weekly skill artifacts.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    print(json.dumps(run_portfolio_retro_weekly(root=Path(args.root)), indent=2))


if __name__ == "__main__":
    main()

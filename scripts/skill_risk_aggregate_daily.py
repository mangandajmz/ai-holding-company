"""Risk aggregate daily skill wrapper built on stored company truth."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chief_of_staff import answer_company_question
from org_truth_retriever import ROOT, collect_truth_bundle


SKILL_NAME = "risk-aggregate-daily"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Risk Aggregate Daily",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        f"Owner need: {payload['owner_need']}",
        "",
        "## Brief",
        "",
        payload["brief"],
        "",
        "## Sources",
        "",
    ]
    sources = payload.get("sources", [])
    if sources:
        lines.extend(f"- `{source}`" for source in sources)
    else:
        lines.append("- No current sources found.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_risk_aggregate_daily(root: Path | str = ROOT) -> dict[str, Any]:
    """Create a natural daily risk brief plus structured sidecar."""

    root_path = Path(root)
    bundle = collect_truth_bundle(root_path)
    answer = answer_company_question("What needs me today?", root=root_path)
    generated_at = datetime.now(timezone.utc).isoformat()
    stamp = _utc_stamp()
    report_dir = root_path / "reports" / "skills" / SKILL_NAME
    markdown_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.md"
    json_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.json"
    latest_md_rel = Path("reports") / "skills" / SKILL_NAME / "latest.md"
    latest_json_rel = Path("reports") / "skills" / SKILL_NAME / "latest.json"

    payload: dict[str, Any] = {
        "ok": True,
        "skill": SKILL_NAME,
        "generated_at_utc": generated_at,
        "status": bundle.company_status,
        "owner_need": answer["owner_need"],
        "truth_state": answer["truth_state"],
        "brief": answer["answer"],
        "sources": answer["sources"],
        "pending_approvals_count": len(bundle.pending_approvals),
        "approved_awaiting_execution_count": len(bundle.approved_awaiting_execution),
        "markdown_path": str(markdown_rel).replace("\\", "/"),
        "json_path": str(json_rel).replace("\\", "/"),
    }

    _write_markdown(root_path / markdown_rel, payload)
    _write_json(root_path / json_rel, payload)
    _write_markdown(root_path / latest_md_rel, payload)
    _write_json(root_path / latest_json_rel, payload)
    report_dir.mkdir(parents=True, exist_ok=True)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate risk aggregate daily skill artifacts.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    print(json.dumps(run_risk_aggregate_daily(root=Path(args.root)), indent=2))


if __name__ == "__main__":
    main()

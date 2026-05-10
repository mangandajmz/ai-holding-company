"""Backtest review guardrail built from local MT5 research evidence."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from org_truth_retriever import ROOT


SKILL_NAME = "backtest-review"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_json(root: Path, folder: Path, pattern: str) -> Path | None:
    target = root / folder
    if not target.exists():
        return None
    candidates = [path for path in target.glob(pattern) if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0


def _decision_counts(review_results: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in review_results:
        if not isinstance(item, dict):
            continue
        decision = str(item.get("decision", "")).upper()
        if not decision:
            continue
        counts[decision] = counts.get(decision, 0) + 1
    return counts


def _research_metrics(research: dict[str, Any]) -> dict[str, Any]:
    summary = research.get("summary", {})
    validation = research.get("validation", {})
    review_results = research.get("review_results", [])
    if not isinstance(summary, dict):
        summary = {}
    if not isinstance(validation, dict):
        validation = {}
    if not isinstance(review_results, list):
        review_results = []

    counts = _decision_counts(review_results)
    selected = _as_int(summary.get("selected_for_review")) or len(review_results)
    approved = _as_int(summary.get("approved")) or counts.get("APPROVE", 0)
    rejected = _as_int(summary.get("rejected")) or counts.get("REJECT", 0)
    approve_blocked = counts.get("APPROVE_BLOCKED", 0)
    pass_rate = round((approved / selected) * 100, 1) if selected else 0.0
    return {
        "selected_for_review": selected,
        "approved_count": approved,
        "rejected_count": rejected,
        "approve_blocked_count": approve_blocked,
        "with_out_of_sample": _as_int(validation.get("with_out_of_sample")),
        "with_walk_forward": _as_int(validation.get("with_walk_forward")),
        "overfit_flagged": _as_int(validation.get("overfit_flagged")),
        "pass_unchanged_rate_pct": pass_rate,
    }


def _data_quality_status(root: Path) -> tuple[str, str, str]:
    path = root / "reports" / "skills" / "data-quality-daily" / "latest.json"
    if not path.exists():
        return "MISSING", "No data-quality guardrail artifact found.", ""
    payload = _read_json(path)
    status = str(payload.get("status", "UNKNOWN")).upper()
    brief = str(payload.get("brief", "Data-quality artifact has no brief."))
    return status, brief, _relative(root, path)


def _status_and_reasons(metrics: dict[str, Any], data_quality_status: str) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if data_quality_status != "GREEN":
        reasons.append(f"Data quality is {data_quality_status}.")
    if metrics["approved_count"] <= 0:
        reasons.append("No reviewed candidate is approved.")
    if metrics["with_out_of_sample"] <= 0:
        reasons.append("No out-of-sample validation is recorded.")
    if metrics["with_walk_forward"] <= 0:
        reasons.append("No walk-forward validation is recorded.")
    if metrics["overfit_flagged"] > 0:
        reasons.append(f"{metrics['overfit_flagged']} candidate(s) are flagged for overfit risk.")
    if reasons:
        return "BLOCKED", reasons
    return "PASS_FOR_OWNER_APPROVAL", ["Evidence clears the local guardrail, but owner approval is still required."]


def _brief(status: str, metrics: dict[str, Any], reasons: list[str]) -> str:
    if status == "BLOCKED":
        return (
            "Backtest review is BLOCKED. "
            f"Latest MT5 research selected {metrics['selected_for_review']} candidate(s), "
            f"approved {metrics['approved_count']}, rejected {metrics['rejected_count']}, "
            f"and has {metrics['with_out_of_sample']} out-of-sample / "
            f"{metrics['with_walk_forward']} walk-forward evidence. {reasons[0]}"
        )
    return (
        "Backtest review passed the local evidence gate for owner approval. "
        f"{metrics['approved_count']} of {metrics['selected_for_review']} reviewed candidate(s) "
        "passed with data-quality, out-of-sample, and walk-forward evidence."
    )


def _required_next_action(status: str) -> str:
    if status == "BLOCKED":
        return "Do not move any reviewed strategy to forward-test; fix the evidence gaps and rerun review."
    return "Request owner approval; this Guardrail skill cannot approve live or forward trading."


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Backtest Review",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        f"Autonomy: {payload['autonomy']}",
        f"Owner need: {payload['owner_need']}",
        "",
        "## Brief",
        "",
        payload["brief"],
        "",
        "## Required Next Action",
        "",
        payload["required_next_action"],
        "",
        "## Metrics",
        "",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Evidence Gaps", ""])
    for reason in payload["reasons"]:
        lines.append(f"- {reason}")
    lines.extend(["", "## Sources", ""])
    for source in payload["sources"]:
        lines.append(f"- `{source}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _blocked_without_research(root_path: Path) -> dict[str, Any]:
    stamp = _utc_stamp()
    markdown_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.md"
    json_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.json"
    payload: dict[str, Any] = {
        "ok": True,
        "skill": SKILL_NAME,
        "autonomy": "Guardrail",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "owner_need": "none",
        "brief": "Backtest review is BLOCKED. No MT5 research artifact found.",
        "required_next_action": "Create or locate a local MT5 research artifact before review.",
        "metrics": {
            "selected_for_review": 0,
            "approved_count": 0,
            "rejected_count": 0,
            "approve_blocked_count": 0,
            "with_out_of_sample": 0,
            "with_walk_forward": 0,
            "overfit_flagged": 0,
            "pass_unchanged_rate_pct": 0.0,
        },
        "reasons": ["No MT5 research artifact found."],
        "sources": [],
        "markdown_path": str(markdown_rel).replace("\\", "/"),
        "json_path": str(json_rel).replace("\\", "/"),
    }
    _write_outputs(root_path, payload, markdown_rel, json_rel)
    return payload


def _write_outputs(root_path: Path, payload: dict[str, Any], markdown_rel: Path, json_rel: Path) -> None:
    latest_md_rel = Path("reports") / "skills" / SKILL_NAME / "latest.md"
    latest_json_rel = Path("reports") / "skills" / SKILL_NAME / "latest.json"
    _write_markdown(root_path / markdown_rel, payload)
    _write_json(root_path / json_rel, payload)
    _write_markdown(root_path / latest_md_rel, payload)
    _write_json(root_path / latest_json_rel, payload)


def run_backtest_review(root: Path | str = ROOT) -> dict[str, Any]:
    """Write a conservative local backtest-review guardrail report."""

    root_path = Path(root)
    research_path = _latest_json(
        root_path,
        Path("mt5-agentic-desk") / "logs" / "research",
        "research_*.json",
    )
    if research_path is None:
        return _blocked_without_research(root_path)

    research = _read_json(research_path)
    metrics = _research_metrics(research)
    dq_status, dq_brief, dq_source = _data_quality_status(root_path)
    status, reasons = _status_and_reasons(metrics, dq_status)

    stamp = _utc_stamp()
    markdown_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.md"
    json_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.json"
    sources = [_relative(root_path, research_path)]
    if dq_source:
        sources.append(dq_source)

    qualification_path = _latest_json(
        root_path,
        Path("mt5-agentic-desk") / "logs" / "strategy_qualification",
        "strategy_qualification_*.json",
    )
    if qualification_path is not None:
        sources.append(_relative(root_path, qualification_path))

    payload: dict[str, Any] = {
        "ok": True,
        "skill": SKILL_NAME,
        "autonomy": "Guardrail",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "owner_need": "approve" if status == "PASS_FOR_OWNER_APPROVAL" else "none",
        "brief": _brief(status, metrics, reasons),
        "required_next_action": _required_next_action(status),
        "data_quality": {
            "status": dq_status,
            "brief": dq_brief,
        },
        "metrics": metrics,
        "reasons": reasons,
        "sources": sources,
        "hard_rule": "Productize the process, not the trades.",
        "markdown_path": str(markdown_rel).replace("\\", "/"),
        "json_path": str(json_rel).replace("\\", "/"),
    }
    _write_outputs(root_path, payload, markdown_rel, json_rel)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate a backtest-review guardrail artifact.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    print(json.dumps(run_backtest_review(root=Path(args.root)), indent=2))


if __name__ == "__main__":
    main()

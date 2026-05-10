"""Data quality daily guardrail built from local evidence files."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from org_truth_retriever import ROOT


SKILL_NAME = "data-quality-daily"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str
    source: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
            "source": self.source,
        }


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _parse_evidence_date(path: Path) -> date | None:
    stem = path.stem
    raw = stem.replace("daily_summary_", "")
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def _latest_mt5_summary(root: Path) -> Path | None:
    evidence_dir = root / "mt5-agentic-desk" / "logs" / "evidence"
    if not evidence_dir.exists():
        return None
    candidates = [
        path
        for path in evidence_dir.glob("daily_summary_*.json")
        if _parse_evidence_date(path) is not None
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: _parse_evidence_date(path) or date.min)


def _mt5_evidence_check(root: Path, as_of: date) -> CheckResult:
    latest = _latest_mt5_summary(root)
    if latest is None:
        return CheckResult(
            name="MT5 evidence freshness",
            status="BLOCKED",
            detail="No MT5 daily evidence summary found.",
        )
    evidence_date = _parse_evidence_date(latest)
    if evidence_date is None:
        return CheckResult(
            name="MT5 evidence freshness",
            status="BLOCKED",
            detail="Latest MT5 evidence summary has an invalid date.",
            source=str(latest.relative_to(root)).replace("\\", "/"),
        )
    age_days = (as_of - evidence_date).days
    status = "GREEN" if age_days <= 1 else "RED"
    detail = f"Latest MT5 daily evidence summary is {age_days} day(s) old."
    return CheckResult(
        name="MT5 evidence freshness",
        status=status,
        detail=detail,
        source=str(latest.relative_to(root)).replace("\\", "/"),
    )


def _static_na_checks() -> list[CheckResult]:
    return [
        CheckResult(
            name="Corporate actions",
            status="N/A",
            detail="Not applicable to current FX/Polymarket evidence scope.",
        ),
        CheckResult(
            name="Vendor cross-check",
            status="N/A",
            detail="No second market-data vendor is wired yet.",
        ),
        CheckResult(
            name="Broker/clearing reconciliation",
            status="N/A",
            detail="No canonical broker, clearing, or internal blotter source exists yet.",
        ),
    ]


def _overall_status(checks: list[CheckResult]) -> str:
    statuses = {check.status for check in checks}
    if "BLOCKED" in statuses:
        return "BLOCKED"
    if "RED" in statuses:
        return "RED"
    if "AMBER" in statuses:
        return "AMBER"
    return "GREEN"


def _brief(status: str, checks: list[CheckResult]) -> str:
    blocking = [check for check in checks if check.status in {"BLOCKED", "RED"}]
    if blocking:
        first = blocking[0]
        return f"Trading data quality is {status}. {first.detail}"
    return "Trading data quality is GREEN for the local checks that currently exist. Missing vendor and broker checks are explicitly marked N/A."


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Data Quality Daily",
        "",
        f"Generated UTC: {payload['generated_at_utc']}",
        f"Status: {payload['status']}",
        f"Owner need: {payload['owner_need']}",
        "",
        "## Brief",
        "",
        payload["brief"],
        "",
        "## Checks",
        "",
    ]
    for check in payload["checks"]:
        source = f" Source: `{check['source']}`." if check.get("source") else ""
        lines.append(f"- {check['name']}: {check['status']} - {check['detail']}{source}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_data_quality_daily(root: Path | str = ROOT, as_of: date | None = None) -> dict[str, Any]:
    """Write a conservative local data-quality guardrail report."""

    root_path = Path(root)
    current_date = as_of or _today_utc()
    checks = [_mt5_evidence_check(root_path, current_date), *_static_na_checks()]
    status = _overall_status(checks)
    stamp = _utc_stamp()
    markdown_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.md"
    json_rel = Path("reports") / "skills" / SKILL_NAME / f"{stamp}.json"
    latest_md_rel = Path("reports") / "skills" / SKILL_NAME / "latest.md"
    latest_json_rel = Path("reports") / "skills" / SKILL_NAME / "latest.json"

    payload: dict[str, Any] = {
        "ok": True,
        "skill": SKILL_NAME,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "owner_need": "none",
        "brief": _brief(status, checks),
        "checks": [check.to_dict() for check in checks],
        "markdown_path": str(markdown_rel).replace("\\", "/"),
        "json_path": str(json_rel).replace("\\", "/"),
    }
    _write_markdown(root_path / markdown_rel, payload)
    _write_json(root_path / json_rel, payload)
    _write_markdown(root_path / latest_md_rel, payload)
    _write_json(root_path / latest_json_rel, payload)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate data quality daily guardrail artifacts.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    parser.add_argument("--as-of", default="", help="Optional YYYY-MM-DD date for deterministic checks.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    as_of = date.fromisoformat(args.as_of) if args.as_of else None
    print(json.dumps(run_data_quality_daily(root=Path(args.root), as_of=as_of), indent=2))


if __name__ == "__main__":
    main()

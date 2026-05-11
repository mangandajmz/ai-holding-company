"""Retrieve durable company truth for Chief of Staff answers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class TruthSource:
    path: str
    exists: bool
    generated_at_utc: str = ""
    truth_state: str = "unknown"


@dataclass
class TruthBundle:
    truth_state: str = "unknown"
    company_status: str = "UNKNOWN"
    generated_at_utc: str = ""
    company_risks: list[str] = field(default_factory=list)
    company_actions: list[str] = field(default_factory=list)
    base_summary: dict[str, Any] = field(default_factory=dict)
    pending_approvals: list[dict[str, Any]] = field(default_factory=list)
    approved_awaiting_execution: list[dict[str, Any]] = field(default_factory=list)
    trading_status: str = "UNKNOWN"
    trading_issues: list[dict[str, Any]] = field(default_factory=list)
    trading_actions: list[str] = field(default_factory=list)
    data_quality_status: str = "UNKNOWN"
    data_quality_brief: str = ""
    backtest_review_status: str = "UNKNOWN"
    backtest_review_brief: str = ""
    backtest_review_next_action: str = ""
    website_status: str = "UNKNOWN"
    website_issues: list[dict[str, Any]] = field(default_factory=list)
    support_triage_status: str = "UNKNOWN"
    support_triage_brief: str = ""
    sources: list[TruthSource] = field(default_factory=list)

    def source_paths(self) -> list[str]:
        return [source.path for source in self.sources if source.exists]


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _source(root: Path, relative_path: str, payload: dict[str, Any] | None) -> TruthSource:
    return TruthSource(
        path=relative_path.replace("\\", "/"),
        exists=(root / relative_path).exists(),
        generated_at_utc=str((payload or {}).get("generated_at_utc", "")).strip(),
        truth_state="known" if payload else "unknown",
    )


def _scorecard_items(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    items = scorecard.get("items", [])
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _scorecard_text_list(scorecard: dict[str, Any], key: str) -> list[str]:
    values = scorecard.get(key, [])
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _extract_pending_approvals(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    snapshot = payload.get("board_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    approvals = snapshot.get("approvals", [])
    if not isinstance(approvals, list):
        return []
    return [item for item in approvals if isinstance(item, dict)]


def _extract_approved_execution(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    phase3_snapshot = payload.get("approval_execution_snapshot", {})
    if isinstance(phase3_snapshot, dict):
        approved = phase3_snapshot.get("approved_awaiting_execution", [])
        if isinstance(approved, list):
            return [item for item in approved if isinstance(item, dict)]

    execution = payload.get("execution_by_approval", {})
    if not isinstance(execution, dict):
        return []
    open_rows: list[dict[str, Any]] = []
    for approval_id, row in execution.items():
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "")).upper()
        if status in {"APPROVED", "ASSIGNED", "STARTED"}:
            clean_row = dict(row)
            clean_row["approval_id"] = str(approval_id)
            open_rows.append(clean_row)
    return open_rows


def _extract_division(
    phase2_payload: dict[str, Any] | None,
    division_name: str,
) -> tuple[str, list[dict[str, Any]], list[str]]:
    if not isinstance(phase2_payload, dict):
        return "UNKNOWN", [], []
    divisions = phase2_payload.get("divisions", [])
    if not isinstance(divisions, list):
        return "UNKNOWN", [], []
    for division in divisions:
        if not isinstance(division, dict):
            continue
        if str(division.get("division", "")).lower() != division_name:
            continue
        scorecard = division.get("scorecard", {})
        scorecard = scorecard if isinstance(scorecard, dict) else {}
        status = str(scorecard.get("status") or division.get("status") or "UNKNOWN").upper()
        issues = [
            item
            for item in _scorecard_items(scorecard)
            if str(item.get("status", "")).upper() in {"AMBER", "RED", "YELLOW", "BLOCKED"}
        ]
        actions = _scorecard_text_list(scorecard, "actions")
        return status, issues, actions
    return "UNKNOWN", [], []


def collect_truth_bundle(root: Path | str = ROOT) -> TruthBundle:
    """Collect current first-party truth without external calls."""

    root_path = Path(root)
    phase3_rel = "reports/phase3_holding_latest.json"
    phase2_rel = "reports/phase2_divisions_latest.json"
    daily_rel = "reports/daily_brief_latest.json"
    approvals_rel = "state/board_approval_decisions.json"
    data_quality_rel = "reports/skills/data-quality-daily/latest.json"
    backtest_review_rel = "reports/skills/backtest-review/latest.json"
    support_triage_rel = "reports/skills/support-triage/latest.json"

    phase3 = _load_json(root_path / phase3_rel)
    phase2 = _load_json(root_path / phase2_rel)
    daily = _load_json(root_path / daily_rel)
    approvals = _load_json(root_path / approvals_rel)
    data_quality = _load_json(root_path / data_quality_rel)
    backtest_review = _load_json(root_path / backtest_review_rel)
    support_triage = _load_json(root_path / support_triage_rel)

    scorecard = phase3.get("company_scorecard", {}) if isinstance(phase3, dict) else {}
    scorecard = scorecard if isinstance(scorecard, dict) else {}
    company_status = str(scorecard.get("status") or "UNKNOWN").upper()
    truth_state = (
        "known"
        if phase3 or phase2 or daily or approvals or data_quality or backtest_review or support_triage
        else "unknown"
    )

    trading_status, trading_issues, trading_actions = _extract_division(phase2, "trading")
    website_status, website_issues, _website_actions = _extract_division(phase2, "websites")

    approved_execution = _extract_approved_execution(phase3)
    if not approved_execution:
        approved_execution = _extract_approved_execution(approvals)

    return TruthBundle(
        truth_state=truth_state,
        company_status=company_status,
        generated_at_utc=str((phase3 or {}).get("generated_at_utc", "")).strip(),
        company_risks=_scorecard_text_list(scorecard, "risks"),
        company_actions=_scorecard_text_list(scorecard, "actions"),
        base_summary=(phase3 or daily or {}).get("base_summary", {})
        if isinstance((phase3 or daily or {}).get("base_summary", {}), dict)
        else {},
        pending_approvals=_extract_pending_approvals(approvals),
        approved_awaiting_execution=approved_execution,
        trading_status=trading_status,
        trading_issues=trading_issues,
        trading_actions=trading_actions,
        data_quality_status=str((data_quality or {}).get("status", "UNKNOWN")).upper(),
        data_quality_brief=str((data_quality or {}).get("brief", "")).strip(),
        backtest_review_status=str((backtest_review or {}).get("status", "UNKNOWN")).upper(),
        backtest_review_brief=str((backtest_review or {}).get("brief", "")).strip(),
        backtest_review_next_action=str((backtest_review or {}).get("required_next_action", "")).strip(),
        website_status=website_status,
        website_issues=website_issues,
        support_triage_status=str((support_triage or {}).get("status", "UNKNOWN")).upper(),
        support_triage_brief=str((support_triage or {}).get("brief", "")).strip(),
        sources=[
            _source(root_path, phase3_rel, phase3),
            _source(root_path, phase2_rel, phase2),
            _source(root_path, daily_rel, daily),
            _source(root_path, approvals_rel, approvals),
            _source(root_path, data_quality_rel, data_quality),
            _source(root_path, backtest_review_rel, backtest_review),
            _source(root_path, support_triage_rel, support_triage),
        ],
    )

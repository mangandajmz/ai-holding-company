from __future__ import annotations

import json
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import company_loop  # noqa: E402


def _config(tmp_path: Path) -> dict:
    return {
        "paths": {
            "reports_dir": str(tmp_path / "reports"),
            "state_dir": str(tmp_path / "state"),
        }
    }


def test_new_loop_writes_state_and_markdown(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(company_loop, "ROOT", tmp_path)
    config = _config(tmp_path)

    result = company_loop.new_loop(
        config,
        goal="Improve FreeTraderHub calculator clarity",
        loop_type="website_improvement",
        division="websites",
    )

    assert result["ok"] is True
    loop = result["loop"]
    assert loop["loop_id"] == "loop_0001"
    assert loop["status"] == "GOAL_CAPTURED"
    state = json.loads((tmp_path / "state" / "company_loops.json").read_text(encoding="utf-8"))
    assert state["loops"][0]["goal"] == "Improve FreeTraderHub calculator clarity"
    report = tmp_path / "reports" / "company_loops" / "loop_0001.md"
    assert "Company Loop loop_0001" in report.read_text(encoding="utf-8")


def test_evidence_and_safe_advance_moves_to_review_ready(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(company_loop, "ROOT", tmp_path)
    config = _config(tmp_path)
    loop_id = company_loop.new_loop(config, goal="Document daily workflow")["loop"]["loop_id"]

    evidence = company_loop.add_evidence(
        config,
        loop_id=loop_id,
        path="reports/daily_brief_latest.md",
        note="Daily brief evidence",
    )
    advanced = company_loop.advance_loop(
        config,
        loop_id=loop_id,
        recommendation="Keep this as an operations-only documentation improvement.",
        measurement_plan="CEO can follow the daily operating guide without extra context.",
    )

    assert evidence["loop"]["status"] == "EVIDENCE_READY"
    assert advanced["loop"]["status"] == "REVIEW_READY"
    assert advanced["loop"]["approval_status"] == "NOT_REQUIRED_YET"


def test_risky_advance_requires_ceo_approval_before_start(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(company_loop, "ROOT", tmp_path)
    config = _config(tmp_path)
    loop_id = company_loop.new_loop(
        config,
        goal="Improve FreeTraderHub page",
        loop_type="website_improvement",
        division="websites",
    )["loop"]["loop_id"]

    advanced = company_loop.advance_loop(
        config,
        loop_id=loop_id,
        recommendation="Publish the updated homepage after production deployment.",
        measurement_plan="Check traffic and calculator usage after deployment.",
    )
    blocked = company_loop.start_action(config, loop_id=loop_id)
    approved = company_loop.approve_loop(
        config,
        loop_id=loop_id,
        note="CEO approved QA-only work; no publishing yet.",
        action="Run QA only.",
    )
    started = company_loop.start_action(config, loop_id=loop_id, note="Start approved QA.")

    assert advanced["loop"]["status"] == "PENDING_CEO_APPROVAL"
    assert advanced["loop"]["approval_status"] == "PENDING_CEO_APPROVAL"
    assert blocked["ok"] is False
    assert "approval is required" in blocked["error"].lower()
    assert approved["loop"]["approval_status"] == "APPROVED"
    assert started["loop"]["status"] == "IN_PROGRESS"


def test_add_evidence_preserves_pending_ceo_approval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(company_loop, "ROOT", tmp_path)
    config = _config(tmp_path)
    loop_id = company_loop.new_loop(
        config,
        goal="Improve FreeTraderHub page",
        loop_type="website_improvement",
        division="websites",
    )["loop"]["loop_id"]
    advanced = company_loop.advance_loop(
        config,
        loop_id=loop_id,
        recommendation="Publish the approved article after CEO review.",
    )
    evidence = company_loop.add_evidence(
        config,
        loop_id=loop_id,
        path="reports/article_brief.md",
        note="Added brief.",
    )

    assert advanced["loop"]["approval_status"] == "PENDING_CEO_APPROVAL"
    assert evidence["loop"]["approval_status"] == "PENDING_CEO_APPROVAL"
    assert evidence["loop"]["status"] == "PENDING_CEO_APPROVAL"
    assert "CEO approval required" in evidence["loop"]["next_step"]


def test_measure_and_done_close_loop(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(company_loop, "ROOT", tmp_path)
    config = _config(tmp_path)
    loop_id = company_loop.new_loop(config, goal="Run weekly operations review")["loop"]["loop_id"]

    measured = company_loop.measure_loop(
        config,
        loop_id=loop_id,
        result="Weekly scorecard reviewed; no risky actions approved.",
    )
    done = company_loop.done_loop(config, loop_id=loop_id, result="Closed after CEO review.")
    status = company_loop.list_loops(config)

    assert measured["loop"]["status"] == "MEASUREMENT_READY"
    assert done["loop"]["status"] == "DONE"
    assert status["count"] == 0

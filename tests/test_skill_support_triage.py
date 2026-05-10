from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from skill_support_triage import run_support_triage  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_run_support_triage_blocks_without_ticket_source(tmp_path: Path) -> None:
    result = run_support_triage(root=tmp_path)

    assert result["ok"] is True
    assert result["status"] == "BLOCKED"
    assert result["owner_need"] == "none"
    assert "No local support ticket source found" in result["brief"]
    assert (tmp_path / result["markdown_path"]).exists()


def test_run_support_triage_classifies_tickets_without_exposing_email(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "state" / "support_tickets.json",
        {
            "tickets": [
                {
                    "id": "ticket_bug",
                    "customer_email": "customer@example.com",
                    "subject": "Calculator is broken",
                    "body": "The position size calculator shows an error.",
                },
                {
                    "id": "ticket_refund",
                    "customer_email": "refund@example.com",
                    "subject": "Refund request",
                    "body": "I was charged and want a refund.",
                },
            ]
        },
    )

    result = run_support_triage(root=tmp_path)

    assert result["status"] == "AMBER"
    assert result["owner_need"] == "approve"
    assert result["metrics"]["ticket_count"] == 2
    assert result["tickets"][0]["category"] == "bug"
    assert result["tickets"][0]["draft_reply"]
    assert result["tickets"][1]["category"] == "billing"
    assert result["tickets"][1]["escalation_reason"] == "Billing, refund, legal, or account issue."
    assert "customer@example.com" not in json.dumps(result)

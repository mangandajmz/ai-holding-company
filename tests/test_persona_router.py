from __future__ import annotations

import json
from pathlib import Path

import sys


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from persona_router import answer_persona, build_truth_packet  # noqa: E402
from nanoclaw_shadow_writer import write_latest_shadow_response  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_chief_of_staff_answers_free_text_from_org_truth(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {
            "board_snapshot": {
                "approvals": [
                    {
                        "approval_id": "board_1",
                        "topic": "Company KPI: Forecast attainment",
                        "priority": "RED",
                    }
                ]
            }
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "RED",
            "owner_need": "approve",
            "brief": "Forecast attainment is RED.",
        },
    )

    response = answer_persona(
        persona="chief of staff",
        message="I just got back. What actually needs my attention and why?",
        root=tmp_path,
    )

    assert response["ok"] is True
    assert response["persona"] == "chief-of-staff"
    assert response["truth_state"] == "known"
    assert response["owner_need"] == "approve"
    assert "Forecast attainment is RED" in response["answer"]
    assert "one approval" in response["answer"]
    assert "state/board_approval_decisions.json" in response["sources"]


def test_persona_answer_carries_evidence_without_chat_memory(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "RED",
            "owner_need": "approve",
            "brief": "Company is RED because forecast attainment is 4.1%.",
        },
    )

    response = answer_persona(
        persona="chief",
        message="Talk to me like my chief of staff. What matters?",
        root=tmp_path,
    )

    assert response["grounding_mode"] == "deterministic_local_truth"
    assert response["no_model_calls"] is True
    assert response["evidence"][0]["source"] == "reports/skills/risk-aggregate-daily/latest.json"
    assert response["evidence"][0]["status"] == "RED"
    assert response["evidence"][0]["brief"] == "Company is RED because forecast attainment is 4.1%."
    assert "I would focus there first" in response["answer"]


def test_chief_of_staff_reply_avoids_report_row_language(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {
            "board_snapshot": {
                "approvals": [{"approval_id": "board_1", "topic": "Company KPI", "priority": "RED"}]
            }
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "skill": "backtest-review",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Backtest review is BLOCKED. No out-of-sample evidence.",
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "support-triage" / "latest.json",
        {
            "skill": "support-triage",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Support triage is BLOCKED. No local support ticket source found.",
        },
    )

    response = answer_persona(persona="chief", message="Hi", root=tmp_path)

    assert response["answer"].startswith("Welcome back.")
    assert "backtest-review:" not in response["answer"]
    assert "issue records" not in response["answer"]
    assert "I would focus there first" in response["answer"]
    assert response["answer"].count("I would focus there first") == 1


def test_chief_of_staff_green_state_drops_urgency_framing(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "GREEN",
            "owner_need": "none",
            "brief": "Company is GREEN. All KPIs within target.",
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "skill": "backtest-review",
            "status": "GREEN",
            "owner_need": "none",
            "brief": "Backtest review is current.",
        },
    )

    response = answer_persona(persona="chief", message="what needs me?", root=tmp_path)

    assert response["answer"].startswith("Welcome back.")
    assert "I would focus there first" not in response["answer"]
    assert "behind that" not in response["answer"]
    assert response["evidence"][0]["status"] == "GREEN"
    assert _clean_brief_for_test(response["evidence"][0]["brief"]) in response["answer"]


def _clean_brief_for_test(brief: str) -> str:
    cleaned = brief.strip()
    for prefix in (
        "Backtest review is BLOCKED. ",
        "Portfolio retro is BLOCKED. ",
        "Support triage is BLOCKED. ",
        "The company is RED in the latest stored CEO report. ",
    ):
        if cleaned.startswith(prefix):
            return cleaned.removeprefix(prefix)
    return cleaned


def test_chief_of_staff_answers_role_question_without_repeating_status(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "skill": "backtest-review",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Backtest review is BLOCKED. No out-of-sample evidence.",
        },
    )

    response = answer_persona(persona="chief", message="what do you do?", root=tmp_path)

    assert "I help you run the company" in response["answer"]
    assert "what needs your attention" in response["answer"]
    assert "No out-of-sample evidence" not in response["answer"]
    assert response["intent"] == "role"


def test_truth_packet_is_the_nanoclaw_boundary(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "state" / "board_approval_decisions.json",
        {"board_snapshot": {"approvals": [{"approval_id": "board_1", "topic": "Company KPI"}]}},
    )
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "RED",
            "owner_need": "approve",
            "brief": "Company is RED because forecast attainment is 4.1%.",
        },
    )

    packet = build_truth_packet(persona="chief", message="what needs me?", root=tmp_path)

    assert packet["schema_version"] == "persona_truth_packet.v1"
    assert packet["packet_id"]
    assert packet["persona"] == "chief-of-staff"
    assert packet["intent"] == "status"
    assert packet["approvals_count"] == 1
    assert packet["policy"]["allowed_claim_source"] == "truth_packet_only"
    assert packet["policy"]["no_tool_calls"] is True
    assert packet["policy"]["no_file_reads"] is True
    assert packet["policy"]["no_writes"] is True
    assert packet["sources"] == [
        "state/board_approval_decisions.json",
        "reports/skills/risk-aggregate-daily/latest.json",
    ]


def test_nanoclaw_shadow_is_recorded_without_changing_live_answer(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "RED",
            "owner_need": "approve",
            "brief": "Company is RED because forecast attainment is 4.1%.",
        },
    )
    packet = build_truth_packet(persona="chief", message="what needs me?", root=tmp_path)
    shadow_path = tmp_path / "state" / "nanoclaw_shadow_outbox.jsonl"
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_path.write_text(
        json.dumps(
            {
                "packet_id": packet["packet_id"],
                "persona": "chief-of-staff",
                "intent": "status",
                "answer": "Morning. The forecast miss is the first thing I would look at.",
                "unsupported_claims": [],
                "confidence": "medium",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    response = answer_persona(
        persona="chief",
        message="what needs me?",
        root=tmp_path,
        conversation_config={
            "provider": "deterministic_fallback",
            "nanoclaw": {
                "mode": "shadow",
                "shadow_outbox_path": "state/nanoclaw_shadow_outbox.jsonl",
            },
        },
    )

    assert response["verbalizer"]["provider"] == "deterministic_fallback"
    assert "Forecast attainment" in response["answer"] or "forecast attainment" in response["answer"]
    assert response["shadow_verbalizer"]["provider"] == "nanoclaw_shadow"
    assert response["shadow_verbalizer"]["accepted"] is True
    assert response["shadow_verbalizer"]["answer"] == "Morning. The forecast miss is the first thing I would look at."


def test_nanoclaw_shadow_rejects_unsupported_claims(tmp_path: Path) -> None:
    packet = build_truth_packet(persona="chief", message="what needs me?", root=tmp_path)
    shadow_path = tmp_path / "state" / "nanoclaw_shadow_outbox.jsonl"
    shadow_path.parent.mkdir(parents=True, exist_ok=True)
    shadow_path.write_text(
        json.dumps(
            {
                "packet_id": packet["packet_id"],
                "persona": "chief-of-staff",
                "intent": "status",
                "answer": "Revenue is fixed.",
                "unsupported_claims": ["Revenue is fixed."],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    response = answer_persona(
        persona="chief",
        message="what needs me?",
        root=tmp_path,
        conversation_config={
            "provider": "deterministic_fallback",
            "nanoclaw": {
                "mode": "shadow",
                "shadow_outbox_path": "state/nanoclaw_shadow_outbox.jsonl",
            },
        },
    )

    assert response["shadow_verbalizer"]["provider"] == "nanoclaw_shadow"
    assert response["shadow_verbalizer"]["accepted"] is False
    assert response["shadow_verbalizer"]["reason"] == "unsupported_claims"


def test_nanoclaw_shadow_mode_writes_truth_packet_inbox(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "RED",
            "owner_need": "approve",
            "brief": "Company is RED because forecast attainment is 4.1%.",
        },
    )

    response = answer_persona(
        persona="chief",
        message="what needs me?",
        root=tmp_path,
        conversation_config={
            "provider": "deterministic_fallback",
            "nanoclaw": {
                "mode": "shadow",
                "shadow_inbox_path": "state/nanoclaw_shadow_inbox.jsonl",
                "shadow_outbox_path": "state/nanoclaw_shadow_outbox.jsonl",
            },
        },
    )

    inbox_path = tmp_path / "state" / "nanoclaw_shadow_inbox.jsonl"
    rows = [json.loads(line) for line in inbox_path.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["packet"]["packet_id"] == response["truth_packet"]["packet_id"]
    assert rows[-1]["packet"]["policy"]["allowed_claim_source"] == "truth_packet_only"
    assert response["shadow_verbalizer"]["reason"] == "no_shadow_output"


def test_nanoclaw_shadow_writer_roundtrip_is_shadow_only(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "risk-aggregate-daily" / "latest.json",
        {
            "skill": "risk-aggregate-daily",
            "status": "RED",
            "owner_need": "approve",
            "brief": "Company is RED because forecast attainment is 4.1%.",
        },
    )
    config = {
        "provider": "deterministic_fallback",
        "nanoclaw": {
            "mode": "shadow",
            "shadow_inbox_path": "state/nanoclaw_shadow_inbox.jsonl",
            "shadow_outbox_path": "state/nanoclaw_shadow_outbox.jsonl",
        },
    }

    first = answer_persona(persona="chief", message="what needs me?", root=tmp_path, conversation_config=config)
    write_result = write_latest_shadow_response(root=tmp_path)
    second = answer_persona(persona="chief", message="what needs me?", root=tmp_path, conversation_config=config)

    assert write_result["ok"] is True
    assert second["answer"] == first["answer"]
    assert second["shadow_verbalizer"]["accepted"] is True
    assert second["shadow_verbalizer"]["answer"]
    assert second["shadow_verbalizer"]["provider"] == "nanoclaw_shadow"


def test_risk_officer_blocks_forward_motion_from_guardrail_sources(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "backtest-review" / "latest.json",
        {
            "skill": "backtest-review",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Backtest review is BLOCKED. No out-of-sample evidence.",
        },
    )
    _write_json(
        tmp_path / "reports" / "skills" / "data-quality-daily" / "latest.json",
        {
            "skill": "data-quality-daily",
            "status": "GREEN",
            "owner_need": "none",
            "brief": "Trading data quality is GREEN.",
        },
    )

    response = answer_persona(
        persona="risk",
        message="Are you comfortable letting the strategy move forward, or are you objecting?",
        root=tmp_path,
    )

    assert response["persona"] == "risk-officer"
    assert response["owner_need"] == "none"
    assert "I object" in response["answer"]
    assert "I would not move it forward" in response["answer"]
    assert "No out-of-sample evidence" in response["answer"]
    assert "reports/skills/backtest-review/latest.json" in response["sources"]


def test_growth_lead_refuses_to_invent_missing_analytics(tmp_path: Path) -> None:
    response = answer_persona(
        persona="growth",
        message="What changed with the websites since yesterday?",
        root=tmp_path,
    )

    assert response["persona"] == "growth-lead"
    assert response["truth_state"] == "unknown"
    assert "I do not have current growth evidence" in response["answer"]
    assert response["sources"] == []


def test_support_lead_reports_missing_inbox_source(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "support-triage" / "latest.json",
        {
            "skill": "support-triage",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Support triage is BLOCKED. No local support ticket source found.",
        },
    )

    response = answer_persona(
        persona="support",
        message="Any angry customers or tickets I should know about?",
        root=tmp_path,
    )

    assert response["persona"] == "support-lead"
    assert "No local support ticket source found" in response["answer"]
    assert response["truth_state"] == "known"


def test_nanoclaw_live_returns_model_text_when_ollama_responds(monkeypatch) -> None:
    import io
    import urllib.request

    import persona_verbalizer

    captured = {}

    class _FakeResp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._body

    def _fake_urlopen(req, timeout=20):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp(json.dumps({"response": "Welcome back, James. Forecast attainment is RED."}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    packet = {
        "persona": "chief-of-staff",
        "display_name": "Chief of Staff",
        "intent": "status",
        "message": "what needs me?",
        "evidence": [{"status": "RED", "brief": "Forecast attainment is RED."}],
    }
    config = {"phase2": {"ollama_model": "llama3.2:latest", "ollama_base_url": "http://127.0.0.1:11434"}}

    out = persona_verbalizer.nanoclaw_live_verbalize(packet, config)

    assert out["provider"] == "nanoclaw_live"
    assert out["no_model_calls"] is False
    assert out["answer"].startswith("Welcome back, James.")
    assert captured["url"].endswith("/api/generate")
    assert captured["body"]["model"] == "llama3.2:latest"
    assert captured["body"]["stream"] is False


def test_nanoclaw_live_returns_empty_answer_when_ollama_unreachable(monkeypatch) -> None:
    import urllib.error
    import urllib.request

    import persona_verbalizer

    def _boom(req, timeout=20):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    out = persona_verbalizer.nanoclaw_live_verbalize({"persona": "chief-of-staff", "intent": "status"}, {})
    assert out["provider"] == "nanoclaw_live"
    assert out["answer"] == ""
    verdict = persona_verbalizer.verify_verbalizer_output(out)
    assert verdict["accepted"] is False
    assert verdict["reason"] == "empty_answer"

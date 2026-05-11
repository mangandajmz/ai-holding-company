from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from nanoclaw_status import compute_status  # noqa: E402
import persona_verbalizer  # noqa: E402


def _write_log(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def test_compute_status_reports_accept_rate_per_persona(tmp_path: Path) -> None:
    log = tmp_path / "state" / "nanoclaw_live_log.jsonl"
    _write_log(
        log,
        [{"persona": "chief-of-staff", "packet_id": str(i), "accepted": i < 4, "reason": "ok"} for i in range(5)]
        + [{"persona": "risk-officer", "packet_id": str(i), "accepted": False, "reason": "empty_answer"} for i in range(3)],
    )

    result = compute_status(
        log_path=log,
        window=10,
        min_accept_rate=0.80,
        personas={"chief-of-staff": "live", "risk-officer": "shadow", "growth-lead": "shadow"},
    )

    by_persona = {p["persona"]: p for p in result["personas"]}
    assert by_persona["chief-of-staff"]["accepted"] == 4
    assert by_persona["chief-of-staff"]["accept_rate"] == 0.8
    # window not satisfied (only 5 records, need 10) so gate is not met
    assert by_persona["chief-of-staff"]["meets_gate"] is False
    assert by_persona["risk-officer"]["accept_rate"] == 0.0
    assert by_persona["growth-lead"]["window_size"] == 0
    assert by_persona["growth-lead"]["current_mode"] == "shadow"


def test_compute_status_gate_passes_when_window_and_rate_met(tmp_path: Path) -> None:
    log = tmp_path / "state" / "nanoclaw_live_log.jsonl"
    _write_log(
        log,
        [{"persona": "chief-of-staff", "packet_id": str(i), "accepted": True, "reason": "ok"} for i in range(50)],
    )

    result = compute_status(log_path=log, window=50, min_accept_rate=0.80, personas={"chief-of-staff": "shadow"})
    cof = next(p for p in result["personas"] if p["persona"] == "chief-of-staff")
    assert cof["accept_rate"] == 1.0
    assert cof["meets_gate"] is True


def test_run_verbalizers_appends_live_log(monkeypatch, tmp_path: Path) -> None:
    import urllib.request

    class _Resp:
        def __init__(self, body): self._b = body
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return self._b

    def _ok(req, timeout=20):
        return _Resp(json.dumps({"response": "Welcome back."}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", _ok)

    packet = {
        "persona": "chief-of-staff",
        "display_name": "Chief of Staff",
        "intent": "status",
        "packet_id": "abc123",
        "message": "hi",
        "evidence": [{"status": "RED", "brief": "Forecast attainment is RED."}],
    }
    conv = {
        "nanoclaw": {
            "mode": "shadow",
            "personas": {"chief-of-staff": "live"},
            "live_log_path": "state/nanoclaw_live_log.jsonl",
        }
    }
    full = {"phase2": {"ollama_model": "llama3.2:latest"}}

    result = persona_verbalizer.run_verbalizers(packet, config=conv, root=tmp_path, full_config=full)
    assert result["primary"]["provider"] == "nanoclaw_live"

    log_path = tmp_path / "state" / "nanoclaw_live_log.jsonl"
    assert log_path.exists()
    records = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records == [
        {"accepted": True, "intent": "status", "packet_id": "abc123", "persona": "chief-of-staff", "reason": "ok"}
    ]

from __future__ import annotations

import json
import sys
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import operating_room_server  # noqa: E402


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_operating_room_server_persona_chat_endpoint(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "reports" / "skills" / "support-triage" / "latest.json",
        {
            "skill": "support-triage",
            "status": "BLOCKED",
            "owner_need": "none",
            "brief": "Support triage is BLOCKED. No local support ticket source found.",
        },
    )
    original_root = operating_room_server.ROOT
    original_config_path = operating_room_server.CONFIG_PATH
    operating_room_server.ROOT = tmp_path
    operating_room_server.CONFIG_PATH = tmp_path / "config" / "projects.yaml"
    _write_json(operating_room_server.CONFIG_PATH, {"conversation": {"provider": "deterministic_fallback"}})
    server = ThreadingHTTPServer(("127.0.0.1", 0), operating_room_server.OperatingRoomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        body = json.dumps({"persona": "support", "message": "Any customers angry?"}).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/persona-chat",
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        operating_room_server.ROOT = original_root
        operating_room_server.CONFIG_PATH = original_config_path

    assert payload["ok"] is True
    assert payload["persona"] == "support-lead"
    assert payload["no_model_calls"] is True
    assert payload["truth_packet"]["schema_version"] == "persona_truth_packet.v1"
    assert payload["verbalizer"]["provider"] == "deterministic_fallback"
    assert "No local support ticket source found" in payload["answer"]


def test_operating_room_server_shadow_write_endpoint(tmp_path: Path) -> None:
    inbox = tmp_path / "state" / "nanoclaw_shadow_inbox.jsonl"
    inbox.parent.mkdir(parents=True, exist_ok=True)
    inbox.write_text(
        json.dumps(
            {
                "type": "nanoclaw_shadow_request",
                "packet_id": "packet_ui",
                "packet": {
                    "packet_id": "packet_ui",
                    "persona": "chief-of-staff",
                    "intent": "role",
                    "evidence": [],
                    "unknowns": [],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    original_root = operating_room_server.ROOT
    operating_room_server.ROOT = tmp_path
    server = ThreadingHTTPServer(("127.0.0.1", 0), operating_room_server.OperatingRoomHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/nanoclaw-shadow-write",
            data=b"{}",
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    finally:
        server.shutdown()
        server.server_close()
        operating_room_server.ROOT = original_root

    assert payload["ok"] is True
    assert payload["packet_id"] == "packet_ui"
    assert (tmp_path / "state" / "nanoclaw_shadow_outbox.jsonl").exists()

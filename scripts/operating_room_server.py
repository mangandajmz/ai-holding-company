"""Local-only operating room server with persona chat endpoint."""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from monitoring import load_config
from nanoclaw_shadow_writer import write_latest_shadow_response
from persona_router import answer_persona


ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = ROOT / "operating-room"
CONFIG_PATH = ROOT / "config" / "projects.yaml"


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2).encode("utf-8")


class OperatingRoomHandler(BaseHTTPRequestHandler):
    """Serve the local operating room and deterministic persona chat."""

    server_version = "OperatingRoom/0.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        return

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/operating-room", "/operating-room/"}:
            self._serve_static(STATIC_ROOT / "index.html")
            return
        if self.path.startswith("/operating-room/"):
            rel_path = self.path.removeprefix("/operating-room/")
            self._serve_static(STATIC_ROOT / rel_path)
            return
        if self.path == "/snapshot.json":
            self._serve_static(STATIC_ROOT / "snapshot.json")
            return
        self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/api/nanoclaw-shadow-write":
            self._send_json(write_latest_shadow_response(root=ROOT))
            return
        if self.path != "/api/persona-chat":
            self._send_json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        payload = self._read_json_body()
        persona = str(payload.get("persona") or "chief-of-staff")
        message = str(payload.get("message") or "").strip()
        if not message:
            self._send_json({"ok": False, "error": "message is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        config = load_config(CONFIG_PATH)
        self._send_json(
            answer_persona(
                persona=persona,
                message=message,
                root=ROOT,
                conversation_config=config.get("conversation", {}),
            )
        )

    def _read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("content-length") or "0")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _serve_static(self, path: Path) -> None:
        resolved = path.resolve()
        if STATIC_ROOT.resolve() not in resolved.parents and resolved != STATIC_ROOT.resolve():
            self._send_json({"ok": False, "error": "invalid path"}, status=HTTPStatus.BAD_REQUEST)
            return
        if not resolved.exists() or not resolved.is_file():
            self._send_json({"ok": False, "error": "file not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
        body = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the local operating room server.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to localhost only.")
    parser.add_argument("--port", type=int, default=8765, help="Bind port.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = ThreadingHTTPServer((args.host, args.port), OperatingRoomHandler)
    print(f"Operating room listening on http://{args.host}:{args.port}/operating-room/")
    server.serve_forever()


if __name__ == "__main__":
    main()

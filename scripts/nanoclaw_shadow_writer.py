"""Local NanoClaw shadow writer simulator.

This does not call NanoClaw or any external model. It consumes the local
truth-packet inbox and writes a candidate response in the same shape expected
from a future NanoClaw verbalizer.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = "state/nanoclaw_shadow_inbox.jsonl"
DEFAULT_OUTBOX = "state/nanoclaw_shadow_outbox.jsonl"


def _latest_inbox_record(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("packet"), dict):
            return payload
    return {}


def _brief_answer(packet: dict[str, Any]) -> str:
    persona = str(packet.get("persona") or "")
    intent = str(packet.get("intent") or "")
    evidence = packet.get("evidence", [])
    if intent == "role" and persona == "chief-of-staff":
        return "I help you run the company by keeping attention, blockers, approvals, and evidence visible."
    if evidence:
        lead = evidence[0]
        brief = str(lead.get("brief") or "")
        return f"I would start here: {brief}"
    unknowns = packet.get("unknowns", [])
    if unknowns:
        return str(unknowns[0])
    return "I do not see a stored issue needing you right now."


def write_latest_shadow_response(
    root: Path | str = ROOT,
    inbox_path: str = DEFAULT_INBOX,
    outbox_path: str = DEFAULT_OUTBOX,
) -> dict[str, Any]:
    """Write a local shadow response for the latest truth packet."""

    root_path = Path(root)
    record = _latest_inbox_record(root_path / inbox_path)
    if not record:
        return {"ok": False, "error": "no_inbox_record"}
    packet = record["packet"]
    output = {
        "packet_id": packet.get("packet_id"),
        "persona": packet.get("persona"),
        "intent": packet.get("intent"),
        "answer": _brief_answer(packet),
        "unsupported_claims": [],
        "confidence": "medium",
        "source": "local_shadow_writer",
    }
    output_file = root_path / outbox_path
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(output, sort_keys=True) + "\n")
    return {"ok": True, "packet_id": output["packet_id"], "outbox_path": outbox_path}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a local NanoClaw shadow response from the latest inbox packet.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    parser.add_argument("--inbox-path", default=DEFAULT_INBOX, help="Relative shadow inbox path.")
    parser.add_argument("--outbox-path", default=DEFAULT_OUTBOX, help="Relative shadow outbox path.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = write_latest_shadow_response(
        root=Path(args.root),
        inbox_path=args.inbox_path,
        outbox_path=args.outbox_path,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

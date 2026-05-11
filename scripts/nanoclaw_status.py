"""Report NanoClaw live acceptance rates per persona.

Reads the live-mode decision log (one JSON record per attempt) and prints a
per-persona accept rate over the configured window. Used by the owner to
decide when a persona is safe to promote from shadow to live.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _read_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    except OSError:
        return []
    return rows


def compute_status(
    log_path: Path,
    window: int,
    min_accept_rate: float,
    personas: dict[str, str] | None = None,
) -> dict[str, Any]:
    rows = _read_log(log_path)
    by_persona: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        persona = str(row.get("persona") or "")
        if not persona:
            continue
        by_persona.setdefault(persona, []).append(row)

    out_personas: list[dict[str, Any]] = []
    seen = set()
    for persona, records in sorted(by_persona.items()):
        window_records = records[-window:]
        accepted = sum(1 for r in window_records if r.get("accepted"))
        total = len(window_records)
        rate = (accepted / total) if total else 0.0
        out_personas.append({
            "persona": persona,
            "current_mode": (personas or {}).get(persona, "unknown"),
            "window_size": total,
            "accepted": accepted,
            "accept_rate": round(rate, 4),
            "meets_gate": total >= window and rate >= min_accept_rate,
        })
        seen.add(persona)

    if personas:
        for persona, mode in sorted(personas.items()):
            if persona in seen:
                continue
            out_personas.append({
                "persona": persona,
                "current_mode": mode,
                "window_size": 0,
                "accepted": 0,
                "accept_rate": 0.0,
                "meets_gate": False,
            })

    return {
        "ok": True,
        "log_path": str(log_path),
        "window": window,
        "min_accept_rate": min_accept_rate,
        "personas": out_personas,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show NanoClaw live acceptance rate per persona.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    parser.add_argument("--config", default=None, help="Path to projects.yaml.")
    return parser


def main() -> None:
    from monitoring import load_config  # pylint: disable=import-outside-toplevel

    args = _build_parser().parse_args()
    root = Path(args.root)
    config_path = Path(args.config) if args.config else root / "config" / "projects.yaml"
    config = load_config(config_path)
    nanoclaw_cfg = (config.get("conversation", {}) or {}).get("nanoclaw", {}) or {}
    log_path = root / str(nanoclaw_cfg.get("live_log_path") or "state/nanoclaw_live_log.jsonl")
    promotion = nanoclaw_cfg.get("promotion", {}) or {}
    window = int(promotion.get("window") or 50)
    min_rate = float(promotion.get("min_accept_rate") or 0.80)
    personas = nanoclaw_cfg.get("personas", {}) or {}
    result = compute_status(log_path, window=window, min_accept_rate=min_rate, personas=personas)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

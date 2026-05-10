"""Build a deterministic read-only operating room snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PERSONAS = [
    {
        "name": "Chief of Staff",
        "slug": "chief-of-staff",
        "grounding": "Reads company-level risk, approvals, current skill outputs, and retros.",
        "contract": "docs/personas/chief-of-staff/contract.md",
    },
    {
        "name": "Risk Officer",
        "slug": "risk-officer",
        "grounding": "Reads guardrail artifacts, risk blocks, and approval state.",
        "contract": "docs/personas/risk-officer/contract.md",
    },
    {
        "name": "Quant Ops",
        "slug": "quant-ops",
        "grounding": "Reads trading data-quality, backtest-review, and broker-reconcile artifacts.",
        "contract": "docs/personas/quant-ops/contract.md",
    },
    {
        "name": "Growth Lead",
        "slug": "growth-lead",
        "grounding": "Reads website analytics, growth digests, and portfolio retro evidence.",
        "contract": "docs/personas/growth-lead/contract.md",
    },
    {
        "name": "Editorial Lead",
        "slug": "editorial-lead",
        "grounding": "Reads content queue, draft, SEO, and analytics evidence when present.",
        "contract": "docs/personas/editorial-lead/contract.md",
    },
    {
        "name": "Engineering/Ops",
        "slug": "engineering-ops",
        "grounding": "Reads operating briefs, reliability records, and deploy/incident evidence.",
        "contract": "docs/personas/engineering-ops/contract.md",
    },
    {
        "name": "Support Lead",
        "slug": "support-lead",
        "grounding": "Reads support-triage output and local ticket sources when present.",
        "contract": "docs/personas/support-lead/contract.md",
    },
    {
        "name": "Finance/Admin",
        "slug": "finance-admin",
        "grounding": "Deferred until reliable finance and admin sources exist.",
        "contract": "docs/personas/finance-admin/contract.md",
    },
]


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_jsonl_sample(path: Path, limit: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        if len(rows) >= limit:
            break
    rows.reverse()
    return rows


def _latest_skill_outputs(root: Path) -> list[dict[str, Any]]:
    skills_dir = root / "reports" / "skills"
    if not skills_dir.exists():
        return []
    outputs: list[dict[str, Any]] = []
    for path in sorted(skills_dir.glob("*/latest.json")):
        payload = _read_json(path)
        if not payload:
            continue
        outputs.append(
            {
                "skill": str(payload.get("skill") or path.parent.name),
                "status": str(payload.get("status") or "UNKNOWN").upper(),
                "owner_need": str(payload.get("owner_need") or "none"),
                "brief": str(payload.get("brief") or ""),
                "source": str(path.relative_to(root)).replace("\\", "/"),
            }
        )
    return outputs


def _approval_view(root: Path) -> dict[str, Any]:
    payload = _read_json(root / "state" / "board_approval_decisions.json")
    snapshot = payload.get("board_snapshot", {})
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    raw_approvals = snapshot.get("approvals", [])
    approvals = raw_approvals if isinstance(raw_approvals, list) else []
    pending = []
    for item in approvals:
        if not isinstance(item, dict):
            continue
        pending.append(
            {
                "approval_id": str(item.get("approval_id") or ""),
                "topic": str(item.get("topic") or "approval"),
                "priority": str(item.get("priority") or "UNKNOWN").upper(),
                "decision": str(item.get("decision") or ""),
            }
        )
    return {
        "pending_count": len(pending),
        "pending": pending,
        "source": "state/board_approval_decisions.json" if payload else "",
    }


def _today_view(skill_outputs: list[dict[str, Any]]) -> dict[str, Any]:
    if not skill_outputs:
        return {
            "status": "UNKNOWN",
            "items": [
                {
                    "skill": "operating-room",
                    "status": "UNKNOWN",
                    "brief": "No skill outputs found under reports/skills/.",
                    "source": "",
                }
            ],
        }
    status_order = {"BLOCKED": 0, "RED": 1, "AMBER": 2, "YELLOW": 2, "GREEN": 3}
    sorted_items = sorted(skill_outputs, key=lambda item: status_order.get(item["status"], 4))
    return {"status": sorted_items[0]["status"], "items": sorted_items}


def _memory_view(root: Path) -> dict[str, Any]:
    rows = _read_jsonl_sample(root / "memory" / "vector_store.jsonl")
    samples = []
    for row in rows:
        samples.append(
            {
                "text": str(row.get("text") or row.get("content") or "")[:240],
                "metadata": row.get("metadata", {}) if isinstance(row.get("metadata", {}), dict) else {},
            }
        )
    return {
        "sample_count": len(samples),
        "samples": samples,
        "source": "memory/vector_store.jsonl" if samples else "",
    }


def _personas_view(root: Path) -> dict[str, Any]:
    personas = []
    for persona in PERSONAS:
        contract_path = root / persona["contract"]
        personas.append(
            {
                **persona,
                "status": "ready" if contract_path.exists() else "missing_contract",
                "deterministic_grounding": True,
            }
        )
    return {"personas": personas}


def build_operating_room_snapshot(root: Path | str = ROOT) -> dict[str, Any]:
    """Build and persist the read-only operating room snapshot."""

    root_path = Path(root)
    skill_outputs = _latest_skill_outputs(root_path)
    snapshot = {
        "ok": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "read_only": True,
        "rule": "Persona chat is free text, then deterministic grounding against local truth; no model calls.",
        "views": {
            "today": _today_view(skill_outputs),
            "approvals": _approval_view(root_path),
            "memory": _memory_view(root_path),
            "personas": _personas_view(root_path),
        },
    }
    output_path = root_path / "operating-room" / "snapshot.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the read-only operating room snapshot.")
    parser.add_argument("--root", default=str(ROOT), help="Project root.")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    print(json.dumps(build_operating_room_snapshot(root=Path(args.root)), indent=2))


if __name__ == "__main__":
    main()

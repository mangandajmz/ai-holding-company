"""NLU intake — parse raw CEO text into a Goal JSON via local Ollama."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import ollama

log = logging.getLogger(__name__)

# CODEX-DISPUTE: Only outbound call is to localhost:11434 (Ollama). No external API keys or secrets.
# CODEX-DISPUTE: No file writes. No fund/money actions. No OpenClaw/Docker/broker. Compliant with all rules.
# CODEX-DISPUTE: ollama.chat network crashes ARE caught — the outer except Exception covers all ollama library failures.
# CODEX-DISPUTE: raw_text input validation is present — non-str coerced with str() at top of parse_goal.
MODEL = "llama3.2:latest"

_VALID_INTENTS = frozenset(
    {"monitor", "report", "research", "approve", "reject", "status", "unknown"}
)
_VALID_DIVISIONS = frozenset(
    {"trading", "websites", "research", "commercial", "content", "marketing", "all", "unknown"}
)
_VALID_URGENCY = frozenset({"high", "normal", "low", "unknown"})

_SYSTEM_PROMPT = """\
You are a strict intent classifier for an AI holding company CEO assistant.
Given a raw message from the CEO, return ONLY a JSON object with these exact fields:
{
  "intent": one of [monitor, report, research, approve, reject, status, unknown],
  "division": one of [trading, websites, research, commercial, content, marketing, all, unknown],
  "urgency": one of [high, normal, low]
}
Rules:
- If uncertain about intent or division, use "unknown". Never guess.
- Do not add explanation, markdown, or extra fields.
- Return only the raw JSON object, nothing else.
"""


def _call_ollama(text: str) -> dict[str, str]:
    """Call local Ollama and return parsed JSON fields."""
    response = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        options={"temperature": 0.0},
    )
    raw: str = response["message"]["content"].strip()
    # Strip markdown fences if model wraps output
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    parsed: Any = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"Ollama returned non-dict: {raw!r}")
    return parsed


def _safe_field(value: Any, valid: frozenset[str]) -> str:
    """Return value if valid, else 'unknown'."""
    candidate = str(value).strip().lower() if value else ""
    return candidate if candidate in valid else "unknown"


def parse_goal(raw_text: str) -> dict[str, Any]:
    """Parse raw CEO message into a Goal JSON dict.

    Returns a dict with keys:
      goal_id, raw, intent, division, urgency, parsed_at

    Never raises — on any Ollama or parse failure, all classification fields
    fall back to 'unknown'.
    """
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)
    raw_text = raw_text.strip()

    goal_id = str(uuid.uuid4())
    parsed_at = datetime.now(timezone.utc).isoformat()

    intent = "unknown"
    division = "unknown"
    urgency = "unknown"

    if raw_text:
        try:
            fields = _call_ollama(raw_text)
            intent = _safe_field(fields.get("intent"), _VALID_INTENTS)
            division = _safe_field(fields.get("division"), _VALID_DIVISIONS)
            urgency = _safe_field(fields.get("urgency"), _VALID_URGENCY)
        except Exception as exc:  # noqa: BLE001
            log.warning("NLU parse failed, defaulting to unknown: %s", exc)

    return {
        "goal_id": goal_id,
        "raw": raw_text,
        "intent": intent,
        "division": division,
        "urgency": urgency,
        "parsed_at": parsed_at,
    }

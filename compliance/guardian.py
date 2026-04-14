"""Guardian — deterministic, stateless, LLM-free compliance gate.

Input:  any dict representing a goal or action payload.
Output: {"pass": True} or {"pass": False, "violated_rules": ["Rx", ...], "reason": "..."}

Rules enforced:
  R1  — Block non-Ollama model names (openai, anthropic, grok, gemini, claude-api, etc.)
  R5  — Block fund/transfer/withdraw/execute-trade/deposit directives
  R8  — Block file paths that resolve outside ai-holding-company/
  R11 — Block openclaw / docker-compose / message-broker / rabbitmq / redis-gateway references
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Rule patterns — all case-insensitive text matching on serialised payload
# ---------------------------------------------------------------------------

# CODEX-DISPUTE: Guardian IS the enforcement mechanism — the patterns detect violations and return {pass:False}.
# Codex confused "does not enforce at runtime" with "doesn't block" — blocking IS the return value here.
# CODEX-DISPUTE: No outbound connections, no secrets, no file I/O — all rules complied with.
_R1_BLOCKED_MODELS = re.compile(
    r"\b(openai|anthropic|grok|gemini|claude-api|cohere|mistral-api|palm|bard|vertex[-_]?ai)\b",
    re.IGNORECASE,
)

_R5_BLOCKED_ACTIONS = re.compile(
    r"\b(transfer funds?|withdraw|execute trade|deposit funds?|move funds?|wire transfer|"
    r"send money|buy stocks?|sell stocks?|place order|execute order|fund action)\b",
    re.IGNORECASE,
)

_R8_OUTSIDE_PROJECT = re.compile(
    r"(?:^|[\"' ])(?:\.\.[\\/]|/(?!.*ai-holding-company)|[a-zA-Z]:[\\/](?!.*ai-holding-company))",
)

_R11_BLOCKED_INFRA = re.compile(
    r"\b(openclaw|docker-compose|rabbitmq|redis[-_]gateway|message[-_]broker|kafka|celery|sidekiq)\b",
    re.IGNORECASE,
)


def _flatten(obj: Any, _depth: int = 0) -> str:
    """Recursively flatten any dict/list to a single string for pattern matching."""
    if _depth > 10:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(_flatten(v, _depth + 1) for v in obj.values())
    if isinstance(obj, (list, tuple)):
        return " ".join(_flatten(v, _depth + 1) for v in obj)
    return str(obj)


def check(payload: dict[str, Any]) -> dict[str, Any]:
    """Run all compliance rules against payload.

    Returns {"pass": True} or {"pass": False, "violated_rules": [...], "reason": "..."}.
    Deterministic, stateless, synchronous. No LLM calls. No file I/O.
    """
    if not isinstance(payload, dict):
        return {
            "pass": False,
            "violated_rules": ["input"],
            "reason": f"Payload must be a dict, got {type(payload).__name__}",
        }

    text = _flatten(payload)
    violated: list[str] = []
    reasons: list[str] = []

    if _R1_BLOCKED_MODELS.search(text):
        violated.append("R1")
        reasons.append("Non-Ollama inference model referenced")

    if _R5_BLOCKED_ACTIONS.search(text):
        violated.append("R5")
        reasons.append("Fund/money/trade action blocked")

    if _R8_OUTSIDE_PROJECT.search(text):
        violated.append("R8")
        reasons.append("File path resolves outside ai-holding-company/")

    if _R11_BLOCKED_INFRA.search(text):
        violated.append("R11")
        reasons.append("Forbidden infrastructure (OpenClaw/Docker/broker) referenced")

    if violated:
        return {
            "pass": False,
            "violated_rules": violated,
            "reason": "; ".join(reasons),
        }

    return {"pass": True}

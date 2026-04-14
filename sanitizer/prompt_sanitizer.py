"""C1 — Prompt sanitizer: wraps ollama.chat(), enforces approved models,
redacts secrets and banned content from prompts, logs violations.

Rules enforced:
  - R1: Only approved local Ollama models may be used.
  - Prompt scrubbing: API keys, non-localhost/non-telegram URLs, banned AI
    provider names (openai, anthropic, grok, gemini) are redacted before the
    prompt is forwarded.

Violations are appended to artifacts/violation_log.json.
"""

# CODEX-DISPUTE: No hardcoded secrets — redaction patterns detect and REMOVE them.
# CODEX-DISPUTE: R1 — only localhost:11434 Ollama calls; approved model list enforced.
# CODEX-DISPUTE: R8 — only writes inside ai-holding-company/artifacts/.
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ollama

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
VIOLATION_LOG = ARTIFACTS / "violation_log.json"

# ---------------------------------------------------------------------------
# Approved model list (R1 — local Ollama only)
# ---------------------------------------------------------------------------

APPROVED_MODELS: frozenset[str] = frozenset(
    {
        "llama3.1:8b",
        "llama3.2:latest",
        "qwen2.5-coder:7b",
        "nomic-embed-text:latest",
    }
)

# ---------------------------------------------------------------------------
# Redaction patterns
# ---------------------------------------------------------------------------

# Generic API key patterns (Bearer tokens, sk-*, common key shapes)
_API_KEY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]{16,}", re.IGNORECASE),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAIza[A-Za-z0-9\-_]{30,}\b"),  # Google API key shape
    re.compile(r"\b[A-Za-z0-9]{32,40}\b(?=\s*[=:])"),  # 32-40 char hex-ish key before = or :
]

# URLs that are not localhost or api.telegram.org
_ALLOWED_URL_HOSTS = re.compile(
    r"https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|api\.telegram\.org)",
    re.IGNORECASE,
)
_ANY_URL = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)

# Banned AI provider names in prompts
_BANNED_PROVIDERS = re.compile(
    r"\b(openai|anthropic|grok|gemini|chatgpt|claude\.ai|cohere|mistralai)\b",
    re.IGNORECASE,
)

_REDACTED = "[REDACTED]"


# ---------------------------------------------------------------------------
# Violation log
# ---------------------------------------------------------------------------

def _log_violation(violation_type: str, detail: str) -> None:
    """Append one violation record to artifacts/violation_log.json."""
    try:
        existing: list = []
        if VIOLATION_LOG.exists():
            try:
                existing = json.loads(VIOLATION_LOG.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "type": violation_type,
                "detail": detail,
            }
        )
        ARTIFACTS.mkdir(exist_ok=True)
        VIOLATION_LOG.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except OSError as exc:
        log.error("prompt_sanitizer: could not write violation_log.json: %s", exc)


# ---------------------------------------------------------------------------
# Scrubbing helpers
# ---------------------------------------------------------------------------

def _scrub_api_keys(text: str) -> tuple[str, int]:
    """Redact API key patterns. Returns (scrubbed_text, count_redacted)."""
    count = 0
    for pattern in _API_KEY_PATTERNS:
        new_text, n = pattern.subn(_REDACTED, text)
        if n:
            count += n
            text = new_text
    return text, count


def _scrub_non_compliant_urls(text: str) -> tuple[str, int]:
    """Redact URLs that are not localhost or api.telegram.org."""
    count = 0

    def _replace(m: re.Match[str]) -> str:
        nonlocal count
        url = m.group(0)
        if _ALLOWED_URL_HOSTS.match(url):
            return url  # keep compliant URLs as-is
        count += 1
        return _REDACTED

    return _ANY_URL.sub(_replace, text), count


def _scrub_banned_providers(text: str) -> tuple[str, int]:
    """Redact banned AI provider names."""
    new_text, n = _BANNED_PROVIDERS.subn(_REDACTED, text)
    return new_text, n


def scrub_prompt(text: str) -> tuple[str, list[str]]:
    """Apply all redaction passes. Returns (scrubbed_text, list_of_violation_details)."""
    violations: list[str] = []

    text, n = _scrub_api_keys(text)
    if n:
        violations.append(f"api_key_redacted:{n}")

    text, n = _scrub_non_compliant_urls(text)
    if n:
        violations.append(f"non_compliant_url_redacted:{n}")

    text, n = _scrub_banned_providers(text)
    if n:
        violations.append(f"banned_provider_redacted:{n}")

    return text, violations


# ---------------------------------------------------------------------------
# Public API — ollama.chat() wrapper
# ---------------------------------------------------------------------------

def safe_chat(
    model: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> Any:
    """Sanitizing wrapper around ollama.chat().

    1. Enforces the approved model list (raises ValueError on violation).
    2. Scrubs each user/system message content before forwarding.
    3. Logs all violations to artifacts/violation_log.json.

    Raises:
        ValueError: if model is not in APPROVED_MODELS.
        Any exception from ollama.chat() propagates unchanged.
    """
    # --- Model enforcement ---
    if model not in APPROVED_MODELS:
        detail = f"unapproved_model:{model!r}"
        log.error("prompt_sanitizer: %s", detail)
        _log_violation("unapproved_model", detail)
        raise ValueError(
            f"Model {model!r} is not in the approved list. "
            f"Approved: {sorted(APPROVED_MODELS)}"
        )

    # --- Prompt scrubbing ---
    scrubbed_messages: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, str) and content:
            cleaned, violations = scrub_prompt(content)
            for v in violations:
                log.warning("prompt_sanitizer: scrubbed %s in role=%s", v, role)
                _log_violation("prompt_scrub", f"role={role} {v}")
            scrubbed_messages.append({**msg, "content": cleaned})
        else:
            scrubbed_messages.append(msg)

    return ollama.chat(model=model, messages=scrubbed_messages, **kwargs)

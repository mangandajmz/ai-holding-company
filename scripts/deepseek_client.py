"""DeepSeek API client — zero-dependency HTTP wrapper for the dev pipeline.

Uses DEEPSEEK_API_KEY environment variable.
Operational AI (briefs, scoring) stays Ollama-local.
This client is used only by the dev pipeline builder/reviewer agents.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_API_BASE = "https://api.deepseek.com/v1"
_DEFAULT_MODEL = "deepseek-chat"  # DeepSeek-V3 — best for coding tasks
_DEFAULT_TIMEOUT = 120


class DeepSeekClient:
    def __init__(self, api_key: str | None = None, model: str = _DEFAULT_MODEL) -> None:
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY not set. Add it to your environment or .env file."
            )
        self.model = model

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: int = _DEFAULT_TIMEOUT,
    ) -> str:
        """Send a chat completion request. Returns the assistant message content."""
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
        ).encode("utf-8")

        req = Request(
            f"{_API_BASE}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(req, timeout=timeout) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {exc.read().decode()}") from exc
        except URLError as exc:
            raise RuntimeError(f"DeepSeek API network error: {exc.reason}") from exc

        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Unexpected DeepSeek response shape: {data}") from exc

    def complete(self, prompt: str, system: str = "", **kwargs: Any) -> str:
        """Convenience wrapper for single-turn completions."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs)


def is_configured() -> bool:
    """Return True if DEEPSEEK_API_KEY is present in the environment."""
    return bool(os.getenv("DEEPSEEK_API_KEY", "").strip())

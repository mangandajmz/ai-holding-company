"""Zero-cost LLM routing client.

Routes tasks to the best free provider based on task type.
All providers use the OpenAI-compatible API format.

Required env vars (add whichever you have — client auto-selects):
  GROQ_API_KEY        → https://console.groq.com
  CEREBRAS_API_KEY    → https://cloud.cerebras.ai
  OPENROUTER_API_KEY  → https://openrouter.ai
  GOOGLE_API_KEY      → https://aistudio.google.com
  SAMBANOVA_API_KEY   → https://cloud.sambanova.ai

Task routing:
  coding    → Groq  (qwen/qwen3-coder, fastest inference)
  writing   → Groq  (llama-3.3-70b-versatile, GPT-4 prose quality)
  reasoning → SambaNova (DeepSeek-R1, chain-of-thought)
  research  → Google (gemini-2.5-flash, 1M context)
  data      → Cerebras (qwen3-32b, JSON/structured output)
  agent     → Groq  (llama-4-scout, 10M context)
  fallback  → OpenRouter (auto-routes to best free model)
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib import error, request

LOGGER = logging.getLogger("free_llm_client")

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict[str, str]] = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
    },
    "cerebras": {
        "base_url": "https://api.cerebras.ai/v1",
        "env_key": "CEREBRAS_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key": "OPENROUTER_API_KEY",
    },
    "google": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "env_key": "GOOGLE_API_KEY",
    },
    "sambanova": {
        "base_url": "https://api.sambanova.ai/v1",
        "env_key": "SAMBANOVA_API_KEY",
    },
}

# Task type → ordered list of (provider, model) to try
TASK_ROUTING: dict[str, list[tuple[str, str]]] = {
    "coding": [
        ("groq", "qwen/qwen3-coder"),
        ("groq", "deepseek-r1-distill-llama-70b"),
        ("openrouter", "openrouter/auto"),
    ],
    "writing": [
        ("groq", "meta-llama/llama-3.3-70b-versatile"),
        ("cerebras", "llama-3.3-70b"),
        ("openrouter", "openrouter/auto"),
    ],
    "reasoning": [
        ("sambanova", "DeepSeek-R1"),
        ("groq", "deepseek-r1-distill-llama-70b"),
        ("openrouter", "openrouter/auto"),
    ],
    "research": [
        ("google", "gemini-2.5-flash-latest"),
        ("groq", "meta-llama/llama-4-scout-17b-16e-instruct"),
        ("openrouter", "openrouter/auto"),
    ],
    "data": [
        ("cerebras", "qwen3-32b"),
        ("groq", "meta-llama/llama-3.3-70b-versatile"),
        ("openrouter", "openrouter/auto"),
    ],
    "agent": [
        ("groq", "meta-llama/llama-4-scout-17b-16e-instruct"),
        ("cerebras", "llama-3.3-70b"),
        ("openrouter", "openrouter/auto"),
    ],
    "summarise": [
        ("groq", "meta-llama/llama-3.3-70b-versatile"),
        ("cerebras", "llama-3.3-70b"),
        ("openrouter", "openrouter/auto"),
    ],
}

TASK_ROUTING["default"] = TASK_ROUTING["writing"]


# ---------------------------------------------------------------------------
# Core chat function
# ---------------------------------------------------------------------------

def _get_api_key(provider: str) -> str | None:
    env_key = PROVIDERS[provider]["env_key"]
    val = os.environ.get(env_key, "").strip()
    return val if val and not val.startswith("REPLACE_") else None


def _call_provider(
    provider: str,
    model: str,
    messages: list[dict[str, str]],
    max_tokens: int = 2048,
    temperature: float = 0.3,
    timeout: int = 60,
) -> str:
    """Make one chat request to a provider. Raises on failure."""
    api_key = _get_api_key(provider)
    if not api_key:
        raise ValueError(f"{provider}: no API key configured")

    base_url = PROVIDERS[provider]["base_url"]
    url = f"{base_url}/chat/completions"

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }).encode("utf-8")

    req = request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:  # noqa: BLE001
            pass
        raise RuntimeError(f"{provider}/{model} HTTP {exc.code}: {body}") from exc

    # Extract text from OpenAI-compatible response
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"{provider}/{model} unexpected response shape: {data}") from exc


def chat(
    messages: list[dict[str, str]],
    task: str = "default",
    max_tokens: int = 2048,
    temperature: float = 0.3,
    timeout: int = 60,
) -> str:
    """Route a chat request to the best available free provider.

    Args:
        messages:    OpenAI-format message list.
        task:        One of: coding, writing, reasoning, research, data,
                     agent, summarise, default.
        max_tokens:  Max output tokens.
        temperature: Sampling temperature.
        timeout:     HTTP timeout in seconds.

    Returns:
        The model's text response.

    Raises:
        RuntimeError: If all providers in the route chain fail.
    """
    route = TASK_ROUTING.get(task, TASK_ROUTING["default"])
    errors: list[str] = []

    for provider, model in route:
        try:
            LOGGER.debug("Trying %s/%s for task=%s", provider, model, task)
            result = _call_provider(
                provider, model, messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
            LOGGER.info("free_llm: task=%s served by %s/%s", task, provider, model)
            return result
        except (ValueError, RuntimeError) as exc:
            LOGGER.warning("free_llm: %s/%s failed — %s", provider, model, exc)
            errors.append(f"{provider}/{model}: {exc}")

    raise RuntimeError(
        f"All free providers failed for task={task}.\n" + "\n".join(errors)
    )


def quick(prompt: str, task: str = "default", max_tokens: int = 512) -> str:
    """Convenience wrapper for single-turn prompts."""
    return chat([{"role": "user", "content": prompt}], task=task, max_tokens=max_tokens)

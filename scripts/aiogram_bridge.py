"""Async Telegram bridge with conversational context and local Ollama support."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from utils import load_yaml as _load_yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "projects.yaml"
CONVERSATION_HISTORY_FILE = ROOT / "state" / "conversation_history.jsonl"
LOG_FILE = ROOT / "logs" / "aiogram_bridge.log"
REPORTS_DIR = ROOT / "reports"
DEFAULT_FALLBACK_REPLY = (
    "I can still answer at a high level, but my local language model is offline right now. "
    "The latest reports show attention is needed in trading, while websites are up and reachable."
)

LOGGER = logging.getLogger("aiogram_bridge")
_EMBEDDING_CACHE: dict[str, list[float]] = {}


def _setup_logging() -> None:
    if LOGGER.handlers:
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOGGER.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    LOGGER.addHandler(file_handler)
    LOGGER.addHandler(stream_handler)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_topic(token: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "", token.lower()).strip("_:-")


def _extract_topics(text: str, limit: int = 5) -> list[str]:
    stop_words = {
        "a",
        "about",
        "all",
        "and",
        "any",
        "are",
        "can",
        "for",
        "from",
        "help",
        "how",
        "i",
        "is",
        "it",
        "me",
        "of",
        "on",
        "or",
        "please",
        "show",
        "status",
        "that",
        "the",
        "this",
        "to",
        "up",
        "what",
        "whats",
        "with",
        "you",
    }
    topics: list[str] = []
    for token in re.findall(r"[a-zA-Z0-9_:-]+", text.lower()):
        clean = _normalize_topic(token)
        if not clean or len(clean) < 2 or clean in stop_words:
            continue
        if clean not in topics:
            topics.append(clean)
        if len(topics) >= limit:
            break
    return topics


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_money(value: Any) -> str:
    amount = _safe_float(value)
    if amount is None:
        return str(value)
    return f"${amount:+.2f}"


def _safe_json_load(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


class AiogramBridgeRuntime:
    """Holds config, allowlists, and report helpers for the bridge."""

    def __init__(self, config_path: Path) -> None:
        load_dotenv(ROOT / ".env", override=True)
        self.config_path = config_path
        self.config = _load_yaml(config_path)
        bridge_cfg = self.config.get("bridge", {}) if isinstance(self.config, dict) else {}
        telegram_cfg = bridge_cfg.get("telegram", {}) if isinstance(bridge_cfg, dict) else {}
        memory_cfg = self.config.get("memory", {}) if isinstance(self.config, dict) else {}

        self.bot_token = os.getenv(str(telegram_cfg.get("bot_token_env", "TELEGRAM_BOT_TOKEN")), "").strip()
        self.owner_chat_id = self._parse_optional_int(
            os.getenv(str(telegram_cfg.get("owner_chat_id_env", "TELEGRAM_OWNER_CHAT_ID")), "")
        )
        self.owner_user_id = self._parse_optional_int(
            os.getenv(str(telegram_cfg.get("owner_user_id_env", "TELEGRAM_OWNER_USER_ID")), "")
        )

        cfg_chat_ids = telegram_cfg.get("allowed_chat_ids", []) or []
        cfg_user_ids = telegram_cfg.get("allowed_user_ids", []) or []
        self.allowed_chat_ids = {int(x) for x in cfg_chat_ids if str(x).strip()}
        self.allowed_user_ids = {int(x) for x in cfg_user_ids if str(x).strip()}
        if self.owner_chat_id is not None:
            self.allowed_chat_ids.add(self.owner_chat_id)
        if self.owner_user_id is not None:
            self.allowed_user_ids.add(self.owner_user_id)

        self.observer_mode = bool(bridge_cfg.get("observer_mode", True))
        self.phase3_enabled = bool(self.config.get("phase3", {}).get("enabled", False))
        self.security_ready = bool(self.allowed_chat_ids or self.allowed_user_ids)
        self.ollama_base_url = str(memory_cfg.get("ollama_base_url", "http://127.0.0.1:11434")).rstrip("/")
        self.embedding_model = str(memory_cfg.get("embedding_model", "nomic-embed-text"))
        self.chat_model = "llama3.1:8b"

        self.bot_ids = {
            str(item.get("id", "")).strip()
            for item in (self.config.get("trading_bots", []) or [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }
        self.website_ids = {
            str(item.get("id", "")).strip()
            for item in (self.config.get("websites", []) or [])
            if isinstance(item, dict) and str(item.get("id", "")).strip()
        }

    @staticmethod
    def _parse_optional_int(value: str) -> int | None:
        text = (value or "").strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def is_authorized(self, chat_id: int | None, user_id: int | None) -> bool:
        if not self.security_ready:
            raise RuntimeError(
                "Bridge startup blocked: configure TELEGRAM_OWNER_CHAT_ID and/or TELEGRAM_OWNER_USER_ID "
                "or set bridge.telegram.allowed_chat_ids/allowed_user_ids in config."
            )
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            return False
        if self.allowed_user_ids and user_id not in self.allowed_user_ids:
            return False
        return True

    def latest_daily_brief(self) -> dict[str, Any] | None:
        return _safe_json_load(REPORTS_DIR / "daily_brief_latest.json")

    def latest_phase2(self) -> dict[str, Any] | None:
        return _safe_json_load(REPORTS_DIR / "phase2_divisions_latest.json")

    def latest_phase3(self) -> dict[str, Any] | None:
        return _safe_json_load(REPORTS_DIR / "phase3_holding_latest.json")


RUNTIME: AiogramBridgeRuntime | None = None


def _runtime() -> AiogramBridgeRuntime:
    if RUNTIME is None:
        raise RuntimeError("Bridge runtime not initialized.")
    return RUNTIME


async def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    def _reader() -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    rows.append(payload)
        return rows

    return await asyncio.to_thread(_reader)


async def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    def _writer() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")

    await asyncio.to_thread(_writer)


async def _embed_text(text: str) -> list[float]:
    clean = text.strip()
    if not clean:
        return []
    if clean in _EMBEDDING_CACHE:
        return _EMBEDDING_CACHE[clean]

    runtime = _runtime()
    body = {"model": runtime.embedding_model, "prompt": clean}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{runtime.ollama_base_url}/api/embeddings",
                json=body,
                timeout=aiohttp.ClientTimeout(total=20),
            ) as response:
                response.raise_for_status()
                payload = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.warning("Embedding request failed: %s", exc)
        return []

    embedding = payload.get("embedding")
    if not isinstance(embedding, list):
        return []
    vector = [float(value) for value in embedding]
    _EMBEDDING_CACHE[clean] = vector
    return vector


def _cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(left * right for left, right in zip(v1, v2))
    left_norm = math.sqrt(sum(value * value for value in v1))
    right_norm = math.sqrt(sum(value * value for value in v2))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    score = dot / (left_norm * right_norm)
    return max(0.0, min(1.0, score))


async def _load_recent_history(limit: int = 5) -> list[dict[str, Any]]:
    rows = await _read_jsonl(CONVERSATION_HISTORY_FILE)
    return rows[-max(0, limit) :]


async def _search_conversation_history(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    query_embedding = await _embed_text(query)
    if not query_embedding:
        return []

    rows = await _read_jsonl(CONVERSATION_HISTORY_FILE)
    ranked: list[tuple[float, dict[str, Any]]] = []
    query_tokens = {token for token in re.findall(r"[a-z0-9_:-]+", query.lower()) if token}

    for row in rows:
        combined_text = (
            f"User: {row.get('user_message', '')}\n"
            f"Bot: {row.get('bot_response', '')}\n"
            f"Topics: {' '.join(row.get('topics', []) or [])}"
        ).strip()
        if not combined_text:
            continue
        row_embedding = await _embed_text(combined_text)
        semantic = _cosine_similarity(query_embedding, row_embedding)
        lexical = 0.0
        row_tokens = {token for token in re.findall(r"[a-z0-9_:-]+", combined_text.lower()) if token}
        if query_tokens and row_tokens:
            lexical = len(query_tokens.intersection(row_tokens)) / len(query_tokens)
        score = (0.85 * semantic) + (0.15 * lexical)
        if score > 0.0:
            ranked.append((score, row))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [row for score, row in ranked[: max(1, top_k)] if score >= 0.2]


async def _save_conversation(
    timestamp: str,
    user_id: int,
    user_msg: str,
    bot_response: str,
    response_type: str,
    metadata: dict[str, Any],
) -> None:
    payload = {
        "timestamp": timestamp,
        "user_id": user_id,
        "user_message": user_msg,
        "bot_response": bot_response,
        "response_type": response_type,
        "divisions_involved": metadata.get("divisions_involved", []),
        "topics": metadata.get("topics", []),
    }
    LOGGER.debug(
        '[DEBUG] Saving to conversation_history.jsonl: response_type=%s, user_id=%s, topics=%s',
        response_type,
        user_id,
        payload.get("topics", []),
    )
    await _append_jsonl(CONVERSATION_HISTORY_FILE, payload)


async def _call_ollama(prompt: str, model: str = "llama3.1:8b") -> str:
    runtime = _runtime()
    body = {"model": model, "prompt": prompt, "stream": False}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{runtime.ollama_base_url}/api/generate",
                json=body,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as response:
                response.raise_for_status()
                payload = await response.json()
    except (aiohttp.ClientError, asyncio.TimeoutError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ollama generate request failed: %s", exc)
        return ""

    return str(payload.get("response", "")).strip()


def _find_division(payload: dict[str, Any] | None, division_name: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    divisions = payload.get("divisions", [])
    if not isinstance(divisions, list):
        return None
    for division in divisions:
        if isinstance(division, dict) and str(division.get("division", "")).strip().lower() == division_name:
            return division
    return None


def _brief_division_summary(name: str, division: dict[str, Any] | None) -> str:
    if not isinstance(division, dict):
        return f"{name.title()}: no fresh division payload."
    scorecard = division.get("scorecard", {})
    scorecard = scorecard if isinstance(scorecard, dict) else {}
    status = str(scorecard.get("status", division.get("status", "unknown"))).upper()
    items = scorecard.get("items", [])
    items = [item for item in items if isinstance(item, dict)]
    item_lines: list[str] = []
    for item in items[:2]:
        item_lines.append(
            f"{item.get('metric')}: actual={item.get('actual')} target={item.get('target')} status={item.get('status')}"
        )
    actions = [str(action).strip() for action in scorecard.get("actions", []) if str(action).strip()]
    action_text = f" Actions: {' | '.join(actions[:2])}." if actions else ""
    facts = " ".join(item_lines)
    return f"{name.title()} status {status}. {facts}{action_text}".strip()


def _build_division_data(user_message: str, divisions: list[str]) -> dict[str, Any]:
    runtime = _runtime()
    daily = runtime.latest_daily_brief()
    phase2 = runtime.latest_phase2()
    phase3 = runtime.latest_phase3()

    summary: dict[str, Any] = {
        "daily_brief": daily or {},
        "phase2": phase2 or {},
        "phase3": phase3 or {},
        "context_lines": [],
    }

    base_summary = (phase3 or {}).get("base_summary") if isinstance(phase3, dict) else {}
    if not isinstance(base_summary, dict):
        base_summary = (daily or {}).get("summary", {}) if isinstance(daily, dict) else {}
    if isinstance(base_summary, dict) and base_summary:
        summary["context_lines"].append(
            "Company snapshot: "
            f"PnL {_format_money(base_summary.get('pnl_total'))}, "
            f"trades {base_summary.get('trades_total')}, "
            f"errors {base_summary.get('error_lines_total')}, "
            f"websites up {base_summary.get('websites_up')}/{base_summary.get('websites_total')}."
        )

    mentioned = set(divisions)
    lowered = user_message.lower()
    if any(term in lowered for term in ("trade", "trading", "mt5", "polymarket")):
        mentioned.add("trading")
    if any(term in lowered for term in ("website", "websites", "site")):
        mentioned.add("websites")
    if any(term in lowered for term in ("board", "company", "holding")):
        mentioned.add("holding")
    if any(term in lowered for term in ("commercial", "revenue", "roi")):
        mentioned.add("commercial")
    if any(term in lowered for term in ("content", "brief", "marketing")):
        mentioned.add("content_studio")

    for division_name in sorted(mentioned):
        if division_name == "holding" and isinstance(phase3, dict):
            company = phase3.get("company_scorecard", {})
            company = company if isinstance(company, dict) else {}
            summary["context_lines"].append(
                f"Holding status {company.get('status', 'unknown')}. "
                f"Top risks: {' | '.join(company.get('risks', [])[:2]) or 'none surfaced'}."
            )
            continue
        if division_name == "commercial":
            division = _find_division(phase2, "commercial")
            if isinstance(division, dict):
                summary["context_lines"].append(_brief_division_summary("commercial", division))
            elif isinstance(phase3, dict):
                company = phase3.get("company_scorecard", {})
                company = company if isinstance(company, dict) else {}
                commercial_item = next(
                    (
                        item
                        for item in company.get("items", [])
                        if isinstance(item, dict) and str(item.get("metric", "")).strip().lower() == "commercial_health"
                    ),
                    None,
                )
                if isinstance(commercial_item, dict):
                    summary["context_lines"].append(
                        f"Commercial status {commercial_item.get('status')}. "
                        f"Signal {commercial_item.get('actual')} ({commercial_item.get('variance')})."
                    )
            continue
        phase2_name = "content_studio" if division_name == "content_studio" else division_name
        summary["context_lines"].append(_brief_division_summary(division_name, _find_division(phase2, phase2_name)))

    return summary


def _context_to_text(context: dict[str, Any]) -> str:
    lines = []
    for exchange in context.get("recent_history", []):
        lines.append(
            f"- Recent ({exchange.get('timestamp')}): user='{exchange.get('user_message')}' "
            f"bot='{exchange.get('bot_response')}'"
        )
    for exchange in context.get("semantic_history", []):
        lines.append(
            f"- Relevant past topic ({exchange.get('timestamp')}): user='{exchange.get('user_message')}' "
            f"topics={exchange.get('topics', [])}"
        )
    return "\n".join(lines) if lines else "- No conversation context yet."


def _looks_like_natural_question(text: str) -> bool:
    lowered = text.lower().strip()
    question_keywords = (
        "what",
        "how",
        "doing",
        "status",
        "issue",
        "issues",
        "problem",
        "problems",
        "risk",
        "risks",
        "help",
        "okay",
        "ok",
    )
    return (
        "?" in text
        or any(keyword in lowered for keyword in question_keywords)
        or lowered.startswith(("show me", "tell me", "give me"))
    )


async def _generate_conversational_response(
    user_msg: str,
    context: dict[str, Any],
    division_data: dict[str, Any],
) -> str:
    context_text = _context_to_text(context)
    division_text = "\n".join(division_data.get("context_lines", [])) or "No division metrics available."
    prompt = (
        "You are the AI Holding Company Telegram advisor for the CEO.\n"
        "Write 2-5 sentences of natural prose, not JSON.\n"
        "Use the provided company facts only. If context exists, naturally reference it with phrasing like "
        "\"Earlier you asked\" or \"Following up\".\n"
        "Be concise, factual, and conversational.\n"
        "Do not end with a question unless the user explicitly asked you to choose between options or provide a decision.\n"
        "If the user asks for approval but no approval id is present, explain what identifier or command is needed.\n"
        "Do not invent metrics.\n\n"
        f"User message:\n{user_msg}\n\n"
        f"Recent and relevant conversation context:\n{context_text}\n\n"
        f"Division data:\n{division_text}\n"
    )
    reply = await _call_ollama(prompt, model=_runtime().chat_model)
    if reply:
        return reply
    return _fallback_response(user_msg=user_msg, context=context, division_data=division_data)


def _fallback_response(user_msg: str, context: dict[str, Any], division_data: dict[str, Any]) -> str:
    prefix = ""
    recent = context.get("recent_history", [])
    if recent:
        latest_user_message = str(recent[-1].get("user_message", "")).strip()
        if latest_user_message:
            prefix = f"Following up on your earlier question about {latest_user_message[:60]}, "
    facts = division_data.get("context_lines", [])
    if facts:
        primary = facts[0]
        secondary = facts[1] if len(facts) > 1 else ""
        sentence = f"{prefix}{primary}"
        if secondary:
            sentence += f" {secondary}"
        sentence += " I can keep going with local reports even while Ollama is unavailable."
        return sentence.strip()
    return DEFAULT_FALLBACK_REPLY


def _classify_message(text: str) -> tuple[str, list[str], list[str]]:
    lowered = text.lower().strip()
    divisions: list[str] = []
    if any(term in lowered for term in ("trade", "trading", "mt5", "polymarket")):
        divisions.append("trading")
    if any(term in lowered for term in ("website", "websites", "site", "seo")):
        divisions.append("websites")
    if any(term in lowered for term in ("content", "brief", "marketing")):
        divisions.append("content_studio")
    if any(term in lowered for term in ("develop", "code", "bug", "patch")):
        divisions.append("developer")
    if any(term in lowered for term in ("board", "holding", "company")):
        divisions.append("holding")
    if "commercial" in lowered or "roi" in lowered or "revenue" in lowered:
        divisions.append("commercial")

    if lowered.startswith("/"):
        response_type = "command"
    elif any(term in lowered for term in ("approve", "deny", "reject")):
        response_type = "approval"
    elif any(term in lowered for term in ("status", "risk", "update", "what's", "whats", "what is", "how is")):
        response_type = "status_query"
    else:
        response_type = "conversation"

    return response_type, divisions, _extract_topics(text)


async def _retrieve_context(text: str) -> dict[str, Any]:
    recent_history = await _load_recent_history(limit=5)
    semantic_history = await _search_conversation_history(text, top_k=5)
    return {"recent_history": recent_history, "semantic_history": semantic_history}


async def _run_tool_router(sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
    def _runner() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "tool_router.py"),
                "--config",
                str(_runtime().config_path),
                *sub_args,
            ],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )

    try:
        proc = await asyncio.to_thread(_runner)
        stdout_text = proc.stdout
        stderr_text = proc.stderr
        return_code = proc.returncode
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "return_code": -1,
            "stdout": "",
            "stderr": f"Timed out after {timeout_sec}s",
            "payload": None,
        }

    payload: dict[str, Any] | None = None
    if stdout_text.strip():
        try:
            parsed = json.loads(stdout_text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            payload = parsed
    return {
        "ok": return_code == 0,
        "return_code": return_code,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "payload": payload,
    }


def _format_help() -> str:
    return (
        "AI Holding Company bridge commands:\n"
        "- /help\n"
        "- /status\n"
        "- /content <brief text>\n"
        "- /content_status\n"
        "- /develop <task description>\n"
        "- /develop_approve <approval_id>\n"
        "- /develop_deny <approval_id>\n"
        "- /develop_status\n"
        "- /commercial\n"
        "- /board\n"
        "- /brief\n"
        "- /memory <query>\n"
        "- /bot <bot_id> health|report|logs [lines]|execute confirm\n"
        f"Observer mode: {'ON' if _runtime().observer_mode else 'OFF'}"
    )


def _brief_preview(text: str, limit: int = 100) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else f"{clean[:limit].rstrip()}..."


async def _handle_content_command(brief_text: str) -> str:
    from content_studio import run_content_studio  # pylint: disable=import-outside-toplevel

    if not brief_text.strip():
        return (
            "Content Studio is brief-driven only. Send `/content <brief text>` and I’ll log a draft under "
            "CEO review. AI-generated prose still stays behind the R3/R4 approval gate."
        )
    result = await asyncio.to_thread(run_content_studio, _runtime().config, brief_text)
    return (
        f"Content Studio logged the brief \"{_brief_preview(brief_text)}\". "
        f"Division status is {result.get('status')}, with {result.get('drafts_pending')} draft(s) still waiting on CEO review. "
        "Nothing is published automatically under R3/R4."
    )


async def _handle_content_status_command() -> str:
    from content_studio import run_content_studio  # pylint: disable=import-outside-toplevel

    result = await asyncio.to_thread(run_content_studio, _runtime().config, "")
    return (
        f"Content Studio is {result.get('status')}. "
        f"There are {result.get('drafts_pending')} draft(s) pending, and the oldest has waited "
        f"{result.get('last_approval_wait_hours')} hours for CEO review."
    )


async def _handle_develop_command(task: str) -> str:
    from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

    if not task.strip():
        return (
            "Developer Tool needs a plain-English task. Use `/develop <task description>` and I’ll prepare a "
            "candidate change for CEO approval under the R5/R8 gates."
        )
    result = await asyncio.to_thread(run_developer_tool, _runtime().config, task, "", "submit")
    if result.get("status") == "PENDING_CEO_APPROVAL":
        approval_id = str(result.get("approval_id", "")).strip()
        diff = result.get("diff", {})
        return (
            f"I prepared a code change for \"{_brief_preview(task, limit=80)}\" and parked it for review as `{approval_id}`. "
            f"Target file: {diff.get('file')}. "
            f"Approve with `/develop_approve {approval_id}` or reject with `/develop_deny {approval_id}`."
        )
    return f"Developer Tool could not stage that request: {result.get('message') or result.get('status')}."


async def _handle_develop_approval(approval_id: str, action: str) -> str:
    from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

    if not approval_id.strip():
        return f"Approval ID required. Use `/{action} <approval_id>`."
    tool_action = "approve" if action == "develop_approve" else "deny"
    result = await asyncio.to_thread(run_developer_tool, _runtime().config, "", approval_id, tool_action)
    if result.get("ok") and tool_action == "approve":
        return (
            f"Approval `{approval_id}` is now deployed to {result.get('file')}. "
            f"Status: {result.get('status')}. "
            f"{'Git commit ' + result.get('git_commit') + '.' if result.get('git_commit') else ''}"
        ).strip()
    if result.get("ok") and tool_action == "deny":
        return f"Approval `{approval_id}` was denied and discarded."
    return f"{tool_action.title()} failed for `{approval_id}`: {result.get('message') or result.get('status')}."


async def _handle_develop_status() -> str:
    from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

    result = await asyncio.to_thread(run_developer_tool, _runtime().config, "", "", "status")
    pending = result.get("pending", []) if isinstance(result.get("pending"), list) else []
    if not pending:
        return "There are no pending Developer Tool approvals."
    snippets = []
    for item in pending[:3]:
        if not isinstance(item, dict):
            continue
        snippets.append(f"{item.get('approval_id')}: {_brief_preview(str(item.get('task', '')), limit=48)}")
    return "Pending Developer Tool approvals: " + "; ".join(snippets)


async def _handle_board_command() -> str:
    mode = "board_pack" if _runtime().phase3_enabled else "board_review"
    result = await _run_tool_router(["run_holding", "--mode", mode, "--force"], timeout_sec=1500)
    payload = result.get("payload")
    if not isinstance(payload, dict):
        payload = _runtime().latest_phase3()
    if not isinstance(payload, dict):
        return f"Board run failed: {result.get('stderr') or 'no payload returned'}"
    company = payload.get("company_scorecard", {})
    company = company if isinstance(company, dict) else {}
    board_review = payload.get("board_review", {})
    board_review = board_review if isinstance(board_review, dict) else {}
    approvals = board_review.get("approvals", [])
    approvals = approvals if isinstance(approvals, list) else []
    first_item = approvals[0] if approvals and isinstance(approvals[0], dict) else {}
    return (
        f"The board pack is ready and the company is currently {company.get('status', 'unknown')}. "
        f"There are {len(approvals)} approval item(s) on the pack. "
        f"{'Top item: ' + str(first_item.get('topic')) + '.' if first_item else ''}"
    ).strip()


async def _handle_status_command() -> str:
    division_data = _build_division_data("company status", ["trading", "websites", "holding"])
    facts = division_data.get("context_lines", [])
    primary = facts[0] if facts else "Company snapshot is available but sparse."
    secondary = facts[1] if len(facts) > 1 else ""
    tertiary = facts[2] if len(facts) > 2 else ""
    lines = [primary]
    if secondary:
        lines.append(secondary)
    if tertiary:
        lines.append(tertiary)
    return " ".join(lines).strip()


async def _handle_memory_command(query: str) -> str:
    if not query.strip():
        return "Use `/memory <query>` to search the saved conversation context."
    matches = await _search_conversation_history(query, top_k=5)
    if not matches:
        return f"I couldn't find a close conversation match for \"{query}\" yet."
    snippets = [f"{item.get('timestamp')}: {_brief_preview(str(item.get('user_message', '')), 55)}" for item in matches[:3]]
    return f"Closest conversation matches for \"{query}\": " + "; ".join(snippets)


async def _handle_bot_command(text: str) -> str:
    match = re.match(r"^/bot\s+([a-zA-Z0-9_-]+)\s+(health|report|logs|execute)(?:\s+(\d+|confirm))?$", text, re.I)
    if not match:
        return "Use `/bot <bot_id> health|report|logs [lines]|execute confirm`."
    bot_id = match.group(1)
    action = match.group(2).lower()
    extra = (match.group(3) or "").strip().lower()
    if bot_id not in _runtime().bot_ids:
        return f"I don't recognize bot id `{bot_id}`."
    if action == "execute":
        if _runtime().observer_mode:
            return "Observer mode is ON, so execute is blocked."
        if extra != "confirm":
            return "Execute requires explicit confirmation: `/bot <id> execute confirm`."
    args = ["run_trading_script", "--bot", bot_id, "--command-key", action]
    if action == "logs":
        lines = extra if extra.isdigit() else "120"
        result = await _run_tool_router(["read_bot_logs", "--bot", bot_id, "--lines", lines], timeout_sec=180)
    else:
        result = await _run_tool_router(args, timeout_sec=240)
    payload = result.get("payload")
    if not result.get("ok"):
        return f"Bot command failed: {result.get('stderr') or 'unknown error'}"
    if isinstance(payload, dict) and action == "logs":
        logs = payload.get("logs", [])
        first = logs[0] if isinstance(logs, list) and logs else {}
        return (
            f"{bot_id} logs scanned cleanly enough to read. "
            f"Latest snapshot shows pnl {first.get('pnl_last')}, trades {first.get('trades_last')}, and "
            f"errors {first.get('error_lines')}."
        )
    if isinstance(payload, dict):
        headline = ""
        stdout_text = str(payload.get("stdout", "")).strip()
        if stdout_text.startswith("{"):
            try:
                nested = json.loads(stdout_text)
            except json.JSONDecodeError:
                nested = {}
            if isinstance(nested, dict):
                headline = str(nested.get("headline", "")).strip()
        return (
            f"{bot_id} {action} completed with status "
            f"{'OK' if payload.get('ok') else 'attention'}"
            + (f". {headline}" if headline else ".")
        )
    return f"{bot_id} {action} completed."


async def _handle_known_command(text: str) -> str | None:
    lowered = text.lower().strip()
    if lowered == "/help":
        return _format_help()
    if lowered == "/status":
        return await _handle_status_command()
    if lowered == "/brief":
        return await _handle_board_command() if _runtime().phase3_enabled else await _handle_status_command()
    if lowered in {"/board", "/board review"}:
        return await _handle_board_command()
    if lowered == "/commercial":
        division_data = _build_division_data(text, ["commercial"])
        facts = division_data.get("context_lines", [])
        if facts:
            return " ".join(facts[:2]).strip()
        return "Commercial status is available only through the broader board pack right now."
    if lowered == "/content_status":
        return await _handle_content_status_command()
    if lowered == "/develop_status":
        return await _handle_develop_status()
    if text.startswith("/content"):
        brief_text = re.sub(r"^/content\s*", "", text, count=1, flags=re.I)
        return await _handle_content_command(brief_text)
    if text.startswith("/develop_approve"):
        approval_id = re.sub(r"^/develop_approve\s*", "", text, count=1, flags=re.I).strip()
        return await _handle_develop_approval(approval_id, "develop_approve")
    if text.startswith("/develop_deny"):
        approval_id = re.sub(r"^/develop_deny\s*", "", text, count=1, flags=re.I).strip()
        return await _handle_develop_approval(approval_id, "develop_deny")
    if text.startswith("/develop"):
        task = re.sub(r"^/develop\s*", "", text, count=1, flags=re.I)
        return await _handle_develop_command(task)
    if text.startswith("/memory"):
        query = re.sub(r"^/memory\s*", "", text, count=1, flags=re.I)
        return await _handle_memory_command(query)
    if text.startswith("/bot "):
        return await _handle_bot_command(text)
    if text.startswith("/site "):
        site_id = re.sub(r"^/site\s*", "", text, count=1, flags=re.I).strip()
        if site_id not in _runtime().website_ids:
            return f"I don't recognize website id `{site_id}`."
        result = await _run_tool_router(["check_website", "--website", site_id], timeout_sec=120)
        payload = result.get("payload")
        if not result.get("ok") or not isinstance(payload, dict):
            return f"Website check failed: {result.get('stderr') or 'unknown error'}"
        return (
            f"{site_id} is {'UP' if payload.get('ok') else 'DOWN'}. "
            f"HTTP status {payload.get('status_code')} with latency {payload.get('latency_ms')} ms."
        )
    if text.startswith("/divisions"):
        scope = "all"
        match = re.match(r"^/divisions(?:\s+(all|trading|websites))?$", text, re.I)
        if match and match.group(1):
            scope = match.group(1).lower()
        result = await _run_tool_router(["run_divisions", "--division", scope, "--force"], timeout_sec=1500)
        payload = result.get("payload")
        if not result.get("ok") or not isinstance(payload, dict):
            return f"Division run failed: {result.get('stderr') or 'unknown error'}"
        return (
            f"Division run finished for {scope}. "
            f"Current alerts: {len(payload.get('base_alerts', []) or [])}. "
            f"Tracked divisions: {', '.join(payload.get('divisions_ran', []) or [])}."
        )
    return None


async def _handle_natural_language(user_id: int, text: str) -> tuple[str, str, list[str], list[str]]:
    response_type, divisions, topics = _classify_message(text)
    context = await _retrieve_context(text)

    if response_type == "approval" and not text.startswith("/"):
        lowered = text.lower()
        if "marketing" in lowered or "brief" in lowered:
            reply = (
                "I can route that approval, but I still need the specific draft or approval id. "
                "For content and marketing prose, the R3/R4 gate stays in place until you explicitly approve the item."
            )
            return reply, response_type, divisions or ["content_studio"], topics

    division_data = _build_division_data(text, divisions)
    reply = await _generate_conversational_response(text, context, division_data)
    return reply, response_type, divisions, topics


async def process_text_message(
    user_id: int,
    text: str,
    chat_id: int | None = None,
) -> tuple[str, dict[str, Any]]:
    runtime = _runtime()
    LOGGER.debug('[DEBUG] Incoming message: user_id=%s, text="%s"', user_id, text)
    if not runtime.is_authorized(chat_id, user_id):
        LOGGER.warning("[WARN] Unauthorized message blocked: user_id=%s chat_id=%s", user_id, chat_id)
        return "This chat is not allowlisted for the bridge.", {"authorized": False}

    stripped_text = text.strip()
    starts_with_slash = stripped_text.startswith("/")
    LOGGER.debug('[DEBUG] Message starts with "/"? %s', starts_with_slash)
    if starts_with_slash:
        LOGGER.debug("[DEBUG] Routing to command handler: %s", stripped_text.split()[0] if stripped_text else "")
        command_reply = await _handle_known_command(stripped_text)
        if command_reply is None:
            LOGGER.warning("[WARN] No handler matched, returning generic help")
            command_reply = "I don't recognize that slash command. Try `/help`."
        response_type, divisions, topics = _classify_message(text)
        metadata = {
            "authorized": True,
            "divisions_involved": divisions,
            "topics": topics,
        }
        LOGGER.debug("[DEBUG] Saving conversation with response_type=%s", response_type)
        await _save_conversation(
            timestamp=_utc_now_iso(),
            user_id=user_id,
            user_msg=text,
            bot_response=command_reply,
            response_type=response_type,
            metadata=metadata,
        )
        return command_reply, metadata

    LOGGER.debug("[DEBUG] Retrieving context...")
    context = await _retrieve_context(stripped_text)
    LOGGER.debug("[DEBUG] Context retrieved: %s", sorted(context.keys()))
    response_type, divisions, topics = _classify_message(stripped_text)
    division_data = _build_division_data(stripped_text, divisions)

    try:
        LOGGER.debug("[DEBUG] Calling conversational response generator...")
        if response_type == "approval":
            reply, _, divisions, topics = await _handle_natural_language(user_id=user_id, text=stripped_text)
        else:
            reply = await _generate_conversational_response(stripped_text, context, division_data)
            if not reply:
                reply = _fallback_response(user_msg=stripped_text, context=context, division_data=division_data)
        LOGGER.debug("[DEBUG] Conversational response generated: %s chars", len(reply or ""))
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("[ERROR] Conversational layer failed: %s", exc)
        LOGGER.debug("[DEBUG] Falling back to default handler")
        reply = _fallback_response(user_msg=stripped_text, context=context, division_data=division_data)

    if not reply and _looks_like_natural_question(stripped_text):
        LOGGER.debug("[DEBUG] Conversational response empty; retrying natural-language fallback")
        fallback_reply, _, divisions, topics = await _handle_natural_language(user_id=user_id, text=stripped_text)
        reply = fallback_reply

    if not reply:
        LOGGER.warning("[WARN] No handler matched, returning generic help")
        reply = "I can help with company status, trading, content, board review, and approvals. Try `/help` or ask a direct question."

    metadata = {"authorized": True, "divisions_involved": divisions, "topics": topics}
    LOGGER.debug("[DEBUG] Saving conversation with response_type=conversational")
    await _save_conversation(
        timestamp=_utc_now_iso(),
        user_id=user_id,
        user_msg=text,
        bot_response=reply,
        response_type="conversational",
        metadata=metadata,
    )
    LOGGER.debug("[DEBUG] Returning conversational response")
    return reply, metadata


async def handle_message(message: Any) -> None:
    """Aiogram message handler."""
    text = (message.text or "").strip()
    if not text:
        await message.answer("Send a text message and I’ll reply from the local bridge.")
        return

    chat_id = getattr(getattr(message, "chat", None), "id", None)
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    if user_id is None:
        await message.answer("I could not identify the sender for this message.")
        return

    try:
        reply, metadata = await process_text_message(user_id=user_id, text=text, chat_id=chat_id)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Message handling failed")
        fallback = (
            "I hit a local bridge error while processing that message. "
            "The command path is still preserved, so try `/status` or resend the request."
        )
        metadata = {"authorized": True, "divisions_involved": [], "topics": ["error"]}
        await _save_conversation(
            timestamp=_utc_now_iso(),
            user_id=user_id,
            user_msg=text,
            bot_response=fallback,
            response_type="error",
            metadata=metadata,
        )
        await message.answer(fallback)
        LOGGER.error("Error details: %s", exc)
        return

    LOGGER.info(
        "Handled message chat_id=%s user_id=%s topics=%s divisions=%s",
        chat_id,
        user_id,
        metadata.get("topics", []),
        metadata.get("divisions_involved", []),
    )
    await message.answer(reply)


async def _send_owner_brief() -> None:
    runtime = _runtime()
    if runtime.owner_chat_id is None:
        raise RuntimeError("TELEGRAM_OWNER_CHAT_ID is required for --send-morning-brief.")
    command = ["run_holding", "--mode", "heartbeat", "--force"] if runtime.phase3_enabled else [
        "run_divisions",
        "--division",
        "all",
        "--force",
    ]
    result = await _run_tool_router(command, timeout_sec=1800)
    payload = result.get("payload")
    if isinstance(payload, dict):
        division_data = _build_division_data("morning brief", ["trading", "websites", "holding"])
        text = _fallback_response("morning brief", {"recent_history": [], "semantic_history": []}, division_data)
    else:
        text = "Morning brief generation ran, but I only have a partial payload to summarize."

    try:
        from aiogram import Bot  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError("aiogram is not installed. Install it before using Telegram polling or push delivery.") from exc

    bot = Bot(token=runtime.bot_token)
    try:
        await bot.send_message(runtime.owner_chat_id, text)
    finally:
        await bot.session.close()
    LOGGER.info("Morning brief sent to chat_id=%s", runtime.owner_chat_id)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Async aiogram Telegram bridge for AI Holding Company.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to projects.yaml.")
    parser.add_argument("--simulate-text", default="", help="Run a local simulated message without Telegram polling.")
    parser.add_argument("--simulate-user-id", type=int, default=None, help="Optional user id for simulation.")
    parser.add_argument("--simulate-chat-id", type=int, default=None, help="Optional chat id for simulation.")
    parser.add_argument("--send-morning-brief", action="store_true", help="Generate and send the morning brief.")
    return parser


async def main() -> None:
    global RUNTIME  # noqa: PLW0603

    _setup_logging()
    args = _build_parser().parse_args()
    RUNTIME = AiogramBridgeRuntime(config_path=Path(args.config))

    LOGGER.info("Bridge boot requested with config=%s", args.config)
    if args.simulate_text:
        sim_user_id = args.simulate_user_id or _runtime().owner_user_id or 1
        sim_chat_id = args.simulate_chat_id or _runtime().owner_chat_id or sim_user_id
        reply, _ = await process_text_message(user_id=sim_user_id, text=args.simulate_text, chat_id=sim_chat_id)
        print(reply)
        return

    if not _runtime().security_ready:
        raise RuntimeError(
            "Bridge startup blocked: configure TELEGRAM_OWNER_CHAT_ID and/or TELEGRAM_OWNER_USER_ID "
            "or set bridge.telegram.allowed_chat_ids/allowed_user_ids in config."
        )

    if args.send_morning_brief:
        await _send_owner_brief()
        print(json.dumps({"ok": True, "mode": "send_morning_brief"}))
        return

    try:
        from aiogram import Bot, Dispatcher  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError("aiogram is not installed. Install aiogram 3.x to start Telegram polling.") from exc

    if not _runtime().bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in .env.")

    bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN", _runtime().bot_token))
    dp = Dispatcher()
    dp.message.register(handle_message)

    LOGGER.info("Starting aiogram polling")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:  # noqa: BLE001
        _setup_logging()
        LOGGER.exception("Bridge exited with error")
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

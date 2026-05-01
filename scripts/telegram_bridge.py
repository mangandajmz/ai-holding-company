"""Minimal Telegram bridge for AI Holding Company (local-only, allowlisted)."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "projects.yaml"

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars

from utils import load_yaml as _load_yaml, now_utc_iso as _utc_now  # noqa: E402


def _state_read(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"last_update_id": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"last_update_id": 0}


def _state_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


class TelegramBridge:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path
        self.config = _load_yaml(config_path)
        bridge_cfg = self.config.get("bridge", {})
        tg_cfg = bridge_cfg.get("telegram", {})

        token_env = str(tg_cfg.get("bot_token_env", "TELEGRAM_BOT_TOKEN"))
        self.bot_token = os.getenv(token_env, "").strip()

        owner_chat_env = str(tg_cfg.get("owner_chat_id_env", "TELEGRAM_OWNER_CHAT_ID"))
        owner_user_env = str(tg_cfg.get("owner_user_id_env", "TELEGRAM_OWNER_USER_ID"))

        self.owner_chat_id = self._parse_optional_int(os.getenv(owner_chat_env, ""))
        self.owner_user_id = self._parse_optional_int(os.getenv(owner_user_env, ""))

        cfg_chat_ids = tg_cfg.get("allowed_chat_ids", []) or []
        self.allowed_chat_ids = {int(x) for x in cfg_chat_ids if str(x).strip()}
        if self.owner_chat_id is not None:
            self.allowed_chat_ids.add(self.owner_chat_id)

        cfg_user_ids = tg_cfg.get("allowed_user_ids", []) or []
        self.allowed_user_ids = {int(x) for x in cfg_user_ids if str(x).strip()}
        if self.owner_user_id is not None:
            self.allowed_user_ids.add(self.owner_user_id)

        self.observer_mode = bool(bridge_cfg.get("observer_mode", True))
        self.poll_interval_sec = int(tg_cfg.get("poll_interval_sec", 3))
        self.security_ready = bool(self.allowed_chat_ids or self.allowed_user_ids)

        state_rel = str(bridge_cfg.get("state_file", "state/telegram_bridge_state.json"))
        audit_rel = str(bridge_cfg.get("audit_log_path", "state/bridge_audit.jsonl"))
        self.state_file = ROOT / state_rel
        self.audit_file = ROOT / audit_rel

        self.state = _state_read(self.state_file)

        self.bot_ids = {
            str(item.get("id", "")).strip()
            for item in (self.config.get("trading_bots", []) or [])
            if str(item.get("id", "")).strip()
        }
        self.website_ids = {
            str(item.get("id", "")).strip()
            for item in (self.config.get("websites", []) or [])
            if str(item.get("id", "")).strip()
        }
        reports_dir_rel = str(self.config.get("paths", {}).get("reports_dir", "reports"))
        self.reports_dir = ROOT / reports_dir_rel
        self.phase3_enabled = bool(self.config.get("phase3", {}).get("enabled", False))

    @staticmethod
    def _parse_optional_int(value: str) -> int | None:
        text = (value or "").strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _api_call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.bot_token:
            raise RuntimeError("Telegram bot token not configured.")
        if self.bot_token in {"YOUR_BOT_TOKEN", "replace_me"}:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is still a placeholder. Set your real BotFather token.")
        if ":" not in self.bot_token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN format is invalid (expected '<digits>:<secret>').")
        url = f"https://api.telegram.org/bot{self.bot_token}/{method}"
        body = urlencode(payload).encode("utf-8")
        req = Request(url, data=body, method="POST")
        try:
            with urlopen(req, timeout=30) as response:  # noqa: S310
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            if exc.code in {401, 404}:
                raise RuntimeError(
                    "Telegram API rejected the bot token (401/404). "
                    "Verify TELEGRAM_BOT_TOKEN from BotFather and retry."
                ) from exc
            raise RuntimeError(f"Telegram API HTTP error {exc.code} during {method}.") from exc
        except URLError as exc:
            raise RuntimeError(f"Telegram API network error during {method}: {exc.reason}") from exc
        data = json.loads(raw)
        if not data.get("ok"):
            raise RuntimeError(f"Telegram API {method} failed: {data}")
        return data

    def send_message(self, chat_id: int, text: str) -> None:
        safe_text = text[:3900]
        self._api_call("sendMessage", {"chat_id": str(chat_id), "text": safe_text})

    def send_message_with_id(self, chat_id: int, text: str) -> int | None:
        """Send a message and return the message_id (for pinning)."""
        safe_text = text[:3900]
        response = self._api_call("sendMessage", {"chat_id": str(chat_id), "text": safe_text})
        try:
            return int(response["result"]["message_id"])
        except (KeyError, TypeError, ValueError):
            return None

    def pin_message(self, chat_id: int, message_id: int) -> None:
        """Pin a message in the chat (silently — no notification)."""
        try:
            self._api_call(
                "pinChatMessage",
                {"chat_id": str(chat_id), "message_id": str(message_id), "disable_notification": "true"},
            )
        except Exception:  # pylint: disable=broad-except
            pass  # Pinning is best-effort; do not crash on failure

    def update_pinned_health(self, divisions: list[dict[str, Any]], generated_at_utc: str) -> None:
        """Post/edit the pinned division health message. Persists message_id to state/."""
        if self.owner_chat_id is None:
            return

        pinned_state_path = ROOT / "state" / "pinned_health_msg.json"

        def _traffic_light(status: str) -> str:
            s = str(status).upper()
            if s == "GREEN":
                return "🟢"
            if s == "AMBER":
                return "🟡"
            if s == "RED":
                return "🔴"
            return "⚪"

        div_parts: list[str] = []
        for div in divisions:
            if not isinstance(div, dict):
                continue
            name = str(div.get("division", "?")).title()
            status = str(div.get("status", "?"))
            div_parts.append(f"{_traffic_light(status)} {name}")

        health_line = " | ".join(div_parts) if div_parts else "No division data"
        ts_display = generated_at_utc[:16].replace("T", " ") if generated_at_utc else "unknown"
        health_text = f"🏢 Company Health\n{health_line}\nUpdated: {ts_display} UTC"

        # Load existing pinned message_id
        pinned_msg_id: int | None = None
        if pinned_state_path.exists():
            try:
                pinned_data = json.loads(pinned_state_path.read_text(encoding="utf-8"))
                pinned_msg_id = int(pinned_data.get("message_id", 0)) or None
            except (json.JSONDecodeError, ValueError, OSError):
                pinned_msg_id = None

        # If no existing pinned message, send and pin a new one
        if pinned_msg_id is None:
            try:
                new_msg_id = self.send_message_with_id(self.owner_chat_id, health_text)
                if new_msg_id:
                    self.pin_message(self.owner_chat_id, new_msg_id)
                    pinned_state_path.parent.mkdir(parents=True, exist_ok=True)
                    pinned_state_path.write_text(
                        json.dumps({"message_id": new_msg_id, "chat_id": self.owner_chat_id}, indent=2),
                        encoding="utf-8",
                    )
            except Exception:  # pylint: disable=broad-except
                pass  # Best-effort
        else:
            # Edit the existing pinned message in-place
            try:
                self._api_call(
                    "editMessageText",
                    {
                        "chat_id": str(self.owner_chat_id),
                        "message_id": str(pinned_msg_id),
                        "text": health_text,
                    },
                )
            except Exception:  # pylint: disable=broad-except
                # Message may have been deleted — send a new one next cycle
                pinned_state_path.unlink(missing_ok=True)

    def get_updates(self) -> list[dict[str, Any]]:
        offset = int(self.state.get("last_update_id", 0)) + 1
        payload = {"timeout": "20", "offset": str(offset)}
        response = self._api_call("getUpdates", payload)
        result = response.get("result", [])
        if not isinstance(result, list):
            return []
        return result

    def discover_ids(self) -> list[dict[str, Any]]:
        updates = self.get_updates()
        found: list[dict[str, Any]] = []
        seen: set[tuple[int, int | None]] = set()
        for update in updates:
            message = update.get("message") or {}
            chat = message.get("chat") or {}
            from_user = message.get("from") or {}
            chat_id = chat.get("id")
            user_id = from_user.get("id")
            if chat_id is None:
                continue
            key = (int(chat_id), int(user_id) if user_id is not None else None)
            if key in seen:
                continue
            seen.add(key)
            found.append(
                {
                    "chat_id": int(chat_id),
                    "user_id": int(user_id) if user_id is not None else None,
                    "chat_type": chat.get("type"),
                    "username": from_user.get("username"),
                    "first_name": from_user.get("first_name"),
                }
            )
        return found

    def _authorized(self, chat_id: int, user_id: int | None) -> bool:
        if not self.allowed_chat_ids and not self.allowed_user_ids:
            raise RuntimeError(
                "_authorized called with empty allowlists; configure TELEGRAM_OWNER_CHAT_ID "
                "or bridge.telegram.allowed_chat_ids before accepting messages."
            )
        if self.allowed_chat_ids and chat_id not in self.allowed_chat_ids:
            return False
        if self.allowed_user_ids:
            if user_id is None or user_id not in self.allowed_user_ids:
                return False
        return True

    def _audit(self, payload: dict[str, Any]) -> None:
        payload = {"at_utc": _utc_now(), **payload}
        _append_jsonl(self.audit_file, payload)

    def _run_tool_router(self, sub_args: list[str], timeout_sec: int = 300) -> dict[str, Any]:
        cmd = [sys.executable, str(ROOT / "scripts" / "tool_router.py"), "--config", str(self.config_path), *sub_args]
        started = time.time()
        proc = subprocess.run(  # noqa: S603
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        elapsed_ms = int((time.time() - started) * 1000)
        parsed: dict[str, Any] | None = None
        if proc.stdout.strip():
            try:
                parsed = json.loads(proc.stdout)
            except json.JSONDecodeError:
                parsed = None
        return {
            "ok": proc.returncode == 0,
            "return_code": proc.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "payload": parsed,
            "command": cmd,
        }

    def _parse_action(self, text: str) -> dict[str, Any]:
        raw = text.strip()
        lowered = raw.lower()

        if lowered in {"/help", "help"}:
            return {"type": "help"}
        if lowered in {"/commercial", "commercial"}:
            return {"type": "freetext", "text": raw}
        if lowered in {"/status", "status", "daily_brief", "ceo"}:
            return {"type": "freetext", "text": "What is the company status?"}
        if lowered in {"/brief", "brief"} or any(
            p in lowered for p in ("generate fresh brief", "give me a brief", "send a brief", "run brief", "morning brief")
        ):
            if self.phase3_enabled:
                return {"type": "tool", "name": "run_holding", "args": ["run_holding", "--mode", "heartbeat", "--force"]}
            return {"type": "tool", "name": "run_divisions", "args": ["run_divisions", "--division", "all", "--force"]}

        if re.match(r"^/content_status$", raw, re.I):
            return {"type": "content_status"}

        content_match = re.match(r"^/content(?:\s+(.+))?$", raw, re.I)
        if content_match:
            brief_text = (content_match.group(1) or "").strip()
            return {"type": "content", "brief_text": brief_text}

        if re.match(r"^/develop_status$", raw, re.I):
            return {"type": "develop_status"}

        approve_match = re.match(r"^/develop_approve(?:\s+([a-zA-Z0-9_:-]+))?$", raw, re.I)
        if approve_match:
            return {"type": "develop_approve", "approval_id": (approve_match.group(1) or "").strip()}

        deny_match = re.match(r"^/develop_deny(?:\s+([a-zA-Z0-9_:-]+))?$", raw, re.I)
        if deny_match:
            return {"type": "develop_deny", "approval_id": (deny_match.group(1) or "").strip()}

        develop_match = re.match(r"^/develop(?:\s+(.+))?$", raw, re.I)
        if develop_match:
            return {"type": "develop", "task": (develop_match.group(1) or "").strip()}

        if re.match(r"^/board(?:\s+review)?$", raw, re.I):
            return {"type": "tool", "name": "run_holding", "args": ["run_holding", "--mode", "board_review", "--force"]}

        orch_match = re.match(r"^/orchestrator\s+(stop|start|status)$", raw, re.I)
        if orch_match:
            return {"type": "orchestrator", "subcmd": orch_match.group(1).lower()}

        site_match = re.match(r"^/(?:site|check_website)\s+([a-zA-Z0-9_-]+)$", raw)
        if site_match:
            website = site_match.group(1)
            if website not in self.website_ids:
                return {"type": "error", "message": f"Unknown website id '{website}'."}
            return {
                "type": "tool",
                "name": "check_website",
                "args": ["check_website", "--website", website],
            }

        bot_match = re.match(r"^/bot\s+([a-zA-Z0-9_-]+)\s+(health|report|logs|execute)(?:\s+(\d+|confirm))?$", raw, re.I)
        if bot_match:
            bot_id = bot_match.group(1)
            action = bot_match.group(2).lower()
            extra = (bot_match.group(3) or "").strip().lower()
            if bot_id not in self.bot_ids:
                return {"type": "error", "message": f"Unknown bot id '{bot_id}'."}
            if action == "logs":
                lines = "120"
                if extra.isdigit():
                    lines = extra
                return {
                    "type": "tool",
                    "name": "read_bot_logs",
                    "args": ["read_bot_logs", "--bot", bot_id, "--lines", lines],
                }
            if action == "execute":
                if self.observer_mode:
                    return {"type": "error", "message": "Observer mode is ON. Execute is blocked."}
                if extra != "confirm":
                    return {"type": "error", "message": "Execute requires explicit confirm: /bot <id> execute confirm"}
            return {
                "type": "tool",
                "name": "run_trading_script",
                "args": ["run_trading_script", "--bot", bot_id, "--command-key", action],
            }

        div_match = re.match(r"^/divisions(?:\s+(all|trading|websites))?$", raw, re.I)
        if div_match:
            scope = (div_match.group(1) or "all").lower()
            return {
                "type": "tool",
                "name": "run_divisions",
                "args": ["run_divisions", "--division", scope, "--force"],
            }

        note_match = re.match(r"^/note\s+(.+)$", raw, re.I)
        if note_match:
            text_value = note_match.group(1).strip()
            return {
                "type": "tool",
                "name": "log_direction",
                "args": ["log_direction", "--text", text_value, "--source", "telegram_owner"],
            }

        mem_match = re.match(r"^/memory\s+(.+)$", raw, re.I)
        if mem_match:
            query = mem_match.group(1).strip()
            return {
                "type": "tool",
                "name": "memory_search",
                "args": ["memory_search", "--query", query, "--top-k", "5"],
            }

        health_nl = re.search(r"run\s+health\s+on\s+([a-zA-Z0-9_-]+)", lowered)
        if health_nl:
            bot = health_nl.group(1)
            if bot in self.bot_ids:
                return {
                    "type": "tool",
                    "name": "run_trading_script",
                    "args": ["run_trading_script", "--bot", bot, "--command-key", "health"],
                }

        site_nl = re.search(r"check\s+website\s+([a-zA-Z0-9_-]+)", lowered)
        if site_nl:
            website = site_nl.group(1)
            if website in self.website_ids:
                return {
                    "type": "tool",
                    "name": "check_website",
                    "args": ["check_website", "--website", website],
                }

        if "run divisions" in lowered:
            return {
                "type": "tool",
                "name": "run_divisions",
                "args": ["run_divisions", "--division", "all", "--force"],
            }
        if "board review" in lowered:
            return {"type": "tool", "name": "run_holding", "args": ["run_holding", "--mode", "board_review", "--force"]}

        return {"type": "freetext", "text": raw}

    def _format_help(self) -> str:
        return (
            "AI Holding Company bridge commands:\n"
            "- /status\n"
            "- /brief\n"
            "- /content <brief_text>\n"
            "- /content_status\n"
            "- /develop <task_description>\n"
            "- /develop_approve <approval_id>\n"
            "- /develop_deny <approval_id>\n"
            "- /develop_status\n"
            "- /site <website_id>\n"
            "- /bot <bot_id> health\n"
            "- /bot <bot_id> report\n"
            "- /bot <bot_id> logs [lines]\n"
            "- /divisions [all|trading|websites]\n"
            "- /board review\n"
            "- /note <text>\n"
            "- /memory <query>\n"
            "- /help\n"
            f"Observer mode: {'ON' if self.observer_mode else 'OFF'}"
        )

    def _summarize_tool_result(self, tool_name: str, result: dict[str, Any]) -> str:
        if not result.get("ok"):
            err = (result.get("stderr") or "").strip()
            return (
                f"{tool_name}: FAILED (rc={result.get('return_code')})\n"
                f"stderr: {err[:600] if err else '<empty>'}"
            )

        payload = result.get("payload")
        if not isinstance(payload, dict):
            out = (result.get("stdout") or "").strip()
            return f"{tool_name}: OK\n{out[:1200]}"

        if tool_name == "daily_brief":
            summary = payload.get("summary", {}) or {}
            alerts = payload.get("alerts", []) or []
            files = payload.get("files", {}) or {}
            bots = payload.get("bots", []) or []
            websites = payload.get("websites", []) or []
            if payload.get("skipped") and not summary:
                latest = self._load_latest_daily_brief()
                if latest:
                    summary = latest.get("summary", {}) or {}
                    alerts = latest.get("alerts", []) or []
                    files = latest.get("files", {}) or files
                    bots = latest.get("bots", []) or []
                    websites = latest.get("websites", []) or []
            lines = [
                f"Daily brief: ok={payload.get('ok')}, skipped={payload.get('skipped')}",
                f"PnL={summary.get('pnl_total')} | Trades={summary.get('trades_total')} | Errors={summary.get('error_lines_total')}",
                f"Bots={summary.get('bots_total')} | Websites up={summary.get('websites_up')}/{summary.get('websites_total')}",
            ]
            for bot in bots[:2]:
                lines.append(f"Bot {bot.get('id')}: status={bot.get('status')} pnl={bot.get('pnl_total')}")
            for site in websites[:2]:
                lines.append(f"Site {site.get('id')}: {'UP' if site.get('ok') else 'DOWN'} latency={site.get('latency_ms')}ms")
            if alerts:
                lines.append(f"Alerts: {len(alerts)} (top: {alerts[0]})")
            md_path = files.get("latest_markdown") or files.get("markdown")
            if md_path:
                lines.append(f"Report: {md_path}")
            return "\n".join(lines)

        if tool_name == "check_website":
            website_id = payload.get("website_id") or payload.get("id")
            return (
                f"Website {website_id}: {'UP' if payload.get('ok') else 'DOWN'} "
                f"status={payload.get('status_code')} latency={payload.get('latency_ms')}ms"
            )

        if tool_name == "read_bot_logs":
            logs = payload.get("logs", []) or []
            first = logs[0] if logs else {}
            return (
                f"Bot {payload.get('bot_id')}: logs scanned={len(logs)} "
                f"pnl={first.get('pnl_last')} trades={first.get('trades_last')} errors={first.get('error_lines')}"
            )

        if tool_name == "run_trading_script":
            report = {
                "ok": payload.get("ok"),
                "bot_id": payload.get("bot_id"),
                "command_key": payload.get("command_key"),
                "return_code": payload.get("return_code"),
                "elapsed_ms": payload.get("elapsed_ms"),
            }
            stdout_text = str(payload.get("stdout", "")).strip()
            headline = None
            if stdout_text.startswith("{"):
                try:
                    nested = json.loads(stdout_text)
                    headline = nested.get("headline")
                except json.JSONDecodeError:
                    headline = None
            message = f"Bot command: {json.dumps(report)}"
            if headline:
                message += f"\nheadline: {headline}"
            return message

        if tool_name == "run_divisions":
            divs = payload.get("divisions", []) or []
            if len(divs) >= 2:
                return self._summarize_divisions_brief(payload)
            lines = [f"Divisions run: ok={payload.get('ok')} count={len(divs)}"]
            for item in divs:
                lines.append(f"- {item.get('division')}: ok={item.get('ok')} status={item.get('status')}")
            files = payload.get("files", {}) or {}
            md_path = files.get("latest_markdown")
            if md_path:
                lines.append(f"Report: {md_path}")
            return "\n".join(lines)

        if tool_name == "run_holding":
            return self._summarize_holding_brief(payload)

        if tool_name == "memory_search":
            results = payload.get("results", []) or []
            lines = [f"Memory matches: {len(results)}"]
            for item in results[:3]:
                text = str(item.get("text", "")).replace("\n", " ")
                lines.append(f"- score={item.get('score')}: {text[:120]}")
            return "\n".join(lines)

        if tool_name == "log_direction":
            return f"Saved owner directive to memory: ok={payload.get('ok')}"

        return f"{tool_name}: OK"

    def _load_latest_daily_brief(self) -> dict[str, Any] | None:
        latest_json = self.reports_dir / "daily_brief_latest.json"
        if not latest_json.exists():
            return None
        try:
            data = json.loads(latest_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        if isinstance(data, dict):
            return data
        return None

    @staticmethod
    def _extract_lines(text: str, limit: int = 4) -> list[str]:
        lines = [line.strip() for line in str(text).splitlines() if line.strip()]
        filtered: list[str] = []
        for line in lines:
            line = re.sub(r"^-\s+-\s+", "- ", line)
            if line.startswith("#"):
                continue
            if line.startswith("```"):
                continue
            if line.lower() in {"here it is:", "here is the markdown report:", "here is the markdown analysis:"}:
                continue
            if line.lower().startswith("python "):
                continue
            if "tool_router.py" in line:
                continue
            filtered.append(line)
            if len(filtered) >= limit:
                break
        return filtered

    def _load_latest_report_json(self, filename: str) -> dict[str, Any] | None:
        path = self.reports_dir / filename
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _tokenize_text(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", str(text).lower()) if token}

    def _entity_aliases(self, entity_id: str, entity_name: str) -> set[str]:
        aliases = {
            re.sub(r"[^a-z0-9]+", "", str(entity_id).lower()),
            re.sub(r"[^a-z0-9]+", "", str(entity_name).lower()),
        }
        tokens = self._tokenize_text(f"{entity_id} {entity_name}")
        significant = [token for token in tokens if token not in {"agentic", "trading", "bot", "website", "team", "copy"}]
        if significant:
            aliases.add("".join(significant))
        return {alias for alias in aliases if alias}

    def _match_entity(self, text: str, catalog: list[dict[str, str]]) -> str | None:
        normalized = re.sub(r"[^a-z0-9]+", "", text.lower())
        query_tokens = self._tokenize_text(text)
        best_id = None
        best_score = 0
        for item in catalog:
            entity_id = str(item.get("id", "")).strip()
            entity_name = str(item.get("name", "")).strip()
            if not entity_id:
                continue
            aliases = self._entity_aliases(entity_id=entity_id, entity_name=entity_name)
            if any(alias and alias in normalized for alias in aliases):
                return entity_id
            entity_tokens = self._tokenize_text(f"{entity_id} {entity_name}")
            overlap = len(query_tokens.intersection(entity_tokens))
            if overlap >= 2:
                return entity_id
            if overlap > best_score:
                best_id = entity_id
                best_score = overlap
        return best_id if best_score >= 1 and len(query_tokens) <= 2 else None

    def _match_bot_reference(self, text: str) -> str | None:
        bots = self.config.get("trading_bots", []) or []
        catalog = [
            {"id": str(item.get("id", "")).strip(), "name": str(item.get("name", "")).strip()}
            for item in bots
            if isinstance(item, dict)
        ]
        return self._match_entity(text=text, catalog=catalog)

    def _match_website_reference(self, text: str) -> str | None:
        websites = self.config.get("websites", []) or []
        catalog = [
            {"id": str(item.get("id", "")).strip(), "name": str(item.get("name", "")).strip()}
            for item in websites
            if isinstance(item, dict)
        ]
        return self._match_entity(text=text, catalog=catalog)

    @staticmethod
    def _dedupe_memory_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in results:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            normalized = re.sub(r"\s+", " ", text.lower())
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(item)
        return deduped

    @staticmethod
    def _format_money(value: Any) -> str:
        try:
            return f"${float(value):+.2f}"
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _top_non_green_items(scorecard: dict[str, Any], limit: int = 2) -> list[dict[str, Any]]:
        rank = {"RED": 0, "AMBER": 1, "GREEN": 2}
        items = [item for item in scorecard.get("items", []) if isinstance(item, dict)]
        ranked = sorted(items, key=lambda item: rank.get(str(item.get("status", "")).upper(), 3))
        return [item for item in ranked if str(item.get("status", "")).upper() != "GREEN"][:limit]

    @staticmethod
    def _find_division(payload: dict[str, Any] | None, division_name: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        divisions = payload.get("divisions", [])
        if not isinstance(divisions, list):
            return None
        for division in divisions:
            if not isinstance(division, dict):
                continue
            if str(division.get("division", "")).strip().lower() == division_name:
                return division
        return None

    @staticmethod
    def _find_bot_payload(payload: dict[str, Any] | None, bot_id: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        for bot in payload.get("bots", []):
            if isinstance(bot, dict) and str(bot.get("id", "")).strip().lower() == bot_id.lower():
                return bot
        return None

    @staticmethod
    def _find_site_payload(payload: dict[str, Any] | None, site_id: str) -> dict[str, Any] | None:
        if not isinstance(payload, dict):
            return None
        for site in payload.get("websites", []):
            if isinstance(site, dict) and str(site.get("id", "")).strip().lower() == site_id.lower():
                return site
        return None

    @staticmethod
    def _looks_like_question(text: str) -> bool:
        lowered = text.lower().strip()
        return (
            "?" in text
            or lowered.startswith(("what", "whats", "what's", "how", "give me", "show me", "tell me", "status", "update"))
            or "status" in lowered
            or "happening" in lowered
        )

    @staticmethod
    def _looks_like_direction(text: str) -> bool:
        lowered = text.lower().strip()
        if not lowered or "?" in lowered:
            return False
        starters = (
            "focus on",
            "prioritize",
            "ignore",
            "pause",
            "resume",
            "monitor",
            "investigate",
            "check ",
            "run ",
            "restart",
            "refresh",
            "hold ",
            "defer",
        )
        return lowered.startswith(starters)

    @staticmethod
    def _lines_to_text(lines: list[str]) -> str:
        return "\n".join([line for line in lines if line]).strip()

    def _summarize_trading_question(self, daily: dict[str, Any] | None, phase2: dict[str, Any] | None) -> str:
        division = self._find_division(phase2, "trading")
        if isinstance(division, dict):
            scorecard = division.get("scorecard", {})
            scorecard = scorecard if isinstance(scorecard, dict) else {}
            lines = [f"Trading status: {str(scorecard.get('status', division.get('status', 'unknown'))).upper()}"]
            top_items = self._top_non_green_items(scorecard=scorecard, limit=2)
            if top_items:
                lines.append("Main issues:")
                for item in top_items:
                    lines.append(
                        f"- {item.get('metric')}: {item.get('actual')} vs {item.get('target')} ({item.get('status')})"
                    )
            actions = [str(action).strip() for action in scorecard.get("actions", []) if str(action).strip()]
            if actions:
                lines.append("Next moves:")
                for action in actions[:2]:
                    lines.append(f"- {action}")
            return self._lines_to_text(lines)

        summary = daily.get("summary", {}) if isinstance(daily, dict) else {}
        bots = daily.get("bots", []) if isinstance(daily, dict) else []
        trading_alerts = [
            str(alert) for alert in (daily.get("alerts", []) if isinstance(daily, dict) else []) if "website" not in str(alert).lower()
        ]
        lines = [
            "Trading status: attention" if trading_alerts else "Trading status: stable",
            f"PnL: {self._format_money(summary.get('pnl_total'))} | Trades: {summary.get('trades_total')} | Errors: {summary.get('error_lines_total')}",
        ]
        for bot in bots[:2]:
            if isinstance(bot, dict):
                lines.append(
                    f"- {bot.get('name', bot.get('id'))}: status={bot.get('status')} pnl={self._format_money(bot.get('pnl_total'))} errors={bot.get('error_lines_total')}"
                )
        if trading_alerts:
            lines.append(f"Top issue: {trading_alerts[0]}")
        return self._lines_to_text(lines)

    def _summarize_websites_question(self, daily: dict[str, Any] | None, phase2: dict[str, Any] | None) -> str:
        division = self._find_division(phase2, "websites")
        if isinstance(division, dict):
            scorecard = division.get("scorecard", {})
            scorecard = scorecard if isinstance(scorecard, dict) else {}
            lines = [f"Websites status: {str(scorecard.get('status', division.get('status', 'unknown'))).upper()}"]
            top_items = self._top_non_green_items(scorecard=scorecard, limit=2)
            if top_items:
                lines.append("Main issues:")
                for item in top_items:
                    lines.append(
                        f"- {item.get('metric')}: {item.get('actual')} vs {item.get('target')} ({item.get('status')})"
                    )
            actions = [str(action).strip() for action in scorecard.get("actions", []) if str(action).strip()]
            if actions:
                lines.append("Next moves:")
                for action in actions[:2]:
                    lines.append(f"- {action}")
            return self._lines_to_text(lines)

        summary = daily.get("summary", {}) if isinstance(daily, dict) else {}
        websites = daily.get("websites", []) if isinstance(daily, dict) else []
        lines = [
            f"Websites status: {summary.get('websites_up')}/{summary.get('websites_total')} up",
        ]
        for site in websites[:3]:
            if isinstance(site, dict):
                lines.append(
                    f"- {site.get('name', site.get('id'))}: {'UP' if site.get('ok') else 'DOWN'} status={site.get('status_code')} latency={site.get('latency_ms')}ms"
                )
        return self._lines_to_text(lines)

    def _summarize_bot_question(self, bot_id: str, daily: dict[str, Any] | None) -> str:
        bot = self._find_bot_payload(payload=daily, bot_id=bot_id)
        if not isinstance(bot, dict):
            return f"I couldn't find current bot data for {bot_id}. Try /brief for a fresh report."
        report_payload = bot.get("report_payload", {})
        report_payload = report_payload if isinstance(report_payload, dict) else {}
        lines = [
            f"{bot.get('name', bot_id)} status: {str(bot.get('status', 'unknown')).upper()}",
            f"PnL: {self._format_money(bot.get('pnl_total'))} | Trades: {bot.get('trades_total')} | Errors: {bot.get('error_lines_total')}",
        ]
        headline = str(report_payload.get("headline", "")).strip()
        if headline:
            lines.append(f"Latest report: {headline}")
        health = bot.get("health_command", {})
        health = health if isinstance(health, dict) else {}
        if health:
            lines.append(f"Live health: {'OK' if health.get('ok') else 'FAILED'} (rc={health.get('return_code')})")
        return self._lines_to_text(lines)

    def _summarize_site_question(self, site_id: str, daily: dict[str, Any] | None) -> str:
        site = self._find_site_payload(payload=daily, site_id=site_id)
        if not isinstance(site, dict):
            return f"I couldn't find current website data for {site_id}. Try /brief for a fresh report."
        lines = [
            f"{site.get('name', site_id)} status: {'UP' if site.get('ok') else 'DOWN'}",
            f"HTTP status: {site.get('status_code')} | Latency: {site.get('latency_ms')}ms | Probe: {site.get('probe_mode')}",
        ]
        reason = str(site.get("reason", "")).strip()
        if reason:
            lines.append(f"Reason: {reason}")
        return self._lines_to_text(lines)

    def _summarize_company_question(self, daily: dict[str, Any] | None, phase3: dict[str, Any] | None) -> str:
        if isinstance(phase3, dict):
            company = phase3.get("company_scorecard", {})
            company = company if isinstance(company, dict) else {}
            summary = phase3.get("base_summary", {})
            summary = summary if isinstance(summary, dict) else {}
            lines = [
                f"Company status: {company.get('status')}",
                f"PnL: {self._format_money(summary.get('pnl_total'))} | Trades: {summary.get('trades_total')} | Alerts: {len(phase3.get('base_alerts', []) or [])}",
            ]
            top_items = self._top_non_green_items(scorecard=company, limit=2)
            if top_items:
                lines.append("Priority issues:")
                for item in top_items:
                    lines.append(
                        f"- {item.get('metric')}: {item.get('actual')} vs {item.get('target')} ({item.get('status')})"
                    )
            return self._lines_to_text(lines)
        summary = daily.get("summary", {}) if isinstance(daily, dict) else {}
        return self._lines_to_text(
            [
                "Company status: latest daily brief only",
                f"PnL: {self._format_money(summary.get('pnl_total'))} | Trades: {summary.get('trades_total')} | Errors: {summary.get('error_lines_total')}",
            ]
        )

    def _summarize_commercial_question(self, phase2: dict[str, Any] | None, phase3: dict[str, Any] | None) -> str:
        division = self._find_division(phase2, "commercial")
        if isinstance(division, dict):
            scorecard = division.get("scorecard", {})
            scorecard = scorecard if isinstance(scorecard, dict) else {}
            lines = [f"Commercial status: {str(scorecard.get('status', division.get('status', 'unknown'))).upper()}"]
            risks = [str(risk).strip() for risk in scorecard.get("risks", []) if str(risk).strip()]
            actions = [str(action).strip() for action in scorecard.get("actions", []) if str(action).strip()]
            if risks:
                lines.append("Main issues:")
                for risk in risks[:2]:
                    lines.append(f"- {risk}")
            if actions:
                lines.append("Next moves:")
                for action in actions[:2]:
                    lines.append(f"- {action}")
            return self._lines_to_text(lines)

        if isinstance(phase3, dict):
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
                return self._lines_to_text(
                    [
                        f"Commercial status: {commercial_item.get('status')}",
                        f"Current signal: {commercial_item.get('actual')} ({commercial_item.get('variance')})",
                        f"Recommended action: {commercial_item.get('action')}",
                    ]
                )

        return (
            "Commercial status is not wired cleanly into the chat bridge yet.\n"
            "I don't have a dedicated commercial payload to summarize here. Use /board review for the broader company view."
        )

    def _answer_from_memory(self, text: str) -> str:
        facts = self._dedupe_memory_results(self._search_memory(text, top_k=6))
        if not facts:
            return (
                "I don't have enough context to answer that clearly yet.\n"
                "Try /brief for a full report, or ask about trading, websites, MT5 desk, or company status."
            )
        lines = ["Closest relevant context:"]
        for fact in facts[:3]:
            lines.append(f"- {fact.get('text')}")
        return self._lines_to_text(lines)

    def _summarize_divisions_brief(self, payload: dict[str, Any]) -> str:
        base = payload.get("base_summary", {})
        base = base if isinstance(base, dict) else {}
        alerts = payload.get("base_alerts", [])
        alerts = alerts if isinstance(alerts, list) else []
        divisions = payload.get("divisions", [])
        divisions = divisions if isinstance(divisions, list) else []
        files = payload.get("files", {})
        files = files if isinstance(files, dict) else {}

        lines = [
            f"{payload.get('company_name', 'AI Holding Company')} - Division Heartbeat",
            f"Generated (UTC): {payload.get('generated_at_utc')}",
            f"PnL={base.get('pnl_total')} | Trades={base.get('trades_total')} | Errors={base.get('error_lines_total')}",
            f"Websites up={base.get('websites_up')}/{base.get('websites_total')} | Alerts={len(alerts)}",
            "",
            "Division Priorities",
        ]
        owner_actions: list[str] = []
        priority = {"RED": 0, "AMBER": 1, "GREEN": 2}

        for div in divisions:
            if not isinstance(div, dict):
                continue
            name = str(div.get("division", "division")).title()
            scorecard = div.get("scorecard", {})
            scorecard = scorecard if isinstance(scorecard, dict) else {}
            status = str(scorecard.get("status", div.get("status", "unknown"))).upper()
            lines.append(f"- {name}: status={status}")
            if scorecard:
                items = scorecard.get("items", [])
                items = items if isinstance(items, list) else []
                ranked_items = sorted(
                    [item for item in items if isinstance(item, dict)],
                    key=lambda item: priority.get(str(item.get("status", "")).upper(), 3),
                )
                if ranked_items:
                    item = ranked_items[0]
                    lines.append(
                        f"  [{item.get('status')}] {item.get('metric')} -> "
                        f"actual={item.get('actual')} target={item.get('target')}"
                    )
                actions = scorecard.get("actions", [])
                actions = actions if isinstance(actions, list) else []
                if status in {"RED", "AMBER"}:
                    for action in actions[:2]:
                        action_text = str(action).strip()
                        if action_text:
                            owner_actions.append(f"{name}: {action_text}")
            else:
                top_lines = self._extract_lines(str(div.get("final_output", "")), limit=4)
                if top_lines:
                    for line_text in top_lines:
                        normalized = line_text.strip()
                        if normalized.startswith("- ") or normalized.startswith("* "):
                            normalized = normalized[2:].strip()
                        lines.append(f"  - {normalized}")
            warnings = div.get("warnings", [])
            warnings = warnings if isinstance(warnings, list) else []
            for warning in warnings[:1]:
                lines.append(f"  - warning: {warning}")

        if owner_actions:
            lines.append("")
            lines.append("Owner Decisions")
            for action in owner_actions[:5]:
                lines.append(f"- {action}")

        report_path = files.get("latest_markdown")
        if report_path:
            lines.append("")
            lines.append(f"Division report file: {report_path}")
        if alerts:
            lines.append(f"Top alert: {alerts[0]}")
        lines.append("Owner reminder: /divisions all | /status | /bot <id> health")
        return "\n".join(lines).strip()

    def _summarize_holding_brief(self, payload: dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return "Holding heartbeat failed: invalid payload."
        summary = payload.get("base_summary", {})
        summary = summary if isinstance(summary, dict) else {}
        company = payload.get("company_scorecard", {})
        company = company if isinstance(company, dict) else {}
        divisions = payload.get("divisions", [])
        divisions = divisions if isinstance(divisions, list) else []

        lines = [
            f"{payload.get('company_name', 'AI Holding Company')} - CEO Heartbeat",
            f"Mode={payload.get('mode')} | Generated (UTC): {payload.get('generated_at_utc')}",
            f"Company status={company.get('status')} | PnL={summary.get('pnl_total')} | Trades={summary.get('trades_total')}",
            f"Websites up={summary.get('websites_up')}/{summary.get('websites_total')} | Alerts={len(payload.get('base_alerts', []) or [])}",
            "",
            "Company KPI Snapshot",
        ]

        priority = {"RED": 0, "AMBER": 1, "GREEN": 2}
        ranked_company = sorted(
            [item for item in company.get("items", []) if isinstance(item, dict)],
            key=lambda item: priority.get(str(item.get("status", "")).upper(), 3),
        )
        for item in ranked_company[:4]:
            lines.append(
                f"- [{item.get('status')}] {item.get('metric')}: "
                f"actual={item.get('actual')} target={item.get('target')} variance={item.get('variance')}"
            )

        lines.append("")
        lines.append("Division Snapshot")
        for div in divisions:
            if not isinstance(div, dict):
                continue
            scorecard = div.get("scorecard", {})
            scorecard = scorecard if isinstance(scorecard, dict) else {}
            lines.append(f"- {str(div.get('division')).title()}: status={scorecard.get('status')}")
            div_items = sorted(
                [item for item in scorecard.get("items", []) if isinstance(item, dict)],
                key=lambda item: priority.get(str(item.get("status", "")).upper(), 3),
            )
            if div_items:
                top = div_items[0]
                lines.append(
                    f"  [{top.get('status')}] {top.get('metric')} -> actual={top.get('actual')} target={top.get('target')}"
                )

        if payload.get("mode") == "board_review":
            lines.append("")
            lines.append("Board Review Approvals")
            board = payload.get("board_review", {})
            board = board if isinstance(board, dict) else {}
            approvals = board.get("approvals", [])
            approvals = approvals if isinstance(approvals, list) else []
            if not approvals:
                lines.append("- None")
            else:
                for item in approvals[:5]:
                    if not isinstance(item, dict):
                        continue
                    lines.append(
                        f"- [{item.get('priority')}] {item.get('topic')}: {item.get('decision')}"
                    )

        report_path = payload.get("files", {}).get("latest_markdown") if isinstance(payload.get("files"), dict) else None
        if report_path:
            lines.append("")
            lines.append(f"Holding report file: {report_path}")
        lines.append("Owner reminder: /brief | /board review | /divisions all | /status")
        return "\n".join(lines).strip()

    def _format_one_pager_brief(self, payload: dict[str, Any]) -> str:
        """Format the holding brief as a one-pager readable in <60s.

        Structure:
          Header + division traffic lights
          PnL / trade / alert summary
          Top 3 alerts
          Pending decisions (board_review RED items)
          Footer / quick commands
        """
        if not isinstance(payload, dict):
            return "Morning brief failed: invalid payload."

        def _light(status: str) -> str:
            s = str(status).upper()
            if s == "GREEN":
                return "🟢"
            if s == "AMBER":
                return "🟡"
            if s == "RED":
                return "🔴"
            return "⚪"

        summary = payload.get("base_summary", {}) or {}
        divisions = [d for d in (payload.get("divisions") or []) if isinstance(d, dict)]
        alerts = [a for a in (payload.get("base_alerts") or []) if a]
        generated_at = str(payload.get("generated_at_utc") or "")
        ts_display = generated_at[:16].replace("T", " ") if generated_at else "?"

        company_name = str(payload.get("company_name") or "AI Holding Company")

        # Division traffic lights
        div_lines: list[str] = []
        for div in divisions:
            name = str(div.get("division", "?")).title()
            status = str(div.get("status") or "?")
            scorecard = div.get("scorecard", {}) or {}
            items = [i for i in (scorecard.get("items") or []) if isinstance(i, dict)]
            priority = {"RED": 0, "AMBER": 1, "GREEN": 2}
            top_items = sorted(items, key=lambda x: priority.get(str(x.get("status", "")).upper(), 3))
            top_issue = ""
            if top_items and str(top_items[0].get("status", "")).upper() != "GREEN":
                top_item = top_items[0]
                top_issue = f" | {top_item.get('metric', '?')}: {top_item.get('actual', '?')}"
            div_lines.append(f"{_light(status)} {name}{top_issue}")

        divs_block = "\n".join(div_lines) if div_lines else "No division data"

        # Summary row
        pnl = summary.get("pnl_total", "?")
        trades = summary.get("trades_total", "?")
        alert_count = len(alerts)
        summary_row = f"📊 PnL: {pnl} | Trades: {trades} | Alerts: {alert_count}"

        # Top 3 alerts
        alert_lines: list[str] = []
        for i, alert in enumerate(alerts[:3], 1):
            alert_lines.append(f"  {i}. {str(alert)[:100]}")
        alerts_block = ("\n⚡ Top alerts:\n" + "\n".join(alert_lines)) if alert_lines else ""

        # Pending decisions — board_review RED items
        board = payload.get("board_review", {}) or {}
        approvals = [a for a in (board.get("approvals") or []) if isinstance(a, dict)]
        red_approvals = [a for a in approvals if str(a.get("priority", "")).upper() == "RED"]
        decisions_block = ""
        if red_approvals:
            decision_lines = [f"  • {a.get('topic', '?')}" for a in red_approvals[:3]]
            decisions_block = f"\n📋 {len(red_approvals)} pending decision(s):\n" + "\n".join(decision_lines)

        # Reasoning cache stale warning
        from orchestrator import read_reasoning_cache, reasoning_cache_is_stale  # pylint: disable=import-outside-toplevel
        cache = read_reasoning_cache()
        stale_banner = ""
        if reasoning_cache_is_stale(cache) and cache:
            stale_banner = f"\n⚠️ STALE — reasoning from {cache.get('generated_at_utc', 'unknown')}"

        lines = [
            f"🏢 {company_name}",
            "━━━━━━━━━━━━━━━━━━━━",
            divs_block,
            "",
            summary_row,
            alerts_block,
            decisions_block,
            stale_banner,
            f"\n⏱ Generated: {ts_display} UTC",
            "💬 /brief | /board review | /orchestrator status",
        ]
        return "\n".join(ln for ln in lines if ln is not None).strip()

    def _search_memory(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Search vector memory for query. Returns [] on any failure."""
        try:
            memory_cfg = self.config.get("memory", {})
            if not isinstance(memory_cfg, dict) or not memory_cfg.get("enabled", True):
                return []
            memory_dir = ROOT / self.config.get("paths", {}).get("memory_dir", "memory")
            store_path = memory_dir / "vector_store.jsonl"
            if not store_path.exists():
                return []
            from local_vector_memory import LocalVectorMemory  # pylint: disable=import-outside-toplevel

            store = LocalVectorMemory(
                data_path=store_path,
                ollama_base_url=str(memory_cfg.get("ollama_base_url", "http://127.0.0.1:11434")),
                embedding_model=str(memory_cfg.get("embedding_model", "nomic-embed-text")),
            )
            return [r for r in store.search(query=query, top_k=top_k) if r.get("score", 0) > 0.4]
        except Exception:  # noqa: BLE001
            return []

    def _answer_freetext(self, text: str) -> str:
        """Answer a natural language question with concise summaries and directive capture."""
        lowered = text.lower()
        daily = self._load_latest_daily_brief()
        phase2 = self._load_latest_report_json("phase2_divisions_latest.json")
        phase3 = self._load_latest_report_json("phase3_holding_latest.json")

        if self._looks_like_direction(text):
            result = self._run_tool_router(["log_direction", "--text", text, "--source", "telegram_freetext"])
            if result.get("ok"):
                return self._lines_to_text(
                    [
                        "Direction logged.",
                        f"- Directive: {text.strip()}",
                        "- I will treat this as owner guidance for future context and follow-up.",
                    ]
                )
            return "I understood that as a direction, but logging it failed. Try /note <directive>."

        mentioned_bot = self._match_bot_reference(text)
        if mentioned_bot:
            return self._summarize_bot_question(bot_id=mentioned_bot, daily=daily)

        mentioned_site = self._match_website_reference(text)
        if mentioned_site:
            return self._summarize_site_question(site_id=mentioned_site, daily=daily)

        if "/commercial" in lowered or "commercial" == lowered.strip():
            return self._summarize_commercial_question(phase2=phase2, phase3=phase3)
        if any(term in lowered for term in ("trading", "mt5", "polymarket")):
            return self._summarize_trading_question(daily=daily, phase2=phase2)
        if any(term in lowered for term in ("website", "websites", "site", "sites")):
            return self._summarize_websites_question(daily=daily, phase2=phase2)
        if self._looks_like_question(text):
            return self._summarize_company_question(daily=daily, phase3=phase3)

        return self._answer_from_memory(text)

    def handle_text(self, text: str) -> str:
        action = self._parse_action(text)
        if action.get("type") == "help":
            return self._format_help()
        if action.get("type") == "error":
            return str(action.get("message"))
        if action.get("type") == "freetext":
            return self._answer_freetext(action["text"])
        if action.get("type") == "content":
            from content_studio import run_content_studio  # pylint: disable=import-outside-toplevel

            brief_text = str(action.get("brief_text", "")).strip()
            if not brief_text:
                return (
                    "Content Studio - brief-driven content creation\n\n"
                    "Usage: /content <brief text>\n"
                    "Example: /content Write a blog post about MT5 signal accuracy. "
                    "Target audience: traders. Format: article.\n\n"
                    "All drafts require CEO approval before publishing (R3/R4).\n"
                    "Track status with /content_status"
                )

            result = run_content_studio(config=self.config, brief_text=brief_text)
            brief_preview = brief_text[:100]
            if len(brief_text) > 100:
                brief_preview += "..."
            return (
                "Content Studio brief received\n\n"
                f"Brief: {brief_preview}\n"
                f"Status: {result.get('status')}\n"
                f"Drafts pending CEO approval: {result.get('drafts_pending')}\n"
                f"Notes: {result.get('notes')}\n\n"
                "CEO will review draft and provide feedback."
            )
        if action.get("type") == "content_status":
            from content_studio import run_content_studio  # pylint: disable=import-outside-toplevel

            result = run_content_studio(config=self.config)
            return (
                "Content Studio Status\n\n"
                f"Division Status: {result.get('status')}\n"
                f"Drafts pending CEO approval: {result.get('drafts_pending')}\n"
                f"Oldest draft pending: {result.get('last_approval_wait_hours')} hours\n\n"
                f"{result.get('notes')}"
            )
        if action.get("type") == "develop":
            from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

            task = str(action.get("task", "")).strip()
            if not task:
                return (
                    "Developer Tool - AI-assisted internal script development\n\n"
                    "Usage: /develop <task description>\n"
                    "Example: /develop Add KPI tracking for pending approvals\n\n"
                    "Process:\n"
                    "1. You describe the task in plain English\n"
                    "2. qwen2.5-coder generates Python code\n"
                    "3. Scope gate validates ai-holding-company/ only (R8)\n"
                    "4. CEO reviews and approves or denies\n"
                    "5. Approved changes deploy with audit logging\n\n"
                    "Scope: ai-holding-company/ files only (R8)\n"
                    "All code changes require CEO approval (R5)\n"
                    "All actions are logged to artifacts/developer_tool_audit.jsonl"
                )

            result = run_developer_tool(config=self.config, task=task, action="submit")
            if result.get("status") == "PENDING_CEO_APPROVAL":
                approval_id = str(result.get("approval_id", ""))
                code_preview = str(result.get("code_preview", ""))[:700]
                diff = result.get("diff", {})
                diff_file = str(diff.get("file", "scripts/developer_generated.py"))
                diff_summary = str(diff.get("diff_summary", "Diff captured"))
                return (
                    f"Code generated for task: {task[:80]}\n\n"
                    f"Approval ID: `{approval_id}`\n"
                    f"Target file: {diff_file}\n"
                    f"Diff: {diff_summary}\n\n"
                    f"Preview:\n```python\n{code_preview}\n```\n\n"
                    f"To approve: `/develop_approve {approval_id}`\n"
                    f"To deny: `/develop_deny {approval_id}`\n\n"
                    "Scope gate: PASSED (ai-holding-company/ only, R8)"
                )
            details = result.get("message") or result.get("violations") or result.get("status")
            return f"Developer Tool request failed: {result.get('status')}\nDetails: {details}"
        if action.get("type") == "develop_approve":
            from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

            approval_id = str(action.get("approval_id", "")).strip()
            if not approval_id:
                return "Approval ID required. Usage: /develop_approve <approval_id>"
            result = run_developer_tool(config=self.config, approval_id=approval_id, action="approve")
            if result.get("ok"):
                git_commit = str(result.get("git_commit", "")).strip()
                commit_line = f"\nGit commit: {git_commit}" if git_commit else ""
                return (
                    "Code approved and deployed\n\n"
                    f"Approval ID: {approval_id}\n"
                    f"File: {result.get('file')}\n"
                    f"Status: {result.get('status')}\n"
                    f"Timestamp: {result.get('timestamp')}"
                    f"{commit_line}\n\n"
                    "R5 gate satisfied: CEO approval recorded."
                )
            details = result.get("message") or result.get("violations") or result.get("error")
            return f"Deployment failed: {result.get('status')}\nDetails: {details}"
        if action.get("type") == "develop_deny":
            from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

            approval_id = str(action.get("approval_id", "")).strip()
            if not approval_id:
                return "Approval ID required. Usage: /develop_deny <approval_id>"
            result = run_developer_tool(config=self.config, approval_id=approval_id, action="deny")
            if result.get("ok"):
                return f"Code submission denied and discarded (ID: {approval_id})"
            return f"Denial failed: {result.get('status')}"
        if action.get("type") == "develop_status":
            from developer_tool import run_developer_tool  # pylint: disable=import-outside-toplevel

            result = run_developer_tool(config=self.config, action="status")
            pending_count = int(result.get("pending_count", 0))
            if pending_count == 0:
                return "No pending code approvals."
            lines = []
            for item in result.get("pending", []):
                if not isinstance(item, dict):
                    continue
                approval_id = str(item.get("approval_id", ""))
                task = str(item.get("task", ""))[:60]
                stamp = str(item.get("timestamp", ""))[:10]
                lines.append(f"- {approval_id}: {task}... ({stamp})")
            pending_list = "\n".join(lines)
            return (
                f"Developer Tool Pending Approvals ({pending_count})\n\n"
                f"{pending_list}\n\n"
                "To approve: /develop_approve <approval_id>\n"
                "To deny: /develop_deny <approval_id>"
            )
        if action.get("type") == "orchestrator":
            from orchestrator import (  # pylint: disable=import-outside-toplevel
                get_orchestrator_status,
                read_pid,
                read_reasoning_cache,
                reasoning_cache_is_stale,
                STOP_FLAG,
            )

            subcmd = str(action.get("subcmd", "status")).lower()

            if subcmd == "status":
                status = get_orchestrator_status()
                pid = read_pid()
                cache = read_reasoning_cache()
                stale = reasoning_cache_is_stale(cache)
                stale_banner = ""
                if stale and cache:
                    stale_banner = f"\n⚠️ STALE — reasoning from {cache.get('generated_at_utc', 'unknown')}"
                return (
                    f"Orchestrator: {status}\n"
                    f"PID: {pid or 'none'}"
                    f"{stale_banner}"
                )

            if subcmd == "stop":
                STOP_FLAG.touch()
                return "Orchestrator stop signal sent. Will halt on next tick (~5 min)."

            if subcmd == "start":
                status = get_orchestrator_status()
                if status == "RUNNING":
                    return "Orchestrator is already RUNNING."
                return (
                    "To start the orchestrator, run on the host machine:\n"
                    "  python scripts/orchestrator.py\n"
                    "Or via Windows Task Scheduler. Remote start is not supported (security)."
                )

            return f"Unknown orchestrator subcommand: {subcmd!r}"

        tool_name = str(action.get("name"))
        args = action.get("args", [])
        result = self._run_tool_router(args)
        return self._summarize_tool_result(tool_name, result)

    def send_morning_brief(self) -> None:
        if self.owner_chat_id is None:
            raise RuntimeError("TELEGRAM_OWNER_CHAT_ID is not set.")
        if self.phase3_enabled:
            result = self._run_tool_router(["run_holding", "--mode", "heartbeat", "--force"], timeout_sec=1500)
        else:
            result = self._run_tool_router(["run_divisions", "--division", "all", "--force"], timeout_sec=1200)
        ok = bool(result.get("ok"))
        text = ""
        payload = result.get("payload")
        if ok and isinstance(payload, dict):
            if self.phase3_enabled:
                text = self._format_one_pager_brief(payload)
                # Update pinned health lights on every morning brief run
                divisions = [d for d in (payload.get("divisions") or []) if isinstance(d, dict)]
                self.update_pinned_health(
                    divisions=divisions,
                    generated_at_utc=str(payload.get("generated_at_utc") or ""),
                )
            else:
                text = self._summarize_divisions_brief(payload)
        else:
            fallback = self._run_tool_router(["daily_brief"])
            text = self._summarize_tool_result("daily_brief", fallback)
            ok = bool(fallback.get("ok"))

        self.send_message(self.owner_chat_id, text)
        self._audit(
            {
                "mode": "send_morning_brief",
                "ok": ok,
                "chat_id": self.owner_chat_id,
                "used": (
                    "run_holding_heartbeat_force"
                    if self.phase3_enabled and result.get("ok")
                    else "run_divisions_all_force"
                    if result.get("ok")
                    else "daily_brief_fallback"
                ),
            }
        )

    def run_once(self) -> int:
        updates = self.get_updates()
        max_update_id = int(self.state.get("last_update_id", 0))
        processed = 0

        for update in updates:
            update_id = int(update.get("update_id", 0))
            if update_id > max_update_id:
                max_update_id = update_id

            message = update.get("message") or {}
            text = str(message.get("text") or "").strip()
            chat = message.get("chat") or {}
            from_user = message.get("from") or {}
            chat_id = chat.get("id")
            user_id = from_user.get("id")

            if chat_id is None or not text:
                continue

            chat_id_int = int(chat_id)
            user_id_int = int(user_id) if user_id is not None else None

            if not self._authorized(chat_id=chat_id_int, user_id=user_id_int):
                self._audit(
                    {
                        "mode": "message",
                        "authorized": False,
                        "chat_id": chat_id_int,
                        "user_id": user_id_int,
                        "text": text[:200],
                    }
                )
                continue

            try:
                response_text = self.handle_text(text)
                self.send_message(chat_id_int, response_text)
                self._audit(
                    {
                        "mode": "message",
                        "authorized": True,
                        "chat_id": chat_id_int,
                        "user_id": user_id_int,
                        "text": text[:200],
                        "ok": True,
                    }
                )
            except Exception as exc:  # pylint: disable=broad-except
                err_text = f"Bridge error: {exc}"
                self.send_message(chat_id_int, err_text)
                self._audit(
                    {
                        "mode": "message",
                        "authorized": True,
                        "chat_id": chat_id_int,
                        "user_id": user_id_int,
                        "text": text[:200],
                        "ok": False,
                        "error": str(exc),
                    }
                )
            processed += 1

        self.state["last_update_id"] = max_update_id
        _state_write(self.state_file, self.state)
        return processed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Telegram bridge for AI Holding Company.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to projects.yaml.")
    parser.add_argument("--once", action="store_true", help="Poll once and exit.")
    parser.add_argument("--send-morning-brief", action="store_true", help="Generate and push morning brief to owner.")
    parser.add_argument("--simulate-text", default="", help="Run parser+tool flow locally without Telegram API.")
    parser.add_argument("--discover-ids", action="store_true", help="Print chat_id/user_id values from recent updates.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bridge = TelegramBridge(config_path=Path(args.config))

    if not bridge.security_ready:
        raise RuntimeError(
            "Bridge startup blocked: configure TELEGRAM_OWNER_CHAT_ID and/or TELEGRAM_OWNER_USER_ID "
            "or set bridge.telegram.allowed_chat_ids/allowed_user_ids in config."
        )

    if args.simulate_text:
        print(bridge.handle_text(args.simulate_text))
        return

    if args.discover_ids:
        ids = bridge.discover_ids()
        print(json.dumps({"ok": True, "count": len(ids), "ids": ids}, indent=2))
        return

    if args.send_morning_brief:
        bridge.send_morning_brief()
        print(json.dumps({"ok": True, "mode": "send_morning_brief"}))
        return

    if args.once:
        count = bridge.run_once()
        print(json.dumps({"ok": True, "mode": "once", "processed": count}))
        return

    while True:
        try:
            bridge.run_once()
        except Exception as exc:  # pylint: disable=broad-except
            _append_jsonl(
                bridge.audit_file,
                {"at_utc": _utc_now(), "mode": "loop_error", "ok": False, "error": str(exc)},
            )
            time.sleep(max(bridge.poll_interval_sec, 2))
            continue
        time.sleep(max(bridge.poll_interval_sec, 1))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

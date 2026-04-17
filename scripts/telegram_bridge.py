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
        if self.allowed_user_ids and user_id is not None and user_id not in self.allowed_user_ids:
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
        if lowered in {"/status", "status"}:
            return {"type": "tool", "name": "daily_brief", "args": ["daily_brief"]}
        if lowered in {"/brief", "brief"} or any(p in lowered for p in ("generate fresh brief", "give me a brief", "send a brief", "run brief", "morning brief")):
            if self.phase3_enabled:
                return {"type": "tool", "name": "run_holding", "args": ["run_holding", "--mode", "heartbeat", "--force"]}
            return {"type": "tool", "name": "run_divisions", "args": ["run_divisions", "--division", "all", "--force"]}

        if re.match(r"^/content_status$", raw, re.I):
            return {"type": "content_status"}

        content_match = re.match(r"^/content(?:\s+(.+))?$", raw, re.I)
        if content_match:
            brief_text = (content_match.group(1) or "").strip()
            return {"type": "content", "brief_text": brief_text}

        if re.match(r"^/board(?:\s+review)?$", raw, re.I):
            return {"type": "tool", "name": "run_holding", "args": ["run_holding", "--mode", "board_review", "--force"]}

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
        """Answer a natural language question using memory search + live health if a bot is named."""
        lowered = text.lower()

        mentioned_bot = next((bid for bid in self.bot_ids if bid.lower() in lowered), None)
        mentioned_site = next((sid for sid in self.website_ids if sid.lower() in lowered), None)

        facts = self._search_memory(text, top_k=3)

        lines: list[str] = []
        if facts:
            lines.append("[context]")
            for f in facts:
                lines.append(f"- {f['text']}")

        if mentioned_bot:
            result = self._run_tool_router(
                ["run_trading_script", "--bot", mentioned_bot, "--command-key", "health"],
                timeout_sec=60,
            )
            summary = self._summarize_tool_result("run_trading_script", result)
            lines.append(f"\n[live: {mentioned_bot}]\n{summary}")
        elif mentioned_site:
            result = self._run_tool_router(
                ["check_website", "--website", mentioned_site],
                timeout_sec=30,
            )
            summary = self._summarize_tool_result("check_website", result)
            lines.append(f"\n[live: {mentioned_site}]\n{summary}")

        if not lines:
            return (
                "I don't have enough context to answer that yet.\n"
                "Try /brief for a full report, or /help for all commands."
            )

        return "\n".join(lines)

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
            text = self._summarize_holding_brief(payload) if self.phase3_enabled else self._summarize_divisions_brief(payload)
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

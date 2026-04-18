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
        if lowered == "/status":
            return {"type": "tool", "name": "daily_brief", "args": ["daily_brief"]}
        # Plain-text "status", "CEO", "daily_brief", "commercial" → synthesised freetext answer
        if lowered in {"status", "ceo", "daily_brief", "commercial", "/commercial"}:
            return {"type": "freetext", "text": raw}
        if lowered in {"/brief", "brief"} or any(p in lowered for p in ("generate fresh brief", "give me a brief", "send a brief", "run brief", "morning brief")):
            if self.phase3_enabled:
                return {"type": "tool", "name": "run_holding", "args": ["run_holding", "--mode", "heartbeat", "--force"]}
            return {"type": "tool", "name": "run_divisions", "args": ["run_divisions", "--division", "all", "--force"]}

        if re.match(r"^/board\s+pack$", raw, re.I):
            return {"type": "tool", "name": "run_holding_board_pack", "args": ["run_holding_board_pack", "--force"]}

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

    @staticmethod
    def _status_emoji(status: str) -> str:
        return {"RED": "🔴", "AMBER": "🟡", "GREEN": "🟢"}.get(str(status).upper(), "⬜")

    def _format_help(self) -> str:
        bots = ", ".join(sorted(self.bot_ids)) or "<none configured>"
        sites = ", ".join(sorted(self.website_ids)) or "<none configured>"
        observer = "ON  (execute blocked)" if self.observer_mode else "OFF"
        return (
            "MANGANDA LTD  ·  CEO Commands\n"
            "──────────────────────────────\n"
            "DAILY OPERATIONS\n"
            "  /status          Quick pulse (cached, instant)\n"
            "  /brief           CEO heartbeat — full scorecard\n"
            "  /divisions all   Division operational review\n"
            "\n"
            "APPROVALS\n"
            "  /board review    Approval matrix (formal)\n"
            "  /board pack      Full 8-field board pack\n"
            "\n"
            "TRADING BOTS\n"
            f"  Bots: {bots}\n"
            "  /bot <id> health     Connectivity check\n"
            "  /bot <id> report     Session P&L report\n"
            "  /bot <id> logs 50    Last 50 log lines\n"
            "\n"
            "WEBSITES\n"
            f"  Sites: {sites}\n"
            "  /site <id>       Live ping\n"
            "\n"
            "MEMORY\n"
            "  /note <text>    Save a directive\n"
            "  /memory <q>     Search past context\n"
            "\n"
            "──────────────────────────────\n"
            f"Observer mode: {observer}\n"
            "→ Start with /brief"
        )

    def _summarize_tool_result(self, tool_name: str, result: dict[str, Any]) -> str:
        if not result.get("ok"):
            err = (result.get("stderr") or "").strip()
            # Strip Python stack trace — internal details must not reach CEO
            if "Traceback" in err:
                clean = [
                    line.strip() for line in err.split("\n")
                    if line.strip()
                    and not any(x in line for x in ("Traceback", "  File ", "    "))
                    and not re.match(r"^[A-Za-z]+(?:Error|Exception):", line.strip())
                ]
                err = " ".join(clean) if clean else "Internal error — check server logs"
            return (
                f"⚠ Command failed: {tool_name}\n"
                f"Reason: {err[:300] if err else 'Unexpected error — check server logs'}\n"
                "→ /status for last cached state"
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
            alert_count = len(alerts)
            if alert_count == 0:
                overall = "🟢 ALL CLEAR"
            elif alert_count <= 2:
                overall = "🟡 AMBER"
            else:
                overall = "🔴 RED"
            now_str = _utc_now()[:16].replace("T", "  ")
            lines = [
                "─────────────────────────────",
                "MANGANDA LTD  ·  Daily Pulse",
                f"{now_str} UTC",
                "─────────────────────────────",
                f"{overall}  —  {alert_count} alert{'s' if alert_count != 1 else ''}",
                "",
                "TRADING",
            ]
            pnl = summary.get("pnl_total")
            trades = summary.get("trades_total")
            errors = summary.get("error_lines_total")
            if pnl is not None:
                sign = "+" if float(pnl) >= 0 else ""
                lines.append(f"  PnL today    {sign}{pnl}")
            if trades is not None:
                lines.append(f"  Trades       {trades}    (target ≥40)")
            if errors is not None:
                err_flag = "✓" if int(errors) <= 3 else "⚠"
                lines.append(f"  Errors       {errors}    (threshold ≤3 {err_flag})")
            for bot in bots[:2]:
                icon = "🟢" if str(bot.get("status", "")).upper() == "RUNNING" else "🟡"
                lines.append(f"  {icon} {bot.get('id')}    pnl={bot.get('pnl_total')}")
            if websites:
                lines.append("")
                lines.append("INFRASTRUCTURE")
                up = summary.get("websites_up", 0)
                total = summary.get("websites_total", len(websites))
                lines.append(f"  Websites     {up} / {total} UP")
                for site in websites[:4]:
                    icon = "🟢" if site.get("ok") else "🔴"
                    lines.append(f"  {icon} {site.get('id')}    {site.get('latency_ms')}ms")
            if alerts:
                lines.append("")
                lines.append(f"ALERTS  ({len(alerts)})")
                for alert in alerts[:3]:
                    lines.append(f"  ⚠ {alert}")
            lines.append("")
            lines.append("→ /brief for full CEO scorecard")
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
            bot_id = payload.get("bot_id", "?")
            cmd_key = str(payload.get("command_key", "?"))
            rc = payload.get("return_code", -1)
            elapsed = int(payload.get("elapsed_ms") or 0)
            ok_flag = bool(payload.get("ok", rc == 0))
            icon = "🟢" if ok_flag else "🔴"
            status = "OK" if ok_flag else "FAILED"
            elapsed_s = f"{elapsed // 1000}.{(elapsed % 1000) // 100}s" if elapsed else "—"
            headline = None
            stdout_text = str(payload.get("stdout", "")).strip()
            if stdout_text.startswith("{"):
                try:
                    headline = json.loads(stdout_text).get("headline")
                except json.JSONDecodeError:
                    pass
            name = bot_id.replace("_", " ").upper()
            lines = [
                f"{name}  ·  {cmd_key.title()}",
                f"{icon} {status}  ·  {elapsed_s}",
            ]
            if headline:
                lines.append(headline)
            lines.append(f"→ /bot {bot_id} report for full detail")
            return "\n".join(lines)

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

        company = payload.get("company_name", "Manganda LTD")
        now_str = str(payload.get("generated_at_utc", _utc_now()))[:16].replace("T", "  ")
        pnl = base.get("pnl_total", "—")
        trades = base.get("trades_total", "—")
        sites_up = base.get("websites_up", "—")
        sites_total = base.get("websites_total", "—")
        sign = "+" if isinstance(pnl, (int, float)) and float(pnl) >= 0 else ""
        lines = [
            f"{company}  ·  Divisions",
            f"{now_str} UTC",
            f"PnL {sign}{pnl}  ·  Trades {trades}  ·  Sites {sites_up}/{sites_total} UP",
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
            lines.append("")
            lines.append(f"{name.upper()}  {self._status_emoji(status)} {status}")
            if scorecard:
                items = scorecard.get("items", [])
                items = items if isinstance(items, list) else []
                ranked_items = sorted(
                    [item for item in items if isinstance(item, dict)],
                    key=lambda item: priority.get(str(item.get("status", "")).upper(), 3),
                )
                for item in ranked_items[:2]:
                    emoji = self._status_emoji(item.get("status", ""))
                    lines.append(
                        f"  {emoji} {item.get('metric')}   "
                        f"{item.get('actual')}  vs  {item.get('target')}"
                    )
                actions = scorecard.get("actions", [])
                actions = actions if isinstance(actions, list) else []
                if status in {"RED", "AMBER"} and actions:
                    owner_actions.append(f"{name}: {str(actions[0]).strip()}")
                    lines.append(f"  Action: {str(actions[0]).strip()}")
                elif status == "GREEN":
                    lines.append("  No action required")
            else:
                top_lines = self._extract_lines(str(div.get("final_output", "")), limit=4)
                for line_text in top_lines:
                    normalized = line_text.strip().lstrip("- *").strip()
                    if normalized:
                        lines.append(f"  {normalized}")
            warnings = div.get("warnings", [])
            warnings = warnings if isinstance(warnings, list) else []
            for warning in warnings[:1]:
                lines.append(f"  ⚠ {warning}")

        if alerts:
            lines.append("")
            lines.append(f"⚠ Alert: {alerts[0]}")

        lines.append("")
        lines.append("→ /brief for CEO scorecard  ·  /bot <id> health")
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
        base_alerts = payload.get("base_alerts", []) or []
        mode = str(payload.get("mode", "heartbeat"))
        company_name = str(payload.get("company_name", "Manganda LTD"))
        now_str = str(payload.get("generated_at_utc", _utc_now()))[:16].replace("T", "  ")

        # — Exec summary line
        company_status = str(company.get("status", "UNKNOWN")).upper()
        priority_order = {"RED": 0, "AMBER": 1, "GREEN": 2}
        all_items = [i for i in company.get("items", []) if isinstance(i, dict)]
        count_red = sum(1 for i in all_items if str(i.get("status", "")).upper() == "RED")
        count_amber = sum(1 for i in all_items if str(i.get("status", "")).upper() == "AMBER")
        count_green = sum(1 for i in all_items if str(i.get("status", "")).upper() == "GREEN")
        summary_line = (
            f"{self._status_emoji(company_status)} {company_status}"
            + (f"  —  {count_red} RED" if count_red else "")
            + (f"  ·  {count_amber} AMBER" if count_amber else "")
            + (f"  ·  {count_green} GREEN" if count_green else "")
        )

        lines = [
            "══════════════════════════════",
            f"{company_name}  ·  CEO Heartbeat",
            f"{now_str} UTC  ·  {mode}",
            "══════════════════════════════",
            summary_line,
            "",
            "COMPANY KPIs",
        ]

        ranked_company = sorted(all_items, key=lambda i: priority_order.get(str(i.get("status", "")).upper(), 3))
        for item in ranked_company[:5]:
            emoji = self._status_emoji(item.get("status", ""))
            action_flag = "  → REVIEW" if str(item.get("status", "")).upper() == "RED" else (
                "  → WATCH" if str(item.get("status", "")).upper() == "AMBER" else ""
            )
            lines.append(
                f"{emoji} {item.get('metric')}   "
                f"{item.get('actual')}  vs  {item.get('target')}  ({item.get('variance')}){action_flag}"
            )

        lines.append("")
        lines.append("DIVISIONS")
        for div in divisions:
            if not isinstance(div, dict):
                continue
            scorecard = div.get("scorecard", {})
            scorecard = scorecard if isinstance(scorecard, dict) else {}
            div_status = str(scorecard.get("status", "UNKNOWN")).upper()
            div_name = str(div.get("division", "division")).title()
            lines.append(f"{div_name}    {self._status_emoji(div_status)} {div_status}")
            div_items = sorted(
                [i for i in scorecard.get("items", []) if isinstance(i, dict)],
                key=lambda i: priority_order.get(str(i.get("status", "")).upper(), 3),
            )
            if div_items:
                top = div_items[0]
                lines.append(
                    f"  {self._status_emoji(top.get('status', ''))} {top.get('metric')}   "
                    f"{top.get('actual')}  vs  {top.get('target')}"
                )

        # — Decisions block (RED/AMBER items with actions)
        decisions = [
            (item, div)
            for div in divisions if isinstance(div, dict)
            for item in (div.get("scorecard", {}) or {}).get("items", []) if isinstance(item, dict)
            if str(item.get("status", "")).upper() in ("RED", "AMBER")
        ]
        company_decisions = [
            item for item in ranked_company
            if str(item.get("status", "")).upper() in ("RED", "AMBER") and item.get("action")
        ]
        if company_decisions:
            lines.append("")
            lines.append(f"DECISIONS REQUIRED  ({count_red} RED · {count_amber} AMBER)")
            for n, item in enumerate(company_decisions[:4], 1):
                deadline = "today" if str(item.get("status", "")).upper() == "RED" else "+7 days"
                lines.append(
                    f"{n}. {self._status_emoji(item.get('status', ''))} {item.get('metric')}: "
                    f"{item.get('action', '').rstrip('.')}"
                )
                lines.append(f"   Owner: Trading  ·  Deadline: {deadline}")

        if mode in ("board_review", "board_pack"):
            lines.append("")
            mode_label = "Board Pack" if mode == "board_pack" else "Board Review"
            board = payload.get("board_review", {})
            board = board if isinstance(board, dict) else {}

            if board.get("gate_blocked"):
                lines.append("🔴 GATE BLOCKED — CEO review cannot proceed")
                incomplete = [
                    f"  • {item.get('topic', '?')}: missing {', '.join(item.get('validation_warnings', []))}"
                    for item in board.get("approvals", [])
                    if isinstance(item, dict) and item.get("validation_warnings")
                ]
                lines.extend(incomplete)
                lines.append("")
                lines.append("→ /brief to force a fresh scorecard run")
            else:
                lines.append(f"{mode_label} Approvals")
                approvals = board.get("approvals", [])
                approvals = approvals if isinstance(approvals, list) else []
                if not approvals:
                    lines.append("  None required")
                else:
                    for n, item in enumerate(approvals[:5], 1):
                        if not isinstance(item, dict):
                            continue
                        pri = str(item.get("priority", "")).upper()
                        deadline = item.get("deadline", "—")
                        owner = str(item.get("owner", "—")).title()
                        dissent = str(item.get("dissent", "")).strip()
                        dissent_label = "PENDING review" if dissent.startswith("PENDING") else dissent[:60]
                        measure = str(item.get("measurement_plan", "")).strip()
                        lines.append(f"\n{n}. {self._status_emoji(pri)} {item.get('topic')}")
                        lines.append(f"   Owner: {owner}  ·  Deadline: {deadline}")
                        lines.append(f"   Dissent: {dissent_label}")
                        if measure:
                            lines.append(f"   Measure: {measure}")
                lines.append("")
                lines.append("Approve, defer, or reject each item explicitly.")

        report_path = payload.get("files", {}).get("latest_markdown") if isinstance(payload.get("files"), dict) else None
        if report_path:
            lines.append("")
            lines.append(f"Report: {report_path}")

        if mode in ("board_review", "board_pack"):
            lines.append("→ /brief to re-run scorecard after changes")
        else:
            lines.append("→ /board review to formalise approvals")
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

    # ------------------------------------------------------------------ #
    #  Freetext helpers                                                   #
    # ------------------------------------------------------------------ #

    def _load_latest_report(self, name: str) -> dict[str, Any] | None:
        """Load reports/{name}_latest.json; return None on any failure."""
        path = self.reports_dir / f"{name}_latest.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    def _resolve_entity_id(self, lowered: str, id_set: set[str]) -> str | None:
        """Fuzzy-match a natural mention to a configured bot/site ID.

        Handles: exact substring, underscore→space, hyphen→space, and
        all-significant-words-present matching (e.g. "mt5 desk" → "mt5_desk").
        """
        for entity_id in id_set:
            if entity_id.lower() in lowered:
                return entity_id
            friendly = entity_id.lower().replace("_", " ").replace("-", " ")
            if friendly in lowered:
                return entity_id
            words = [w for w in friendly.split() if len(w) > 2]
            if words and all(w in lowered for w in words):
                return entity_id
        return None

    @staticmethod
    def _dedupe_memory(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for f in facts:
            key = str(f.get("text", "")).strip()[:80].lower()
            if key and key not in seen:
                seen.add(key)
                out.append(f)
        return out

    @staticmethod
    def _is_question(lowered: str) -> bool:
        starters = (
            "what", "how", "why", "when", "where", "which", "who",
            "is ", "are ", "can ", "could ", "do ", "does ", "did ",
            "has ", "have ", "will ", "would ", "should ",
        )
        return lowered.endswith("?") or any(lowered.startswith(s) for s in starters)

    def _detect_intent(self, lowered: str) -> str | None:
        """Return a coarse intent tag for a freetext message."""
        # Commercial — no live data yet (match anywhere in the sentence)
        if re.search(r"\bcommercial\b", lowered):
            return "commercial"

        # Direction (imperative, not a question)
        direction_patterns = [
            r"\b(focus|prioritise|prioritize|ignore|skip|defer|stop|start|pause|switch)\b",
            r"\b(for now|going forward|from now on|until further notice)\b",
            r"\b(make sure|ensure|remember to|note that|don't|do not)\b",
        ]
        if not self._is_question(lowered) and any(re.search(p, lowered) for p in direction_patterns):
            return "direction"

        # Bot-specific
        bot_id = self._resolve_entity_id(lowered, self.bot_ids)
        if bot_id:
            return f"bot:{bot_id}"

        # Site-specific
        site_id = self._resolve_entity_id(lowered, self.website_ids)
        if site_id:
            return f"site:{site_id}"

        # Trading
        if any(w in lowered for w in ("trading", "trades", "pnl", "p&l", "profit", "loss", "drawdown", "position", "strategy", "mt5")):
            return "trading"

        # Websites
        if any(w in lowered for w in ("website", "uptime", "latency", "site")):
            return "websites"

        # Company / CEO / status
        if any(w in lowered for w in ("company", "overall", "ceo", "holding", "status", "daily_brief", "how are we", "how is the", "everything")):
            return "company"

        return None

    def _format_bot_summary(self, bot_id: str, result: dict[str, Any]) -> str:
        name = bot_id.replace("_", " ").title()
        payload = result.get("payload") or {}
        ok = result.get("ok", False)
        icon = "🟢" if ok else "🔴"
        status = "CONNECTED" if ok else "ATTENTION"
        lines = [f"{name} status: {status}"]
        pnl = payload.get("pnl_total") or payload.get("pnl")
        trades = payload.get("trades_total") or payload.get("trades")
        errors = payload.get("error_lines") or payload.get("errors")
        metrics = []
        if pnl is not None:
            metrics.append(f"PnL: {pnl}")
        if trades is not None:
            metrics.append(f"Trades: {trades}")
        if errors is not None:
            metrics.append(f"Errors: {errors}")
        if metrics:
            lines.append(" | ".join(metrics))
        stdout_text = str(payload.get("stdout", "")).strip()
        if stdout_text.startswith("{"):
            try:
                headline = json.loads(stdout_text).get("headline")
                if headline:
                    lines.append(f"Latest report: {headline}")
            except json.JSONDecodeError:
                pass
        lines.append(f"Live health: {icon} rc={result.get('return_code', '—')}")
        lines.append(f"→ /bot {bot_id} report for full detail")
        return "\n".join(lines)

    def _format_site_summary(self, site_id: str, result: dict[str, Any]) -> str:
        payload = result.get("payload") or {}
        name = site_id.replace("_", " ").replace("-", " ").title()
        ok = payload.get("ok", result.get("ok", False))
        icon = "🟢" if ok else "🔴"
        lines = [f"{name}: {icon} {'UP' if ok else 'DOWN'}"]
        details = []
        if payload.get("status_code"):
            details.append(f"HTTP {payload['status_code']}")
        if payload.get("latency_ms") is not None:
            details.append(f"{payload['latency_ms']}ms")
        if payload.get("probe_mode"):
            details.append(f"mode={payload['probe_mode']}")
        if details:
            lines.append(" | ".join(details))
        if not ok and payload.get("reason"):
            lines.append(f"Reason: {payload['reason']}")
        return "\n".join(lines)

    def _format_trading_summary(self, report: dict[str, Any]) -> str:
        divisions = report.get("divisions", []) or []
        trading_div = next(
            (d for d in divisions if isinstance(d, dict) and str(d.get("division", "")).lower() == "trading"),
            None,
        )
        if not trading_div:
            return "Trading status: no data available.\n→ /divisions all to run a fresh report."
        scorecard = trading_div.get("scorecard", {}) or {}
        status = str(scorecard.get("status", "UNKNOWN")).upper()
        lines = [f"Trading status: {self._status_emoji(status)} {status}"]
        priority_order = {"RED": 0, "AMBER": 1, "GREEN": 2}
        items = [i for i in scorecard.get("items", []) if isinstance(i, dict)]
        ranked = sorted(items, key=lambda i: priority_order.get(str(i.get("status", "")).upper(), 3))
        non_green = [i for i in ranked if str(i.get("status", "")).upper() in ("RED", "AMBER")]
        if non_green:
            lines.append("Main issues:")
            for item in non_green[:3]:
                lines.append(f"  - {item.get('metric')}: {item.get('actual')} vs {item.get('target')}")
        actions = scorecard.get("actions", []) or []
        if actions:
            lines.append("Next moves:")
            for action in actions[:3]:
                lines.append(f"  - {str(action).strip()}")
        return "\n".join(lines)

    def _format_websites_summary(self, report: dict[str, Any]) -> str:
        divisions = report.get("divisions", []) or []
        websites_div = next(
            (d for d in divisions if isinstance(d, dict) and str(d.get("division", "")).lower() == "websites"),
            None,
        )
        if not websites_div:
            return "Website status: no data available.\n→ /divisions all to run a fresh report."
        scorecard = websites_div.get("scorecard", {}) or {}
        status = str(scorecard.get("status", "UNKNOWN")).upper()
        lines = [f"Website status: {self._status_emoji(status)} {status}"]
        priority_order = {"RED": 0, "AMBER": 1, "GREEN": 2}
        items = [i for i in scorecard.get("items", []) if isinstance(i, dict)]
        ranked = sorted(items, key=lambda i: priority_order.get(str(i.get("status", "")).upper(), 3))
        non_green = [i for i in ranked if str(i.get("status", "")).upper() in ("RED", "AMBER")]
        if non_green:
            lines.append("Main issues:")
            for item in non_green[:3]:
                lines.append(f"  - {item.get('metric')}: {item.get('actual')} vs {item.get('target')}")
        actions = scorecard.get("actions", []) or []
        if actions:
            lines.append("Next moves:")
            for action in actions[:3]:
                lines.append(f"  - {str(action).strip()}")
        if not non_green and not actions:
            lines.append("All metrics on target.")
        return "\n".join(lines)

    def _format_company_summary(self, report: dict[str, Any]) -> str:
        company = report.get("company_scorecard", {}) or {}
        summary = report.get("base_summary", {}) or {}
        alerts = report.get("base_alerts", []) or []
        status = str(company.get("status", "UNKNOWN")).upper()
        pnl = summary.get("pnl_total", "—")
        trades = summary.get("trades_total", "—")
        sign = "+" if isinstance(pnl, (int, float)) and float(pnl) >= 0 else ""
        lines = [
            f"Company status: {self._status_emoji(status)} {status}",
            f"PnL: {sign}{pnl} | Trades: {trades} | Alerts: {len(alerts)}",
        ]
        priority_order = {"RED": 0, "AMBER": 1, "GREEN": 2}
        items = [i for i in company.get("items", []) if isinstance(i, dict)]
        ranked = sorted(items, key=lambda i: priority_order.get(str(i.get("status", "")).upper(), 3))
        non_green = [i for i in ranked if str(i.get("status", "")).upper() in ("RED", "AMBER")]
        if non_green:
            lines.append("Priority issues:")
            for item in non_green[:4]:
                emoji = self._status_emoji(item.get("status", ""))
                lines.append(f"  - {emoji} {item.get('metric')}: {item.get('actual')} vs {item.get('target')}")
        lines.append("→ /brief for full CEO scorecard")
        return "\n".join(lines)

    def _answer_freetext(self, text: str) -> str:
        """Synthesise a structured answer — memory is background context only, never raw output."""
        lowered = text.lower().strip()
        intent = self._detect_intent(lowered)

        # 1. Direction → log and confirm
        if intent == "direction":
            self._run_tool_router(
                ["log_direction", "--text", text.strip(), "--source", "telegram_owner"],
                timeout_sec=10,
            )
            return f'Direction logged.\n"{text.strip()}"'

        # 2. Commercial → clear fallback, no memory dump
        if intent == "commercial":
            return (
                "Commercial status is not wired cleanly into the chat bridge yet.\n"
                "Try /brief for the full company scorecard."
            )

        # 3. Bot-specific
        if intent and intent.startswith("bot:"):
            bot_id = intent[4:]
            result = self._run_tool_router(
                ["run_trading_script", "--bot", bot_id, "--command-key", "health"],
                timeout_sec=60,
            )
            return self._format_bot_summary(bot_id, result)

        # 4. Site-specific
        if intent and intent.startswith("site:"):
            site_id = intent[5:]
            result = self._run_tool_router(
                ["check_website", "--website", site_id],
                timeout_sec=30,
            )
            return self._format_site_summary(site_id, result)

        # 5. Trading question → prefer Phase 2 cached report
        if intent == "trading":
            report = self._load_latest_report("phase2_divisions")
            if report:
                return self._format_trading_summary(report)

        # 6. Websites question → prefer Phase 2 cached report
        if intent == "websites":
            report = self._load_latest_report("phase2_divisions")
            if report:
                return self._format_websites_summary(report)

        # 7. Company / CEO / status → prefer Phase 3, fallback Phase 2
        if intent == "company":
            report = self._load_latest_report("phase3_holding")
            if report:
                return self._format_company_summary(report)
            report = self._load_latest_report("phase2_divisions")
            if report:
                return self._format_trading_summary(report)

        # 8. Fallback: memory search — skip for noise/greeting inputs
        words = [w for w in re.split(r"\W+", lowered) if len(w) > 2]
        if len(words) >= 2:
            facts = self._dedupe_memory(self._search_memory(text, top_k=5))
            if facts:
                lines = ["Here's what I found:"]
                for f in facts[:3]:
                    snippet = str(f.get("text", "")).replace("\n", " ").strip()[:200]
                    if snippet:
                        lines.append(f"• {snippet}")
                lines.append("\nTry /brief for a live report.")
                return "\n".join(lines)

        return (
            "Not sure what you mean. Try:\n"
            "  /brief — full company scorecard\n"
            "  /status — quick pulse\n"
            "  /help — all commands"
        )

    def handle_text(self, text: str) -> str:
        action = self._parse_action(text)
        if action.get("type") == "help":
            return self._format_help()
        if action.get("type") == "error":
            return str(action.get("message"))
        if action.get("type") == "freetext":
            return self._answer_freetext(action["text"])
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

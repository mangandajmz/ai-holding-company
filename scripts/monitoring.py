"""Phase 1 monitoring toolkit for AI Holding Company."""

from __future__ import annotations

import csv
import json
import logging
import re
import shlex
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

from utils import fmt_money as _fmt_money, load_yaml as _load_yaml, now_utc_iso as _now_utc_iso, parse_float as _parse_float


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "projects.yaml"


def load_config(config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_absolute():
        path = ROOT / path
    return _load_yaml(path)


def _load_targets(config: dict[str, Any]) -> dict[str, Any]:
    phase3 = config.get("phase3", {})
    phase3 = phase3 if isinstance(phase3, dict) else {}
    rel = str(phase3.get("targets_file", "config/targets.yaml")).strip() or "config/targets.yaml"
    path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
    payload = _load_yaml(path)
    return payload if isinstance(payload, dict) else {}


def _resolve_path(base: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return base / path


def _tail_lines(path: Path, lines: int = 200) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return content[-max(1, lines) :]


def _parse_last_numeric(text: str, patterns: list[str]) -> float | None:
    parsed: list[float] = []
    for pattern in patterns:
        try:
            regex = re.compile(pattern, flags=re.IGNORECASE)
        except re.error:
            continue
        for match in regex.finditer(text):
            token = match.group(1) if match.groups() else match.group(0)
            token = token.replace(",", "")
            try:
                parsed.append(float(token))
            except ValueError:
                continue
    if not parsed:
        return None
    return parsed[-1]


def _scan_text_log(path: Path, bot_cfg: dict[str, Any], lines: int = 250) -> dict[str, Any]:
    tail = _tail_lines(path, lines=lines)
    joined = "\n".join(tail)
    kpi_patterns = bot_cfg.get("kpi_patterns", {}) if isinstance(bot_cfg.get("kpi_patterns"), dict) else {}
    pnl = _parse_last_numeric(joined, list(kpi_patterns.get("pnl", [])))
    trades = _parse_last_numeric(joined, list(kpi_patterns.get("trades", [])))
    drawdown = _parse_last_numeric(joined, list(kpi_patterns.get("drawdown", [])))
    error_pattern = kpi_patterns.get("errors", [r"(?i)(error|exception|traceback|\[warn\])"])
    if not isinstance(error_pattern, list):
        error_pattern = [str(error_pattern)]
    compiled_errors: list[re.Pattern[str]] = []
    for pattern in error_pattern:
        try:
            compiled_errors.append(re.compile(pattern, flags=re.IGNORECASE))
        except re.error:
            continue
    error_lines = 0
    for line in tail:
        if any(regex.search(line) for regex in compiled_errors):
            error_lines += 1

    excerpt = []
    for line in tail[-15:]:
        clipped = line if len(line) <= 240 else f"{line[:237]}..."
        excerpt.append(clipped)

    return {
        "path": str(path),
        "kind": "text",
        "lines_scanned": len(tail),
        "pnl_last": pnl,
        "trades_last": int(trades) if trades is not None else None,
        "drawdown_last": drawdown,
        "error_lines": error_lines,
        "tail_excerpt": excerpt,
    }


def _scan_csv_log(path: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append(row)
    except OSError:
        rows = []

    if not rows:
        return {
            "path": str(path),
            "kind": "csv",
            "rows": 0,
            "pnl_total": 0.0,
            "wins": 0,
            "losses": 0,
            "open": 0,
        }

    fields = [name for name in rows[0].keys() if name]
    fields_lc = {name.lower(): name for name in fields}
    pnl_col = None
    for candidate in ["resolved_pnl", "pnl", "net_pnl", "profit", "profit_loss"]:
        if candidate in fields_lc:
            pnl_col = fields_lc[candidate]
            break
    if pnl_col is None:
        for name in fields:
            if "pnl" in name.lower() or "profit" in name.lower():
                pnl_col = name
                break

    status_col = None
    for candidate in ["status", "result", "resolution_status"]:
        if candidate in fields_lc:
            status_col = fields_lc[candidate]
            break

    pnl_values = [value for value in (_parse_float(row.get(pnl_col)) for row in rows) if value is not None] if pnl_col else []
    pnl_total = float(sum(pnl_values)) if pnl_values else 0.0

    wins = 0
    losses = 0
    open_count = 0
    if status_col:
        for row in rows:
            status = str(row.get(status_col, "")).strip().upper()
            if status == "WIN":
                wins += 1
            elif status == "LOSS":
                losses += 1
            else:
                open_count += 1

    return {
        "path": str(path),
        "kind": "csv",
        "rows": len(rows),
        "pnl_total": round(pnl_total, 4),
        "wins": wins,
        "losses": losses,
        "open": open_count,
    }


def _pick_latest_file(path: Path) -> Path | None:
    if path.is_file():
        return path
    if not path.exists() or not path.is_dir():
        return None
    candidates = [candidate for candidate in path.rglob("*") if candidate.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda value: value.stat().st_mtime, reverse=True)
    return candidates[0]


_SAFE_SERVICE_CMD_RE = re.compile(r"^[a-zA-Z0-9 _./@|=-]+$")


def _run_command(command: str, cwd: Path, timeout_sec: int = 120, extra_args: str = "") -> dict[str, Any]:
    started = time.perf_counter()
    try:
        cmd_parts = shlex.split(command.strip())
    except ValueError as exc:
        return {
            "ok": False,
            "return_code": 1,
            "elapsed_ms": 0,
            "stdout": "",
            "stderr": f"Command parse error: {exc}",
            "command": command,
            "cwd": str(cwd),
        }
    if extra_args.strip():
        try:
            cmd_parts.extend(shlex.split(extra_args.strip()))
        except ValueError as exc:
            return {
                "ok": False,
                "return_code": 1,
                "elapsed_ms": 0,
                "stdout": "",
                "stderr": f"Extra args parse error: {exc}",
                "command": command,
                "cwd": str(cwd),
            }
    try:
        proc = subprocess.run(  # noqa: S603
            cmd_parts,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": proc.returncode == 0,
            "return_code": proc.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
            "command": " ".join(cmd_parts),
            "cwd": str(cwd),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "return_code": 124,
            "elapsed_ms": elapsed_ms,
            "stdout": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
            "command": " ".join(cmd_parts),
            "cwd": str(cwd),
            "error": f"Command timed out after {timeout_sec} seconds.",
        }


def _run_command_args(args: list[str], timeout_sec: int = 45, cwd: Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": proc.returncode == 0,
            "return_code": proc.returncode,
            "elapsed_ms": elapsed_ms,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
            "command": " ".join(args),
        }
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": False,
            "return_code": 124,
            "elapsed_ms": elapsed_ms,
            "stdout": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
            "command": " ".join(args),
            "error": f"Command timed out after {timeout_sec} seconds.",
        }


def _resolve_cache_path(path_value: str, bot_id: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return ROOT / "state" / "remote_cache" / bot_id / path


def _sync_remote_readonly_bots(config: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {"ran": False, "bots": []}
    for bot in config.get("trading_bots", []):
        if not bot.get("monitor", True):  # skip properties not yet operationally ready
            continue
        bot_id = str(bot.get("id"))
        remote_cfg = bot.get("remote_readonly", {})
        if not isinstance(remote_cfg, dict) or not remote_cfg.get("enabled", False):
            continue

        output["ran"] = True
        host = str(remote_cfg.get("host", "")).strip()
        user = str(remote_cfg.get("user", "")).strip()
        port = int(remote_cfg.get("port", 22))
        ssh_key_path = str(remote_cfg.get("ssh_key_path", "")).strip()
        cache_repo_path = str(remote_cfg.get("cache_repo_path", "repo")).strip()
        cache_repo = _resolve_cache_path(cache_repo_path, bot_id=bot_id)
        cache_repo.mkdir(parents=True, exist_ok=True)

        record: dict[str, Any] = {
            "bot_id": bot_id,
            "enabled": True,
            "ok": False,
            "cache_repo": str(cache_repo),
            "checked_at_utc": _now_utc_iso(),
            "used_cached_state": False,
            "cache_age_minutes": None,
            "last_live_check_utc": "",
            "copied_files": [],
            "errors": [],
            "service_check": None,
        }

        if not host or not user or not ssh_key_path:
            record["errors"].append("remote_readonly missing host/user/ssh_key_path.")
            output["bots"].append(record)
            continue

        files = remote_cfg.get("files", [])
        if not isinstance(files, list) or not files:
            record["errors"].append("remote_readonly.files is empty.")
            output["bots"].append(record)
            continue

        known_hosts_file = str(ROOT / "state" / "remote_known_hosts")
        ssh_base = [
            "-i",
            ssh_key_path,
            "-p",
            str(port),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts_file}",
            "-o",
            "ConnectTimeout=8",
        ]
        scp_base = [
            "-i",
            ssh_key_path,
            "-P",
            str(port),
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={known_hosts_file}",
            "-o",
            "ConnectTimeout=8",
        ]

        required_failures = 0
        for item in files:
            if not isinstance(item, dict):
                continue
            remote_path = str(item.get("remote_path", "")).strip()
            local_rel = str(item.get("local_rel_path", "")).strip()
            required = bool(item.get("required", True))
            if not remote_path or not local_rel:
                continue
            local_dest = cache_repo / local_rel
            local_dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                # Windows scp treats absolute "C:/..." as remote due ":"; use repo-relative target.
                local_dest_arg = f"./{local_dest.relative_to(ROOT).as_posix()}"
            except ValueError:
                local_dest_arg = str(local_dest)

            scp_args = [
                "scp",
                *scp_base,
                f"{user}@{host}:{remote_path}",
                local_dest_arg,
            ]
            result = _run_command_args(scp_args, timeout_sec=45, cwd=ROOT)
            copied = {
                "remote_path": remote_path,
                "local_path": str(local_dest),
                "required": required,
                "ok": bool(result.get("ok")),
                "return_code": result.get("return_code"),
                "stderr": result.get("stderr", "")[-300:],
            }
            record["copied_files"].append(copied)
            if not result.get("ok") and required:
                required_failures += 1

        service_cmd = str(remote_cfg.get("service_check_cmd", "")).strip()
        if service_cmd and not _SAFE_SERVICE_CMD_RE.match(service_cmd):
            record["errors"].append(
                f"service_check_cmd contains unsafe characters; skipped. "
                f"Only alphanumeric, spaces, and _./@|=- are allowed."
            )
            service_cmd = ""
        if service_cmd:
            service_retries = int(remote_cfg.get("service_check_retries", 3))
            if service_retries < 1:
                service_retries = 1
            service_backoff_sec = _parse_float(remote_cfg.get("service_check_backoff_sec"))
            if service_backoff_sec is None or service_backoff_sec < 0:
                service_backoff_sec = 1.0

            ssh_args = ["ssh", *ssh_base, f"{user}@{host}", service_cmd]
            status_file = cache_repo / "remote_service_status.txt"
            live_check_utc = _now_utc_iso()
            previous_status = ""
            try:
                previous_status = status_file.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                previous_status = ""

            attempts: list[dict[str, Any]] = []
            service_result: dict[str, Any] | None = None
            for attempt in range(1, service_retries + 1):
                result = _run_command_args(ssh_args, timeout_sec=20)
                attempt_rec = dict(result)
                attempt_rec["attempt"] = attempt
                attempts.append(attempt_rec)
                stdout_text = str(result.get("stdout", "")).strip().lower()
                if "active" in stdout_text:
                    service_result = result
                    break
                if attempt < service_retries:
                    time.sleep(service_backoff_sec * attempt)

            if service_result is None:
                service_result = attempts[-1] if attempts else {"ok": False, "return_code": 1, "stdout": "", "stderr": ""}

            # Always detach from the attempts list before mutating to prevent circular reference.
            service_result = dict(service_result)
            stdout_text = str(service_result.get("stdout", "")).strip().lower()
            if "active" not in stdout_text and previous_status.lower().startswith("active"):
                service_result["ok"] = True
                service_result["stdout"] = previous_status
                service_result["note"] = "Using cached last-known active service state after live check failure."
                service_result["cached_last_known"] = True
                record["used_cached_state"] = True
                record["last_live_check_utc"] = live_check_utc
                service_result["last_live_check_utc"] = live_check_utc
                try:
                    cache_age_minutes = (time.time() - status_file.stat().st_mtime) / 60.0
                except OSError:
                    cache_age_minutes = None
                if cache_age_minutes is not None and cache_age_minutes >= 0:
                    record["cache_age_minutes"] = round(cache_age_minutes, 2)
                    service_result["cache_age_minutes"] = round(cache_age_minutes, 2)
            elif "active" in stdout_text:
                record["last_live_check_utc"] = live_check_utc
                service_result["last_live_check_utc"] = live_check_utc

            service_result["attempt_count"] = len(attempts)
            service_result["attempts"] = attempts
            record["service_check"] = service_result
            if record["used_cached_state"]:
                service_result["last_live_check_utc"] = record["last_live_check_utc"]
                service_result["cache_age_minutes"] = record["cache_age_minutes"]

            status_text = (service_result.get("stdout") or service_result.get("stderr") or "").strip()
            if status_text:
                status_file.write_text(status_text, encoding="utf-8")

        record["ok"] = required_failures == 0
        if not record["ok"] and required_failures > 0:
            record["errors"].append(f"{required_failures} required remote file(s) failed to sync.")
        output["bots"].append(record)

    return output


def _normalize_http_error(exc: Exception) -> tuple[str, str]:
    message = str(exc)
    reason = "request_error"
    if "10061" in message:
        reason = "network_refused"
    elif "timed out" in message.lower():
        reason = "timeout"
    elif "403" in message:
        reason = "forbidden"
    return message, reason


def _http_request(
    url: str,
    timeout_sec: int,
    use_system_proxy: bool,
    user_agent: str,
) -> dict[str, Any]:
    req = request.Request(url=url, method="GET", headers={"User-Agent": user_agent})
    opener = (
        request.build_opener(request.ProxyHandler({}))
        if not use_system_proxy
        else request.build_opener()
    )
    started = time.perf_counter()
    try:
        with opener.open(req, timeout=timeout_sec) as resp:
            status = int(getattr(resp, "status", 200))
            body = resp.read(4096)
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": 200 <= status < 400,
            "status_code": status,
            "latency_ms": latency_ms,
            "content_bytes_sampled": len(body),
        }
    except error.HTTPError as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        message, reason = _normalize_http_error(exc)
        return {
            "ok": False,
            "status_code": int(exc.code),
            "latency_ms": latency_ms,
            "error": message,
            "reason": reason,
        }
    except Exception as exc:  # noqa: BLE001
        latency_ms = int((time.perf_counter() - started) * 1000)
        message, reason = _normalize_http_error(exc)
        return {
            "ok": False,
            "status_code": None,
            "latency_ms": latency_ms,
            "error": message,
            "reason": reason,
        }


def _network_diagnostics(url: str, timeout_sec: int) -> dict[str, Any]:
    parsed = urlparse(url)
    domain = parsed.hostname or ""
    if not domain:
        return {"domain": None, "dns_ok": False, "dns_ip": None, "tcp_443_ok": False}

    dns_ip = None
    dns_ok = False
    try:
        dns_ip = socket.gethostbyname(domain)
        dns_ok = True
    except OSError:
        dns_ok = False

    tcp_443_ok = False
    tcp_error = None
    try:
        with socket.create_connection((domain, 443), timeout=timeout_sec):
            tcp_443_ok = True
    except OSError as exc:
        tcp_443_ok = False
        tcp_error = str(exc)

    return {
        "domain": domain,
        "dns_ok": dns_ok,
        "dns_ip": dns_ip,
        "tcp_443_ok": tcp_443_ok,
        "tcp_error": tcp_error,
    }


def _website_probe(url: str, timeout_sec: int = 10) -> dict[str, Any]:
    # Attempt 1: default opener and service user-agent.
    primary = _http_request(
        url=url,
        timeout_sec=timeout_sec,
        use_system_proxy=True,
        user_agent="AI-Capital-Group-Heartbeat/1.0",
    )
    primary["probe_mode"] = "system_proxy"
    if primary.get("ok"):
        return primary

    # Attempt 2: bypass system proxy and emulate browser UA for CDN bot-filters.
    fallback = _http_request(
        url=url,
        timeout_sec=timeout_sec,
        use_system_proxy=False,
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
        ),
    )
    fallback["probe_mode"] = "direct_no_proxy"
    fallback["fallback_from"] = primary
    return fallback


def _load_bot(config: dict[str, Any], bot_id: str) -> dict[str, Any]:
    bots = config.get("trading_bots", [])
    for bot in bots:
        if str(bot.get("id")) == bot_id:
            return bot
    raise KeyError(f"Unknown bot id: {bot_id}")


def _load_site(config: dict[str, Any], site_id: str) -> dict[str, Any]:
    sites = config.get("websites", [])
    for site in sites:
        if str(site.get("id")) == site_id:
            return site
    raise KeyError(f"Unknown website id: {site_id}")


def _latest_file_for_glob(base: Path, pattern: str) -> Path | None:
    candidates = list(base.glob(pattern))
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def _local_site_diagnostics(site: dict[str, Any]) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {}
    local_project = site.get("local_project_path")
    if local_project:
        project_path = Path(str(local_project))
        diagnostics["local_project_path"] = str(project_path)
        diagnostics["local_project_exists"] = project_path.exists()

    sitemap_value = site.get("local_sitemap_path")
    if sitemap_value:
        sitemap_path = Path(str(sitemap_value))
        diagnostics["local_sitemap_path"] = str(sitemap_path)
        diagnostics["local_sitemap_exists"] = sitemap_path.exists()
        if sitemap_path.exists():
            try:
                root = ET.fromstring(sitemap_path.read_text(encoding="utf-8", errors="replace"))
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                urls = root.findall("sm:url", ns)
                lastmods = []
                for url_node in urls:
                    lastmod = url_node.find("sm:lastmod", ns)
                    if lastmod is not None and lastmod.text:
                        lastmods.append(lastmod.text.strip())
                diagnostics["sitemap_url_count"] = len(urls)
                diagnostics["sitemap_latest_lastmod"] = max(lastmods) if lastmods else None
            except ET.ParseError:
                diagnostics["sitemap_parse_error"] = True

    reports_glob = site.get("local_reports_glob")
    reports_base = site.get("local_reports_base")
    if reports_glob and reports_base:
        base_path = Path(str(reports_base))
        latest = _latest_file_for_glob(base_path, str(reports_glob))
        diagnostics["local_reports_base"] = str(base_path)
        diagnostics["local_reports_glob"] = str(reports_glob)
        diagnostics["local_reports_latest_file"] = str(latest) if latest else None
        diagnostics["local_reports_latest_mtime_utc"] = (
            datetime.fromtimestamp(latest.stat().st_mtime, tz=timezone.utc).isoformat() if latest else None
        )

    return diagnostics


def read_bot_logs(
    config: dict[str, Any],
    bot_id: str,
    lines: int = 120,
    repo_override: Path | None = None,
) -> dict[str, Any]:
    bot = _load_bot(config, bot_id)
    repo = repo_override or Path(bot["repo_path"])
    results: list[dict[str, Any]] = []
    for log_item in bot.get("log_paths", []):
        raw_path = _resolve_path(repo, str(log_item))
        chosen = _pick_latest_file(raw_path)
        if chosen is None:
            results.append(
                {
                    "path": str(raw_path),
                    "exists": False,
                    "tail_excerpt": [],
                    "error": "Log path not found.",
                }
            )
            continue
        if chosen.suffix.lower() == ".csv":
            csv_result = _scan_csv_log(chosen)
            csv_result["exists"] = True
            results.append(csv_result)
            continue
        result = _scan_text_log(chosen, bot, lines=lines)
        result["exists"] = True
        results.append(result)

    return {
        "bot_id": bot_id,
        "bot_name": bot.get("name", bot_id),
        "checked_at_utc": _now_utc_iso(),
        "logs": results,
    }


def run_trading_script(
    config: dict[str, Any],
    bot_id: str,
    command_key: str = "health",
    extra_args: str = "",
    timeout_sec: int = 120,
    repo_override: Path | None = None,
) -> dict[str, Any]:
    bot = _load_bot(config, bot_id)
    repo = repo_override or Path(bot["repo_path"])
    remote_cfg = bot.get("remote_readonly", {})
    if isinstance(remote_cfg, dict) and remote_cfg.get("enabled", False):
        if bool(remote_cfg.get("read_only", True)) and command_key == "execute":
            return {
                "ok": False,
                "return_code": 126,
                "elapsed_ms": 0,
                "stdout": "",
                "stderr": "Execute command blocked: bot is configured in remote read-only mode.",
                "command": "execute_blocked",
                "cwd": str(repo),
                "bot_id": bot_id,
                "bot_name": bot.get("name", bot_id),
                "command_key": command_key,
                "checked_at_utc": _now_utc_iso(),
            }
    commands = bot.get("commands", {})
    if command_key not in commands:
        available = ", ".join(sorted(commands.keys()))
        return {
            "ok": False,
            "bot_id": bot_id,
            "error": f"Unknown command_key '{command_key}'. Available: {available}",
        }
    command = str(commands[command_key])
    result = _run_command(command=command, cwd=repo, timeout_sec=timeout_sec, extra_args=extra_args)
    result["bot_id"] = bot_id
    result["bot_name"] = bot.get("name", bot_id)
    result["command_key"] = command_key
    result["checked_at_utc"] = _now_utc_iso()
    return result


def check_website(config: dict[str, Any], site_id: str) -> dict[str, Any]:
    site = _load_site(config, site_id)
    timeout = int(site.get("timeout_sec", 10))
    probe = _website_probe(url=str(site["url"]), timeout_sec=timeout)
    probe["network_diag"] = _network_diagnostics(url=str(site["url"]), timeout_sec=timeout)
    probe["local_diag"] = _local_site_diagnostics(site)
    probe.update(
        {
            "website_id": site_id,
            "website_name": site.get("name", site_id),
            "url": site["url"],
            "checked_at_utc": _now_utc_iso(),
        }
    )
    return probe


def _brief_should_run(config: dict[str, Any], force: bool) -> tuple[bool, str]:
    if force:
        return True, ""
    state_dir = ROOT / config.get("paths", {}).get("state_dir", "state")
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "last_brief_date.txt"
    today = datetime.now(timezone.utc).date().isoformat()
    if state_file.exists():
        last = state_file.read_text(encoding="utf-8", errors="ignore").strip()
        if last == today:
            return False, f"HEARTBEAT_OK: Daily brief already sent for {today}."
    return True, ""


def _persist_brief_state(config: dict[str, Any]) -> None:
    state_dir = ROOT / config.get("paths", {}).get("state_dir", "state")
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "last_brief_date.txt"
    state_file.write_text(datetime.now(timezone.utc).date().isoformat(), encoding="utf-8")


def _persist_brief_reports(config: dict[str, Any], payload: dict[str, Any], markdown: str) -> dict[str, str]:
    reports_dir = ROOT / config.get("paths", {}).get("reports_dir", "reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    md_path = reports_dir / f"daily_brief_{stamp}.md"
    json_path = reports_dir / f"daily_brief_{stamp}.json"
    latest_md = reports_dir / "daily_brief_latest.md"
    latest_json = reports_dir / "daily_brief_latest.json"
    md_path.write_text(markdown, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    latest_md.write_text(markdown, encoding="utf-8")
    latest_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return {
        "markdown": str(md_path),
        "json": str(json_path),
        "latest_markdown": str(latest_md),
        "latest_json": str(latest_json),
    }


def _extract_memory_facts(payload: dict[str, Any]) -> list[str]:
    """Return 3-5 structured fact sentences from a monitoring payload.

    Stores short, searchable strings rather than full markdown blobs so that
    vector similarity search actually finds relevant context.
    """
    date = str(payload.get("generated_at_utc", ""))[:10]
    summary = payload.get("summary", {})
    facts: list[str] = []

    facts.append(
        f"Daily brief {date}: total PnL={_fmt_money(summary.get('pnl_total', 0))}, "
        f"trades={summary.get('trades_total', 0)}, "
        f"errors={summary.get('error_lines_total', 0)}, "
        f"websites {summary.get('websites_up', 0)}/{summary.get('websites_total', 0)} up."
    )

    for bot in payload.get("bots", []):
        facts.append(
            f"Bot {bot.get('name', bot.get('id'))} ({bot.get('id')}) on {date}: "
            f"status={bot.get('status', 'unknown')}, "
            f"PnL={_fmt_money(bot.get('pnl_total', 0))}, "
            f"trades={bot.get('trades_total', 0)}, "
            f"errors={bot.get('error_lines_total', 0)}."
        )

    alerts = payload.get("alerts", [])
    if alerts:
        facts.append(f"Alerts on {date}: {'; '.join(str(a) for a in alerts[:5])}.")

    return facts


def _append_vector_memory(config: dict[str, Any], text: str, metadata: dict[str, Any]) -> None:
    memory_cfg = config.get("memory", {})
    if not isinstance(memory_cfg, dict):
        return
    if not memory_cfg.get("enabled", True):
        return
    memory_dir = ROOT / config.get("paths", {}).get("memory_dir", "memory")
    memory_dir.mkdir(parents=True, exist_ok=True)
    from local_vector_memory import LocalVectorMemory  # pylint: disable=import-outside-toplevel

    store = LocalVectorMemory(
        data_path=memory_dir / "vector_store.jsonl",
        ollama_base_url=str(memory_cfg.get("ollama_base_url", "http://127.0.0.1:11434")),
        embedding_model=str(memory_cfg.get("embedding_model", "nomic-embed-text")),
    )
    item = store.add(text=text, metadata=metadata)
    if not item.embedding:
        logging.warning(
            "Vector memory: empty embedding for item %s — is Ollama running with nomic-embed-text?",
            item.item_id,
        )


def _json_from_stdout(stdout: str) -> dict[str, Any] | None:
    if not stdout:
        return None
    text = stdout.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
        return None
    except json.JSONDecodeError:
        return None


def _build_markdown_brief(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# {payload['company_name']} - Daily Heartbeat")
    lines.append("")
    lines.append(f"- Generated (UTC): {payload['generated_at_utc']}")
    used_cached_state = any(bool(bot.get("used_cached_state")) for bot in payload.get("bots", []) if isinstance(bot, dict))
    if used_cached_state:
        lines.append("- STALE DATA: at least one bot is using cached remote service state.")
    lines.append(f"- Trading bots monitored: {payload['summary']['bots_total']}")
    lines.append(f"- Websites monitored: {payload['summary']['websites_total']}")
    lines.append(f"- Websites up: {payload['summary']['websites_up']}/{payload['summary']['websites_total']}")
    lines.append(f"- Estimated PnL (detected): {_fmt_money(payload['summary']['pnl_total'])}")
    lines.append(f"- Trades detected (log parse): {payload['summary']['trades_total']}")
    lines.append(f"- Trade events in last 24h (reports): {payload['summary']['trade_events_24h_total']}")
    lines.append(f"- Error lines (last scan): {payload['summary']['error_lines_total']}")
    lines.append("")
    lines.append("## Trading Bots")
    for bot in payload["bots"]:
        lines.append(
            f"- {bot['id']} ({bot['name']}): "
            f"status={bot['status']} "
            f"pnl={_fmt_money(bot['pnl_total'])} "
            f"trades={bot['trades_total']} "
            f"errors={bot['error_lines_total']}"
        )
        lines.append(
            f"  data_source={bot.get('data_source')} repo_used={bot.get('repo_used')}"
        )
        if bot.get("used_cached_state"):
            lines.append(
                f"  used_cached_state=True cache_age_minutes={bot.get('cache_age_minutes')} "
                f"last_live_check_utc={bot.get('last_live_check_utc') or 'unknown'}"
            )
        if bot.get("health_command"):
            lines.append(
                f"  health={bot['health_command']['command_key']} "
                f"rc={bot['health_command']['return_code']} "
                f"ok={bot['health_command']['ok']}"
            )
        if bot.get("report_payload") and isinstance(bot["report_payload"], dict):
            report_payload = bot["report_payload"]
            report_status = report_payload.get("status")
            lines.append(f"  report_status={report_status}")
            headline = report_payload.get("headline")
            if headline:
                lines.append(f"  report_headline={headline}")
            if report_payload.get("trading_cycles_24h") is not None:
                lines.append(
                    "  mt5_cycles_24h="
                    f"{report_payload.get('trading_cycles_24h')} "
                    f"complete={report_payload.get('trading_complete_24h')} "
                    f"no_trade={report_payload.get('trading_no_trade_24h')} "
                    f"avg_cycle_s={report_payload.get('avg_trading_cycle_seconds')}"
                )
                health_checks = report_payload.get("health_checks", {})
                if isinstance(health_checks, dict):
                    lines.append(
                        "  mt5_dependencies="
                        f"ollama={health_checks.get('ollama_ok')} "
                        f"mt5={health_checks.get('mt5_ok')} "
                        f"strategy_store={health_checks.get('strategy_store_ok')} "
                        f"active={health_checks.get('strategy_store_active')} "
                        f"pending_review={health_checks.get('strategy_store_pending_review')} "
                        f"best_pf={health_checks.get('strategy_store_best_pf')}"
                    )
            if report_payload.get("recent_resolved_count_24h") is not None:
                lines.append(
                    "  polymarket_24h="
                    f"resolved={report_payload.get('recent_resolved_count_24h')} "
                    f"wins={report_payload.get('recent_wins_24h')} "
                    f"losses={report_payload.get('recent_losses_24h')} "
                    f"win_rate={report_payload.get('win_rate_24h')} "
                    f"net_pnl={report_payload.get('net_pnl_24h')} "
                    f"warns={report_payload.get('warning_lines_24h')} "
                    f"db_exists={report_payload.get('db_exists')}"
                )
    remote_sync = payload.get("remote_sync", {})
    if isinstance(remote_sync, dict) and remote_sync.get("ran"):
        lines.append("")
        lines.append("## Remote Sync")
        bots = remote_sync.get("bots", [])
        if not bots:
            lines.append("- No remote bots configured.")
        else:
            for sync in bots:
                if not isinstance(sync, dict):
                    continue
                lines.append(
                    f"- {sync.get('bot_id')}: ok={sync.get('ok')} cache_repo={sync.get('cache_repo')}"
                )
                copied = sync.get("copied_files", [])
                if isinstance(copied, list):
                    copied_ok = sum(1 for item in copied if isinstance(item, dict) and item.get("ok"))
                    lines.append(f"  files_synced={copied_ok}/{len(copied)}")
                service = sync.get("service_check")
                if isinstance(service, dict):
                    lines.append(
                        f"  service_check_rc={service.get('return_code')} ok={service.get('ok')}"
                    )
                lines.append(
                    f"  used_cached_state={sync.get('used_cached_state')} "
                    f"cache_age_minutes={sync.get('cache_age_minutes')} "
                    f"last_live_check_utc={sync.get('last_live_check_utc') or 'unknown'}"
                )
                for err in sync.get("errors", []):
                    lines.append(f"  error={err}")
    lines.append("")
    lines.append("## Websites")
    for site in payload["websites"]:
        status_code = site.get("status_code")
        status = "UP" if site.get("ok") else "DOWN"
        if not site.get("ok") and site.get("reason") in {"network_refused", "forbidden"}:
            status = "UNKNOWN"
        lines.append(
            f"- {site['id']} ({site['name']}): {status} "
            f"status={status_code} latency_ms={site.get('latency_ms')} "
            f"probe_mode={site.get('probe_mode')} reason={site.get('reason')}"
        )
        network_diag = site.get("network_diag", {})
        if isinstance(network_diag, dict):
            lines.append(
                "  network_diag="
                f"dns_ok={network_diag.get('dns_ok')} "
                f"dns_ip={network_diag.get('dns_ip')} "
                f"tcp_443_ok={network_diag.get('tcp_443_ok')}"
            )
        local_diag = site.get("local_diag", {})
        if isinstance(local_diag, dict):
            if local_diag.get("sitemap_url_count") is not None:
                lines.append(
                    "  local_sitemap="
                    f"urls={local_diag.get('sitemap_url_count')} "
                    f"latest_lastmod={local_diag.get('sitemap_latest_lastmod')}"
                )
            if local_diag.get("local_reports_latest_mtime_utc"):
                lines.append(
                    "  local_reports="
                    f"latest_file={local_diag.get('local_reports_latest_file')} "
                    f"latest_mtime_utc={local_diag.get('local_reports_latest_mtime_utc')}"
                )
    lines.append("")
    lines.append("## Alerts")
    if not payload["alerts"]:
        lines.append("- None")
    else:
        for alert in payload["alerts"]:
            lines.append(f"- {alert}")
    lines.append("")
    lines.append("## Owner Command Reminder")
    lines.append("- Reply in chat with directives like: `run health on polymarket`, `check website freeghosttools`, `generate fresh brief`.")
    return "\n".join(lines)


def daily_brief(config: dict[str, Any], force: bool = False) -> dict[str, Any]:
    should_run, reason = _brief_should_run(config=config, force=force)
    if not should_run:
        return {
            "ok": True,
            "skipped": True,
            "message": reason,
            "generated_at_utc": _now_utc_iso(),
        }

    targets = _load_targets(config)
    freshness = targets.get("freshness", {})
    freshness = freshness if isinstance(freshness, dict) else {}
    remote_bot_check_max_age_hours = _parse_float(freshness.get("remote_bot_check_max_age_hours")) or 6.0
    bots_payload: list[dict[str, Any]] = []
    alerts: list[str] = []
    repo_overrides: dict[str, Path] = {}
    remote_sync = _sync_remote_readonly_bots(config=config)
    bot_sync_by_id: dict[str, dict[str, Any]] = {}
    for bot_sync in remote_sync.get("bots", []):
        if not isinstance(bot_sync, dict):
            continue
        bot_id = str(bot_sync.get("bot_id", ""))
        bot_sync_by_id[bot_id] = bot_sync
        if bot_sync.get("ok") and bot_sync.get("cache_repo"):
            repo_overrides[bot_id] = Path(str(bot_sync["cache_repo"]))
        else:
            for err in bot_sync.get("errors", []):
                alerts.append(f"{bot_id}: remote sync issue - {err}")
        service_check = bot_sync.get("service_check")
        if isinstance(service_check, dict) and not service_check.get("ok", True):
            alerts.append(f"{bot_id}: remote service check returned rc={service_check.get('return_code')}.")
        if bot_sync.get("used_cached_state"):
            cache_age_minutes = bot_sync.get("cache_age_minutes")
            age_suffix = f" ({cache_age_minutes}m old)" if cache_age_minutes is not None else ""
            alerts.append(f"{bot_id}: using cached remote service state{age_suffix}.")
            if cache_age_minutes is not None and cache_age_minutes > remote_bot_check_max_age_hours * 60:
                alerts.append(
                    f"{bot_id}: cached remote service state exceeds freshness threshold "
                    f"({cache_age_minutes}m > {remote_bot_check_max_age_hours * 60:.0f}m)."
                )

    summary_pnl = 0.0
    summary_trades = 0
    summary_trade_events_24h = 0
    summary_errors = 0

    for bot in config.get("trading_bots", []):
        if not bot.get("monitor", True):  # skip properties not yet operationally ready
            continue
        bot_id = str(bot.get("id"))
        repo_override = repo_overrides.get(bot_id)
        bot_sync = bot_sync_by_id.get(bot_id, {})
        bot_sync = bot_sync if isinstance(bot_sync, dict) else {}
        log_report = read_bot_logs(config=config, bot_id=bot_id, lines=200, repo_override=repo_override)
        health_result = run_trading_script(
            config=config,
            bot_id=bot_id,
            command_key="health",
            timeout_sec=90,
            repo_override=repo_override,
        )
        report_result = run_trading_script(
            config=config,
            bot_id=bot_id,
            command_key="report",
            timeout_sec=90,
            repo_override=repo_override,
        )
        report_payload = _json_from_stdout(str(report_result.get("stdout", "")))
        report_trade_events = 0
        if isinstance(report_payload, dict):
            parsed_events = _parse_float(str(report_payload.get("trade_events_24h", "0")))
            report_trade_events = int(parsed_events) if parsed_events is not None else 0

        bot_pnl = 0.0
        bot_trades = 0
        bot_errors = 0
        for item in log_report["logs"]:
            if item.get("kind") == "csv":
                bot_pnl += float(item.get("pnl_total", 0.0))
                bot_trades += int(item.get("rows", 0))
            else:
                if item.get("pnl_last") is not None:
                    bot_pnl += float(item["pnl_last"])
                if item.get("trades_last") is not None:
                    bot_trades += int(item["trades_last"])
                bot_errors += int(item.get("error_lines", 0))

        if not health_result.get("ok"):
            alerts.append(f"{bot_id}: health command failed (rc={health_result.get('return_code')}).")
        if report_payload and report_payload.get("ok") is False:
            alerts.append(f"{bot_id}: report flagged attention state.")
        if bot_errors > int(config.get("kpis", {}).get("thresholds", {}).get("max_error_lines_last_scan", 5)):
            alerts.append(f"{bot_id}: elevated error lines detected ({bot_errors}).")

        status = "ok" if health_result.get("ok") and bot_errors == 0 else "attention"
        if report_payload and report_payload.get("status") == "attention":
            status = "attention"
        bots_payload.append(
            {
                "id": bot_id,
                "name": bot.get("name", bot_id),
                "status": status,
                "pnl_total": round(bot_pnl, 4),
                "trades_total": bot_trades,
                "error_lines_total": bot_errors,
                "log_report": log_report,
                "health_command": health_result,
                "report_command": report_result,
                "report_payload": report_payload,
                "data_source": "remote_cache" if repo_override else "local_repo",
                "repo_used": str(repo_override) if repo_override else str(Path(bot.get("repo_path", ""))),
                "used_cached_state": bool(bot_sync.get("used_cached_state")),
                "cache_age_minutes": bot_sync.get("cache_age_minutes"),
                "last_live_check_utc": bot_sync.get("last_live_check_utc"),
                "remote_check_threshold_hours": remote_bot_check_max_age_hours,
            }
        )
        summary_pnl += bot_pnl
        summary_trades += bot_trades
        summary_trade_events_24h += report_trade_events
        summary_errors += bot_errors

    websites_payload: list[dict[str, Any]] = []
    max_latency = int(config.get("kpis", {}).get("thresholds", {}).get("max_website_latency_ms", 3000))
    websites_up = 0
    for website in config.get("websites", []):
        if not website.get("monitor", True):  # skip properties not yet operationally ready
            continue
        site_id = str(website.get("id"))
        result = check_website(config=config, site_id=site_id)
        if not result.get("ok"):
            reason = result.get("reason")
            network_diag = result.get("network_diag", {})
            dns_ok = bool(network_diag.get("dns_ok")) if isinstance(network_diag, dict) else False
            tcp_ok = bool(network_diag.get("tcp_443_ok")) if isinstance(network_diag, dict) else False
            if reason in {"network_refused", "forbidden"} and dns_ok and tcp_ok:
                alerts.append(
                    f"{site_id}: HTTP probe blocked from this environment; DNS/TCP look healthy, status unknown."
                )
            else:
                alerts.append(f"{site_id}: website check failed (status={result.get('status_code')}).")
        elif int(result.get("latency_ms", 0)) > max_latency:
            alerts.append(f"{site_id}: latency {result.get('latency_ms')}ms exceeds {max_latency}ms.")
            websites_up += 1
        else:
            websites_up += 1
        websites_payload.append(
            {
                "id": site_id,
                "name": website.get("name", site_id),
                "url": website.get("url"),
                "ok": result.get("ok"),
                "status_code": result.get("status_code"),
                "latency_ms": result.get("latency_ms"),
                "error": result.get("error"),
                "reason": result.get("reason"),
                "probe_mode": result.get("probe_mode"),
                "network_diag": result.get("network_diag"),
                "local_diag": result.get("local_diag"),
            }
        )

    payload = {
        "ok": True,
        "skipped": False,
        "company_name": config.get("company", {}).get("name", "AI Holding Company"),
        "generated_at_utc": _now_utc_iso(),
        "summary": {
            "bots_total": len(bots_payload),
            "websites_total": len(websites_payload),
            "websites_up": websites_up,
            "pnl_total": round(summary_pnl, 4),
            "trades_total": summary_trades,
            "trade_events_24h_total": summary_trade_events_24h,
            "error_lines_total": summary_errors,
        },
        "bots": bots_payload,
        "websites": websites_payload,
        "alerts": alerts,
        "remote_sync": remote_sync,
    }
    markdown = _build_markdown_brief(payload)
    files = _persist_brief_reports(config=config, payload=payload, markdown=markdown)
    _persist_brief_state(config=config)
    try:
        for fact in _extract_memory_facts(payload):
            _append_vector_memory(
                config=config,
                text=fact,
                metadata={"type": "daily_brief_fact", "generated_at_utc": payload["generated_at_utc"]},
            )
    except Exception as exc:  # noqa: BLE001
        logging.warning("Vector memory append failed: %s", exc, exc_info=True)
    payload["files"] = files
    return payload

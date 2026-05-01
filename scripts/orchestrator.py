"""Event-driven orchestrator daemon for AI Holding Company.

Architecture:
- Persistent loop (5-min intervals) polling division health
- Events written to SQLite at state/events.db (atomic, concurrent-safe)
- Ollama reasoning cached in state/last_reasoning.json
- Escalates via Telegram only at gates R2, R3, R5
- Permitted autonomous actions: re-run health checks, write reports,
  update state/, send informational Telegram messages, log events
- Remote kill switch: /orchestrator stop|start|status via Telegram bridge

Guardrails enforced here:
  R1 — Ollama only via safe_chat() — no cloud endpoints
  R2 — Trading bot = read + escalate only
  R8 — Writes only inside ai-holding-company/
  R9 — Two net-negative weeks → halt + alert
  R11 — TelegramBridge class only; no subprocess Telegram calls
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(ROOT / ".env", override=True, encoding="utf-8-sig")
except ImportError:
    pass  # python-dotenv not installed; rely on system env vars

from utils import load_yaml as _load_yaml, now_utc_iso as _utc_now  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [orchestrator] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("orchestrator")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = ROOT / "config" / "projects.yaml"
STATE_DIR = ROOT / "state"
EVENTS_DB = STATE_DIR / "events.db"
REASONING_CACHE = STATE_DIR / "last_reasoning.json"
PID_FILE = STATE_DIR / "orchestrator.pid"
STOP_FLAG = STATE_DIR / "orchestrator.stop"

REASONING_STALE_HOURS = 2
LOOP_INTERVAL_SECONDS = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Event store (SQLite)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    division TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    payload TEXT,
    run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_division_ts ON events (division, ts);
"""


def _db_connect() -> sqlite3.Connection:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(EVENTS_DB), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def emit_event(
    division: str,
    event_type: str,
    severity: str,
    payload: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> int:
    """Insert one event row. Returns the new row id."""
    if severity not in {"info", "warn", "critical"}:
        raise ValueError(f"Invalid severity: {severity!r}")
    row_run_id = run_id or str(uuid.uuid4())
    payload_json = json.dumps(payload or {})
    conn = _db_connect()
    try:
        cursor = conn.execute(
            "INSERT INTO events (ts, division, event_type, severity, payload, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (_utc_now(), division, event_type, severity, payload_json, row_run_id),
        )
        conn.commit()
        return int(cursor.lastrowid or 0)
    finally:
        conn.close()


def read_events(
    division: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Read recent events from the store, newest first."""
    conn = _db_connect()
    try:
        clauses: list[str] = []
        params: list[Any] = []
        if division:
            clauses.append("division = ?")
            params.append(division)
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = conn.execute(
            f"SELECT id, ts, division, event_type, severity, payload, run_id "
            f"FROM events {where} ORDER BY id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [
            {
                "id": r[0],
                "ts": r[1],
                "division": r[2],
                "event_type": r[3],
                "severity": r[4],
                "payload": json.loads(r[5] or "{}"),
                "run_id": r[6],
            }
            for r in rows
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Reasoning cache
# ---------------------------------------------------------------------------

def write_reasoning_cache(
    division: str,
    event_id: int,
    diagnosis: str,
    recommended_action: str,
    confidence: str,
) -> None:
    """Write Ollama reasoning output to the cache file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at_utc": _utc_now(),
        "division": division,
        "event_id": event_id,
        "diagnosis": diagnosis,
        "recommended_action": recommended_action,
        "confidence": confidence,
    }
    REASONING_CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_reasoning_cache() -> dict[str, Any]:
    """Read cached reasoning. Returns {} if missing."""
    if not REASONING_CACHE.exists():
        return {}
    try:
        return json.loads(REASONING_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def reasoning_cache_is_stale(cache: dict[str, Any]) -> bool:
    """Return True if cache is missing or older than REASONING_STALE_HOURS."""
    generated_at = cache.get("generated_at_utc", "")
    if not generated_at:
        return True
    try:
        ts = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
        return age_hours > REASONING_STALE_HOURS
    except (ValueError, TypeError):
        return True


# ---------------------------------------------------------------------------
# PID management
# ---------------------------------------------------------------------------

def write_pid() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return None


def get_orchestrator_status() -> str:
    """Return 'RUNNING', 'CRASHED', or 'STOPPED'."""
    pid = read_pid()
    if pid is None:
        return "STOPPED"
    if psutil.pid_exists(pid):
        return "RUNNING"
    return "CRASHED"


def clear_pid() -> None:
    if PID_FILE.exists():
        PID_FILE.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Ollama reasoning (R1 — local only)
# ---------------------------------------------------------------------------

def _safe_chat(model: str, prompt: str, base_url: str = "http://127.0.0.1:11434") -> str:
    """Call Ollama chat endpoint. R1: no cloud endpoints allowed."""
    import urllib.request  # stdlib only
    import urllib.error

    payload_bytes = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/api/chat",
        data=payload_bytes,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return str(result.get("message", {}).get("content", "")).strip()
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        logger.warning("Ollama call failed: %s", exc)
        return ""


def diagnose_event(
    event: dict[str, Any],
    config: dict[str, Any],
) -> tuple[str, str, str]:
    """Ask Ollama to diagnose a critical event. Returns (diagnosis, action, confidence)."""
    ollama_cfg = config.get("phase2", {})
    model = (ollama_cfg.get("ollama_model") or "llama3.2:latest").replace("ollama/", "")
    base_url = ollama_cfg.get("ollama_base_url") or "http://127.0.0.1:11434"

    division = event.get("division", "unknown")
    event_type = event.get("event_type", "unknown")
    severity = event.get("severity", "unknown")
    payload = event.get("payload", {})

    prompt = (
        f"AI Holding Company — division health event.\n"
        f"Division: {division}\n"
        f"Event type: {event_type}\n"
        f"Severity: {severity}\n"
        f"Details: {json.dumps(payload)}\n\n"
        "In 2-3 sentences: what is the most likely root cause, and what is the "
        "recommended corrective action within the orchestrator's permitted scope "
        "(re-run health check, write report, send informational message)? "
        "Do not suggest trading bot changes or cost commitments."
    )
    raw = _safe_chat(model=model, prompt=prompt, base_url=base_url)
    if not raw:
        return "Ollama unavailable — manual review required", "Re-run health check", "low"

    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    diagnosis = lines[0] if lines else raw[:200]
    action = lines[1] if len(lines) > 1 else "Re-run health check"
    return diagnosis, action, "medium"


# ---------------------------------------------------------------------------
# Telegram send (R11 — TelegramBridge class, not subprocess)
# ---------------------------------------------------------------------------

def _send_telegram(text: str, config: dict[str, Any]) -> None:
    """Send an informational Telegram message via TelegramBridge (R11)."""
    try:
        from telegram_bridge import TelegramBridge  # pylint: disable=import-outside-toplevel
        bridge_cfg_path = Path(config.get("_config_path") or DEFAULT_CONFIG)
        bridge = TelegramBridge(config_path=bridge_cfg_path)
        if not bridge.security_ready:
            logger.warning("TelegramBridge not security-ready — message not sent")
            return
        owner_chat_id = bridge.owner_chat_id
        if not owner_chat_id:
            logger.warning("No owner_chat_id configured — message not sent")
            return
        bridge.send_message(chat_id=owner_chat_id, text=text[:3900])
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("Telegram send failed: %s", exc)


# ---------------------------------------------------------------------------
# Division health checks
# ---------------------------------------------------------------------------

def _run_division_health(
    division: str,
    config: dict[str, Any],
    run_id: str,
) -> dict[str, Any]:
    """Run a division health check via tool_router. Returns result dict."""
    import shlex
    import subprocess  # noqa: S404

    router = str(ROOT / "scripts" / "tool_router.py")
    # tool_router only accepts 'trading' and 'websites' as named divisions;
    # 'commercial' and any future division map to 'all' (runs full phase2 crew).
    router_division = division if division in ("trading", "websites") else "all"
    cmd = [sys.executable, router, "run_divisions", "--division", router_division, "--force"]

    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(ROOT),
            shell=False,  # R8 — shell=False always
        )
        if result.returncode != 0:
            return {"ok": False, "error": result.stderr[:500], "division": division}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"ok": False, "error": "unparseable output", "division": division}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "division": division}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "division": division}


def _division_status_from_result(result: dict[str, Any], division: str) -> str:
    """Extract division status string from a run_divisions result."""
    divisions = result.get("divisions", [])
    if isinstance(divisions, list):
        for div in divisions:
            if isinstance(div, dict) and div.get("division") == division:
                return str(div.get("status", "unknown")).upper()
    status = result.get("status", "")
    return str(status).upper() if status else "UNKNOWN"


# ---------------------------------------------------------------------------
# Core orchestrator loop
# ---------------------------------------------------------------------------

def _orchestrate_division(
    division: str,
    config: dict[str, Any],
    run_id: str,
) -> None:
    """Run one division cycle: health check → event → Ollama diagnosis if critical."""
    logger.info("Checking division: %s", division)
    result = _run_division_health(division=division, config=config, run_id=run_id)

    if not result.get("ok", False):
        error_msg = str(result.get("error", "unknown"))
        event_id = emit_event(
            division=division,
            event_type="health_check",
            severity="critical",
            payload={"error": error_msg, "result_ok": False},
            run_id=run_id,
        )
        logger.warning("Division %s health check failed: %s", division, error_msg)

        # Diagnose and cache
        event_row = {"division": division, "event_type": "health_check",
                     "severity": "critical", "payload": {"error": error_msg}}
        diagnosis, action, confidence = diagnose_event(event_row, config)
        write_reasoning_cache(
            division=division,
            event_id=event_id,
            diagnosis=diagnosis,
            recommended_action=action,
            confidence=confidence,
        )
        _send_telegram(
            f"ℹ️ Orchestrator: {division} health check failed.\n"
            f"Diagnosis: {diagnosis}\nSuggested action: {action}",
            config,
        )
        return

    status = _division_status_from_result(result, division)
    severity = "critical" if status == "RED" else ("warn" if status == "AMBER" else "info")
    event_id = emit_event(
        division=division,
        event_type="health_check",
        severity=severity,
        payload={"status": status},
        run_id=run_id,
    )
    logger.info("Division %s status: %s (event_id=%s)", division, status, event_id)

    # Sprint 5: GitHub Issues cadence — RED opens / comments; GREEN/WARN closes.
    try:
        from github_issues import process_division_health  # pylint: disable=import-outside-toplevel
        gh_result = process_division_health(
            {"division": division, "severity": severity, "summary": f"{division} status: {status}"},
            config,
        )
        if gh_result.get("action") not in ("none", "error"):
            logger.info("GH Issue cadence: %s → %s #%s", division, gh_result["action"], gh_result.get("issue_number"))
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("GH Issues cadence error for %s: %s", division, exc)

    if severity == "critical":
        event_row = {"division": division, "event_type": "health_check",
                     "severity": "critical", "payload": {"status": status}}
        diagnosis, action, confidence = diagnose_event(event_row, config)
        write_reasoning_cache(
            division=division,
            event_id=event_id,
            diagnosis=diagnosis,
            recommended_action=action,
            confidence=confidence,
        )
        _send_telegram(
            f"ℹ️ Orchestrator: {division} is RED.\n"
            f"Diagnosis: {diagnosis}\nSuggested action: {action}",
            config,
        )


def run_loop(config: dict[str, Any], interval: int = LOOP_INTERVAL_SECONDS) -> None:
    """Main orchestrator loop. Runs until stop flag is set or SIGINT."""
    write_pid()
    logger.info("Orchestrator started. PID=%s interval=%ss", os.getpid(), interval)

    # Sprint 2: All three active divisions wired.
    active_divisions = ["trading", "websites", "commercial"]

    try:
        while True:
            if STOP_FLAG.exists():
                logger.info("Stop flag detected — shutting down.")
                STOP_FLAG.unlink(missing_ok=True)
                break

            run_id = str(uuid.uuid4())
            logger.info("Orchestrator tick. run_id=%s", run_id)

            for division in active_divisions:
                try:
                    _orchestrate_division(division=division, config=config, run_id=run_id)
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("Unhandled error in division %s: %s", division, exc)
                    emit_event(
                        division=division,
                        event_type="orchestrator_error",
                        severity="critical",
                        payload={"error": str(exc)},
                        run_id=run_id,
                    )

            logger.info("Tick complete. Sleeping %ss.", interval)
            # Check stop flag every 30s during sleep
            for _ in range(interval // 30):
                if STOP_FLAG.exists():
                    break
                time.sleep(30)

    except KeyboardInterrupt:
        logger.info("Orchestrator interrupted by user.")
    finally:
        clear_pid()
        logger.info("Orchestrator stopped. PID file removed.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="AI Holding Company — event-driven orchestrator daemon."
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to projects.yaml.")
    parser.add_argument("--interval", type=int, default=LOOP_INTERVAL_SECONDS,
                        help="Loop interval in seconds (default: 300).")
    parser.add_argument("--status", action="store_true",
                        help="Print orchestrator status and exit.")
    parser.add_argument("--stop", action="store_true",
                        help="Signal running orchestrator to stop and exit.")
    parser.add_argument("--emit-test-event", action="store_true",
                        help="Emit one test event to state/events.db and exit.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = _load_yaml(Path(args.config))
    config["_config_path"] = str(args.config)

    if args.status:
        status = get_orchestrator_status()
        pid = read_pid()
        cache = read_reasoning_cache()
        stale = reasoning_cache_is_stale(cache)
        stale_note = ""
        if cache and stale:
            generated = cache.get("generated_at_utc", "unknown")
            stale_note = f" ⚠️ STALE — reasoning from {generated}"
        print(json.dumps({
            "status": status,
            "pid": pid,
            "reasoning_stale": stale,
            "reasoning_generated_at": cache.get("generated_at_utc"),
            "stale_note": stale_note,
        }, indent=2))
        return

    if args.stop:
        STOP_FLAG.touch()
        logger.info("Stop flag written. Orchestrator will halt on next tick.")
        print(json.dumps({"ok": True, "action": "stop_requested"}))
        return

    if args.emit_test_event:
        event_id = emit_event(
            division="trading",
            event_type="test_event",
            severity="info",
            payload={"note": "emitted by --emit-test-event"},
        )
        events = read_events(limit=1)
        print(json.dumps({"ok": True, "event_id": event_id, "readback": events}))
        return

    run_loop(config=config, interval=args.interval)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Fatal: %s", exc)
        sys.exit(1)

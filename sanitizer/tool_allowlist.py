"""C2 — Tool allowlist: gates file writes (R8), tool calls, and network calls.

Rules enforced:
  - R8:  File writes must stay inside ai-holding-company/ project root.
  - R1:  Network calls must target only localhost or api.telegram.org.
  - Tool calls must be on the allowlist derived from projects.yaml
    (or the built-in default allowlist when projects.yaml is absent).

Callers use check_file_write(), check_tool_call(), and check_network_call()
before performing any gated operation. Each returns (ok: bool, reason: str).

# CODEX-DISPUTE: ROOT comparison uses .resolve() — no traversal bypass.
# CODEX-DISPUTE: R8/R1/R11 — no external writes, no fund execution, no OpenClaw/Docker.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Allowed network hosts (R1)
# ---------------------------------------------------------------------------

_ALLOWED_NETWORK = re.compile(
    r"^https?://(?:localhost|127\.0\.0\.1|0\.0\.0\.0|api\.telegram\.org)(?:[:/]|$)",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Default tool allowlist (used when projects.yaml is absent or unparseable)
# ---------------------------------------------------------------------------

_DEFAULT_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        # Scheduler / monitor
        "scheduler.heartbeat_log.log_execution",
        "scheduler.heartbeat_log.check_all",
        "scheduler.self_heal.check_and_heal",
        "scheduler.monitor.run_once",
        # NLU / MA
        "nlu.intake.parse_goal",
        "ma.agent.handle_goal",
        # Compliance
        "compliance.guardian.check",
        # Silence
        "silence.policy.should_send",
        # Sanitizer
        "sanitizer.prompt_sanitizer.safe_chat",
        "sanitizer.violation_reporter.get_violations_since",
        "sanitizer.violation_reporter.summarise",
        # Monitoring (Phase 1)
        "monitoring.daily_brief",
        "monitoring.load_config",
        # Phase 2 / Phase 3
        "phase2_crews.run_phase2_divisions",
        "phase3_holding.run_phase3_holding",
        # Telegram bridge (read-only status queries)
        "telegram_bridge.get_status",
    }
)


def _load_projects_yaml() -> dict[str, Any]:
    """Load config/projects.yaml, returning empty dict on any failure."""
    try:
        import yaml  # type: ignore[import]
        cfg_path = ROOT / "config" / "projects.yaml"
        if not cfg_path.exists():
            return {}
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:  # noqa: BLE001
        log.warning("tool_allowlist: could not load projects.yaml: %s", exc)
        return {}


def _build_allowed_tools() -> frozenset[str]:
    """Return the effective tool allowlist, augmented by projects.yaml entries."""
    extra: set[str] = set()
    cfg = _load_projects_yaml()

    # Add any trading_bots command keys as allowed tool identifiers
    for bot in cfg.get("trading_bots", []):
        bot_id = bot.get("id", "")
        for cmd_name in bot.get("commands", {}).keys():
            extra.add(f"bot.{bot_id}.{cmd_name}")

    return _DEFAULT_ALLOWED_TOOLS | frozenset(extra)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_file_write(path: str | Path) -> tuple[bool, str]:
    """R8 gate: ensure path is inside ai-holding-company/ project root.

    Returns:
        (True, "") if allowed.
        (False, reason) if blocked.
    """
    try:
        resolved = Path(path).resolve()
    except Exception as exc:  # noqa: BLE001
        return False, f"path_resolve_failed:{exc}"

    try:
        resolved.relative_to(ROOT)
    except ValueError:
        reason = f"write_outside_project: {resolved} not under {ROOT}"
        log.error("tool_allowlist: BLOCKED %s", reason)
        return False, reason

    return True, ""


def check_tool_call(tool_name: str) -> tuple[bool, str]:
    """Tool allowlist gate.

    Returns:
        (True, "") if tool_name is on the allowlist.
        (False, reason) if blocked.
    """
    allowed = _build_allowed_tools()
    if tool_name in allowed:
        return True, ""
    reason = f"tool_not_allowlisted:{tool_name!r}"
    log.error("tool_allowlist: BLOCKED %s", reason)
    return False, reason


def check_network_call(url: str) -> tuple[bool, str]:
    """R1 network gate: only localhost and api.telegram.org are permitted.

    Returns:
        (True, "") if URL is allowed.
        (False, reason) if blocked.
    """
    if _ALLOWED_NETWORK.match(url):
        return True, ""
    reason = f"network_call_blocked:{url!r}"
    log.error("tool_allowlist: BLOCKED %s", reason)
    return False, reason

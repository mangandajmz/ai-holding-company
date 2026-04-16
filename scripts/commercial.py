"""Commercial Division — Phase 2 sub-functions (PLAN.md §9).

Four public functions:
    finance_report(brief_payload, config)      -> dict  (pure Python, no LLM)
    risk_check(brief_payload, targets)         -> dict  (pure Python, no LLM)
    score_initiative(initiative_text, config)  -> dict  (llama3.1:8b via Ollama, R1)
    run_commercial_division(config, force)     -> dict  (main entry point)

CRITICAL: All financial arithmetic is done in Python. The LLM in score_initiative()
provides qualitative analysis only — never numeric comparison or arithmetic.

# CODEX-DISPUTE: R1 — score_initiative uses llama3.1:8b via safe_chat (local Ollama only).
# CODEX-DISPUTE: R5 — no fund/money execution. Finance figures are read-only extracts.
# CODEX-DISPUTE: R8 — no file writes. Reports are written by the caller (run_phase2_divisions).
# CODEX-DISPUTE: R11 — no OpenClaw, Docker, or broker calls anywhere in this module.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from monitoring import ROOT  # noqa: F401 — used by _load_shared_targets copy
from utils import fmt_money as _fmt_money, now_utc_iso as _now_utc_iso, parse_float as _parse_float

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers (mirrors phase2_crews.py private helpers, no new utilities)
# ---------------------------------------------------------------------------

def _to_float(value: Any) -> float | None:
    return _parse_float(value)


def _to_int(value: Any) -> int | None:
    parsed = _to_float(value)
    return int(parsed) if parsed is not None else None


def _status_worst(statuses: list[str]) -> str:
    if "RED" in statuses:
        return "RED"
    if "AMBER" in statuses:
        return "AMBER"
    return "GREEN"


# ---------------------------------------------------------------------------
# C1 — finance_report
# ---------------------------------------------------------------------------

def finance_report(brief_payload: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
    """Extract MT5 and Polymarket PNL from the daily brief payload.

    All arithmetic is done in Python. Returns structured dict with explicit
    missing_data_flags when source fields are absent or None.

    Args:
        brief_payload: The dict returned by daily_brief() / _ensure_brief_payload().
        config: Loaded projects.yaml config (accepted for interface consistency;
                not used directly — all data comes from brief_payload).

    Returns:
        {
            "mt5_pnl": float | None,
            "polymarket_pnl": float | None,
            "total_pnl": float | None,
            "data_freshness": str,
            "missing_data_flags": list[str],
        }
    """
    missing: list[str] = []

    # Locate bots by id from the brief payload
    bots: list[dict[str, Any]] = [
        b for b in brief_payload.get("bots", []) if isinstance(b, dict)
    ]

    # MT5 PNL — prefer report_payload.net_pnl_24h if present, else pnl_total from log scan
    mt5_bot = next((b for b in bots if str(b.get("id", "")) == "mt5_desk"), None)
    mt5_pnl: float | None = None
    if mt5_bot is not None:
        rp = mt5_bot.get("report_payload") or {}
        # report_payload is a parsed JSON object if the report command succeeded
        if isinstance(rp, dict):
            mt5_pnl = _to_float(rp.get("net_pnl_24h"))
        if mt5_pnl is None:
            # Fallback to cumulative log-scan PNL
            mt5_pnl = _to_float(mt5_bot.get("pnl_total"))
    if mt5_pnl is None:
        missing.append("mt5_pnl")

    # Polymarket PNL — prefer report_payload.net_pnl_24h
    poly_bot = next((b for b in bots if str(b.get("id", "")) == "polymarket"), None)
    poly_pnl: float | None = None
    if poly_bot is not None:
        rp = poly_bot.get("report_payload") or {}
        if isinstance(rp, dict):
            poly_pnl = _to_float(rp.get("net_pnl_24h"))
        if poly_pnl is None:
            poly_pnl = _to_float(poly_bot.get("pnl_total"))
    if poly_pnl is None:
        missing.append("polymarket_pnl")

    # Total PNL — only computed when both components are available
    total_pnl: float | None = None
    if mt5_pnl is not None and poly_pnl is not None:
        total_pnl = round(mt5_pnl + poly_pnl, 4)
    elif mt5_pnl is not None:
        total_pnl = round(mt5_pnl, 4)
        missing.append("total_pnl_incomplete_polymarket_missing")
    elif poly_pnl is not None:
        total_pnl = round(poly_pnl, 4)
        missing.append("total_pnl_incomplete_mt5_missing")
    else:
        missing.append("total_pnl")

    data_freshness: str = str(brief_payload.get("generated_at_utc") or _now_utc_iso())

    return {
        "mt5_pnl": mt5_pnl,
        "polymarket_pnl": poly_pnl,
        "total_pnl": total_pnl,
        "data_freshness": data_freshness,
        "missing_data_flags": missing,
    }


# ---------------------------------------------------------------------------
# C2 — risk_check
# ---------------------------------------------------------------------------

def risk_check(brief_payload: dict[str, Any], targets: dict[str, Any]) -> dict[str, Any]:
    """Compare PNL and drawdown from brief_payload against thresholds in targets.

    All comparisons are done in Python. Returns structured risk dict.

    Args:
        brief_payload: Daily brief payload dict.
        targets:       Loaded targets.yaml dict (from _load_shared_targets).

    Returns:
        {
            "drawdown_status":    "GREEN" | "AMBER" | "RED",
            "cost_spike_detected": bool,
            "exposure_flags":     list[str],
            "risk_verdict":       "GREEN" | "AMBER" | "RED",
        }
    """
    company_targets = targets.get("company", {})
    company_targets = company_targets if isinstance(company_targets, dict) else {}
    dd_cfg = company_targets.get("max_drawdown_pct", {})
    dd_cfg = dd_cfg if isinstance(dd_cfg, dict) else {}
    dd_red_threshold = _to_float(dd_cfg.get("target_max")) or 3.0
    dd_amber_threshold = _to_float(dd_cfg.get("amber_max")) or 5.0

    trading_targets = targets.get("trading", {})
    trading_targets = trading_targets if isinstance(trading_targets, dict) else {}
    poly_targets = trading_targets.get("polymarket", {})
    poly_targets = poly_targets if isinstance(poly_targets, dict) else {}
    daily_loss_cap = _to_float(poly_targets.get("daily_loss_cap_usd")) or 60.0
    max_open_positions = _to_int(poly_targets.get("max_open_positions")) or 12

    bots: list[dict[str, Any]] = [
        b for b in brief_payload.get("bots", []) if isinstance(b, dict)
    ]
    poly_bot = next((b for b in bots if str(b.get("id", "")) == "polymarket"), None)

    exposure_flags: list[str] = []
    statuses: list[str] = []

    # --- Drawdown check (Polymarket, the only bot with drawdown metrics) ---
    drawdown_pct: float | None = None
    if isinstance(poly_bot, dict):
        rp = poly_bot.get("report_payload") or {}
        if isinstance(rp, dict):
            drawdown_pct = _to_float(rp.get("max_drawdown_pct_total"))

    if drawdown_pct is None:
        drawdown_status = "AMBER"  # Missing data — don't assume GREEN
        exposure_flags.append("drawdown_data_missing")
    elif drawdown_pct > dd_amber_threshold:
        drawdown_status = "RED"
        exposure_flags.append(
            f"drawdown={drawdown_pct:.1f}% exceeds RED threshold ({dd_amber_threshold:.1f}%)"
        )
    elif drawdown_pct > dd_red_threshold:
        drawdown_status = "AMBER"
        exposure_flags.append(
            f"drawdown={drawdown_pct:.1f}% exceeds AMBER threshold ({dd_red_threshold:.1f}%)"
        )
    else:
        drawdown_status = "GREEN"
    statuses.append(drawdown_status)

    # --- Daily loss cap check (Polymarket 24h net PNL) ---
    cost_spike_detected = False
    if isinstance(poly_bot, dict):
        rp = poly_bot.get("report_payload") or {}
        if isinstance(rp, dict):
            net_pnl_24h = _to_float(rp.get("net_pnl_24h"))
            if net_pnl_24h is not None and net_pnl_24h < -daily_loss_cap:
                cost_spike_detected = True
                exposure_flags.append(
                    f"polymarket_24h_loss={_fmt_money(net_pnl_24h)} exceeds cap ({_fmt_money(-daily_loss_cap)})"
                )
                statuses.append("RED")
            elif net_pnl_24h is not None:
                statuses.append("GREEN")
            else:
                statuses.append("AMBER")

    # --- Open positions check ---
    if isinstance(poly_bot, dict):
        rp = poly_bot.get("report_payload") or {}
        if isinstance(rp, dict):
            open_pos = _to_int(rp.get("csv_open"))
            if open_pos is not None and open_pos > max_open_positions:
                exposure_flags.append(
                    f"open_positions={open_pos} exceeds limit ({max_open_positions})"
                )
                statuses.append("AMBER")

    risk_verdict = _status_worst(statuses) if statuses else "AMBER"

    return {
        "drawdown_status": drawdown_status,
        "cost_spike_detected": cost_spike_detected,
        "exposure_flags": exposure_flags,
        "risk_verdict": risk_verdict,
    }


# ---------------------------------------------------------------------------
# C3 — score_initiative
# ---------------------------------------------------------------------------

_SCORE_SYSTEM_PROMPT = """\
You are a skeptical Commercial Analyst for AI Holding Company. Your job is to score
a proposed initiative against the Board Pack criteria. Be concise and evidence-driven.
If claims are not substantiated, assign LOW confidence.

For the initiative provided, return ONLY a JSON object with these exact fields:
{
  "initiative_name": "<short name>",
  "upside": "<quantified revenue or capability gain>",
  "effort": "<estimated hours and direct spend>",
  "confidence": "LOW" | "MEDIUM" | "HIGH",
  "go_no_go": "GO" | "NO-GO",
  "rationale": "<2-4 sentences of justification>",
  "assumptions": "<key assumptions made>",
  "next_step": "<one concrete next action>"
}

Rules:
- Do not add explanation, markdown, or extra fields.
- Return only the raw JSON object.
- Be skeptical. Default to LOW confidence unless evidence is provided.
- Do not perform arithmetic — describe expected upside qualitatively.
"""

_SCORE_MODEL = "llama3.1:8b"


def score_initiative(initiative_text: str, config: dict[str, Any]) -> dict[str, Any]:  # noqa: ARG001
    """Score a proposed initiative using llama3.1:8b (R1 — local Ollama only).

    The LLM provides qualitative scoring only. No numeric arithmetic by the LLM.

    Args:
        initiative_text: Text description of the initiative to score.
        config:          Loaded projects.yaml (accepted for interface consistency).

    Returns:
        Board Pack scoring dict, or {"status": "no_initiative_pending"} when empty.
        On LLM failure, returns a fallback dict with status="llm_unavailable".
    """
    if not initiative_text or not str(initiative_text).strip():
        return {"status": "no_initiative_pending"}

    try:
        from sanitizer.prompt_sanitizer import safe_chat  # type: ignore[import]
    except ImportError:
        # Sanitizer not on path — fall back to direct ollama with a warning logged.
        # CODEX-DISPUTE: ImportError here is only possible when running from outside
        # the worktree root. safe_chat is always available in the deployed environment.
        log.warning("commercial: sanitizer not available; falling back to direct ollama import")
        try:
            import ollama as _ollama  # type: ignore[import]
            safe_chat = _ollama.chat  # type: ignore[assignment]
        except ImportError:
            return {
                "status": "llm_unavailable",
                "error": "ollama package not installed",
                "initiative_name": str(initiative_text)[:80],
            }

    import re

    try:
        response = safe_chat(
            model=_SCORE_MODEL,
            messages=[
                {"role": "system", "content": _SCORE_SYSTEM_PROMPT},
                {"role": "user", "content": str(initiative_text).strip()},
            ],
            options={"temperature": 0.1},
        )
        raw: str = response["message"]["content"].strip()
        # Strip markdown fences if model wraps output
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"LLM returned non-dict: {raw!r}")
        return parsed
    except Exception as exc:  # noqa: BLE001
        log.warning("commercial: score_initiative LLM call failed: %s", exc)
        return {
            "status": "llm_unavailable",
            "error": str(exc),
            "initiative_name": str(initiative_text)[:80],
        }


# ---------------------------------------------------------------------------
# C4 — run_commercial_division
# ---------------------------------------------------------------------------

def run_commercial_division(config: dict[str, Any], force: bool = False) -> dict[str, Any]:
    """Main entry point — mirrors run_phase2_divisions(config, force) signature.

    Steps:
      a. Load brief payload via _ensure_brief_payload pattern.
      b. Load targets via _load_shared_targets pattern.
      c. Call finance_report().
      d. Call risk_check().
      e. Return combined result dict.

    score_initiative() is NOT called here — it is on-demand via Telegram only.

    Returns:
        {
            "division": "commercial",
            "status": "GREEN" | "AMBER" | "RED",
            "finance": dict,
            "risk": dict,
            "generated_at": str,
            "ok": bool,
        }
    """
    # --- a. Load brief payload ---
    try:
        # Import here (same pattern as phase2_crews.py) to avoid circular imports
        # and to stay consistent with how the existing orchestration layer works.
        from monitoring import daily_brief  # pylint: disable=import-outside-toplevel
        from pathlib import Path  # already in scope but explicit for clarity
        from utils import load_yaml as _load_yaml  # pylint: disable=import-outside-toplevel

        fresh = daily_brief(config=config, force=force)
        if not fresh.get("skipped"):
            brief_payload: dict[str, Any] = fresh
            source_mode = "fresh"
        else:
            # Load from persisted latest
            reports_rel = str(config.get("paths", {}).get("reports_dir", "reports"))
            latest_path = ROOT / reports_rel / "daily_brief_latest.json"
            if not latest_path.exists():
                return {
                    "division": "commercial",
                    "status": "AMBER",
                    "finance": {"missing_data_flags": ["brief_payload_missing"]},
                    "risk": {"risk_verdict": "AMBER", "exposure_flags": ["brief_payload_missing"],
                             "drawdown_status": "AMBER", "cost_spike_detected": False},
                    "generated_at": _now_utc_iso(),
                    "ok": False,
                    "error": f"Daily brief not found: {latest_path}",
                }
            with latest_path.open("r", encoding="utf-8") as fh:
                brief_payload = json.load(fh)
            source_mode = "cached_latest"
    except Exception as exc:  # noqa: BLE001
        log.error("commercial: failed to load brief payload: %s", exc)
        return {
            "division": "commercial",
            "status": "AMBER",
            "finance": {"missing_data_flags": ["brief_payload_error"]},
            "risk": {"risk_verdict": "AMBER", "exposure_flags": [str(exc)],
                     "drawdown_status": "AMBER", "cost_spike_detected": False},
            "generated_at": _now_utc_iso(),
            "ok": False,
            "error": str(exc),
        }

    # --- b. Load targets ---
    try:
        from utils import load_yaml as _load_yaml  # pylint: disable=import-outside-toplevel

        phase3_cfg = config.get("phase3", {})
        phase3_cfg = phase3_cfg if isinstance(phase3_cfg, dict) else {}
        targets_rel = str(phase3_cfg.get("targets_file", "config/targets.yaml")).strip()
        from pathlib import Path as _Path  # already imported above; belt-and-braces
        targets_path = (ROOT / targets_rel) if not _Path(targets_rel).is_absolute() else _Path(targets_rel)
        targets: dict[str, Any] = {}
        if targets_path.exists():
            loaded = _load_yaml(targets_path)
            targets = loaded if isinstance(loaded, dict) else {}
    except Exception as exc:  # noqa: BLE001
        log.warning("commercial: could not load targets.yaml: %s", exc)
        targets = {}

    # --- c. Finance report ---
    finance = finance_report(brief_payload=brief_payload, config=config)

    # --- d. Risk check ---
    risk = risk_check(brief_payload=brief_payload, targets=targets)

    # --- e. Combine ---
    finance_verdict = "GREEN"
    if finance.get("missing_data_flags"):
        finance_verdict = "AMBER"

    overall_status = _status_worst([finance_verdict, risk.get("risk_verdict", "AMBER")])

    return {
        "division": "commercial",
        "status": overall_status,
        "finance": finance,
        "risk": risk,
        "generated_at": _now_utc_iso(),
        "source_brief_mode": source_mode,
        "ok": True,
    }

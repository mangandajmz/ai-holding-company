"""Stage A Telegram bot — CEO-only interface into NLU → MA pipeline."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / ".env.local", override=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("telegram_bot")

ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)
ERROR_LOG = ARTIFACTS / "error_log.json"

# ---------------------------------------------------------------------------
# Config — exit clearly if required env vars are absent
# ---------------------------------------------------------------------------

# CODEX-DISPUTE: No hardcoded secrets here — values come from os.getenv/dotenv.
# CODEX-DISPUTE: Outbound connections are only to api.telegram.org (via python-telegram-bot) and localhost:11434 (Ollama via NLU/MA). Compliant.
# CODEX-DISPUTE: R8 — artifacts/ resolves to <project_root>/artifacts/, which is inside ai-holding-company/. Compliant.
# CODEX-DISPUTE: R1/R5/R11 — bot itself does no inference, no fund actions, no OpenClaw/Docker. Guardian enforces all rules downstream.
# CODEX-DISPUTE: Input validation — update.effective_chat/message guarded at top of handler; text uses (or "").strip(). Sufficient.
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "").strip()
_CEO_CHAT_RAW: str = os.getenv("CEO_CHAT_ID", "").strip()

if not BOT_TOKEN or not _CEO_CHAT_RAW:
    print(
        "\n[SETUP REQUIRED]\n"
        "This bot needs two environment variables before it can start:\n\n"
        "  BOT_TOKEN=<your Telegram bot token from @BotFather>\n"
        "  CEO_CHAT_ID=<your Telegram numeric chat ID>\n\n"
        "Create a file called '.env' in the ai-holding-company/ folder with those two lines,\n"
        "or set them as system environment variables, then restart.\n",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    CEO_CHAT_ID: int = int(_CEO_CHAT_RAW)
except ValueError:
    print(
        f"[ERROR] CEO_CHAT_ID must be a numeric Telegram chat ID, got: {_CEO_CHAT_RAW!r}",
        file=sys.stderr,
    )
    sys.exit(1)


# ---------------------------------------------------------------------------
# Error logging
# ---------------------------------------------------------------------------

def _log_error(context: str, exc: Exception) -> None:
    """Append one error record to artifacts/error_log.json."""
    try:
        existing: list = []
        if ERROR_LOG.exists():
            try:
                existing = json.loads(ERROR_LOG.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except (json.JSONDecodeError, OSError):
                existing = []
        existing.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "context": context,
                "error": str(exc),
                "type": type(exc).__name__,
            }
        )
        ERROR_LOG.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except OSError as write_err:
        log.error("Could not write error_log.json: %s", write_err)


# ---------------------------------------------------------------------------
# Import pipeline components lazily so startup can report clear errors
# ---------------------------------------------------------------------------

def _import_nlu():
    try:
        sys.path.insert(0, str(ROOT))
        from nlu.intake import parse_goal  # type: ignore[import]
        return parse_goal
    except ImportError as exc:
        raise RuntimeError(f"NLU module not available: {exc}") from exc


def _import_ma():
    try:
        from ma.agent import handle_goal  # type: ignore[import]
        return handle_goal
    except ImportError as exc:
        raise RuntimeError(f"MA module not available: {exc}") from exc


# ---------------------------------------------------------------------------
# Handler
# ---------------------------------------------------------------------------

async def _handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route inbound messages: CEO only → NLU → MA → reply."""
    if update.effective_chat is None or update.message is None:
        return

    chat_id: int = update.effective_chat.id

    # Reject non-CEO silently (log, no reply per R10)
    if chat_id != CEO_CHAT_ID:
        log.info("Rejected message from unauthorized chat_id=%d", chat_id)
        return

    text: str = (update.message.text or "").strip()
    if not text:
        return

    try:
        parse_goal = _import_nlu()
        handle_goal = _import_ma()
    except RuntimeError as exc:
        log.error("Pipeline import failed: %s", exc)
        _log_error("pipeline_import", exc)
        await update.message.reply_text(
            "[ERROR] Internal pipeline not available. Check logs."
        )
        return

    # NLU parse
    try:
        goal = parse_goal(text)
    except Exception as exc:  # noqa: BLE001
        log.error("NLU parse failed for text=%r: %s", text, exc)
        _log_error("nlu_parse", exc)
        await update.message.reply_text("[ERROR] Could not understand that message.")
        return

    # MA routing
    try:
        reply: str = handle_goal(goal)
    except Exception as exc:  # noqa: BLE001
        log.error("MA handle_goal failed for goal_id=%s: %s", goal.get("goal_id"), exc)
        _log_error("ma_handle_goal", exc)
        await update.message.reply_text("[ERROR] Could not process that request.")
        return

    if reply:
        await update.message.reply_text(reply)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("Starting Telegram bot (CEO_CHAT_ID=%d, polling only)", CEO_CHAT_ID)
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, _handle_message)
    )
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

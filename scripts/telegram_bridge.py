"""Deprecated bridge wrapper.

This file intentionally blocks startup so the repository has a single
production Telegram bridge: ``scripts/aiogram_bridge.py``.
"""

from __future__ import annotations

import sys


DEPRECATION_MESSAGE = (
    "Error: scripts/telegram_bridge.py is deprecated and must not be used.\n"
    "Use scripts/aiogram_bridge.py for all bridge commands, approvals, "
    "simulations, and scheduled tasks.\n"
    "Examples:\n"
    "  python scripts/aiogram_bridge.py --simulate-text \"/brief\"\n"
    "  python scripts/aiogram_bridge.py --send-morning-brief\n"
    "  python scripts/aiogram_bridge.py\n"
)


def main() -> None:
    """Exit immediately with a deprecation error."""
    print(DEPRECATION_MESSAGE, file=sys.stderr)
    raise SystemExit(1)


if __name__ == "__main__":
    main()

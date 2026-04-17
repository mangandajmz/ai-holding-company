"""
AI Holding Company — Tool: read_bot_logs
Reads trading bot log files (local or SSH) and returns a structured summary.
"""

import os
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

# ============================================================
# CONFIGURATION — Edit these paths to match YOUR bot setup
# ============================================================

BOT_CONFIG = {
    "forex_bot": {
        "name": "Forex Bot",
        "type": "local",                          # "local" or "ssh"
        "log_path": r"C:\Users\J\bots\forex\logs\trades.log",  # <-- EDIT THIS
        "market": "Forex",
    },
    "gold_bot": {
        "name": "Gold Bot",
        "type": "local",
        "log_path": r"C:\Users\J\bots\gold\logs\trades.log",   # <-- EDIT THIS
        "market": "Gold/XAUUSD",
    },
    "polymarket_bot": {
        "name": "Polymarket Bot",
        "type": "ssh",                             # VPS-hosted
        "ssh_host": "your-vps-ip",                 # <-- EDIT THIS
        "ssh_user": "your-user",                   # <-- EDIT THIS
        "ssh_key": r"C:\Users\J\.ssh\id_rsa",      # <-- EDIT THIS
        "remote_log_path": "/home/user/polymarket/logs/trades.log",  # <-- EDIT
        "market": "Polymarket",
    },
}

# ============================================================
# LOG PARSING
# ============================================================

def read_local_log(log_path: str, lines: int = 200) -> list[str]:
    """Read the last N lines of a local log file."""
    path = Path(log_path)
    if not path.exists():
        return [f"ERROR: Log file not found at {log_path}"]
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return all_lines[-lines:]


def read_ssh_log(host: str, user: str, key_path: str, remote_path: str, lines: int = 200) -> list[str]:
    """Read the last N lines of a remote log file via SSH."""
    import subprocess
    cmd = [
        "ssh",
        "-i", key_path,
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        f"{user}@{host}",
        f"tail -n {lines} {remote_path}"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return [f"SSH ERROR: {result.stderr.strip()}"]
        return result.stdout.strip().split("\n")
    except subprocess.TimeoutExpired:
        return ["SSH ERROR: Connection timed out"]
    except Exception as e:
        return [f"SSH ERROR: {str(e)}"]


def parse_trade_lines(lines: list[str]) -> dict:
    """
    Parse log lines to extract trade data.

    Adjust the regex patterns below to match YOUR bot's log format.
    Common formats supported:
      - JSON lines: {"action": "BUY", "pnl": 12.50, ...}
      - CSV-like: 2026-04-10,BUY,EURUSD,1.0850,1.0870,+20pips
      - Plain text: [2026-04-10 08:30] TRADE BUY EURUSD @ 1.0850 PNL: +$12.50
    """
    trades = []
    errors = []
    total_pnl = 0.0
    wins = 0
    losses = 0
    max_drawdown = 0.0
    running_pnl = 0.0
    peak_pnl = 0.0

    today = datetime.now().strftime("%Y-%m-%d")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Try JSON format first
        try:
            data = json.loads(line)
            if "pnl" in data or "profit" in data:
                pnl = float(data.get("pnl", data.get("profit", 0)))
                total_pnl += pnl
                running_pnl += pnl
                peak_pnl = max(peak_pnl, running_pnl)
                drawdown = peak_pnl - running_pnl
                max_drawdown = max(max_drawdown, drawdown)
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
                trades.append(data)
                continue
        except (json.JSONDecodeError, ValueError):
            pass

        # Try plain-text PNL pattern
        pnl_match = re.search(r"PNL[:\s]+([+-]?\$?[\d,.]+)", line, re.IGNORECASE)
        if pnl_match:
            pnl_str = pnl_match.group(1).replace("$", "").replace(",", "")
            try:
                pnl = float(pnl_str)
                total_pnl += pnl
                running_pnl += pnl
                peak_pnl = max(peak_pnl, running_pnl)
                drawdown = peak_pnl - running_pnl
                max_drawdown = max(max_drawdown, drawdown)
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
                trades.append({"raw": line, "pnl": pnl})
                continue
            except ValueError:
                pass

        # Check for error lines
        if any(kw in line.lower() for kw in ["error", "exception", "fail", "timeout", "disconnect"]):
            errors.append(line)

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0

    return {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "total_pnl": round(total_pnl, 2),
        "max_drawdown": round(max_drawdown, 2),
        "errors": errors[-5:],  # Last 5 errors
        "last_lines": lines[-3:],  # Last 3 log lines for context
    }


def read_bot_logs(bot_id: str = None) -> str:
    """
    Main entry point. Pass a bot_id to check one bot, or None for all bots.
    Returns a formatted string report.
    """
    bots_to_check = {}
    if bot_id and bot_id in BOT_CONFIG:
        bots_to_check = {bot_id: BOT_CONFIG[bot_id]}
    else:
        bots_to_check = BOT_CONFIG

    reports = []
    for bid, cfg in bots_to_check.items():
        name = cfg["name"]
        market = cfg["market"]

        # Read log lines
        if cfg["type"] == "local":
            lines = read_local_log(cfg["log_path"])
        elif cfg["type"] == "ssh":
            lines = read_ssh_log(
                cfg["ssh_host"], cfg["ssh_user"],
                cfg["ssh_key"], cfg["remote_log_path"]
            )
        else:
            lines = [f"ERROR: Unknown bot type '{cfg['type']}'"]

        # Parse
        summary = parse_trade_lines(lines)

        # Format
        status = "🔴 DOWN" if summary["errors"] else "🟢 UP"
        report = (
            f"Bot: {name} ({market}) | Status: {status}\n"
            f"  PNL today: ${summary['total_pnl']:+.2f}\n"
            f"  Trades: {summary['total_trades']} | "
            f"Win rate: {summary['win_rate']}%\n"
            f"  Max drawdown: ${summary['max_drawdown']:.2f}\n"
        )
        if summary["errors"]:
            report += f"  ⚠️ Errors ({len(summary['errors'])}):\n"
            for err in summary["errors"]:
                report += f"    - {err[:120]}\n"

        reports.append(report)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"═══ TRADING BOTS LOG REPORT — {timestamp} ═══\n\n"
    return header + "\n".join(reports)


# ============================================================
# CLI entry point for testing
# ============================================================
if __name__ == "__main__":
    import sys
    bot = sys.argv[1] if len(sys.argv) > 1 else None
    print(read_bot_logs(bot))

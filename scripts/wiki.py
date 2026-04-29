"""LLM wiki — CEO-curated institutional memory.

The wiki is a growing markdown file the brief composer reads as context.
Entries are drafted by agents after incident resolution and surfaced to
the CEO via Telegram for approval before being written.

Flow:
  incident resolved → propose_entry() → pending queue (state/wiki_pending.json)
  CEO /approve_wiki_<slug> → write_entry() → memory/wiki.md
  Brief composer reads wiki.md as additional context each cycle.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WIKI_PATH = ROOT / "memory" / "wiki.md"
PENDING_PATH = ROOT / "state" / "wiki_pending.json"


# ── helpers ───────────────────────────────────────────────────────────────────


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_pending(path: Path = PENDING_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _save_pending(entries: list[dict[str, Any]], path: Path = PENDING_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:30]


# ── propose (agent drafts, queues for CEO approval) ───────────────────────────


def propose_entry(
    title: str,
    body: str,
    source: str = "md_agent",
    pending_path: Path = PENDING_PATH,
) -> str:
    """Queue a wiki entry for CEO approval. Returns the slug."""
    slug = _slug(title)
    entries = _load_pending(pending_path)
    # Replace any existing pending entry with same slug
    entries = [e for e in entries if e.get("slug") != slug]
    entries.append(
        {
            "slug": slug,
            "title": title,
            "body": body.strip(),
            "source": source,
            "proposed_at": _now_utc(),
        }
    )
    _save_pending(entries, pending_path)
    return slug


def get_pending(pending_path: Path = PENDING_PATH) -> list[dict[str, Any]]:
    """Return all pending wiki entries awaiting CEO approval."""
    return _load_pending(pending_path)


def get_pending_entry(slug: str, pending_path: Path = PENDING_PATH) -> dict[str, Any] | None:
    """Return a specific pending entry by slug, or None."""
    for entry in _load_pending(pending_path):
        if entry.get("slug") == slug:
            return entry
    return None


# ── approve (CEO approves → written to wiki.md) ───────────────────────────────


def approve_entry(
    slug: str,
    wiki_path: Path = WIKI_PATH,
    pending_path: Path = PENDING_PATH,
) -> bool:
    """Write approved entry to wiki.md and remove from pending. Returns True if found."""
    entries = _load_pending(pending_path)
    target = next((e for e in entries if e.get("slug") == slug), None)
    if target is None:
        return False

    # Write to wiki
    wiki_path.parent.mkdir(parents=True, exist_ok=True)
    approved_at = _now_utc()[:10]  # date only for readability
    entry_md = (
        f"\n## {target['title']}\n"
        f"*Added {approved_at} · source: {target.get('source', '?')}*\n\n"
        f"{target['body']}\n"
    )

    if not wiki_path.exists():
        wiki_path.write_text(
            "# AI Holding Company — Institutional Memory\n\n"
            "> Agent-observed heuristics, curated and approved by CEO.\n"
            "> Read by the brief composer each cycle as additional context.\n"
            + entry_md,
            encoding="utf-8",
        )
    else:
        with wiki_path.open("a", encoding="utf-8") as f:
            f.write(entry_md)

    # Remove from pending
    remaining = [e for e in entries if e.get("slug") != slug]
    _save_pending(remaining, pending_path)
    return True


def reject_entry(slug: str, pending_path: Path = PENDING_PATH) -> bool:
    """Remove a pending entry without writing it. Returns True if found."""
    entries = _load_pending(pending_path)
    before = len(entries)
    entries = [e for e in entries if e.get("slug") != slug]
    if len(entries) == before:
        return False
    _save_pending(entries, pending_path)
    return True


# ── read (brief composer uses this) ───────────────────────────────────────────


def read_wiki(wiki_path: Path = WIKI_PATH) -> str:
    """Return wiki contents as a string, or empty string if no wiki yet."""
    if not wiki_path.exists():
        return ""
    try:
        return wiki_path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def format_pending_for_telegram(entry: dict[str, Any]) -> str:
    """Format a pending wiki entry for CEO review via Telegram."""
    slug = entry.get("slug", "?")
    title = entry.get("title", "?")
    body = entry.get("body", "")
    proposed = str(entry.get("proposed_at", ""))[:10]
    preview = body[:300] + ("…" if len(body) > 300 else "")
    return (
        f"📖 Wiki entry proposed ({proposed})\n"
        f"Title: {title}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{preview}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"→ /approve_wiki_{slug}  to add to institutional memory\n"
        f"→ /reject_wiki_{slug}   to discard"
    )

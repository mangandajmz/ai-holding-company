"""Semantic memory initialization - Stage I startup."""

from __future__ import annotations

from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def initialize_semantic_memory(config: dict[str, Any]) -> dict[str, Any]:
    """Initialize local semantic memory and index core project documents."""
    try:
        from local_vector_memory import LocalVectorMemory  # pylint: disable=import-outside-toplevel
    except Exception:  # noqa: BLE001
        return {"ok": False, "message": "LocalVectorMemory not available"}

    memory_cfg = config.get("memory", {})
    memory_cfg = memory_cfg if isinstance(memory_cfg, dict) else {}

    memory_dir = ROOT / str(config.get("paths", {}).get("memory_dir", "memory"))
    memory_dir.mkdir(parents=True, exist_ok=True)
    vector_store_path = memory_dir / "vector_store.jsonl"

    store = LocalVectorMemory(
        data_path=vector_store_path,
        ollama_base_url=str(memory_cfg.get("ollama_base_url", "http://127.0.0.1:11434")),
        embedding_model=str(memory_cfg.get("embedding_model", "nomic-embed-text")),
    )

    indexed_count = 0

    plan_path = ROOT / "PLAN.md"
    if plan_path.exists():
        plan_text = plan_path.read_text(encoding="utf-8", errors="replace")
        store.add(text=plan_text[:2000], metadata={"type": "system_plan", "source": "PLAN.md"})
        indexed_count += 1

    soul_path = ROOT / "SOUL.md"
    if soul_path.exists():
        soul_text = soul_path.read_text(encoding="utf-8", errors="replace")
        store.add(text=soul_text, metadata={"type": "company_identity", "source": "SOUL.md"})
        indexed_count += 1

    return {
        "ok": True,
        "vector_store_path": str(vector_store_path),
        "indexed_documents": indexed_count,
        "model": str(memory_cfg.get("embedding_model", "nomic-embed-text")),
        "ready": indexed_count > 0,
        "message": f"Semantic memory initialized with {indexed_count} documents",
    }


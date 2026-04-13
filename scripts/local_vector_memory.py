"""Minimal local vector memory backed by JSONL and Ollama embeddings."""

from __future__ import annotations

import argparse
import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request

from utils import now_utc_iso as utc_now_iso


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    a_norm = math.sqrt(sum(x * x for x in a))
    b_norm = math.sqrt(sum(y * y for y in b))
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return dot / (a_norm * b_norm)


@dataclass
class MemoryItem:
    item_id: str
    timestamp_utc: str
    text: str
    metadata: dict[str, Any]
    embedding: list[float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "timestamp_utc": self.timestamp_utc,
            "text": self.text,
            "metadata": self.metadata,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MemoryItem":
        return cls(
            item_id=str(value.get("item_id", "")),
            timestamp_utc=str(value.get("timestamp_utc", "")),
            text=str(value.get("text", "")),
            metadata=dict(value.get("metadata", {})),
            embedding=list(value.get("embedding", [])),
        )


class LocalVectorMemory:
    def __init__(
        self,
        data_path: Path,
        ollama_base_url: str = "http://127.0.0.1:11434",
        embedding_model: str = "nomic-embed-text",
    ) -> None:
        self.data_path = data_path
        self.ollama_base_url = ollama_base_url.rstrip("/")
        self.embedding_model = embedding_model
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self.data_path.touch(exist_ok=True)

    def _embed(self, text: str) -> list[float]:
        body = json.dumps({"model": self.embedding_model, "prompt": text}).encode("utf-8")
        req = request.Request(
            url=f"{self.ollama_base_url}/api/embeddings",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            embedding = payload.get("embedding")
            if isinstance(embedding, list):
                return [float(x) for x in embedding]
            return []
        except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            return []

    def add(self, text: str, metadata: dict[str, Any] | None = None) -> MemoryItem:
        item = MemoryItem(
            item_id=str(uuid.uuid4()),
            timestamp_utc=utc_now_iso(),
            text=text.strip(),
            metadata=metadata or {},
            embedding=self._embed(text.strip()),
        )
        with self.data_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item.to_dict(), ensure_ascii=True) + "\n")
        return item

    def all_items(self) -> list[MemoryItem]:
        items: list[MemoryItem] = []
        with self.data_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                stripped = raw_line.strip()
                if not stripped:
                    continue
                try:
                    items.append(MemoryItem.from_dict(json.loads(stripped)))
                except (ValueError, json.JSONDecodeError, TypeError):
                    continue
        return items

    def search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        query_embedding = self._embed(query)
        query_tokens = {t for t in query.lower().split() if t}
        ranked: list[tuple[float, MemoryItem]] = []

        for item in self.all_items():
            semantic = _cosine_similarity(query_embedding, item.embedding) if query_embedding else 0.0
            lexical = 0.0
            item_tokens = {t for t in item.text.lower().split() if t}
            if query_tokens and item_tokens:
                lexical = len(query_tokens.intersection(item_tokens)) / len(query_tokens)
            score = (0.85 * semantic) + (0.15 * lexical)
            ranked.append((score, item))

        ranked.sort(key=lambda pair: pair[0], reverse=True)
        return [
            {
                "score": round(score, 5),
                "item_id": item.item_id,
                "timestamp_utc": item.timestamp_utc,
                "text": item.text,
                "metadata": item.metadata,
            }
            for score, item in ranked[: max(1, top_k)]
            if score > 0.0
        ]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local vector memory helper.")
    parser.add_argument(
        "--data-path",
        default=str(Path(__file__).resolve().parents[1] / "memory" / "vector_store.jsonl"),
        help="JSONL file for vector memory entries.",
    )
    parser.add_argument(
        "--embedding-model",
        default="nomic-embed-text",
        help="Ollama embedding model.",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:11434", help="Ollama API base URL.")
    sub = parser.add_subparsers(dest="command", required=True)

    add_cmd = sub.add_parser("add", help="Add a memory item.")
    add_cmd.add_argument("--text", required=True, help="Memory text.")
    add_cmd.add_argument("--metadata", default="{}", help="JSON metadata object.")

    find_cmd = sub.add_parser("search", help="Search memory items.")
    find_cmd.add_argument("--query", required=True, help="Search query.")
    find_cmd.add_argument("--top-k", type=int, default=5, help="Top K matches.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    memory = LocalVectorMemory(
        data_path=Path(args.data_path),
        ollama_base_url=args.base_url,
        embedding_model=args.embedding_model,
    )

    if args.command == "add":
        try:
            metadata = json.loads(args.metadata)
            if not isinstance(metadata, dict):
                metadata = {}
        except json.JSONDecodeError:
            metadata = {}
        item = memory.add(text=args.text, metadata=metadata)
        print(json.dumps(item.to_dict(), indent=2))
        return

    if args.command == "search":
        results = memory.search(query=args.query, top_k=args.top_k)
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

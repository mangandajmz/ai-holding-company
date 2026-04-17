"""search_tool.py — DuckDuckGo web search tool for CrewAI using duckduckgo_search."""

import json
from crewai.tools import tool
from duckduckgo_search import DDGS


@tool("DuckDuckGo Web Search")
def duckduckgo_search(query: str) -> str:
    """
    Search the web using DuckDuckGo. Returns the top results for the query,
    each with title, URL, and a brief snippet.

    Args:
        query: The search query string.

    Returns:
        JSON string with a list of result objects (title, url, snippet).
    """
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=8))
        results = [
            {
                "title": r.get("title", ""),
                "url": r.get("href", ""),
                "snippet": r.get("body", "")[:300],
            }
            for r in raw
        ]
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, indent=2)

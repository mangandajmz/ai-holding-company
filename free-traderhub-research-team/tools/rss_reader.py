"""rss_reader.py — Parse configured RSS feeds with feedparser."""

import json
import feedparser
from crewai.tools import tool
from config import RSS_FEEDS

_MAX_ARTICLES_PER_FEED = 5
_SUMMARY_MAX_CHARS = 300


@tool("Get Finance Headlines")
def get_finance_headlines(placeholder: str = "") -> str:
    """
    Parse all configured RSS feeds and return the latest finance headlines.

    Returns up to 5 articles per feed, each containing:
    - source: feed title or domain
    - title: article headline
    - summary: first 300 characters of article summary
    - published: publication date string
    - link: article URL

    Returns:
        JSON string with a list of article objects across all configured feeds.
    """
    all_articles = []

    for feed_url in RSS_FEEDS:
        try:
            parsed = feedparser.parse(feed_url)
            feed_title = parsed.feed.get("title", feed_url.split("/")[2])

            entries = parsed.entries[:_MAX_ARTICLES_PER_FEED]
            for entry in entries:
                summary = entry.get("summary") or entry.get("description") or ""
                summary = summary[:_SUMMARY_MAX_CHARS]

                published = (
                    entry.get("published")
                    or entry.get("updated")
                    or "Unknown"
                )

                all_articles.append(
                    {
                        "source": feed_title,
                        "title": entry.get("title", ""),
                        "summary": summary,
                        "published": published,
                        "link": entry.get("link", ""),
                    }
                )
        except Exception as exc:
            all_articles.append(
                {
                    "source": feed_url,
                    "error": str(exc),
                    "title": "",
                    "summary": "",
                    "published": "",
                    "link": "",
                }
            )

    result = {
        "feeds_parsed": len(RSS_FEEDS),
        "articles_retrieved": len([a for a in all_articles if "error" not in a]),
        "articles": all_articles,
    }
    return json.dumps(result, ensure_ascii=False, indent=2)

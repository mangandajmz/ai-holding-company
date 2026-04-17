"""reddit_reader.py — Reddit public JSON API tools (no authentication required)."""

import json
import requests
from crewai.tools import tool
from config import SUBREDDITS, REDDIT_POST_LIMIT

_HEADERS = {"User-Agent": "FreeTraderHub-ResearchBot/1.0"}


def _fetch_subreddit(subreddit: str, limit: int = REDDIT_POST_LIMIT) -> list[dict]:
    """Fetch hot posts from a single subreddit via the public JSON API."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        response = requests.get(url, headers=_HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        return [{"error": str(exc), "subreddit": subreddit}]
    except json.JSONDecodeError:
        return [{"error": "Invalid JSON response", "subreddit": subreddit}]

    posts = []
    for child in data.get("data", {}).get("children", []):
        post = child.get("data", {})
        if post.get("stickied"):
            continue
        selftext = (post.get("selftext") or "").strip()
        posts.append(
            {
                "subreddit": subreddit,
                "title": post.get("title", ""),
                "score": post.get("score", 0),
                "comments": post.get("num_comments", 0),
                "url": post.get("url", ""),
                "flair": post.get("link_flair_text") or "",
                "selftext_preview": selftext[:400],
            }
        )
    return posts


@tool("Get Reddit Hot Posts")
def get_reddit_hot_posts(subreddit: str) -> str:
    """
    Fetch the current hot posts from a single subreddit using the Reddit
    public JSON API (no authentication required).

    Args:
        subreddit: Name of the subreddit to fetch (without r/ prefix).

    Returns:
        JSON string containing a list of post objects with title, score,
        comments, url, flair, and a preview of the post body.
    """
    posts = _fetch_subreddit(subreddit)
    return json.dumps(posts, ensure_ascii=False, indent=2)


@tool("Scan All Subreddits")
def scan_all_subreddits(placeholder: str = "") -> str:
    """
    Loop over all configured subreddits and return combined hot post results.

    Returns:
        JSON string with a dict keyed by subreddit name, each value being a
        list of post objects.
    """
    results: dict[str, list] = {}
    for sub in SUBREDDITS:
        results[sub] = _fetch_subreddit(sub)

    summary = {
        "subreddits_scanned": list(results.keys()),
        "total_posts": sum(len(v) for v in results.values()),
        "data": results,
    }
    return json.dumps(summary, ensure_ascii=False, indent=2)

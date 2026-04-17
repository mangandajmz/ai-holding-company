# config.py — FreeTraderHub Research Team Configuration

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
AVAILABLE_MODELS = {
    "llama3.2": "ollama/llama3.2:latest",
    "llama3.1": "ollama/llama3.1:8b",
}

MODEL = "ollama/llama3.2:latest"   # Change to "ollama/llama3.1:8b" for the smaller model
BASE_URL = "http://localhost:11434"

# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------
SITE_NAME = "FreeTraderHub"
SITE_URL = "https://freetraderhub.com"
SITE_DESCRIPTION = (
    "FreeTraderHub offers free forex and crypto calculators: "
    "Lot Size, Pip Value, Position Size, Risk/Reward, Compounding, Drawdown."
)
CALCULATORS = [
    "Lot Size",
    "Pip Value",
    "Position Size",
    "Risk/Reward",
    "Compounding",
    "Drawdown",
]

# ---------------------------------------------------------------------------
# Reddit
# ---------------------------------------------------------------------------
SUBREDDITS = ["Forex", "Daytrading", "Trading", "algotrading", "Stocks"]
REDDIT_POST_LIMIT = 25

# ---------------------------------------------------------------------------
# RSS Feeds
# ---------------------------------------------------------------------------
RSS_FEEDS = [
    "https://www.financemagnates.com/feed/",
    "https://www.fxempire.com/api/v1/en/articles/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
]

# ---------------------------------------------------------------------------
# Competitors
# ---------------------------------------------------------------------------
COMPETITORS = [
    "babypips.com/tools",
    "myfxbook.com/forex-calculators",
    "forexprofitcalculator.net",
]

# ---------------------------------------------------------------------------
# Compliance
# ---------------------------------------------------------------------------
DISCLAIMER = (
    "DISCLAIMER: This content is for educational purposes only and does not "
    "constitute financial advice. Trading forex, crypto, or any financial "
    "instrument involves significant risk of loss and may not be suitable for "
    "all investors. Past performance is not indicative of future results. "
    "Always consult a qualified financial professional before making any "
    "investment or trading decisions. FreeTraderHub is not a regulated "
    "financial entity and does not provide investment advice."
)

FORBIDDEN_PHRASES = [
    "will make you money",
    "guaranteed",
    "always profitable",
    "buy now",
    "sell now",
    "expected return",
    "you should trade",
    "I recommend buying",
    "risk-free",
    "certain profit",
    "never lose",
    "cant lose",
    "can't lose",
    "100% accurate",
]

# ---------------------------------------------------------------------------
# Quality Gates (minimums the Team Lead enforces)
# ---------------------------------------------------------------------------
MIN_RESEARCH_WORDS = 300
MIN_REDDIT_POSTS = 5
MIN_BLOG_WORDS = 700

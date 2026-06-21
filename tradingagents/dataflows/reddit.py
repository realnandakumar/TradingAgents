"""Reddit search fetcher for ticker-specific discussion posts.

Uses Reddit's public JSON endpoints (``reddit.com/r/{sub}/search.json``)
which do not require an API key. Public throughput is ~10 requests per
minute per IP, well within budget for a single agent run that queries
a handful of finance subreddits per ticker.

Returns formatted plaintext blocks ready for prompt injection. Degrades
gracefully — returns a placeholder string rather than raising, so callers
never have to special-case missing data.
"""

from __future__ import annotations

from datetime import datetime
import html
import json
import logging
import re
import time
from typing import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from tradingagents.dataflows.tool_response_logging import log_tool_response
from tradingagents.dataflows.utils import ssl_context

logger = logging.getLogger(__name__)

_JSON_API = "https://www.reddit.com/r/{sub}/search.json?{qs}"
_RSS_API = "https://www.reddit.com/r/{sub}/search.rss?{qs}"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "TradingAgents/0.2 (+https://github.com/TauricResearch/TradingAgents)"
)
_ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}

# Subreddits ordered roughly by signal density for ticker-specific discussion.
# The US set preserves the original behavior; India adds local market forums.
MARKET_SUBREDDITS = {
    "us": ("wallstreetbets", "stocks", "investing"),
    "india": ("IndianStreetBets", "IndiaInvestments", "IndiaStockMarket"),
}
DEFAULT_REDDIT_MARKET = "us"
DEFAULT_SUBREDDITS = MARKET_SUBREDDITS[DEFAULT_REDDIT_MARKET]


def get_subreddits_for_market(market: str | None) -> tuple[str, ...]:
    """Return the subreddit set for a supported market mode."""
    normalized = (market or DEFAULT_REDDIT_MARKET).strip().lower()
    try:
        return MARKET_SUBREDDITS[normalized]
    except KeyError as exc:
        supported = ", ".join(sorted(MARKET_SUBREDDITS))
        raise ValueError(
            f"Unsupported Reddit market {market!r}. Expected one of: {supported}"
        ) from exc


def _configured_subreddits() -> tuple[str, ...]:
    from tradingagents.dataflows.config import get_config

    market = get_config().get("reddit_market", DEFAULT_REDDIT_MARKET)
    return get_subreddits_for_market(market)


def _search_query_for_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    for suffix in (".NS", ".BO"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


def _mention_label(ticker: str) -> str:
    query = _search_query_for_ticker(ticker)
    ticker_label = ticker.upper()
    if query == ticker_label:
        return ticker_label
    return f"{ticker_label} (searched as {query})"


def _fetch_subreddit_json(
    ticker: str,
    sub: str,
    limit: int,
    timeout: float,
) -> list[dict] | None:
    qs = urlencode({
        "q": _search_query_for_ticker(ticker),
        "restrict_sr": "on",
        "sort": "new",
        "t": "week",  # last 7 days
        "limit": limit,
    })
    url = _JSON_API.format(sub=sub, qs=qs)
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            payload = json.loads(resp.read())
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.info("Reddit JSON fetch failed for r/%s · %s: %s", sub, ticker, exc)
        return None
    children = (payload.get("data") or {}).get("children") or []
    return [c.get("data", {}) for c in children if isinstance(c, dict)]


def _html_to_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return re.sub(r"(^|\s+)submitted by\s+/u/\S+.*$", "", text, flags=re.IGNORECASE).strip()


def _parse_atom_timestamp(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _fetch_subreddit_rss(
    ticker: str,
    sub: str,
    limit: int,
    timeout: float,
) -> list[dict]:
    qs = urlencode({
        "q": _search_query_for_ticker(ticker),
        "restrict_sr": "on",
        "sort": "new",
        "t": "week",
        "limit": limit,
    })
    url = _RSS_API.format(sub=sub, qs=qs)
    req = Request(
        url,
        headers={
            "User-Agent": _UA,
            "Accept": "application/atom+xml, application/rss+xml, application/xml",
        },
    )
    try:
        with urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            payload = resp.read()
        root = ElementTree.fromstring(payload)
    except (HTTPError, URLError, ElementTree.ParseError, TimeoutError) as exc:
        logger.warning("Reddit fetch failed for r/%s · %s: %s", sub, ticker, exc)
        return []

    posts = []
    for entry in root.findall("atom:entry", _ATOM_NS):
        title = entry.findtext("atom:title", default="", namespaces=_ATOM_NS).strip()
        content = entry.findtext("atom:content", default="", namespaces=_ATOM_NS)
        published = entry.findtext("atom:published", namespaces=_ATOM_NS)
        updated = entry.findtext("atom:updated", namespaces=_ATOM_NS)
        link = entry.find("atom:link", _ATOM_NS)
        posts.append({
            "title": title,
            "selftext": _html_to_text(content),
            "created_utc": _parse_atom_timestamp(published or updated),
            "permalink": link.get("href") if link is not None else "",
        })
    return posts


def _fetch_subreddit(
    ticker: str,
    sub: str,
    limit: int,
    timeout: float,
) -> list[dict]:
    posts = _fetch_subreddit_json(ticker, sub, limit, timeout)
    if posts:
        return posts
    return _fetch_subreddit_rss(ticker, sub, limit, timeout)


def fetch_reddit_posts(
    ticker: str,
    subreddits: Iterable[str] | None = None,
    limit_per_sub: int = 5,
    timeout: float = 10.0,
    inter_request_delay: float = 0.4,
) -> str:
    """Fetch recent Reddit posts mentioning ``ticker`` across finance
    subreddits and return them as a formatted plaintext block.

    ``inter_request_delay`` keeps us under Reddit's public rate limit
    (~10 req/min per IP) even if the caller queries many subreddits.
    """
    if subreddits is None:
        subreddits = _configured_subreddits()
    else:
        subreddits = tuple(subreddits)

    blocks = []
    total_posts = 0
    mention_label = _mention_label(ticker)
    for i, sub in enumerate(subreddits):
        if i > 0:
            time.sleep(inter_request_delay)
        posts = _fetch_subreddit(ticker, sub, limit_per_sub, timeout)
        total_posts += len(posts)
        if not posts:
            blocks.append(f"r/{sub}: <no posts found mentioning {mention_label} in the past 7 days>")
            continue

        lines = [f"r/{sub} — {len(posts)} recent posts mentioning {mention_label}:"]
        for p in posts:
            title = (p.get("title") or "").replace("\n", " ").strip()
            score = p.get("score")
            comments = p.get("num_comments")
            score_str = f"{score:>4}↑" if isinstance(score, int) else "   ?↑"
            comments_str = f"{comments:>3}c" if isinstance(comments, int) else "  ?c"
            created = p.get("created_utc")
            created_str = (
                time.strftime("%Y-%m-%d", time.gmtime(created)) if created else "?"
            )
            selftext = (p.get("selftext") or "").replace("\n", " ").strip()
            if len(selftext) > 240:
                selftext = selftext[:240] + "…"
            lines.append(
                f"  [{created_str} · {score_str} · {comments_str}] {title}"
                + (f"\n    body excerpt: {selftext}" if selftext else "")
            )
        blocks.append("\n".join(lines))

    log_metadata = {
        "subreddits": list(subreddits),
        "limit_per_sub": limit_per_sub,
        "total_posts": total_posts,
    }
    if total_posts == 0:
        result = (
            f"<no Reddit posts found mentioning {mention_label} across "
            f"{', '.join(f'r/{s}' for s in subreddits)} in the past 7 days>"
        )
        log_tool_response("reddit", result, ticker=ticker, metadata=log_metadata)
        return result
    result = "\n\n".join(blocks)
    log_tool_response("reddit", result, ticker=ticker, metadata=log_metadata)
    return result

"""StockTwits public symbol-stream fetcher.

StockTwits exposes a per-symbol message stream at
``api.stocktwits.com/api/2/streams/symbol/{ticker}.json`` that requires no
API key, no OAuth, and no registration. Each message includes a
user-labeled sentiment field (``Bullish``/``Bearish``/null), the message
body, timestamp, and posting user.

The function is deliberately self-contained: short timeout, graceful
degradation on any HTTP or parse failure, and a string return type so
the calling agent gets a uniform interface regardless of whether the
network call succeeded.
"""

from __future__ import annotations

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from tradingagents.dataflows.tool_response_logging import log_tool_response
from tradingagents.dataflows.utils import ssl_context

logger = logging.getLogger(__name__)

_API = "https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
_UA = "tradingagents/0.2 (+https://github.com/TauricResearch/TradingAgents)"


def normalize_stocktwits_symbol(ticker: str, market: str = "us") -> str:
    """Return the symbol format expected by StockTwits for the configured market."""
    symbol = ticker.strip().upper().lstrip("$")
    if market.strip().lower() == "india":
        if symbol.endswith(".NS"):
            return symbol[:-3] + ".NSE"
        if symbol.endswith(".BO"):
            return symbol[:-3] + ".BSE"
    return symbol


def fetch_stocktwits_messages(
    ticker: str,
    limit: int = 30,
    timeout: float = 10.0,
    market: str = "us",
) -> str:
    """Fetch recent StockTwits messages for ``ticker`` and return them as a
    formatted plaintext block ready for prompt injection.

    Returns a placeholder string when the endpoint is unreachable, the
    symbol has no messages, or the response shape is unexpected — the
    caller never has to special-case None or exceptions.
    """
    stocktwits_symbol = normalize_stocktwits_symbol(ticker, market=market)
    log_metadata = {
        "market": market,
        "limit": limit,
        "lookup_symbol": stocktwits_symbol,
    }
    url = _API.format(ticker=stocktwits_symbol)
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout, context=ssl_context()) as resp:
            data = json.loads(resp.read())
    except (HTTPError, URLError, json.JSONDecodeError, TimeoutError) as exc:
        logger.warning(
            "StockTwits fetch failed for %s (lookup symbol %s): %s",
            ticker,
            stocktwits_symbol,
            exc,
        )
        result = f"<stocktwits unavailable: {type(exc).__name__}>"
        log_tool_response("stocktwits", result, ticker=ticker, metadata=log_metadata)
        return result

    messages = data.get("messages", []) if isinstance(data, dict) else []
    if not messages:
        result = f"<no StockTwits messages found for ${stocktwits_symbol}>"
        log_tool_response("stocktwits", result, ticker=ticker, metadata=log_metadata)
        return result

    lines = []
    bullish = bearish = unlabeled = 0
    for m in messages[:limit]:
        created = m.get("created_at", "")
        user = (m.get("user") or {}).get("username", "?")
        entities = m.get("entities") or {}
        sentiment_obj = entities.get("sentiment") or {}
        sentiment = sentiment_obj.get("basic") if isinstance(sentiment_obj, dict) else None
        body = (m.get("body") or "").replace("\n", " ").strip()
        if len(body) > 280:
            body = body[:280] + "…"

        if sentiment == "Bullish":
            bullish += 1
            tag = "Bullish"
        elif sentiment == "Bearish":
            bearish += 1
            tag = "Bearish"
        else:
            unlabeled += 1
            tag = "no-label"
        lines.append(f"[{created} · @{user} · {tag}] {body}")

    total = bullish + bearish + unlabeled
    bull_pct = round(100 * bullish / total) if total else 0
    bear_pct = round(100 * bearish / total) if total else 0
    summary = (
        f"Bullish: {bullish} ({bull_pct}%) · "
        f"Bearish: {bearish} ({bear_pct}%) · "
        f"Unlabeled: {unlabeled} · "
        f"Total: {total} most-recent messages"
    )
    result = summary + "\n\n" + "\n".join(lines)
    log_tool_response(
        "stocktwits",
        result,
        ticker=ticker,
        metadata={**log_metadata, "message_count": total},
    )
    return result

from __future__ import annotations

import json
from urllib.error import HTTPError

from tradingagents.dataflows import stocktwits


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_normalize_stocktwits_symbol_maps_ns_only_in_india_mode():
    assert (
        stocktwits.normalize_stocktwits_symbol("RELIANCE.NS", market="india")
        == "RELIANCE.NSE"
    )
    assert stocktwits.normalize_stocktwits_symbol("tcs.ns", market="INDIA") == "TCS.NSE"
    assert stocktwits.normalize_stocktwits_symbol("RELIANCE.NS", market="us") == "RELIANCE.NS"


def test_normalize_stocktwits_symbol_maps_bo_only_in_india_mode():
    assert (
        stocktwits.normalize_stocktwits_symbol("RELIANCE.BO", market="india")
        == "RELIANCE.BSE"
    )
    assert stocktwits.normalize_stocktwits_symbol("tcs.bo", market="INDIA") == "TCS.BSE"
    assert stocktwits.normalize_stocktwits_symbol("RELIANCE.BO", market="us") == "RELIANCE.BO"


def test_normalize_stocktwits_symbol_preserves_us_symbols():
    assert stocktwits.normalize_stocktwits_symbol("AAPL", market="india") == "AAPL"
    assert stocktwits.normalize_stocktwits_symbol("$SPY", market="us") == "SPY"


def test_fetch_stocktwits_messages_uses_normalized_india_symbol(monkeypatch):
    seen_urls = []

    def fake_urlopen(req, timeout, context=None):
        seen_urls.append(req.full_url)
        return _FakeResponse(
            {
                "messages": [
                    {
                        "created_at": "2026-05-30T00:00:00Z",
                        "user": {"username": "tester"},
                        "entities": {"sentiment": {"basic": "Bullish"}},
                        "body": "$TCS.NSE looks constructive",
                    }
                ]
            }
        )

    monkeypatch.setattr(stocktwits, "urlopen", fake_urlopen)

    output = stocktwits.fetch_stocktwits_messages("TCS.NS", market="india")

    assert seen_urls == ["https://api.stocktwits.com/api/2/streams/symbol/TCS.NSE.json"]
    assert "Bullish: 1 (100%)" in output
    assert "$TCS.NSE looks constructive" in output


def test_fetch_stocktwits_messages_leaves_ns_symbol_unchanged_in_us_mode(monkeypatch):
    seen_urls = []

    def fake_urlopen(req, timeout, context=None):
        seen_urls.append(req.full_url)
        return _FakeResponse({"messages": []})

    monkeypatch.setattr(stocktwits, "urlopen", fake_urlopen)

    output = stocktwits.fetch_stocktwits_messages("TCS.NS", market="us")

    assert seen_urls == ["https://api.stocktwits.com/api/2/streams/symbol/TCS.NS.json"]
    assert output == "<no StockTwits messages found for $TCS.NS>"


def test_fetch_stocktwits_messages_returns_placeholder_on_http_error(monkeypatch):
    seen_urls = []

    def fake_urlopen(req, timeout, context=None):
        seen_urls.append(req.full_url)
        raise HTTPError(req.full_url, 404, "Not Found", hdrs=None, fp=None)

    monkeypatch.setattr(stocktwits, "urlopen", fake_urlopen)

    output = stocktwits.fetch_stocktwits_messages("RELIANCE.NS", market="india")

    assert seen_urls == ["https://api.stocktwits.com/api/2/streams/symbol/RELIANCE.NSE.json"]
    assert output == "<stocktwits unavailable: HTTPError>"

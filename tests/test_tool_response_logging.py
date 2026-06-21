from __future__ import annotations

import copy
import json

import pytest

from tradingagents.dataflows import reddit, stocktwits, tool_response_logging
from tradingagents.dataflows.config import set_config
from tradingagents.dataflows.tool_response_logging import (
    _LOG_FILENAME,
    log_tool_response,
)
from tradingagents.default_config import DEFAULT_CONFIG


@pytest.fixture()
def log_dir(tmp_path):
    """Point tool_response_log_dir at a temp dir and restore config after."""
    target = tmp_path / "tool_responses"
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["tool_response_log_dir"] = str(target)
    set_config(config)
    try:
        yield target
    finally:
        set_config(copy.deepcopy(DEFAULT_CONFIG))


def _read_log(log_dir):
    return (log_dir / _LOG_FILENAME).read_text(encoding="utf-8")


def test_log_tool_response_writes_full_text_and_metadata(log_dir):
    log_tool_response(
        "stocktwits",
        "full response body line 1\nline 2",
        ticker="AAPL",
        metadata={"market": "us", "limit": 30},
    )

    contents = _read_log(log_dir)
    assert "===== TOOL RESPONSE START =====" in contents
    assert "===== TOOL RESPONSE END =====" in contents
    assert "source: stocktwits" in contents
    assert "ticker: AAPL" in contents
    assert '"market": "us"' in contents
    assert "full response body line 1\nline 2" in contents


def test_log_tool_response_appends_multiple_entries(log_dir):
    log_tool_response("reddit", "first", ticker="AAPL")
    log_tool_response("reddit", "second", ticker="AAPL")

    contents = _read_log(log_dir)
    assert contents.count("===== TOOL RESPONSE START =====") == 2
    assert "first" in contents
    assert "second" in contents


def test_log_tool_response_noop_when_unconfigured(tmp_path):
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["tool_response_log_dir"] = None
    set_config(config)
    try:
        # Should not raise and should not create any file.
        log_tool_response("stocktwits", "body", ticker="AAPL")
    finally:
        set_config(copy.deepcopy(DEFAULT_CONFIG))

    assert not (tmp_path / _LOG_FILENAME).exists()


def test_log_tool_response_noop_when_disabled(tmp_path):
    log_dir = tmp_path / "tool_responses"
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["tool_response_log_dir"] = str(log_dir)
    config["tool_response_logging_enabled"] = False
    set_config(config)
    try:
        log_tool_response("stocktwits", "body", ticker="AAPL")
    finally:
        set_config(copy.deepcopy(DEFAULT_CONFIG))

    assert not (log_dir / _LOG_FILENAME).exists()


def test_log_tool_response_never_raises_on_bad_metadata(log_dir):
    class Unserializable:
        pass

    # default=str in json.dumps keeps this from raising; the call must succeed.
    log_tool_response(
        "technical_indicators",
        "body",
        ticker="AAPL",
        metadata={"obj": Unserializable()},
    )

    assert (log_dir / _LOG_FILENAME).exists()


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return json.dumps(self._payload).encode("utf-8")


def test_stocktwits_fetch_logs_response(monkeypatch, log_dir):
    def fake_urlopen(req, timeout, context=None):
        return _FakeResponse(
            {
                "messages": [
                    {
                        "created_at": "2026-05-30T00:00:00Z",
                        "user": {"username": "tester"},
                        "entities": {"sentiment": {"basic": "Bullish"}},
                        "body": "$AAPL looks strong",
                    }
                ]
            }
        )

    monkeypatch.setattr(stocktwits, "urlopen", fake_urlopen)

    output = stocktwits.fetch_stocktwits_messages("AAPL", market="us")

    contents = _read_log(log_dir)
    assert "source: stocktwits" in contents
    assert output in contents
    assert "$AAPL looks strong" in contents


def test_stocktwits_logs_placeholder_when_no_messages(monkeypatch, log_dir):
    monkeypatch.setattr(
        stocktwits, "urlopen", lambda req, timeout, context=None: _FakeResponse({"messages": []})
    )

    output = stocktwits.fetch_stocktwits_messages("AAPL", market="us")

    assert output.startswith("<no StockTwits messages found")
    assert output in _read_log(log_dir)


def test_reddit_fetch_logs_response(monkeypatch, log_dir):
    def fake_fetch(ticker, sub, limit, timeout):
        return [
            {
                "title": "AAPL breakout incoming",
                "score": 120,
                "num_comments": 45,
                "created_utc": 1748563200,
                "selftext": "some discussion",
            }
        ]

    monkeypatch.setattr(reddit, "_fetch_subreddit", fake_fetch)
    monkeypatch.setattr(reddit.time, "sleep", lambda _: None)

    output = reddit.fetch_reddit_posts("AAPL", subreddits=("stocks",))

    contents = _read_log(log_dir)
    assert "source: reddit" in contents
    assert output in contents
    assert "AAPL breakout incoming" in contents

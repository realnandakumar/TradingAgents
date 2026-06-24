"""Offline unit tests for the dashboard sync layer (no network)."""

from types import SimpleNamespace as NS

import pytest

from tradingagents.sync import (
    SupabaseSync,
    paper_snapshot,
    screen_snapshot,
    sync_results,
)

pytestmark = pytest.mark.unit


def _candidate():
    rs = NS(rs_percentile=100.0, rs_score=0.18, close=4200.0)
    return NS(symbol="LT.NS", rs=rs, composite=2.27,
              fired_signals=["rsi_breakout"], decision_rating="Buy",
              levels={"stoploss": 4000.0, "target": 4600.0,
                      "stop_pct": -4.8, "target_pct": 9.5})


def test_unconfigured_is_noop(monkeypatch):
    # Clear any ambient creds (a developer .env may set these).
    for var in ("SUPABASE_URL", "SUPABASE_SECRET_KEY", "SUPABASE_SERVICE_KEY"):
        monkeypatch.delenv(var, raising=False)
    c = SupabaseSync(url=None, service_key=None)
    assert c.configured is False
    assert c.push("paper", {"x": 1}) is False   # must not raise


def test_configured_flag():
    c = SupabaseSync(url="https://x.supabase.co", service_key="svc")
    assert c.configured is True


def test_screen_snapshot_shape():
    snap = screen_snapshot("2026-06-21", [_candidate()], opened=["LT.NS"])
    assert snap["trade_date"] == "2026-06-21"
    assert snap["opened"] == ["LT.NS"]
    cand = snap["candidates"][0]
    assert cand["rank"] == 1
    assert cand["symbol"] == "LT.NS"
    assert cand["rating"] == "Buy"
    assert cand["opened"] is True
    assert cand["signals"] == ["rsi_breakout"]
    assert cand["stoploss"] == 4000.0
    assert cand["target"] == 4600.0


def test_paper_snapshot_shape():
    book = NS(capital=1_000_000.0,
              positions=[{"ticker": "LT.NS", "status": "open"}],
              stats=lambda: {"overall": {"trades": 0}})
    snap = paper_snapshot(book)
    assert snap["capital"] == 1_000_000.0
    assert len(snap["positions"]) == 1
    assert "stats" in snap and "generated_at" in snap


def test_sync_results_short_circuits_without_creds(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    book = NS(capital=1.0, positions=[], stats=lambda: {})
    assert sync_results({}, "2026-06-21", [_candidate()], [], book) is False


def test_push_inserts_via_rest(monkeypatch):
    """When configured, push() POSTs to the REST endpoint with auth headers."""
    captured = {}

    class FakeResp:
        status_code = 201
        text = ""

    def fake_post(url, headers=None, json=None, timeout=None):
        captured.update(url=url, headers=headers, json=json)
        return FakeResp()

    import tradingagents.sync.supabase_sync as mod
    fake_requests = NS(post=fake_post)
    monkeypatch.setitem(__import__("sys").modules, "requests", fake_requests)

    c = SupabaseSync(url="https://x.supabase.co", service_key="svc", table="snapshots")
    assert c.push("paper", {"a": 1}) is True
    assert captured["url"] == "https://x.supabase.co/rest/v1/snapshots"
    assert captured["headers"]["apikey"] == "svc"
    assert captured["json"] == {"kind": "paper", "data": {"a": 1}}

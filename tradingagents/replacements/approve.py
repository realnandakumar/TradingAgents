"""Approve pending portfolio replacement proposals for strategy desks."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set, Tuple

from tradingagents.default_config import DEFAULT_CONFIG


def parse_ids_option(ids: Optional[str]) -> Optional[Set[str]]:
    if not ids or not ids.strip():
        return None
    return {part.strip() for part in ids.split(",") if part.strip()}


def _pick_map_screener(
    desk_id: str,
    config: dict,
) -> Tuple[object, Dict[str, object]]:
    if desk_id == "swing":
        from tradingagents.screening.swing_screener import screen_swing
        from tradingagents.swing import PortfolioPaperTradeManager

        manager = PortfolioPaperTradeManager(config)
        picks = {p.symbol: p for p in screen_swing(config)}
        return manager, picks

    if desk_id == "momentum":
        from tradingagents.momentum import MomentumPaperTradeManager
        from tradingagents.screening.momentum_screener import screen_momentum

        manager = MomentumPaperTradeManager(config)
        picks = {p.symbol: p for p in screen_momentum(config)}
        return manager, picks

    if desk_id == "nss":
        from tradingagents.nss import NSSPaperTradeManager
        from tradingagents.screening.nss_screener import screen_nss

        manager = NSSPaperTradeManager(config)
        picks = {p.symbol: p for p in screen_nss(config)}
        return manager, picks

    if desk_id == "supertrend-rsi":
        from tradingagents.screening.supertrend_rsi_screener import screen_supertrend_rsi
        from tradingagents.supertrend_rsi import SuperTrendRSIPaperTradeManager

        manager = SuperTrendRSIPaperTradeManager(config)
        picks = {p.symbol: p for p in screen_supertrend_rsi(config) if p.direction == "BUY"}
        return manager, picks

    if desk_id == "trama":
        from tradingagents.screening.trama_screener import screen_trama
        from tradingagents.trama import TramaPaperTradeManager

        manager = TramaPaperTradeManager(config)
        picks = {p.symbol: p for p in screen_trama(config) if p.direction == "BUY"}
        return manager, picks

    if desk_id == "gap-fill":
        from tradingagents.gap_fill import GapFillPaperTradeManager
        from tradingagents.screening.gap_fill_screener import screen_gap_fill

        manager = GapFillPaperTradeManager(config)
        picks = {p.symbol: p for p in screen_gap_fill(config) if p.is_long_candidate}
        return manager, picks

    if desk_id == "nw-envelope":
        from tradingagents.nw_envelope import NwEnvelopePaperTradeManager
        from tradingagents.screening.nw_envelope_screener import screen_nw_envelope

        manager = NwEnvelopePaperTradeManager(config)
        picks = {p.symbol: p for p in screen_nw_envelope(config) if p.direction == "BUY"}
        return manager, picks

    if desk_id == "pattern-forecast":
        from tradingagents.pattern_forecast import PatternForecastPaperTradeManager
        from tradingagents.screening.pattern_forecast_screener import screen_pattern_forecast

        cfg = dict(config)
        cfg["pattern_forecast_directions"] = "UP"
        manager = PatternForecastPaperTradeManager(cfg)
        picks = {p.symbol: p for p in screen_pattern_forecast(cfg) if p.direction == "UP"}
        return manager, picks

    raise ValueError(f"Unknown portfolio desk: {desk_id}")


DESK_ID_BY_APPROVE_COMMAND: Dict[str, str] = {
    "swing-approve": "swing",
    "momentum-approve": "momentum",
    "nss-approve": "nss",
    "supertrend-rsi-approve": "supertrend-rsi",
    "trama-approve": "trama",
    "gap-fill-approve": "gap-fill",
    "nw-envelope-approve": "nw-envelope",
    "pattern-forecast-approve": "pattern-forecast",
}


def approve_portfolio_replacements(
    desk_id: str,
    *,
    yes: bool = False,
    ids: Optional[Set[str]] = None,
    config: Optional[dict] = None,
    confirm: Optional[Callable[[object], bool]] = None,
) -> dict:
    """Approve pending replacement proposals for a strategy desk."""
    cfg = config or DEFAULT_CONFIG.copy()
    manager, picks = _pick_map_screener(desk_id, cfg)
    pending = manager.pending_proposals()
    if not pending:
        return {"approved": 0, "skipped": [], "messages": ["No pending replacement proposals."]}

    approved = 0
    skipped: List[dict] = []
    messages: List[str] = []

    for prop in pending:
        if ids is not None and prop.id not in ids:
            continue
        pick = picks.get(prop.new_ticker)
        if pick is None:
            skipped.append({"id": prop.id, "new_ticker": prop.new_ticker, "reason": "not in screener"})
            messages.append(f"Skip {prop.new_ticker} — not in today's screener.")
            continue

        ok = False
        if yes:
            ok = True
        elif confirm is not None:
            ok = confirm(prop)
        if ok and manager.approve_replacement(prop.id, pick):
            approved += 1
            messages.append(f"Approved: {prop.close_ticker} → {prop.new_ticker}")

    return {"approved": approved, "skipped": skipped, "messages": messages}

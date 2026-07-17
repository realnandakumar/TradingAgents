"""Approve pending portfolio replacement proposals for strategy desks.

Foreclosure is disabled on all paper desks — positions exit via stop/target only.
These helpers clear any stale pending queue and report that the feature is off.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, Set

from tradingagents.default_config import DEFAULT_CONFIG


def parse_ids_option(ids: Optional[str]) -> Optional[Set[str]]:
    if not ids or not ids.strip():
        return None
    return {part.strip() for part in ids.split(",") if part.strip()}


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

_DISABLED_MESSAGE = (
    "Foreclosure is disabled. Positions exit on stop loss or targets only."
)


def _manager_for_desk(desk_id: str, config: dict):
    if desk_id == "swing":
        from tradingagents.swing import PortfolioPaperTradeManager

        return PortfolioPaperTradeManager(config)
    if desk_id == "momentum":
        from tradingagents.momentum import MomentumPaperTradeManager

        return MomentumPaperTradeManager(config)
    if desk_id == "nss":
        from tradingagents.nss import NSSPaperTradeManager

        return NSSPaperTradeManager(config)
    if desk_id == "supertrend-rsi":
        from tradingagents.supertrend_rsi import SuperTrendRSIPaperTradeManager

        return SuperTrendRSIPaperTradeManager(config)
    if desk_id == "trama":
        from tradingagents.trama import TramaPaperTradeManager

        return TramaPaperTradeManager(config)
    if desk_id == "gap-fill":
        from tradingagents.gap_fill import GapFillPaperTradeManager

        return GapFillPaperTradeManager(config)
    if desk_id == "nw-envelope":
        from tradingagents.nw_envelope import NwEnvelopePaperTradeManager

        return NwEnvelopePaperTradeManager(config)
    if desk_id == "pattern-forecast":
        from tradingagents.pattern_forecast import PatternForecastPaperTradeManager

        return PatternForecastPaperTradeManager(config)
    raise ValueError(f"Unknown portfolio desk: {desk_id}")


def approve_portfolio_replacements(
    desk_id: str,
    *,
    yes: bool = False,
    ids: Optional[Set[str]] = None,
    config: Optional[dict] = None,
    confirm: Optional[Callable[[object], bool]] = None,
) -> dict:
    """No-op: foreclosure disabled. Clears any stale pending proposals."""
    _ = (yes, ids, confirm)
    cfg = config or DEFAULT_CONFIG.copy()
    manager = _manager_for_desk(desk_id, cfg)
    pending = manager._load_pending()  # noqa: SLF001 — intentional clear
    cleared = len(pending)
    if pending:
        manager._save_pending([])  # noqa: SLF001
    return {
        "approved": 0,
        "skipped": [],
        "cleared": cleared,
        "messages": [_DISABLED_MESSAGE],
    }

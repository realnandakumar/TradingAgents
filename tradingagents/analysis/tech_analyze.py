"""Quick technical analysis using only the Market Analyst agent."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents import create_market_analyst
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.agent_utils import (
    create_msg_delete,
    get_indicators,
    get_stock_data,
)
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator
from tradingagents.llm_clients import create_llm_client


def _get_provider_kwargs(config: Dict[str, Any]) -> Dict[str, Any]:
    """Get provider-specific kwargs for LLM client creation."""
    kwargs: Dict[str, Any] = {}
    provider = config.get("llm_provider", "").lower()

    if provider == "google":
        thinking_level = config.get("google_thinking_level")
        if thinking_level:
            kwargs["thinking_level"] = thinking_level

    elif provider == "openai":
        reasoning_effort = config.get("openai_reasoning_effort")
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort

    elif provider == "anthropic":
        effort = config.get("anthropic_effort")
        if effort:
            kwargs["effort"] = effort

    return kwargs


def _build_tech_graph(quick_llm, conditional_logic: ConditionalLogic):
    """Build mini LangGraph: Market Analyst → tools_market loop → Msg Clear Market → END."""
    tools_market = ToolNode([get_stock_data, get_indicators])

    workflow = StateGraph(AgentState)
    workflow.add_node("Market Analyst", create_market_analyst(quick_llm))
    workflow.add_node("tools_market", tools_market)
    workflow.add_node("Msg Clear Market", create_msg_delete())

    workflow.add_edge(START, "Market Analyst")
    workflow.add_conditional_edges(
        "Market Analyst",
        conditional_logic.should_continue_market,
        ["tools_market", "Msg Clear Market"],
    )
    workflow.add_edge("tools_market", "Market Analyst")
    workflow.add_edge("Msg Clear Market", END)

    return workflow.compile()


def _prepare_config(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = (config or DEFAULT_CONFIG).copy()
    set_config(cfg)
    os.makedirs(cfg["data_cache_dir"], exist_ok=True)
    return cfg


def run_tech_analyze(
    ticker: str,
    trade_date: str,
    config: Optional[Dict[str, Any]] = None,
    callbacks: Optional[List] = None,
    asset_type: str = "stock",
) -> dict:
    """Run market-only technical analysis for a single ticker."""
    cfg = _prepare_config(config)

    llm_kwargs = _get_provider_kwargs(cfg)
    if callbacks:
        llm_kwargs["callbacks"] = callbacks

    quick_client = create_llm_client(
        provider=cfg["llm_provider"],
        model=cfg["quick_think_llm"],
        base_url=cfg.get("backend_url"),
        **llm_kwargs,
    )
    quick_llm = quick_client.get_llm()

    conditional_logic = ConditionalLogic(
        max_debate_rounds=cfg.get("max_debate_rounds", 1),
        max_risk_discuss_rounds=cfg.get("max_risk_discuss_rounds", 1),
    )
    graph = _build_tech_graph(quick_llm, conditional_logic)

    propagator = Propagator(max_recur_limit=cfg.get("max_recur_limit", 100))
    init_state = propagator.create_initial_state(
        ticker, trade_date, asset_type=asset_type
    )
    args = propagator.get_graph_args(callbacks=callbacks)

    final_state: Dict[str, Any] = {}
    for chunk in graph.stream(init_state, **args):
        final_state.update(chunk)

    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "market_report": final_state.get("market_report", ""),
        "final_state": final_state,
    }


def run_tech_analyze_batch(
    tickers: List[str],
    trade_date: str,
    config: Optional[Dict[str, Any]] = None,
    callbacks: Optional[List] = None,
    asset_type: str = "stock",
) -> List[dict]:
    """Run market-only technical analysis for multiple tickers sequentially."""
    return [
        run_tech_analyze(
            ticker,
            trade_date,
            config=config,
            callbacks=callbacks,
            asset_type=asset_type,
        )
        for ticker in tickers
    ]


def save_tech_report(result: dict, output_dir: Path) -> Path:
    """Save tech-only report: market.md and complete_report.md."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ticker = result["ticker"]
    trade_date = result["trade_date"]
    market_report = result.get("market_report", "")

    (output_dir / "market.md").write_text(market_report, encoding="utf-8")

    header = (
        f"# Technical Analysis Report: {ticker}\n\n"
        f"As of: {trade_date}\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    complete = header + f"## Market Analyst\n\n{market_report}\n"
    report_file = output_dir / "complete_report.md"
    report_file.write_text(complete, encoding="utf-8")
    return report_file

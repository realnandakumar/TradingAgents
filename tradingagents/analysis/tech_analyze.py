"""Quick technical analysis using only the Market Analyst agent."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from tradingagents.agents.analysts.market_analyst_tech import create_tech_market_analyst
from tradingagents.agents.utils.agent_states import AgentState
from tradingagents.agents.utils.agent_utils import (
    create_msg_delete,
    get_indicators,
    get_stock_data,
)
from tradingagents.agents.utils.structured import bind_structured
from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.propagation import Propagator
from tradingagents.llm_clients import create_llm_client
from tradingagents.tech_desk.report_excerpt import (
    ensure_pm_summary_fence,
    extract_pm_summary,
    is_actionable_pm_summary,
    pm_summary_thin_reason,
)
from tradingagents.tech_desk.schemas import PmSummary

logger = logging.getLogger(__name__)


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
    workflow.add_node("Market Analyst", create_tech_market_analyst(quick_llm))
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


_META_PREAMBLE_RE = re.compile(
    r"^(?:now i have (?:all )?(?:the )?(?:data|information)|"
    r"let me (?:now )?(?:analyze|write|compile|prepare)|"
    r"i(?:'ll| will) now (?:analyze|write|compile|prepare)|"
    r"based on (?:the )?(?:data|information) (?:i've |i have )?gathered).*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_market_report_preamble(text: str) -> str:
    """Remove meta narration before the report heading (tech-analyze backup)."""
    if not text:
        return text
    cleaned = _META_PREAMBLE_RE.sub("", text).strip()
    if cleaned.startswith("#"):
        return cleaned
    for i, line in enumerate(cleaned.splitlines()):
        if line.strip().startswith("#"):
            return "\n".join(cleaned.splitlines()[i:]).strip()
    return cleaned


def _pm_summary_from_structured(result: Any) -> Optional[Dict[str, Any]]:
    if isinstance(result, PmSummary):
        return result.as_dict()
    if isinstance(result, dict):
        inner = result.get("pm_summary", result)
        if isinstance(inner, dict):
            try:
                return PmSummary.model_validate(inner).as_dict()
            except Exception:
                return inner
    return None


def fill_pm_summary_from_report(
    llm: Any,
    market_report: str,
    *,
    ticker: str = "",
) -> Optional[Dict[str, Any]]:
    """Second-pass structured extract/fill of PmSummary from free-form MA markdown."""
    if not market_report or not str(market_report).strip():
        return None

    structured_llm = bind_structured(llm, PmSummary, "Tech MA PmSummary")
    prompt = f"""Extract a complete PM summary for {ticker or 'this ticker'} from the
technical report below. Use ONLY levels stated or clearly implied in the report
(entry/pullback zone, stop, targets, SMAs, ATR). Do not invent unrelated prices.

Rules:
- proposal: exactly BUY, HOLD, WAIT, or SELL (uppercase)
- For BUY / WAIT / HOLD setups: stop, target_1, entry_zone_low, and entry_zone_high
  must be real non-zero prices from the report (zone_high > zone_low)
- stop must sit below the entry zone; target_1 above it
- Use 0 for a field only when the report truly has no such level
- confidence: integer 0-100 reflecting the report's conviction

Technical report:
---
{market_report[-12000:]}
---
"""
    if structured_llm is not None:
        try:
            result = structured_llm.invoke(prompt)
            parsed = _pm_summary_from_structured(result)
            if parsed:
                return parsed
        except Exception as exc:
            logger.warning(
                "Tech MA PmSummary structured fill failed for %s (%s); trying free-text JSON",
                ticker or "?",
                exc,
            )

    try:
        response = llm.invoke(
            prompt
            + "\nRespond with ONLY a JSON object matching the PmSummary fields "
            "(proposal, bias, confidence, entry_zone_low, entry_zone_high, stop, "
            "target_1, target_2, atr, sma_50, sma_200, key_support, key_resistance, "
            "invalidation). No markdown fence."
        )
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in content
            )
        text = str(content or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        return _pm_summary_from_structured(data)
    except Exception as exc:
        logger.warning(
            "Tech MA PmSummary free-text fill failed for %s (%s)",
            ticker or "?",
            exc,
        )
        return None


def enforce_pm_summary(
    market_report: str,
    *,
    llm: Any = None,
    ticker: str = "",
) -> tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """Ensure report has an actionable pm_summary fence when possible.

    Returns ``(market_report, summary, thin_reason)``.
    """
    summary = extract_pm_summary(market_report)
    thin = pm_summary_thin_reason(summary)

    if thin and llm is not None:
        filled = fill_pm_summary_from_report(llm, market_report, ticker=ticker)
        if filled and is_actionable_pm_summary(filled):
            summary = filled
            thin = None
        elif filled and summary:
            # Prefer filled numeric fields even if still incomplete
            merged = {**summary, **{k: v for k, v in filled.items() if v not in (None, "", 0, 0.0)}}
            if is_actionable_pm_summary(merged):
                summary = merged
                thin = None
            elif filled:
                summary = filled
                thin = pm_summary_thin_reason(summary)
        elif filled:
            summary = filled
            thin = pm_summary_thin_reason(summary)

    if summary and is_actionable_pm_summary(summary):
        market_report = ensure_pm_summary_fence(market_report, summary)
        return market_report, summary, None

    if summary:
        market_report = ensure_pm_summary_fence(market_report, summary)
    return market_report, summary, thin or pm_summary_thin_reason(summary)


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

    market_report = strip_market_report_preamble(final_state.get("market_report", ""))
    market_report, pm_summary, thin_reason = enforce_pm_summary(
        market_report,
        llm=quick_llm,
        ticker=ticker,
    )
    if thin_reason:
        logger.warning(
            "tech-analyze %s: pm_summary still thin after enforce (%s)",
            ticker,
            thin_reason,
        )

    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "market_report": market_report,
        "pm_summary": pm_summary,
        "pm_summary_thin_reason": thin_reason,
        "final_state": {**final_state, "market_report": market_report},
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
    """Save tech-only report: market.md, pm_summary.json, and complete_report.md."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ticker = result["ticker"]
    trade_date = result["trade_date"]
    market_report = result.get("market_report", "")

    summary = result.get("pm_summary")
    if summary is None:
        summary = extract_pm_summary(market_report)
    if summary and not result.get("pm_summary"):
        # Keep fence aligned when caller only passed markdown
        market_report = ensure_pm_summary_fence(market_report, summary)

    (output_dir / "market.md").write_text(market_report, encoding="utf-8")

    if summary:
        (output_dir / "pm_summary.json").write_text(
            json.dumps({"pm_summary": summary}, indent=2),
            encoding="utf-8",
        )

    header = (
        f"# Technical Analysis Report: {ticker}\n\n"
        f"As of: {trade_date}\n"
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    complete = header + f"## Market Analyst\n\n{market_report}\n"
    report_file = output_dir / "complete_report.md"
    report_file.write_text(complete, encoding="utf-8")
    return report_file

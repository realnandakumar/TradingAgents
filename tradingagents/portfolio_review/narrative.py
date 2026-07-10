"""Single-shot LLM narrative grounded on portfolio facts."""

from __future__ import annotations

import json

from tradingagents.portfolio_review.grounding import build_grounding_sheet

SYSTEM_PROMPT = """You are a hedge fund portfolio manager writing an internal desk memo.

STRICT RULES (zero hallucination):
1. Use ONLY numbers from the GROUNDING SHEET and TABLES below — copy integers exactly.
2. Do NOT create markdown tables in your response (tables are appended separately).
3. Do NOT compute new percentages (e.g. portfolio return on capital) unless listed in GROUNDING SHEET.
4. If a metric is missing, write "data not available".
5. Do not mention news, macro, or fundamentals unless in signal_summary.
6. Cite positions as [desk:ticker] e.g. [swing:MAPMYINDIA.NS].
7. Action items: prefix with "Consider:" only — suggestions, not orders.
8. Keep prose concise: ~500-700 words. No duplicate desk summary tables.

OUTPUT FORMAT (markdown headings only):
## Executive summary
## P&L attribution
## Risk review
## Desk notes
## Action items
"""

USER_PROMPT_TEMPLATE = """Write the portfolio manager memo for as-of {as_of_date}.

GROUNDING SHEET (copy these numbers exactly when cited):
{grounding_sheet}

COMPACT FACTS JSON:
```json
{facts_json}
```

PRE-RENDERED TABLES (authoritative for all figures — do not recreate):
{tables}

Write descriptive commentary plus actionable suggestions from risk_flags and open positions.
"""


def _compact_facts(facts: dict) -> dict:
    """Trim facts for token efficiency while keeping price/P&L fields."""
    return {
        "as_of_date": facts["as_of_date"],
        "summary": facts["summary"],
        "desks": facts["desks"],
        "top_contributors": facts["top_contributors"],
        "top_detractors": facts["top_detractors"],
        "risk_flags": facts["risk_flags"],
        "positions": [
            {
                "id": p["id"],
                "desk": p["desk"],
                "ticker": p["ticker"],
                "symbol": p["symbol"],
                "status": p["status"],
                "entry_price": p.get("entry_price"),
                "current_price": p.get("current_price"),
                "shares": p.get("shares"),
                "market_value_inr": p.get("market_value_inr"),
                "total_inr": p["total_inr"],
                "realized_inr": p["realized_inr"],
                "unrealized_inr": p["unrealized_inr"],
                "return_pct": p["return_pct"],
                "stop_cushion_pct": p["stop_cushion_pct"],
                "days_held": p["days_held"],
                "signal_summary": p["signal_summary"],
                "ai_rating": p.get("ai_rating"),
                "exit_reason": p.get("exit_reason"),
            }
            for p in facts["positions"]
        ],
    }


def generate_narrative(facts: dict, tables: str, config: dict) -> str:
    from tradingagents.llm_clients.factory import create_llm_client

    compact = _compact_facts(facts)
    facts_json = json.dumps(compact, indent=2)
    grounding_sheet = build_grounding_sheet(facts)

    user_msg = USER_PROMPT_TEMPLATE.format(
        as_of_date=facts["as_of_date"],
        grounding_sheet=grounding_sheet,
        facts_json=facts_json,
        tables=tables,
    )

    provider = (config.get("llm_provider") or "openai").lower()
    model = config.get("quick_think_llm") or config.get("deep_think_llm")
    if not model:
        raise ValueError("No LLM model configured (quick_think_llm / deep_think_llm).")

    client = create_llm_client(
        provider=provider,
        model=model,
        base_url=config.get("backend_url"),
        google_thinking_level=config.get("google_thinking_level"),
        openai_reasoning_effort=config.get("openai_reasoning_effort"),
        anthropic_effort=config.get("anthropic_effort"),
    )
    llm = client.get_llm()
    llm.temperature = 0

    from langchain_core.messages import HumanMessage, SystemMessage

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_msg),
    ])
    content = response.content if hasattr(response, "content") else str(response)
    if isinstance(content, list):
        content = "\n".join(str(x) for x in content)
    return str(content).strip()

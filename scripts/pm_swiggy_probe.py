"""One-off probe: run Tech Desk PM on saved SWIGGY report (no open positions)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import create_llm_client
from tradingagents.tech_desk.agents.portfolio_manager import run_tech_desk_batch_pm
from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import render_batch_decision


def main() -> None:
    report_path = Path.home() / ".tradingagents/tech_reports/SWIGGY.NS/2026-07-10/market.md"
    if not report_path.exists():
        print(f"Missing report: {report_path}")
        sys.exit(1)

    text = report_path.read_text(encoding="utf-8")
    snap = TechReportSnapshot(
        ticker="SWIGGY.NS",
        report_date="2026-07-10",
        report_dir=report_path.parent,
        market_text=text,
        source_file="market.md",
    )

    # Price when first process ran (above analyst's 256-260 zone)
    current_price = 273.25
    config = DEFAULT_CONFIG.copy()

    provider = config.get("llm_provider", "openai")
    llm_kwargs: dict = {}
    if provider == "openai" and config.get("openai_reasoning_effort"):
        llm_kwargs["reasoning_effort"] = config["openai_reasoning_effort"]

    client = create_llm_client(
        provider=provider,
        model=config["quick_think_llm"],
        base_url=config.get("backend_url"),
        **llm_kwargs,
    )
    llm = client.get_llm()

    print(f"Provider: {provider} / {config['quick_think_llm']}")
    print(f"Current price: {current_price} (report close was 280.95; analyst zone 256-260)")
    print("Open positions: none\n")

    decision, pm_error = run_tech_desk_batch_pm(
        llm,
        [snap],
        open_positions=[],
        slots_available=10,
        config=config,
        prices={"SWIGGY.NS": current_price},
    )

    if pm_error:
        print(f"PM error: {pm_error}\n")

    print(render_batch_decision(decision))
    print("\n--- structured ---")
    for label, plans in [
        ("opens", decision.opens),
        ("waits", decision.waits),
        ("skips", decision.skips),
    ]:
        for p in plans:
            if hasattr(p, "model_dump"):
                print(f"{label}: {p.model_dump()}")
            else:
                print(f"{label}: {p}")


if __name__ == "__main__":
    main()

"""Orchestrate grounded portfolio review: facts → tables → optional LLM memo."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from tradingagents.portfolio_review.facts import collect_portfolio_facts
from tradingagents.portfolio_review.grounding import validate_narrative
from tradingagents.portfolio_review.narrative import generate_narrative
from tradingagents.portfolio_review.tables import render_tables


def reports_dir() -> Path:
    home = Path(os.environ.get("TRADINGAGENTS_HOME", os.path.expanduser("~/.tradingagents")))
    path = home / "portfolio_reports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_portfolio_review(
    config: dict,
    *,
    as_of: Optional[str] = None,
    use_llm: bool = True,
    output_dir: Optional[Path] = None,
) -> dict:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    facts = collect_portfolio_facts(config, as_of=as_of)
    tables = render_tables(facts)

    narrative = ""
    validation_ok = True
    validation_issues: list = []

    if use_llm:
        narrative = generate_narrative(facts, tables, config)
        validation_ok, validation_issues = validate_narrative(narrative, facts, tables)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = output_dir or reports_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    facts_path = out_dir / f"portfolio_facts_{as_of}_{stamp}.json"
    memo_path = out_dir / f"portfolio_memo_{as_of}_{stamp}.md"

    facts_path.write_text(json.dumps(facts, indent=2), encoding="utf-8")

    header = (
        f"# Portfolio Manager Memo\n\n"
        f"**As of:** {as_of}  \n"
        f"**Generated:** {facts['generated_at']}  \n"
        f"**Desks:** {facts['summary']['desks_tracked']} · "
        f"**Open:** {facts['summary']['open_positions']} · "
        f"**Total P&L:** ₹{facts['summary']['total_pnl_inr']:,.0f}\n\n"
        f"---\n\n"
    )

    validation_note = ""
    if use_llm and not validation_ok:
        validation_note = (
            "\n\n---\n\n"
            "*⚠ Grounding check: some numeric tokens in the narrative could not be "
            "verified against facts. Treat figures in the tables above as authoritative.*\n"
            f"*Issues: {', '.join(validation_issues[:5])}*\n"
        )

    memo_body = tables
    if narrative:
        memo_body = f"{narrative}\n\n---\n\n{tables}"

    memo_path.write_text(header + memo_body + validation_note, encoding="utf-8")

    return {
        "as_of_date": as_of,
        "facts_path": str(facts_path),
        "memo_path": str(memo_path),
        "summary": facts["summary"],
        "narrative": narrative,
        "tables": tables,
        "validation_ok": validation_ok,
        "validation_issues": validation_issues,
        "use_llm": use_llm,
    }

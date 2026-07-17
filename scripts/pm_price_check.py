"""Compare Tech Desk PM zones vs live prices from pending entries."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager
from tradingagents.tech_desk.process import fetch_prices
from tradingagents.tech_desk.schemas import SkipEntry, TechDeskBatchDecision, TechTradePlan, render_batch_decision

home = Path.home() / ".tradingagents" / "tech_desk"
pending_path = home / "pending_entries.json"
skip_path = home / "process" / "2026-07-13.json"

if not pending_path.exists():
    print("No pending_entries.json found")
    sys.exit(1)

pending = json.loads(pending_path.read_text(encoding="utf-8")).get("pending", [])
skips = []
if skip_path.exists():
    log = json.loads(skip_path.read_text(encoding="utf-8"))
    for s in log.get("skipped", []):
        if isinstance(s, dict):
            skips.append(SkipEntry(ticker=s["ticker"], reason=s.get("reason", "")))

waits = [TechTradePlan(action="wait", **{k: v for k, v in p.items() if k != "plan_date" and k != "report_path" and k != "report_date" and k != "added_at"}) for p in pending]
decision = TechDeskBatchDecision(waits=waits, skips=skips)

tickers = [w.ticker for w in waits] + [s.ticker for s in skips]
mgr = TechDeskPaperTradeManager(DEFAULT_CONFIG.copy())
prices = fetch_prices(tickers, mgr)

print(render_batch_decision(decision, prices=prices))

"""Tests for quick tech-analyze and watchlist."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.analysis.tech_analyze import (
    _build_tech_graph,
    save_tech_report,
)
from tradingagents.analysis.watchlist import (
    add_to_watchlist,
    load_watchlist,
    remove_from_watchlist,
    save_watchlist,
)
from tradingagents.graph.conditional_logic import ConditionalLogic


class WatchlistTests(unittest.TestCase):
    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "watchlist.txt")
            save_watchlist(["reliance", "TCS.NS", "INFY"], path=path)
            loaded = load_watchlist(path)
            self.assertEqual(loaded, ["RELIANCE.NS", "TCS.NS", "INFY.NS"])

    def test_add_and_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "watchlist.txt")
            save_watchlist(["RELIANCE"], path=path)
            updated = add_to_watchlist(["tcs", "RELIANCE"], path=path)
            self.assertEqual(updated, ["RELIANCE.NS", "TCS.NS"])
            updated = remove_from_watchlist(["tcs"], path=path)
            self.assertEqual(updated, ["RELIANCE.NS"])

    def test_load_csv_with_symbol_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "watchlist.csv"
            path.write_text("symbol,name\nreliance,Reliance\nTCS,Tata\n", encoding="utf-8")
            loaded = load_watchlist(str(path))
            self.assertEqual(loaded, ["RELIANCE.NS", "TCS.NS"])

    def test_empty_file_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "missing.txt")
            self.assertEqual(load_watchlist(path), [])


class TechGraphTests(unittest.TestCase):
    def test_mini_graph_compiles_with_expected_nodes(self):
        mock_llm = MagicMock()
        conditional_logic = ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1)
        graph = _build_tech_graph(mock_llm, conditional_logic)
        node_names = set(graph.get_graph().nodes.keys())
        self.assertIn("Market Analyst", node_names)
        self.assertIn("tools_market", node_names)
        self.assertIn("Msg Clear Market", node_names)
        self.assertIn("__end__", node_names)

    @patch("tradingagents.analysis.tech_analyze.create_llm_client")
    @patch("tradingagents.analysis.tech_analyze._build_tech_graph")
    def test_run_tech_analyze_returns_market_report(self, mock_build_graph, mock_llm_client):
        from tradingagents.analysis.tech_analyze import run_tech_analyze

        mock_client = MagicMock()
        mock_client.get_llm.return_value = MagicMock()
        mock_llm_client.return_value = mock_client

        mock_graph = MagicMock()
        mock_graph.stream.return_value = [
            {"market_report": ""},
            {"market_report": "RSI is bullish. MACD crossed up."},
        ]
        mock_build_graph.return_value = mock_graph

        result = run_tech_analyze(
            "AAPL",
            "2026-01-15",
            config={"llm_provider": "openai", "quick_think_llm": "gpt-test", "data_cache_dir": "/tmp"},
        )

        self.assertEqual(result["ticker"], "AAPL")
        self.assertEqual(result["trade_date"], "2026-01-15")
        self.assertEqual(result["market_report"], "RSI is bullish. MACD crossed up.")
        mock_graph.stream.assert_called_once()


class SaveTechReportTests(unittest.TestCase):
    def test_save_tech_report_writes_market_and_complete_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "AAPL" / "2026-01-15"
            result = {
                "ticker": "AAPL",
                "trade_date": "2026-01-15",
                "market_report": "Bullish trend on daily chart.",
            }
            report_file = save_tech_report(result, save_path)
            self.assertTrue((save_path / "market.md").exists())
            self.assertTrue(report_file.exists())
            complete = report_file.read_text(encoding="utf-8")
            self.assertIn("Technical Analysis Report: AAPL", complete)
            self.assertIn("Bullish trend on daily chart.", complete)
            self.assertEqual(
                (save_path / "market.md").read_text(encoding="utf-8"),
                "Bullish trend on daily chart.",
            )


if __name__ == "__main__":
    unittest.main()

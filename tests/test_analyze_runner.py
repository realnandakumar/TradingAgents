"""Tests for the dashboard analysis runner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.analysis.report import save_report_to_disk
from tradingagents.analysis.runner import (
    ProgressWriter,
    _default_analysts_for_ticker,
    _resolve_analyst_keys,
    job_path_for_id,
    progress_path_for_job,
)


class SaveReportTests(unittest.TestCase):
    def test_save_report_writes_complete_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "AAPL_20260101_120000"
            final_state = {
                "market_report": "Bullish trend.",
                "final_trade_decision": "BUY",
            }
            report_file = save_report_to_disk(final_state, "AAPL", save_path)
            self.assertTrue(report_file.exists())
            text = report_file.read_text(encoding="utf-8")
            self.assertIn("Trading Analysis Report: AAPL", text)
            self.assertIn("Bullish trend.", text)


class AnalystDefaultsTests(unittest.TestCase):
    def test_stock_gets_all_analysts(self):
        keys = _default_analysts_for_ticker("AAPL")
        self.assertEqual(keys, ["market", "social", "news", "fundamentals"])

    def test_crypto_excludes_fundamentals(self):
        keys = _default_analysts_for_ticker("BTC-USD")
        self.assertNotIn("fundamentals", keys)
        self.assertIn("market", keys)

    def test_resolve_analyst_keys_respects_job(self):
        job = {"analysts": ["market", "news"]}
        keys = _resolve_analyst_keys(job, "AAPL")
        self.assertEqual(keys, ["market", "news"])


class JobPathTests(unittest.TestCase):
    def test_job_and_progress_paths_use_job_id(self):
        job_id = "abc-123"
        self.assertTrue(str(job_path_for_id(job_id)).endswith("abc-123.json"))
        self.assertTrue(str(progress_path_for_job(job_id)).endswith("abc-123.progress.json"))


class ProgressWriterTests(unittest.TestCase):
    def test_writes_json_progress_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "job.progress.json"
            from tradingagents.analysis.runner import AnalysisMessageBuffer

            buf = AnalysisMessageBuffer()
            buf.init_for_analysis(["market"])
            buf.add_message("System", "hello")
            writer = ProgressWriter(path, "job-1")
            writer.write(buf, stage="analysts")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["jobId"], "job-1")
            self.assertEqual(data["status"], "running")
            self.assertEqual(data["stage"], "analysts")
            self.assertEqual(len(data["messages"]), 1)


class RunAnalysisJobIOTests(unittest.TestCase):
    @patch("tradingagents.analysis.runner.TradingAgentsGraph")
    def test_job_manifest_updated_on_success(self, mock_graph_cls):
        mock_graph = MagicMock()
        mock_graph_cls.return_value = mock_graph
        mock_graph.propagator.create_initial_state.return_value = {}
        mock_graph.propagator.get_graph_args.return_value = {}
        mock_graph.graph.stream.return_value = [
            {"final_trade_decision": "BUY recommendation"},
        ]
        mock_graph.process_signal.return_value = "BUY"

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            jobs = home / "analyze" / "jobs"
            reports = home / "analyze" / "reports"
            jobs.mkdir(parents=True)
            reports.mkdir(parents=True)

            with patch("tradingagents.analysis.runner.get_analyze_home", return_value=home / "analyze"):
                with patch("tradingagents.analysis.runner.jobs_dir", return_value=jobs):
                    with patch("tradingagents.analysis.runner.reports_dir", return_value=reports):
                        job_id = "test-job-1"
                        job = {
                            "job_id": job_id,
                            "ticker": "AAPL",
                            "analysis_date": "2026-01-15",
                            "analysts": ["market"],
                            "research_depth": 1,
                        }
                        job_path = jobs / f"{job_id}.json"
                        job_path.write_text(json.dumps(job), encoding="utf-8")
                        progress_path = jobs / f"{job_id}.progress.json"

                        from tradingagents.analysis.runner import run_analysis_job

                        result = run_analysis_job(job, progress_path)

                        self.assertEqual(result["status"], "completed")
                        self.assertEqual(result["decision"], "BUY")
                        saved = json.loads(job_path.read_text(encoding="utf-8"))
                        self.assertEqual(saved["status"], "completed")
                        self.assertTrue(Path(result["report_path"]).exists())


if __name__ == "__main__":
    unittest.main()

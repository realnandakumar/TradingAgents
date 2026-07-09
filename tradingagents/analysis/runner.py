"""Headless analysis runner for dashboard jobs."""

from __future__ import annotations

import ast
import datetime
import json
import os
import time
import traceback
from collections import deque
from pathlib import Path
from typing import Any, Dict, List, Optional

from cli.utils import detect_asset_type, filter_analysts_for_asset_type, normalize_ticker_symbol
from cli.models import AnalystType
from cli.stats_handler import StatsCallbackHandler
from tradingagents.analysis.report import save_report_to_disk
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.analyst_execution import (
    AnalystWallTimeTracker,
    build_analyst_execution_plan,
    get_initial_analyst_node,
    sync_analyst_tracker_from_chunk,
)
from tradingagents.graph.trading_graph import TradingAgentsGraph

ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Sentiment Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}

DEFAULT_ANALYSTS = ["market", "social", "news", "fundamentals"]
STAGE_WEIGHTS = {
    "starting": 0,
    "analysts": 35,
    "research": 55,
    "trading": 70,
    "risk": 85,
    "portfolio": 95,
    "saving": 98,
    "completed": 100,
}


def get_tradingagents_home() -> Path:
    return Path(os.environ.get("TRADINGAGENTS_HOME", os.path.expanduser("~/.tradingagents")))


def get_analyze_home() -> Path:
    return get_tradingagents_home() / "analyze"


def jobs_dir() -> Path:
    return get_analyze_home() / "jobs"


def reports_dir() -> Path:
    return get_analyze_home() / "reports"


def progress_path_for_job(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.progress.json"


def job_path_for_id(job_id: str) -> Path:
    return jobs_dir() / f"{job_id}.json"


class AnalysisMessageBuffer:
    """Lightweight message buffer for headless analysis runs."""

    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }
    ANALYST_MAPPING = ANALYST_AGENT_NAMES
    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Sentiment Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }

    def __init__(self, max_length: int = 100):
        self.messages: deque = deque(maxlen=max_length)
        self.tool_calls: deque = deque(maxlen=max_length)
        self.agent_status: Dict[str, str] = {}
        self.report_sections: Dict[str, Any] = {}
        self.selected_analysts: List[str] = []
        self._processed_message_ids: set = set()

    def init_for_analysis(self, selected_analysts: List[str]) -> None:
        self.selected_analysts = [a.lower() for a in selected_analysts]
        self.agent_status = {}
        for analyst_key in self.selected_analysts:
            if analyst_key in self.ANALYST_MAPPING:
                self.agent_status[self.ANALYST_MAPPING[analyst_key]] = "pending"
        for team_agents in self.FIXED_AGENTS.values():
            for agent in team_agents:
                self.agent_status[agent] = "pending"
        self.report_sections = {}
        for section, (analyst_key, _) in self.REPORT_SECTIONS.items():
            if analyst_key is None or analyst_key in self.selected_analysts:
                self.report_sections[section] = None
        self.messages.clear()
        self.tool_calls.clear()
        self._processed_message_ids.clear()

    def add_message(self, message_type: str, content: str) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.messages.append((timestamp, message_type, content))

    def add_tool_call(self, tool_name: str, args: dict) -> None:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.tool_calls.append((timestamp, tool_name, args))

    def update_agent_status(self, agent: str, status: str) -> None:
        if agent in self.agent_status:
            self.agent_status[agent] = status

    def update_report_section(self, section_name: str, content: Any) -> None:
        if section_name in self.report_sections:
            self.report_sections[section_name] = content


class ProgressWriter:
    """Write analysis progress to a JSON file for dashboard polling."""

    def __init__(self, path: Path, job_id: str):
        self.path = path
        self.job_id = job_id
        self.stage = "starting"
        self.status = "running"
        self.error: Optional[str] = None
        self.started_at = datetime.datetime.now().isoformat()
        self.updated_at = self.started_at

    def write(
        self,
        message_buffer: AnalysisMessageBuffer,
        *,
        stage: Optional[str] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        if stage is not None:
            self.stage = stage
        if status is not None:
            self.status = status
        if error is not None:
            self.error = error
        self.updated_at = datetime.datetime.now().isoformat()

        completed = sum(1 for s in message_buffer.agent_status.values() if s == "completed")
        total = len(message_buffer.agent_status) or 1
        agent_ratio = completed / total
        base = STAGE_WEIGHTS.get(self.stage, 0)
        next_stage = min(
            [w for k, w in STAGE_WEIGHTS.items() if w > base],
            default=100,
        )
        percent = int(base + (next_stage - base) * agent_ratio)

        messages_tail = [
            {"time": t, "type": mt, "content": c[:500]}
            for t, mt, c in list(message_buffer.messages)[-20:]
        ]

        payload: Dict[str, Any] = {
            "jobId": self.job_id,
            "status": self.status,
            "stage": self.stage,
            "percent": min(percent, 99) if self.status == "running" else 100,
            "agentStatus": dict(message_buffer.agent_status),
            "messages": messages_tail,
            "startedAt": self.started_at,
            "updatedAt": self.updated_at,
            "error": self.error,
        }
        if extra:
            payload.update(extra)

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _extract_content_string(content: Any) -> Optional[str]:
    def is_empty(val: Any) -> bool:
        if val is None or val == "":
            return True
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return True
            try:
                return not bool(ast.literal_eval(s))
            except (ValueError, SyntaxError):
                return False
        return not bool(val)

    if is_empty(content):
        return None
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() if not is_empty(text) else None
    if isinstance(content, list):
        text_parts = [
            item.get("text", "").strip()
            if isinstance(item, dict) and item.get("type") == "text"
            else (item.strip() if isinstance(item, str) else "")
            for item in content
        ]
        result = " ".join(t for t in text_parts if t and not is_empty(t))
        return result if result else None
    return str(content).strip() if not is_empty(content) else None


def _classify_message_type(message) -> tuple[str, Optional[str]]:
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = _extract_content_string(getattr(message, "content", None))
    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("Control", content)
        return ("User", content)
    if isinstance(message, ToolMessage):
        return ("Data", content)
    if isinstance(message, AIMessage):
        return ("Agent", content)
    return ("System", content)


def _update_research_team_status(message_buffer: AnalysisMessageBuffer, status: str) -> None:
    for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
        message_buffer.update_agent_status(agent, status)


def _update_analyst_statuses(
    message_buffer: AnalysisMessageBuffer,
    chunk: dict,
    wall_time_tracker: Optional[AnalystWallTimeTracker] = None,
) -> None:
    selected = message_buffer.selected_analysts
    found_active = False

    if wall_time_tracker is not None:
        sync_analyst_tracker_from_chunk(wall_time_tracker, chunk)

    for analyst_key in ANALYST_ORDER:
        if analyst_key not in selected:
            continue
        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        report_key = ANALYST_REPORT_MAP[analyst_key]
        if chunk.get(report_key):
            message_buffer.update_report_section(report_key, chunk[report_key])
        has_report = bool(message_buffer.report_sections.get(report_key))
        if has_report:
            message_buffer.update_agent_status(agent_name, "completed")
        elif not found_active:
            message_buffer.update_agent_status(agent_name, "in_progress")
            found_active = True
        else:
            message_buffer.update_agent_status(agent_name, "pending")

    if not found_active and selected:
        if message_buffer.agent_status.get("Bull Researcher") == "pending":
            message_buffer.update_agent_status("Bull Researcher", "in_progress")


def _default_analysts_for_ticker(ticker: str) -> List[str]:
    asset_type = detect_asset_type(ticker)
    all_analysts = [AnalystType(v) for v in DEFAULT_ANALYSTS]
    filtered = filter_analysts_for_asset_type(all_analysts, asset_type)
    return [a.value for a in filtered]


def _resolve_analyst_keys(job: dict, ticker: str) -> List[str]:
    raw = job.get("analysts")
    if not raw:
        return _default_analysts_for_ticker(ticker)
    selected_set = {str(a).lower() for a in raw}
    return [a for a in ANALYST_ORDER if a in selected_set] or _default_analysts_for_ticker(ticker)


def _build_config(job: dict, ticker: str, analysis_date: str) -> dict:
    config = DEFAULT_CONFIG.copy()
    research_depth = int(job.get("research_depth") or config.get("max_debate_rounds", 1))
    config["max_debate_rounds"] = research_depth
    config["max_risk_discuss_rounds"] = research_depth

    if job.get("llm_provider"):
        config["llm_provider"] = str(job["llm_provider"]).lower()
    if job.get("deep_think_llm"):
        config["deep_think_llm"] = job["deep_think_llm"]
    if job.get("quick_think_llm"):
        config["quick_think_llm"] = job["quick_think_llm"]
    if job.get("backend_url") is not None:
        config["backend_url"] = job["backend_url"]
    if job.get("output_language"):
        config["output_language"] = job["output_language"]
    if job.get("reddit_market"):
        config["reddit_market"] = str(job["reddit_market"]).lower()

    config["checkpoint_enabled"] = bool(job.get("checkpoint", False))
    config["tool_response_log_dir"] = str(
        Path(config["results_dir"]) / ticker / analysis_date / "tool_responses"
    )
    return config


def run_analysis_job(job: dict, progress_path: Path) -> dict:
    """Run a headless analysis job and persist progress + report."""
    job_id = job["job_id"]
    ticker = normalize_ticker_symbol(job["ticker"])
    analysis_date = job.get("analysis_date") or datetime.date.today().isoformat()
    asset_type = detect_asset_type(ticker).value

    progress = ProgressWriter(progress_path, job_id)
    message_buffer = AnalysisMessageBuffer()
    selected_analyst_keys = _resolve_analyst_keys(job, ticker)

    job_path = job_path_for_id(job_id)
    job.update(
        {
            "status": "running",
            "ticker": ticker,
            "analysis_date": analysis_date,
            "analysts": selected_analyst_keys,
            "started_at": datetime.datetime.now().isoformat(),
        }
    )
    job_path.parent.mkdir(parents=True, exist_ok=True)
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")

    try:
        config = _build_config(job, ticker, analysis_date)
        stats_handler = StatsCallbackHandler()
        analyst_execution_plan = build_analyst_execution_plan(
            selected_analyst_keys,
            concurrency_limit=config["analyst_concurrency_limit"],
        )
        analyst_wall_time_tracker = AnalystWallTimeTracker(analyst_execution_plan)

        graph = TradingAgentsGraph(
            selected_analyst_keys,
            config=config,
            debug=True,
            callbacks=[stats_handler],
        )

        message_buffer.init_for_analysis(selected_analyst_keys)
        message_buffer.add_message("System", f"Selected ticker: {ticker}")
        message_buffer.add_message("System", f"Detected asset type: {asset_type}")
        message_buffer.add_message("System", f"Analysis date: {analysis_date}")
        message_buffer.add_message(
            "System", f"Selected analysts: {', '.join(selected_analyst_keys)}"
        )

        first_analyst = get_initial_analyst_node(analyst_execution_plan)
        message_buffer.update_agent_status(first_analyst, "in_progress")
        analyst_wall_time_tracker.mark_started(selected_analyst_keys[0])
        progress.write(message_buffer, stage="starting")

        init_agent_state = graph.propagator.create_initial_state(
            ticker, analysis_date, asset_type=asset_type
        )
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])

        trace: List[dict] = []
        progress.write(message_buffer, stage="analysts")

        for chunk in graph.graph.stream(init_agent_state, **args):
            for message in chunk.get("messages", []):
                msg_id = getattr(message, "id", None)
                if msg_id is not None:
                    if msg_id in message_buffer._processed_message_ids:
                        continue
                    message_buffer._processed_message_ids.add(msg_id)

                msg_type, content = _classify_message_type(message)
                if content and content.strip():
                    message_buffer.add_message(msg_type, content)

                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tool_call in message.tool_calls:
                        if isinstance(tool_call, dict):
                            message_buffer.add_tool_call(tool_call["name"], tool_call["args"])
                        else:
                            message_buffer.add_tool_call(tool_call.name, tool_call.args)

            _update_analyst_statuses(message_buffer, chunk, analyst_wall_time_tracker)

            if chunk.get("investment_debate_state"):
                progress.write(message_buffer, stage="research")
                debate_state = chunk["investment_debate_state"]
                bull_hist = debate_state.get("bull_history", "").strip()
                bear_hist = debate_state.get("bear_history", "").strip()
                judge = debate_state.get("judge_decision", "").strip()
                if bull_hist or bear_hist:
                    _update_research_team_status(message_buffer, "in_progress")
                if bull_hist:
                    message_buffer.update_report_section(
                        "investment_plan", f"### Bull Researcher Analysis\n{bull_hist}"
                    )
                if bear_hist:
                    message_buffer.update_report_section(
                        "investment_plan", f"### Bear Researcher Analysis\n{bear_hist}"
                    )
                if judge:
                    message_buffer.update_report_section(
                        "investment_plan", f"### Research Manager Decision\n{judge}"
                    )
                    _update_research_team_status(message_buffer, "completed")
                    message_buffer.update_agent_status("Trader", "in_progress")

            if chunk.get("trader_investment_plan"):
                progress.write(message_buffer, stage="trading")
                message_buffer.update_report_section(
                    "trader_investment_plan", chunk["trader_investment_plan"]
                )
                if message_buffer.agent_status.get("Trader") != "completed":
                    message_buffer.update_agent_status("Trader", "completed")
                    message_buffer.update_agent_status("Aggressive Analyst", "in_progress")

            if chunk.get("risk_debate_state"):
                progress.write(message_buffer, stage="risk")
                risk_state = chunk["risk_debate_state"]
                agg_hist = risk_state.get("aggressive_history", "").strip()
                con_hist = risk_state.get("conservative_history", "").strip()
                neu_hist = risk_state.get("neutral_history", "").strip()
                judge = risk_state.get("judge_decision", "").strip()

                if agg_hist:
                    if message_buffer.agent_status.get("Aggressive Analyst") != "completed":
                        message_buffer.update_agent_status("Aggressive Analyst", "in_progress")
                    message_buffer.update_report_section(
                        "final_trade_decision", f"### Aggressive Analyst Analysis\n{agg_hist}"
                    )
                if con_hist:
                    if message_buffer.agent_status.get("Conservative Analyst") != "completed":
                        message_buffer.update_agent_status("Conservative Analyst", "in_progress")
                    message_buffer.update_report_section(
                        "final_trade_decision", f"### Conservative Analyst Analysis\n{con_hist}"
                    )
                if neu_hist:
                    if message_buffer.agent_status.get("Neutral Analyst") != "completed":
                        message_buffer.update_agent_status("Neutral Analyst", "in_progress")
                    message_buffer.update_report_section(
                        "final_trade_decision", f"### Neutral Analyst Analysis\n{neu_hist}"
                    )
                if judge:
                    progress.write(message_buffer, stage="portfolio")
                    if message_buffer.agent_status.get("Portfolio Manager") != "completed":
                        message_buffer.update_agent_status("Portfolio Manager", "in_progress")
                        message_buffer.update_report_section(
                            "final_trade_decision", f"### Portfolio Manager Decision\n{judge}"
                        )
                        message_buffer.update_agent_status("Aggressive Analyst", "completed")
                        message_buffer.update_agent_status("Conservative Analyst", "completed")
                        message_buffer.update_agent_status("Neutral Analyst", "completed")
                        message_buffer.update_agent_status("Portfolio Manager", "completed")

            trace.append(chunk)
            progress.write(message_buffer)

        final_state: dict = {}
        for chunk in trace:
            final_state.update(chunk)

        decision = graph.process_signal(final_state["final_trade_decision"])

        for agent in message_buffer.agent_status:
            message_buffer.update_agent_status(agent, "completed")
        message_buffer.add_message("System", f"Completed analysis for {analysis_date}")
        message_buffer.add_message("System", analyst_wall_time_tracker.format_summary())

        progress.write(message_buffer, stage="saving")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        report_id = f"{ticker}_{timestamp}"
        save_path = reports_dir() / report_id
        report_file = save_report_to_disk(final_state, ticker, save_path)

        result = {
            "job_id": job_id,
            "status": "completed",
            "ticker": ticker,
            "analysis_date": analysis_date,
            "decision": decision,
            "report_id": report_id,
            "report_path": str(report_file),
            "report_dir": str(save_path),
            "completed_at": datetime.datetime.now().isoformat(),
            "wall_time_summary": analyst_wall_time_tracker.format_summary(),
        }

        job.update(result)
        job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
        progress.write(
            message_buffer,
            stage="completed",
            status="completed",
            extra={"decision": decision, "reportId": report_id},
        )
        return result

    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"
        tb = traceback.format_exc()
        job.update(
            {
                "status": "failed",
                "error": err,
                "traceback": tb,
                "failed_at": datetime.datetime.now().isoformat(),
            }
        )
        job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
        progress.write(message_buffer, status="failed", error=err)
        raise

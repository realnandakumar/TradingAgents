from typing import Optional
import datetime
import json
import sys
import typer
import questionary
from pathlib import Path
from functools import wraps
from rich.console import Console
from rich.panel import Panel
from rich.spinner import Spinner
from rich.live import Live
from rich.columns import Columns
from rich.markdown import Markdown
from rich.layout import Layout
from rich.text import Text
from rich.table import Table
from collections import deque
import time
from rich.tree import Tree
from rich import box
from rich.align import Align
from rich.rule import Rule

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.graph.analyst_execution import (
    AnalystWallTimeTracker,
    build_analyst_execution_plan,
    get_initial_analyst_node,
    sync_analyst_tracker_from_chunk,
)
from tradingagents.analysis.report import save_report_to_disk
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.reddit import get_subreddits_for_market
from cli.models import AnalystType
from cli.utils import *
from cli.announcements import fetch_announcements, display_announcements
from cli.stats_handler import StatsCallbackHandler

console = Console()


def _portfolio_approve(
    desk_id: str,
    *,
    yes: bool = False,
    ids: Optional[str] = None,
) -> None:
    """Deprecated no-op — foreclosure disabled on all paper desks."""
    from tradingagents.replacements.approve import approve_portfolio_replacements

    _ = (yes, ids)
    result = approve_portfolio_replacements(desk_id)
    for msg in result.get("messages") or []:
        console.print(f"[yellow]{msg}[/yellow]")
    raise typer.Exit(0)

app = typer.Typer(
    name="TradingAgents",
    help="TradingAgents CLI: Multi-Agents LLM Financial Trading Framework",
    add_completion=True,  # Enable shell completion
)


# Create a deque to store recent messages with a maximum length
class MessageBuffer:
    # Fixed teams that always run (not user-selectable)
    FIXED_AGENTS = {
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    # Analyst name mapping
    ANALYST_MAPPING = {
        "market": "Market Analyst",
        "social": "Sentiment Analyst",
        "news": "News Analyst",
        "fundamentals": "Fundamentals Analyst",
    }

    # Report section mapping: section -> (analyst_key for filtering, finalizing_agent)
    # analyst_key: which analyst selection controls this section (None = always included)
    # finalizing_agent: which agent must be "completed" for this report to count as done
    REPORT_SECTIONS = {
        "market_report": ("market", "Market Analyst"),
        "sentiment_report": ("social", "Sentiment Analyst"),
        "news_report": ("news", "News Analyst"),
        "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
        "investment_plan": (None, "Research Manager"),
        "trader_investment_plan": (None, "Trader"),
        "final_trade_decision": (None, "Portfolio Manager"),
    }

    def __init__(self, max_length=100):
        self.messages = deque(maxlen=max_length)
        self.tool_calls = deque(maxlen=max_length)
        self.current_report = None
        self.final_report = None  # Store the complete final report
        self.agent_status = {}
        self.current_agent = None
        self.report_sections = {}
        self.selected_analysts = []
        self._processed_message_ids = set()

    def init_for_analysis(self, selected_analysts):
        """Initialize agent status and report sections based on selected analysts.

        Args:
            selected_analysts: List of analyst type strings (e.g., ["market", "news"])
        """
        self.selected_analysts = [a.lower() for a in selected_analysts]

        # Build agent_status dynamically
        self.agent_status = {}

        # Add selected analysts
        for analyst_key in self.selected_analysts:
            if analyst_key in self.ANALYST_MAPPING:
                self.agent_status[self.ANALYST_MAPPING[analyst_key]] = "pending"

        # Add fixed teams
        for team_agents in self.FIXED_AGENTS.values():
            for agent in team_agents:
                self.agent_status[agent] = "pending"

        # Build report_sections dynamically
        self.report_sections = {}
        for section, (analyst_key, _) in self.REPORT_SECTIONS.items():
            if analyst_key is None or analyst_key in self.selected_analysts:
                self.report_sections[section] = None

        # Reset other state
        self.current_report = None
        self.final_report = None
        self.current_agent = None
        self.messages.clear()
        self.tool_calls.clear()
        self._processed_message_ids.clear()

    def get_completed_reports_count(self):
        """Count reports that are finalized (their finalizing agent is completed).

        A report is considered complete when:
        1. The report section has content (not None), AND
        2. The agent responsible for finalizing that report has status "completed"

        This prevents interim updates (like debate rounds) from counting as completed.
        """
        count = 0
        for section in self.report_sections:
            if section not in self.REPORT_SECTIONS:
                continue
            _, finalizing_agent = self.REPORT_SECTIONS[section]
            # Report is complete if it has content AND its finalizing agent is done
            has_content = self.report_sections.get(section) is not None
            agent_done = self.agent_status.get(finalizing_agent) == "completed"
            if has_content and agent_done:
                count += 1
        return count

    def add_message(self, message_type, content):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.messages.append((timestamp, message_type, content))

    def add_tool_call(self, tool_name, args):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.tool_calls.append((timestamp, tool_name, args))

    def update_agent_status(self, agent, status):
        if agent in self.agent_status:
            self.agent_status[agent] = status
            self.current_agent = agent

    def update_report_section(self, section_name, content):
        if section_name in self.report_sections:
            self.report_sections[section_name] = content
            self._update_current_report()

    def _update_current_report(self):
        # For the panel display, only show the most recently updated section
        latest_section = None
        latest_content = None

        # Find the most recently updated section
        for section, content in self.report_sections.items():
            if content is not None:
                latest_section = section
                latest_content = content
               
        if latest_section and latest_content:
            # Format the current section for display
            section_titles = {
                "market_report": "Market Analysis",
                "sentiment_report": "Social Sentiment",
                "news_report": "News Analysis",
                "fundamentals_report": "Fundamentals Analysis",
                "investment_plan": "Research Team Decision",
                "trader_investment_plan": "Trading Team Plan",
                "final_trade_decision": "Portfolio Management Decision",
            }
            self.current_report = (
                f"### {section_titles[latest_section]}\n{latest_content}"
            )

        # Update the final complete report
        self._update_final_report()

    def _update_final_report(self):
        report_parts = []

        # Analyst Team Reports - use .get() to handle missing sections
        analyst_sections = ["market_report", "sentiment_report", "news_report", "fundamentals_report"]
        if any(self.report_sections.get(section) for section in analyst_sections):
            report_parts.append("## Analyst Team Reports")
            if self.report_sections.get("market_report"):
                report_parts.append(
                    f"### Market Analysis\n{self.report_sections['market_report']}"
                )
            if self.report_sections.get("sentiment_report"):
                report_parts.append(
                    f"### Social Sentiment\n{self.report_sections['sentiment_report']}"
                )
            if self.report_sections.get("news_report"):
                report_parts.append(
                    f"### News Analysis\n{self.report_sections['news_report']}"
                )
            if self.report_sections.get("fundamentals_report"):
                report_parts.append(
                    f"### Fundamentals Analysis\n{self.report_sections['fundamentals_report']}"
                )

        # Research Team Reports
        if self.report_sections.get("investment_plan"):
            report_parts.append("## Research Team Decision")
            report_parts.append(f"{self.report_sections['investment_plan']}")

        # Trading Team Reports
        if self.report_sections.get("trader_investment_plan"):
            report_parts.append("## Trading Team Plan")
            report_parts.append(f"{self.report_sections['trader_investment_plan']}")

        # Portfolio Management Decision
        if self.report_sections.get("final_trade_decision"):
            report_parts.append("## Portfolio Management Decision")
            report_parts.append(f"{self.report_sections['final_trade_decision']}")

        self.final_report = "\n\n".join(report_parts) if report_parts else None


message_buffer = MessageBuffer()


def create_layout():
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="footer", size=3),
    )
    layout["main"].split_column(
        Layout(name="upper", ratio=3), Layout(name="analysis", ratio=5)
    )
    layout["upper"].split_row(
        Layout(name="progress", ratio=2), Layout(name="messages", ratio=3)
    )
    return layout


def format_tokens(n):
    """Format token count for display."""
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def update_display(layout, spinner_text=None, stats_handler=None, start_time=None):
    # Header with welcome message
    layout["header"].update(
        Panel(
            "[bold green]Welcome to TradingAgents CLI[/bold green]\n"
            "[dim]© [Tauric Research](https://github.com/TauricResearch)[/dim]",
            title="Welcome to TradingAgents",
            border_style="green",
            padding=(1, 2),
            expand=True,
        )
    )

    # Progress panel showing agent status
    progress_table = Table(
        show_header=True,
        header_style="bold magenta",
        show_footer=False,
        box=box.SIMPLE_HEAD,  # Use simple header with horizontal lines
        title=None,  # Remove the redundant Progress title
        padding=(0, 2),  # Add horizontal padding
        expand=True,  # Make table expand to fill available space
    )
    progress_table.add_column("Team", style="cyan", justify="center", width=20)
    progress_table.add_column("Agent", style="green", justify="center", width=20)
    progress_table.add_column("Status", style="yellow", justify="center", width=20)

    # Group agents by team - filter to only include agents in agent_status
    all_teams = {
        "Analyst Team": [
            "Market Analyst",
            "Sentiment Analyst",
            "News Analyst",
            "Fundamentals Analyst",
        ],
        "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
        "Trading Team": ["Trader"],
        "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
        "Portfolio Management": ["Portfolio Manager"],
    }

    # Filter teams to only include agents that are in agent_status
    teams = {}
    for team, agents in all_teams.items():
        active_agents = [a for a in agents if a in message_buffer.agent_status]
        if active_agents:
            teams[team] = active_agents

    for team, agents in teams.items():
        # Add first agent with team name
        first_agent = agents[0]
        status = message_buffer.agent_status.get(first_agent, "pending")
        if status == "in_progress":
            spinner = Spinner(
                "dots", text="[blue]in_progress[/blue]", style="bold cyan"
            )
            status_cell = spinner
        else:
            status_color = {
                "pending": "yellow",
                "completed": "green",
                "error": "red",
            }.get(status, "white")
            status_cell = f"[{status_color}]{status}[/{status_color}]"
        progress_table.add_row(team, first_agent, status_cell)

        # Add remaining agents in team
        for agent in agents[1:]:
            status = message_buffer.agent_status.get(agent, "pending")
            if status == "in_progress":
                spinner = Spinner(
                    "dots", text="[blue]in_progress[/blue]", style="bold cyan"
                )
                status_cell = spinner
            else:
                status_color = {
                    "pending": "yellow",
                    "completed": "green",
                    "error": "red",
                }.get(status, "white")
                status_cell = f"[{status_color}]{status}[/{status_color}]"
            progress_table.add_row("", agent, status_cell)

        # Add horizontal line after each team
        progress_table.add_row("─" * 20, "─" * 20, "─" * 20, style="dim")

    layout["progress"].update(
        Panel(progress_table, title="Progress", border_style="cyan", padding=(1, 2))
    )

    # Messages panel showing recent messages and tool calls
    messages_table = Table(
        show_header=True,
        header_style="bold magenta",
        show_footer=False,
        expand=True,  # Make table expand to fill available space
        box=box.MINIMAL,  # Use minimal box style for a lighter look
        show_lines=True,  # Keep horizontal lines
        padding=(0, 1),  # Add some padding between columns
    )
    messages_table.add_column("Time", style="cyan", width=8, justify="center")
    messages_table.add_column("Type", style="green", width=10, justify="center")
    messages_table.add_column(
        "Content", style="white", no_wrap=False, ratio=1
    )  # Make content column expand

    # Combine tool calls and messages
    all_messages = []

    # Add tool calls
    for timestamp, tool_name, args in message_buffer.tool_calls:
        formatted_args = format_tool_args(args)
        all_messages.append((timestamp, "Tool", f"{tool_name}: {formatted_args}"))

    # Add regular messages
    for timestamp, msg_type, content in message_buffer.messages:
        content_str = str(content) if content else ""
        if len(content_str) > 200:
            content_str = content_str[:197] + "..."
        all_messages.append((timestamp, msg_type, content_str))

    # Sort by timestamp descending (newest first)
    all_messages.sort(key=lambda x: x[0], reverse=True)

    # Calculate how many messages we can show based on available space
    max_messages = 12

    # Get the first N messages (newest ones)
    recent_messages = all_messages[:max_messages]

    # Add messages to table (already in newest-first order)
    for timestamp, msg_type, content in recent_messages:
        # Format content with word wrapping
        wrapped_content = Text(content, overflow="fold")
        messages_table.add_row(timestamp, msg_type, wrapped_content)

    layout["messages"].update(
        Panel(
            messages_table,
            title="Messages & Tools",
            border_style="blue",
            padding=(1, 2),
        )
    )

    # Analysis panel showing current report
    if message_buffer.current_report:
        layout["analysis"].update(
            Panel(
                Markdown(message_buffer.current_report),
                title="Current Report",
                border_style="green",
                padding=(1, 2),
            )
        )
    else:
        layout["analysis"].update(
            Panel(
                "[italic]Waiting for analysis report...[/italic]",
                title="Current Report",
                border_style="green",
                padding=(1, 2),
            )
        )

    # Footer with statistics
    # Agent progress - derived from agent_status dict
    agents_completed = sum(
        1 for status in message_buffer.agent_status.values() if status == "completed"
    )
    agents_total = len(message_buffer.agent_status)

    # Report progress - based on agent completion (not just content existence)
    reports_completed = message_buffer.get_completed_reports_count()
    reports_total = len(message_buffer.report_sections)

    # Build stats parts
    stats_parts = [f"Agents: {agents_completed}/{agents_total}"]

    # LLM and tool stats from callback handler
    if stats_handler:
        stats = stats_handler.get_stats()
        stats_parts.append(f"LLM: {stats['llm_calls']}")
        stats_parts.append(f"Tools: {stats['tool_calls']}")

        # Token display with graceful fallback
        if stats["tokens_in"] > 0 or stats["tokens_out"] > 0:
            tokens_str = f"Tokens: {format_tokens(stats['tokens_in'])}\u2191 {format_tokens(stats['tokens_out'])}\u2193"
        else:
            tokens_str = "Tokens: --"
        stats_parts.append(tokens_str)

    stats_parts.append(f"Reports: {reports_completed}/{reports_total}")

    # Elapsed time
    if start_time:
        elapsed = time.time() - start_time
        elapsed_str = f"\u23f1 {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        stats_parts.append(elapsed_str)

    stats_table = Table(show_header=False, box=None, padding=(0, 2), expand=True)
    stats_table.add_column("Stats", justify="center")
    stats_table.add_row(" | ".join(stats_parts))

    layout["footer"].update(Panel(stats_table, border_style="grey50"))


def get_user_selections():
    """Get all user selections before starting the analysis display."""
    # Display ASCII art welcome message
    with open(Path(__file__).parent / "static" / "welcome.txt", "r", encoding="utf-8") as f:
        welcome_ascii = f.read()

    # Create welcome box content
    welcome_content = f"{welcome_ascii}\n"
    welcome_content += "[bold green]TradingAgents: Multi-Agents LLM Financial Trading Framework - CLI[/bold green]\n\n"
    welcome_content += "[bold]Workflow Steps:[/bold]\n"
    welcome_content += "I. Analyst Team → II. Research Team → III. Trader → IV. Risk Management → V. Portfolio Management\n\n"
    welcome_content += (
        "[dim]Built by [Tauric Research](https://github.com/TauricResearch)[/dim]"
    )

    # Create and center the welcome box
    welcome_box = Panel(
        welcome_content,
        border_style="green",
        padding=(1, 2),
        title="Welcome to TradingAgents",
        subtitle="Multi-Agents LLM Financial Trading Framework",
    )
    console.print(Align.center(welcome_box))
    console.print()
    console.print()  # Add vertical space before announcements

    # Fetch and display announcements (silent on failure)
    announcements = fetch_announcements()
    display_announcements(console, announcements)

    # Create a boxed questionnaire for each step
    def create_question_box(title, prompt, default=None):
        box_content = f"[bold]{title}[/bold]\n"
        box_content += f"[dim]{prompt}[/dim]"
        if default:
            box_content += f"\n[dim]Default: {default}[/dim]"
        return Panel(box_content, border_style="blue", padding=(1, 2))

    # Step 1: Ticker symbol
    console.print(
        create_question_box(
            "Step 1: Ticker Symbol",
            "Enter the exact ticker symbol to analyze, including exchange suffix when needed (examples: SPY, CNC.TO, 7203.T, 0700.HK)",
            "SPY",
        )
    )
    selected_ticker = get_ticker()
    asset_type = detect_asset_type(selected_ticker)
    console.print(
        f"[green]Detected asset type:[/green] {asset_type.value}"
    )

    # Step 2: Analysis date
    default_date = datetime.datetime.now().strftime("%Y-%m-%d")
    console.print(
        create_question_box(
            "Step 2: Analysis Date",
            "Enter the analysis date (YYYY-MM-DD)",
            default_date,
        )
    )
    analysis_date = get_analysis_date()

    # Step 3: Output language
    console.print(
        create_question_box(
            "Step 3: Output Language",
            "Select the language for analyst reports and final decision"
        )
    )
    output_language = ask_output_language()

    # Step 4: Select analysts
    console.print(
        create_question_box(
            "Step 4: Analysts Team", "Select your LLM analyst agents for the analysis"
        )
    )
    selected_analysts = select_analysts(asset_type)
    console.print(
        f"[green]Selected analysts:[/green] {', '.join(analyst.value for analyst in selected_analysts)}"
    )

    # Step 5: Research depth
    console.print(
        create_question_box(
            "Step 5: Research Depth", "Select your research depth level"
        )
    )
    selected_research_depth = select_research_depth()

    # Step 6: LLM Provider
    console.print(
        create_question_box(
            "Step 6: LLM Provider", "Select your LLM provider"
        )
    )
    selected_llm_provider, backend_url = select_llm_provider()

    # Providers with regional endpoints prompt for the region as a secondary
    # step so the main dropdown stays clean (mainland China and international
    # accounts cannot share API keys).
    if selected_llm_provider == "qwen":
        selected_llm_provider, backend_url = ask_qwen_region()
    elif selected_llm_provider == "minimax":
        selected_llm_provider, backend_url = ask_minimax_region()
    elif selected_llm_provider == "glm":
        selected_llm_provider, backend_url = ask_glm_region()

    # For Ollama, surface the resolved endpoint (OLLAMA_BASE_URL vs default)
    # before model selection so it's obvious where we're connecting.
    if selected_llm_provider == "ollama":
        confirm_ollama_endpoint(backend_url)

    # Confirm the provider's API key is present; prompt the user to paste
    # one and persist it to .env if it's missing, so the analysis run
    # doesn't fail later at the first API call.
    ensure_api_key(selected_llm_provider)

    # Step 7: Thinking agents
    console.print(
        create_question_box(
            "Step 7: Thinking Agents", "Select your thinking agents for analysis"
        )
    )
    selected_shallow_thinker = select_shallow_thinking_agent(selected_llm_provider)
    selected_deep_thinker = select_deep_thinking_agent(selected_llm_provider)

    # Step 8: Provider-specific thinking configuration
    thinking_level = None
    reasoning_effort = None
    anthropic_effort = None

    provider_lower = selected_llm_provider.lower()
    if provider_lower == "google":
        console.print(
            create_question_box(
                "Step 8: Thinking Mode",
                "Configure Gemini thinking mode"
            )
        )
        thinking_level = ask_gemini_thinking_config()
    elif provider_lower == "openai":
        console.print(
            create_question_box(
                "Step 8: Reasoning Effort",
                "Configure OpenAI reasoning effort level"
            )
        )
        reasoning_effort = ask_openai_reasoning_effort()
    elif provider_lower == "anthropic":
        console.print(
            create_question_box(
                "Step 8: Effort Level",
                "Configure Claude effort level"
            )
        )
        anthropic_effort = ask_anthropic_effort()

    return {
        "ticker": selected_ticker,
        "asset_type": asset_type.value,
        "analysis_date": analysis_date,
        "analysts": selected_analysts,
        "research_depth": selected_research_depth,
        "llm_provider": selected_llm_provider.lower(),
        "backend_url": backend_url,
        "shallow_thinker": selected_shallow_thinker,
        "deep_thinker": selected_deep_thinker,
        "google_thinking_level": thinking_level,
        "openai_reasoning_effort": reasoning_effort,
        "anthropic_effort": anthropic_effort,
        "output_language": output_language,
    }


def get_ticker():
    """Get ticker symbol from user input, preserving exchange suffixes."""
    # typer.prompt strips trailing dot-suffixes on some shells (e.g. 000404.SH
    # collapses to 000404). questionary.text reads the raw line.
    ticker = questionary.text(
        "",
        validate=lambda value: (
            not value.strip()
            or (
                all(ch.isalnum() or ch in "._-^" for ch in value.strip())
                and len(value.strip()) <= 32
            )
        )
        or "Please enter a valid ticker symbol, e.g. AAPL, 000404.SZ, 0700.HK.",
    ).ask()

    if ticker is None:
        console.print("\n[red]No ticker symbol provided. Exiting...[/red]")
        raise typer.Exit(1)

    return (ticker.strip() or "SPY").upper()


def get_analysis_date():
    """Get the analysis date from user input."""
    while True:
        date_str = typer.prompt(
            "", default=datetime.datetime.now().strftime("%Y-%m-%d")
        )
        try:
            # Validate date format and ensure it's not in the future
            analysis_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if analysis_date.date() > datetime.datetime.now().date():
                console.print("[red]Error: Analysis date cannot be in the future[/red]")
                continue
            return date_str
        except ValueError:
            console.print(
                "[red]Error: Invalid date format. Please use YYYY-MM-DD[/red]"
            )


def display_complete_report(final_state):
    """Display the complete analysis report sequentially (avoids truncation)."""
    console.print()
    console.print(Rule("Complete Analysis Report", style="bold green"))

    # I. Analyst Team Reports
    analysts = []
    if final_state.get("market_report"):
        analysts.append(("Market Analyst", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analysts.append(("Sentiment Analyst", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analysts.append(("News Analyst", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analysts.append(("Fundamentals Analyst", final_state["fundamentals_report"]))
    if analysts:
        console.print(Panel("[bold]I. Analyst Team Reports[/bold]", border_style="cyan"))
        for title, content in analysts:
            console.print(Panel(Markdown(content), title=title, border_style="blue", padding=(1, 2)))

    # II. Research Team Reports
    if final_state.get("investment_debate_state"):
        debate = final_state["investment_debate_state"]
        research = []
        if debate.get("bull_history"):
            research.append(("Bull Researcher", debate["bull_history"]))
        if debate.get("bear_history"):
            research.append(("Bear Researcher", debate["bear_history"]))
        if debate.get("judge_decision"):
            research.append(("Research Manager", debate["judge_decision"]))
        if research:
            console.print(Panel("[bold]II. Research Team Decision[/bold]", border_style="magenta"))
            for title, content in research:
                console.print(Panel(Markdown(content), title=title, border_style="blue", padding=(1, 2)))

    # III. Trading Team
    if final_state.get("trader_investment_plan"):
        console.print(Panel("[bold]III. Trading Team Plan[/bold]", border_style="yellow"))
        console.print(Panel(Markdown(final_state["trader_investment_plan"]), title="Trader", border_style="blue", padding=(1, 2)))

    # IV. Risk Management Team
    if final_state.get("risk_debate_state"):
        risk = final_state["risk_debate_state"]
        risk_reports = []
        if risk.get("aggressive_history"):
            risk_reports.append(("Aggressive Analyst", risk["aggressive_history"]))
        if risk.get("conservative_history"):
            risk_reports.append(("Conservative Analyst", risk["conservative_history"]))
        if risk.get("neutral_history"):
            risk_reports.append(("Neutral Analyst", risk["neutral_history"]))
        if risk_reports:
            console.print(Panel("[bold]IV. Risk Management Team Decision[/bold]", border_style="red"))
            for title, content in risk_reports:
                console.print(Panel(Markdown(content), title=title, border_style="blue", padding=(1, 2)))

        # V. Portfolio Manager Decision
        if risk.get("judge_decision"):
            console.print(Panel("[bold]V. Portfolio Manager Decision[/bold]", border_style="green"))
            console.print(Panel(Markdown(risk["judge_decision"]), title="Portfolio Manager", border_style="blue", padding=(1, 2)))


def update_research_team_status(status):
    """Update status for research team members (not Trader)."""
    research_team = ["Bull Researcher", "Bear Researcher", "Research Manager"]
    for agent in research_team:
        message_buffer.update_agent_status(agent, status)


# Ordered list of analysts for status transitions
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


def update_analyst_statuses(message_buffer, chunk, wall_time_tracker=None):
    """Update analyst statuses based on accumulated report state.

    Logic:
    - Store new report content from the current chunk if present
    - Check accumulated report_sections (not just current chunk) for status
    - Analysts with reports = completed
    - First analyst without report = in_progress
    - Remaining analysts without reports = pending
    - When all analysts done, set Bull Researcher to in_progress
    """
    selected = message_buffer.selected_analysts
    found_active = False

    if wall_time_tracker is not None:
        sync_analyst_tracker_from_chunk(wall_time_tracker, chunk)

    for analyst_key in ANALYST_ORDER:
        if analyst_key not in selected:
            continue

        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        report_key = ANALYST_REPORT_MAP[analyst_key]

        # Capture new report content from current chunk
        if chunk.get(report_key):
            message_buffer.update_report_section(report_key, chunk[report_key])

        # Determine status from accumulated sections, not just current chunk
        has_report = bool(message_buffer.report_sections.get(report_key))

        if has_report:
            message_buffer.update_agent_status(agent_name, "completed")
        elif not found_active:
            message_buffer.update_agent_status(agent_name, "in_progress")
            found_active = True
        else:
            message_buffer.update_agent_status(agent_name, "pending")

    # When all analysts complete, transition research team to in_progress
    if not found_active and selected:
        if message_buffer.agent_status.get("Bull Researcher") == "pending":
            message_buffer.update_agent_status("Bull Researcher", "in_progress")

def extract_content_string(content):
    """Extract string content from various message formats.
    Returns None if no meaningful text content is found.
    """
    import ast

    def is_empty(val):
        """Check if value is empty using Python's truthiness."""
        if val is None or val == '':
            return True
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return True
            try:
                return not bool(ast.literal_eval(s))
            except (ValueError, SyntaxError):
                return False  # Can't parse = real text
        return not bool(val)

    if is_empty(content):
        return None

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, dict):
        text = content.get('text', '')
        return text.strip() if not is_empty(text) else None

    if isinstance(content, list):
        text_parts = [
            item.get('text', '').strip() if isinstance(item, dict) and item.get('type') == 'text'
            else (item.strip() if isinstance(item, str) else '')
            for item in content
        ]
        result = ' '.join(t for t in text_parts if t and not is_empty(t))
        return result if result else None

    return str(content).strip() if not is_empty(content) else None


def classify_message_type(message) -> tuple[str, str | None]:
    """Classify LangChain message into display type and extract content.

    Returns:
        (type, content) - type is one of: User, Agent, Data, Control
                        - content is extracted string or None
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    content = extract_content_string(getattr(message, 'content', None))

    if isinstance(message, HumanMessage):
        if content and content.strip() == "Continue":
            return ("Control", content)
        return ("User", content)

    if isinstance(message, ToolMessage):
        return ("Data", content)

    if isinstance(message, AIMessage):
        return ("Agent", content)

    # Fallback for unknown types
    return ("System", content)


def format_tool_args(args, max_length=80) -> str:
    """Format tool arguments for terminal display."""
    result = str(args)
    if len(result) > max_length:
        return result[:max_length - 3] + "..."
    return result

def _normalize_reddit_market(market: str) -> str:
    normalized = market.strip().lower()
    get_subreddits_for_market(normalized)
    return normalized


def run_analysis(checkpoint: bool = False, reddit_market: Optional[str] = None):
    # First get all user selections
    selections = get_user_selections()

    # Create config with selected research depth
    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = selections["research_depth"]
    config["max_risk_discuss_rounds"] = selections["research_depth"]
    config["quick_think_llm"] = selections["shallow_thinker"]
    config["deep_think_llm"] = selections["deep_thinker"]
    config["backend_url"] = selections["backend_url"]
    config["llm_provider"] = selections["llm_provider"].lower()
    # Provider-specific thinking configuration
    config["google_thinking_level"] = selections.get("google_thinking_level")
    config["openai_reasoning_effort"] = selections.get("openai_reasoning_effort")
    config["anthropic_effort"] = selections.get("anthropic_effort")
    config["output_language"] = selections.get("output_language", "English")
    config["checkpoint_enabled"] = checkpoint
    if reddit_market is not None:
        config["reddit_market"] = _normalize_reddit_market(reddit_market)

    # Per-run directory where dataflow fetchers append full tool responses.
    # Set before the graph is constructed so set_config() picks it up.
    config["tool_response_log_dir"] = str(
        Path(config["results_dir"])
        / selections["ticker"]
        / selections["analysis_date"]
        / "tool_responses"
    )

    # Create stats callback handler for tracking LLM/tool calls
    stats_handler = StatsCallbackHandler()

    # Normalize analyst selection to predefined order (selection is a 'set', order is fixed)
    selected_set = {analyst.value for analyst in selections["analysts"]}
    selected_analyst_keys = [a for a in ANALYST_ORDER if a in selected_set]
    analyst_execution_plan = build_analyst_execution_plan(
        selected_analyst_keys,
        concurrency_limit=config["analyst_concurrency_limit"],
    )
    analyst_wall_time_tracker = AnalystWallTimeTracker(analyst_execution_plan)

    # Initialize the graph with callbacks bound to LLMs
    graph = TradingAgentsGraph(
        selected_analyst_keys,
        config=config,
        debug=True,
        callbacks=[stats_handler],
    )

    # Initialize message buffer with selected analysts
    message_buffer.init_for_analysis(selected_analyst_keys)

    # Track start time for elapsed display
    start_time = time.time()

    # Create result directory
    results_dir = Path(config["results_dir"]) / selections["ticker"] / selections["analysis_date"]
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir = results_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    log_file = results_dir / "message_tool.log"
    log_file.touch(exist_ok=True)

    def save_message_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, message_type, content = obj.messages[-1]
            content = content.replace("\n", " ")  # Replace newlines with spaces
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [{message_type}] {content}\n")
        return wrapper
    
    def save_tool_call_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
            timestamp, tool_name, args = obj.tool_calls[-1]
            args_str = ", ".join(f"{k}={v}" for k, v in args.items())
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} [Tool Call] {tool_name}({args_str})\n")
        return wrapper

    def save_report_section_decorator(obj, func_name):
        func = getattr(obj, func_name)
        @wraps(func)
        def wrapper(section_name, content):
            func(section_name, content)
            if section_name in obj.report_sections and obj.report_sections[section_name] is not None:
                content = obj.report_sections[section_name]
                if content:
                    file_name = f"{section_name}.md"
                    text = "\n".join(str(item) for item in content) if isinstance(content, list) else content
                    with open(report_dir / file_name, "w", encoding="utf-8") as f:
                        f.write(text)
        return wrapper

    message_buffer.add_message = save_message_decorator(message_buffer, "add_message")
    message_buffer.add_tool_call = save_tool_call_decorator(message_buffer, "add_tool_call")
    message_buffer.update_report_section = save_report_section_decorator(message_buffer, "update_report_section")

    # Now start the display layout
    layout = create_layout()

    with Live(layout, refresh_per_second=4) as live:
        # Initial display
        update_display(layout, stats_handler=stats_handler, start_time=start_time)

        # Add initial messages
        message_buffer.add_message("System", f"Selected ticker: {selections['ticker']}")
        message_buffer.add_message("System", f"Detected asset type: {selections['asset_type']}")
        message_buffer.add_message(
            "System", f"Analysis date: {selections['analysis_date']}"
        )
        message_buffer.add_message(
            "System",
            f"Selected analysts: {', '.join(analyst.value for analyst in selections['analysts'])}",
        )
        if "social" in selected_analyst_keys:
            message_buffer.add_message(
                "System", f"Reddit market mode: {config.get('reddit_market', 'india')}"
            )
        update_display(layout, stats_handler=stats_handler, start_time=start_time)

        # Update agent status to in_progress for the first analyst
        first_analyst = get_initial_analyst_node(analyst_execution_plan)
        message_buffer.update_agent_status(first_analyst, "in_progress")
        analyst_wall_time_tracker.mark_started(selected_analyst_keys[0])
        update_display(layout, stats_handler=stats_handler, start_time=start_time)

        # Create spinner text
        spinner_text = (
            f"Analyzing {selections['ticker']} on {selections['analysis_date']}..."
        )
        update_display(layout, spinner_text, stats_handler=stats_handler, start_time=start_time)

        # Initialize state and get graph args with callbacks
        init_agent_state = graph.propagator.create_initial_state(
            selections["ticker"],
            selections["analysis_date"],
            asset_type=selections["asset_type"],
        )
        # Pass callbacks to graph config for tool execution tracking
        # (LLM tracking is handled separately via LLM constructor)
        args = graph.propagator.get_graph_args(callbacks=[stats_handler])

        # Stream the analysis
        trace = []
        for chunk in graph.graph.stream(init_agent_state, **args):
            # Process all messages in chunk, deduplicating by message ID
            for message in chunk.get("messages", []):
                msg_id = getattr(message, "id", None)
                if msg_id is not None:
                    if msg_id in message_buffer._processed_message_ids:
                        continue
                    message_buffer._processed_message_ids.add(msg_id)

                msg_type, content = classify_message_type(message)
                if content and content.strip():
                    message_buffer.add_message(msg_type, content)

                if hasattr(message, "tool_calls") and message.tool_calls:
                    for tool_call in message.tool_calls:
                        if isinstance(tool_call, dict):
                            message_buffer.add_tool_call(tool_call["name"], tool_call["args"])
                        else:
                            message_buffer.add_tool_call(tool_call.name, tool_call.args)

            # Update analyst statuses based on report state (runs on every chunk)
            update_analyst_statuses(
                message_buffer,
                chunk,
                wall_time_tracker=analyst_wall_time_tracker,
            )

            # Research Team - Handle Investment Debate State
            if chunk.get("investment_debate_state"):
                debate_state = chunk["investment_debate_state"]
                bull_hist = debate_state.get("bull_history", "").strip()
                bear_hist = debate_state.get("bear_history", "").strip()
                judge = debate_state.get("judge_decision", "").strip()

                # Only update status when there's actual content
                if bull_hist or bear_hist:
                    update_research_team_status("in_progress")
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
                    update_research_team_status("completed")
                    message_buffer.update_agent_status("Trader", "in_progress")

            # Trading Team
            if chunk.get("trader_investment_plan"):
                message_buffer.update_report_section(
                    "trader_investment_plan", chunk["trader_investment_plan"]
                )
                if message_buffer.agent_status.get("Trader") != "completed":
                    message_buffer.update_agent_status("Trader", "completed")
                    message_buffer.update_agent_status("Aggressive Analyst", "in_progress")

            # Risk Management Team - Handle Risk Debate State
            if chunk.get("risk_debate_state"):
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
                    if message_buffer.agent_status.get("Portfolio Manager") != "completed":
                        message_buffer.update_agent_status("Portfolio Manager", "in_progress")
                        message_buffer.update_report_section(
                            "final_trade_decision", f"### Portfolio Manager Decision\n{judge}"
                        )
                        message_buffer.update_agent_status("Aggressive Analyst", "completed")
                        message_buffer.update_agent_status("Conservative Analyst", "completed")
                        message_buffer.update_agent_status("Neutral Analyst", "completed")
                        message_buffer.update_agent_status("Portfolio Manager", "completed")

            # Update the display
            update_display(layout, stats_handler=stats_handler, start_time=start_time)

            trace.append(chunk)

        # Streamed chunks are per-node deltas, not full state. Merge them
        # so every report field populated across the run is present.
        final_state = {}
        for chunk in trace:
            final_state.update(chunk)
        decision = graph.process_signal(final_state["final_trade_decision"])

        try:
            from tradingagents.swing import SwingPositionBook
            from tradingagents.momentum import MomentumPositionBook
            from tradingagents.screening.universe import _normalise_symbol

            ticker_ns = _normalise_symbol(selections["ticker"])
            swing_book = SwingPositionBook(DEFAULT_CONFIG.copy())
            if swing_book.set_ai_rating(ticker_ns, decision):
                console.print(f"[dim]Swing book AI rating saved:[/dim] {decision}")
            momentum_book = MomentumPositionBook(DEFAULT_CONFIG.copy())
            if momentum_book.set_ai_rating(ticker_ns, decision):
                console.print(f"[dim]Momentum book AI rating saved:[/dim] {decision}")
        except Exception:  # noqa: BLE001
            pass

        # Update all agent statuses to completed
        for agent in message_buffer.agent_status:
            message_buffer.update_agent_status(agent, "completed")

        message_buffer.add_message(
            "System", f"Completed analysis for {selections['analysis_date']}"
        )
        message_buffer.add_message("System", analyst_wall_time_tracker.format_summary())

        # Update final report sections
        for section in message_buffer.report_sections.keys():
            if section in final_state:
                message_buffer.update_report_section(section, final_state[section])

        update_display(layout, stats_handler=stats_handler, start_time=start_time)

    # Post-analysis prompts (outside Live context for clean interaction)
    console.print("\n[bold cyan]Analysis Complete![/bold cyan]\n")
    console.print(f"[dim]{analyst_wall_time_tracker.format_summary()}[/dim]")

    # Prompt to save report
    save_choice = typer.prompt("Save report?", default="Y").strip().upper()
    if save_choice in ("Y", "YES", ""):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = Path.cwd() / "reports" / f"{selections['ticker']}_{timestamp}"
        save_path_str = typer.prompt(
            "Save path (press Enter for default)",
            default=str(default_path)
        ).strip()
        save_path = Path(save_path_str)
        try:
            report_file = save_report_to_disk(final_state, selections["ticker"], save_path)
            console.print(f"\n[green]✓ Report saved to:[/green] {save_path.resolve()}")
            console.print(f"  [dim]Complete report:[/dim] {report_file.name}")
        except Exception as e:
            console.print(f"[red]Error saving report: {e}[/red]")

    # Prompt to display full report
    display_choice = typer.prompt("\nDisplay full report on screen?", default="Y").strip().upper()
    if display_choice in ("Y", "YES", ""):
        display_complete_report(final_state)


@app.command()
def analyze(
    checkpoint: bool = typer.Option(
        False,
        "--checkpoint",
        help="Enable checkpoint/resume: save state after each node so a crashed run can resume.",
    ),
    clear_checkpoints: bool = typer.Option(
        False,
        "--clear-checkpoints",
        help="Delete all saved checkpoints before running (force fresh start).",
    ),
    reddit_market: Optional[str] = typer.Option(
        None,
        "--market",
        help="Reddit sentiment market mode: us or india. Defaults to config/env.",
    ),
):
    if clear_checkpoints:
        from tradingagents.graph.checkpointer import clear_all_checkpoints
        n = clear_all_checkpoints(DEFAULT_CONFIG["data_cache_dir"])
        console.print(f"[yellow]Cleared {n} checkpoint(s).[/yellow]")
    run_analysis(checkpoint=checkpoint, reddit_market=reddit_market)


def _print_tech_report(sym: str, report_text: str) -> None:
    """Emit the Market Analyst report as raw markdown on stdout."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(report_text.rstrip(), flush=True)


@app.command("tech-analyze")
def tech_analyze(
    ticker: Optional[str] = typer.Option(
        None, "--ticker", "-t", help="Single ticker to analyze."
    ),
    watchlist: bool = typer.Option(
        False, "--watchlist", "-w", help="Use saved default watchlist."
    ),
    watchlist_file: Optional[str] = typer.Option(
        None, "--watchlist-file", help="Custom watchlist file path."
    ),
    date: Optional[str] = typer.Option(
        None, "--date", help="As-of date (YYYY-MM-DD). Default: today."
    ),
    save: bool = typer.Option(
        True, "--save/--no-save", help="Save report to disk."
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Custom output directory for saved reports."
    ),
    language: Optional[str] = typer.Option(
        None, "--language", help="Output language for the technical report."
    ),
):
    """Quick technical analysis using only the Market Analyst agent."""
    from tradingagents.analysis.tech_analyze import (
        run_tech_analyze,
        save_tech_report,
    )
    from tradingagents.analysis.watchlist import load_watchlist

    sources = [bool(ticker), watchlist, bool(watchlist_file)]
    if sum(sources) != 1:
        console.print(
            "[red]Specify exactly one of: --ticker, --watchlist, or --watchlist-file[/red]"
        )
        raise typer.Exit(1)

    config = DEFAULT_CONFIG.copy()
    if language:
        config["output_language"] = language

    ensure_api_key(config.get("llm_provider", "openai"))

    trade_date = date or datetime.date.today().isoformat()

    if ticker:
        tickers = [normalize_ticker_symbol(ticker)]
    elif watchlist:
        tickers = load_watchlist()
        if not tickers:
            console.print(
                "[red]Watchlist is empty. Add tickers with: "
                "tradingagents watchlist add TICKER[/red]"
            )
            raise typer.Exit(1)
    else:
        tickers = load_watchlist(watchlist_file)
        if not tickers:
            console.print(f"[red]No symbols found in watchlist file: {watchlist_file}[/red]")
            raise typer.Exit(1)

    stats_handler = StatsCallbackHandler()
    reports_base = Path(output_dir) if output_dir else Path(config["tech_analyze_reports_dir"])

    console.print(Panel.fit(
        f"[bold]Quick technical analysis[/bold]\n"
        f"Tickers: {', '.join(tickers)}\n"
        f"As of: {trade_date}\n"
        f"Language: {config.get('output_language', 'English')}",
        title="Tech Analyze",
    ))

    results = []
    for i, sym in enumerate(tickers):
        if i > 0:
            console.print(Rule(style="dim"))

        asset_type = detect_asset_type(sym).value
        config["tool_response_log_dir"] = str(
            Path(config["results_dir"]) / sym / trade_date / "tool_responses"
        )

        with console.status(f"[bold green]Analyzing {sym}...", spinner="dots"):
            result = run_tech_analyze(
                sym,
                trade_date,
                config=config,
                callbacks=[stats_handler],
                asset_type=asset_type,
            )
        results.append(result)

        report_text = result.get("market_report", "").strip()

        if save:
            save_path = reports_base / sym / trade_date
            try:
                report_file = save_tech_report(result, save_path)
                console.print(
                    f"[green]Report saved:[/green] {save_path.resolve()}\n"
                    f"  [dim]Complete report:[/dim] {report_file.name}"
                )
            except Exception as e:
                console.print(f"[red]Error saving report for {sym}: {e}[/red]")

        if report_text:
            _print_tech_report(sym, report_text)
        else:
            console.print(f"[yellow]No market report generated for {sym}.[/yellow]")


@app.command("tech-desk-process")
def tech_desk_process(
    reports_dir: Optional[str] = typer.Option(
        None, "--reports-dir", help="Folder of saved tech-analyze reports."
    ),
    date: Optional[str] = typer.Option(
        None, "--date", help="Process as-of date (YYYY-MM-DD). Default: today."
    ),
    apply_replacements: bool = typer.Option(
        False,
        "--apply-replacements",
        help="After process, apply any queued portfolio replacements from today's log.",
    ),
):
    """Load saved tech-analyze reports, run PM batch, execute opens/closes."""
    from tradingagents.tech_desk import run_tech_desk_process
    from tradingagents.tech_desk.manager import TechDeskPaperTradeManager

    config = DEFAULT_CONFIG.copy()
    ensure_api_key(config.get("llm_provider", "openai"))

    console.print(Panel.fit(
        f"[bold]Tech Desk batch process[/bold]\n"
        f"Reports: {reports_dir or config['tech_analyze_reports_dir']}\n"
        f"Watchlist: {config.get('tech_watchlist_path', '~/.tradingagents/watchlist.txt')}\n"
        f"Max slots: {config.get('tech_desk_max_positions', 10)} · "
        f"Min confidence: {config.get('tech_desk_min_confidence', 60)} · "
        f"Max report age: {config.get('tech_desk_max_report_age_days', 14)}d",
        title="tech-desk-process",
    ))

    with console.status("[bold green]Processing batch...", spinner="dots") as status:
        report = run_tech_desk_process(
            config,
            reports_dir=reports_dir,
            process_date=date,
            progress=lambda m: status.update(f"[bold green]{m}"),
        )

    if report.get("skipped"):
        reason = report.get("reason")
        if reason == "empty_watchlist":
            console.print("[yellow]Skipped:[/yellow] watchlist is empty — add tickers first.")
        else:
            console.print(f"[yellow]Skipped:[/yellow] {reason}")
        raise typer.Exit()

    decision_md = report.get("decision_markdown")
    if decision_md:
        console.print(Panel(decision_md, title="PM decision", border_style="cyan"))

    if report.get("pm_error"):
        console.print(f"[red]PM error:[/red] {report['pm_error']}")

    summary = report.get("summary") or {}
    console.print(
        f"Watchlist: {report.get('watchlist_count')} · candidates: {report.get('candidates')} · "
        f"opened: {summary.get('opened', len(report.get('opened', [])))} · "
        f"waits: {summary.get('waits', len(report.get('waits', [])))} · "
        f"closes: {summary.get('closes', len(report.get('closes', [])))} · "
        f"open: {report.get('open_positions')}"
    )
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")
    if report.get("waits"):
        console.print(f"  [cyan]pending zones:[/cyan] {', '.join(report['waits'])}")
    stale = report.get("stale_tickers") or []
    if stale:
        console.print(
            f"  [dim]stale reports skipped (>{config.get('tech_desk_max_report_age_days', 14)}d):[/dim] "
            f"{', '.join(stale)}"
        )
    skipped = report.get("skipped") or []
    if skipped:
        for s in skipped[:8]:
            if isinstance(s, dict):
                console.print(f"  [dim]skip {s.get('ticker')}:[/dim] {s.get('reason')}")
        if len(skipped) > 8:
            console.print(f"  [dim]… and {len(skipped) - 8} more skips[/dim]")

    if apply_replacements:
        console.print(
            "[dim]Foreclosure/replacements disabled — Tech Desk exits via stop/target only.[/dim]"
        )

    console.print("[dim]Full log:[/dim] [bold]tradingagents tech-desk-report[/bold]")


@app.command("rs-desk-process")
def rs_desk_process(
    reports_dir: Optional[str] = typer.Option(
        None, "--reports-dir", help="Shared tech reports folder (default: tech_analyze_reports_dir)."
    ),
    date: Optional[str] = typer.Option(
        None, "--date", help="Process as-of date (YYYY-MM-DD). Default: today."
    ),
):
    """RS Desk PM over latest shared reports (last screen + open/pending). Separate book."""
    from tradingagents.rs_desk import run_rs_desk_process

    config = DEFAULT_CONFIG.copy()
    ensure_api_key(config.get("llm_provider", "openai"))

    console.print(Panel.fit(
        f"[bold]RS Desk batch process[/bold]\n"
        f"Shared reports: {reports_dir or config['tech_analyze_reports_dir']}\n"
        f"Book: {config.get('rs_desk_book_path')}\n"
        f"Max slots: {config.get('rs_desk_max_positions', 20)} · "
        f"Min confidence: {config.get('rs_desk_min_confidence', 60)} · "
        f"Max report age: {config.get('rs_desk_max_report_age_days', 14)}d\n"
        "[dim]Candidates: last screen shortlist ∪ RS open/pending "
        "(latest report on disk wins — same folder as Tech Desk)[/dim]",
        title="rs-desk-process",
    ))

    with console.status("[bold green]RS Desk processing...", spinner="dots") as status:
        report = run_rs_desk_process(
            config,
            reports_dir=reports_dir,
            process_date=date,
            progress=lambda m: status.update(f"[bold green]{m}"),
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    decision_md = report.get("decision_markdown")
    if decision_md:
        console.print(Panel(decision_md, title="RS Desk PM decision", border_style="cyan"))

    if report.get("pm_error"):
        console.print(f"[red]PM error:[/red] {report['pm_error']}")

    summary = report.get("summary") or {}
    console.print(
        f"Candidates: {report.get('candidates')} · "
        f"opened: {summary.get('opened', len(report.get('opened', [])))} · "
        f"waits: {summary.get('waits', len(report.get('waits', [])))} · "
        f"open: {report.get('open_positions')}"
    )
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")
    if report.get("waits"):
        console.print(f"  [cyan]pending zones:[/cyan] {', '.join(report['waits'])}")
    skip_entries = report.get("skip_entries") or []
    if skip_entries:
        for s in skip_entries[:8]:
            if isinstance(s, dict):
                console.print(f"  [dim]skip {s.get('ticker')}:[/dim] {s.get('reason')}")


@app.command("rs-desk-daily")
def rs_desk_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op."),
):
    """Rules-only RS Desk daily: stop/target/time exits + pending zone fills."""
    from tradingagents.rs_desk import run_rs_desk_daily

    config = DEFAULT_CONFIG.copy()
    with console.status("[bold green]RS Desk daily...", spinner="dots"):
        report = run_rs_desk_daily(config, force=force)

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]rs-desk daily[/bold]\n"
        f"Exits: {len(report.get('exits', []))} · zone fills: {len(report.get('zone_fills', []))} · "
        f"open: {report.get('open_positions')} · pending: {report.get('pending_entries')}",
        title="RS Desk daily",
    ))


@app.command("rs-desk-positions")
def rs_desk_positions():
    """Show RS Desk paper positions, pending zones, and stats."""
    from tradingagents.rs_desk import as_tech_desk_config
    from tradingagents.tech_desk.book import TechDeskPositionBook

    book = TechDeskPositionBook(as_tech_desk_config(DEFAULT_CONFIG.copy()))
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    pending = book.pending_entries()

    if not book.positions and not pending:
        console.print(Panel.fit(
            "No RS Desk positions yet. Run [bold]tradingagents screen[/bold] "
            "(MA -> RS Desk PM) or [bold]rs-desk-process[/bold].",
            title="RS Desk",
        ))
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]RS Desk[/bold] · strategy={book.strategy_name}\n"
        f"Open: {len(open_positions)} / {book.max_positions} · pending: {len(pending)}\n"
        f"Book: {book.path}",
        title="rs-desk-positions",
    ))
    if open_positions:
        from rich.table import Table
        from rich import box

        t = Table(box=box.SIMPLE_HEAD, title="Open")
        t.add_column("Ticker", style="bold")
        t.add_column("Entry", justify="right")
        t.add_column("Stop", justify="right")
        t.add_column("T1", justify="right")
        t.add_column("Conf", justify="right")
        for p in open_positions:
            t.add_row(
                p.get("ticker", ""),
                f"{float(p.get('entry_price') or 0):.2f}",
                f"{float(p.get('stop_loss') or 0):.2f}",
                f"{float(p.get('target_1') or 0):.2f}",
                str(p.get("confidence") or "—"),
            )
        console.print(t)
    if pending:
        console.print("\n[cyan]Pending zones:[/cyan]")
        for row in pending:
            console.print(
                f"  {row.get('ticker')} zone "
                f"{row.get('zone_low')}-{row.get('zone_high')} "
                f"SL {row.get('stop_loss')} T1 {row.get('target_1')}"
            )
    o = stats.get("overall") or {}
    if o.get("trades"):
        console.print(
            f"\n[dim]Closed {o['trades']} · win {o.get('win_rate')}% · "
            f"P&L Rs {o.get('total_pnl', 0):,.0f}[/dim]"
        )


@app.command("tech-desk-apply-process")
def tech_desk_apply_process(
    date: Optional[str] = typer.Option(
        None, "--date", help="Process log date (YYYY-MM-DD). Default: today."
    ),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated replacement ids (foreclose->open)."
    ),
    yes: bool = typer.Option(False, "--yes", "-y", help="Apply all pending replacements."),
):
    """Deprecated no-op: Tech Desk foreclosure is disabled (exits via stop/target only)."""
    from tradingagents.tech_desk.manager import TechDeskPaperTradeManager

    config = DEFAULT_CONFIG.copy()
    manager = TechDeskPaperTradeManager(config)
    proc_date = date or datetime.datetime.now().strftime("%Y-%m-%d")
    _ = (ids, yes)  # kept for CLI compatibility
    result = manager.apply_pending_replacements(process_date=proc_date)
    console.print(
        f"[yellow]{result.get('message') or 'Tech Desk foreclosure is disabled.'}[/yellow]"
    )
    raise typer.Exit(0)


@app.command("tech-desk-daily")
def tech_desk_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
):
    """Rules-only daily job: stop/target/time exits + pending zone fills (no LLM)."""
    from tradingagents.tech_desk import run_tech_desk_daily

    config = DEFAULT_CONFIG.copy()
    with console.status("[bold green]Tech Desk daily...", spinner="dots"):
        report = run_tech_desk_daily(config, force=force)

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]tech-desk daily[/bold]\n"
        f"Exits: {len(report.get('exits', []))} · zone fills: {len(report.get('zone_fills', []))} · "
        f"open: {report.get('open_positions')} · pending: {report.get('pending_entries')}",
        title="Tech Desk daily",
    ))


@app.command("tech-desk-review")
def tech_desk_review(
    reports_dir: Optional[str] = typer.Option(
        None, "--reports-dir", help="Folder of saved tech-analyze reports."
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Execute CLOSE / tighten_stop / trail_stop on the book after review.",
    ),
):
    """Manual weekly LLM review of open Tech Desk positions."""
    from tradingagents.llm_clients import create_llm_client
    from tradingagents.tech_desk import TechDeskPaperTradeManager

    config = DEFAULT_CONFIG.copy()
    ensure_api_key(config.get("llm_provider", "openai"))

    client = create_llm_client(
        provider=config["llm_provider"],
        model=config["quick_think_llm"],
        base_url=config.get("backend_url"),
    )
    manager = TechDeskPaperTradeManager(config)

    with console.status("[bold green]Running weekly review...", spinner="dots"):
        result = manager.run_review(
            client.get_llm(),
            reports_dir=reports_dir or config.get("tech_analyze_reports_dir"),
            apply=apply,
        )

    if result.get("message") == "no open positions":
        console.print("[yellow]No open Tech Desk positions to review.[/yellow]")
        raise typer.Exit()

    md = result.get("review_markdown")
    if md:
        console.print(Markdown(md))
    else:
        console.print("[yellow]Review did not produce structured output.[/yellow]")

    applied = result.get("applied")
    if applied:
        if applied.get("closed"):
            console.print(f"[green]Applied closes:[/green] {', '.join(applied['closed'])}")
        if applied.get("stops_raised"):
            console.print(f"[green]Stops raised:[/green] {', '.join(applied['stops_raised'])}")
        if applied.get("skipped"):
            console.print(f"[dim]Skipped {len(applied['skipped'])} review action(s).[/dim]")


@app.command("tech-desk-positions")
def tech_desk_positions():
    """Show Tech Desk paper positions, pending zone entries, and stats."""
    from tradingagents.tech_desk import STRATEGY_NAME, TechDeskPositionBook

    book = TechDeskPositionBook(DEFAULT_CONFIG.copy())
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    pending = book.pending_entries()

    if not book.positions and not pending:
        console.print(Panel.fit(
            "No Tech Desk positions yet. Run [bold]tradingagents tech-desk-process[/bold] "
            "after saving tech-analyze reports.",
            title="tech-desk",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("SL Rs", justify="right")
        t.add_column("T1 Rs", justify="right")
        t.add_column("Conf", justify="right")
        t.add_column("Bias")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                *open_meta_cells(p),
                f"{p['entry_price']:,.2f}",
                f"{p['stop_loss']:,.2f}",
                f"{p.get('target_1', 0):,.2f}",
                str(p.get("confidence", "—")),
                p.get("bias", "—"),
            )
        console.print(t)

    closed = [p for p in book.positions if p.get("status") == "closed"]
    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title=f"{STRATEGY_NAME} — closed positions")

    if pending:
        console.print(f"\n[dim]Pending zone entries: {len(pending)}[/dim]")
        for pe in pending:
            console.print(
                f"  {pe['ticker']} · zone {pe.get('zone_low')}–{pe.get('zone_high')} · "
                f"conf {pe.get('confidence')}"
            )

    ov = stats.get("overall", {})
    console.print(
        f"\n[dim]Open {stats.get('open_positions', 0)} · closed {stats.get('closed_positions', 0)} · "
        f"win rate {ov.get('win_rate')}% · total P&L ₹{ov.get('total_pnl', 0):,.0f}[/dim]"
    )


@app.command("tech-desk-report")
def tech_desk_report():
    """Show Tech Desk portfolio stats and latest process/daily logs."""
    from tradingagents.tech_desk import TechDeskPaperTradeManager, TechDeskPositionBook

    book = TechDeskPositionBook(DEFAULT_CONFIG.copy())
    stats = book.stats()
    manager = TechDeskPaperTradeManager(DEFAULT_CONFIG.copy())
    process_report = manager.latest_process_report()
    daily_report = manager.latest_daily_report()

    ov = stats.get("overall", {})
    console.print(Panel.fit(
        f"[bold]Tech Desk stats[/bold]\n"
        f"Closed: {ov.get('trades', 0)} · win rate {ov.get('win_rate')}% · "
        f"avg return {ov.get('avg_return')}% · avg R {ov.get('avg_r')} · "
        f"total P&L ₹{ov.get('total_pnl', 0):,.0f}\n"
        f"Open: {stats.get('open_positions', 0)} · pending zones: {stats.get('pending_entries', 0)}",
        title="tech-desk-report",
    ))

    by_reason = stats.get("by_exit_reason") or {}
    if by_reason:
        t = Table(box=box.SIMPLE_HEAD, title="P&L by exit reason")
        t.add_column("Reason")
        t.add_column("Trades", justify="right")
        t.add_column("Win%", justify="right")
        t.add_column("Avg R", justify="right")
        t.add_column("P&L ₹", justify="right")
        for reason, agg in by_reason.items():
            t.add_row(
                reason,
                str(agg.get("trades", 0)),
                str(agg.get("win_rate") if agg.get("win_rate") is not None else "—"),
                str(agg.get("avg_r") if agg.get("avg_r") is not None else "—"),
                f"{agg.get('total_pnl', 0):,.0f}",
            )
        console.print(t)

    if not process_report and not daily_report and ov.get("trades", 0) == 0:
        console.print(
            "[yellow]No Tech Desk activity yet. Run tech-desk-process or tech-desk-daily.[/yellow]"
        )
        raise typer.Exit()

    if process_report:
        console.print(Panel.fit(
            f"[bold]Latest process[/bold] · {process_report.get('date')}\n"
            f"Opened: {len(process_report.get('opened', []))} · "
            f"waits: {len(process_report.get('waits', []))} · "
            f"open: {process_report.get('open_positions')}",
            title="Tech Desk process",
        ))
    if daily_report:
        console.print(Panel.fit(
            f"[bold]Latest daily[/bold] · {daily_report.get('date')}\n"
            f"Exits: {len(daily_report.get('exits', []))} · "
            f"zone fills: {len(daily_report.get('zone_fills', []))}",
            title="Tech Desk daily",
        ))


watchlist_app = typer.Typer(help="Manage the tech-analyze watchlist.")
app.add_typer(watchlist_app, name="watchlist")


@watchlist_app.command("show")
def watchlist_show():
    """Show saved watchlist tickers."""
    from tradingagents.analysis.watchlist import list_watchlist

    symbols = list_watchlist()
    if not symbols:
        console.print("[dim]Watchlist is empty.[/dim]")
        console.print(
            "[dim]Add tickers with: tradingagents watchlist add RELIANCE TCS[/dim]"
        )
        return

    table = Table(box=box.SIMPLE_HEAD, title="Tech-analyze watchlist")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Ticker", style="bold")
    for i, sym in enumerate(symbols, 1):
        table.add_row(str(i), sym)
    console.print(table)


@watchlist_app.command("add")
def watchlist_add(
    tickers: list[str] = typer.Argument(..., help="Ticker symbol(s) to add."),
):
    """Add ticker(s) to the watchlist."""
    from tradingagents.analysis.watchlist import add_to_watchlist

    updated = add_to_watchlist([normalize_ticker_symbol(t) for t in tickers])
    console.print(
        f"[green]Added {len(tickers)} ticker(s).[/green] "
        f"Watchlist now has {len(updated)} symbol(s)."
    )


@watchlist_app.command("remove")
def watchlist_remove(
    tickers: list[str] = typer.Argument(..., help="Ticker symbol(s) to remove."),
):
    """Remove ticker(s) from the watchlist."""
    from tradingagents.analysis.watchlist import remove_from_watchlist

    updated = remove_from_watchlist([normalize_ticker_symbol(t) for t in tickers])
    console.print(
        f"[green]Removed {len(tickers)} ticker(s).[/green] "
        f"Watchlist now has {len(updated)} symbol(s)."
    )


custom_ticker_app = typer.Typer(help="Manage custom tickers for price sync.")
app.add_typer(custom_ticker_app, name="custom-ticker")


@custom_ticker_app.command("list")
def custom_ticker_list():
    """Show custom tickers included in price sync."""
    from tradingagents.dataflows.custom_tickers import list_custom_tickers

    symbols = list_custom_tickers()
    if not symbols:
        console.print("[dim]Custom tickers list is empty.[/dim]")
        console.print(
            "[dim]Add tickers with: tradingagents custom-ticker add RELIANCE TCS[/dim]"
        )
        return

    table = Table(box=box.SIMPLE_HEAD, title="Custom price-sync tickers")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Ticker", style="bold")
    for i, sym in enumerate(symbols, 1):
        table.add_row(str(i), sym)
    console.print(table)


@custom_ticker_app.command("add")
def custom_ticker_add(
    tickers: list[str] = typer.Argument(..., help="Ticker symbol(s) to add."),
):
    """Add ticker(s) to the custom price-sync list."""
    from tradingagents.dataflows.custom_tickers import add_custom_ticker
    from tradingagents.dataflows.ohlcv_store import sync_symbol

    config = DEFAULT_CONFIG.copy()
    normalized = [normalize_ticker_symbol(t) for t in tickers]
    updated = add_custom_ticker(normalized)
    for sym in normalized:
        try:
            sync_symbol(sym, mode="incremental", cache_dir=config.get("data_cache_dir"))
        except Exception as e:  # noqa: BLE001
            console.print(f"[yellow]Price sync for {sym} failed:[/yellow] {e}")
    console.print(
        f"[green]Added {len(tickers)} ticker(s).[/green] "
        f"Custom list now has {len(updated)} symbol(s)."
    )


@custom_ticker_app.command("remove")
def custom_ticker_remove(
    tickers: list[str] = typer.Argument(..., help="Ticker symbol(s) to remove."),
):
    """Remove ticker(s) from the custom price-sync list."""
    from tradingagents.dataflows.custom_tickers import remove_custom_ticker

    updated = remove_custom_ticker([normalize_ticker_symbol(t) for t in tickers])
    console.print(
        f"[green]Removed {len(tickers)} ticker(s).[/green] "
        f"Custom list now has {len(updated)} symbol(s)."
    )


@app.command()
def sync():
    """Refresh the local dashboard snapshot from the current paper book.

    Re-marks the book to market and writes a fresh paper snapshot to local JSON.
    Useful after positions close (e.g. from a scheduled mark-to-market) without
    re-running a full screen. Runs fully offline — no Supabase required."""
    from tradingagents.paper.book import PaperBook
    from tradingagents.paper.snapshots import save_paper_snapshot

    config = DEFAULT_CONFIG.copy()
    book = PaperBook(config)
    book.mark_to_market()
    path = save_paper_snapshot(config, book)
    console.print(f"[green]Refreshed dashboard snapshot.[/green] [dim]({path})[/dim]")
    console.print("[dim]View:[/dim] [bold]http://localhost:3000/positions[/bold]")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context):
    """Run the interactive single-ticker analysis when no subcommand is given.

    Preserves the original ``tradingagents`` behaviour (bare command launches
    the interactive analysis) now that the app has multiple subcommands.
    """
    if ctx.invoked_subcommand is None:
        run_analysis()


def _screen_config(top: Optional[int], universe: Optional[str], min_pct: Optional[float]) -> dict:
    config = DEFAULT_CONFIG.copy()
    if top is not None:
        config["screen_top_n"] = top
    if universe is not None:
        config["screen_universe_csv"] = universe
    if min_pct is not None:
        config["screen_rs_min_percentile"] = min_pct
    return config


def _render_candidates(candidates, analyzed: bool):
    table = Table(box=box.SIMPLE_HEAD, title="Screened candidates")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Ticker", style="bold")
    table.add_column("RS %", justify="right")
    table.add_column("Score", justify="right")
    if analyzed:
        table.add_column("AI rating", style="bold")
    table.add_column("Signals fired")
    for i, c in enumerate(candidates, 1):
        row = [
            str(i),
            c.symbol,
            f"{c.rs.rs_percentile:.0f}",
            f"{c.composite:.2f}",
        ]
        if analyzed:
            rating = c.decision_rating or "-"
            colour = "green" if str(rating).upper() == "BUY" else (
                "red" if str(rating).upper() in ("SELL", "WAIT") else "yellow"
            )
            row.append(f"[{colour}]{rating}[/{colour}]")
        row.append(c.pattern.summary())
        table.add_row(*row)
    console.print(table)


@app.command()
def screen(
    top: Optional[int] = typer.Option(None, "--top", help="How many top-ranked stocks get Market Analyst (tech-desk style)."),
    universe: Optional[str] = typer.Option(None, "--universe", help="Path to a CSV of NSE tickers to screen (overrides the live/fallback list)."),
    min_pct: Optional[float] = typer.Option(None, "--min-rs", help="Keep only stocks at/above this relative-strength percentile (0-100)."),
    preview: bool = typer.Option(False, "--preview", help="Only screen and show the ranked picks — no Market Analyst, no token cost."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the cost-confirmation prompt (for non-interactive / automated runs)."),
):
    """Screen NSE stocks by RS + patterns, then Market Analyst on top-N.

    Saves MA reports to the shared tech_reports folder, then runs the RS Desk PM
    (same agent/rules as Tech Desk) into a separate rs_desk book.
    """
    from tradingagents.screening.batch_runner import run_screen

    config = _screen_config(top, universe, min_pct)
    n = config["screen_top_n"]

    console.print(Panel.fit(
        "[bold]India RS + pattern screen -> RS Desk[/bold]\n"
        f"Universe: {'custom CSV' if config.get('screen_universe_csv') else 'NSE Nifty 500 (live/fallback)'}\n"
        f"RS gate: top {100 - config['screen_rs_min_percentile']:.0f}% by strength\n"
        f"Market Analyst: top {n} -> shared tech_reports/\n"
        f"Then: RS Desk PM -> {config.get('rs_desk_book_path', '~/.tradingagents/rs_desk/')}"
        + ("" if preview else f"\nEstimated: ~{n} MA calls + 1 PM batch"),
        title="Screen",
    ))

    if not preview and not yes:
        if not questionary.confirm(
            f"Run Market Analyst on {n} stocks + RS Desk PM (real LLM cost)? Continue?",
            default=False,
        ).ask():
            console.print("[yellow]Aborted. Use --preview to see picks for free.[/yellow]")
            raise typer.Exit()

    with console.status("[bold green]Screening...", spinner="dots") as status:
        run = run_screen(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            analyze=not preview,
        )

    console.print()
    _render_candidates(run.candidates, analyzed=not preview)

    if preview:
        console.print("\n[dim]Preview only — no MA / RS Desk. Drop --preview to analyze.[/dim]")
    else:
        if run.opened:
            console.print(f"\n[green]RS Desk opened {len(run.opened)}:[/green] {', '.join(run.opened)}")
        if run.waits:
            console.print(f"[cyan]RS Desk waits {len(run.waits)}:[/cyan] {', '.join(run.waits)}")
        if not run.opened and not run.waits:
            console.print("\n[yellow]No open/wait plans from RS Desk PM.[/yellow]")
        if run.skipped:
            reasons = ", ".join(
                f"{s.get('ticker', '?')} ({s.get('reason', '')})" for s in run.skipped[:8]
            )
            more = f" …+{len(run.skipped) - 8}" if len(run.skipped) > 8 else ""
            console.print(f"[dim]Skipped:[/dim] {reasons}{more}")
        ps = run.paper_summary
        console.print(
            f"[dim]RS Desk book: {ps.get('open_positions', 0)} open. "
            f"Run [bold]tradingagents rs-desk-positions[/bold] or dashboard /positions.[/dim]"
        )


@app.command()
def paper():
    """Show the paper-trading portfolio: open positions, P&L, and the
    reliability stats (win rate / avg return / avg alpha vs Nifty), including a
    per-signal breakdown of which patterns actually produced winners."""
    from tradingagents.paper.book import PaperBook

    book = PaperBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()  # value + close matured positions first
    stats = book.stats()

    # Keep the dashboard paper snapshot fresh (local + optional Supabase).
    try:
        from tradingagents.paper.snapshots import save_paper_snapshot

        save_paper_snapshot(DEFAULT_CONFIG.copy(), book)
    except Exception:  # noqa: BLE001
        pass
    try:
        from tradingagents.sync import SupabaseSync, paper_snapshot
        client = SupabaseSync()
        if client.configured:
            client.push("paper", paper_snapshot(book))
    except Exception:  # noqa: BLE001
        pass

    open_positions = [p for p in book.positions if p["status"] == "open"]
    closed = [p for p in book.positions if p["status"] == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No paper trades yet. Run [bold]tradingagents screen[/bold] to generate some.",
            title="Paper book",
        ))
        raise typer.Exit()

    # Open positions
    if open_positions:
        from cli.position_tables import print_rs_paper_open

        print_rs_paper_open(console, open_positions)
        console.print(f"[dim]Unrealized P&L (open): Rs {summary.get('unrealized_pnl', 0):,.0f}[/dim]\n")

    # Closed trades
    if closed:
        from cli.position_tables import print_rs_paper_closed

        print_rs_paper_closed(console, closed)

    # Reliability stats
    o = stats["overall"]
    if o["trades"]:
        console.print(Panel.fit(
            f"Closed trades: [bold]{o['trades']}[/bold]\n"
            f"Win rate: [bold]{o['win_rate']}%[/bold]\n"
            f"Avg return: [bold]{o['avg_return']:+}%[/bold]\n"
            f"Avg alpha vs Nifty: [bold]{o['avg_alpha'] if o['avg_alpha'] is not None else 'n/a'}%[/bold]\n"
            f"Realized P&L: [bold]₹{o['total_pnl']:,.0f}[/bold]",
            title="Reliability (overall)",
        ))
        if stats["per_signal"]:
            t = Table(box=box.SIMPLE_HEAD, title="Reliability by signal")
            t.add_column("Signal", style="bold")
            t.add_column("Trades", justify="right")
            t.add_column("Win rate", justify="right")
            t.add_column("Avg return", justify="right")
            t.add_column("Avg alpha", justify="right")
            for name, s in stats["per_signal"].items():
                t.add_row(name, str(s["trades"]), f"{s['win_rate']}%",
                          f"{s['avg_return']:+}%",
                          f"{s['avg_alpha']:+}%" if s["avg_alpha"] is not None else "n/a")
            console.print(t)
    else:
        console.print("[yellow]No closed trades yet — reliability stats appear once positions reach their holding period.[/yellow]")


@app.command("portfolio-review")
def portfolio_review(
    as_of: Optional[str] = typer.Option(
        None, "--as-of", help="As-of date for P&L (YYYY-MM-DD). Default: today.",
    ),
    no_llm: bool = typer.Option(
        False, "--no-llm", help="Facts + tables only; skip LLM narrative (zero token cost).",
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", help="Directory for saved facts JSON and memo markdown.",
    ),
):
    """Grounded portfolio PM memo across all 7 paper desks.

    Builds facts from real book data and live prices, renders tables in Python,
    then (unless --no-llm) asks the quick-think model for descriptive +
    action-oriented commentary. Reports save under ~/.tradingagents/portfolio_reports/.
    """
    from tradingagents.portfolio_review import run_portfolio_review

    config = DEFAULT_CONFIG.copy()
    if not no_llm:
        from cli.utils import ensure_api_key

        ensure_api_key(config.get("llm_provider", "openai"))

    out = Path(output_dir).expanduser() if output_dir else None
    try:
        result = run_portfolio_review(
            config,
            as_of=as_of,
            use_llm=not no_llm,
            output_dir=out,
        )
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Portfolio review failed:[/red] {exc}")
        raise typer.Exit(1) from exc

    s = result["summary"]
    console.print(Panel.fit(
        f"[bold]Portfolio review[/bold] · as of {result['as_of_date']}\n"
        f"Open: {s['open_positions']} · Closed: {s['closed_positions']}\n"
        f"Realized: [bold]Rs {s['total_realized_inr']:,.0f}[/bold] · "
        f"Unrealized: [bold]Rs {s['total_unrealized_inr']:,.0f}[/bold] · "
        f"Total: [bold]Rs {s['total_pnl_inr']:,.0f}[/bold]",
        title="portfolio-review",
    ))

    if result.get("narrative"):
        # Windows cp1252 consoles choke on ₹ in Rich Markdown; print plain text.
        safe = result["narrative"].replace("\u20b9", "Rs ")
        console.print(Markdown(safe))
        if not result.get("validation_ok"):
            console.print(
                "[yellow]Grounding check flagged unverified numbers — "
                "trust the tables in the saved memo for figures.[/yellow]"
            )
    else:
        console.print("[dim]Tables written to memo file (use a UTF-8 terminal to preview here).[/dim]")

    console.print(f"\n[green]Saved facts:[/green] {result['facts_path']}")
    console.print(f"[green]Saved memo:[/green]  {result['memo_path']}")


def _render_swing_picks(picks):
    table = Table(box=box.SIMPLE_HEAD, title="Swing screener — top picks (manual AI selection)")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Ticker", style="bold green")
    table.add_column("Stock")
    table.add_column("Entry ₹", justify="right")
    table.add_column("Stop ₹", justify="right")
    table.add_column("Stop%", justify="right")
    table.add_column("T1 ₹", justify="right")
    table.add_column("T1%", justify="right")
    table.add_column("T2 ₹", justify="right")
    table.add_column("T2%", justify="right")
    table.add_column("R:R", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("ADX", justify="right")
    table.add_column("Vol%", justify="right")
    for i, p in enumerate(picks, 1):
        table.add_row(
            str(i),
            p.symbol.replace(".NS", ""),
            p.stock_name[:22],
            f"{p.entry_price:.2f}",
            f"{p.stop_loss:.2f}",
            f"{p.stop_loss_pct:.1f}%",
            f"{p.target_1:.2f}",
            f"+{p.target_1_pct:.1f}%",
            f"{p.target_2:.2f}",
            f"+{p.target_2_pct:.1f}%",
            f"{p.risk_reward_ratio:.1f}:{p.risk_reward_ratio_2:.1f}",
            f"{p.rsi:.1f}",
            f"{p.adx:.1f}",
            f"{p.volume_spike_pct:+.0f}%",
        )
    console.print(table)


def _export_swing_csv(path: str, picks) -> None:
    import csv

    fields = [
        "symbol", "stock_name", "sector", "entry_price", "stop_loss",
        "stop_loss_pct", "target_1", "target_1_pct", "target_2", "target_2_pct",
        "risk_reward_ratio", "risk_reward_ratio_2", "supertrend_status",
        "rsi", "adx", "volume_spike_pct", "relative_volume",
        "market_cap_cr", "avg_traded_value_cr",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in picks:
            writer.writerow({
                "symbol": p.symbol,
                "stock_name": p.stock_name,
                "sector": p.sector,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
                "stop_loss_pct": p.stop_loss_pct,
                "target_1": p.target_1,
                "target_1_pct": p.target_1_pct,
                "target_2": p.target_2,
                "target_2_pct": p.target_2_pct,
                "risk_reward_ratio": p.risk_reward_ratio,
                "risk_reward_ratio_2": p.risk_reward_ratio_2,
                "supertrend_status": p.supertrend_status,
                "rsi": p.rsi,
                "adx": p.adx,
                "volume_spike_pct": p.volume_spike_pct,
                "relative_volume": p.relative_volume,
                "market_cap_cr": p.market_cap_cr,
                "avg_traded_value_cr": p.avg_traded_value_cr,
            })


@app.command()
def swing(
    universe: Optional[str] = typer.Option(
        None, "--universe", help="CSV of NSE tickers (overrides live/fallback list).",
    ),
    top: Optional[int] = typer.Option(
        None, "--top", help="How many ranked picks to show (default 10).",
    ),
    save: bool = typer.Option(
        True, "--save/--no-save",
        help="Save picks to the swing_trade_positional book (default: save).",
    ),
    export: Optional[str] = typer.Option(
        None, "--export", help="Write results to a CSV file at this path.",
    ),
):
    """Screen NSE stocks for early swing setups (20-day hold style).

    Supertrend flip within 3 sessions, RSI 50–65, close > EMA20,
    volume ≥120%, ADX>15, liquidity gates. Shows a ranked shortlist only —
    pick tickers yourself for AI analysis via ``tradingagents analyze``."""
    from tradingagents.screening.swing_screener import screen_swing
    from tradingagents.swing import STRATEGY_NAME, SwingPositionBook

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["swing_top_n"] = top

    console.print(Panel.fit(
        "[bold]India swing screener[/bold] (early entry · 20-day hold)\n"
        "ST (10,3) Sell→Buy within 3 sessions · RSI 50–65 (trend confirm)\n"
        "Close > EMA20 · Volume ≥120% · ADX>15\n"
        "MCap>₹5,000 Cr · Traded value>₹10 Cr · No 52-week lows\n"
        f"Top [bold]{config['swing_top_n']}[/bold] by rel. volume → ADX → RSI (50–65)\n"
        "[dim]No AI calls — review list, then run analyze on your picks.[/dim]",
        title="Swing",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_swing(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
        )

    console.print()
    if not picks:
        console.print("[yellow]No stocks matched all swing criteria today.[/yellow]")
        raise typer.Exit()

    _render_swing_picks(picks)
    console.print(
        f"\n[dim]{len(picks)} pick(s). Entry/stop/targets = latest close + Supertrend line.[/dim]"
    )
    console.print(
        f"[dim]Analyze a pick:[/dim] [bold]tradingagents analyze TICKER[/bold]  "
        f"[dim](e.g. {picks[0].symbol.replace('.NS', '')})[/dim]"
    )

    if save:
        book = SwingPositionBook(config)
        saved = book.save_picks(picks)
        console.print(
            f"\n[green]Saved {len(saved)} position(s) to swing_trade_positional[/green] "
            f"[dim]({book.path})[/dim]"
        )
        console.print("[dim]View book:[/dim] [bold]tradingagents swing-positions[/bold]")

    if export:
        _export_swing_csv(export, picks)
        console.print(f"[green]Exported to {export}[/green]")


@app.command("swing-positions")
def swing_positions():
    """Show saved swing_trade_positional positions and closed-trade stats."""
    from tradingagents.swing import STRATEGY_NAME, SwingPositionBook

    book = SwingPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No swing positions yet. Run [bold]tradingagents swing[/bold] to screen and save picks.",
            title="swing_trade_positional",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("Stop%", justify="right")
        t.add_column("T1%", justify="right")
        t.add_column("R:R", justify="right")
        t.add_column("Phase")
        t.add_column("Rem%", justify="right")
        t.add_column("Trail Rs", justify="right")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:22],
                *open_meta_cells(p),
                f"{p['entry_price']:.2f}",
                f"{p.get('stop_loss_pct', 0):.1f}%",
                f"+{p.get('target_1_pct', 0):.1f}%",
                f"{p.get('risk_reward_ratio', 0):.1f}:{p.get('risk_reward_ratio_2', 0):.1f}",
                p.get("phase", "initial"),
                f"{p.get('remaining_pct', 100):.0f}",
                f"{p.get('trailing_stop', p.get('stop_loss', 0)):.2f}",
            )
        console.print(t)
        console.print(
            f"[dim]{summary.get('open_positions', 0)} open · "
            f"closed this run: {summary.get('closed_now', 0)}[/dim]\n"
        )

    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed swing positions")

    o = stats.get("overall", {})
    if o.get("trades"):
        msg = (
            f"\n[bold]Reliability[/bold] ({o['trades']} closed): "
            f"win rate {o['win_rate']}% · avg return {o['avg_return']:+.2f}%"
        )
        if o.get("avg_alpha") is not None:
            msg += f" · avg alpha {o['avg_alpha']:+.2f}%"
        console.print(msg)
    else:
        console.print(
            "[yellow]No closed swing trades yet — stats appear after the 20-day hold.[/yellow]"
        )


@app.command("swing-daily")
def swing_daily(
    force: bool = typer.Option(
        False, "--force", help="Deprecated no-op; daily runs every calendar day.",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y",
        help="Deprecated no-op (foreclosure disabled).",
    ),
):
    """Daily swing portfolio job (9:30 / 11:45 / 14:30 IST every day).

    Screens on daily (1D) charts, processes stop/T1/time exits,
    opens new picks when slots are free (exits via stop/target only — no foreclosure)."""
    from tradingagents.swing import PortfolioPaperTradeManager, run_swing_daily

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]Swing daily run...", spinner="dots") as status:
        report = run_swing_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]swing_trade_positional daily[/bold] · chart: [cyan]1D[/cyan]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="Swing daily",
    ))

    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  [dim]exit[/dim] {e['ticker']} · {e['reason']} · {e.get('raw_return', 0)*100:+.1f}%")
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")

    console.print("[dim]Full report:[/dim] [bold]tradingagents swing-report[/bold]")


@app.command("swing-approve")
def swing_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending replacements."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Deprecated: foreclosure disabled — exits via stop/target only."""
    _portfolio_approve("swing", yes=yes, ids=ids)


@app.command("swing-report")
def swing_report():
    """Show the latest swing daily portfolio report."""
    from tradingagents.swing import PortfolioPaperTradeManager

    manager = PortfolioPaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if not report:
        console.print("[yellow]No daily reports yet. Run tradingagents swing-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"Date: {report.get('date')} · timeframe: {report.get('chart_timeframe', '1d')}\n"
        f"Picks: {report.get('screener_picks')} · Open: {report.get('open_positions')}",
        title="Latest swing daily report",
    ))
    console.print(json.dumps(report, indent=2))


def _render_momentum_picks(picks):
    table = Table(box=box.SIMPLE_HEAD, title="Momentum screener — top picks (manual AI selection)")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Ticker", style="bold green")
    table.add_column("Stock")
    table.add_column("Entry ₹", justify="right")
    table.add_column("Stop%", justify="right")
    table.add_column("T1%", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("ADX", justify="right")
    table.add_column("MACD", justify="right")
    table.add_column("Vol5/20", justify="right")
    table.add_column("Ext%", justify="right")
    table.add_column("ADX↑", justify="right")
    table.add_column("PB", justify="center")
    for i, p in enumerate(picks, 1):
        table.add_row(
            str(i),
            p.symbol.replace(".NS", ""),
            p.stock_name[:22],
            f"{p.entry_price:.2f}",
            f"{p.stop_loss_pct:.1f}%",
            f"+{p.target_1_pct:.1f}%",
            f"{p.rsi:.1f}",
            f"{p.adx:.1f}",
            f"{p.macd:.2f}",
            f"{p.volume_ratio_5_20:.2f}x",
            f"{p.extension_pct:.1f}%",
            "Y" if p.adx_rising else "—",
            "✓" if getattr(p, "hh_pullback", False) else "—",
        )
    console.print(table)


def _export_momentum_csv(path: str, picks) -> None:
    import csv

    fields = [
        "symbol", "stock_name", "sector", "entry_price", "stop_loss",
        "stop_loss_pct", "target_1", "target_1_pct", "target_2", "target_2_pct",
        "risk_reward_ratio", "risk_reward_ratio_2", "supertrend_status",
        "rsi", "adx", "macd", "macd_signal", "volume_ratio_5_20",
        "extension_pct", "adx_rising", "hh_pullback", "market_cap_cr", "avg_traded_value_cr",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in picks:
            writer.writerow({
                "symbol": p.symbol,
                "stock_name": p.stock_name,
                "sector": p.sector,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
                "stop_loss_pct": p.stop_loss_pct,
                "target_1": p.target_1,
                "target_1_pct": p.target_1_pct,
                "target_2": p.target_2,
                "target_2_pct": p.target_2_pct,
                "risk_reward_ratio": p.risk_reward_ratio,
                "risk_reward_ratio_2": p.risk_reward_ratio_2,
                "supertrend_status": p.supertrend_status,
                "rsi": p.rsi,
                "adx": p.adx,
                "macd": p.macd,
                "macd_signal": p.macd_signal,
                "volume_ratio_5_20": p.volume_ratio_5_20,
                "extension_pct": p.extension_pct,
                "adx_rising": p.adx_rising,
                "hh_pullback": getattr(p, "hh_pullback", False),
                "market_cap_cr": p.market_cap_cr,
                "avg_traded_value_cr": p.avg_traded_value_cr,
            })


@app.command()
def momentum(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="How many ranked picks to show."),
    save: bool = typer.Option(True, "--save/--no-save", help="Save picks to momentum book."),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Screen NSE stocks for momentum continuation setups (20-day max hold).

    EMA50>EMA200, ST Buy, ADX>20, RSI 50–65, MACD bullish, vol 5d>20d.
    Ranked shortlist — run analyze on your picks."""
    from tradingagents.screening.momentum_screener import screen_momentum
    from tradingagents.momentum import MomentumPositionBook

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["momentum_top_n"] = top

    console.print(Panel.fit(
        "[bold]India momentum screener[/bold] (continuation · 20-day max hold)\n"
        "Close > EMA50 > EMA200 · ST Buy ≥4 sessions (no recent flip)\n"
        "ADX>20 · RSI 50–65 · MACD > signal · Vol 5d ≥ 20d\n"
        "PB = HH after EMA pullback (shown, not required) · ext <15% · excludes swing early-entry zone\n"
        "MCap>₹5,000 Cr · Traded value>₹10 Cr · No 52-week lows\n"
        f"Top [bold]{config['momentum_top_n']}[/bold] by ADX rising → ADX → vol → RSI · max 4/sector\n"
        "[dim]No AI calls — review list, then run analyze on your picks.[/dim]",
        title="Momentum",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_momentum(config, progress=lambda m: status.update(f"[bold green]{m}"))

    console.print()
    if not picks:
        console.print("[yellow]No stocks matched all momentum criteria today.[/yellow]")
        raise typer.Exit()

    _render_momentum_picks(picks)
    console.print(f"\n[dim]{len(picks)} pick(s). T1 full exit · 20 trading-day max hold.[/dim]")

    if save:
        book = MomentumPositionBook(config)
        saved = book.save_picks(picks)
        console.print(
            f"\n[green]Saved {len(saved)} position(s) to momentum_trade_positional[/green] "
            f"[dim]({book.path})[/dim]"
        )
        console.print("[dim]View book:[/dim] [bold]tradingagents momentum-positions[/bold]")
        console.print("[dim]Desk:[/dim] [bold]http://localhost:3000/momentum[/bold]")

    if export:
        _export_momentum_csv(export, picks)
        console.print(f"[green]Exported to {export}[/green]")


@app.command("momentum-positions")
def momentum_positions():
    """Show momentum_trade_positional positions and stats."""
    from tradingagents.momentum import STRATEGY_NAME, MomentumPositionBook

    book = MomentumPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No momentum positions yet. Run [bold]tradingagents momentum[/bold] to screen and save.",
            title="momentum_trade_positional",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("Stop%", justify="right")
        t.add_column("T1%", justify="right")
        t.add_column("Phase")
        t.add_column("Rem%", justify="right")
        t.add_column("Trail Rs", justify="right")
        t.add_column("RSI", justify="right")
        t.add_column("ADX", justify="right")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:22],
                *open_meta_cells(p),
                f"{p['entry_price']:.2f}",
                f"{p.get('stop_loss_pct', 0):.1f}%",
                f"+{p.get('target_1_pct', 0):.1f}%",
                p.get("phase", "initial"),
                f"{p.get('remaining_pct', 100):.0f}",
                f"{p.get('trailing_stop', p.get('stop_loss', 0)):.2f}",
                f"{p.get('rsi', 0):.1f}",
                f"{p.get('adx', 0):.1f}",
            )
        console.print(t)
        console.print(
            f"[dim]{summary.get('open_positions', 0)} open · "
            f"closed this run: {summary.get('closed_now', 0)}[/dim]\n"
        )

    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed momentum positions")

    o = stats.get("overall", {})
    if o.get("trades"):
        msg = (
            f"\n[bold]Reliability[/bold] ({o['trades']} closed): "
            f"win rate {o['win_rate']}% · avg return {o['avg_return']:+.2f}%"
        )
        if o.get("avg_alpha") is not None:
            msg += f" · avg alpha {o['avg_alpha']:+.2f}%"
        console.print(msg)
    else:
        console.print("[yellow]No closed momentum trades yet.[/yellow]")

    console.print(f"\n[dim]Book:[/dim] {book.path}")
    console.print("[dim]Daily report:[/dim] [bold]tradingagents momentum-report[/bold]")


@app.command("momentum-daily")
def momentum_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve replacement proposals."),
):
    """Daily momentum portfolio job (9:30 / 11:45 / 14:30 IST every day)."""
    from tradingagents.momentum import MomentumPaperTradeManager, run_momentum_daily

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]Momentum daily run...", spinner="dots") as status:
        report = run_momentum_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]momentum_trade_positional daily[/bold] · chart: [cyan]1D[/cyan]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="Momentum daily",
    ))

    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  [dim]exit[/dim] {e['ticker']} · {e['reason']} · {e.get('raw_return', 0)*100:+.1f}%")
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")

    console.print("[dim]Full report:[/dim] [bold]tradingagents momentum-report[/bold]")


@app.command("momentum-approve")
def momentum_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending replacements."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Approve pending momentum portfolio replacement proposals."""
    _portfolio_approve("momentum", yes=yes, ids=ids)


@app.command("momentum-report")
def momentum_report():
    """Show the latest momentum daily portfolio report."""
    from tradingagents.momentum import MomentumPaperTradeManager

    manager = MomentumPaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if not report:
        console.print("[yellow]No daily reports yet. Run tradingagents momentum-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"Date: {report.get('date')} · timeframe: {report.get('chart_timeframe', '1d')}\n"
        f"Picks: {report.get('screener_picks')} · Open: {report.get('open_positions')}",
        title="Latest momentum daily report",
    ))
    console.print(json.dumps(report, indent=2))


def _render_nss_picks(picks):
    table = Table(box=box.SIMPLE_HEAD, title="NSS screener — top picks (structure-first)")
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Ticker", style="bold green")
    table.add_column("Stock")
    table.add_column("Score", justify="right")
    table.add_column("Conf")
    table.add_column("Entry ₹", justify="right")
    table.add_column("Stop%", justify="right")
    table.add_column("T1%", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("ADX", justify="right")
    table.add_column("Vol", justify="right")
    table.add_column("BO", justify="center")
    table.add_column("VOL✓", justify="center")
    table.add_column("Range%", justify="right")
    table.add_column("Reason")
    for i, p in enumerate(picks, 1):
        table.add_row(
            str(i),
            p.symbol.replace(".NS", ""),
            p.stock_name[:20],
            f"{p.composite_score:.0f}",
            p.confidence[:4] if p.confidence else "—",
            f"{p.entry_price:.2f}",
            f"{p.stop_loss_pct:.1f}%",
            f"+{p.target_1_pct:.1f}%",
            f"{p.rsi:.1f}",
            f"{p.adx:.1f}",
            f"{p.relative_volume:.2f}x",
            "✓" if getattr(p, "breakout_ok", False) else "—",
            "✓" if getattr(p, "volume_ok", False) else "—",
            f"{p.range_pct:.1f}%",
            (p.primary_reason or "")[:28],
        )
    console.print(table)


def _export_nss_csv(path: str, picks) -> None:
    import csv

    fields = [
        "symbol", "stock_name", "sector", "composite_score", "confidence", "primary_reason",
        "entry_price", "stop_loss", "stop_loss_pct", "target_1", "target_1_pct", "target_2",
        "target_2_pct", "risk_reward_ratio", "risk_reward_ratio_2", "rsi", "adx",
        "relative_volume", "range_pct", "atr_ratio", "risk_pct", "breakout_ok", "volume_ok",
        "market_cap_cr", "avg_traded_value_cr",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for p in picks:
            writer.writerow({
                "symbol": p.symbol,
                "stock_name": p.stock_name,
                "sector": p.sector,
                "composite_score": p.composite_score,
                "confidence": p.confidence,
                "primary_reason": p.primary_reason,
                "entry_price": p.entry_price,
                "stop_loss": p.stop_loss,
                "stop_loss_pct": p.stop_loss_pct,
                "target_1": p.target_1,
                "target_1_pct": p.target_1_pct,
                "target_2": p.target_2,
                "target_2_pct": p.target_2_pct,
                "risk_reward_ratio": p.risk_reward_ratio,
                "risk_reward_ratio_2": p.risk_reward_ratio_2,
                "rsi": p.rsi,
                "adx": p.adx,
                "relative_volume": p.relative_volume,
                "range_pct": p.range_pct,
                "atr_ratio": p.atr_ratio,
                "risk_pct": p.risk_pct,
                "breakout_ok": getattr(p, "breakout_ok", False),
                "volume_ok": getattr(p, "volume_ok", False),
                "market_cap_cr": p.market_cap_cr,
                "avg_traded_value_cr": p.avg_traded_value_cr,
            })


@app.command()
def nss(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="How many ranked picks to show."),
    save: bool = typer.Option(True, "--save/--no-save", help="Save picks to NSS book."),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Screen NSE stocks for NSS structure-first swing setups (40-day max hold).

    Consolidation + breakout scoring with explainable stages. Top 20 by composite score."""
    from tradingagents.screening.nss_screener import screen_nss
    from tradingagents.nss import NSSPositionBook

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["nss_top_n"] = top

    console.print(Panel.fit(
        "[bold]NANDA Swing Scanner (NSS)[/bold] · structure-first · 40-day max hold\n"
        "EMA50>EMA200 · consolidation + ATR contraction · BO/VOL scored (shown, not required)\n"
        "RSI 45–65 · ADX≥15 · risk ≤8% · max 4 names per sector\n"
        "Excludes swing early-entry & momentum continuation zones\n"
        f"Top [bold]{config['nss_top_n']}[/bold] by composite score (min {config['nss_min_score']})\n"
        "[dim]No AI calls — review list, then run analyze on your picks.[/dim]",
        title="NSS",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_nss(config, progress=lambda m: status.update(f"[bold green]{m}"))

    console.print()
    if not picks:
        console.print("[yellow]No stocks matched NSS criteria today.[/yellow]")
        raise typer.Exit()

    _render_nss_picks(picks)
    console.print(f"\n[dim]{len(picks)} pick(s). T1 full exit · 40 trading-day max hold.[/dim]")

    if save:
        book = NSSPositionBook(config)
        saved = book.save_picks(picks)
        console.print(
            f"\n[green]Saved {len(saved)} position(s) to nanda_swing_scanner[/green] "
            f"[dim]({book.path})[/dim]"
        )
        console.print("[dim]View book:[/dim] [bold]tradingagents nss-positions[/bold]")
        console.print("[dim]Desk:[/dim] [bold]http://localhost:3000/nss[/bold]")

    if export:
        _export_nss_csv(export, picks)
        console.print(f"[green]Exported to {export}[/green]")


@app.command("nss-positions")
def nss_positions():
    """Show nanda_swing_scanner positions and stats."""
    from tradingagents.nss import STRATEGY_NAME, NSSPositionBook

    book = NSSPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No NSS positions yet. Run [bold]tradingagents nss[/bold] to screen and save.",
            title="nanda_swing_scanner",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        t.add_column("Score", justify="right")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("Stop%", justify="right")
        t.add_column("T1%", justify="right")
        t.add_column("Phase")
        t.add_column("Rem%", justify="right")
        t.add_column("Trail Rs", justify="right")
        t.add_column("RSI", justify="right")
        t.add_column("ADX", justify="right")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:20],
                f"{p.get('composite_score', 0):.0f}",
                *open_meta_cells(p),
                f"{p['entry_price']:.2f}",
                f"{p.get('stop_loss_pct', 0):.1f}%",
                f"+{p.get('target_1_pct', 0):.1f}%",
                p.get("phase", "initial"),
                f"{p.get('remaining_pct', 100):.0f}",
                f"{p.get('trailing_stop', p.get('stop_loss', 0)):.2f}",
                f"{p.get('rsi', 0):.1f}",
                f"{p.get('adx', 0):.1f}",
            )
        console.print(t)
        console.print(
            f"[dim]{summary.get('open_positions', 0)} open · "
            f"closed this run: {summary.get('closed_now', 0)}[/dim]\n"
        )

    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed NSS positions")

    o = stats.get("overall", {})
    if o.get("trades"):
        msg = (
            f"\n[bold]Reliability[/bold] ({o['trades']} closed): "
            f"win rate {o['win_rate']}% · avg return {o['avg_return']:+.2f}%"
        )
        if o.get("avg_alpha") is not None:
            msg += f" · avg alpha {o['avg_alpha']:+.2f}%"
        console.print(msg)
    else:
        console.print("[yellow]No closed NSS trades yet.[/yellow]")

    console.print(f"\n[dim]Book:[/dim] {book.path}")
    console.print("[dim]Daily report:[/dim] [bold]tradingagents nss-report[/bold]")


@app.command("nss-daily")
def nss_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve replacement proposals."),
):
    """Daily NSS portfolio job (9:30 / 11:45 / 14:30 IST every day)."""
    from tradingagents.nss import NSSPaperTradeManager, run_nss_daily

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]NSS daily run...", spinner="dots") as status:
        report = run_nss_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]nanda_swing_scanner daily[/bold] · chart: [cyan]1D[/cyan]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="NSS daily",
    ))

    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  [dim]exit[/dim] {e['ticker']} · {e['reason']} · {e.get('raw_return', 0)*100:+.1f}%")
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")

    console.print("[dim]Full report:[/dim] [bold]tradingagents nss-report[/bold]")


@app.command("nss-approve")
def nss_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending replacements."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Approve pending NSS portfolio replacement proposals."""
    _portfolio_approve("nss", yes=yes, ids=ids)


@app.command("nss-report")
def nss_report():
    """Show the latest NSS daily portfolio report."""
    from tradingagents.nss import NSSPaperTradeManager

    manager = NSSPaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if not report:
        console.print("[yellow]No daily reports yet. Run tradingagents nss-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"Date: {report.get('date')} · timeframe: {report.get('chart_timeframe', '1d')}\n"
        f"Picks: {report.get('screener_picks')} · Open: {report.get('open_positions')}",
        title="Latest NSS daily report",
    ))
    console.print(json.dumps(report, indent=2))


def _render_nss_waterfall(waterfall):
    t = Table(box=box.SIMPLE_HEAD, title="NSS scanner waterfall (v1.1)")
    t.add_column("Stage")
    t.add_column("In", justify="right")
    t.add_column("Out", justify="right", style="bold cyan")
    t.add_column("Rejected", justify="right", style="red")
    t.add_column("Rej%", justify="right")
    for step in waterfall:
        t.add_row(
            step.label,
            str(step.input_count),
            str(step.output_count),
            str(step.rejection_count) if step.rejection_count else "—",
            f"{step.rejection_pct:.1f}%" if step.rejection_pct else "—",
        )
    console.print(t)


def _render_nss_near_misses(near_misses):
    if not near_misses:
        console.print("[yellow]No near-miss candidates.[/yellow]")
        return
    t = Table(box=box.SIMPLE_HEAD, title="Near miss — top rejected")
    t.add_column("#", justify="right")
    t.add_column("Ticker", style="bold")
    t.add_column("Partial", justify="right")
    t.add_column("Gap", justify="right")
    t.add_column("Failed at")
    t.add_column("Required")
    t.add_column("Actual")
    t.add_column("Distance")
    t.add_column("Action")
    for n in near_misses[:20]:
        t.add_row(
            str(n.rank),
            n.symbol.replace(".NS", ""),
            f"{n.partial_score:.1f}",
            f"{n.score_gap:.1f}",
            n.failure_stage,
            n.threshold_required or "—",
            n.threshold_actual or "—",
            n.threshold_distance or "—",
            (n.watch_action or "")[:40],
        )
    console.print(t)


def _render_ticker_diagnostic(diag):
    title = f"{diag.symbol.replace('.NS', '')} — {'PICKED' if diag.status == 'picked' else 'REJECTED'}"
    gran = getattr(diag, "granular_failure_stage", None)
    if gran or diag.failure_stage:
        title += f" @ {gran or diag.failure_stage}"
    console.print(Panel.fit(
        f"{title}\n"
        f"Rating: [bold]{getattr(diag, 'overall_rating', '—')}[/bold] · "
        f"Confidence: {getattr(diag, 'overall_confidence', '—')} · "
        f"Composite: {diag.partial_score:.1f}",
        title="NSS explain (v1.1)",
    ))

    if diag.status == "picked" and getattr(diag, "selection_reason", ""):
        console.print(f"[green]Why selected:[/green] {diag.selection_reason}")
    if diag.failure_reason:
        console.print(f"[dim]Rejection:[/dim] {diag.failure_reason}")

    modules = getattr(diag, "modules", {}) or {}
    if modules:
        t = Table(box=box.SIMPLE_HEAD, title="Module scores")
        t.add_column("Module")
        t.add_column("Pass", justify="center")
        t.add_column("Score", justify="right")
        t.add_column("Conf")
        t.add_column("Explanation")
        for m in modules.values():
            if m.name.endswith("_overlap") and m.name != "overlap":
                continue
            mark = "[green]Y[/green]" if m.passed else "[red]N[/red]"
            t.add_row(m.name, mark, f"{m.score:.1f}", m.confidence, (m.explanation or "")[:50])
            for sub in (m.submodules or {}).values():
                sm = "[green]Y[/green]" if sub.passed else "[red]N[/red]"
                t.add_row(f"  {sub.name}", sm, f"{sub.score:.1f}", sub.confidence, (sub.explanation or "")[:48])
        console.print(t)

    if diag.score_components:
        sc = diag.score_components
        console.print(
            "[bold]Weighted components:[/bold] "
            f"Trend {sc.get('trend', 0):.1f} · Consol {sc.get('consolidation', 0):.1f} · "
            f"Break {sc.get('breakout', 0):.1f} · Vol {sc.get('volume', 0):.1f} · "
            f"Mom {sc.get('momentum', 0):.1f} · Risk {sc.get('risk', 0):.1f} · "
            f"[bold]Composite {sc.get('composite', 0):.1f}[/bold]"
        )
    if diag.market_cap_cr is not None:
        console.print(f"[dim]MCap {diag.market_cap_cr} Cr · Avg traded {diag.avg_traded_value_cr} Cr[/dim]")


@app.command("nss-diagnostics")
def nss_diagnostics(
    near_miss: int = typer.Option(50, "--near-miss", help="How many near-miss names to show."),
    export: Optional[str] = typer.Option(None, "--export", help="Write full JSON report."),
    rejections: bool = typer.Option(False, "--rejections", help="Print every rejection reason."),
):
    """NSS scanner diagnostics: waterfall funnel, near misses, rejection breakdown."""
    from tradingagents.screening.nss_diagnostics import run_scan_diagnostics

    config = DEFAULT_CONFIG.copy()
    with console.status("[bold green]Running NSS diagnostics...", spinner="dots") as status:
        report = run_scan_diagnostics(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            near_miss_limit=near_miss,
        )

    console.print()
    console.print(Panel.fit(
        f"Universe: {report.universe_size} · Picks: {len(report.picks)} · "
        f"Rejected: {report.rejected_count}",
        title="NSS diagnostics",
    ))
    _render_nss_waterfall(report.waterfall)

    if report.rejection_by_stage:
        t = Table(box=box.SIMPLE_HEAD, title="Rejections by stage")
        t.add_column("Stage", style="bold")
        t.add_column("Count", justify="right")
        for stage, count in sorted(report.rejection_by_stage.items(), key=lambda x: -x[1]):
            t.add_row(stage, str(count))
        console.print(t)

    _render_nss_near_misses(report.near_misses)

    if report.market_health:
        h = report.market_health
        console.print(
            f"\n[bold]Market health[/bold] ({h.get('date')}): "
            f"trend {h.get('trend_stocks')} · consolidating {h.get('consolidating_stocks')} · "
            f"breakout {h.get('breakout_candidates')} · vol confirmed {h.get('volume_confirmed')} · "
            f"picks {h.get('final_picks')}"
        )

    if report.picks:
        console.print(f"\n[green]Picks ({len(report.picks)}):[/green] {', '.join(p.replace('.NS', '') for p in report.picks)}")

    if rejections:
        for d in report.diagnostics:
            if d.status == "picked":
                continue
            sym = d.symbol.replace(".NS", "")
            console.print(f"  [red]{sym}[/red] @ {d.failure_stage}: {d.failure_reason}")

    if export:
        import json as _json
        payload = report.to_dict(include_rejections=True)
        with open(export, "w", encoding="utf-8") as f:
            _json.dump(payload, f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


@app.command("nss-explain")
def nss_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE or RELIANCE.NS)."),
    export: Optional[str] = typer.Option(None, "--export", help="Write JSON explanation."),
):
    """Detailed NSS pass/fail explanation for one ticker."""
    from tradingagents.screening.nss_diagnostics import explain_ticker

    config = DEFAULT_CONFIG.copy()
    with console.status(f"[bold green]Explaining {ticker}...", spinner="dots"):
        diag = explain_ticker(ticker, config)

    console.print()
    _render_ticker_diagnostic(diag)

    if export:
        import json as _json
        with open(export, "w", encoding="utf-8") as f:
            _json.dump(diag.to_dict(), f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


def _render_strsi_picks(picks):
    t = Table(box=box.SIMPLE_HEAD, title="SuperTrend + RSI — signals")
    t.add_column("#", justify="right", style="cyan")
    t.add_column("Ticker", style="bold")
    t.add_column("Dir")
    t.add_column("Score", justify="right")
    t.add_column("Grade")
    t.add_column("RSI", justify="right")
    t.add_column("ST age", justify="right")
    t.add_column("Reasons")
    for i, p in enumerate(picks, 1):
        s = p.signal
        t.add_row(
            str(i),
            s.symbol.replace(".NS", ""),
            f"[green]{s.direction}[/green]" if s.direction == "BUY" else f"[red]{s.direction}[/red]",
            str(s.score),
            f"{s.grade_stars} {s.grade}",
            f"{s.rsi:.1f}",
            str(s.flip_age),
            "; ".join(s.reasons[:3]),
        )
    console.print(t)


def _render_strsi_signal(sig):
    status = sig.direction if not sig.rejected else f"{sig.direction} (FILTERED)"
    console.print(Panel.fit(
        f"[bold]{sig.symbol.replace('.NS', '')}[/bold] — {status}\n"
        f"Score: [bold]{sig.score}[/bold]/100 · {sig.grade_stars} {sig.grade}\n"
        f"RSI {sig.rsi:.1f} · Close {sig.close:.2f} · ST {sig.supertrend_value:.2f} · Flip age {sig.flip_age}",
        title="SuperTrend + RSI",
    ))
    if sig.rejected and sig.reject_reason:
        console.print(f"[red]Filtered:[/red] {sig.reject_reason}")
    if not sig.mandatory_pass and sig.reject_reason:
        console.print(f"[yellow]No signal:[/yellow] {sig.reject_reason}")

    c = sig.components
    t = Table(box=box.SIMPLE_HEAD, title="Component breakdown (raw / max)")
    t.add_column("Component")
    t.add_column("Raw", justify="right")
    t.add_column("Max", justify="right")
    for name, val, mx in [
        ("SuperTrend freshness", c.supertrend_freshness, 40),
        ("RSI 50 cross", c.rsi_cross, 25),
        ("RSI strength", c.rsi_strength, 25),
        ("RSI momentum", c.rsi_momentum, 15),
        ("RSI MA cross", c.rsi_ma_cross, 15),
        ("ST distance", c.st_distance, 15),
        ("Candle strength", c.candle_strength, 15),
        ("Volume", c.volume, 10),
        ("EMA trend", c.ema_trend, 10),
    ]:
        t.add_row(name, f"{val:.0f}", str(mx))
    t.add_row("[bold]Total[/bold]", f"[bold]{c.raw_total:.0f}[/bold]", "170")
    console.print(t)

    if sig.reasons:
        console.print("[bold]Reasons[/bold]")
        for r in sig.reasons:
            console.print(f"  [green]✓[/green] {r}")


@app.command("supertrend-rsi")
def supertrend_rsi_cmd(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="Max signals to show."),
    min_score: Optional[int] = typer.Option(None, "--min-score", help="Minimum score (0 = no floor)."),
    save: bool = typer.Option(True, "--save/--no-save", help="Save BUY picks to paper book."),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Screen for SuperTrend + RSI crossover signals (BUY/SELL with confidence score)."""
    from tradingagents.supertrend_rsi import STRATEGY_NAME, SuperTrendRSIPositionBook, screen_supertrend_rsi

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["strsi_top_n"] = top
    if min_score is not None:
        config["strsi_min_score"] = min_score

    min_label = "none" if config["strsi_min_score"] <= 0 else str(config["strsi_min_score"])
    console.print(Panel.fit(
        f"[bold]{STRATEGY_NAME}[/bold] v1.0 · [cyan]supertrend_rsi[/cyan]\n"
        "ST(10,3) crossover + RSI(14) confirmation + 9-component scoring\n"
        "BUY opens only · SELL closes matching open longs · T1 full exit · 20d max · max 4/sector\n"
        f"Top [bold]{config['strsi_top_n']}[/bold] BUY · Min score [bold]{min_label}[/bold] · Fresh flip ≤[bold]{config['strsi_mandatory_flip_max_age']}[/bold] bars",
        title="SuperTrend + RSI",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_supertrend_rsi(config, progress=lambda m: status.update(f"[bold green]{m}"))

    console.print()
    if not picks:
        console.print("[yellow]No SuperTrend+RSI signals matched criteria today.[/yellow]")
        console.print("[dim]Try: tradingagents supertrend-rsi-explain TICKER[/dim]")
        raise typer.Exit()

    _render_strsi_picks(picks)
    buys = sum(1 for p in picks if p.direction == "BUY")
    sells = len(picks) - buys
    console.print(f"\n[dim]{len(picks)} signal(s): {buys} BUY · {sells} SELL[/dim]")

    if save:
        book = SuperTrendRSIPositionBook(config)
        saved = book.save_picks(picks)
        sell_n = sum(1 for p in picks if p.direction == "SELL")
        console.print(
            f"\n[green]Saved {len(saved)} BUY position(s) to supertrend_rsi[/green] "
            f"[dim]({book.path})[/dim]"
        )
        if sell_n:
            console.print(f"[dim]Stored {sell_n} SELL signal(s) (used on daily to close open longs).[/dim]")
        console.print("[dim]View book:[/dim] [bold]tradingagents supertrend-rsi-positions[/bold]")
        console.print("[dim]Desk:[/dim] [bold]http://localhost:3000/supertrend-rsi[/bold]")

    if export:
        import csv
        with open(export, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "symbol", "direction", "score", "grade", "rsi", "flip_age", "reasons",
            ])
            w.writeheader()
            for p in picks:
                s = p.signal
                w.writerow({
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "score": s.score,
                    "grade": s.grade,
                    "rsi": s.rsi,
                    "flip_age": s.flip_age,
                    "reasons": "; ".join(s.reasons),
                })
        console.print(f"[green]Exported to {export}[/green]")


@app.command("supertrend-rsi-positions")
def supertrend_rsi_positions():
    """Show supertrend_rsi paper positions and stats."""
    from tradingagents.supertrend_rsi import STRATEGY_NAME, SuperTrendRSIPositionBook

    book = SuperTrendRSIPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No ST+RSI positions yet. Run [bold]tradingagents supertrend-rsi[/bold] to screen and save.",
            title="supertrend_rsi",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        t.add_column("Score", justify="right")
        t.add_column("Age", justify="right")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("Stop%", justify="right")
        t.add_column("T1%", justify="right")
        t.add_column("Phase")
        t.add_column("Trail Rs", justify="right")
        t.add_column("RSI", justify="right")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:20],
                str(p.get("signal_score", 0)),
                str(p.get("flip_age", "—")),
                *open_meta_cells(p),
                f"{p['entry_price']:.2f}",
                f"{p.get('stop_loss_pct', 0):.1f}%",
                f"+{p.get('target_1_pct', 0):.1f}%",
                p.get("phase", "initial"),
                f"{p.get('trailing_stop', p.get('stop_loss', 0)):.2f}",
                f"{p.get('rsi', 0):.1f}",
            )
        console.print(t)
        console.print(
            f"[dim]{summary.get('open_positions', 0)} open · "
            f"closed this run: {summary.get('closed_now', 0)}[/dim]\n"
        )

    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed ST+RSI positions")

    o = stats.get("overall", {})
    if o.get("trades"):
        msg = (
            f"\n[bold]Reliability[/bold] ({o['trades']} closed): "
            f"win rate {o['win_rate']}% · avg return {o['avg_return']:+.2f}%"
        )
        if o.get("avg_alpha") is not None:
            msg += f" · avg alpha {o['avg_alpha']:+.2f}%"
        console.print(msg)
    else:
        console.print("[yellow]No closed ST+RSI trades yet.[/yellow]")

    console.print(f"\n[dim]Book:[/dim] {book.path}")
    console.print("[dim]Daily report:[/dim] [bold]tradingagents supertrend-rsi-report[/bold]")


@app.command("supertrend-rsi-daily")
def supertrend_rsi_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve replacement proposals."),
):
    """Daily SuperTrend+RSI portfolio job (9:30 / 11:45 / 14:30 IST every day)."""
    from tradingagents.supertrend_rsi import (
        SuperTrendRSIPaperTradeManager,
        run_supertrend_rsi_daily,
    )

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]ST+RSI daily run...", spinner="dots") as status:
        report = run_supertrend_rsi_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]supertrend_rsi daily[/bold] · chart: [cyan]1D[/cyan]\n"
        f"Date: {report.get('date')} · BUY picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="ST+RSI daily",
    ))

    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  [dim]exit[/dim] {e['ticker']} · {e['reason']} · {e.get('raw_return', 0)*100:+.1f}%")
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")

    console.print("[dim]Full report:[/dim] [bold]tradingagents supertrend-rsi-report[/bold]")


@app.command("supertrend-rsi-approve")
def supertrend_rsi_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending proposals."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Approve pending ST+RSI portfolio replacement proposals."""
    _portfolio_approve("supertrend-rsi", yes=yes, ids=ids)


@app.command("supertrend-rsi-report")
def supertrend_rsi_report():
    """Show latest ST+RSI daily portfolio report."""
    from tradingagents.supertrend_rsi import SuperTrendRSIPaperTradeManager

    manager = SuperTrendRSIPaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if report is None:
        console.print("[yellow]No daily reports yet. Run tradingagents supertrend-rsi-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]supertrend_rsi daily report[/bold]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="ST+RSI report",
    ))
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")
    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  exit {e['ticker']} · {e['reason']}")


@app.command("supertrend-rsi-explain")
def supertrend_rsi_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE)."),
    export: Optional[str] = typer.Option(None, "--export", help="Write JSON breakdown."),
):
    """Detailed SuperTrend+RSI signal analysis for one ticker."""
    from tradingagents.supertrend_rsi import explain_supertrend_rsi

    config = DEFAULT_CONFIG.copy()
    with console.status(f"[bold green]Analyzing {ticker}...", spinner="dots"):
        sig = explain_supertrend_rsi(ticker, config)

    console.print()
    _render_strsi_signal(sig)

    if export:
        import json as _json
        with open(export, "w", encoding="utf-8") as f:
            _json.dump(sig.to_dict(), f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


def _render_trama_picks(picks) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Dir", justify="center", width=5)
    table.add_column("Age", justify="right", width=4)
    table.add_column("Close", justify="right")
    table.add_column("TRAMA", justify="right")
    table.add_column("Dist%", justify="right")
    table.add_column("Remark")
    for i, p in enumerate(picks, 1):
        s = p.signal
        dir_style = "green" if s.direction == "BUY" else "red"
        table.add_row(
            str(i),
            s.symbol.replace(".NS", ""),
            f"[{dir_style}]{s.direction}[/{dir_style}]",
            str(s.cross_age),
            f"{s.close:,.2f}",
            f"{s.trama:,.2f}",
            f"{s.dist_pct:+.2f}",
            s.remark,
        )
    console.print(table)


def _render_trama_signal(sig) -> None:
    style = "green" if sig.direction == "BUY" else ("red" if sig.direction == "SELL" else "yellow")
    console.print(Panel.fit(
        f"[bold {style}]{sig.direction}[/bold {style}]  {sig.symbol}\n"
        f"{sig.remark}",
        title="TRAMA signal",
    ))
    if sig.rejected:
        console.print(f"[yellow]Rejected:[/yellow] {sig.reject_reason}")
        return
    console.print(
        f"  close={sig.close:,.2f}  trama={sig.trama:,.2f}  "
        f"dist={sig.dist_pct:+.2f}%  age={sig.cross_age}"
    )
    if sig.reasons:
        console.print("[bold]Remarks[/bold]")
        for r in sig.reasons:
            console.print(f"  [green]·[/green] {r}")


def _render_pattern_forecast_picks(picks) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Stock", no_wrap=True)
    table.add_column("Dir", justify="center", width=5)
    table.add_column("Prob%", justify="right", width=6)
    table.add_column("Score", justify="right", width=7)
    table.add_column("R:R", justify="right", width=5)
    table.add_column("Close", justify="right")
    table.add_column("Proj 5d", justify="right")
    table.add_column("Max 5d", justify="right")
    table.add_column("Move%", justify="right")
    table.add_column("Max%", justify="right")
    table.add_column("SL", justify="right")
    table.add_column("Analogue", no_wrap=True)
    for i, p in enumerate(picks, 1):
        s = p.signal
        dir_style = "green" if s.direction == "UP" else "red"
        table.add_row(
            str(i),
            s.symbol.replace(".NS", ""),
            (p.stock_name or "")[:18],
            f"[{dir_style}]{s.direction}[/{dir_style}]",
            f"{s.probability:.1f}",
            f"{s.composite_score:.3f}",
            f"{s.risk_reward:.1f}",
            f"{s.close:,.2f}",
            f"{s.projected_close_5d:,.2f}",
            f"{s.projected_max_high_5d:,.2f}",
            f"{s.projected_move_pct:+.2f}",
            f"{s.projected_max_pct:+.2f}",
            f"{s.stop_loss:,.2f}" if s.stop_loss else "—",
            s.analogue_end_date,
        )
    console.print(table)


def _render_pattern_forecast_signal(sig) -> None:
    style = "green" if sig.direction == "UP" else ("red" if sig.direction == "DOWN" else "yellow")
    console.print(Panel.fit(
        f"[bold {style}]{sig.direction}[/bold {style}]  {sig.symbol}\n"
        f"{sig.remark}",
        title="Pattern Forecast",
    ))
    if sig.rejected:
        console.print(f"[yellow]Rejected:[/yellow] {sig.reject_reason}")
        return
    console.print(
        f"  close={sig.close:,.2f}  proj_5d={sig.projected_close_5d:,.2f}  "
        f"max_5d={sig.projected_max_high_5d:,.2f}  sl={sig.stop_loss:,.2f}  corr={sig.correlation:.3f}"
    )
    if sig.reasons:
        console.print("[bold]Remarks[/bold]")
        for r in sig.reasons:
            console.print(f"  [green]-[/green] {r}")


@app.command()
def trama(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="Max signals to show."),
    max_age: Optional[int] = typer.Option(
        None, "--max-age", help="Only crossovers within last N trading days (default 3).",
    ),
    length: Optional[int] = typer.Option(
        None, "--length", help="TRAMA length (LuxAlgo default 100).",
    ),
    buy_only: bool = typer.Option(False, "--buy-only", help="Show BUY crosses only."),
    save: bool = typer.Option(True, "--save/--no-save", help="Save BUY picks to paper book."),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Screen for LuxAlgo TRAMA close crossovers (within last 3 trading days).

    BUY = close crossed above TRAMA.  SELL = close crossed below TRAMA.
    Only fresh crosses (age < max-age) are shown, with clear remarks.
    """
    from tradingagents.screening.trama_engine import STRATEGY_NAME
    from tradingagents.screening.trama_screener import screen_trama
    from tradingagents.trama import TramaPositionBook

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["trama_top_n"] = top
    if max_age is not None:
        config["trama_cross_max_age"] = max_age
    if length is not None:
        config["trama_length"] = length
        config["trama_min_bars"] = length + 5
    if buy_only:
        config["trama_directions"] = "BUY"

    console.print(Panel.fit(
        f"[bold]{STRATEGY_NAME}[/bold] v1.0 · [cyan]trama[/cyan]\n"
        "LuxAlgo TRAMA (TradingView default length=100, src=close)\n"
        "BUY opens only · SELL closes matching open longs · T1 full exit · 20d · max 4/sector\n"
        f"Freshness: cross within last [bold]{config['trama_cross_max_age']}[/bold] trading days\n"
        f"Hold check: age 1–2 must still be on signal side · Top [bold]{config['trama_top_n']}[/bold] BUY\n"
        f"Directions: [bold]{config['trama_directions']}[/bold]",
        title="TRAMA Crossover",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_trama(config, progress=lambda m: status.update(f"[bold green]{m}"))

    console.print()
    if not picks:
        console.print("[yellow]No TRAMA close crossovers in the freshness window.[/yellow]")
        console.print("[dim]Try: tradingagents trama-explain TICKER[/dim]")
        raise typer.Exit()

    _render_trama_picks(picks)
    buys = sum(1 for p in picks if p.direction == "BUY")
    sells = len(picks) - buys
    console.print(f"\n[dim]{len(picks)} signal(s): {buys} BUY · {sells} SELL[/dim]")
    console.print("[dim]Remark legend: BUY/SELL - crossover age - close vs TRAMA[/dim]")

    if save:
        book = TramaPositionBook(config)
        saved = book.save_picks(picks)
        console.print(
            f"\n[green]Saved {len(saved)} BUY position(s) to trama[/green] "
            f"[dim]({book.path})[/dim]"
        )
        if sells:
            console.print(f"[dim]Stored {sells} SELL signal(s) (used on daily to close open longs).[/dim]")
        console.print("[dim]View book:[/dim] [bold]tradingagents trama-positions[/bold]")
        console.print("[dim]Desk:[/dim] [bold]http://localhost:3000/trama[/bold]")

    if export:
        import csv
        with open(export, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "symbol", "direction", "cross_age", "close", "trama", "dist_pct", "remark",
            ])
            w.writeheader()
            for p in picks:
                s = p.signal
                w.writerow({
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "cross_age": s.cross_age,
                    "close": s.close,
                    "trama": s.trama,
                    "dist_pct": s.dist_pct,
                    "remark": s.remark,
                })
        console.print(f"[green]Exported to {export}[/green]")


@app.command("trama-positions")
def trama_positions():
    """Show TRAMA paper positions and stats."""
    from tradingagents.trama import STRATEGY_NAME, TramaPositionBook

    book = TramaPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No TRAMA positions yet. Run [bold]tradingagents trama[/bold] to screen and save.",
            title="trama",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        t.add_column("Age", justify="right")
        t.add_column("Dist%", justify="right")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("TRAMA Rs", justify="right")
        t.add_column("Stop%", justify="right")
        t.add_column("T1%", justify="right")
        t.add_column("Phase")
        t.add_column("Trail Rs", justify="right")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:20],
                str(p.get("cross_age", "—")),
                f"{p.get('dist_pct', 0):+.1f}%",
                *open_meta_cells(p),
                f"{p['entry_price']:.2f}",
                f"{p.get('trama_value', 0):.2f}",
                f"{p.get('stop_loss_pct', 0):.1f}%",
                f"+{p.get('target_1_pct', 0):.1f}%",
                p.get("phase", "initial"),
                f"{p.get('trailing_stop', p.get('stop_loss', 0)):.2f}",
            )
        console.print(t)
        console.print(
            f"[dim]{summary.get('open_positions', 0)} open · "
            f"closed this run: {summary.get('closed_now', 0)}[/dim]\n"
        )

    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed TRAMA positions")

    o = stats.get("overall", {})
    if o.get("trades"):
        msg = (
            f"\n[bold]Reliability[/bold] ({o['trades']} closed): "
            f"win rate {o['win_rate']}% · avg return {o['avg_return']:+.2f}%"
        )
        if o.get("avg_alpha") is not None:
            msg += f" · avg alpha {o['avg_alpha']:+.2f}%"
        console.print(msg)
    else:
        console.print("[yellow]No closed TRAMA trades yet.[/yellow]")

    console.print(f"\n[dim]Book:[/dim] {book.path}")
    console.print("[dim]Daily report:[/dim] [bold]tradingagents trama-report[/bold]")


@app.command("trama-daily")
def trama_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve replacement proposals."),
):
    """Daily TRAMA portfolio job (9:30 / 11:45 / 14:30 IST every day)."""
    from tradingagents.trama import run_trama_daily

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]TRAMA daily run...", spinner="dots") as status:
        report = run_trama_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]trama daily[/bold] · chart: [cyan]1D[/cyan]\n"
        f"Date: {report.get('date')} · BUY picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="TRAMA daily",
    ))

    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  [dim]exit[/dim] {e['ticker']} · {e['reason']} · {e.get('raw_return', 0)*100:+.1f}%")
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")

    console.print("[dim]Full report:[/dim] [bold]tradingagents trama-report[/bold]")


@app.command("trama-approve")
def trama_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending proposals."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Approve pending TRAMA portfolio replacement proposals."""
    _portfolio_approve("trama", yes=yes, ids=ids)


@app.command("trama-report")
def trama_report():
    """Show latest TRAMA daily portfolio report."""
    from tradingagents.trama import TramaPaperTradeManager

    manager = TramaPaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if report is None:
        console.print("[yellow]No daily reports yet. Run tradingagents trama-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]trama daily report[/bold]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="TRAMA report",
    ))
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")
    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  exit {e['ticker']} · {e['reason']}")


@app.command("trama-explain")
def trama_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE)."),
    export: Optional[str] = typer.Option(None, "--export", help="Write JSON breakdown."),
):
    """Detailed TRAMA crossover analysis for one ticker (with remarks)."""
    from tradingagents.screening.trama_engine import explain_trama

    config = DEFAULT_CONFIG.copy()
    with console.status(f"[bold green]Analyzing {ticker}...", spinner="dots"):
        sig = explain_trama(ticker, config)

    console.print()
    _render_trama_signal(sig)

    if export:
        import json as _json
        with open(export, "w", encoding="utf-8") as f:
            _json.dump(sig.to_dict(), f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


def _render_gap_fill_picks(picks) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Dir", justify="center", width=5)
    table.add_column("Age", justify="right", width=4)
    table.add_column("Gap%", justify="right")
    table.add_column("RSI", justify="right")
    table.add_column("Fill%", justify="right")
    table.add_column("Close", justify="right")
    table.add_column("Target", justify="right")
    table.add_column("Remark")
    for i, p in enumerate(picks, 1):
        s = p.signal
        dir_style = "green" if s.direction == "DOWN" else "red"
        table.add_row(
            str(i),
            s.symbol.replace(".NS", ""),
            f"[{dir_style}]{s.direction}[/{dir_style}]",
            str(s.gap_age),
            f"{s.gap_pct:+.2f}",
            f"{s.rsi:.0f}" if s.rsi else "—",
            f"{s.fill_pct:.0f}",
            f"{s.close:,.2f}",
            f"{s.fill_target:,.2f}",
            s.remark,
        )
    console.print(table)


def _render_gap_fill_signal(sig) -> None:
    style = "green" if sig.direction == "DOWN" else ("red" if sig.direction == "UP" else "yellow")
    console.print(Panel.fit(
        f"[bold {style}]{sig.direction}[/bold {style}]  {sig.symbol}\n"
        f"{sig.remark}",
        title="Gap Screener",
    ))
    if sig.rejected:
        console.print(f"[yellow]Rejected:[/yellow] {sig.reject_reason}")
        return
    console.print(
        f"  close={sig.close:,.2f}  fill_target={sig.fill_target:,.2f}  "
        f"gap={sig.gap_pct:+.2f}%  rsi={sig.rsi:.1f}  fill={sig.fill_pct:.0f}%  age={sig.gap_age}"
    )
    if sig.reasons:
        console.print("[bold]Remarks[/bold]")
        for r in sig.reasons:
            console.print(f"  [green]·[/green] {r}")


@app.command("gap-fill")
def gap_fill(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="Max signals to show."),
    max_age: Optional[int] = typer.Option(
        None, "--max-age", help="Only gaps within last N completed trading days (default 30).",
    ),
    min_pct: Optional[float] = typer.Option(
        None, "--min-pct", help="Minimum gap size in percent (default 5).",
    ),
    down_only: bool = typer.Option(False, "--down-only", help="Show gap DOWN only."),
    up_only: bool = typer.Option(False, "--up-only", help="Show gap UP only."),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Screen for active true daily gaps (pure screener, no paper book).

    Lists gap UP / gap DOWN names with gap size, age, and fill progress.
    Today's bar is excluded from gap detection while the market is open.
    """
    from tradingagents.screening.gap_fill_engine import STRATEGY_NAME
    from tradingagents.screening.gap_fill_screener import screen_gap_fill

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["gap_fill_top_n"] = top
    if max_age is not None:
        config["gap_fill_max_age"] = max_age
    if min_pct is not None:
        config["gap_fill_min_pct"] = min_pct
    if down_only:
        config["gap_fill_directions"] = "DOWN"
    elif up_only:
        config["gap_fill_directions"] = "UP"

    console.print(Panel.fit(
        f"[bold]{STRATEGY_NAME}[/bold] v2.0 · [cyan]gap-fill[/cyan]\n"
        "Pure gap screener — active true gaps on completed sessions (today excluded)\n"
        f"Gap min: [bold]{config['gap_fill_min_pct']}%[/bold] · "
        f"Lookback: [bold]{config['gap_fill_max_age']}[/bold] days · "
        f"Top [bold]{config['gap_fill_top_n']}[/bold] · "
        f"Directions: [bold]{config['gap_fill_directions']}[/bold]",
        title="Gap Screener",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_gap_fill(config, progress=lambda m: status.update(f"[bold green]{m}"))

    console.print()
    if not picks:
        console.print("[yellow]No active gaps in the lookback window.[/yellow]")
        console.print("[dim]Try: tradingagents gap-fill-explain TICKER[/dim]")
        raise typer.Exit()

    _render_gap_fill_picks(picks)
    downs = sum(1 for p in picks if p.direction == "DOWN")
    ups = len(picks) - downs
    console.print(f"\n[dim]{len(picks)} gap(s): {downs} DOWN · {ups} UP[/dim]")

    if export:
        import csv
        with open(export, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "symbol", "direction", "gap_age", "gap_pct", "fill_pct",
                "close", "fill_target", "remark",
            ])
            w.writeheader()
            for p in picks:
                s = p.signal
                w.writerow({
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "gap_age": s.gap_age,
                    "gap_pct": s.gap_pct,
                    "fill_pct": s.fill_pct,
                    "close": s.close,
                    "fill_target": s.fill_target,
                    "remark": s.remark,
                })
        console.print(f"[green]Exported to {export}[/green]")


@app.command("gap-fill-positions")
def gap_fill_positions():
    """Show Gap Fill paper positions and stats."""
    from tradingagents.gap_fill import STRATEGY_NAME, GapFillPositionBook

    book = GapFillPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No Gap Fill positions yet. Run [bold]tradingagents gap-fill[/bold] to screen and save.",
            title="gap_fill",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        t.add_column("Age", justify="right")
        t.add_column("Gap%", justify="right")
        t.add_column("Fill%", justify="right")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("Target Rs", justify="right")
        t.add_column("Stop%", justify="right")
        t.add_column("T1%", justify="right")
        t.add_column("Phase")
        t.add_column("Trail Rs", justify="right")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:20],
                str(p.get("gap_age", "—")),
                f"{p.get('gap_pct', 0):+.1f}%",
                f"{p.get('fill_pct', 0):.0f}%",
                *open_meta_cells(p),
                f"{p['entry_price']:.2f}",
                f"{p.get('fill_target', 0):.2f}",
                f"{p.get('stop_loss_pct', 0):.1f}%",
                f"+{p.get('target_1_pct', 0):.1f}%",
                p.get("phase", "initial"),
                f"{p.get('trailing_stop', p.get('stop_loss', 0)):.2f}",
            )
        console.print(t)
        console.print(
            f"[dim]{summary.get('open_positions', 0)} open · "
            f"closed this run: {summary.get('closed_now', 0)}[/dim]\n"
        )

    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed Gap Fill positions")

    o = stats.get("overall", {})
    if o.get("trades"):
        msg = (
            f"\n[bold]Reliability[/bold] ({o['trades']} closed): "
            f"win rate {o['win_rate']}% · avg return {o['avg_return']:+.2f}%"
        )
        if o.get("avg_alpha") is not None:
            msg += f" · avg alpha {o['avg_alpha']:+.2f}%"
        console.print(msg)
    else:
        console.print("[yellow]No closed Gap Fill trades yet.[/yellow]")

    console.print(f"\n[dim]Book:[/dim] {book.path}")
    console.print("[dim]Daily report:[/dim] [bold]tradingagents gap-fill-report[/bold]")


@app.command("gap-fill-reset")
def gap_fill_reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm reset without prompt."),
):
    """Clear Gap Fill paper book and pending replacement proposals."""
    from tradingagents.gap_fill import GapFillPaperTradeManager

    if not yes:
        confirmed = questionary.confirm(
            "Reset Gap Fill paper book and pending replacements?",
            default=False,
        ).ask()
        if not confirmed:
            raise typer.Exit(0)

    manager = GapFillPaperTradeManager(DEFAULT_CONFIG.copy())
    manager.reset_portfolio()
    console.print("[green]Gap Fill paper book reset.[/green]")
    console.print(f"[dim]Book:[/dim] {manager.book.path}")
    console.print("[dim]Next:[/dim] [bold]tradingagents gap-fill-daily --yes[/bold]")


@app.command("gap-fill-daily")
def gap_fill_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve replacement proposals."),
):
    """Daily Gap Fill portfolio job (9:30 / 11:45 / 14:30 IST every day)."""
    from tradingagents.gap_fill import run_gap_fill_daily

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]Gap Fill daily run...", spinner="dots") as status:
        report = run_gap_fill_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]gap_fill daily[/bold] · chart: [cyan]1D[/cyan]\n"
        f"Date: {report.get('date')} · BUY picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="Gap Fill daily",
    ))

    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  [dim]exit[/dim] {e['ticker']} · {e['reason']} · {e.get('raw_return', 0)*100:+.1f}%")
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")

    console.print("[dim]Full report:[/dim] [bold]tradingagents gap-fill-report[/bold]")


@app.command("gap-fill-approve")
def gap_fill_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending proposals."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Approve pending Gap Fill portfolio replacement proposals."""
    _portfolio_approve("gap-fill", yes=yes, ids=ids)


@app.command("gap-fill-report")
def gap_fill_report():
    """Show latest Gap Fill daily portfolio report."""
    from tradingagents.gap_fill import GapFillPaperTradeManager

    manager = GapFillPaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if report is None:
        console.print("[yellow]No daily reports yet. Run tradingagents gap-fill-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]gap_fill daily report[/bold]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="Gap Fill report",
    ))
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")
    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  exit {e['ticker']} · {e['reason']}")


@app.command("gap-fill-explain")
def gap_fill_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE)."),
    export: Optional[str] = typer.Option(None, "--export", help="Write JSON breakdown."),
):
    """Detailed Gap Fill analysis for one ticker (with remarks)."""
    from tradingagents.screening.gap_fill_engine import explain_gap_fill

    config = DEFAULT_CONFIG.copy()
    with console.status(f"[bold green]Analyzing {ticker}...", spinner="dots"):
        sig = explain_gap_fill(ticker, config)

    console.print()
    _render_gap_fill_signal(sig)

    if export:
        import json as _json
        with open(export, "w", encoding="utf-8") as f:
            _json.dump(sig.to_dict(), f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


def _render_chart_pattern_picks(picks) -> None:
    from tradingagents.screening.chart_pattern_engine import PATTERN_CATALOG
    from tradingagents.screening.chart_pattern_screener import group_chart_pattern_picks

    groups = group_chart_pattern_picks(picks)
    for pattern_id, group in groups:
        meta = PATTERN_CATALOG[pattern_id]
        bias_style = {
            "BULLISH": "green",
            "BEARISH": "red",
            "NEUTRAL": "yellow",
        }.get(meta["bias"], "white")
        title = (
            f"{meta['label']}  "
            f"[{bias_style}]{meta['bias']}[/{bias_style}]  "
            f"*{meta['stars']}  ({len(group)} hit(s))"
        )
        table = Table(title=title, show_header=True, header_style="bold")
        table.add_column("#", justify="right", style="dim", width=3)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Name", max_width=22)
        table.add_column("Age", justify="right", width=4)
        table.add_column("Status", width=12)
        table.add_column("Dist%", justify="right", width=6)
        table.add_column("Score", justify="right", width=5)
        table.add_column("Close", justify="right")
        table.add_column("Trigger", justify="right")
        for i, p in enumerate(group, 1):
            s = p.signal
            status_style = {
                "AT_TRIGGER": "bold green",
                "APPROACHING": "green",
                "NEAR_TOP": "yellow",
                "NEAR_BOTTOM": "yellow",
            }.get(s.setup_status, "white")
            table.add_row(
                str(i),
                s.symbol.replace(".NS", ""),
                p.stock_name or "—",
                str(s.pattern_age),
                f"[{status_style}]{s.setup_status}[/{status_style}]",
                f"{s.distance_to_trigger_pct:.1f}",
                f"{s.actionability_score:.0f}",
                f"{s.close:,.2f}",
                f"{s.trigger_level:,.2f}" if s.trigger_level else "—",
            )
        console.print(table)
        console.print()


def _render_chart_pattern_signals(signals) -> None:
    if not signals:
        console.print("[yellow]No patterns detected.[/yellow]")
        return
    if len(signals) == 1 and signals[0].rejected:
        console.print(f"[yellow]Rejected:[/yellow] {signals[0].reject_reason}")
        return
    for sig in signals:
        bias_style = {
            "BULLISH": "green",
            "BEARISH": "red",
            "NEUTRAL": "yellow",
        }.get(sig.bias, "white")
        console.print(Panel.fit(
            f"[bold {bias_style}]{sig.pattern_name}[/bold {bias_style}]  "
            f"{sig.bias}  {sig.stars_label}  score={sig.actionability_score:.0f}\n"
            f"{sig.setup_status} · {sig.distance_to_trigger_pct:.1f}% to trigger · age {sig.pattern_age}d\n"
            f"{sig.remark}",
            title=f"Chart Patterns — {sig.symbol}",
        ))
        if sig.reasons:
            console.print("[bold]Remarks[/bold]")
            for r in sig.reasons:
                console.print(f"  [green]·[/green] {r}")


@app.command("chart-patterns")
def chart_patterns(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="Max rows per pattern table."),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", help="Comma-separated pattern ids (e.g. double_bottom,rectangle).",
    ),
    min_confidence: Optional[float] = typer.Option(
        None, "--min-confidence", help="Minimum detection confidence (default 55).",
    ),
    bullish_only: bool = typer.Option(False, "--bullish-only", help="Show bullish patterns only."),
    bearish_only: bool = typer.Option(False, "--bearish-only", help="Show bearish patterns only."),
    max_age: Optional[int] = typer.Option(None, "--max-age", help="Max pattern age in trading days, exclusive (default 6)."),
    max_dist: Optional[float] = typer.Option(
        None, "--max-dist", help="Max %% distance to trigger for actionable setup (default 5).",
    ),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Screen for classic chart patterns (pure screener, no paper book).

    One table per pattern; rows sorted by actionability score.
    """
    from tradingagents.screening.chart_pattern_engine import STRATEGY_NAME, STRATEGY_VERSION
    from tradingagents.screening.chart_pattern_screener import screen_chart_patterns

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["chart_pattern_top_n"] = top
    if pattern is not None:
        config["chart_pattern_patterns"] = pattern
    if min_confidence is not None:
        config["chart_pattern_min_confidence"] = min_confidence
    if bullish_only:
        config["chart_pattern_bullish_only"] = True
    elif bearish_only:
        config["chart_pattern_bearish_only"] = True
    if max_age is not None:
        config["chart_pattern_max_age_days"] = max_age
    if max_dist is not None:
        config["chart_pattern_max_distance_to_trigger_pct"] = max_dist

    console.print(Panel.fit(
        f"[bold]{STRATEGY_NAME}[/bold] v{STRATEGY_VERSION} · [cyan]chart-patterns[/cyan]\n"
        "Actionable setups only — coiling near trigger inside a fresh pattern\n"
        f"History: [bold]{config['chart_pattern_history_period']}[/bold] · "
        f"Max age: [bold]<{config['chart_pattern_max_age_days']}[/bold]d · "
        f"Max dist to trigger: [bold]{config['chart_pattern_max_distance_to_trigger_pct']}[/bold]% · "
        f"Exclude today: [bold]{config['chart_pattern_exclude_today']}[/bold] · "
        f"Top [bold]{config['chart_pattern_top_n']}[/bold] per pattern",
        title="Chart Patterns",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_chart_patterns(config, progress=lambda m: status.update(f"[bold green]{m}"))

    console.print()
    if not picks:
        console.print("[yellow]No chart patterns matched the filters.[/yellow]")
        console.print("[dim]Try: tradingagents chart-patterns-explain TICKER[/dim]")
        raise typer.Exit()

    _render_chart_pattern_picks(picks)
    bullish = sum(1 for p in picks if p.bias == "BULLISH")
    bearish = sum(1 for p in picks if p.bias == "BEARISH")
    neutral = len(picks) - bullish - bearish
    console.print(
        f"\n[dim]{len(picks)} row(s): {bullish} bullish · {bearish} bearish · {neutral} neutral[/dim]"
    )

    if export:
        import csv
        with open(export, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "symbol", "pattern_id", "pattern_name", "bias", "reliability",
                "pattern_age", "setup_status", "distance_to_trigger_pct",
                "actionability_score", "confidence", "close", "trigger_level",
                "support_level", "resistance_level", "detail", "remark",
            ])
            w.writeheader()
            for p in picks:
                s = p.signal
                w.writerow({
                    "symbol": s.symbol,
                    "pattern_id": s.pattern_id,
                    "pattern_name": s.pattern_name,
                    "bias": s.bias,
                    "reliability": s.reliability,
                    "pattern_age": s.pattern_age,
                    "setup_status": s.setup_status,
                    "distance_to_trigger_pct": s.distance_to_trigger_pct,
                    "actionability_score": s.actionability_score,
                    "confidence": s.confidence,
                    "close": s.close,
                    "trigger_level": s.trigger_level,
                    "support_level": s.support_level,
                    "resistance_level": s.resistance_level,
                    "detail": s.detail,
                    "remark": s.remark,
                })
        console.print(f"[green]Exported to {export}[/green]")


@app.command("chart-patterns-explain")
def chart_patterns_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE)."),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", help="Comma-separated pattern ids to check.",
    ),
    min_confidence: Optional[float] = typer.Option(
        None, "--min-confidence", help="Minimum detection confidence.",
    ),
    export: Optional[str] = typer.Option(None, "--export", help="Write JSON breakdown."),
):
    """Detailed chart-pattern analysis for one ticker (with remarks)."""
    from tradingagents.screening.chart_pattern_engine import explain_chart_patterns

    config = DEFAULT_CONFIG.copy()
    if pattern is not None:
        config["chart_pattern_patterns"] = pattern
    if min_confidence is not None:
        config["chart_pattern_min_confidence"] = min_confidence

    with console.status(f"[bold green]Analyzing {ticker}...", spinner="dots"):
        signals = explain_chart_patterns(ticker, config)

    console.print()
    _render_chart_pattern_signals(signals)

    if export:
        import json as _json
        with open(export, "w", encoding="utf-8") as f:
            _json.dump([s.to_dict() for s in signals], f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


@app.command("candlesticks")
def candlesticks(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="Max rows per pattern table."),
    pattern: Optional[str] = typer.Option(
        None,
        "--pattern",
        help="Comma-separated pattern ids (hammer,shooting_star,bullish_engulfing,bearish_engulfing,doji).",
    ),
    min_confidence: Optional[float] = typer.Option(
        None, "--min-confidence", help="Minimum detection confidence (default 55).",
    ),
    bullish_only: bool = typer.Option(False, "--bullish-only", help="Show bullish patterns only."),
    bearish_only: bool = typer.Option(False, "--bearish-only", help="Show bearish patterns only."),
    max_age: Optional[int] = typer.Option(
        None, "--max-age", help="Max age of confirm bar in sessions (default 1).",
    ),
):
    """Screen for confirmed Japanese candlesticks (daily, pure screener, no paper book).

    Patterns require a confirmation bar after the signal candle. Also runs inside Sync now.
    """
    from tradingagents.screening.candle_engine import STRATEGY_NAME, STRATEGY_VERSION
    from tradingagents.screening.candle_screener import group_candle_picks, screen_candlesticks

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["candle_top_n"] = top
    if pattern is not None:
        config["candle_enabled"] = pattern
    if min_confidence is not None:
        config["candle_min_confidence"] = min_confidence
    if bullish_only:
        config["candle_bullish_only"] = True
    if bearish_only:
        config["candle_bearish_only"] = True
    if max_age is not None:
        config["candle_max_age_days"] = max_age

    console.print(
        f"[bold]{STRATEGY_NAME}[/bold] v{STRATEGY_VERSION} · [cyan]candlesticks[/cyan]\n"
        "[dim]Confirm bar required · daily only · no paper book[/dim]\n"
    )

    with console.status("[bold green]Scanning candlesticks...", spinner="dots"):
        picks = screen_candlesticks(config)

    if not picks:
        console.print("[yellow]No confirmed candlestick setups found.[/yellow]")
        return

    for pattern_id, group in group_candle_picks(picks):
        table = Table(show_header=True, header_style="bold", title=group[0].signal.pattern_name)
        table.add_column("#", justify="right", style="dim", width=3)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Bias", justify="center", width=8)
        table.add_column("Age", justify="right", width=4)
        table.add_column("Entry", justify="right")
        table.add_column("Stop", justify="right")
        table.add_column("T1", justify="right")
        table.add_column("R:R", justify="right")
        table.add_column("Conf", justify="right")
        for i, p in enumerate(group, 1):
            s = p.signal
            bias_style = "green" if s.bias == "BULLISH" else ("red" if s.bias == "BEARISH" else "yellow")
            table.add_row(
                str(i),
                s.symbol.replace(".NS", ""),
                f"[{bias_style}]{s.bias}[/{bias_style}]",
                str(s.pattern_age),
                f"{s.entry_level:,.2f}",
                f"{s.stop_loss:,.2f}",
                f"{s.target_1:,.2f}",
                f"{s.risk_reward_ratio:.1f}",
                f"{s.confidence:.0f}",
            )
        console.print(table)
        console.print()


@app.command("candlesticks-explain")
def candlesticks_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE)."),
    pattern: Optional[str] = typer.Option(
        None, "--pattern", help="Comma-separated pattern ids to check.",
    ),
    min_confidence: Optional[float] = typer.Option(
        None, "--min-confidence", help="Minimum detection confidence.",
    ),
):
    """Detailed candlestick analysis for one ticker (confirm bar required)."""
    from tradingagents.screening.candle_engine import explain_candlesticks

    config = DEFAULT_CONFIG.copy()
    if pattern is not None:
        config["candle_enabled"] = pattern
    if min_confidence is not None:
        config["candle_min_confidence"] = min_confidence

    with console.status(f"[bold green]Analyzing {ticker}...", spinner="dots"):
        signals = explain_candlesticks(ticker, config)

    if not signals:
        console.print(f"[yellow]No confirmed candlesticks for {ticker}.[/yellow]")
        return

    for s in signals:
        style = "green" if s.bias == "BULLISH" else ("red" if s.bias == "BEARISH" else "yellow")
        console.print(
            Panel.fit(
                f"[bold {style}]{s.bias}[/bold {style}]  {s.pattern_name}\n"
                f"{s.detail}\n"
                f"Entry {s.entry_level:.2f} · Stop {s.stop_loss:.2f} · "
                f"T1 {s.target_1:.2f} · R:R {s.risk_reward_ratio:.1f} · conf {s.confidence:.0f}",
                title=s.symbol,
            )
        )


def _render_nw_envelope_picks(picks) -> None:
    table = Table(show_header=True, header_style="bold")
    table.add_column("#", justify="right", style="dim", width=3)
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Dir", justify="center", width=5)
    table.add_column("Age", justify="right", width=4)
    table.add_column("Close", justify="right")
    table.add_column("Lower", justify="right")
    table.add_column("Upper", justify="right")
    table.add_column("Dist%", justify="right")
    table.add_column("Remark")
    for i, p in enumerate(picks, 1):
        s = p.signal
        dir_style = "green" if s.direction == "BUY" else "red"
        table.add_row(
            str(i),
            s.symbol.replace(".NS", ""),
            f"[{dir_style}]{s.direction}[/{dir_style}]",
            str(s.cross_age),
            f"{s.close:,.2f}",
            f"{s.lower:,.2f}",
            f"{s.upper:,.2f}",
            f"{s.dist_pct:+.2f}",
            s.remark,
        )
    console.print(table)


def _render_nw_envelope_signal(sig) -> None:
    style = "green" if sig.direction == "BUY" else ("red" if sig.direction == "SELL" else "yellow")
    console.print(Panel.fit(
        f"[bold {style}]{sig.direction}[/bold {style}]  {sig.symbol}\n"
        f"{sig.remark}",
        title="NW Envelope signal",
    ))
    if sig.rejected:
        console.print(f"[yellow]Rejected:[/yellow] {sig.reject_reason}")
        return
    console.print(
        f"  close={sig.close:,.2f}  mid={sig.middle:,.2f}  "
        f"lower={sig.lower:,.2f}  upper={sig.upper:,.2f}  "
        f"dist={sig.dist_pct:+.2f}%  age={sig.cross_age}"
    )
    if sig.reasons:
        console.print("[bold]Remarks[/bold]")
        for r in sig.reasons:
            console.print(f"  [green]·[/green] {r}")


@app.command("nw-envelope")
def nw_envelope(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="Max signals to show."),
    max_age: Optional[int] = typer.Option(
        None, "--max-age", help="Only crossovers within last N trading days (default 3).",
    ),
    bandwidth: Optional[float] = typer.Option(
        None, "--bandwidth", help="Gaussian bandwidth (LuxAlgo default 8.0).",
    ),
    mult: Optional[float] = typer.Option(
        None, "--mult", help="MAE multiplier (LuxAlgo default 3.0).",
    ),
    lookback: Optional[int] = typer.Option(
        None, "--lookback", help="Kernel lookback (LuxAlgo default 500).",
    ),
    buy_only: bool = typer.Option(False, "--buy-only", help="Show BUY crosses only."),
    save: bool = typer.Option(True, "--save/--no-save", help="Save BUY picks to paper book."),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Screen for LuxAlgo Nadaraya-Watson Envelope contrarian crosses.

    BUY = close crossed below lower band (oversold).  SELL = close crossed above upper.
    """
    from tradingagents.screening.nw_envelope_engine import STRATEGY_NAME
    from tradingagents.screening.nw_envelope_screener import screen_nw_envelope
    from tradingagents.nw_envelope import NwEnvelopePositionBook

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["nwe_top_n"] = top
    if max_age is not None:
        config["nwe_cross_max_age"] = max_age
    if bandwidth is not None:
        config["nwe_bandwidth"] = bandwidth
    if mult is not None:
        config["nwe_mult"] = mult
    if lookback is not None:
        config["nwe_lookback"] = lookback
    if buy_only:
        config["nwe_directions"] = "BUY"

    console.print(Panel.fit(
        f"[bold]{STRATEGY_NAME}[/bold] v1.0 · [cyan]nw_envelope[/cyan]\n"
        "LuxAlgo NWE (bw=8, mult=3, lookback=500, src=close)\n"
        "Signal: contrarian close crossover of upper/lower envelope\n"
        f"Freshness: cross within last [bold]{config['nwe_cross_max_age']}[/bold] trading days\n"
        f"Hold check: age 1–2 must still be on signal side · Top [bold]{config['nwe_top_n']}[/bold]\n"
        f"Directions: [bold]{config['nwe_directions']}[/bold]",
        title="NW Envelope",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_nw_envelope(config, progress=lambda m: status.update(f"[bold green]{m}"))

    console.print()
    if not picks:
        console.print("[yellow]No NWE envelope crossovers in the freshness window.[/yellow]")
        console.print("[dim]Try: tradingagents nw-envelope-explain TICKER[/dim]")
        raise typer.Exit()

    _render_nw_envelope_picks(picks)
    buys = sum(1 for p in picks if p.direction == "BUY")
    sells = len(picks) - buys
    console.print(f"\n[dim]{len(picks)} signal(s): {buys} BUY · {sells} SELL[/dim]")
    console.print("[dim]Remark legend: BUY/SELL - crossover age - close vs band[/dim]")

    if save:
        book = NwEnvelopePositionBook(config)
        saved = book.save_picks(picks)
        console.print(
            f"\n[green]Saved {len(saved)} BUY position(s) to nw_envelope[/green] "
            f"[dim]({book.path})[/dim]"
        )
        console.print("[dim]View book:[/dim] [bold]tradingagents nw-envelope-positions[/bold]")
        console.print("[dim]Desk:[/dim] [bold]http://localhost:3000/nw-envelope[/bold]")

    if export:
        import csv
        with open(export, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "symbol", "direction", "cross_age", "close", "middle", "lower", "upper",
                "dist_pct", "remark",
            ])
            w.writeheader()
            for p in picks:
                s = p.signal
                w.writerow({
                    "symbol": s.symbol,
                    "direction": s.direction,
                    "cross_age": s.cross_age,
                    "close": s.close,
                    "middle": s.middle,
                    "lower": s.lower,
                    "upper": s.upper,
                    "dist_pct": s.dist_pct,
                    "remark": s.remark,
                })
        console.print(f"[green]Exported to {export}[/green]")


@app.command("nw-envelope-positions")
def nw_envelope_positions():
    """Show NW Envelope paper positions and stats."""
    from tradingagents.nw_envelope import STRATEGY_NAME, NwEnvelopePositionBook

    book = NwEnvelopePositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No NW Envelope positions yet. Run [bold]tradingagents nw-envelope[/bold] to screen and save.",
            title="nw_envelope",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        t.add_column("Age", justify="right")
        t.add_column("Dist%", justify="right")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("Lower Rs", justify="right")
        t.add_column("Stop%", justify="right")
        t.add_column("T1%", justify="right")
        t.add_column("Phase")
        t.add_column("Trail Rs", justify="right")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:20],
                str(p.get("cross_age", "—")),
                f"{p.get('dist_pct', 0):+.1f}%",
                *open_meta_cells(p),
                f"{p['entry_price']:.2f}",
                f"{p.get('nwe_lower', 0):.2f}",
                f"{p.get('stop_loss_pct', 0):.1f}%",
                f"+{p.get('target_1_pct', 0):.1f}%",
                p.get("phase", "initial"),
                f"{p.get('trailing_stop', p.get('stop_loss', 0)):.2f}",
            )
        console.print(t)
        console.print(
            f"[dim]{summary.get('open_positions', 0)} open · "
            f"closed this run: {summary.get('closed_now', 0)}[/dim]\n"
        )

    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed NW Envelope positions")

    o = stats.get("overall", {})
    if o.get("trades"):
        msg = (
            f"\n[bold]Reliability[/bold] ({o['trades']} closed): "
            f"win rate {o['win_rate']}% · avg return {o['avg_return']:+.2f}%"
        )
        if o.get("avg_alpha") is not None:
            msg += f" · avg alpha {o['avg_alpha']:+.2f}%"
        console.print(msg)
    else:
        console.print("[yellow]No closed NW Envelope trades yet.[/yellow]")

    console.print(f"\n[dim]Book:[/dim] {book.path}")
    console.print("[dim]Daily report:[/dim] [bold]tradingagents nw-envelope-report[/bold]")


@app.command("nw-envelope-reset")
def nw_envelope_reset(
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm reset without prompt."),
):
    """Clear NW Envelope paper book and pending replacement proposals."""
    from tradingagents.nw_envelope import NwEnvelopePaperTradeManager

    if not yes:
        confirmed = questionary.confirm(
            "Reset NW Envelope paper book and pending replacements?",
            default=False,
        ).ask()
        if not confirmed:
            raise typer.Exit(0)

    manager = NwEnvelopePaperTradeManager(DEFAULT_CONFIG.copy())
    manager.reset_portfolio()
    console.print("[green]NW Envelope paper book reset.[/green]")
    console.print(f"[dim]Book:[/dim] {manager.book.path}")
    console.print("[dim]Next:[/dim] [bold]tradingagents nw-envelope-daily --yes[/bold]")


@app.command("nw-envelope-daily")
def nw_envelope_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve replacement proposals."),
):
    """Daily NW Envelope portfolio job (9:30 / 11:45 / 14:30 IST every day)."""
    from tradingagents.nw_envelope import run_nw_envelope_daily

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]NW Envelope daily run...", spinner="dots") as status:
        report = run_nw_envelope_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]nw_envelope daily[/bold] · chart: [cyan]1D[/cyan]\n"
        f"Date: {report.get('date')} · BUY picks: {report.get('screener_picks')} · "
        f"SELL: {report.get('sell_signals', 0)} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="NW Envelope daily",
    ))

    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  [dim]exit[/dim] {e['ticker']} · {e['reason']} · {e.get('raw_return', 0)*100:+.1f}%")
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")

    console.print("[dim]Full report:[/dim] [bold]tradingagents nw-envelope-report[/bold]")


@app.command("nw-envelope-approve")
def nw_envelope_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending proposals."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Approve pending NW Envelope portfolio replacement proposals."""
    _portfolio_approve("nw-envelope", yes=yes, ids=ids)


@app.command("nw-envelope-report")
def nw_envelope_report():
    """Show latest NW Envelope daily portfolio report."""
    from tradingagents.nw_envelope import NwEnvelopePaperTradeManager

    manager = NwEnvelopePaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if report is None:
        console.print("[yellow]No daily reports yet. Run tradingagents nw-envelope-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]nw_envelope daily report[/bold]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="NW Envelope report",
    ))
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")
    if report.get("exits"):
        for e in report["exits"]:
            console.print(f"  exit {e['ticker']} · {e['reason']}")


@app.command("nw-envelope-explain")
def nw_envelope_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE)."),
    export: Optional[str] = typer.Option(None, "--export", help="Write JSON breakdown."),
):
    """Detailed NW Envelope crossover analysis for one ticker (with remarks)."""
    from tradingagents.screening.nw_envelope_engine import explain_nw_envelope

    config = DEFAULT_CONFIG.copy()
    with console.status(f"[bold green]Analyzing {ticker}...", spinner="dots"):
        sig = explain_nw_envelope(ticker, config)

    console.print()
    _render_nw_envelope_signal(sig)

    if export:
        import json as _json
        with open(export, "w", encoding="utf-8") as f:
            _json.dump(sig.to_dict(), f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


@app.command("pattern-forecast")
def pattern_forecast(
    universe: Optional[str] = typer.Option(None, "--universe", help="CSV of NSE tickers."),
    top: Optional[int] = typer.Option(None, "--top", help="Max picks to show (default 10)."),
    min_corr: Optional[float] = typer.Option(
        None, "--min-corr", help="Minimum analogue correlation (default 0.55).",
    ),
    window: Optional[int] = typer.Option(
        None, "--window", help="Recent pattern window in trading days (default 20).",
    ),
    horizon: Optional[int] = typer.Option(
        None, "--horizon", help="Forward projection horizon in trading days (default 5).",
    ),
    up_only: bool = typer.Option(False, "--up-only", help="Show UP projections only."),
    save: bool = typer.Option(True, "--save/--no-save", help="Save UP picks to paper book."),
    export: Optional[str] = typer.Option(None, "--export", help="Write results to CSV."),
):
    """Find strongest 2y historical analogues and project 5-day direction + max high.

    v1: Pearson correlation on daily returns (Echo-inspired). Top UP picks can be
    saved to the 5-day paper desk with mandatory stop loss.
    """
    from tradingagents.screening.pattern_forecast_engine import STRATEGY_NAME
    from tradingagents.screening.pattern_forecast_screener import screen_pattern_forecast
    from tradingagents.pattern_forecast import PatternForecastPositionBook

    config = DEFAULT_CONFIG.copy()
    if universe is not None:
        config["screen_universe_csv"] = universe
    if top is not None:
        config["pattern_forecast_top_n"] = top
    if min_corr is not None:
        config["pattern_forecast_min_correlation"] = min_corr
    if window is not None:
        config["pattern_forecast_window"] = window
    if horizon is not None:
        config["pattern_forecast_horizon"] = horizon
    if up_only:
        config["pattern_forecast_directions"] = "UP"

    console.print(Panel.fit(
        f"[bold]{STRATEGY_NAME}[/bold] v1.1 · [cyan]pattern-forecast[/cyan]\n"
        "ATR stops · stock/weekly regime · Spearman consensus · 12% move cap\n"
        f"Window: [bold]{config['pattern_forecast_window']}[/bold] bars · "
        f"Project: [bold]{config['pattern_forecast_horizon']}[/bold] trading days\n"
        f"Min correlation: [bold]{config['pattern_forecast_min_correlation']}[/bold] · "
        f"Top [bold]{config['pattern_forecast_top_n']}[/bold] · "
        f"Directions: [bold]{config['pattern_forecast_directions']}[/bold]",
        title="Pattern Forecast",
    ))

    with console.status("[bold green]Screening...", spinner="dots") as status:
        picks = screen_pattern_forecast(
            config, progress=lambda m: status.update(f"[bold green]{m}")
        )

    console.print()
    if not picks:
        console.print("[yellow]No pattern forecasts above the correlation floor.[/yellow]")
        console.print("[dim]Try: tradingagents pattern-forecast-explain TICKER[/dim]")
        raise typer.Exit()

    _render_pattern_forecast_picks(picks)
    ups = sum(1 for p in picks if p.direction == "UP")
    downs = len(picks) - ups
    console.print(f"\n[dim]{len(picks)} pick(s): {ups} UP · {downs} DOWN[/dim]")
    console.print("[dim]Score = corr x hist_fwd x R:R. Desk saves UP picks only.[/dim]")

    if save:
        book = PatternForecastPositionBook(config)
        up_picks = [p for p in picks if p.direction == "UP"]
        saved = book.save_picks(up_picks)
        console.print(f"\n[green]Saved {len(saved)} UP pick(s) to paper book[/green]")

    if export:
        import csv as _csv
        with open(export, "w", newline="", encoding="utf-8") as f:
            w = _csv.writer(f)
            w.writerow([
                "symbol", "stock_name", "sector", "direction", "probability", "correlation",
                "close", "projected_close_5d", "projected_max_high_5d",
                "projected_move_pct", "projected_max_pct", "analogue_end_date", "remark",
            ])
            for p in picks:
                s = p.signal
                w.writerow([
                    s.symbol.replace(".NS", ""), p.stock_name, p.sector,
                    s.direction, s.probability, s.correlation,
                    s.close, s.projected_close_5d, s.projected_max_high_5d,
                    s.projected_move_pct, s.projected_max_pct,
                    s.analogue_end_date, s.remark,
                ])
        console.print(f"\n[green]Exported to {export}[/green]")


@app.command("pattern-forecast-positions")
def pattern_forecast_positions():
    """Show Pattern Forecast paper positions and stats."""
    from tradingagents.pattern_forecast import STRATEGY_NAME, PatternForecastPositionBook

    book = PatternForecastPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    if not book.positions:
        console.print(Panel.fit(
            "No Pattern Forecast positions yet. Run [bold]tradingagents pattern-forecast-daily[/bold].",
            title="pattern-forecast",
        ))
        raise typer.Exit()

    if open_positions:
        from cli.position_tables import add_open_meta_columns, open_meta_cells

        t = Table(box=box.SIMPLE_HEAD, title=f"{STRATEGY_NAME} — open positions")
        t.add_column("Ticker", style="bold")
        t.add_column("Stock")
        t.add_column("Score", justify="right")
        t.add_column("R:R", justify="right")
        add_open_meta_columns(t)
        t.add_column("Entry Rs", justify="right")
        t.add_column("SL Rs", justify="right")
        t.add_column("Max 5d Rs", justify="right")
        t.add_column("Proj 5d Rs", justify="right")
        t.add_column("Analogue")
        for p in open_positions:
            t.add_row(
                p["ticker"].replace(".NS", ""),
                (p.get("stock_name") or "")[:20],
                f"{p.get('probability', 0):.1f}",
                f"{p.get('risk_reward', 0):.1f}",
                *open_meta_cells(p),
                f"{p['entry_price']:,.2f}",
                f"{p['stop_loss']:,.2f}",
                f"{p.get('target_max', 0):,.2f}",
                f"{p.get('projected_close_5d', 0):,.2f}",
                p.get("analogue_end_date") or "—",
            )
        console.print(t)

    ov = stats.get("overall", {})
    console.print(
        f"\n[dim]Open {summary['open_positions']} · closed {stats.get('closed_positions', 0)} · "
        f"win rate {ov.get('win_rate')}% · avg return {ov.get('avg_return')}%[/dim]"
    )
    if closed:
        from cli.position_tables import print_closed_positions_ledger

        print_closed_positions_ledger(console, closed, title="Closed Pattern Forecast positions")


@app.command("pattern-forecast-daily")
def pattern_forecast_daily(
    force: bool = typer.Option(False, "--force", help="Deprecated no-op; daily runs every calendar day."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-approve replacement proposals."),
):
    """Run Pattern Forecast screener and update 5-day paper book."""
    from tradingagents.pattern_forecast import run_pattern_forecast_daily

    config = DEFAULT_CONFIG.copy()
    _ = yes  # foreclosure disabled; kept for CLI compatibility

    with console.status("[bold green]Running daily...", spinner="dots") as status:
        report = run_pattern_forecast_daily(
            config,
            progress=lambda m: status.update(f"[bold green]{m}"),
            force=force,
        )

    if report.get("skipped"):
        console.print(f"[yellow]Skipped:[/yellow] {report.get('reason')}")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]pattern-forecast daily[/bold]\n"
        f"UP picks: {report.get('screener_picks')} · opened: {len(report.get('opened', []))} · "
        f"exits: {len(report.get('exits', []))} · open: {report.get('open_positions')}",
        title="Pattern Forecast daily",
    ))
    if report.get("opened"):
        console.print(f"  [green]opened:[/green] {', '.join(report['opened'])}")
    for e in report.get("exits", []):
        console.print(f"  exit {e['ticker']} · {e['reason']}")


@app.command("pattern-forecast-approve")
def pattern_forecast_approve(
    yes: bool = typer.Option(False, "--yes", "-y", help="Approve all pending proposals."),
    ids: Optional[str] = typer.Option(
        None, "--ids", help="Comma-separated proposal ids to approve."
    ),
):
    """Approve pending Pattern Forecast replacement proposals."""
    _portfolio_approve("pattern-forecast", yes=yes, ids=ids)


@app.command("pattern-forecast-report")
def pattern_forecast_report():
    """Show latest Pattern Forecast daily portfolio report."""
    from tradingagents.pattern_forecast import PatternForecastPaperTradeManager

    manager = PatternForecastPaperTradeManager(DEFAULT_CONFIG.copy())
    report = manager.latest_daily_report()
    if report is None:
        console.print("[yellow]No daily reports yet. Run tradingagents pattern-forecast-daily.[/yellow]")
        raise typer.Exit()

    console.print(Panel.fit(
        f"[bold]pattern-forecast daily report[/bold]\n"
        f"Date: {report.get('date')} · picks: {report.get('screener_picks')} · "
        f"opened: {len(report.get('opened', []))} · exits: {len(report.get('exits', []))} · "
        f"open: {report.get('open_positions')}",
        title="Pattern Forecast report",
    ))


@app.command("pattern-forecast-audit")
def pattern_forecast_audit(
    sample: int = typer.Option(100, "--sample", help="Max tickers to audit (0 = full universe)."),
    step: int = typer.Option(5, "--step", help="Walk-forward step in trading days."),
):
    """Walk-forward accuracy audit on 2y history before trusting projections."""
    from tradingagents.screening.pattern_forecast_audit import audit_universe
    from tradingagents.screening.prices import download_history
    from tradingagents.screening.universe import load_universe

    config = DEFAULT_CONFIG.copy()
    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    if sample > 0:
        universe = universe[:sample]

    period = config.get("pattern_forecast_history_period", "2y")
    benchmark = config.get("paper_benchmark", "^NSEI")
    with console.status(f"[bold green]Downloading {period} for {len(universe)} tickers...", spinner="dots"):
        tickers = list(universe[:sample] if sample > 0 else universe)
        if benchmark not in tickers:
            tickers.append(benchmark)
        price_data = download_history(tickers, period=period)

    with console.status("[bold green]Running walk-forward audit (v1.7)...", spinner="dots"):
        summary = audit_universe(
            config, price_data, step=step, up_only=True, benchmark_df=price_data.get(benchmark)
        )

    d = summary.to_dict()
    console.print(Panel.fit(
        f"[bold]Pattern Forecast v1.7 audit[/bold]\n"
        f"Symbols: {d['symbols_tested']} · UP signals: {d['signals']}\n"
        f"Direction accuracy: [bold]{d['direction_accuracy_pct']}%[/bold]\n"
        f"Max-high touch rate: [bold]{d['max_touch_rate_pct']}%[/bold]\n"
        f"Stop hit rate: [bold]{d['stop_hit_rate_pct']}%[/bold]\n"
        f"Avg return (SL applied): [bold]{d['avg_return_pct']}%[/bold]\n"
        f"Win rate: [bold]{d['win_rate_pct']}%[/bold]",
        title="Audit",
    ))
    if d.get("by_probability_bucket"):
        console.print("\n[bold]By probability bucket[/bold]")
        bt = Table(box=box.SIMPLE_HEAD)
        bt.add_column("Bucket")
        bt.add_column("N", justify="right")
        bt.add_column("Dir%", justify="right")
        bt.add_column("Max%", justify="right")
        bt.add_column("Win%", justify="right")
        for bucket, stats in sorted(d["by_probability_bucket"].items(), reverse=True):
            bt.add_row(
                bucket,
                str(stats["n"]),
                f"{stats['direction_accuracy_pct']:.1f}",
                f"{stats['max_touch_rate_pct']:.1f}",
                f"{stats['win_rate_pct']:.1f}",
            )
        console.print(bt)


@app.command("pattern-forecast-explain")
def pattern_forecast_explain(
    ticker: str = typer.Argument(..., help="NSE ticker (e.g. RELIANCE)."),
    export: Optional[str] = typer.Option(None, "--export", help="Write JSON breakdown."),
):
    """Detailed 2y analogue pattern forecast for one ticker."""
    from tradingagents.screening.pattern_forecast_engine import explain_pattern_forecast

    config = DEFAULT_CONFIG.copy()
    with console.status(f"[bold green]Analyzing {ticker}...", spinner="dots"):
        sig = explain_pattern_forecast(ticker, config)

    console.print()
    _render_pattern_forecast_signal(sig)

    if export:
        import json as _json
        with open(export, "w", encoding="utf-8") as f:
            _json.dump(sig.to_dict(), f, indent=2)
        console.print(f"\n[green]Exported to {export}[/green]")


if __name__ == "__main__":
    app()

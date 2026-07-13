<p align="center">
  <img src="assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="./assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents: Multi-Agents LLM Financial Trading Framework

## News
- [2026-07] **Unified EOD price sync** — Local SQLite + CSV OHLCV store for the Nifty-500 universe (plus watchlist, custom tickers, and open positions). Scheduled pipeline syncs prices, runs all desk screeners and dailies; Command Center **Sync now** for manual catch-up.
- [2026-07] **Daily charts** — `/charts` with desk overlays (stops, targets, pattern geometry), 5m/15m intraday panel, and local-first cache (no Yahoo call per page load).
- [2026-07] **Chart Patterns screener** — Classic pattern detection (double bottom, triangles, flags, etc.) with pattern-specific trade levels, geometry on charts, and optional historical T1 audit.
- [2026-07] **Tech Desk** — LLM watchlist pipeline (`tech-analyze` → PM batch process → daily rules), dashboard at `/tech-desk`, pullback zone entries, and explicit approval for portfolio replacements.
- [2026-07] **India multi-strategy screeners** — Swing, Momentum, NSS, SuperTrend+RSI, TRAMA, NW Envelope, Pattern Forecast, Gap Fill, and Chart Patterns desks with per-strategy paper trading, shared price store, and a fully offline local dashboard (no Supabase required).
- [2026-05] **TradingAgents v0.2.5** released with the grounded Sentiment Analyst, GPT-5.5 etc. model coverage, Qwen/GLM/MiniMax dual-region support, `TRADINGAGENTS_*` env-var configurability with API-key auto-detection, remote Ollama support, non-US alpha benchmarks, and ticker path-traversal hardening. See [CHANGELOG.md](CHANGELOG.md) for the full list.
- [2026-04] **TradingAgents v0.2.4** released with structured-output agents (Research Manager, Trader, Portfolio Manager), LangGraph checkpoint resume, persistent decision log, DeepSeek/Qwen/GLM/Azure provider support, Docker, and a Windows UTF-8 encoding fix.
- [2026-03] **TradingAgents v0.2.3** released with multi-language support, GPT-5.4 family models, unified model catalog, backtesting date fidelity, and proxy support.
- [2026-03] **TradingAgents v0.2.2** released with GPT-5.4/Gemini 3.1/Claude 4.6 model coverage, five-tier rating scale, OpenAI Responses API, Anthropic effort control, and cross-platform stability.
- [2026-02] **TradingAgents v0.2.0** released with multi-provider LLM support (GPT-5.x, Gemini 3.x, Claude 4.x, Grok 4.x) and improved system architecture.
- [2026-01] **Trading-R1** [Technical Report](https://arxiv.org/abs/2509.11420) released, with [Terminal](https://github.com/TauricResearch/Trading-R1) expected to land soon.

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** officially released! We have received numerous inquiries about the work, and we would like to express our thanks for the enthusiasm in our community.
>
> So we decided to fully open-source the framework. Looking forward to building impactful projects with you!

<div align="center">

🚀 [TradingAgents](#tradingagents-framework) | ⚡ [Installation & CLI](#installation-and-cli) | 🇮🇳 [India Screeners](#india-screeners--paper-trading) | 🎬 [Demo](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [Package Usage](#tradingagents-package) | 🤝 [Contributing](#contributing) | 📄 [Citation](#citation)

</div>

## TradingAgents Framework

TradingAgents is a multi-agent trading framework that mirrors the dynamics of real-world trading firms. By deploying specialized LLM-powered agents: from fundamental analysts, sentiment experts, and technical analysts, to trader, risk management team, the platform collaboratively evaluates market conditions and informs trading decisions. Moreover, these agents engage in dynamic discussions to pinpoint the optimal strategy.

<p align="center">
  <img src="assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents framework is designed for research purposes. Trading performance may vary based on many factors, including the chosen backbone language models, model temperature, trading periods, the quality of data, and other non-deterministic factors. [It is not intended as financial, investment, or trading advice.](https://tauric.ai/disclaimer/)

Our framework decomposes complex trading tasks into specialized roles. This ensures the system achieves a robust, scalable approach to market analysis and decision-making.

### Analyst Team
- Fundamentals Analyst: Evaluates company financials and performance metrics, identifying intrinsic values and potential red flags.
- Sentiment Analyst: Aggregates news headlines, StockTwits, and Reddit chatter into a single sentiment read to gauge short-term market mood.
- News Analyst: Monitors global news and macroeconomic indicators, interpreting the impact of events on market conditions.
- Technical Analyst: Utilizes technical indicators (like MACD and RSI) to detect trading patterns and forecast price movements.

<p align="center">
  <img src="assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### Researcher Team
- Comprises both bullish and bearish researchers who critically assess the insights provided by the Analyst Team. Through structured debates, they balance potential gains against inherent risks.

<p align="center">
  <img src="assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Trader Agent
- Composes reports from the analysts and researchers to make informed trading decisions. It determines the timing and magnitude of trades based on comprehensive market insights.

<p align="center">
  <img src="assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### Risk Management and Portfolio Manager
- Continuously evaluates portfolio risk by assessing market volatility, liquidity, and other risk factors. The risk management team evaluates and adjusts trading strategies, providing assessment reports to the Portfolio Manager for final decision.
- The Portfolio Manager approves/rejects the transaction proposal. If approved, the order will be sent to the simulated exchange and executed.

<p align="center">
  <img src="assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## Installation and CLI

### Installation

Clone TradingAgents:
```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

Create a virtual environment in any of your favorite environment managers:
```bash
conda create -n tradingagents python=3.13
conda activate tradingagents
```

Install the package and its dependencies:
```bash
pip install .
```

### Docker

Alternatively, run with Docker:
```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

For local models with Ollama:
```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### Required APIs

TradingAgents supports multiple LLM providers. Set the API key for your chosen provider:

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io, M2.x, 204K ctx)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com, M2.x, 204K ctx)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

For enterprise providers (e.g. Azure OpenAI, AWS Bedrock), copy `.env.enterprise.example` to `.env.enterprise` and fill in your credentials.

For local models, configure Ollama with `llm_provider: "ollama"`. The default endpoint is `http://localhost:11434/v1`; set `OLLAMA_BASE_URL` to point at a remote `ollama-serve`. Pull models with `ollama pull <name>`, and pick "Custom model ID" in the CLI for any model not listed by default.

Alternatively, copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

### CLI Usage

Launch the interactive CLI:
```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```
You will see a screen where you can select your desired tickers, analysis date, LLM provider, research depth, and more.

<p align="center">
  <img src="assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

An interface will appear showing results as they load, letting you track the agent's progress as it runs.

<p align="center">
  <img src="assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## India Screeners + Paper Trading

Beyond analyzing a single ticker, you can **screen the NSE universe** with
multiple strategies, **paper-trade** the picks (no real money), and track P&L,
win rate, and per-signal reliability on a **local dashboard** — fully offline,
no Supabase required.

All screeners share the same Nifty-500 universe. **Daily OHLCV** is synced once into a local store (`~/.tradingagents/prices.db` + per-symbol CSV under `cache/`) via the **EOD pipeline** — screeners and charts read from disk instead of hitting Yahoo on every run.

> **New to the CLI?** See **[docs/USER_CLI_GUIDE.md](docs/USER_CLI_GUIDE.md)** — a
> beginner-friendly walkthrough for every screener, paper desk, dashboard page, and
> daily script (VS Code + Windows).

### Quick start

```bash
pip install .

# Full EOD: sync prices → all screeners → all dailies (recommended after market close):
python scripts/run_eod_pipeline.py

# Or screen / daily only (skips price re-sync if EOD already ran today):
python scripts/run_all_screeners_now.py
python scripts/run_all_daily_now.py

# Incremental price sync only:
python scripts/sync_price_cache.py

# One-time full 10y history pull (SQLite prices.db + CSV):
python scripts/run_full_10y_sync.py
# equivalent: python scripts/sync_price_cache.py --mode full --period 10y

# Chart pattern walk-forward backtest (next-day open fill; reads prices.db first):
python scripts/run_chart_pattern_backtest.py --period 10y --sample 80

# Launch the local dashboard (reads ~/.tradingagents/ JSON — no Supabase):
cd dashboard && npm install && npm run dev   # http://localhost:3000

# RS screener with AI analysis (needs OPENAI_API_KEY):
tradingagents screen --top 10
```

### EOD price sync (scheduled + manual)

After the NSE close, one pipeline refreshes prices through the last trading day, then runs every desk screener and daily job:

```bash
python scripts/run_eod_pipeline.py              # full pipeline
python scripts/run_eod_pipeline.py --force      # re-sync even if already ran today
python scripts/run_eod_if_missed.py             # catch-up at logon if PC was off at 4:10 PM
```

**Windows scheduler** (IST timezone):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/schedule_eod_pipeline.ps1
```

Registers **4:10 PM** weekday EOD plus **logon catch-up**. Dashboard **Command Center** (`/command-center`) has a **Sync now** button for the same flow.

**Sync symbol set:** Nifty 500 ∪ watchlist ∪ custom tickers ∪ open desk positions.

```bash
tradingagents custom-ticker add WIPRO    # add symbol outside universe (synced on EOD)
tradingagents custom-ticker list
python scripts/ensure_symbol_cached.py RELIANCE.NS   # warm cache for one ticker
```

### Legacy RS screener (AI-assisted)

The original funnel: `Nifty 500 → relative strength vs Nifty → technical pattern
engine (RSI breakout, volume surge, breakout-soon squeeze, ascending triangle,
cup-and-handle, pullback-in-uptrend) → composite rank → deep AI analysis on the
top N → paper-trade bullish calls & track P&L + alpha`.

```bash
# Preview the picks for free (no LLM calls):
tradingagents screen --preview

# Run the full funnel: screen, analyze the top N, open paper positions:
tradingagents screen --top 10

# View the paper portfolio: open positions, P&L, win rate, per-signal reliability:
tradingagents paper

# Refresh the dashboard snapshot without re-screening:
tradingagents sync
```

Each `screen` run marks open positions to market and closes any that have reached
their holding period, scoring return and alpha vs Nifty.

### Technical screeners (no AI calls)

Nine rule-based screeners rank setups from the same universe. Each has its own
paper book (where applicable), daily job, and dashboard desk. **Screeners run via the EOD pipeline** — individual per-desk screener buttons were removed from the dashboard; use Command Center **Sync now** instead.

| Strategy | CLI | Hold style | What it looks for |
|----------|-----|------------|-------------------|
| **Swing** | `tradingagents swing` | ~20 days | Supertrend flip, RSI 50–65, EMA20, volume, ADX |
| **Momentum** | `tradingagents momentum` | 30–90 days | EMA50>EMA200, ST buy, MACD, ADX, continuation |
| **NSS** | `tradingagents nss` | 30–90 days | Consolidation + breakout structure scoring |
| **SuperTrend+RSI** | `tradingagents supertrend-rsi` | configurable | ST(10,3) crossover + RSI confirmation + 9-part score |
| **TRAMA** | `tradingagents trama` | ~20 days | LuxAlgo TRAMA close crossover within last 3 days |
| **NW Envelope** | `tradingagents nw-envelope` | ~20 days | LuxAlgo Nadaraya-Watson envelope band crosses (contrarian) |
| **Pattern Forecast** | `tradingagents pattern-forecast` | 5 days | 2y analogue Pearson projection + mandatory stop |
| **Gap Fill** | `tradingagents gap-fill` | configurable | Active true gaps on completed sessions |
| **Chart Patterns** | `tradingagents chart-patterns` | screener only | Double bottom/top, triangles, flags, H&S, etc. (max age 6d) |

Per-strategy commands (same pattern for paper-trading desks):

```bash
tradingagents swing                    # screen + save picks
tradingagents swing-positions          # open book + stats
tradingagents swing-daily              # daily job: exits, opens, replacements
tradingagents swing-report             # closed-trade summary
```

Replace `swing` with `momentum`, `nss`, `supertrend-rsi`, `trama`, `nw-envelope`,
`pattern-forecast`, or `gap-fill` as needed. **Chart Patterns** is screener-only (no paper book).
Use `*-explain TICKER` on NSS, SuperTrend+RSI, TRAMA, NW Envelope, Gap Fill, and Pattern Forecast to debug why a name passed or failed.

```bash
python scripts/run_chart_pattern_audit.py    # historical T1 hit rates → chart_patterns/audit.json
```

### Tech Desk (LLM watchlist paper trading)

Separate from the rule-based screeners above: maintain a **watchlist**, run quick
**technical analysis** per ticker (Market Analyst only — no full multi-agent debate),
then an **AI portfolio manager** reads those saved reports and opens trades or queues
**pullback limit zones**. Daily runs are rules-only (stops, targets, time exits, zone
fills) with no extra LLM cost.

```bash
tradingagents watchlist add RELIANCE TCS       # ~/.tradingagents/watchlist.txt
tradingagents tech-analyze --watchlist         # saves to tech_reports/TICKER/DATE/
tradingagents tech-analyze -t SWIGGY.NS        # single ticker (does not add to watchlist)
tradingagents tech-desk-process                # PM: open / wait / skip (watchlist tickers)
tradingagents tech-desk-apply-process          # approve queued portfolio replacements
tradingagents tech-desk-daily                  # exits + zone fills (no LLM)
tradingagents tech-desk-positions              # open book + pending zones
tradingagents tech-desk-report               # closed-trade stats (win rate, avg R, P&L)
tradingagents tech-desk-review               # weekly memo on open positions (read only)
tradingagents tech-desk-review --apply       # execute review closes / stop raises
```

Weekly rhythm: refresh reports → **Process** → **Daily** each session → optional **Review**.
Process uses watchlist reports ≤14 days old; HOLD / wait-for-pullback setups become
pending zones rather than immediate market buys when price is above the cited entry band.

Dashboard **`/tech-desk`**: watchlist editor, pipeline P&L, Analyze / Process / Daily /
Review buttons (desk-cli jobs), blotter, and closed history. See
**[§13 Tech Desk](docs/USER_CLI_GUIDE.md#13-tech-desk-paper-trading)** in the user guide.

Per-strategy one-shot scripts:

```bash
python scripts/run_<strategy>_screener_now.py   # screen only
python scripts/run_<strategy>_daily_now.py      # screen + sync paper book
python scripts/reset_paper_capital.py           # clear closed P&L, resize open lots
```

### Run all screeners at once

The **EOD pipeline** is the preferred entry point (price sync + all screeners + all dailies).
These scripts still work standalone and skip price re-sync if EOD already completed today:

```bash
python scripts/run_eod_pipeline.py        # recommended: sync + screen + daily
python scripts/run_all_screeners_now.py   # screen all strategies
python scripts/run_all_daily_now.py       # run all daily paper-trade jobs
```

### Daily charts

Interactive daily candles with desk overlays (stop, trigger, T1, T2), pattern geometry,
SMA 50/200, and an optional 5m/15m intraday panel. Open from any desk blotter or directly:

```
/charts?ticker=RELIANCE&desk=chart-patterns&pattern_id=double_bottom
```

Data is read from the local price store; missing symbols are synced on demand.

### Local dashboard

Results are written to `~/.tradingagents/` as JSON (paper books, screen snapshots).
The Next.js dashboard reads those files directly — no cloud database setup.

```bash
cd dashboard
npm install
npm run dev          # http://localhost:3000
```

| Page | What it shows |
|------|---------------|
| `/` | RS screener overview — win rate, alpha, reliability chart |
| `/command-center` | **Sync now** (EOD pipeline), custom tickers, bulk desk actions, job monitor |
| `/charts` | Daily chart + desk overlays + intraday panel |
| `/screens` | History of RS screen runs and ranked candidates |
| `/positions` | RS paper book — open/closed trades |
| `/swing` | Swing desk blotter |
| `/momentum` | Momentum desk blotter |
| `/nss` | NSS desk blotter |
| `/supertrend-rsi` | SuperTrend+RSI desk blotter |
| `/trama` | TRAMA crossover desk blotter |
| `/nw-envelope` | Nadaraya-Watson Envelope desk blotter |
| `/pattern-forecast` | Pattern Forecast desk blotter |
| `/gap-fill` | Gap Fill desk blotter + gap screener snapshot |
| `/chart-patterns` | Chart Patterns screener blotter (links to `/charts` with pattern overlay) |
| `/tech-desk` | Tech Desk — watchlist, LLM analyze/process pipeline, paper blotter |
| `/data-health` | Local file freshness (price DB, EOD manifest, desk snapshots) |

Run **Sync now** on Command Center, `python scripts/run_eod_pipeline.py`, or any strategy's daily job to refresh data, then reload the dashboard.

Desk pages expose **Daily**, **Approve**, and **Explain** actions where applicable. Per-desk **Run screener** buttons were removed — screeners run as part of EOD.

Local data lives under `~/.tradingagents/`:

| Path | Contents |
|------|----------|
| `cache/` | Per-symbol daily OHLCV CSV (`RELIANCE.NS.csv`) + `manifest.json` (last EOD run, per-symbol `last_bar`) |
| `prices.db` | SQLite canonical OHLCV store (source for screeners; CSV exported for charts) |
| `custom_tickers.txt` | Extra symbols synced on EOD (outside Nifty 500) |
| `chart_patterns/screener.json` | Chart Patterns screener snapshot |
| `chart_patterns/audit.json` | Optional historical T1 hit-rate audit |
| `paper/paper_snapshot.json` | RS paper book snapshot for `/` and `/positions` |
| `paper/screens.json` | RS screen history for `/screens` |
| `swing/positions.json` | Swing desk |
| `momentum/positions.json` | Momentum desk |
| `nss/positions.json` | NSS desk |
| `supertrend_rsi/positions.json` | SuperTrend+RSI desk |
| `trama/positions.json` | TRAMA desk |
| `nw_envelope/positions.json` | NW Envelope desk |
| `pattern_forecast/positions.json` | Pattern Forecast desk |
| `gap_fill/positions.json` | Gap Fill desk |
| `watchlist.txt` | Tech Desk watchlist (one ticker per line) |
| `tech_reports/TICKER/DATE/market.md` | Saved `tech-analyze` reports |
| `tech_desk/positions.json` | Tech Desk open book |
| `tech_desk/pending_entries.json` | Pullback limit zones waiting for fill |
| `tech_desk/process/` | Process logs (opens, waits, replacements) |
| `tech_desk/daily/` | Daily exit / zone-fill logs |
| `logs/eod_YYYYMMDD.json` | EOD pipeline run report |

### Configuration

See `tradingagents/default_config.py` or `TRADINGAGENTS_*` env vars. Key knobs:

- **Universe:** `screen_universe_csv`, live NSE Nifty-500 download, or bundled fallback
- **RS screener:** `screen_benchmark`, `screen_top_n`, `screen_rs_min_percentile`
- **Paper (RS):** `paper_capital`, `paper_max_positions`, `paper_holding_days`
- **Per-strategy:** `swing_*`, `momentum_*`, `nss_*`, `strsi_*`, `trama_*`, `nwe_*`,
  `pattern_forecast_*`, `gap_fill_*`, `chart_pattern_*` keys for hold windows, position limits,
  stop/target R-multiples, pattern max age (`chart_pattern_max_age_days`, default 6), and book paths
- **Price store:** `data_cache_dir`, `prices_db_path`, `custom_tickers_path`; env `TRADINGAGENTS_CACHE_DIR`, `TRADINGAGENTS_PRICES_DB_PATH`
- **Tech Desk:** `tech_desk_max_positions`, `tech_desk_min_confidence`,
  `tech_desk_holding_days`, `tech_desk_max_report_age_days`, `tech_analyze_reports_dir`
- **Desk capital:** `desk_capital` (₹1L per strategy desk, equal-weight slots)

> Pattern detection (especially cup-and-handle and ascending triangle) is heuristic
> and approximate. The paper-trading layer exists precisely to measure which
> signals are worth trusting. Research only — not financial advice.

## TradingAgents Package

### Implementation Details

We built TradingAgents with LangGraph to ensure flexibility and modularity. The framework supports multiple LLM providers: OpenAI, Google, Anthropic, xAI, DeepSeek, Qwen (Alibaba DashScope, international and China endpoints), GLM (Zhipu), MiniMax (global + China), OpenRouter, Ollama for local models, and Azure OpenAI for enterprise.

### Python Usage

To use TradingAgents inside your code, you can import the `tradingagents` module and initialize a `TradingAgentsGraph()` object. The `.propagate()` function will return a decision. You can run `main.py`, here's also a quick example:

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

You can also adjust the default configuration to set your own choice of LLMs, debate rounds, etc.

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # openai, google, anthropic, xai, deepseek, qwen, qwen-cn, glm, glm-cn, minimax, minimax-cn, openrouter, ollama, azure
config["deep_think_llm"] = "gpt-5.4"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

See `tradingagents/default_config.py` for all configuration options.

## Persistence and Recovery

TradingAgents persists two kinds of state across runs.

### Decision log

The decision log is always on. Each completed run appends its decision to `~/.tradingagents/memory/trading_memory.md`. On the next run for the same ticker, TradingAgents fetches the realised return (raw and alpha vs SPY), generates a one-paragraph reflection, and injects the most recent same-ticker decisions plus recent cross-ticker lessons into the Portfolio Manager prompt, so each analysis carries forward what worked and what didn't.

Override the path with `TRADINGAGENTS_MEMORY_LOG_PATH`.

### Checkpoint resume

Checkpoint resume is opt-in via `--checkpoint`. When enabled, LangGraph saves state after each node so a crashed or interrupted run resumes from the last successful step instead of starting over. On a resume run you will see `Resuming from step N for <TICKER> on <date>` in the logs; on a new run you will see `Starting fresh`. Checkpoints are cleared automatically on successful completion.

Per-ticker SQLite databases live at `~/.tradingagents/cache/checkpoints/<TICKER>.db` (override the base with `TRADINGAGENTS_CACHE_DIR`). Use `--clear-checkpoints` to reset all of them before a run.

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

## Contributing

We welcome contributions from the community! Whether it's fixing a bug, improving documentation, or suggesting a new feature, your input helps make this project better. If you are interested in this line of research, please consider joining our open-source financial AI research community [Tauric Research](https://tauric.ai/).

Past contributions, including code, design feedback, and bug reports, are credited per release in [`CHANGELOG.md`](CHANGELOG.md).

## Citation

Please reference our work if you find *TradingAgents* provides you with some help :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```

# TradingAgents — Complete Beginner Guide (VS Code + CLI)

A plain-language guide for using **this entire project** from **VS Code on Windows**.

**What this project does (simple version):**

1. **Screens** ~500 NSE stocks for trading setups (rules-based and/or AI).
2. **Paper-trades** some strategies (fake money, no broker) to track what works.
3. **Shows results** in a local web dashboard and in the terminal.

> **Not financial advice.** Research and learning only.

---

## Table of contents

1. [One-time setup](#1-one-time-setup)
2. [Open the terminal in VS Code](#2-open-the-terminal-in-vs-code)
3. [Start the dashboard](#3-start-the-dashboard)
4. [Daily routine](#4-daily-routine-recommended)
5. [Two kinds of tools](#5-two-kinds-of-tools)
6. [Strategy cheat sheet](#6-strategy-cheat-sheet)
7. [Pure screeners (no paper book)](#7-pure-screeners-no-paper-book)
8. [Paper desks (screen + track fake trades)](#8-paper-desks-screen--track-fake-trades)
9. [RS + AI screener (uses API keys)](#9-rs--ai-screener-uses-api-keys)
10. [Deep AI analysis on one stock](#10-deep-ai-analysis-on-one-stock)
11. [Quick technical analysis (tech-analyze)](#11-quick-technical-analysis-tech-analyze)
12. [Portfolio review (all desks)](#12-portfolio-review-all-desks)
13. [Run everything at once (scripts)](#13-run-everything-at-once-scripts)
14. [Dashboard pages](#14-dashboard-pages)
15. [Where data is saved](#15-where-data-is-saved)
16. [Optional: API keys (.env)](#16-optional-api-keys-env)
17. [Troubleshooting](#17-troubleshooting)
18. [Quick reference card](#18-quick-reference-card)

---

## 1. One-time setup

### Open the project

1. Open **VS Code**
2. **File → Open Folder**
3. Select: `C:\Users\nanda\OneDrive\Desktop\TradingAgents`

### Install Python package

Open a terminal (see [section 2](#2-open-the-terminal-in-vs-code)) and run:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python -m pip install -e .
```

### Install dashboard (for browser UI)

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents\dashboard
npm install
```

### Verify CLI works

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
tradingagents --help
```

You should see a long list of commands.

**Alternative if `tradingagents` is not found:**

```powershell
python -m cli.main --help
```

(Replace `tradingagents` with `python -m cli.main` in any command below.)

---

## 2. Open the terminal in VS Code

1. Menu: **Terminal → New Terminal**
2. Bottom panel shows something like: `PS C:\...\TradingAgents>`
3. Always `cd` to the project folder first:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
```

**Tip:** Click the **+** dropdown in the terminal panel to open a **second tab** (useful: one tab for screeners, one for the dashboard).

---

## 3. Start the dashboard

In a terminal tab:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents\dashboard
npm run dev
```

Open in your browser: **http://localhost:3000**

Leave this terminal running. Press `Ctrl+C` to stop the dashboard.

**Refresh the browser** after you run screeners or daily jobs in the other terminal.

---

## 4. Daily routine (recommended)

Best time: **after market close** (so yesterday’s daily bar is complete).

### Terminal tab A — Screen everything (optional, ~5–10 min)

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python scripts/run_all_screeners_now.py
```

### Terminal tab A — Or run only what you care about

```powershell
tradingagents gap-fill
tradingagents chart-patterns
tradingagents swing
tradingagents momentum
```

### Terminal tab A — Paper desks daily job (optional)

Updates open positions, exits, new entries for strategies that use paper books:

```powershell
python scripts/run_all_daily_now.py
```

Or one desk:

```powershell
tradingagents swing-daily
tradingagents pattern-forecast-daily
```

### Terminal tab B — Dashboard

```powershell
cd dashboard
npm run dev
```

Then browse http://localhost:3000

---

## 5. Two kinds of tools

| Kind | What it does | Opens real trades? | Example commands |
|------|----------------|-------------------|------------------|
| **Pure screener** | Lists setups only | No | `gap-fill`, `chart-patterns` |
| **Paper desk** | Screens + saves to a “book” + daily P&L | No (simulated) | `swing`, `swing-daily`, `swing-positions` |
| **RS + AI** | Ranks stocks + AI writes a report | No | `screen`, `analyze` |

---

## 6. Strategy cheat sheet

| Strategy | Type | Main screen command | Hold style (paper) |
|----------|------|---------------------|--------------------|
| **Gap Screener** | Pure screener | `tradingagents gap-fill` | — |
| **Chart Patterns** | Pure screener | `tradingagents chart-patterns` | — |
| **Swing** | Paper desk | `tradingagents swing` | ~20 days |
| **Momentum** | Paper desk | `tradingagents momentum` | 30–90 days |
| **NSS** | Paper desk | `tradingagents nss` | 30–90 days |
| **SuperTrend + RSI** | Paper desk | `tradingagents supertrend-rsi` | configurable |
| **TRAMA** | Paper desk | `tradingagents trama` | ~20 days |
| **NW Envelope** | Paper desk | `tradingagents nw-envelope` | ~20 days |
| **Pattern Forecast** | Paper desk | `tradingagents pattern-forecast` | 5 days |
| **RS + patterns + AI** | AI funnel | `tradingagents screen` | RS paper book |

Every **paper desk** uses the same command pattern:

```text
tradingagents <strategy>              # screen (and usually save picks)
tradingagents <strategy>-positions    # show open book
tradingagents <strategy>-daily        # daily job: exits + new entries
tradingagents <strategy>-report       # closed trades summary
tradingagents <strategy>-approve      # approve replacement proposals (if portfolio full)
tradingagents <strategy>-explain TICKER   # one-stock detail (where available)
```

---

## 7. Pure screeners (no paper book)

### Gap Screener

Finds **active true gaps** (default ≥5%) on daily charts. Today’s bar is excluded while the market is open.

```powershell
tradingagents gap-fill
tradingagents gap-fill --down-only
tradingagents gap-fill --up-only
tradingagents gap-fill --top 20 --max-age 14 --min-pct 8
tradingagents gap-fill-explain TRENT
tradingagents gap-fill --export gaps.csv
```

| Column | Meaning |
|--------|---------|
| DOWN | Gapped down — often watched for partial fill **up** |
| UP | Gapped up — often watched for partial fill **down** |
| Gap% | Size of gap |
| Age | Trading days since gap |
| Fill% | How much already filled (info only) |

**Dashboard:** http://localhost:3000/gap-screener

**Script:**

```powershell
python scripts/run_gap_fill_screener_now.py
```

---

### Chart Patterns

Finds **classic chart patterns** (double top, H&S, flags, etc.). One **table per pattern**. Only **fresh, actionable** setups (default: pattern &lt; 14 days, within 5% of trigger). Today’s bar excluded.

```powershell
tradingagents chart-patterns
tradingagents chart-patterns --bullish-only
tradingagents chart-patterns --bearish-only
tradingagents chart-patterns --pattern double_bottom,inverse_head_shoulders
tradingagents chart-patterns --max-age 7 --max-dist 3 --top 10
tradingagents chart-patterns-explain SOBHA
tradingagents chart-patterns --export patterns.csv
```

**Pattern IDs for `--pattern`:**

`head_shoulders`, `inverse_head_shoulders`, `double_top`, `double_bottom`, `ascending_triangle`, `descending_triangle`, `rising_wedge`, `falling_wedge`, `cup_and_handle`, `bull_flag`, `bear_flag`, `pennant`, `rectangle`

| Column | Meaning |
|--------|---------|
| Age | Days since pattern completed |
| Status | `AT_TRIGGER` = at breakout level; `APPROACHING` = coiling |
| Dist% | Distance to trigger (lower = closer) |
| Score | Actionability 0–100 (higher = better now) |
| Trigger | Price level that “activates” the pattern |

**Dashboard:** http://localhost:3000/chart-patterns

**Script:**

```powershell
python scripts/run_chart_patterns_screener_now.py
```

---

## 8. Paper desks (screen + track fake trades)

### Swing

Early swing setups: Supertrend flip, RSI, EMA20, volume, ADX.

```powershell
tradingagents swing
tradingagents swing --top 15 --no-save
tradingagents swing-positions
tradingagents swing-daily
tradingagents swing-report
```

**Dashboard:** http://localhost:3000/swing  
**Script:** `python scripts/run_swing_screener_now.py` · `python scripts/run_swing_daily_now.py`

---

### Momentum

Continuation trades: EMA50 &gt; EMA200, strong trend, MACD, ADX.

```powershell
tradingagents momentum
tradingagents momentum-positions
tradingagents momentum-daily
tradingagents momentum-report
```

**Dashboard:** http://localhost:3000/momentum  
**Script:** `python scripts/run_momentum_screener_now.py` · `python scripts/run_momentum_daily_now.py`

---

### NSS (NANDA Swing Scanner)

Structure-first: consolidation, breakout scoring, explainable stages.

```powershell
tradingagents nss
tradingagents nss-diagnostics
tradingagents nss-explain RELIANCE
tradingagents nss-positions
tradingagents nss-daily
tradingagents nss-report
```

**Dashboard:** http://localhost:3000/nss  
**Script:** `python scripts/run_nss_screener_now.py` · `python scripts/run_nss_daily_now.py`

---

### SuperTrend + RSI

ST(10,3) crossover + RSI confirmation + 9-part score.

```powershell
tradingagents supertrend-rsi
tradingagents supertrend-rsi-explain TCS
tradingagents supertrend-rsi-positions
tradingagents supertrend-rsi-daily
tradingagents supertrend-rsi-report
```

**Dashboard:** http://localhost:3000/supertrend-rsi  
**Script:** `python scripts/run_supertrend_rsi_screener_now.py` · `python scripts/run_supertrend_rsi_daily_now.py`

---

### TRAMA

LuxAlgo TRAMA close crossover (buy/sell within last few days).

```powershell
tradingagents trama
tradingagents trama --buy-only
tradingagents trama-explain INFY
tradingagents trama-positions
tradingagents trama-daily
tradingagents trama-report
```

**Dashboard:** http://localhost:3000/trama  
**Script:** `python scripts/run_trama_screener_now.py` · `python scripts/run_trama_daily_now.py`

---

### NW Envelope

Nadaraya-Watson envelope band crosses (contrarian).

```powershell
tradingagents nw-envelope
tradingagents nw-envelope-explain HDFCBANK
tradingagents nw-envelope-positions
tradingagents nw-envelope-daily
tradingagents nw-envelope-report
```

**Dashboard:** http://localhost:3000/nw-envelope  
**Script:** `python scripts/run_nw_envelope_screener_now.py` · `python scripts/run_nw_envelope_daily_now.py`

---

### Pattern Forecast

5-day UP forecast from 2-year price analogues + mandatory stop.

```powershell
tradingagents pattern-forecast
tradingagents pattern-forecast-explain TCS
tradingagents pattern-forecast-audit
tradingagents pattern-forecast-positions
tradingagents pattern-forecast-daily
tradingagents pattern-forecast-report
```

**Dashboard:** http://localhost:3000/pattern-forecast  
**Script:** `python scripts/run_pattern_forecast_screener_now.py` · `python scripts/run_pattern_forecast_daily_now.py`

---

### Gap Fill desk (legacy paper book)

The **gap screener** is pure (`gap-fill`). These commands are for the **old paper desk** only if you still use it:

```powershell
tradingagents gap-fill-positions
tradingagents gap-fill-daily
tradingagents gap-fill-report
```

**Dashboard (paper book):** http://localhost:3000/gap-fill

---

## 9. RS + AI screener (uses API keys)

The **original** funnel: relative strength vs Nifty → pattern score → **AI analysis** on top names → RS paper book.

### Free preview (no AI cost)

```powershell
tradingagents screen --preview
```

### Full run (costs API tokens)

Needs `OPENAI_API_KEY` or another LLM key in `.env` (see [section 15](#15-optional-api-keys-env)).

```powershell
tradingagents screen --top 10
tradingagents screen --top 10 --yes
```

### View RS paper portfolio

```powershell
tradingagents paper
tradingagents sync
```

**Dashboard:** http://localhost:3000 (overview) · `/screens` (history) · `/positions` (RS paper book)

---

## 10. Deep AI analysis on one stock

Interactive multi-agent report on **one ticker** (fundamentals, news, technicals, risk debate).

```powershell
tradingagents analyze
```

Follow the on-screen prompts (ticker, date, model, etc.).

**Or use the dashboard:** http://localhost:3000/analyze

**Non-interactive / scripted:**

```powershell
python scripts/run_analyze_job.py
```

---

## 11. Quick technical analysis (`tech-analyze`)

A **fast, cheap slice** of the full Tauric `analyze` flow. Runs **only the Market Analyst** agent — the same one that picks up to **8 complementary indicators** from a catalog of 14 (moving averages, MACD family, RSI, Bollinger bands, ATR, VWMA), fetches price data, and writes a detailed technical report with a summary table.

**Does not run:** Sentiment, News, Fundamentals, Bull/Bear debate, Trader, or Risk teams. The full `tradingagents analyze` command is unchanged.

**Requires an API key** (same as `analyze`) — set `OPENAI_API_KEY` in `.env` or your provider’s key.

### Single ticker

```powershell
tradingagents tech-analyze --ticker SWIGGY.NS
tradingagents tech-analyze -t RELIANCE --date 2026-07-10
tradingagents tech-analyze -t TCS --language English --no-save
```

**Terminal output:** raw **markdown only** (headings, tables, indicator commentary). Status lines (`Analyzing…`, `Report saved:`) use normal CLI styling; the report body is plain markdown you can pipe or paste into a viewer.

**Saved files** (when `--save`, default on):

| File | Contents |
|------|----------|
| `market.md` | Market Analyst report |
| `complete_report.md` | Same report with header |

Default folder: `C:\Users\nanda\.tradingagents\tech_reports\<TICKER>\<DATE>\`

Example after a run:

```text
C:\Users\nanda\.tradingagents\tech_reports\SWIGGY.NS\2026-07-10\complete_report.md
```

Open in VS Code with **Markdown preview** (`Ctrl+Shift+V`) for formatted tables.

### Watchlist

Default list file: `C:\Users\nanda\.tradingagents\watchlist.txt` (one ticker per line, or CSV with `symbol` / `ticker` column).

```powershell
tradingagents watchlist add SWIGGY.NS RELIANCE TCS
tradingagents watchlist show
tradingagents tech-analyze --watchlist
tradingagents watchlist remove TCS
```

### Custom watchlist file

```powershell
tradingagents tech-analyze --watchlist-file C:\path\to\my_tickers.csv
```

### Options

| Flag | Purpose |
|------|---------|
| `--ticker` / `-t` | One symbol (e.g. `SWIGGY.NS`, `RELIANCE`) |
| `--watchlist` / `-w` | Run every symbol in the saved watchlist |
| `--watchlist-file` | Run symbols from a file |
| `--date` | As-of date `YYYY-MM-DD` (default: today) |
| `--save` / `--no-save` | Write reports to disk (default: save) |
| `--output-dir` | Override report folder |
| `--language` | Report language (`English`, etc.) |

**Rule:** use exactly one of `--ticker`, `--watchlist`, or `--watchlist-file`.

### What you get (example)

For `SWIGGY.NS`, the agent typically covers:

- Price swing / wave structure (uptrend vs downtrend, pullback vs extended)
- **8 indicators** it chose for that setup (e.g. 10 EMA, 50/200 SMA, MACD, RSI, Bollinger, ATR, volume)
- Support/resistance and pattern reads (interpretive)
- Markdown summary table + a directional note (often BUY/HOLD/SELL style)

Typical runtime: **~1–2 minutes per ticker** (Yahoo data + a few LLM tool rounds).

### vs full `analyze`

| | `tech-analyze` | `analyze` |
|--|----------------|-----------|
| Agents | Market Analyst only | All analysts + research + trader + risk |
| Cost | Low (few LLM calls) | High (many LLM calls) |
| Output | Technical markdown | Full investment memo + final decision |
| Watchlist | Built-in | One ticker per interactive run |

---

## 12. Portfolio review (all desks)

Summary across **all paper desks** — tables + optional AI memo.

```powershell
tradingagents portfolio-review
tradingagents portfolio-review --no-llm
```

Reports save under: `C:\Users\nanda\.tradingagents\portfolio_reports\`

---

## 13. Run everything at once (scripts)

All commands below are run from:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
```

| Script | What it does |
|--------|----------------|
| `python scripts/run_all_screeners_now.py` | One Yahoo download → all technical screeners |
| `python scripts/run_all_daily_now.py` | One download → all paper daily jobs |
| `python scripts/run_<strategy>_screener_now.py` | Single screener only |
| `python scripts/run_<strategy>_daily_now.py` | Single daily job only |

**`<strategy>` examples:** `swing`, `momentum`, `nss`, `trama`, `supertrend_rsi`, `nw_envelope`, `pattern_forecast`, `gap_fill`, `chart_patterns`

---

## 14. Dashboard pages

| URL | What you see |
|-----|----------------|
| http://localhost:3000/ | RS overview — win rate, reliability |
| http://localhost:3000/analyze | AI analysis UI |
| http://localhost:3000/swing | Swing paper blotter |
| http://localhost:3000/momentum | Momentum paper blotter |
| http://localhost:3000/nss | NSS paper blotter |
| http://localhost:3000/supertrend-rsi | ST+RSI paper blotter |
| http://localhost:3000/trama | TRAMA paper blotter |
| http://localhost:3000/gap-screener | **Gap pure screener snapshot** |
| http://localhost:3000/chart-patterns | **Chart patterns pure screener snapshot** |
| http://localhost:3000/gap-fill | Gap paper desk (legacy) |
| http://localhost:3000/nw-envelope | NW Envelope paper blotter |
| http://localhost:3000/pattern-forecast | Pattern Forecast paper blotter |
| http://localhost:3000/screens | RS screen history |
| http://localhost:3000/positions | RS paper positions |

---

## 15. Where data is saved

Everything lives under: **`C:\Users\nanda\.tradingagents\`**

| Folder / file | Contents |
|---------------|----------|
| `gap_fill/screener.json` | Gap screener snapshot (dashboard) |
| `chart_patterns/screener.json` | Chart patterns snapshot (dashboard) |
| `swing/positions.json` | Swing paper book |
| `momentum/positions.json` | Momentum paper book |
| `nss/positions.json` | NSS paper book |
| `supertrend_rsi/positions.json` | ST+RSI paper book |
| `trama/positions.json` | TRAMA paper book |
| `nw_envelope/positions.json` | NW Envelope paper book |
| `pattern_forecast/positions.json` | Pattern Forecast paper book |
| `gap_fill/positions.json` | Gap paper book (legacy desk) |
| `paper/paper_snapshot.json` | RS paper snapshot |
| `paper/screens.json` | RS screen history |
| `portfolio_reports/` | Portfolio review memos |
| `watchlist.txt` | Tech-analyze watchlist |
| `tech_reports/` | Quick technical analysis reports |
| `cache/` | Downloaded price cache |

---

## 16. Optional: API keys (.env)

**Not needed** for rule-based screeners (gap, chart patterns, swing, momentum, etc.).

**Needed** for:

- `tradingagents screen` (full AI analysis)
- `tradingagents analyze`
- `tradingagents tech-analyze`
- `tradingagents portfolio-review` (unless `--no-llm`)

Setup:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
copy .env.example .env
```

Edit `.env` in VS Code and add your key, e.g.:

```text
OPENAI_API_KEY=sk-...
```

---

## 17. Troubleshooting

### `tradingagents` is not recognized

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python -m pip install -e .
```

Or use: `python -m cli.main gap-fill`

### Dashboard is empty

1. Run the screener or daily job in the terminal first
2. Refresh the browser (F5)

### “No results” from a screener

Normal on quiet days. Loosen filters, e.g.:

```powershell
tradingagents chart-patterns --max-age 21 --max-dist 8
tradingagents gap-fill --max-age 30
```

### Command is slow

First run downloads ~500 stocks from Yahoo (30–90 seconds). Later runs may be faster.

### Internet required

Screeners need internet for price data.

### `npm run dev` fails

```powershell
cd dashboard
npm install
npm run dev
```

---

## 18. Quick reference card

```powershell
# --- Setup (once) ---
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python -m pip install -e .
cd dashboard && npm install

# --- Every day ---
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python scripts/run_all_screeners_now.py          # all screeners
python scripts/run_all_daily_now.py              # all paper desks (optional)

# --- Pure screeners ---
tradingagents gap-fill
tradingagents chart-patterns

# --- One paper desk example ---
tradingagents swing
tradingagents swing-daily
tradingagents swing-positions

# --- RS + AI (needs API key) ---
tradingagents screen --preview
tradingagents screen --top 10 --yes
tradingagents paper

# --- One stock deep dive ---
tradingagents analyze
tradingagents tech-analyze -t RELIANCE
tradingagents tech-analyze --watchlist
tradingagents chart-patterns-explain SOBHA
tradingagents nss-explain RELIANCE

# --- All desks summary ---
tradingagents portfolio-review --no-llm

# --- Dashboard ---
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents\dashboard
npm run dev
# → http://localhost:3000
```

---

*Last updated for branch `cursor/setup-audit-env-and-pf-schedule` — includes Gap Screener, Chart Patterns, and full India desk stack.*

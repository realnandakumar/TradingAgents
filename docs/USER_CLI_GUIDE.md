# TradingAgents — Complete Beginner Guide (VS Code + CLI)

A plain-language guide for using **this entire project** from **VS Code on Windows**.

**What this project does (simple version):**

1. **Screens** ~500 NSE stocks for trading setups (rules-based and/or AI).
2. **Paper-trades** some strategies (fake money, no broker) to track what works.
3. **Shows results** in a local web dashboard and in the terminal.

> **Not financial advice.** Research and learning only.

---

## Table of contents

0. [VS Code: make commands work (read this first)](#0-vs-code-make-commands-work-read-this-first)
1. [One-time setup](#1-one-time-setup)
2. [Open the terminal in VS Code](#2-open-the-terminal-in-vs-code)
3. [Start the dashboard](#3-start-the-dashboard)
4. [Daily & weekly routine](#4-daily--weekly-routine)
5. [Audit guide — which command when](#5-audit-guide--which-command-when)
6. [Three ways to trade (overview)](#6-three-ways-to-trade-overview)
7. [Command reference (all commands + remarks)](#7-command-reference-all-commands--remarks)
8. [Pure screeners (detail)](#8-pure-screeners-detail)
9. [Rule-based paper desks (detail)](#9-rule-based-paper-desks-detail)
10. [RS + AI funnel](#10-rs--ai-funnel)
11. [Deep AI analysis (`analyze`)](#11-deep-ai-analysis-analyze)
12. [Quick technical analysis (`tech-analyze`)](#12-quick-technical-analysis-tech-analyze)
13. [Tech Desk paper trading](#13-tech-desk-paper-trading)
14. [Portfolio review (all desks)](#14-portfolio-review-all-desks)
15. [Batch scripts](#15-batch-scripts)
16. [Dashboard pages](#16-dashboard-pages)
17. [Where data is saved](#17-where-data-is-saved)
18. [Config (`default_config.py`)](#18-config-default_configpy)
19. [Optional: API keys (.env)](#19-optional-api-keys-env)
20. [Troubleshooting](#20-troubleshooting)
21. [Quick reference card](#21-quick-reference-card)

---

## 0. VS Code: make commands work (read this first)

Most “command not found” / `ModuleNotFoundError` issues come from **VS Code using a different Python** than the one where you installed this project.

### Step A — Pick the right Python in VS Code

1. **Ctrl+Shift+P** → **Python: Select Interpreter**
2. Choose **`.venv (Python 3.13.x)`** — it should appear automatically after setup below.
3. If you do not see it: **Enter interpreter path** → browse to:
   ```
   C:\Users\nanda\OneDrive\Desktop\TradingAgents\.venv\Scripts\python.exe
   ```
4. **Avoid** the bare `Python 3.14` from `AppData\Local\Programs\...` unless you install the project into that interpreter too.

### Step B — One-time setup (project virtual env)

Open **Terminal → New Terminal** (PowerShell), then run **once**:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

*Remark: Creates an isolated `.venv` folder inside the project. VS Code will detect it automatically (see `.vscode/settings.json`).*

If `python -m venv` fails, browse to any installed Python (e.g. `C:\Users\nanda\anaconda3\python.exe`) and run:

```powershell
C:\Users\nanda\anaconda3\python.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

### Step C — Smoke test (must pass before anything else)

Run these **in order** from the project root:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python -m cli.main --help
python -m cli.main watchlist show
```

Expected: help text, then `Watchlist is empty.` (or your tickers).  
If you see `ModuleNotFoundError: No module named 'typer'`, repeat Step A + B with the correct interpreter.

### Step D — How to run commands in VS Code (two valid forms)

| Form | When to use |
|------|-------------|
| `python -m cli.main <command>` | **Recommended in VS Code** — always uses the selected interpreter |
| `tradingagents <command>` | Works only if that interpreter’s `Scripts` folder is on your PATH (often true in Anaconda, not always in VS Code) |

Examples — **same command, two spellings:**

```powershell
python -m cli.main gap-fill --help
tradingagents gap-fill --help

python -m cli.main tech-desk-positions
tradingagents tech-desk-positions
```

**Rule:** If `tradingagents` fails but `python -m cli.main` works, keep using `python -m cli.main` — nothing is broken.

### Step E — PowerShell syntax (Windows)

- Chain commands with **`;`** not `&&` (older PowerShell):
  ```powershell
  cd C:\Users\nanda\OneDrive\Desktop\TradingAgents\dashboard; npm run dev
  ```
- Batch scripts need the project root as cwd:
  ```powershell
  cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
  python scripts/run_all_screeners_now.py
  ```

---

## 1. One-time setup

### Open the project

1. Open **VS Code**
2. **File → Open Folder**
3. Select: `C:\Users\nanda\OneDrive\Desktop\TradingAgents`

### Install Python package

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python -m pip install -e .
```

*Remark: Installs the `tradingagents` command so you can run screeners and desks from the terminal.*

### Install dashboard

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents\dashboard
npm install
```

*Remark: One-time install for the local web UI at localhost:3000.*

### Verify CLI

```powershell
python -m cli.main --help
```

*Remark: Prefer this over bare `tradingagents --help` in VS Code (see [§0](#0-vs-code-make-commands-work-read-this-first)).*

Optional — if `tradingagents` is on PATH:

```powershell
tradingagents --help
```

---

## 2. Open the terminal in VS Code

**Terminal → New Terminal**, then:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
```

Use **two tabs**: one for CLI commands, one for `npm run dev` (dashboard).

---

## 3. Start the dashboard

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents\dashboard
npm run dev
```

Open **http://localhost:3000** · Press **F5** to refresh after running screeners or daily jobs.

*Remark: Reads JSON from `C:\Users\nanda\.tradingagents\` — no database setup.*

---

## 4. Daily & weekly routine

Best time: **after NSE close** (daily bar complete).

### Every trading day (pick what you use)

| Step | Command | Remark |
|------|---------|--------|
| Rule desks | `python scripts/run_all_daily_now.py` | Updates **all** rule-based paper books (swing, momentum, etc.) in one go |
| Tech Desk only | `python -m cli.main tech-desk-daily` | Checks stops, targets, time exits, and **pullback zone fills** — no AI cost |
| One desk | `python -m cli.main swing-daily` | Same as above but for swing only |

### Weekly (Tech Desk track)

| Step | Command | Remark |
|------|---------|--------|
| 1 | `python -m cli.main tech-analyze --watchlist` | Refresh AI technical reports for your watchlist (~1–2 min per ticker) |
| 2 | Delete old report folders you no longer trust | Manual cleanup under `tech_reports\` |
| 3 | `python -m cli.main tech-desk-process` | AI PM reads reports, picks best names, opens trades or sets pullback waits |
| 4 | `python -m cli.main tech-desk-review` | Optional memo on open positions — read first |
| 5 | `python -m cli.main tech-desk-review --apply` | Only if you agree — executes closes and stop raises |

### Optional (discovery)

| Step | Command | Remark |
|------|---------|--------|
| Scan NSE | `python scripts/run_all_screeners_now.py` | All rule screeners in one download — find **new** ideas |
| Check stats | `python -m cli.main tech-desk-report` | Win rate, avg R, P&L by exit type |

---

## 5. Audit guide — which command when

Use this when you are not sure what to run.

### By goal

| I want to… | Use this | Not this |
|------------|----------|----------|
| Scan **all NSE** for rule-based setups | `run_all_screeners_now.py` or `tradingagents swing` | `tech-analyze` (your list only) |
| Research **my watchlist** with AI technicals | `tech-analyze --watchlist` | Full `analyze` (overkill, expensive) |
| **Paper-trade** my watchlist from those reports | `tech-desk-process` then `tech-desk-daily` | `tech-analyze` alone (no trades) |
| Run a **systematic** paper strategy (rules only) | `swing-daily`, `momentum-daily`, etc. | Tech Desk |
| **Deep dive** one stock (news, fundamentals, debate) | `tradingagents analyze` | `tech-analyze` |
| Original **RS + AI** funnel on Nifty 500 | `tradingagents screen` | `tech-desk-process` |
| See **gaps** or **chart patterns** only (no AI) | `gap-fill`, `chart-patterns` | Paper desks |
| Check **all desks** at once | `portfolio-review --no-llm` | Opening each `-positions` |
| See open Tech Desk trades | `tech-desk-positions` or `/tech-desk` | `tech-analyze` |

### By how often

| Frequency | Must run | Nice to have |
|-----------|----------|--------------|
| **Daily** | `tech-desk-daily` (if using Tech Desk) · `run_all_daily_now.py` (if using rule desks) | Dashboard refresh |
| **Weekly** | `tech-analyze --watchlist` + `tech-desk-process` | `tech-desk-review` |
| **Monthly** | `tech-desk-report` — check win rate & foreclosure P&L | `portfolio-review` |
| **Ad hoc** | `gap-fill`, `chart-patterns`, `tech-analyze -t TICKER` | `analyze` for big decisions |

### Three tracks (do not mix them up)

```text
TRACK A — Rule screeners + rule desks
  run_all_screeners_now  →  find ideas
  swing / momentum / nss →  screen + save picks
  *-daily                →  paper P&L (no AI)

TRACK B — Tech Desk (your watchlist + AI)
  tech-analyze           →  save technical reports
  tech-desk-process      →  AI PM opens / waits
  tech-desk-daily        →  exits + zone fills (no AI)
  tech-desk-review       →  optional weekly tune-up

TRACK C — Full AI (expensive, one-off)
  analyze                →  one ticker, full memo
  screen                 →  Nifty 500 funnel + RS paper book
```

### Decision tree (simple)

```text
Do I already have a ticker list I care about?
  YES → tech-analyze → tech-desk-process → tech-desk-daily (daily)
  NO  → run_all_screeners_now OR gap-fill / chart-patterns / swing

Do I need news + fundamentals + risk debate?
  YES → analyze
  NO  → tech-analyze (technicals only)

Am I paper-trading to measure edge?
  YES → use *-daily every day + *-report / tech-desk-report monthly
  NO  → pure screeners only (gap-fill, chart-patterns)
```

### Expert audit checklist (before trusting Tech Desk)

- [ ] Reports are **&lt; 14 days** old (`tech_desk_max_report_age_days`)
- [ ] You ran `tech-desk-daily` **every session** after close
- [ ] You checked `tech-desk-report` for **foreclosure** vs **stop_loss** P&L
- [ ] You have **20+ closed trades** before judging win rate
- [ ] You read `tech-desk-review` **before** `--apply`

---

## 6. Three ways to trade (overview)

| Kind | What it does | Real money? | API key? |
|------|----------------|-------------|----------|
| **Pure screener** | Lists setups only | No | No |
| **Rule paper desk** | Rules screen → fake portfolio → daily P&L | No | No |
| **Tech Desk** | AI report → AI PM → fake portfolio → rule exits | No | Yes |
| **RS + AI** | Rank NSE → AI on top names → RS paper book | No | Yes |

---

## 7. Command reference (all commands + remarks)

Plain English for every main command. *Remark* = what it actually does.

### Setup & dashboard

| Command | Remark |
|---------|--------|
| `python -m pip install -e .` | Install/update the project CLI |
| `npm install` (in `dashboard/`) | Install dashboard dependencies |
| `npm run dev` (in `dashboard/`) | Start local website on port 3000 |

### Batch scripts

| Command | Remark |
|---------|--------|
| `python scripts/run_all_screeners_now.py` | Download prices once, run **all** rule screeners, print ranked lists |
| `python scripts/run_all_daily_now.py` | Download once, run **all** rule-based paper daily jobs (excludes Tech Desk) |
| `python scripts/run_<strategy>_screener_now.py` | Run one screener only (e.g. `run_swing_screener_now.py`) |
| `python scripts/run_<strategy>_daily_now.py` | Run one desk daily job only |
| `python scripts/run_analyze_job.py` | Headless full `analyze` for dashboard jobs |

### Pure screeners

| Command | Remark |
|---------|--------|
| `tradingagents gap-fill` | List stocks with active price gaps ≥5%; no trades |
| `tradingagents gap-fill --down-only` | Same, only gaps down |
| `tradingagents gap-fill --up-only` | Same, only gaps up |
| `tradingagents gap-fill-explain TICKER` | Show one ticker’s gap detail |
| `tradingagents gap-fill --export file.csv` | Save gap list to CSV |
| `tradingagents chart-patterns` | List chart patterns in separate tables; no trades |
| `tradingagents chart-patterns --bullish-only` | Only bullish pattern tables |
| `tradingagents chart-patterns --bearish-only` | Only bearish pattern tables |
| `tradingagents chart-patterns-explain TICKER` | One ticker’s pattern detail |
| `tradingagents chart-patterns --export file.csv` | Save pattern hits to CSV |

### Rule paper desks (replace `<strategy>`)

| Command | Remark |
|---------|--------|
| `tradingagents <strategy>` | Screen NSE, show ranked picks, usually save to paper book |
| `tradingagents <strategy> --no-save` | Screen only — do not write to book |
| `tradingagents <strategy>-positions` | Show open/closed fake positions and P&L |
| `tradingagents <strategy>-daily` | After close: run exits, open new picks, sync book |
| `tradingagents <strategy>-report` | Summary of closed trades and stats |
| `tradingagents <strategy>-approve` | Approve swapping a weak position for a new pick (when full) |
| `tradingagents <strategy>-explain TICKER` | Deep detail for one symbol (where available) |

**`<strategy>` values:** `swing`, `momentum`, `nss`, `supertrend-rsi`, `trama`, `nw-envelope`, `pattern-forecast`, `gap-fill`

*(Note: `tradingagents gap-fill` without `-daily` is the **pure gap screener** (no paper book). The **gap-fill paper desk** uses `gap-fill-daily`, `gap-fill-positions`, etc.)*

**Extra:**

| Command | Remark |
|---------|--------|
| `tradingagents nss-diagnostics` | Health check for NSS pipeline |

### RS + AI

| Command | Remark |
|---------|--------|
| `tradingagents screen --preview` | Rank NSE by RS + patterns only — **no AI cost** |
| `tradingagents screen --top 10 --yes` | Full funnel: AI analyzes top 10, may add RS paper trades |
| `tradingagents paper` | Show RS paper book P&L and reliability |
| `tradingagents sync` | Refresh RS dashboard JSON from paper book |

### Full analyze

| Command | Remark |
|---------|--------|
| `tradingagents analyze` | Interactive: all agents, full investment memo on **one** ticker |
| `tradingagents analyze --checkpoint` | Same, but can resume if it crashes |

### Tech-analyze (Market Analyst only)

| Command | Remark |
|---------|--------|
| `tradingagents tech-analyze -t TICKER` | AI technical report on one stock; saves markdown |
| `tradingagents tech-analyze --watchlist` | Run report for every ticker in `watchlist.txt` |
| `tradingagents tech-analyze --watchlist-file path` | Same from a custom CSV/txt file |
| `tradingagents tech-analyze --no-save` | Print report only — do not save to disk |
| `tradingagents tech-analyze --date YYYY-MM-DD` | As-of date for the analysis |
| `tradingagents watchlist add T1 T2` | Add tickers to default watchlist file |
| `tradingagents watchlist show` | Print current watchlist |
| `tradingagents watchlist remove T1` | Remove tickers from watchlist |

### Tech Desk

| Command | Remark |
|---------|--------|
| `tradingagents tech-desk-process` | Read **saved** tech reports → AI PM picks best → open / wait / skip |
| `tradingagents tech-desk-daily` | **Rules only:** hit stops, targets, time exit, fill pullback zones |
| `tradingagents tech-desk-review` | Weekly AI memo on open positions — **does not trade** |
| `tradingagents tech-desk-review --apply` | Same memo, then **execute** closes and stop raises |
| `tradingagents tech-desk-positions` | Show open book, pending zones, quick stats |
| `tradingagents tech-desk-report` | Win rate, avg R, P&L by exit reason (stop, target, foreclosure) |

### Portfolio

| Command | Remark |
|---------|--------|
| `tradingagents portfolio-review` | AI memo across **all** paper desks |
| `tradingagents portfolio-review --no-llm` | Tables only — free, no API |

---

## 8. Pure screeners (detail)

### Gap Screener

True gaps on daily chart; today excluded while market open.

| Column | Meaning |
|--------|---------|
| DOWN / UP | Gap direction |
| Gap% | Size of gap |
| Age | Days since gap |
| Fill% | How much filled (informational) |

**Dashboard:** http://localhost:3000/gap-screener

### Chart Patterns

13 pattern types; default &lt; 14 days old, within 5% of trigger.

**Dashboard:** http://localhost:3000/chart-patterns

**Pattern IDs:** `head_shoulders`, `inverse_head_shoulders`, `double_top`, `double_bottom`, `ascending_triangle`, `descending_triangle`, `rising_wedge`, `falling_wedge`, `cup_and_handle`, `bull_flag`, `bear_flag`, `pennant`, `rectangle`

---

## 9. Rule-based paper desks (detail)

| Strategy | Screen logic (short) | Hold | Dashboard |
|----------|---------------------|------|-----------|
| Swing | ST flip, RSI, EMA20, volume | ~20d | `/swing` |
| Momentum | EMA50&gt;200, trend, MACD | 30–90d | `/momentum` |
| NSS | Consolidation + breakout score | 30–90d | `/nss` |
| ST+RSI | Supertrend + RSI score | varies | `/supertrend-rsi` |
| TRAMA | LuxAlgo TRAMA cross | ~20d | `/trama` |
| NW Envelope | Band cross contrarian | ~20d | `/nw-envelope` |
| Pattern Forecast | 5d analogue forecast + SL | 5d | `/pattern-forecast` |

All use **₹1L desk capital**, **10 slots**, **whole shares** (same as Tech Desk sizing).

---

## 10. RS + AI funnel

```powershell
tradingagents screen --preview          # free ranking
tradingagents screen --top 10 --yes     # paid AI on top names
tradingagents paper                     # view RS paper book
```

**Dashboard:** `/` · `/screens` · `/positions`

---

## 11. Deep AI analysis (`analyze`)

```powershell
tradingagents analyze
```

Runs **Market + Sentiment + News + Fundamentals → Bull/Bear → Trader → Risk → Final decision**.

Use when: one high-conviction name, need full picture.  
Skip when: watchlist batch work → use `tech-analyze` instead.

**Dashboard:** http://localhost:3000/analyze

---

## 12. Quick technical analysis (`tech-analyze`)

**Only** the Market Analyst: picks up to **8 indicators**, writes technical markdown.

| | `tech-analyze` | `analyze` |
|--|----------------|-----------|
| Agents | Market only | All + debate |
| Cost | Low | High |
| Watchlist | Yes | One ticker |
| Output | `tech_reports/` | Full memo |

**Output:** raw markdown in terminal + saved files:

```text
C:\Users\nanda\.tradingagents\tech_reports\SWIGGY.NS\2026-07-10\complete_report.md
```

Preview in VS Code: **Ctrl+Shift+V**

**Requires API key** in `.env`.

---

## 13. Tech Desk paper trading

Turns saved `tech-analyze` reports into a **paper portfolio**.

### How entries work

| PM decision | Meaning |
|-------------|---------|
| **open** + market | Buy now at last price |
| **wait** + zone | Put in pending — buy when price hits pullback zone |
| **skip** | Pass this ticker |
| Portfolio full | Auto-sell **weakest** open name (foreclosure), open new pick |

### Workflow (copy-paste)

```powershell
python -m cli.main watchlist add SWIGGY.NS RELIANCE TCS
python -m cli.main tech-analyze --watchlist
python -m cli.main tech-desk-process
python -m cli.main tech-desk-daily
python -m cli.main tech-desk-positions
python -m cli.main tech-desk-report
```

### Settings (defaults)

| Setting | Value |
|---------|-------|
| Capital | ₹1,00,000 |
| Max positions | 10 |
| Min confidence to open | 60 |
| Max report age | 14 days |
| Daily job | Rules only (no LLM) |
| Long-only | SELL = exit only |

### Data paths

| Path | Contents |
|------|----------|
| `tech_reports\TICKER\DATE\` | Saved AI technical reports |
| `tech_desk\positions.json` | Open/closed paper trades |
| `tech_desk\pending_entries.json` | Waiting for pullback price |
| `tech_desk\process\` | Batch process logs |
| `tech_desk\daily\` | Daily exit/fill logs |

**Dashboard:** http://localhost:3000/tech-desk

Each open position stores **`report_path`** and **`report_date`** for audit.

---

## 14. Portfolio review (all desks)

```powershell
tradingagents portfolio-review --no-llm
tradingagents portfolio-review
```

Saves to: `C:\Users\nanda\.tradingagents\portfolio_reports\`

---

## 15. Batch scripts

Run from project root:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
```

| Script | Remark |
|--------|--------|
| `run_all_screeners_now.py` | One Yahoo download → all rule screeners |
| `run_all_daily_now.py` | One download → all rule desk daily jobs |
| `run_gap_fill_screener_now.py` | Gap screener only |
| `run_chart_patterns_screener_now.py` | Chart patterns only |
| `run_*_screener_now.py` | Single strategy screener |
| `run_*_daily_now.py` | Single strategy daily |

---

## 16. Dashboard pages

| URL | Remark |
|-----|--------|
| http://localhost:3000/ | RS paper overview |
| http://localhost:3000/analyze | Launch full AI analyze |
| http://localhost:3000/swing | Swing paper blotter |
| http://localhost:3000/momentum | Momentum paper blotter |
| http://localhost:3000/nss | NSS paper blotter |
| http://localhost:3000/supertrend-rsi | ST+RSI paper blotter |
| http://localhost:3000/trama | TRAMA paper blotter |
| http://localhost:3000/gap-screener | Latest gap scan snapshot |
| http://localhost:3000/chart-patterns | Latest pattern scan snapshot |
| http://localhost:3000/tech-desk | **Tech Desk** open + pending + closed |
| http://localhost:3000/nw-envelope | NW Envelope desk |
| http://localhost:3000/pattern-forecast | Pattern Forecast desk |
| http://localhost:3000/screens | RS screen history |
| http://localhost:3000/positions | RS paper positions |

---

## 17. Where data is saved

Root: **`C:\Users\nanda\.tradingagents\`**

| Path | Remark |
|------|--------|
| `watchlist.txt` | Your tech-analyze ticker list |
| `tech_reports/` | AI technical reports (input for Tech Desk) |
| `tech_desk/positions.json` | Tech Desk paper book |
| `tech_desk/pending_entries.json` | Pullback zones not filled yet |
| `gap_fill/screener.json` | Gap dashboard snapshot |
| `chart_patterns/screener.json` | Pattern dashboard snapshot |
| `swing/positions.json` | Swing paper book |
| `momentum/positions.json` | Momentum paper book |
| `nss/positions.json` | NSS paper book |
| `paper/` | RS screener paper book |
| `portfolio_reports/` | Cross-desk review memos |
| `cache/` | Downloaded price cache |

---

## 18. Config (`default_config.py`)

Key Tech Desk / tech-analyze keys in `tradingagents/default_config.py`:

| Key | Default | Remark |
|-----|---------|--------|
| `tech_watchlist_path` | `~/.tradingagents/watchlist.txt` | Watchlist file |
| `tech_analyze_reports_dir` | `~/.tradingagents/tech_reports` | Where reports are saved |
| `tech_desk_max_positions` | 10 | Max open trades |
| `tech_desk_holding_days` | 20 | Default time exit |
| `tech_desk_min_confidence` | 60 | PM must score ≥ this to open |
| `tech_desk_max_report_age_days` | 14 | Ignore older reports in process |
| `desk_capital` | 100000 | ₹1L shared sizing base |

**Env overrides:**

```env
TRADINGAGENTS_TECH_WATCHLIST_PATH=C:\path\to\watchlist.txt
TRADINGAGENTS_TECH_DESK_MAX_REPORT_AGE_DAYS=21
```

---

## 19. Optional: API keys (.env)

**Not needed:** gap-fill, chart-patterns, swing, momentum, nss, all `*-daily` rule desks, `portfolio-review --no-llm`.

**Needed:** `screen`, `analyze`, `tech-analyze`, `tech-desk-process`, `tech-desk-review`, `portfolio-review` (with LLM).

### Your project (already configured)

A `.env` file at the repo root is **already set up** for **DeepSeek**:

| Variable | Your value |
|----------|------------|
| `TRADINGAGENTS_LLM_PROVIDER` | `deepseek` |
| `TRADINGAGENTS_QUICK_THINK_LLM` | `deepseek-v4-flash` |
| `TRADINGAGENTS_DEEP_THINK_LLM` | `deepseek-v4-pro` |
| `DEEPSEEK_API_KEY` | set (loaded by CLI) |

AI commands (`tech-analyze`, `tech-desk-process`, etc.) should work without adding OpenAI.

### Verify the key loads

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
python -c "import tradingagents; from tradingagents.default_config import DEFAULT_CONFIG; import os; p=DEFAULT_CONFIG['llm_provider']; k='DEEPSEEK_API_KEY' if p=='deepseek' else 'OPENAI_API_KEY'; print('provider:', p, '| key loaded:', bool(os.environ.get(k)))"
```

Expected: `provider: deepseek | key loaded: True`

### New machine / fresh copy

```powershell
Copy-Item .env.example .env
```

Edit `.env` — sample for DeepSeek (matches this project):

```env
DEEPSEEK_API_KEY=your-deepseek-key-here
TRADINGAGENTS_LLM_PROVIDER=deepseek
TRADINGAGENTS_QUICK_THINK_LLM=deepseek-v4-flash
TRADINGAGENTS_DEEP_THINK_LLM=deepseek-v4-pro
```

For OpenAI instead, set `OPENAI_API_KEY=sk-...` and either omit `TRADINGAGENTS_LLM_PROVIDER` or set it to `openai`.

---

## 20. Troubleshooting

| Problem | What you see | Fix |
|---------|--------------|-----|
| Wrong Python in VS Code | `ModuleNotFoundError: No module named 'typer'` | Select **`.venv`** interpreter ([§0](#0-vs-code-make-commands-work-read-this-first)) or run `.\.venv\Scripts\python.exe -m pip install -e .` |
| `tradingagents` not found | `'tradingagents' is not recognized...` | Use `python -m cli.main ...` **or** install in the active env and restart terminal |
| Script fails | `can't open file 'scripts\...'` | `cd C:\Users\nanda\OneDrive\Desktop\TradingAgents` first |
| PowerShell `&&` error | `The token '&&' is not a valid statement separator` | Use `;` instead: `cd dashboard; npm run dev` |
| Dashboard empty | Page loads, no rows | Run screener/daily first, then F5 |
| Tech Desk skipped all tickers | Log says reports too old | Reports &gt; 14 days — re-run `tech-analyze --watchlist` |
| No Tech Desk opens | Process ran, book empty | Reports said HOLD + zone — check `pending_entries.json` |
| AI command fails immediately | API key error | Check `.env` at repo root — this project uses **DeepSeek** (`DEEPSEEK_API_KEY`). Run the verify one-liner in [§19](#19-optional-api-keys-env) |
| Screener empty | 0 results | Normal on quiet days; try `--max-age 60` |
| Slow first run | Long wait on first screen | Yahoo download for ~500 stocks — cached after that |
| `*-positions` / `tech-desk-report` crash in terminal | `UnicodeEncodeError: ... '\u20b9'` | **Use the dashboard** (start with `cd dashboard; npm run dev`) instead of CLI for P&amp;L tables — see table below |
| `*-daily` hangs | Prompt: "Approve foreclosure?" | Add **`--yes`**: e.g. `python -m cli.main swing-daily --yes` |

### Windows: use dashboard instead of `*-positions`

On Windows, Rich tables with ₹ can crash the VS Code terminal. **Open the dashboard** for positions and stats:

| CLI command | Dashboard URL |
|-------------|---------------|
| `tech-desk-positions` / `tech-desk-report` | http://localhost:3000/tech-desk |
| `swing-positions` / `swing-report` | http://localhost:3000/swing |
| `momentum-positions` / `momentum-report` | http://localhost:3000/momentum |
| `nss-positions` / `nss-report` | http://localhost:3000/nss |
| `supertrend-rsi-positions` | http://localhost:3000/supertrend-rsi |
| `trama-positions` / `trama-report` | http://localhost:3000/trama |
| `nw-envelope-positions` | http://localhost:3000/nw-envelope |
| `pattern-forecast-positions` | http://localhost:3000/pattern-forecast |
| `gap-fill-positions` | http://localhost:3000/gap-fill |
| `paper` | http://localhost:3000/positions |
| `portfolio-review --no-llm` | Open several desk pages above, or read `~/.tradingagents/portfolio_reports/` |

Run screeners/dailies from CLI first, then **F5** in the browser to refresh.

### Copy-paste recovery block

If nothing works, run this whole block in a **new** VS Code terminal:

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m cli.main --help
.\.venv\Scripts\python.exe -m cli.main watchlist show
.\.venv\Scripts\python.exe -m cli.main tech-desk-positions
```

All four commands should succeed (last one may say “No Tech Desk positions yet” — that is OK).

---

## 21. Quick reference card

Use `python -m cli.main` in VS Code (replace with `tradingagents` if that works on your machine).

```powershell
cd C:\Users\nanda\OneDrive\Desktop\TradingAgents

# --- VERIFY (run once after setup) ---
python -m cli.main --help
python -m cli.main watchlist show

# --- DAILY (after close) ---
python -m cli.main tech-desk-daily              # Tech Desk: stops, targets, zone fills
python scripts/run_all_daily_now.py             # All rule desks: swing, momentum, etc.

# --- WEEKLY (Tech Desk track) ---
python -m cli.main tech-analyze --watchlist     # Refresh AI reports for watchlist
python -m cli.main tech-desk-process            # AI PM: open best / set pullback waits
python -m cli.main tech-desk-review             # Read weekly memo (optional)
python -m cli.main tech-desk-review --apply     # Execute memo actions (optional)

# --- DISCOVERY (optional) ---
python scripts/run_all_screeners_now.py         # Scan NSE with all rule screeners
python -m cli.main gap-fill                     # Gaps only (no API key)
python -m cli.main chart-patterns               # Patterns only (no API key)

# --- CHECK ---
python -m cli.main tech-desk-positions          # What's open + pending zones
python -m cli.main tech-desk-report             # Win rate, avg R, P&L by exit
python -m cli.main portfolio-review --no-llm    # All desks summary (no API key)

# --- ONE STOCK DEEP DIVE ---
python -m cli.main tech-analyze -t SWIGGY.NS    # Technicals only (needs API key)
python -m cli.main analyze                      # Full AI memo (needs API key)

# --- DASHBOARD ---
cd dashboard; npm run dev                       # → http://localhost:3000/tech-desk
```

---

*Last updated: VS Code interpreter fix, `python -m cli.main` as primary invocation, audit guide, Tech Desk.*

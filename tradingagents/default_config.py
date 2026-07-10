import os

_TRADINGAGENTS_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

# Single source of truth for env-var → config-key overrides. To expose
# a new config key for environment-based override, add a row here — no
# entry-point script changes required. Coercion is driven by the type
# of the existing default, so users can keep writing plain strings in
# their .env file.
_ENV_OVERRIDES = {
    "TRADINGAGENTS_LLM_PROVIDER":         "llm_provider",
    "TRADINGAGENTS_DEEP_THINK_LLM":       "deep_think_llm",
    "TRADINGAGENTS_QUICK_THINK_LLM":      "quick_think_llm",
    "TRADINGAGENTS_LLM_BACKEND_URL":      "backend_url",
    "TRADINGAGENTS_OUTPUT_LANGUAGE":      "output_language",
    "TRADINGAGENTS_MAX_DEBATE_ROUNDS":    "max_debate_rounds",
    "TRADINGAGENTS_MAX_RISK_ROUNDS":      "max_risk_discuss_rounds",
    "TRADINGAGENTS_OPENAI_REASONING_EFFORT": "openai_reasoning_effort",
    "TRADINGAGENTS_GOOGLE_THINKING_LEVEL":   "google_thinking_level",
    "TRADINGAGENTS_ANTHROPIC_EFFORT":        "anthropic_effort",
    "TRADINGAGENTS_CHECKPOINT_ENABLED":   "checkpoint_enabled",
    "TRADINGAGENTS_BENCHMARK_TICKER":     "benchmark_ticker",
    "TRADINGAGENTS_REDDIT_MARKET":         "reddit_market",
    "TRADINGAGENTS_STOCKTWIST_MARKET":     "stocktwits_market",
    "TRADINGAGENTS_STOCKTWITS_MARKET":     "stocktwits_market",
    "TRADINGAGENTS_TOOL_RESPONSE_LOGGING_ENABLED": "tool_response_logging_enabled",
    # India RS screener + paper-trading knobs
    "TRADINGAGENTS_SCREEN_UNIVERSE_CSV":  "screen_universe_csv",
    "TRADINGAGENTS_SCREEN_BENCHMARK":     "screen_benchmark",
    "TRADINGAGENTS_SCREEN_TOP_N":         "screen_top_n",
    "TRADINGAGENTS_SCREEN_RS_MIN_PCT":    "screen_rs_min_percentile",
    "TRADINGAGENTS_SCREEN_HISTORY_PERIOD": "screen_history_period",
    "TRADINGAGENTS_PAPER_CAPITAL":        "paper_capital",
    "TRADINGAGENTS_DESK_CAPITAL":         "desk_capital",
    "TRADINGAGENTS_PAPER_MAX_POSITIONS":  "paper_max_positions",
    "TRADINGAGENTS_PAPER_HOLDING_DAYS":   "paper_holding_days",
    "TRADINGAGENTS_PAPER_SNAPSHOT_PATH":  "paper_snapshot_path",
    "TRADINGAGENTS_PAPER_SCREENS_PATH":   "paper_screens_path",
    # Swing screener knobs
    "TRADINGAGENTS_SWING_HISTORY_PERIOD": "swing_history_period",
    "TRADINGAGENTS_SWING_MIN_MARKET_CAP_CR": "swing_min_market_cap_cr",
    "TRADINGAGENTS_SWING_MIN_TRADED_VALUE_CR": "swing_min_avg_traded_value_cr",
    "TRADINGAGENTS_SWING_VOLUME_MULT": "swing_volume_mult",
    "TRADINGAGENTS_SWING_ADX_MIN": "swing_adx_min",
    "TRADINGAGENTS_SWING_TOP_N": "swing_top_n",
    "TRADINGAGENTS_SWING_FLIP_LOOKBACK": "swing_flip_lookback_sessions",
    "TRADINGAGENTS_SWING_BOOK_PATH": "swing_book_path",
    # TRAMA crossover screener
    "TRADINGAGENTS_TRAMA_LENGTH": "trama_length",
    "TRADINGAGENTS_TRAMA_CROSS_MAX_AGE": "trama_cross_max_age",
    "TRADINGAGENTS_TRAMA_TOP_N": "trama_top_n",
    "TRADINGAGENTS_TRAMA_HISTORY_PERIOD": "trama_history_period",
    "TRADINGAGENTS_TRAMA_BOOK_PATH": "trama_book_path",
    "TRADINGAGENTS_TRAMA_MAX_POSITIONS": "trama_max_positions",
    # Gap Fill screener
    "TRADINGAGENTS_GAP_FILL_HISTORY_PERIOD": "gap_fill_history_period",
    "TRADINGAGENTS_GAP_FILL_MIN_PCT": "gap_fill_min_pct",
    "TRADINGAGENTS_GAP_FILL_RSI_PERIOD": "gap_fill_rsi_period",
    "TRADINGAGENTS_GAP_FILL_RSI_OVERSOLD": "gap_fill_rsi_oversold",
    "TRADINGAGENTS_GAP_FILL_RSI_OVERBOUGHT": "gap_fill_rsi_overbought",
    "TRADINGAGENTS_GAP_FILL_MIN_OPEN_PCT": "gap_fill_min_open_pct",
    "TRADINGAGENTS_GAP_FILL_MAX_EXTENSION_PCT": "gap_fill_max_extension_pct",
    "TRADINGAGENTS_GAP_FILL_REQUIRE_FILL_BAND": "gap_fill_require_fill_band",
    "TRADINGAGENTS_GAP_FILL_MAX_AGE": "gap_fill_max_age",
    "TRADINGAGENTS_GAP_FILL_MIN_PROGRESS": "gap_fill_min_progress",
    "TRADINGAGENTS_GAP_FILL_MAX_PROGRESS": "gap_fill_max_progress",
    "TRADINGAGENTS_GAP_FILL_TOP_N": "gap_fill_top_n",
    "TRADINGAGENTS_GAP_FILL_DIRECTIONS": "gap_fill_directions",
    "TRADINGAGENTS_GAP_FILL_MAX_POSITIONS": "gap_fill_max_positions",
    "TRADINGAGENTS_GAP_FILL_HOLDING_DAYS": "gap_fill_holding_days",
    "TRADINGAGENTS_GAP_FILL_TARGET_1_RR": "gap_fill_target_1_rr",
    "TRADINGAGENTS_GAP_FILL_TARGET_2_RR": "gap_fill_target_2_rr",
    "TRADINGAGENTS_GAP_FILL_T2_EXIT_PCT": "gap_fill_t2_exit_pct",
    "TRADINGAGENTS_GAP_FILL_BOOK_PATH": "gap_fill_book_path",
    # Chart Patterns screener
    "TRADINGAGENTS_CHART_PATTERN_HISTORY_PERIOD": "chart_pattern_history_period",
    "TRADINGAGENTS_CHART_PATTERN_MIN_BARS": "chart_pattern_min_bars",
    "TRADINGAGENTS_CHART_PATTERN_SWING_ORDER": "chart_pattern_swing_order",
    "TRADINGAGENTS_CHART_PATTERN_TOP_N": "chart_pattern_top_n",
    "TRADINGAGENTS_CHART_PATTERN_ENABLED": "chart_pattern_enabled",
    "TRADINGAGENTS_CHART_PATTERN_MIN_CONFIDENCE": "chart_pattern_min_confidence",
    "TRADINGAGENTS_CHART_PATTERN_MAX_AGE_DAYS": "chart_pattern_max_age_days",
    "TRADINGAGENTS_CHART_PATTERN_MAX_BREAKOUT_PCT": "chart_pattern_max_breakout_pct",
    "TRADINGAGENTS_CHART_PATTERN_MAX_INVALIDATION_PCT": "chart_pattern_max_invalidation_pct",
    "TRADINGAGENTS_CHART_PATTERN_REQUIRE_ACTIONABLE": "chart_pattern_require_actionable",
    "TRADINGAGENTS_CHART_PATTERN_MAX_DISTANCE_TO_TRIGGER_PCT": "chart_pattern_max_distance_to_trigger_pct",
    "TRADINGAGENTS_CHART_PATTERN_MIN_POSITION_PCT": "chart_pattern_min_position_pct",
    "TRADINGAGENTS_CHART_PATTERN_MAX_POSITION_PCT": "chart_pattern_max_position_pct",
    "TRADINGAGENTS_CHART_PATTERN_EXCLUDE_TODAY": "chart_pattern_exclude_today",
    # NW Envelope screener
    "TRADINGAGENTS_NWE_BANDWIDTH": "nwe_bandwidth",
    "TRADINGAGENTS_NWE_MULT": "nwe_mult",
    "TRADINGAGENTS_NWE_LOOKBACK": "nwe_lookback",
    "TRADINGAGENTS_NWE_CROSS_MAX_AGE": "nwe_cross_max_age",
    "TRADINGAGENTS_NWE_TOP_N": "nwe_top_n",
    "TRADINGAGENTS_NWE_HISTORY_PERIOD": "nwe_history_period",
    "TRADINGAGENTS_NWE_BOOK_PATH": "nwe_book_path",
    "TRADINGAGENTS_NWE_MAX_POSITIONS": "nwe_max_positions",
    "TRADINGAGENTS_PATTERN_FORECAST_HISTORY_PERIOD": "pattern_forecast_history_period",
    "TRADINGAGENTS_PATTERN_FORECAST_TOP_N": "pattern_forecast_top_n",
    "TRADINGAGENTS_PATTERN_FORECAST_MIN_CORRELATION": "pattern_forecast_min_correlation",
    "TRADINGAGENTS_PATTERN_FORECAST_BOOK_PATH": "pattern_forecast_book_path",
    "TRADINGAGENTS_PATTERN_FORECAST_MAX_POSITIONS": "pattern_forecast_max_positions",
    "TRADINGAGENTS_TECH_WATCHLIST_PATH": "tech_watchlist_path",
}


def _coerce(value: str, reference):
    """Coerce env-var string to the type of the existing default value."""
    if isinstance(reference, bool):
        return value.strip().lower() in ("true", "1", "yes", "on")
    if isinstance(reference, int) and not isinstance(reference, bool):
        return int(value)
    if isinstance(reference, float):
        return float(value)
    return value


def _apply_env_overrides(config: dict) -> dict:
    """Apply TRADINGAGENTS_* env vars to the config dict in-place."""
    for env_var, key in _ENV_OVERRIDES.items():
        raw = os.environ.get(env_var)
        if raw is None or raw == "":
            continue
        config[key] = _coerce(raw, config.get(key))
    return config


DEFAULT_CONFIG = _apply_env_overrides({
    "project_dir": os.path.abspath(os.path.join(os.path.dirname(__file__), ".")),
    "results_dir": os.getenv("TRADINGAGENTS_RESULTS_DIR", os.path.join(_TRADINGAGENTS_HOME, "logs")),
    "data_cache_dir": os.getenv("TRADINGAGENTS_CACHE_DIR", os.path.join(_TRADINGAGENTS_HOME, "cache")),
    # Quick tech-analyze watchlist and report output
    "tech_watchlist_path": os.path.join(_TRADINGAGENTS_HOME, "watchlist.txt"),
    "tech_analyze_reports_dir": os.path.join(_TRADINGAGENTS_HOME, "tech_reports"),
    # Per-run directory for full tool response logs (StockTwits, Reddit,
    # yfinance news, technical indicators). None disables this logging; the
    # CLI sets it per run to a tool_responses/ subdir under results_dir.
    "tool_response_log_dir": None,
    # Master switch for per-run tool-response logging.
    "tool_response_logging_enabled": True,
    "memory_log_path": os.getenv("TRADINGAGENTS_MEMORY_LOG_PATH", os.path.join(_TRADINGAGENTS_HOME, "memory", "trading_memory.md")),
    # Optional cap on the number of resolved memory log entries. When set,
    # the oldest resolved entries are pruned once this limit is exceeded.
    # Pending entries are never pruned. None disables rotation entirely.
    "memory_log_max_entries": None,
    # LLM settings
    "llm_provider": "openai",
    "deep_think_llm": "gpt-5.4",
    "quick_think_llm": "gpt-5.4-mini",
    # When None, each provider's client falls back to its own default endpoint
    # (api.openai.com for OpenAI, generativelanguage.googleapis.com for Gemini, ...).
    # The CLI overrides this per provider when the user picks one. Keeping a
    # provider-specific URL here would leak (e.g. OpenAI's /v1 was previously
    # being forwarded to Gemini, producing malformed request URLs).
    "backend_url": None,
    # Provider-specific thinking configuration
    "google_thinking_level": None,      # "high", "minimal", etc.
    "openai_reasoning_effort": None,    # "medium", "high", "low"
    "anthropic_effort": None,           # "high", "medium", "low"
    # Checkpoint/resume: when True, LangGraph saves state after each node
    # so a crashed run can resume from the last successful step.
    "checkpoint_enabled": False,
    # Output language for analyst reports and final decision
    # Internal agent debate stays in English for reasoning quality
    "output_language": "English",
    # Debate and discussion settings
    "max_debate_rounds": 1,
    "max_risk_discuss_rounds": 1,
    "max_recur_limit": 100,
    "analyst_concurrency_limit": 1,
    # News / data fetching parameters
    # Increase for longer lookback strategies or to broaden macro coverage;
    # decrease to reduce token usage in agent prompts.
    "news_article_limit": 20,             # max articles per ticker (ticker-news)
    "global_news_article_limit": 10,      # max articles for global/macro news
    "global_news_lookback_days": 7,       # macro news lookback window
    # Search queries used by get_global_news for macro headlines. Extend or
    # replace to broaden geographic / sector coverage.
    "global_news_queries": [
        "Federal Reserve interest rates inflation",
        "S&P 500 earnings GDP economic outlook",
        "geopolitical risk trade war sanctions",
        "ECB Bank of England BOJ central bank policy",
        "oil commodities supply chain energy",
    ],
    # Reddit market mode for sentiment analysis. "us" preserves the original
    # subreddit set; "india" targets India-focused stock market communities.
    "reddit_market": "us",
    # StockTwits market mode for sentiment analysis. "india" maps Yahoo-style
    # NSE tickers such as TCS.NS to StockTwits cashtags such as TCS.NSE.
    "stocktwits_market": "us",
    # Data vendor configuration
    # Category-level configuration (default for all tools in category)
    "data_vendors": {
        "core_stock_apis": "yfinance",       # Options: alpha_vantage, yfinance
        "technical_indicators": "yfinance",  # Options: alpha_vantage, yfinance
        "fundamental_data": "yfinance",      # Options: alpha_vantage, yfinance
        "news_data": "yfinance",             # Options: alpha_vantage, yfinance
    },
    # Tool-level configuration (takes precedence over category-level)
    "tool_vendors": {
        # Example: "get_stock_data": "alpha_vantage",  # Override category default
    },
    # Benchmark for alpha calculation in the reflection layer.
    # ``benchmark_ticker`` (when set) overrides the suffix map for all
    # tickers; leave it None to use ``benchmark_map`` for auto-detection
    # based on the ticker's exchange suffix. SPY remains the US default
    # so the reflection label keeps reading "Alpha vs SPY" for US tickers
    # while non-US tickers get their regional index automatically.
    "benchmark_ticker": None,
    # --- India Relative-Strength screener + paper-trading ---
    # Universe: None -> live NSE Nifty 500 download (cached) with a bundled
    # fallback list; set a CSV path (or TRADINGAGENTS_SCREEN_UNIVERSE_CSV) to
    # pin an exact list.
    "screen_universe_csv": None,
    "screen_benchmark": "^NSEI",          # Nifty 50 — market baseline for RS
    "screen_history_period": "1y",        # yfinance lookback for screening
    "screen_rs_min_percentile": 50.0,     # gate: keep top X% by relative strength
    "screen_top_n": 10,                   # how many to deep-analyze with the AI
    # Paper book (no real money): used to measure reliability of the calls.
    "desk_capital": 100_000.0,            # virtual ₹ per strategy desk
    "paper_capital": 100_000.0,           # legacy RS paper book (same per-desk size)
    "paper_max_positions": 20,            # equal-weight sizing divisor
    "paper_holding_days": 20,             # trading days to hold before scoring
    "paper_benchmark": "^NSEI",           # alpha baseline for paper trades
    # Offline dashboard snapshots (local JSON — no Supabase required)
    "paper_snapshot_path": os.path.join(_TRADINGAGENTS_HOME, "paper", "paper_snapshot.json"),
    "paper_screens_path": os.path.join(_TRADINGAGENTS_HOME, "paper", "screens.json"),
    "paper_screens_history": 30,          # how many screen runs to retain locally
    # --- Swing trading screener (NSE) ---
    "swing_history_period": "2y",         # lookback for 52-week low check
    "swing_supertrend_period": 10,
    "swing_supertrend_multiplier": 3.0,
    "swing_flip_lookback_sessions": 3,    # ST Sell→Buy within last N sessions
    "swing_rsi_period": 14,
    "swing_rsi_min": 50.0,
    "swing_rsi_max": 65.0,              # momentum sweet spot
    "swing_adx_period": 14,
    "swing_adx_min": 15.0,
    "swing_volume_lookback": 20,
    "swing_volume_mult": 1.2,             # 120% of 20-day average volume
    "swing_ema_mid": 50,
    "swing_ema_mid_stack": False,       # early entry: only price > EMA20 (not 20>50)
    "swing_top_n": 10,                    # ranked shortlist size
    "swing_max_positions": 20,            # max open paper positions
    "swing_holding_days": 20,             # trading-day hold before time exit
    "swing_book_path": os.getenv(
        "TRADINGAGENTS_SWING_BOOK_PATH",
        os.path.join(_TRADINGAGENTS_HOME, "swing", "positions.json"),
    ),
    "swing_min_market_cap_cr": 5000.0,    # ₹5,000 crore
    "swing_min_avg_traded_value_cr": 10.0,  # ₹10 crore avg daily traded value
    "swing_target_1_rr": 1.5,
    "swing_target_2_rr": 2.5,
    "swing_t2_exit_pct": 75.0,            # sell this % at Target 2; trail the rest
    # Run times (IST, informational — scheduler uses scripts/schedule_swing_daily.ps1)
    "swing_run_times": ["09:30", "11:45", "14:30"],
    # --- Momentum continuation screener (NSE) ---
    "momentum_history_period": "2y",
    "momentum_supertrend_period": 10,
    "momentum_supertrend_multiplier": 3.0,
    "momentum_ema_fast": 50,
    "momentum_ema_slow": 200,
    "momentum_rsi_period": 14,
    "momentum_rsi_min": 50.0,
    "momentum_rsi_max": 65.0,
    "momentum_adx_period": 14,
    "momentum_adx_min": 20.0,
    "momentum_adx_rising_sessions": 3,
    "momentum_macd_fast": 12,
    "momentum_macd_slow": 26,
    "momentum_macd_signal": 9,
    "momentum_volume_short": 5,
    "momentum_volume_long": 20,
    "momentum_volume_min_ratio": 1.0,
    "momentum_pullback_sessions": 10,
    "momentum_hh_lookback": 10,
    "momentum_ema_pullback_tolerance": 1.02,
    "momentum_max_extension_pct": 15.0,
    "momentum_st_min_buy_sessions": 4,
    "momentum_exclude_swing_overlap": True,
    "momentum_top_n": 10,
    "momentum_max_positions": 20,
    "momentum_min_holding_days": 30,
    "momentum_max_holding_days": 90,
    "momentum_book_path": os.getenv(
        "TRADINGAGENTS_MOMENTUM_BOOK_PATH",
        os.path.join(_TRADINGAGENTS_HOME, "momentum", "positions.json"),
    ),
    "momentum_pending_path": os.path.join(_TRADINGAGENTS_HOME, "momentum", "pending_replacements.json"),
    "momentum_daily_dir": os.path.join(_TRADINGAGENTS_HOME, "momentum", "daily"),
    "momentum_min_market_cap_cr": 5000.0,
    "momentum_min_avg_traded_value_cr": 10.0,
    "momentum_target_1_rr": 1.5,
    "momentum_target_2_rr": 2.5,
    "momentum_t2_exit_pct": 75.0,
    "momentum_run_times": ["09:30", "11:45", "14:30"],
    # NANDA Swing Scanner (NSS) — structure-first early swing, top 20, 30–90 day hold
    "nss_history_period": "2y",
    "nss_supertrend_period": 10,
    "nss_supertrend_multiplier": 3.0,
    "nss_ema_fast": 50,
    "nss_ema_slow": 200,
    "nss_trend_slope_lookback": 20,
    "nss_consolidation_lookback": 15,
    "nss_consolidation_max_range_pct": 8.0,
    "nss_atr_contraction_max": 0.95,
    "nss_breakout_lookback": 20,
    "nss_breakout_fresh_sessions": 3,
    "nss_volume_lookback": 20,
    "nss_volume_mult": 1.2,
    "nss_rsi_period": 14,
    "nss_rsi_min": 45.0,
    "nss_rsi_max": 65.0,
    "nss_adx_period": 14,
    "nss_adx_min": 15.0,
    "nss_max_risk_pct": 8.0,
    "nss_exclude_swing_overlap": True,
    "nss_exclude_momentum_overlap": True,
    "nss_momentum_overlap_ext_pct": 8.0,
    "nss_weight_trend": 15,
    "nss_weight_consolidation": 30,
    "nss_weight_breakout": 25,
    "nss_weight_volume": 15,
    "nss_weight_momentum": 10,
    "nss_weight_risk": 5,
    "nss_min_score": 50.0,
    "nss_top_n": 20,
    "nss_max_positions": 20,
    "nss_min_holding_days": 30,
    "nss_max_holding_days": 90,
    "nss_book_path": os.getenv(
        "TRADINGAGENTS_NSS_BOOK_PATH",
        os.path.join(_TRADINGAGENTS_HOME, "nss", "positions.json"),
    ),
    "nss_pending_path": os.path.join(_TRADINGAGENTS_HOME, "nss", "pending_replacements.json"),
    "nss_daily_dir": os.path.join(_TRADINGAGENTS_HOME, "nss", "daily"),
    "nss_min_market_cap_cr": 5000.0,
    "nss_min_avg_traded_value_cr": 10.0,
    "nss_target_1_rr": 1.5,
    "nss_target_2_rr": 2.5,
    "nss_t2_exit_pct": 75.0,
    "nss_run_times": ["09:30", "11:45", "14:30"],
    "nss_near_miss_limit": 50,
    # v1.1 diagnostics / scoring (screening gates unchanged — mode fixed)
    "nss_threshold_mode": "fixed",
    "nss_threshold_overrides": {},
    "nss_volume_score_tiers": [
        [2.00, 10], [1.75, 9], [1.50, 8], [1.30, 6], [1.15, 4], [0, 0],
    ],
    "nss_breakout_freshness_scores": [
        [0, 25], [1, 22], [2, 20], [3, 17], [4, 12], [5, 8],
    ],
    "nss_breakout_weight_price": 0.6,
    "nss_breakout_weight_freshness": 0.4,
    "nss_volume_dryup_ratio": 0.85,
    "nss_consol_weight_range": 25,
    "nss_consol_weight_atr": 20,
    "nss_consol_weight_vol_dryup": 15,
    "nss_consol_weight_ema": 20,
    "nss_consol_weight_hl": 10,
    "nss_consol_weight_compression": 10,
    "nss_health_history_path": os.path.join(_TRADINGAGENTS_HOME, "nss", "health_history.json"),
    "nss_health_history_days": 365,
    # SuperTrend + RSI (supertrend_rsi v1.0) — independent signal strategy
    "strsi_history_period": "1y",
    "strsi_supertrend_period": 10,
    "strsi_supertrend_multiplier": 3.0,
    "strsi_rsi_period": 14,
    "strsi_rsi_ma_period": 9,
    "strsi_min_bars": 60,
    "strsi_min_score": 0,
    "strsi_mandatory_flip_max_age": 5,
    "strsi_top_n": 10,
    "strsi_min_market_cap_cr": 500.0,
    "strsi_min_avg_traded_value_cr": 1.0,
    "strsi_opposite_flip_lookback": 3,
    "strsi_min_atr": 0.0,
    "strsi_min_body_pct": 0.15,
    "strsi_max_st_distance_atr": 3.0,
    "strsi_min_volume_ratio": 0.60,
    "strsi_max_positions": 10,
    "strsi_holding_days": 20,
    "strsi_target_1_rr": 1.5,
    "strsi_target_2_rr": 2.5,
    "strsi_t2_exit_pct": 75.0,
    "strsi_book_path": os.getenv(
        "TRADINGAGENTS_STRSI_BOOK_PATH",
        os.path.join(_TRADINGAGENTS_HOME, "supertrend_rsi", "positions.json"),
    ),
    "strsi_pending_path": os.path.join(_TRADINGAGENTS_HOME, "supertrend_rsi", "pending_replacements.json"),
    "strsi_daily_dir": os.path.join(_TRADINGAGENTS_HOME, "supertrend_rsi", "daily"),
    "strsi_run_times": ["09:30", "11:45", "14:30"],
    # TRAMA Crossover (LuxAlgo) — close crosses TRAMA within last N days
    "trama_history_period": "1y",
    "trama_length": 100,                  # LuxAlgo TradingView default
    "trama_min_bars": 105,                # length + warm-up buffer
    "trama_cross_max_age": 3,             # only crosses within last 3 trading days
    "trama_require_still_on_side": True,  # age 1–2: close must stay on signal side
    "trama_top_n": 20,
    "trama_directions": "BUY,SELL",       # both sides; set "BUY" for long-only
    "trama_max_positions": 10,
    "trama_holding_days": 20,
    "trama_target_1_rr": 1.5,
    "trama_target_2_rr": 2.5,
    "trama_t2_exit_pct": 75.0,
    "trama_book_path": os.getenv(
        "TRADINGAGENTS_TRAMA_BOOK_PATH",
        os.path.join(_TRADINGAGENTS_HOME, "trama", "positions.json"),
    ),
    "trama_pending_path": os.path.join(_TRADINGAGENTS_HOME, "trama", "pending_replacements.json"),
    "trama_daily_dir": os.path.join(_TRADINGAGENTS_HOME, "trama", "daily"),
    "trama_run_times": ["09:30", "11:45", "14:30"],
    # Gap Fill — trade partial fills back toward prior close
    "gap_fill_history_period": "1y",
    "gap_fill_min_pct": 5.0,
    "gap_fill_max_age": 30,
    "gap_fill_exclude_today": True,
    "gap_fill_require_fill_band": False,
    "gap_fill_rsi_period": 14,
    "gap_fill_rsi_oversold": 30.0,
    "gap_fill_rsi_overbought": 70.0,
    "gap_fill_min_open_pct": 10.0,
    "gap_fill_max_extension_pct": 25.0,
    "gap_fill_min_progress": 10,
    "gap_fill_max_progress": 85,
    "gap_fill_top_n": 50,
    "gap_fill_directions": "UP,DOWN",
    "gap_fill_max_positions": 10,
    "gap_fill_holding_days": 15,
    "gap_fill_target_1_rr": 1.5,
    "gap_fill_target_2_rr": 2.5,
    "gap_fill_t2_exit_pct": 75.0,
    "gap_fill_stop_buffer_pct": 0.5,
    "gap_fill_min_bars": 30,
    "gap_fill_book_path": os.getenv(
        "TRADINGAGENTS_GAP_FILL_BOOK_PATH",
        os.path.join(_TRADINGAGENTS_HOME, "gap_fill", "positions.json"),
    ),
    "gap_fill_pending_path": os.path.join(_TRADINGAGENTS_HOME, "gap_fill", "pending_replacements.json"),
    "gap_fill_daily_dir": os.path.join(_TRADINGAGENTS_HOME, "gap_fill", "daily"),
    "gap_fill_run_times": ["09:30", "11:45", "14:30"],
    "gap_fill_screener_snapshot_path": os.path.join(_TRADINGAGENTS_HOME, "gap_fill", "screener.json"),
    # Chart Patterns — classic technical pattern screener (pure, no paper book)
    "chart_pattern_history_period": "2y",
    "chart_pattern_min_bars": 60,
    "chart_pattern_swing_order": 5,
    "chart_pattern_top_n": 25,
    "chart_pattern_enabled": "all",
    "chart_pattern_min_confidence": 55,
    "chart_pattern_max_age_days": 14,
    "chart_pattern_max_breakout_pct": 3.0,
    "chart_pattern_max_invalidation_pct": 5.0,
    "chart_pattern_require_actionable": True,
    "chart_pattern_max_distance_to_trigger_pct": 5.0,
    "chart_pattern_min_position_pct": 0.40,
    "chart_pattern_max_position_pct": 0.60,
    "chart_pattern_exclude_today": True,
    "chart_pattern_screener_snapshot_path": os.path.join(
        _TRADINGAGENTS_HOME, "chart_patterns", "screener.json"
    ),
    # Nadaraya-Watson Envelope [LuxAlgo] — contrarian band crosses
    "nwe_history_period": "2y",
    "nwe_bandwidth": 8.0,
    "nwe_mult": 3.0,
    "nwe_lookback": 500,
    "nwe_min_bars": 60,
    "nwe_cross_max_age": 3,
    "nwe_require_still_on_side": True,
    "nwe_top_n": 20,
    "nwe_directions": "BUY",
    "nwe_max_positions": 10,
    "nwe_holding_days": 20,
    "nwe_target_1_rr": 1.5,
    "nwe_target_2_rr": 2.5,
    "nwe_t2_exit_pct": 75.0,
    "nwe_book_path": os.getenv(
        "TRADINGAGENTS_NWE_BOOK_PATH",
        os.path.join(_TRADINGAGENTS_HOME, "nw_envelope", "positions.json"),
    ),
    "nwe_pending_path": os.path.join(_TRADINGAGENTS_HOME, "nw_envelope", "pending_replacements.json"),
    "nwe_daily_dir": os.path.join(_TRADINGAGENTS_HOME, "nw_envelope", "daily"),
    "nwe_run_times": ["09:30", "11:45", "14:30"],
    # Pattern Forecast v1.1 — accuracy-tuned 5d UP forecast (Pearson + consensus)
    "pattern_forecast_history_period": "2y",
    "pattern_forecast_window": 20,
    "pattern_forecast_horizon": 5,
    "pattern_forecast_use_v17": False,
    "pattern_forecast_min_correlation": 0.56,
    "pattern_forecast_min_bars": 126,
    "pattern_forecast_top_n": 10,
    "pattern_forecast_directions": "UP",
    "pattern_forecast_bullish_only": True,
    "pattern_forecast_correlation_method": "pearson",
    "pattern_forecast_use_consensus": True,
    "pattern_forecast_consensus_top_n": 5,
    "pattern_forecast_consensus_median_n": 3,
    "pattern_forecast_consensus_min_agree": 2,
    "pattern_forecast_use_consensus_dispersion": False,
    "pattern_forecast_consensus_dispersion_max_pct": 12.0,
    "pattern_forecast_recency_weight": 0.20,
    "pattern_forecast_min_hist_fwd_pct": 1.5,
    "pattern_forecast_min_projected_move_pct": 0.5,
    "pattern_forecast_max_projected_move_pct": 50.0,
    "pattern_forecast_min_max_touch_pct": 0.5,
    "pattern_forecast_min_risk_reward": 0.5,
    "pattern_forecast_require_positive_20d_return": False,
    "pattern_forecast_require_nifty_above_ma": False,
    "pattern_forecast_nifty_ma_period": 20,
    "pattern_forecast_require_stock_above_ma": False,
    "pattern_forecast_stock_ma_period": 20,
    "pattern_forecast_min_stock_return_20d": 0.0,
    "pattern_forecast_require_weekly_above_ma": False,
    "pattern_forecast_weekly_ma_period": 10,
    "pattern_forecast_atr_period": 14,
    "pattern_forecast_atr_stop_mult": 1.5,
    "pattern_forecast_atr_stop_floor_mult": 1.2,
    "pattern_forecast_target_atr_mult": 1.5,
    "pattern_forecast_use_atr_target_cap": False,
    "pattern_forecast_atr_regime_tolerance_pct": 40.0,
    "pattern_forecast_require_analogue_quality": False,
    "pattern_forecast_min_fwd_volume_ratio": 0.65,
    "pattern_forecast_max_stop_pct": 5.0,
    "pattern_forecast_min_stop_pct": 2.0,
    "pattern_forecast_stop_on_close_only": False,
    "pattern_forecast_breakeven_trigger_pct": 0.0,
    "pattern_forecast_max_positions": 10,
    "pattern_forecast_holding_days": 5,
    "pattern_forecast_book_path": os.path.join(
        os.path.expanduser("~"), ".tradingagents", "pattern_forecast", "positions.json"
    ),
    "pattern_forecast_pending_path": os.path.join(
        os.path.expanduser("~"), ".tradingagents", "pattern_forecast", "pending_replacements.json"
    ),
    "pattern_forecast_daily_dir": os.path.join(
        os.path.expanduser("~"), ".tradingagents", "pattern_forecast", "daily"
    ),
    "pattern_forecast_run_times": ["09:30", "11:45", "14:30"],
    "benchmark_map": {
        ".NS":  "^NSEI",    # NSE India (Nifty 50)
        ".BO":  "^BSESN",   # BSE India (Sensex)
        ".T":   "^N225",    # Tokyo (Nikkei 225)
        ".HK":  "^HSI",     # Hong Kong (Hang Seng)
        ".L":   "^FTSE",    # London (FTSE 100)
        ".TO":  "^GSPTSE",  # Toronto (TSX Composite)
        ".AX":  "^AXJO",    # Australia (ASX 200)
        "":     "SPY",      # default for US-listed tickers (no suffix)
    },
})

"""Stock screening: relative-strength + technical-pattern engine for the
Indian (NSE) market, feeding the TradingAgents analysis pipeline.

Public entry points:
- ``load_universe``            (universe.py)   -- NSE ticker list
- ``rank_by_relative_strength``(relative_strength.py)
- ``score_patterns``           (patterns.py)   -- per-ticker technical signals
- ``run_screen``               (batch_runner.py) -- full funnel + paper trades
- ``screen_swing``             (swing_screener.py) -- Supertrend swing screener
- ``screen_trama``             (trama_screener.py) -- LuxAlgo TRAMA close crossover
- ``screen_nw_envelope``       (nw_envelope_screener.py) -- LuxAlgo NWE contrarian crosses
- ``screen_pattern_forecast``  (pattern_forecast_screener.py) -- 2y analogue projection
"""

"""Unified end-of-day price sync + screeners + dailies pipeline."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.paper.json_store import dump_json
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.gap_fill import run_gap_fill_daily
from tradingagents.momentum import run_momentum_daily
from tradingagents.nss import run_nss_daily
from tradingagents.dataflows.ohlcv_store import (
    expected_completed_session,
    get_manifest_eod_status,
    manifest_eod_ran_today,
    set_manifest_eod_run,
    sync_price_cache,
)
from tradingagents.dataflows.sync_symbols import collect_sync_symbols, resolve_benchmark
from tradingagents.nw_envelope import run_nw_envelope_daily
from tradingagents.pattern_forecast import run_pattern_forecast_daily
from tradingagents.screening.candle_screener import screen_candlesticks
from tradingagents.screening.chart_pattern_screener import screen_chart_patterns
from tradingagents.screening.gap_fill_screener import screen_gap_fill
from tradingagents.screening.momentum_screener import screen_momentum
from tradingagents.screening.nss_screener import screen_nss
from tradingagents.screening.nw_envelope_screener import screen_nw_envelope
from tradingagents.screening.pattern_forecast_screener import screen_pattern_forecast
from tradingagents.screening.prices import read_history
from tradingagents.screening.supertrend_rsi_screener import screen_supertrend_rsi
from tradingagents.screening.swing_screener import screen_swing
from tradingagents.screening.trama_screener import screen_trama
from tradingagents.screening.universe import load_universe
from tradingagents.supertrend_rsi import run_supertrend_rsi_daily
from tradingagents.swing import run_swing_daily
from tradingagents.tech_desk import run_tech_desk_daily
from tradingagents.rs_desk import run_rs_desk_daily
from tradingagents.trama import run_trama_daily

SHARED_PERIOD = "2y"


def _stamp_blockers(sync_step: dict, config: dict) -> list[str]:
    """Reasons to withhold the EOD manifest stamp.

    Suspended tickers and Yahoo rate limits cost a few symbols on most
    evenings. Withholding the stamp for those leaves the dashboard reporting
    that EOD never ran, so only a missing benchmark — which would silently
    skew relative strength and alpha — or a broad outage blocks it.
    """
    failed = int(sync_step.get("failed") or 0)
    if failed == 0:
        return []

    blockers: list[str] = []
    failed_symbols = {str(s) for s in (sync_step.get("failed_symbols") or [])}
    benchmark = resolve_benchmark(config)
    if benchmark and benchmark in failed_symbols:
        blockers.append(f"benchmark {benchmark} did not sync")

    tolerance = int(config.get("eod_sync_failure_tolerance", 5))
    if failed > tolerance:
        blockers.append(f"{failed} symbols failed to sync (tolerance {tolerance})")
    return blockers


def _summary(name: str, report: dict) -> None:
    if report.get("skipped"):
        print(f"  {name:<16} skipped ({report.get('reason')})")
        return
    print(
        f"  {name:<16} picks={report.get('screener_picks', 0):<3} "
        f"opened={len(report.get('opened', []))} "
        f"exits={len(report.get('exits', []))} "
        f"open_now={report.get('open_positions', 0)} "
        f"pending={len(report.get('proposals', []))}"
    )


def _stale_watchlist_tickers(config: dict) -> list[str]:
    from tradingagents.analysis.watchlist import load_watchlist
    from tradingagents.tech_desk.report_loader import load_tech_reports

    symbols = load_watchlist(config.get("tech_watchlist_path"))
    if not symbols:
        return []

    max_age = config.get("tech_desk_max_report_age_days", 14)
    reports_dir = config.get("tech_analyze_reports_dir")
    fresh, _stale = load_tech_reports(
        reports_dir,
        tickers=symbols,
        max_report_age_days=max_age,
    )
    fresh_set = {s.ticker.upper() for s in fresh}
    return sorted(sym for sym in symbols if sym.upper() not in fresh_set)


def _run_tech_analyze_stale(config: dict) -> dict:
    from tradingagents.analysis.tech_analyze import run_tech_analyze, save_tech_report
    from cli.utils import detect_asset_type, ensure_api_key

    tickers = _stale_watchlist_tickers(config)
    if not tickers:
        print("Tech analyze: no stale or missing watchlist tickers")
        return {"skipped": True, "reason": "nothing_stale", "analyzed": 0}

    max_batch = int(config.get("eod_tech_analyze_max", 5))
    deferred = max(0, len(tickers) - max_batch)
    tickers = tickers[:max_batch]
    if deferred:
        print(
            f"Tech analyze: capping batch to {max_batch} "
            f"({deferred} deferred to a later EOD)"
        )

    try:
        ensure_api_key(config.get("llm_provider", "openai"))
    except Exception as e:  # noqa: BLE001
        print(f"Tech analyze skipped (API key): {e}")
        return {"skipped": True, "reason": "no_api_key", "analyzed": 0}

    trade_date = datetime.now().strftime("%Y-%m-%d")
    reports_base = Path(config["tech_analyze_reports_dir"])
    analyzed = 0
    errors: list[str] = []

    for sym in tickers:
        try:
            asset_type = detect_asset_type(sym).value
            result = run_tech_analyze(
                sym,
                trade_date,
                config=config,
                asset_type=asset_type,
            )
            save_path = reports_base / sym / trade_date
            save_tech_report(result, save_path)
            analyzed += 1
            print(f"  tech-analyze     {sym}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{sym}: {e}")
            print(f"  tech-analyze     {sym} FAILED ({e})")

    return {
        "analyzed": analyzed,
        "errors": errors,
        "tickers": tickers,
        "deferred": deferred,
        "max_batch": max_batch,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified EOD price + screener pipeline")
    parser.add_argument("--force", action="store_true", help="Re-sync prices even if EOD ran today")
    parser.add_argument("--skip-tech-analyze", action="store_true", help="Skip stale tech-analyze step")
    parser.add_argument("--skip-dailies", action="store_true", help="Skip strategy daily jobs")
    parser.add_argument("--skip-screeners", action="store_true", help="Skip screener runs")
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    cache_dir = config.get("data_cache_dir")
    logs_dir = Path(config.get("results_dir", Path.home() / ".tradingagents" / "logs"))
    logs_dir.mkdir(parents=True, exist_ok=True)
    report_path = logs_dir / f"eod_{datetime.now().strftime('%Y%m%d')}.json"

    report: dict = {
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "steps": {},
    }

    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=cache_dir,
        allow_download=True,
    )
    print(f"Step 1: universe loaded — {len(universe)} tickers")
    report["steps"]["universe"] = {"count": len(universe)}

    symbols = collect_sync_symbols(config)
    print(f"Step 2: sync symbol set — {len(symbols)} tickers")
    report["steps"]["sync_symbols"] = {"count": len(symbols)}

    skip_sync = manifest_eod_ran_today(cache_dir) and not args.force
    if skip_sync:
        print("Step 3: price sync skipped (EOD already ran today; use --force to re-sync)")
        report["steps"]["sync"] = {"skipped": True, "reason": "eod_ran_today"}
    else:
        print(f"Step 3: syncing price cache (incremental) for {len(symbols)} tickers...")
        sync_report = sync_price_cache(
            symbols,
            mode="incremental",
            cache_dir=cache_dir,
            require_through=expected_completed_session(),
        )
        print(
            f"  synced={sync_report.synced} skipped={sync_report.skipped} "
            f"failed={sync_report.failed}"
        )
        report["steps"]["sync"] = {
            "synced": sync_report.synced,
            "skipped": sync_report.skipped,
            "failed": sync_report.failed,
            "failed_symbols": sync_report.failed_symbols[:50],
            "errors": sync_report.errors[:50],
        }

    print(f"Step 4: loading {SHARED_PERIOD} history from store...")
    price_data = read_history(symbols, period=SHARED_PERIOD, cache_dir=cache_dir)
    print(f"  usable history for {len(price_data)} tickers")
    report["steps"]["history"] = {"usable": len(price_data), "period": SHARED_PERIOD}

    screener_counts: dict = {}
    if not args.skip_screeners:
        print("Step 5: running all screeners...")
        screener_counts = {
            "swing": len(screen_swing(config, price_data=price_data)),
            "momentum": len(screen_momentum(config, price_data=price_data)),
            "nss": len(screen_nss(config, price_data=price_data)),
            "supertrend_rsi": len(screen_supertrend_rsi(config, price_data=price_data)),
            "trama": len(screen_trama(config, price_data=price_data)),
            "gap_fill": len(screen_gap_fill(config, price_data=price_data)),
            "chart_patterns": len(screen_chart_patterns(config, price_data=price_data)),
            "candlesticks": len(screen_candlesticks(config, price_data=price_data)),
            "nw_envelope": len(screen_nw_envelope(config, price_data=price_data)),
            "pattern_forecast": len(screen_pattern_forecast(config, price_data=price_data)),
        }
        for name, count in screener_counts.items():
            print(f"  {name:<16} {count} picks")
        report["steps"]["screeners"] = screener_counts
    else:
        print("Step 5: screeners skipped")
        report["steps"]["screeners"] = {"skipped": True}

    daily_reports: dict = {}
    if not args.skip_dailies:
        print("Step 6: running all dailies...")
        daily_reports = {
            "swing": run_swing_daily(config, price_data=price_data),
            "momentum": run_momentum_daily(config, price_data=price_data),
            "nss": run_nss_daily(config, price_data=price_data),
            "supertrend_rsi": run_supertrend_rsi_daily(config, price_data=price_data),
            "trama": run_trama_daily(config, price_data=price_data),
            "nw_envelope": run_nw_envelope_daily(config, price_data=price_data),
            "pattern_forecast": run_pattern_forecast_daily(config, price_data=price_data),
            "gap_fill": run_gap_fill_daily(config, price_data=price_data),
            "rs_desk": run_rs_desk_daily(config),
            "tech_desk": run_tech_desk_daily(config),
        }
        for name, rep in daily_reports.items():
            _summary(name, rep if isinstance(rep, dict) else {})
        report["steps"]["dailies"] = {
            k: {
                "skipped": v.get("skipped") if isinstance(v, dict) else False,
                "open_positions": v.get("open_positions") if isinstance(v, dict) else None,
            }
            for k, v in daily_reports.items()
        }
    else:
        print("Step 6: dailies skipped")
        report["steps"]["dailies"] = {"skipped": True}

    if not args.skip_tech_analyze:
        print("Step 7: tech-analyze stale & missing...")
        report["steps"]["tech_analyze"] = _run_tech_analyze_stale(config)
    else:
        print("Step 7: tech-analyze skipped")
        report["steps"]["tech_analyze"] = {"skipped": True}

    sync_step = report["steps"].get("sync") or {}
    sync_failed = int(sync_step.get("failed") or 0)
    blockers = _stamp_blockers(sync_step, config)
    if blockers:
        reason = "; ".join(blockers)
        print(f"Step 8: SKIPPED manifest stamp ({reason}; fix prices then re-run EOD)")
        report["last_eod_run"] = None
        report["manifest_stamp_skipped"] = True
        report["manifest_stamp_reason"] = reason
    else:
        last_eod = set_manifest_eod_run(cache_dir)
        print(f"Step 8: manifest last_eod_run = {last_eod}")
        if sync_failed:
            print(
                f"  note: {sync_failed} symbol(s) failed to sync but stayed within "
                f"tolerance — {', '.join(sync_step.get('failed_symbols') or [])}"
            )
        report["last_eod_run"] = last_eod
        report["manifest_stamp_skipped"] = False
    report["sync_failures_tolerated"] = 0 if blockers else sync_failed
    report["manifest"] = get_manifest_eod_status(cache_dir)
    report["completed_at"] = datetime.now().isoformat(timespec="seconds")

    dump_json(report_path, report)
    print(f"\nEOD report written to {report_path}")
    print("Done.")


if __name__ == "__main__":
    main()

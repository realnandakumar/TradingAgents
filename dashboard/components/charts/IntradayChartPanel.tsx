"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Time } from "lightweight-charts";

import { TradingChart } from "@/components/charts/TradingChart";
import { formatChartCrosshairTime } from "@/lib/chart-locale";
import type {
  ChartHLine,
  ChartLineSeries,
  ChartPayload,
  ChartTimeframe,
  IntradayRange,
} from "@/lib/chart-types";

const INTERVALS: { id: ChartTimeframe; label: string }[] = [
  { id: "5m", label: "5m" },
  { id: "15m", label: "15m" },
];

const RANGES: { id: IntradayRange; label: string }[] = [
  { id: "1d", label: "1D" },
  { id: "5d", label: "5D" },
];

export function IntradayChartPanel({
  ticker,
  defaultOpen = false,
  deskLevels = [],
}: {
  ticker: string;
  defaultOpen?: boolean;
  deskLevels?: ChartHLine[];
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [interval, setInterval] = useState<"5m" | "15m">("5m");
  const [range, setRange] = useState<IntradayRange>("5d");
  const [data, setData] = useState<ChartPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showEma20, setShowEma20] = useState(true);
  const [showVwap, setShowVwap] = useState(true);
  const [showDeskLevels, setShowDeskLevels] = useState(true);
  const abortRef = useRef<AbortController | null>(null);

  const loadIntraday = useCallback(async (sym: string, iv: "5m" | "15m", rng: IntradayRange) => {
    if (!sym.trim()) {
      setData(null);
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/chart/intraday?ticker=${encodeURIComponent(sym)}&interval=${iv}&range=${rng}`,
        { signal: controller.signal, cache: "no-store" },
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to load intraday chart");
      setData(json as ChartPayload);
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      setData(null);
      setError(e instanceof Error ? e.message : "Failed to load intraday chart");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!open || !ticker) return;
    const handle = window.setTimeout(() => {
      void loadIntraday(ticker, interval, range);
    }, 0);
    return () => {
      window.clearTimeout(handle);
      abortRef.current?.abort();
    };
  }, [open, ticker, interval, range, loadIntraday]);

  const chartData = useMemo(() => {
    if (!data) return null;
    const lines: ChartLineSeries[] = [...data.lines];
    if (showEma20 && data.bars.length >= 20) {
      const multiplier = 2 / 21;
      let ema = data.bars.slice(0, 20).reduce((sum, bar) => sum + bar.close, 0) / 20;
      const points: ChartLineSeries["data"] = [{ time: data.bars[19].time, value: ema }];
      for (let index = 20; index < data.bars.length; index += 1) {
        ema = (data.bars[index].close - ema) * multiplier + ema;
        points.push({ time: data.bars[index].time, value: ema });
      }
      lines.push({ id: "intraday-ema20", label: "EMA 20", color: "#22d3ee", data: points });
    }
    if (showVwap) {
      let cumulativePriceVolume = 0;
      let cumulativeVolume = 0;
      const points: ChartLineSeries["data"] = [];
      for (const bar of data.bars) {
        const typical = (bar.high + bar.low + bar.close) / 3;
        cumulativePriceVolume += typical * bar.volume;
        cumulativeVolume += bar.volume;
        if (cumulativeVolume > 0) {
          points.push({ time: bar.time, value: cumulativePriceVolume / cumulativeVolume });
        }
      }
      lines.push({ id: "intraday-vwap", label: "VWAP", color: "#f59e0b", data: points });
    }
    return {
      ...data,
      lines,
      hlines: showDeskLevels ? deskLevels : [],
    };
  }, [data, deskLevels, showDeskLevels, showEma20, showVwap]);

  return (
    <div className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-4 py-3 text-left border-b border-border/60 hover:bg-surface-2/50"
      >
        <span className="text-xs font-semibold uppercase tracking-wide">Intraday</span>
        <span className="text-[10px] text-muted font-mono">
          {interval} · {range} · Yahoo
        </span>
        <span className="ml-auto text-muted text-xs">{open ? "▾" : "▸"}</span>
      </button>

      {open ? (
        <div className="p-4 space-y-3">
          <div className="flex flex-wrap gap-2 items-center text-xs">
            <span className="text-muted uppercase text-[10px] tracking-wide mr-1">Interval</span>
            {INTERVALS.map((i) => (
              <button
                key={i.id}
                type="button"
                onClick={() => setInterval(i.id as "5m" | "15m")}
                className={`px-2.5 py-1.5 rounded-lg font-mono ${
                  interval === i.id
                    ? "bg-accent/20 text-accent border border-accent/40"
                    : "bg-surface-2 border border-border text-muted hover:text-foreground"
                }`}
              >
                {i.label}
              </button>
            ))}
            <span className="text-muted uppercase text-[10px] tracking-wide mx-1">Range</span>
            {RANGES.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => setRange(r.id)}
                className={`px-2.5 py-1.5 rounded-lg font-mono ${
                  range === r.id
                    ? "bg-accent/20 text-accent border border-accent/40"
                    : "bg-surface-2 border border-border text-muted hover:text-foreground"
                }`}
              >
                {r.label}
              </button>
            ))}
            <span className="text-muted uppercase text-[10px] tracking-wide mx-1">Tools</span>
            {[
              ["EMA 20", showEma20, () => setShowEma20((value) => !value)],
              ["VWAP", showVwap, () => setShowVwap((value) => !value)],
              ["Desk levels", showDeskLevels, () => setShowDeskLevels((value) => !value)],
            ].map(([label, active, onClick]) => (
              <button
                key={String(label)}
                type="button"
                onClick={onClick as () => void}
                className={`px-2 py-1 rounded border ${
                  active ? "border-accent/50 text-accent bg-accent/10" : "border-border text-muted"
                }`}
              >
                {String(label)}
              </button>
            ))}
          </div>

          {loading ? (
            <div className="py-12 text-center text-muted text-sm">Loading intraday…</div>
          ) : error ? (
            <div className="py-8 text-center text-bear text-sm">{error}</div>
          ) : chartData ? (
            <>
              <TradingChart data={chartData} height={420} />
              <div className="text-[10px] text-muted font-mono">
                {chartData.meta.barCount} bars · last{" "}
                {chartData.meta.last
                  ? typeof chartData.bars[chartData.bars.length - 1]?.time === "number"
                    ? formatChartCrosshairTime(chartData.bars[chartData.bars.length - 1].time as Time, true)
                    : chartData.meta.last.slice(0, 10)
                  : "—"}{" "}
                IST
              </div>
            </>
          ) : (
            <div className="py-8 text-center text-muted text-sm">No intraday data.</div>
          )}
        </div>
      ) : null}
    </div>
  );
}

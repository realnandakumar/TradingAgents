"use client";

import { useCallback, useEffect, useState } from "react";
import type { Time } from "lightweight-charts";

import { TradingChart } from "@/components/charts/TradingChart";
import { formatChartCrosshairTime } from "@/lib/chart-locale";
import type { ChartPayload, ChartTimeframe, IntradayRange } from "@/lib/chart-types";

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
}: {
  ticker: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [interval, setInterval] = useState<"5m" | "15m">("5m");
  const [range, setRange] = useState<IntradayRange>("5d");
  const [data, setData] = useState<ChartPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadIntraday = useCallback(async (sym: string, iv: "5m" | "15m", rng: IntradayRange) => {
    if (!sym.trim()) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/chart/intraday?ticker=${encodeURIComponent(sym)}&interval=${iv}&range=${rng}`,
      );
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to load intraday chart");
      setData(json as ChartPayload);
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : "Failed to load intraday chart");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen]);

  useEffect(() => {
    if (open && ticker) loadIntraday(ticker, interval, range);
  }, [open, ticker, interval, range, loadIntraday]);

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
          </div>

          {loading ? (
            <div className="py-12 text-center text-muted text-sm">Loading intraday…</div>
          ) : error ? (
            <div className="py-8 text-center text-bear text-sm">{error}</div>
          ) : data ? (
            <>
              <TradingChart data={data} height={360} />
              <div className="text-[10px] text-muted font-mono">
                {data.meta.barCount} bars · last{" "}
                {data.meta.last
                  ? typeof data.bars[data.bars.length - 1]?.time === "number"
                    ? formatChartCrosshairTime(data.bars[data.bars.length - 1].time as Time, true)
                    : data.meta.last.slice(0, 10)
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

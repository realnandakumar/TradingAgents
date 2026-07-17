"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { TradingChart } from "@/components/charts/TradingChart";
import { IntradayChartPanel } from "@/components/charts/IntradayChartPanel";
import { mergeDeskOverlaysClient } from "@/lib/chart-client";
import { CHART_DESK_META } from "@/lib/chart-desks";
import type { ChartLineSeries, ChartPayload, ChartRange } from "@/lib/chart-types";

const RANGES: { id: ChartRange; label: string }[] = [
  { id: "3m", label: "3M" },
  { id: "6m", label: "6M" },
  { id: "1y", label: "1Y" },
  { id: "3y", label: "3Y" },
  { id: "5y", label: "5Y" },
  { id: "max", label: "Max" },
];

function shortSymbol(ticker: string): string {
  return ticker.replace(/\.NS$/i, "");
}

function resolveTickerFromQuery(query: string, tickers: string[]): string | null {
  const raw = query.trim().toUpperCase();
  if (!raw) return null;
  if (tickers.includes(raw)) return raw;
  const withNs = raw.includes(".") ? raw : `${raw}.NS`;
  if (tickers.includes(withNs)) return withNs;
  const bare = raw.replace(/\.NS$/i, "");
  return tickers.find((t) => shortSymbol(t) === bare) ?? null;
}

function computeEma(data: ChartPayload["bars"], period: number): ChartLineSeries["data"] {
  if (data.length < period) return [];
  const multiplier = 2 / (period + 1);
  let ema = data.slice(0, period).reduce((sum, bar) => sum + bar.close, 0) / period;
  const result: ChartLineSeries["data"] = [{ time: data[period - 1].time, value: ema }];
  for (let index = period; index < data.length; index += 1) {
    ema = (data[index].close - ema) * multiplier + ema;
    result.push({ time: data[index].time, value: ema });
  }
  return result;
}

function computeBollinger(
  data: ChartPayload["bars"],
  period = 20,
  deviations = 2,
): { upper: ChartLineSeries["data"]; lower: ChartLineSeries["data"] } {
  const upper: ChartLineSeries["data"] = [];
  const lower: ChartLineSeries["data"] = [];
  for (let index = period - 1; index < data.length; index += 1) {
    const closes = data.slice(index - period + 1, index + 1).map((bar) => bar.close);
    const mean = closes.reduce((sum, value) => sum + value, 0) / period;
    const variance =
      closes.reduce((sum, value) => sum + (value - mean) ** 2, 0) / period;
    const width = Math.sqrt(variance) * deviations;
    upper.push({ time: data[index].time, value: mean + width });
    lower.push({ time: data[index].time, value: mean - width });
  }
  return { upper, lower };
}

export function ChartWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tickerParam = searchParams.get("ticker") ?? "";
  const rangeParam = (searchParams.get("range") ?? "1y") as ChartRange;
  const deskParam = searchParams.get("desk");
  const desksParam = searchParams.get("desks");
  const indicatorParam = searchParams.get("indicators");
  const scaleParam = searchParams.get("scale");
  const patternIdParam = searchParams.get("pattern_id");
  const intradayDefault =
    searchParams.get("intraday") === "1" || searchParams.get("mode") === "intraday";

  const [tickers, setTickers] = useState<string[]>([]);
  const [ticker, setTicker] = useState(tickerParam);
  const effectiveTicker = tickerParam.trim() ? tickerParam : ticker;
  const [range, setRange] = useState<ChartRange>(
    RANGES.some((r) => r.id === rangeParam) ? rangeParam : "1y",
  );
  const [data, setData] = useState<ChartPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [enabledDesks, setEnabledDesks] = useState<Set<string>>(new Set());
  const initialIndicators = indicatorParam?.split(",") ?? ["ema20", "sma50", "sma200"];
  const [showSma50, setShowSma50] = useState(initialIndicators.includes("sma50"));
  const [showSma200, setShowSma200] = useState(initialIndicators.includes("sma200"));
  const [showEma20, setShowEma20] = useState(initialIndicators.includes("ema20"));
  const [showBollinger, setShowBollinger] = useState(initialIndicators.includes("bollinger"));
  const [logScale, setLogScale] = useState(scaleParam === "log");
  const [fullscreen, setFullscreen] = useState(false);
  const [chartHeight, setChartHeight] = useState(520);
  const [desksReady, setDesksReady] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const requestRef = useRef(0);

  useEffect(() => {
    fetch("/api/chart?list=1")
      .then((r) => r.json())
      .then((j) => setTickers(j.tickers ?? []))
      .catch(() => setTickers([]));
  }, []);

  useEffect(() => {
    const resize = () => {
      setChartHeight(window.innerWidth < 640 ? 420 : window.innerWidth < 1024 ? 480 : 520);
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    if (!fullscreen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setFullscreen(false);
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [fullscreen]);

  const prevTickerRef = useRef<string | null>(null);

  const loadChart = useCallback(async (sym: string, rng: ChartRange, patternId?: string | null) => {
    if (!sym.trim()) {
      setData(null);
      return;
    }
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    const requestId = ++requestRef.current;
    const tickerChanged = prevTickerRef.current !== sym;
    prevTickerRef.current = sym;
    if (tickerChanged) {
      setDesksReady(false);
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        ticker: sym,
        range: rng,
      });
      if (patternId) params.set("pattern_id", patternId);
      let res = await fetch(`/api/chart?${params.toString()}`, {
        cache: "no-store",
        signal: controller.signal,
      });
      if (res.status === 404) {
        setError("Preparing local chart data… retrying automatically.");
        await new Promise((resolve) => window.setTimeout(resolve, 1500));
        if (controller.signal.aborted) return;
        res = await fetch(`/api/chart?${params.toString()}`, {
          cache: "no-store",
          signal: controller.signal,
        });
      }
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to load chart");
      if (requestId !== requestRef.current) return;
      const payload = json as ChartPayload;
      setData(payload);
      const available = new Set(payload.deskOverlays.map((d) => d.deskId));
      if (!desksReady) {
        if (deskParam && available.has(deskParam)) {
          setEnabledDesks(new Set([deskParam]));
        } else if (desksParam) {
          const requested = desksParam.split(",").filter((id) => available.has(id));
          setEnabledDesks(new Set(requested));
        } else if (available.size > 0) {
          const stored = window.localStorage.getItem("charts.enabledDesks");
          let remembered: string[] = [];
          try {
            const parsed = stored ? JSON.parse(stored) : [];
            remembered = Array.isArray(parsed)
              ? parsed.filter((id): id is string => typeof id === "string" && available.has(id))
              : [];
          } catch {
            remembered = [];
          }
          const fallback = payload.deskOverlays.find((desk) => desk.deskId !== "chart-patterns");
          setEnabledDesks(new Set(remembered.length > 0 ? remembered : fallback ? [fallback.deskId] : []));
        } else {
          setEnabledDesks(new Set());
        }
        setDesksReady(true);
      } else {
        setEnabledDesks((prev) => {
          const next = new Set<string>();
          for (const id of prev) {
            if (available.has(id)) next.add(id);
          }
          if (next.size === 0 && available.size > 0) return available;
          return next;
        });
      }
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") return;
      if (requestId !== requestRef.current) return;
      setData(null);
      setError(e instanceof Error ? e.message : "Failed to load chart");
    } finally {
      if (requestId === requestRef.current) setLoading(false);
    }
  }, [
    deskParam,
    desksParam,
    desksReady,
    setData,
    setDesksReady,
    setEnabledDesks,
    setError,
    setLoading,
  ]);

  useEffect(() => {
    if (!effectiveTicker) return;
    const handle = window.setTimeout(() => {
      void loadChart(effectiveTicker, range, patternIdParam);
    }, 0);
    return () => {
      window.clearTimeout(handle);
      abortRef.current?.abort();
    };
  }, [effectiveTicker, range, patternIdParam, loadChart]);

  useEffect(() => {
    if (!desksReady) return;
    window.localStorage.setItem(
      "charts.enabledDesks",
      JSON.stringify(Array.from(enabledDesks)),
    );
  }, [desksReady, enabledDesks]);

  useEffect(() => {
    if (!desksReady || !effectiveTicker) return;
    const url = new URL(window.location.href);
    url.searchParams.delete("desk");
    const desks = Array.from(enabledDesks).sort();
    if (desks.length > 0) url.searchParams.set("desks", desks.join(","));
    else url.searchParams.set("desks", "none");
    const indicators = [
      showEma20 ? "ema20" : null,
      showSma50 ? "sma50" : null,
      showSma200 ? "sma200" : null,
      showBollinger ? "bollinger" : null,
    ].filter(Boolean);
    url.searchParams.set("indicators", indicators.join(","));
    if (logScale) url.searchParams.set("scale", "log");
    else url.searchParams.delete("scale");
    window.history.replaceState(window.history.state, "", url);
  }, [
    desksReady,
    effectiveTicker,
    enabledDesks,
    logScale,
    showBollinger,
    showEma20,
    showSma50,
    showSma200,
  ]);

  const filteredTickers = useMemo(() => {
    const q = query.trim().toUpperCase();
    if (!q) return tickers.slice(0, 40);
    return tickers.filter((t) => t.includes(q) || shortSymbol(t).includes(q)).slice(0, 40);
  }, [tickers, query]);

  const chartData = useMemo(() => {
    if (!data) return null;
    const merged = mergeDeskOverlaysClient(data.deskOverlays, enabledDesks);
    const lines = [
      ...data.lines.filter((l) => {
        if (l.id === "sma50") return showSma50;
        if (l.id === "sma200") return showSma200;
        return true;
      }),
      ...(showEma20
        ? [{
            id: "ema20",
            label: "EMA 20",
            color: "#22d3ee",
            data: computeEma(data.bars, 20),
          } satisfies ChartLineSeries]
        : []),
      ...(showBollinger
        ? (() => {
            const bands = computeBollinger(data.bars);
            return [
              { id: "bb-upper", label: "BB upper", color: "#64748b", data: bands.upper },
              { id: "bb-lower", label: "BB lower", color: "#64748b", data: bands.lower },
            ] satisfies ChartLineSeries[];
          })()
        : []),
      ...merged.segments,
    ];
    return { ...data, lines, ...merged };
  }, [data, enabledDesks, showSma50, showSma200, showEma20, showBollinger]);

  const pushUrl = (
    sym: string,
    rng: ChartRange,
    desk?: string | null,
    patternId?: string | null,
    intraday?: boolean,
  ) => {
    const params = new URLSearchParams();
    params.set("ticker", sym);
    params.set("range", rng);
    if (desk) params.set("desk", desk);
    if (patternId) params.set("pattern_id", patternId);
    if (intraday) params.set("intraday", "1");
    router.replace(`/charts?${params.toString()}`);
  };

  const onSelectTicker = (sym: string) => {
    setTicker(sym);
    setQuery(shortSymbol(sym));
    pushUrl(sym, range, deskParam, patternIdParam, intradayDefault);
  };

  const commitSearch = () => {
    const resolved = resolveTickerFromQuery(query, tickers);
    if (resolved) onSelectTicker(resolved);
  };

  const onSelectRange = (rng: ChartRange) => {
    setRange(rng);
    if (effectiveTicker) pushUrl(effectiveTicker, rng, deskParam, patternIdParam, intradayDefault);
  };

  const toggleDesk = (deskId: string) => {
    setEnabledDesks((prev) => {
      const next = new Set(prev);
      if (next.has(deskId)) next.delete(deskId);
      else next.add(deskId);
      return next;
    });
  };

  const applyOverlayPreset = (preset: "core" | "positions" | "patterns" | "all" | "none") => {
    if (!data) return;
    const ids = data.deskOverlays.map((desk) => desk.deskId);
    if (preset === "all") return setEnabledDesks(new Set(ids));
    if (preset === "none") return setEnabledDesks(new Set());
    if (preset === "patterns") {
      return setEnabledDesks(new Set(ids.filter((id) => id === "chart-patterns")));
    }
    if (preset === "positions") {
      return setEnabledDesks(new Set(ids.filter((id) => id !== "chart-patterns")));
    }
    const linked = deskParam && ids.includes(deskParam) ? deskParam : null;
    const firstPosition = data.deskOverlays.find((desk) => desk.deskId !== "chart-patterns");
    setEnabledDesks(new Set(linked ? [linked] : firstPosition ? [firstPosition.deskId] : []));
  };

  const exportCsv = () => {
    if (!data) return;
    const rows = [
      "time,open,high,low,close,volume",
      ...data.bars.map((bar) =>
        [bar.time, bar.open, bar.high, bar.low, bar.close, bar.volume].join(","),
      ),
    ];
    const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${shortSymbol(data.ticker)}-${range}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const last = data?.meta.lastClose;
  const symLabel = effectiveTicker ? shortSymbol(effectiveTicker) : "—";

  return (
    <div className="space-y-4">
      <div className="px-4 sm:px-6 flex flex-wrap items-end gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Charts</h1>
          <p className="text-muted text-sm mt-1">
            Daily candles from local cache · desk overlays · separate intraday panel
          </p>
        </div>
        <div className="ml-auto text-right">
          <div className="text-2xl font-semibold tabular-nums">{symLabel}</div>
          <div className="text-sm text-muted tabular-nums">
            {last != null ? `₹${last.toLocaleString("en-IN", { maximumFractionDigits: 2 })}` : "—"}
            {data?.meta.last ? ` · ${data.meta.last}` : ""}
          </div>
          <div className="text-[10px] text-muted font-mono">
            {data?.source ?? "—"} · {data?.meta.barCount ?? 0} bars
          </div>
        </div>
      </div>

      <div className="mx-4 sm:mx-6 card p-4 space-y-3">
        <div className="flex flex-wrap gap-3 items-center">
          <div className="relative min-w-[200px] flex-1 max-w-xs flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitSearch();
              }}
              onBlur={() => {
                const resolved = resolveTickerFromQuery(query, tickers);
                if (resolved && resolved !== effectiveTicker) commitSearch();
              }}
              placeholder="Search ticker (ACC, INFY…)"
              className="w-full bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm"
              list="chart-ticker-list"
            />
            <button
              type="button"
              onClick={commitSearch}
              className="shrink-0 px-3 py-2 rounded-lg bg-surface-2 border border-border text-xs hover:border-accent/40"
            >
              Go
            </button>
            <datalist id="chart-ticker-list">
              {filteredTickers.map((t) => (
                <option key={t} value={shortSymbol(t)} />
              ))}
            </datalist>
          </div>
          <select
            className="bg-surface-2 border border-border rounded-lg px-3 py-2 text-sm max-w-[220px]"
            value={effectiveTicker}
            onChange={(e) => onSelectTicker(e.target.value)}
          >
            <option value="">Select ticker…</option>
            {tickers.map((t) => (
              <option key={t} value={t}>
                {shortSymbol(t)}
              </option>
            ))}
          </select>
          <div className="flex gap-1">
            {RANGES.map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => onSelectRange(r.id)}
                className={`px-2.5 py-1.5 rounded-lg text-xs font-mono ${
                  range === r.id
                    ? "bg-accent/20 text-accent border border-accent/40"
                    : "bg-surface-2 border border-border text-muted hover:text-foreground"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 items-center text-xs">
          <span className="text-muted uppercase text-[10px] tracking-wide mr-1">Indicators</span>
          <button
            type="button"
            onClick={() => setShowEma20((value) => !value)}
            className={`px-2 py-1 rounded border ${
              showEma20 ? "border-cyan-400/50 text-cyan-300 bg-cyan-500/10" : "border-border text-muted"
            }`}
          >
            EMA 20
          </button>
          <button
            type="button"
            onClick={() => setShowSma50((v) => !v)}
            className={`px-2 py-1 rounded border ${
              showSma50 ? "border-amber-500/50 text-amber-400 bg-amber-500/10" : "border-border text-muted"
            }`}
          >
            SMA 50
          </button>
          <button
            type="button"
            onClick={() => setShowSma200((v) => !v)}
            className={`px-2 py-1 rounded border ${
              showSma200 ? "border-violet-400/50 text-violet-300 bg-violet-500/10" : "border-border text-muted"
            }`}
          >
            SMA 200
          </button>
          <button
            type="button"
            onClick={() => setShowBollinger((value) => !value)}
            className={`px-2 py-1 rounded border ${
              showBollinger ? "border-slate-400/50 text-slate-300 bg-slate-500/10" : "border-border text-muted"
            }`}
          >
            Bollinger
          </button>
          <span className="h-4 w-px bg-border mx-1" />
          <button
            type="button"
            onClick={() => setLogScale((value) => !value)}
            className={`px-2 py-1 rounded border ${
              logScale ? "border-accent/50 text-accent bg-accent/10" : "border-border text-muted"
            }`}
          >
            Log scale
          </button>
          <button
            type="button"
            onClick={() => setFullscreen((value) => !value)}
            className="px-2 py-1 rounded border border-border text-muted hover:text-foreground"
          >
            {fullscreen ? "Exit fullscreen" : "Fullscreen"}
          </button>
          <button
            type="button"
            onClick={exportCsv}
            disabled={!data}
            className="px-2 py-1 rounded border border-border text-muted hover:text-foreground disabled:opacity-40"
          >
            Export CSV
          </button>
        </div>

        {data && data.deskOverlays.length > 0 ? (
          <div className="space-y-2">
            <div className="flex flex-wrap gap-1.5 items-center text-xs">
              <span className="text-muted uppercase text-[10px] tracking-wide mr-1">Presets</span>
              {(["core", "positions", "patterns", "all", "none"] as const).map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => applyOverlayPreset(preset)}
                  className="px-2 py-1 rounded border border-border bg-surface-2 text-muted hover:text-foreground hover:border-accent/40 capitalize"
                >
                  {preset}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2 items-center text-xs">
              <span className="text-muted uppercase text-[10px] tracking-wide mr-1">Desk overlays</span>
            {data.deskOverlays.map((d) => (
              <button
                key={d.deskId}
                type="button"
                onClick={() => toggleDesk(d.deskId)}
                className={`px-2 py-1 rounded border font-mono ${
                  enabledDesks.has(d.deskId)
                    ? "border-current bg-current/10"
                    : "border-border text-muted opacity-50"
                }`}
                style={{ color: enabledDesks.has(d.deskId) ? d.color : undefined }}
              >
                {d.deskLabel}
              </button>
            ))}
            </div>
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="mx-4 sm:mx-6 card p-8 text-center text-bear text-sm">{error}</div>
      ) : effectiveTicker ? (
        <div
          className={
            fullscreen
              ? "fixed inset-0 z-50 overflow-auto bg-background p-3 sm:p-6 space-y-3"
              : "mx-4 sm:mx-6 space-y-3"
          }
        >
          {fullscreen ? (
            <div className="flex items-center justify-between">
              <div className="font-semibold">{symLabel} · Daily</div>
              <button
                type="button"
                onClick={() => setFullscreen(false)}
                className="rounded border border-border bg-surface px-3 py-1.5 text-xs"
              >
                Close fullscreen
              </button>
            </div>
          ) : null}
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">Daily</div>
          {loading && !chartData ? (
            <div className="card p-12 text-center text-muted text-sm">Loading chart…</div>
          ) : chartData ? (
            <>
              <TradingChart
                data={chartData}
                logScale={logScale}
                height={fullscreen ? Math.max(620, chartHeight + 200) : chartHeight}
              />
              <div className="flex flex-wrap gap-3 text-[10px] text-muted font-mono">
                {chartData.lines.map((l) => (
                  <span key={l.id} style={{ color: l.color }}>
                    ● {l.label}
                  </span>
                ))}
                {chartData.hlines.map((h) => (
                  <span key={h.id} style={{ color: h.color }}>
                    — {h.label} {h.price.toFixed(2)}
                  </span>
                ))}
                {chartData.zones.map((z) => (
                  <span key={z.id} style={{ color: z.color ?? "#5b8cff" }}>
                    ▣ {z.label} {z.low.toFixed(2)}–{z.high.toFixed(2)}
                  </span>
                ))}
              </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                {data?.deskOverlays
                  .filter((desk) => enabledDesks.has(desk.deskId))
                  .map((desk) => (
                    <details
                      key={desk.deskId}
                      className="rounded border border-border bg-surface-2/40 px-3 py-2 text-[10px]"
                    >
                      <summary className="cursor-pointer text-muted">
                        <span style={{ color: desk.color }}>{desk.deskLabel}</span>
                        {" · "}
                        {desk.hlines.length} levels · {desk.zones.length} zones ·{" "}
                        {desk.markers.length} markers
                      </summary>
                      <div className="mt-2 space-y-1 text-muted">
                        {desk.hlines.map((line) => (
                          <div key={line.id}>
                            {line.label}: <span className="font-mono">{line.price.toFixed(2)}</span>
                          </div>
                        ))}
                        {desk.zones.map((zone) => (
                          <div key={zone.id}>
                            {zone.label}:{" "}
                            <span className="font-mono">
                              {zone.low.toFixed(2)}–{zone.high.toFixed(2)}
                            </span>
                          </div>
                        ))}
                        <Link
                          href={CHART_DESK_META.find((meta) => meta.id === desk.deskId)?.href ?? "#"}
                          className="inline-block pt-1 hover:text-accent"
                          style={{ color: desk.color }}
                        >
                          Open {desk.deskLabel} →
                        </Link>
                      </div>
                    </details>
                  ))}
              </div>
            </>
          ) : null}
          <IntradayChartPanel
            ticker={effectiveTicker}
            defaultOpen={intradayDefault}
            deskLevels={chartData?.hlines ?? []}
          />
        </div>
      ) : (
        <div className="mx-4 sm:mx-6 card p-12 text-center text-muted text-sm">
          Pick a ticker with cached data or on your watchlist.
        </div>
      )}

      {filteredTickers.length > 0 && !effectiveTicker ? (
        <div className="mx-4 sm:mx-6 card p-4">
          <div className="text-xs text-muted mb-2">Cached tickers</div>
          <div className="flex flex-wrap gap-2">
            {filteredTickers.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => onSelectTicker(t)}
                className="px-2 py-1 rounded bg-surface-2 border border-border text-xs hover:border-accent/40"
              >
                {shortSymbol(t)}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}

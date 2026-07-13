"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { TradingChart } from "@/components/charts/TradingChart";
import { IntradayChartPanel } from "@/components/charts/IntradayChartPanel";
import { mergeDeskOverlaysClient } from "@/lib/chart-client";
import { CHART_DESK_META } from "@/lib/chart-desks";
import type { ChartPayload, ChartRange } from "@/lib/chart-types";

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

export function ChartWorkspace() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tickerParam = searchParams.get("ticker") ?? "";
  const rangeParam = (searchParams.get("range") ?? "1y") as ChartRange;
  const deskParam = searchParams.get("desk");
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
  const [showSma50, setShowSma50] = useState(true);
  const [showSma200, setShowSma200] = useState(true);
  const [desksReady, setDesksReady] = useState(false);

  useEffect(() => {
    fetch("/api/chart?list=1")
      .then((r) => r.json())
      .then((j) => setTickers(j.tickers ?? []))
      .catch(() => setTickers([]));
  }, []);

  const prevTickerRef = useRef<string | null>(null);

  const loadChart = useCallback(async (sym: string, rng: ChartRange, patternId?: string | null) => {
    if (!sym.trim()) {
      setData(null);
      return;
    }
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
      const res = await fetch(`/api/chart?${params.toString()}`);
      const json = await res.json();
      if (!res.ok) throw new Error(json.error ?? "Failed to load chart");
      const payload = json as ChartPayload;
      setData(payload);
      const available = new Set(payload.deskOverlays.map((d) => d.deskId));
      if (!desksReady) {
        if (deskParam && available.has(deskParam)) {
          setEnabledDesks(new Set([deskParam]));
        } else if (available.size > 0) {
          setEnabledDesks(available);
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
      setData(null);
      setError(e instanceof Error ? e.message : "Failed to load chart");
    } finally {
      setLoading(false);
    }
  }, [deskParam, desksReady]);

  useEffect(() => {
    if (!effectiveTicker) return;
    const handle = window.setTimeout(() => {
      void loadChart(effectiveTicker, range, patternIdParam);
    }, 0);
    return () => window.clearTimeout(handle);
  }, [effectiveTicker, range, patternIdParam, loadChart]);

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
      ...merged.segments,
    ];
    return { ...data, lines, patternHighlight: merged.patternHighlight, ...merged };
  }, [data, enabledDesks, showSma50, showSma200]);

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
        </div>

        {data && data.deskOverlays.length > 0 ? (
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
            <button
              type="button"
              onClick={() => setEnabledDesks(new Set(data.deskOverlays.map((d) => d.deskId)))}
              className="px-2 py-1 text-muted hover:text-foreground"
            >
              All
            </button>
            <button
              type="button"
              onClick={() => setEnabledDesks(new Set())}
              className="px-2 py-1 text-muted hover:text-foreground"
            >
              None
            </button>
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="mx-4 sm:mx-6 card p-8 text-center text-bear text-sm">{error}</div>
      ) : effectiveTicker ? (
        <div className="mx-4 sm:mx-6 space-y-3">
          <div className="text-xs font-semibold uppercase tracking-wide text-muted">Daily</div>
          {loading && !chartData ? (
            <div className="card p-12 text-center text-muted text-sm">Loading chart…</div>
          ) : chartData ? (
            <>
              <TradingChart data={chartData} />
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
              {data?.deskOverlays.map((d) => (
                <div key={d.deskId} className="text-[10px] text-muted">
                  <Link
                    href={CHART_DESK_META.find((m) => m.id === d.deskId)?.href ?? "#"}
                    className="hover:text-accent"
                    style={{ color: d.color }}
                  >
                    {d.deskLabel}
                  </Link>
                  {" · "}
                  {d.hlines.length} levels · {d.zones.length} zones · {d.markers.length} markers
                </div>
              ))}
            </>
          ) : null}
          <IntradayChartPanel ticker={effectiveTicker} defaultOpen={intradayDefault} />
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

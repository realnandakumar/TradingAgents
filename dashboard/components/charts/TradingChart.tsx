"use client";

import { useEffect, useRef } from "react";
import {
  BaselineSeries,
  CandlestickSeries,
  ColorType,
  LineStyle,
  createChart,
  createSeriesMarkers,
  HistogramSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type Time,
} from "lightweight-charts";

import type { ChartPayload, ChartPatternHighlight, ChartTime, ChartZone } from "@/lib/chart-types";

const THEME = {
  background: "#14161d",
  text: "#8b90a0",
  grid: "#262a36",
  border: "#262a36",
  up: "#2ecc71",
  down: "#ff5470",
  dimUp: "rgba(46,204,113,0.22)",
  dimDown: "rgba(255,84,112,0.22)",
  dimVolUp: "rgba(46,204,113,0.12)",
  dimVolDown: "rgba(255,84,112,0.12)",
};

interface TradingChartProps {
  data: ChartPayload;
  height?: number;
}

function isIntradayPayload(data: ChartPayload): boolean {
  return data.timeframe !== "1d";
}

function hexToRgba(hex: string, alpha: number): string {
  const raw = hex.replace("#", "");
  if (raw.length !== 6) return `rgba(91, 140, 255, ${alpha})`;
  const r = Number.parseInt(raw.slice(0, 2), 16);
  const g = Number.parseInt(raw.slice(2, 4), 16);
  const b = Number.parseInt(raw.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function barTimeKey(time: ChartTime): string {
  if (typeof time === "number") {
    return new Date(time * 1000).toISOString().slice(0, 10);
  }
  return String(time).slice(0, 10);
}

function isInPatternWindow(
  time: ChartTime,
  highlight: ChartPatternHighlight,
): boolean {
  const key = barTimeKey(time);
  return key >= highlight.windowStart && key <= highlight.windowEnd;
}

function candleColors(
  bullish: boolean,
  inWindow: boolean,
): { color: string; borderColor: string; wickColor: string } {
  if (inWindow) {
    const c = bullish ? THEME.up : THEME.down;
    return { color: c, borderColor: c, wickColor: c };
  }
  const c = bullish ? THEME.dimUp : THEME.dimDown;
  return { color: c, borderColor: c, wickColor: c };
}

function addZoneBands(
  chart: IChartApi,
  bars: ChartPayload["bars"],
  zones: ChartZone[],
): ISeriesApi<"Baseline">[] {
  if (zones.length === 0 || bars.length === 0) return [];

  const zoneData = bars.map((b) => ({ time: b.time as Time }));
  const series: ISeriesApi<"Baseline">[] = [];

  for (const zone of zones) {
    if (zone.high <= zone.low) continue;
    const color = zone.color ?? "#5b8cff";
    const band = chart.addSeries(
      BaselineSeries,
      {
        baseValue: { type: "price", price: zone.low },
        topFillColor1: hexToRgba(color, 0.22),
        topFillColor2: hexToRgba(color, 0.06),
        topLineColor: hexToRgba(color, 0.45),
        bottomFillColor1: "transparent",
        bottomFillColor2: "transparent",
        bottomLineColor: "transparent",
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      },
      0,
    );
    band.setData(zoneData.map((p) => ({ ...p, value: zone.high })));
    series.push(band);
  }

  return series;
}

export function TradingChart({ data, height = 520 }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || data.bars.length === 0) return;

    const intraday = isIntradayPayload(data);
    const highlight = data.patternHighlight ?? null;

    const chart = createChart(el, {
      width: el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: THEME.background },
        textColor: THEME.text,
        fontFamily: "var(--font-geist-mono), monospace",
      },
      grid: {
        vertLines: { color: THEME.grid },
        horzLines: { color: THEME.grid },
      },
      rightPriceScale: { borderColor: THEME.border },
      timeScale: {
        borderColor: THEME.border,
        timeVisible: true,
        secondsVisible: intraday,
      },
      crosshair: { mode: 1 },
    });
    chartRef.current = chart;

    const volumePane = chart.addPane();
    volumePane.setHeight(100);

    const candles = chart.addSeries(
      CandlestickSeries,
      {
        upColor: THEME.up,
        downColor: THEME.down,
        borderUpColor: THEME.up,
        borderDownColor: THEME.down,
        wickUpColor: THEME.up,
        wickDownColor: THEME.down,
      },
      0,
    );

    candles.setData(
      data.bars.map((b) => {
        const bullish = b.close >= b.open;
        const inWindow = !highlight || isInPatternWindow(b.time, highlight);
        const colors = candleColors(bullish, inWindow);
        return {
          time: b.time as Time,
          open: b.open,
          high: b.high,
          low: b.low,
          close: b.close,
          ...colors,
        };
      }),
    );

    const zoneSeries = addZoneBands(chart, data.bars, data.zones);

    const priceLines: ReturnType<ISeriesApi<"Candlestick">["createPriceLine"]>[] = [];
    for (const h of data.hlines) {
      priceLines.push(
        candles.createPriceLine({
          price: h.price,
          color: h.color,
          lineWidth: 1,
          lineStyle: h.style === "dashed" ? LineStyle.Dashed : LineStyle.Solid,
          axisLabelVisible: true,
          title: h.label,
        }),
      );
    }

    const lineSeries: ISeriesApi<"Line">[] = [];
    for (const line of data.lines) {
      if (line.data.length === 0) continue;
      const isPatternSegment = line.deskId === "chart-patterns" || line.lineWidth != null;
      const s = chart.addSeries(
        LineSeries,
        {
          color: line.color,
          lineWidth: line.lineWidth ?? (isPatternSegment ? 2 : 1),
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        },
        0,
      );
      s.setData(line.data.map((p) => ({ time: p.time as Time, value: p.value })));
      lineSeries.push(s);
    }

    let markersApi: ISeriesMarkersPluginApi<Time> | null = null;
    if (data.markers.length > 0) {
      markersApi = createSeriesMarkers(
        candles,
        data.markers.map((m) => ({
          time: m.time as Time,
          position: m.position,
          color: m.color,
          shape: m.position === "belowBar" ? "arrowUp" : "arrowDown",
          text: m.text,
        })),
      );
    }

    const volume = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: "volume" },
        priceLineVisible: false,
        lastValueVisible: false,
      },
      1,
    );
    volume.setData(
      data.bars.map((b) => {
        const bullish = b.close >= b.open;
        const inWindow = !highlight || isInPatternWindow(b.time, highlight);
        const color = inWindow
          ? bullish
            ? "rgba(46,204,113,0.35)"
            : "rgba(255,84,112,0.35)"
          : bullish
            ? THEME.dimVolUp
            : THEME.dimVolDown;
        return {
          time: b.time as Time,
          value: b.volume,
          color,
        };
      }),
    );

    chart.timeScale().fitContent();

    const ro = new ResizeObserver(() => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      for (const pl of priceLines) candles.removePriceLine(pl);
      for (const zs of zoneSeries) chart.removeSeries(zs);
      for (const ls of lineSeries) chart.removeSeries(ls);
      markersApi?.detach();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height]);

  const highlight = data.patternHighlight;

  return (
    <div className="relative w-full rounded-xl border border-border overflow-hidden bg-surface">
      {data.zones.length > 0 ? (
        <div className="absolute top-2 left-2 z-10 flex flex-wrap gap-1.5 text-[10px] pointer-events-none">
          {data.zones.map((z) => (
            <span
              key={z.id}
              className="px-2 py-0.5 rounded border"
              style={{
                color: z.color ?? "#5b8cff",
                borderColor: `${z.color ?? "#5b8cff"}55`,
                backgroundColor: `${z.color ?? "#5b8cff"}18`,
              }}
            >
              {z.label}: {z.low.toFixed(2)}–{z.high.toFixed(2)}
            </span>
          ))}
        </div>
      ) : null}
      {highlight ? (
        <div className="absolute top-2 right-2 z-10 pointer-events-none">
          <span
            className="px-2.5 py-1 rounded border text-[10px] font-medium tracking-wide"
            style={{
              color: highlight.color,
              borderColor: `${highlight.color}66`,
              backgroundColor: `${highlight.color}1a`,
            }}
          >
            {highlight.label}
          </span>
        </div>
      ) : null}
      <div ref={containerRef} className="w-full" style={{ height }} />
    </div>
  );
}

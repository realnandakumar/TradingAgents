"use client";

import { useEffect, useRef, useState } from "react";
import {
  BaselineSeries,
  CandlestickSeries,
  ColorType,
  LineStyle,
  PriceScaleMode,
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
import { chartTimeLocaleOptions } from "@/lib/chart-locale";

const THEME = {
  background: "#14161d",
  text: "#8b90a0",
  grid: "#262a36",
  border: "#262a36",
  up: "#2ecc71",
  down: "#ff5470",
  dimUp: "rgba(46,204,113,0.38)",
  dimDown: "rgba(255,84,112,0.38)",
  dimVolUp: "rgba(46,204,113,0.2)",
  dimVolDown: "rgba(255,84,112,0.2)",
};

interface TradingChartProps {
  data: ChartPayload;
  height?: number;
  logScale?: boolean;
}

interface InspectorValue {
  time: ChartTime;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  changePct: number | null;
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

/** Bright = full color only inside the selected pattern window. */
function isBrightBar(time: ChartTime, highlight: ChartPatternHighlight | null): boolean {
  if (!highlight) return true;
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

  const series: ISeriesApi<"Baseline">[] = [];

  for (const zone of zones) {
    if (zone.high <= zone.low) continue;
    const zoneData = bars
      .filter((b) => {
        const key = barTimeKey(b.time);
        return (!zone.startTime || key >= barTimeKey(zone.startTime)) &&
          (!zone.endTime || key <= barTimeKey(zone.endTime));
      })
      .map((b) => ({ time: b.time as Time }));
    if (zoneData.length === 0) continue;
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

function lineSemantics(label: string): {
  color?: string;
  style: LineStyle;
  width: 1 | 2;
} {
  const normalized = label.toLowerCase();
  if (normalized.includes("stop") || normalized.includes("invalid")) {
    return { color: "#ff5470", style: LineStyle.Dashed, width: 2 };
  }
  if (
    normalized.includes("target") ||
    normalized.includes("t1") ||
    normalized.includes("t2")
  ) {
    return { color: "#2ecc71", style: LineStyle.Dashed, width: 2 };
  }
  if (
    normalized.includes("entry") ||
    normalized.includes("trigger") ||
    normalized.includes("fill")
  ) {
    return { color: "#5b8cff", style: LineStyle.Solid, width: 2 };
  }
  return { style: LineStyle.Dotted, width: 1 };
}

export function TradingChart({ data, height = 520, logScale = false }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const visibleRangeRef = useRef<ReturnType<IChartApi["timeScale"]> extends infer T
    ? T extends { getVisibleLogicalRange(): infer R }
      ? R
      : never
    : never>(null);
  const [inspector, setInspector] = useState<InspectorValue | null>(null);

  const downloadPng = () => {
    const canvas = chartRef.current?.takeScreenshot();
    if (!canvas) return;
    const anchor = document.createElement("a");
    anchor.href = canvas.toDataURL("image/png");
    anchor.download = `${data.ticker.replace(/\.NS$/i, "")}-${data.timeframe}.png`;
    anchor.click();
  };

  useEffect(() => {
    const el = containerRef.current;
    if (!el || data.bars.length === 0) return;

    const intraday = isIntradayPayload(data);
    const highlight = data.patternHighlight ?? null;
    const localeOpts = chartTimeLocaleOptions(intraday);

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
      rightPriceScale: {
        borderColor: THEME.border,
        mode: logScale ? PriceScaleMode.Logarithmic : PriceScaleMode.Normal,
      },
      localization: localeOpts.localization,
      timeScale: {
        borderColor: THEME.border,
        timeVisible: true,
        secondsVisible: intraday,
        tickMarkFormatter: localeOpts.timeScale.tickMarkFormatter,
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
        const inWindow = isBrightBar(b.time, highlight);
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
      const semantics = lineSemantics(h.label);
      priceLines.push(
        candles.createPriceLine({
          price: h.price,
          color: semantics.color ?? h.color,
          lineWidth: semantics.width,
          lineStyle:
            h.style === "solid"
              ? LineStyle.Solid
              : h.style === "dashed"
                ? LineStyle.Dashed
                : semantics.style,
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
        const inWindow = isBrightBar(b.time, highlight);
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

    chart.subscribeCrosshairMove((param) => {
      if (!param.time) {
        setInspector(null);
        return;
      }
      const bar = data.bars.find((candidate) => String(candidate.time) === String(param.time));
      if (!bar) {
        setInspector(null);
        return;
      }
      const previousIndex = data.bars.indexOf(bar) - 1;
      const previousClose = previousIndex >= 0 ? data.bars[previousIndex]?.close : null;
      setInspector({
        ...bar,
        changePct:
          previousClose && previousClose !== 0
            ? ((bar.close - previousClose) / previousClose) * 100
            : null,
      });
    });

    if (visibleRangeRef.current) {
      chart.timeScale().setVisibleLogicalRange(visibleRangeRef.current);
    } else {
      chart.timeScale().fitContent();
    }
    chart.timeScale().applyOptions({ rightOffset: 8 });

    const ro = new ResizeObserver(() => {
      if (!containerRef.current) return;
      chart.applyOptions({ width: containerRef.current.clientWidth });
    });
    ro.observe(el);

    return () => {
      visibleRangeRef.current = chart.timeScale().getVisibleLogicalRange();
      ro.disconnect();
      for (const pl of priceLines) candles.removePriceLine(pl);
      for (const zs of zoneSeries) chart.removeSeries(zs);
      for (const ls of lineSeries) chart.removeSeries(ls);
      markersApi?.detach();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height, logScale]);

  const highlight = data.patternHighlight;
  const nearbyLevels = inspector
    ? data.hlines
        .map((line) => ({ ...line, distance: Math.abs(line.price - inspector.close) }))
        .sort((a, b) => a.distance - b.distance)
        .slice(0, 3)
    : [];

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
        <div className="absolute top-10 right-2 z-10 pointer-events-none">
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
      <button
        type="button"
        onClick={downloadPng}
        className="absolute right-2 top-2 z-20 rounded border border-border/80 bg-surface/85 px-2 py-1 text-[10px] text-muted shadow backdrop-blur hover:text-foreground"
        title="Download chart as PNG"
      >
        PNG
      </button>
      {inspector ? (
        <div className="absolute bottom-2 left-2 right-2 z-10 pointer-events-none">
          <div className="inline-flex max-w-full flex-wrap gap-x-3 gap-y-0.5 rounded border border-border/80 bg-surface/90 px-2 py-1 text-[10px] font-mono shadow-lg backdrop-blur">
            <span className="text-muted">{barTimeKey(inspector.time)}</span>
            <span>O {inspector.open.toFixed(2)}</span>
            <span>H {inspector.high.toFixed(2)}</span>
            <span>L {inspector.low.toFixed(2)}</span>
            <span>C {inspector.close.toFixed(2)}</span>
            <span className={inspector.changePct != null && inspector.changePct >= 0 ? "text-bull" : "text-bear"}>
              {inspector.changePct == null ? "—" : `${inspector.changePct >= 0 ? "+" : ""}${inspector.changePct.toFixed(2)}%`}
            </span>
            <span className="text-muted">V {inspector.volume.toLocaleString("en-IN")}</span>
            {nearbyLevels.map((level) => (
              <span key={level.id} style={{ color: lineSemantics(level.label).color ?? level.color }}>
                {level.label} {level.price.toFixed(2)}
              </span>
            ))}
          </div>
        </div>
      ) : null}
      <div ref={containerRef} className="w-full" style={{ height }} />
    </div>
  );
}

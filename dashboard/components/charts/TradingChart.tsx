"use client";

import { useEffect, useRef } from "react";
import {
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

import type { ChartPayload } from "@/lib/chart-types";

const THEME = {
  background: "#14161d",
  text: "#8b90a0",
  grid: "#262a36",
  border: "#262a36",
  up: "#2ecc71",
  down: "#ff5470",
};

interface TradingChartProps {
  data: ChartPayload;
  height?: number;
}

function isIntradayPayload(data: ChartPayload): boolean {
  return data.timeframe !== "1d";
}

export function TradingChart({ data, height = 520 }: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || data.bars.length === 0) return;

    const intraday = isIntradayPayload(data);

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

    const candles = chart.addSeries(CandlestickSeries, {
      upColor: THEME.up,
      downColor: THEME.down,
      borderUpColor: THEME.up,
      borderDownColor: THEME.down,
      wickUpColor: THEME.up,
      wickDownColor: THEME.down,
    }, 0);

    candles.setData(
      data.bars.map((b) => ({
        time: b.time as Time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      })),
    );

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
      const s = chart.addSeries(
        LineSeries,
        {
          color: line.color,
          lineWidth: 1,
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
      data.bars.map((b) => ({
        time: b.time as Time,
        value: b.volume,
        color: b.close >= b.open ? "rgba(46,204,113,0.35)" : "rgba(255,84,112,0.35)",
      })),
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
      markersApi?.detach();
      chart.remove();
      chartRef.current = null;
    };
  }, [data, height]);

  return (
    <div className="relative w-full rounded-xl border border-border overflow-hidden bg-surface">
      {data.zones.length > 0 ? (
        <div className="absolute top-2 left-2 z-10 flex flex-wrap gap-1.5 text-[10px]">
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
      <div ref={containerRef} className="w-full" style={{ height }} />
    </div>
  );
}

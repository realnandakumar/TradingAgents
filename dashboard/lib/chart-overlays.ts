import { readGapFillBook } from "@/lib/gap-fill-server";
import { readMomentumBook } from "@/lib/momentum-server";
import { readNssBook } from "@/lib/nss-server";
import { readNwEnvelopeBook } from "@/lib/nw-envelope-server";
import { readPatternForecastBook } from "@/lib/pattern-forecast-server";
import { readStrsiBook } from "@/lib/supertrend-rsi-server";
import { readSwingBook } from "@/lib/swing-server";
import { readTechDeskBook, readTechDeskPending } from "@/lib/tech-desk-server";
import { readTramaBook } from "@/lib/trama-server";
import {
  readChartPatternScreenerSnapshot,
  type ChartPatternScreenerPick,
} from "@/lib/chart-patterns-server";
import { pickTradeLevels } from "@/lib/chart-pattern-levels";

import { CHART_DESK_META, type ChartDeskMeta } from "./chart-desks";
import type { ChartHLine, ChartLineSeries, ChartMarker, ChartPatternHighlight, ChartZone } from "./chart-types";

export { CHART_DESK_META, type ChartDeskMeta };

export interface DeskChartOverlay {
  deskId: string;
  deskLabel: string;
  color: string;
  hlines: ChartHLine[];
  zones: ChartZone[];
  markers: ChartMarker[];
  segments: ChartLineSeries[];
  patternHighlight?: ChartPatternHighlight | null;
}

export function normalizeChartTicker(raw: string): string {
  const t = raw.trim().toUpperCase();
  if (!t) return "";
  return t.includes(".") ? t : `${t}.NS`;
}

function num(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function matchesTicker(positionTicker: string, norm: string): boolean {
  return normalizeChartTicker(positionTicker) === norm;
}

function deskMeta(deskId: string): ChartDeskMeta {
  return CHART_DESK_META.find((d) => d.id === deskId) ?? {
    id: deskId,
    label: deskId,
    color: "#8b90a0",
    href: `/${deskId}`,
  };
}

function emptyOverlay(deskId: string): DeskChartOverlay {
  const meta = deskMeta(deskId);
  return {
    deskId,
    deskLabel: meta.label,
    color: meta.color,
    hlines: [],
    zones: [],
    markers: [],
    segments: [],
    patternHighlight: null,
  };
}

function pushHline(
  out: DeskChartOverlay,
  id: string,
  price: number | null,
  label: string,
  style: "solid" | "dashed" = "dashed",
): void {
  if (price == null || price <= 0) return;
  out.hlines.push({
    id: `${out.deskId}_${id}`,
    deskId: out.deskId,
    price,
    color: out.color,
    label: `${out.deskLabel} ${label}`,
    style,
  });
}

function swingPositionOverlay(
  deskId: string,
  p: Record<string, unknown>,
): DeskChartOverlay {
  const out = emptyOverlay(deskId);
  const stop = num(p.trailing_stop) ?? num(p.stop_loss);
  const t1 = num(p.target_1) ?? num(p.target_max) ?? num(p.fill_target);
  const t2 = num(p.target_2);

  pushHline(out, "stop", stop, "stop");
  pushHline(out, "t1", t1, "T1");
  pushHline(out, "t2", t2, "T2");

  const entry = num(p.entry_price);
  const screenDate = typeof p.screen_date === "string" ? p.screen_date : null;
  if (screenDate && entry != null) {
    out.markers.push({
      deskId: out.deskId,
      time: screenDate,
      text: `${out.deskLabel} @ ${entry.toFixed(2)}`,
      color: out.color,
      position: "belowBar",
    });
  }

  if (deskId === "gap-fill") {
    const gapLow = num(p.gap_low);
    const gapHigh = num(p.gap_high);
    if (gapLow != null && gapHigh != null && gapHigh > gapLow) {
      out.zones.push({
        id: `${deskId}_gap`,
        deskId,
        low: gapLow,
        high: gapHigh,
        label: `${out.deskLabel} gap`,
        color: out.color,
      });
    } else if (gapLow != null) {
      pushHline(out, "gap_low", gapLow, "gap low");
    }
    const fillTarget = num(p.fill_target);
    if (fillTarget != null && fillTarget !== t1) {
      pushHline(out, "fill", fillTarget, "fill tgt");
    }
  }

  if (deskId === "trama") {
    pushHline(out, "trama", num(p.trama_value), "TRAMA");
  }

  if (deskId === "nw-envelope") {
    pushHline(out, "nwe_upper", num(p.nwe_upper), "upper");
    pushHline(out, "nwe_mid", num(p.nwe_middle), "middle");
    pushHline(out, "nwe_lower", num(p.nwe_lower), "lower");
  }

  if (deskId === "pattern-forecast") {
    pushHline(out, "proj", num(p.projected_close_5d), "proj 5d");
  }

  return out;
}

function techDeskOverlay(norm: string): DeskChartOverlay {
  const out = emptyOverlay("tech-desk");

  const book = readTechDeskBook();
  for (const p of book?.positions ?? []) {
    if (!matchesTicker(p.ticker, norm) || p.status !== "open") continue;
    const row = swingPositionOverlay("tech-desk", p as unknown as Record<string, unknown>);
    out.hlines.push(...row.hlines);
    out.markers.push(...row.markers);
  }

  for (const pe of readTechDeskPending()) {
    if (!matchesTicker(pe.ticker, norm)) continue;
    const zl = num(pe.zone_low);
    const zh = num(pe.zone_high);
    if (zl != null && zh != null && zh > zl) {
      out.zones.push({
        id: "tech_desk_pending_zone",
        deskId: "tech-desk",
        low: zl,
        high: zh,
        label: `${out.deskLabel} buy zone`,
        color: out.color,
      });
      pushHline(out, "zone_low", zl, "zone low");
      pushHline(out, "zone_high", zh, "zone high");
    }
    if (!out.hlines.some((h) => h.id.includes("stop"))) {
      pushHline(out, "pending_stop", num(pe.stop_loss), "stop");
    }
    if (!out.hlines.some((h) => h.id.includes("t1"))) {
      pushHline(out, "pending_t1", num(pe.target_1), "T1");
    }
  }

  return out;
}

function findPatternPick(norm: string, patternId?: string | null): ChartPatternScreenerPick | null {
  const snapshot = readChartPatternScreenerSnapshot();
  if (!snapshot) return null;

  if (patternId?.trim()) {
    for (const g of snapshot.groups) {
      for (const p of g.picks) {
        if (p.pattern_id === patternId && matchesTicker(p.ticker, norm)) return p;
      }
    }
  }

  let best: ChartPatternScreenerPick | null = null;
  for (const g of snapshot.groups) {
    for (const p of g.picks) {
      if (!matchesTicker(p.ticker, norm)) continue;
      if (!best || p.actionability_score > best.actionability_score) {
        best = p;
      }
    }
  }
  return best;
}

function chartPatternOverlay(norm: string, patternId?: string | null): DeskChartOverlay {
  const out = emptyOverlay("chart-patterns");
  const pick = findPatternPick(norm, patternId);
  if (!pick) return out;

  const levels = pickTradeLevels(pick);
  if (!levels) return out;

  const support = num(pick.support_level);
  const resistance = num(pick.resistance_level);
  const trigger = num(pick.trigger_level);
  const rr = levels.riskReward.toFixed(1);

  pushHline(out, "trigger", trigger, "trigger", "solid");
  pushHline(out, "stop", levels.stop, "stop");
  pushHline(out, "t1", levels.t1, `T1 (${rr}:1)`);
  pushHline(out, "t2", levels.t2, "T2 (2R)");

  if (support != null && resistance != null && resistance > support) {
    out.zones.push({
      id: "chart_patterns_range",
      deskId: out.deskId,
      low: support,
      high: resistance,
      label: `${out.deskLabel} ${pick.pattern_name}`,
      color: out.color,
    });
  }

  for (const line of pick.geometry_lines ?? []) {
    if (!line.points?.length) continue;
    out.segments.push({
      id: line.id,
      label: line.label,
      color: line.color ?? out.color,
      deskId: out.deskId,
      lineWidth: 2,
      data: line.points.map((p) => ({ time: p.time, value: p.value })),
    });
  }

  for (const p of pick.pivots ?? []) {
    out.markers.push({
      deskId: out.deskId,
      time: p.time,
      text: p.role.replace(/_/g, " "),
      color: out.color,
      position: p.position,
    });
  }

  if (pick.pattern_window_start && pick.pattern_window_end) {
    out.patternHighlight = {
      windowStart: pick.pattern_window_start,
      windowEnd: pick.pattern_window_end,
      label: `${pick.pattern_name} · ${pick.setup_status}`,
      color: out.color,
    };
  }

  return out;
}

type BookReader = () => { positions: Record<string, unknown>[] } | null;

const SWING_BOOK_READERS: Record<string, BookReader> = {
  swing: () => readSwingBook(),
  momentum: () => readMomentumBook(),
  nss: () => readNssBook(),
  "supertrend-rsi": () => readStrsiBook(),
  trama: () => readTramaBook(),
  "gap-fill": () => readGapFillBook(),
  "nw-envelope": () => readNwEnvelopeBook(),
  "pattern-forecast": () => readPatternForecastBook(),
};

function appendBundle(target: DeskChartOverlay, row: DeskChartOverlay): void {
  target.hlines.push(...row.hlines);
  target.zones.push(...row.zones);
  target.markers.push(...row.markers);
  target.segments.push(...row.segments);
}

export function collectDeskOverlays(
  ticker: string,
  patternId?: string | null,
): DeskChartOverlay[] {
  const norm = normalizeChartTicker(ticker);
  if (!norm) return [];

  const overlays: DeskChartOverlay[] = [];

  for (const deskId of Object.keys(SWING_BOOK_READERS)) {
    const book = SWING_BOOK_READERS[deskId]();
    const bundle = emptyOverlay(deskId);
    for (const p of book?.positions ?? []) {
      if ((p.status as string) !== "open") continue;
      if (!matchesTicker(String(p.ticker ?? ""), norm)) continue;
      appendBundle(bundle, swingPositionOverlay(deskId, p));
    }
    if (bundle.hlines.length || bundle.zones.length || bundle.markers.length) {
      overlays.push(bundle);
    }
  }

  const tech = techDeskOverlay(norm);
  if (tech.hlines.length || tech.zones.length || tech.markers.length) {
    overlays.push(tech);
  }

  const patterns = chartPatternOverlay(norm, patternId);
  if (
    patterns.hlines.length ||
    patterns.zones.length ||
    patterns.markers.length ||
    patterns.segments.length
  ) {
    overlays.push(patterns);
  }

  return overlays;
}

export function mergeDeskOverlays(
  desks: DeskChartOverlay[],
  enabledDeskIds?: Set<string>,
): { hlines: ChartHLine[]; zones: ChartZone[]; markers: ChartMarker[]; segments: ChartLineSeries[]; patternHighlight: ChartPatternHighlight | null } {
  const hlines: ChartHLine[] = [];
  const zones: ChartZone[] = [];
  const markers: ChartMarker[] = [];
  const segments: ChartLineSeries[] = [];
  let patternHighlight: ChartPatternHighlight | null = null;

  for (const d of desks) {
    if (enabledDeskIds && !enabledDeskIds.has(d.deskId)) continue;
    hlines.push(...d.hlines);
    zones.push(...d.zones);
    markers.push(...d.markers);
    segments.push(...d.segments);
    if (d.patternHighlight) patternHighlight = d.patternHighlight;
  }

  return { hlines, zones, markers, segments, patternHighlight };
}

export function parseDeskFilter(raw: string | null | undefined): Set<string> | undefined {
  if (!raw?.trim()) return undefined;
  const ids = raw
    .split(",")
    .map((s) => s.trim())
    .filter((id) => CHART_DESK_META.some((d) => d.id === id));
  return ids.length ? new Set(ids) : undefined;
}

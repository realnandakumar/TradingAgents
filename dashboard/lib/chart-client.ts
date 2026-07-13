import type { ChartHLine, ChartLineSeries, ChartMarker, ChartPatternHighlight, ChartPayload, ChartZone } from "@/lib/chart-types";

export function mergeDeskOverlaysClient(
  desks: ChartPayload["deskOverlays"],
  enabledDeskIds: Set<string>,
): {
  hlines: ChartHLine[];
  zones: ChartZone[];
  markers: ChartMarker[];
  segments: ChartLineSeries[];
  patternHighlight: ChartPatternHighlight | null;
} {
  const hlines: ChartHLine[] = [];
  const zones: ChartZone[] = [];
  const markers: ChartMarker[] = [];
  const segments: ChartLineSeries[] = [];
  let patternHighlight: ChartPatternHighlight | null = null;
  for (const d of desks) {
    if (!enabledDeskIds.has(d.deskId)) continue;
    hlines.push(...d.hlines);
    zones.push(...d.zones);
    markers.push(...d.markers);
    segments.push(...(d.segments ?? []));
    if (d.patternHighlight) patternHighlight = d.patternHighlight;
  }
  return { hlines, zones, markers, segments, patternHighlight };
}

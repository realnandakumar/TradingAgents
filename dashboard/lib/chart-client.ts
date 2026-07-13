import type { ChartHLine, ChartMarker, ChartPayload, ChartZone } from "@/lib/chart-types";

export function mergeDeskOverlaysClient(
  desks: ChartPayload["deskOverlays"],
  enabledDeskIds: Set<string>,
): { hlines: ChartHLine[]; zones: ChartZone[]; markers: ChartMarker[] } {
  const hlines: ChartHLine[] = [];
  const zones: ChartZone[] = [];
  const markers: ChartMarker[] = [];
  for (const d of desks) {
    if (!enabledDeskIds.has(d.deskId)) continue;
    hlines.push(...d.hlines);
    zones.push(...d.zones);
    markers.push(...d.markers);
  }
  return { hlines, zones, markers };
}

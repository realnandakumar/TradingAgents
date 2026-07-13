export type ChartRange = "3m" | "6m" | "1y" | "3y" | "5y" | "max";
export type ChartTimeframe = "1d" | "5m" | "15m";
export type IntradayRange = "1d" | "5d";
export type ChartTime = string | number;

export interface ChartBar {
  time: ChartTime;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartLineSeries {
  id: string;
  label: string;
  color: string;
  data: { time: ChartTime; value: number }[];
  deskId?: string;
  lineWidth?: 1 | 2 | 3 | 4;
}

export interface ChartHLine {
  id: string;
  deskId?: string;
  price: number;
  color: string;
  label: string;
  style?: "solid" | "dashed";
}

export interface ChartZone {
  id: string;
  deskId?: string;
  low: number;
  high: number;
  label: string;
  color?: string;
}

export interface ChartMarker {
  deskId?: string;
  time: ChartTime;
  text: string;
  color: string;
  position: "belowBar" | "aboveBar";
}

export interface ChartPatternHighlight {
  windowStart: string;
  windowEnd: string;
  label: string;
  color: string;
}

export interface ChartPayload {
  ticker: string;
  timeframe: ChartTimeframe;
  range: ChartRange | IntradayRange;
  source: "cache" | "prices.db" | "yahoo" | "cache+yahoo";
  cacheFile?: string | null;
  bars: ChartBar[];
  lines: ChartLineSeries[];
  hlines: ChartHLine[];
  zones: ChartZone[];
  markers: ChartMarker[];
  deskOverlays: {
    deskId: string;
    deskLabel: string;
    color: string;
    hlines: ChartHLine[];
    zones: ChartZone[];
    markers: ChartMarker[];
    segments?: ChartLineSeries[];
    patternHighlight?: ChartPatternHighlight | null;
  }[];
  meta: {
    barCount: number;
    first: string | null;
    last: string | null;
    lastClose: number | null;
  };
  patternHighlight?: ChartPatternHighlight | null;
}

import fs from "fs";
import os from "os";
import path from "path";

const DEFAULT_SNAPSHOT = path.join(
  os.homedir(),
  ".tradingagents",
  "chart_patterns",
  "screener.json",
);

export type ChartPatternScreenerPick = {
  rank: number;
  symbol: string;
  ticker: string;
  stock_name: string;
  sector: string;
  pattern_id: string;
  pattern_name: string;
  bias: string;
  reliability: number;
  pattern_age: number;
  setup_status: string;
  distance_to_trigger_pct: number;
  actionability_score: number;
  confidence: number;
  close: number;
  trigger_level: number;
  support_level: number;
  resistance_level: number;
  detail: string;
};

export type ChartPatternScreenerGroup = {
  pattern_id: string;
  pattern_name: string;
  bias: string;
  stars: number;
  count: number;
  picks: ChartPatternScreenerPick[];
};

export type ChartPatternScreenerSnapshot = {
  strategy_id: string;
  strategy_name: string;
  version: string;
  updated_at: string;
  filters: Record<string, unknown>;
  checked: number;
  total_hits: number;
  group_count: number;
  groups: ChartPatternScreenerGroup[];
};

export function chartPatternScreenerSnapshotPath(): string {
  return (
    process.env.CHART_PATTERN_SCREENER_SNAPSHOT_PATH ??
    process.env.TRADINGAGENTS_CHART_PATTERN_SCREENER_SNAPSHOT_PATH ??
    DEFAULT_SNAPSHOT
  );
}

export function readChartPatternScreenerSnapshot(): ChartPatternScreenerSnapshot | null {
  const snapshotPath = chartPatternScreenerSnapshotPath();
  try {
    const raw = fs.readFileSync(snapshotPath, "utf-8");
    return JSON.parse(raw) as ChartPatternScreenerSnapshot;
  } catch {
    return null;
  }
}

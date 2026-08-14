import fs from "fs";
import os from "os";
import path from "path";

import { parseBookJson } from "@/lib/parse-book-json";

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
  entry_level?: number;
  stop_loss?: number;
  target_1?: number;
  target_2?: number;
  risk_reward_ratio?: number;
  risk_reward_market?: number;
  entry_type?: string;
  market_entry?: number;
  measured_move?: number;
  levels_valid?: boolean;
  geometry_lines?: {
    id: string;
    label: string;
    color: string;
    points: { time: string; value: number }[];
  }[];
  pattern_window_start?: string;
  pattern_window_end?: string;
  pivots?: {
    time: string;
    price: number;
    role: string;
    position: "belowBar" | "aboveBar";
  }[];
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

const DEFAULT_AUDIT = path.join(
  os.homedir(),
  ".tradingagents",
  "chart_patterns",
  "audit.json",
);

export type ChartPatternAuditSummary = {
  t1_hit_rate_pct?: number;
  by_pattern?: Record<string, { t1_hit_rate_pct?: number; signals?: number }>;
};

export function chartPatternAuditPath(): string {
  return (
    process.env.CHART_PATTERN_AUDIT_PATH ??
    process.env.TRADINGAGENTS_CHART_PATTERN_AUDIT_PATH ??
    DEFAULT_AUDIT
  );
}

export function readChartPatternAudit(): ChartPatternAuditSummary | null {
  try {
    const raw = fs.readFileSync(chartPatternAuditPath(), "utf-8");
    return parseBookJson<ChartPatternAuditSummary>(raw);
  } catch {
    return null;
  }
}

export function readChartPatternScreenerSnapshot(): ChartPatternScreenerSnapshot | null {
  const snapshotPath = chartPatternScreenerSnapshotPath();
  try {
    const raw = fs.readFileSync(snapshotPath, "utf-8");
    return parseBookJson<ChartPatternScreenerSnapshot>(raw);
  } catch {
    return null;
  }
}

import fs from "fs";
import os from "os";
import path from "path";

import { parseBookJson } from "@/lib/parse-book-json";

const DEFAULT_SNAPSHOT = path.join(
  os.homedir(),
  ".tradingagents",
  "candlesticks",
  "screener.json",
);

export type CandleScreenerPick = {
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
  entry_level: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  risk_reward_ratio: number;
  levels_valid?: boolean;
  detail: string;
  pattern_window_start?: string;
  pattern_window_end?: string;
};

export type CandleScreenerGroup = {
  pattern_id: string;
  pattern_name: string;
  bias: string;
  stars: number;
  count: number;
  picks: CandleScreenerPick[];
};

export type CandleScreenerSnapshot = {
  strategy_id: string;
  strategy_name: string;
  version: string;
  updated_at: string;
  filters: Record<string, unknown>;
  checked: number;
  total_hits: number;
  group_count: number;
  groups: CandleScreenerGroup[];
};

export function candleScreenerSnapshotPath(): string {
  return (
    process.env.CANDLE_SCREENER_SNAPSHOT_PATH ??
    process.env.TRADINGAGENTS_CANDLE_SCREENER_SNAPSHOT_PATH ??
    DEFAULT_SNAPSHOT
  );
}

export function readCandleScreenerSnapshot(): CandleScreenerSnapshot | null {
  const filePath = candleScreenerSnapshotPath();
  if (!fs.existsSync(filePath)) return null;
  try {
    return parseBookJson<CandleScreenerSnapshot>(fs.readFileSync(filePath, "utf-8"));
  } catch {
    return null;
  }
}

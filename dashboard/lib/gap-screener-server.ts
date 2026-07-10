import fs from "fs";
import os from "os";
import path from "path";

const DEFAULT_SNAPSHOT = path.join(
  os.homedir(),
  ".tradingagents",
  "gap_fill",
  "screener.json",
);

export type GapScreenerPick = {
  rank: number;
  symbol: string;
  ticker: string;
  stock_name: string;
  sector: string;
  direction: "UP" | "DOWN" | string;
  gap_age: number;
  gap_pct: number;
  fill_pct: number;
  close: number;
  rsi: number;
  gap_low: number;
  gap_high: number;
  fill_target: number;
  remark: string;
};

export type GapScreenerSnapshot = {
  strategy_id: string;
  strategy_name: string;
  version: string;
  updated_at: string;
  filters: Record<string, unknown>;
  checked: number;
  total_hits: number;
  picks: GapScreenerPick[];
};

export function gapScreenerSnapshotPath(): string {
  return (
    process.env.GAP_FILL_SCREENER_SNAPSHOT_PATH ??
    process.env.TRADINGAGENTS_GAP_FILL_SCREENER_SNAPSHOT_PATH ??
    DEFAULT_SNAPSHOT
  );
}

export function readGapScreenerSnapshot(): GapScreenerSnapshot | null {
  const snapshotPath = gapScreenerSnapshotPath();
  try {
    const raw = fs.readFileSync(snapshotPath, "utf-8");
    return JSON.parse(raw) as GapScreenerSnapshot;
  } catch {
    return null;
  }
}

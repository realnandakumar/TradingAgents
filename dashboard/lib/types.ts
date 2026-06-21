// Shapes mirror the JSON snapshots pushed by tradingagents/sync/supabase_sync.py.

export type Rating = "Buy" | "Overweight" | "Hold" | "Underweight" | "Sell";

export interface Candidate {
  rank: number;
  symbol: string;
  rs_percentile: number;
  rs_score: number;
  close: number;
  composite: number;
  signals: string[];
  rating: Rating | null;
  opened: boolean;
}

export interface ScreenSnapshot {
  trade_date: string;
  generated_at: string;
  opened: string[];
  candidates: Candidate[];
}

export interface Position {
  ticker: string;
  rating: string;
  signals: string[];
  entry_date: string;
  entry_price: number;
  shares: number;
  alloc: number;
  status: "open" | "closed";
  exit_date: string | null;
  exit_price: number | null;
  raw_return: number | null;
  alpha_return: number | null;
  holding_days_actual: number | null;
}

export interface Agg {
  trades: number;
  win_rate: number | null;
  avg_return: number | null;
  avg_alpha: number | null;
  total_pnl: number;
}

export interface Stats {
  overall: Agg;
  open_positions: number;
  closed_positions: number;
  per_signal: Record<string, Agg>;
}

export interface PaperSnapshot {
  generated_at: string;
  capital: number;
  positions: Position[];
  stats: Stats;
}

export interface SnapshotRow<T> {
  id: number;
  kind: "screen" | "paper";
  created_at: string;
  data: T;
}

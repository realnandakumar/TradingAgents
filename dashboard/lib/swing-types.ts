export interface SwingPosition {
  ticker: string;
  stock_name: string;
  sector: string;
  screen_date: string;
  entry_price: number;
  stop_loss: number;
  stop_loss_pct: number;
  target_1: number;
  target_1_pct: number;
  target_2: number;
  target_2_pct: number;
  risk_reward_ratio: number;
  risk_reward_ratio_2: number;
  status: "open" | "closed";
  phase?: string;
  remaining_pct?: number;
  trailing_stop?: number;
  rsi?: number;
  adx?: number;
  composite_score?: number;
  confidence?: string;
  primary_reason?: string;
  relative_volume?: number;
  range_pct?: number;
  atr_ratio?: number;
  raw_return?: number | null;
  exit_reason?: string | null;
}

export interface SwingBook {
  strategy: string;
  updated_at: string;
  positions: SwingPosition[];
}

export function shortSector(sector: string): string {
  if (sector === "Information Technology") return "IT";
  if (sector === "Automobile and Auto Components") return "Auto";
  if (sector === "Financial Services") return "Fin Svcs";
  return sector.length > 14 ? `${sector.slice(0, 13)}…` : sector;
}

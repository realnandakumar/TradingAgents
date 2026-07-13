import type { ChartPatternScreenerPick } from "./chart-patterns-server";

export const NEAR_BREAKOUT_STATUSES = new Set([
  "APPROACHING",
  "AT_TRIGGER",
  "NEAR_TOP",
  "NEAR_BOTTOM",
]);

export function isNearBreakoutStatus(status: string): boolean {
  return NEAR_BREAKOUT_STATUSES.has(status);
}

export interface PatternTradeLevels {
  entry: number;
  stop: number;
  t1: number;
  t2: number;
  riskReward: number;
  riskRewardMarket: number;
  entryType: string;
  marketEntry: number;
}

const VALIDATED = new Set([
  "double_top",
  "double_bottom",
  "ascending_triangle",
  "descending_triangle",
  "head_shoulders",
  "inverse_head_shoulders",
  "cup_and_handle",
  "rectangle",
  "bull_flag",
  "bear_flag",
  "pennant",
  "rising_wedge",
  "falling_wedge",
]);

function rr(entry: number, stop: number, target: number): number {
  const risk = Math.abs(entry - stop);
  if (risk <= 0) return 0;
  return Math.abs(target - entry) / risk;
}

function pack(
  entry: number,
  stop: number,
  t1: number,
  t2: number,
  close: number,
): PatternTradeLevels | null {
  if (entry <= 0 || stop <= 0 || t1 <= 0 || t2 <= 0) return null;
  const riskReward = rr(entry, stop, t1);
  if (riskReward <= 0) return null;
  return {
    entry,
    stop,
    t1,
    t2,
    riskReward,
    riskRewardMarket: rr(close, stop, t1),
    entryType: "trigger",
    marketEntry: close,
  };
}

/** Prefer persisted snapshot levels; fallback to client-side formula. */
export function pickTradeLevels(pick: ChartPatternScreenerPick): PatternTradeLevels | null {
  if (
    pick.levels_valid &&
    pick.stop_loss != null &&
    pick.target_1 != null &&
    pick.entry_level != null
  ) {
    return {
      entry: pick.entry_level,
      stop: pick.stop_loss,
      t1: pick.target_1,
      t2: pick.target_2 ?? pick.target_1,
      riskReward: pick.risk_reward_ratio ?? 0,
      riskRewardMarket: pick.risk_reward_market ?? 0,
      entryType: pick.entry_type ?? "trigger",
      marketEntry: pick.market_entry ?? pick.close,
    };
  }
  return computePatternTradeLevels(pick);
}

export function computePatternTradeLevels(
  pick: ChartPatternScreenerPick,
): PatternTradeLevels | null {
  if (!isNearBreakoutStatus(pick.setup_status)) return null;
  if (!VALIDATED.has(pick.pattern_id)) return null;

  const { bias, setup_status, pattern_id, trigger_level, support_level, resistance_level, close } =
    pick;
  const support = support_level;
  const resistance = resistance_level;
  const trigger = trigger_level;
  const height = resistance > support ? resistance - support : 0;
  const poleHeight = pick.measured_move && pick.measured_move > 0 ? pick.measured_move : height;

  if (["bull_flag", "bear_flag", "pennant"].includes(pattern_id)) {
    if (poleHeight <= 0) return null;
    const bullish = pattern_id === "bull_flag" || (pattern_id === "pennant" && bias !== "BEARISH");
    const entry = trigger > 0 ? trigger : bullish ? resistance : support;
    const stop = bullish ? support : resistance;
    const t1 = bullish ? entry + poleHeight : entry - poleHeight;
    const t2 = bullish ? entry + 2 * poleHeight : entry - 2 * poleHeight;
    return pack(entry, stop, t1, t2, close);
  }

  if (pattern_id === "rising_wedge") {
    const move = height;
    if (move <= 0) return null;
    return pack(support, resistance, support - move, support - 2 * move, close);
  }
  if (pattern_id === "falling_wedge") {
    const move = height;
    if (move <= 0) return null;
    return pack(resistance, support, resistance + move, resistance + 2 * move, close);
  }

  if (pattern_id === "head_shoulders") {
    const entry = trigger > 0 ? trigger : support;
    const stop = resistance;
    return pack(entry, stop, entry - height, entry - 2 * height, close);
  }
  if (pattern_id === "inverse_head_shoulders") {
    const entry = trigger > 0 ? trigger : resistance;
    const stop = support;
    return pack(entry, stop, entry + height, entry + 2 * height, close);
  }
  if (pattern_id === "cup_and_handle") {
    const entry = resistance;
    const stop = support;
    return pack(entry, stop, entry + height, entry + 2 * height, close);
  }

  if (bias === "BULLISH") {
    const entry = trigger > 0 ? trigger : resistance;
    return pack(entry, support, entry + height, entry + 2 * height, close);
  }
  if (bias === "BEARISH") {
    const entry = trigger > 0 ? trigger : support;
    return pack(entry, resistance, entry - height, entry - 2 * height, close);
  }
  if (setup_status === "NEAR_TOP") {
    return pack(resistance, support, resistance + height, resistance + 2 * height, close);
  }
  if (setup_status === "NEAR_BOTTOM") {
    return pack(support, resistance, support - height, support - 2 * height, close);
  }
  return null;
}

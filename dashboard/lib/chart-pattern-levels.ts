import type { ChartPatternScreenerPick } from "./chart-patterns-server";

const NEAR_BREAKOUT_STATUSES = new Set([
  "APPROACHING",
  "AT_TRIGGER",
  "NEAR_TOP",
  "NEAR_BOTTOM",
]);

export interface PatternTradeLevels {
  entry: number;
  stop: number;
  t1: number;
  riskReward: number;
}

export function computePatternTradeLevels(
  pick: ChartPatternScreenerPick,
): PatternTradeLevels | null {
  if (!NEAR_BREAKOUT_STATUSES.has(pick.setup_status)) return null;

  const { bias, setup_status, trigger_level, support_level, resistance_level } = pick;
  const support = support_level;
  const resistance = resistance_level;
  const trigger = trigger_level;
  const height = resistance > support ? resistance - support : 0;

  let entry: number;
  let stop: number;
  let t1: number;

  if (bias === "BULLISH") {
    entry = trigger;
    stop = support;
    t1 = trigger + height;
  } else if (bias === "BEARISH") {
    entry = trigger;
    stop = resistance;
    t1 = trigger - height;
  } else if (setup_status === "NEAR_TOP") {
    entry = resistance;
    stop = support;
    t1 = resistance + height;
  } else if (setup_status === "NEAR_BOTTOM") {
    entry = support;
    stop = resistance;
    t1 = support - height;
  } else {
    return null;
  }

  if (!Number.isFinite(entry) || !Number.isFinite(stop) || entry <= 0 || stop <= 0) {
    return null;
  }

  const risk = Math.abs(entry - stop);
  if (risk <= 0) return null;

  const reward = Math.abs(t1 - entry);
  const riskReward = reward / risk;

  return { entry, stop, t1, riskReward };
}

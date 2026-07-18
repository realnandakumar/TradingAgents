/** Client/server candle detectors mirroring tradingagents/screening/candle_engine.py */

import type { ChartBar } from "@/lib/chart-types";
import candleRules from "@/lib/candle_rules.json";

export type CandleBias = "BULLISH" | "BEARISH" | "NEUTRAL";

export interface CandleHit {
  pattern_id: string;
  pattern_name: string;
  bias: CandleBias;
  confidence: number;
  entry_level: number;
  stop_loss: number;
  target_1: number;
  target_2: number;
  risk_reward_ratio: number;
  detail: string;
  pattern_window_start: string;
  pattern_window_end: string;
  pattern_age: number;
}

const CATALOG: Record<string, { label: string; bias: CandleBias }> = {
  hammer: { label: "Hammer", bias: "BULLISH" },
  shooting_star: { label: "Shooting Star", bias: "BEARISH" },
  bullish_engulfing: { label: "Bullish Engulfing", bias: "BULLISH" },
  bearish_engulfing: { label: "Bearish Engulfing", bias: "BEARISH" },
  doji: { label: "Doji", bias: "NEUTRAL" },
};

const RULES = candleRules as {
  min_confidence: number;
  max_age_days: number;
  hammer: {
    max_body_to_range: number;
    min_lower_wick_to_body: number;
    strong_lower_wick_to_body: number;
    confidence: number;
    strong_confidence: number;
  };
  shooting_star: {
    max_body_to_range: number;
    min_upper_wick_to_body: number;
    strong_upper_wick_to_body: number;
    confidence: number;
    strong_confidence: number;
  };
  engulfing: { confidence: number };
  doji: { max_body_to_range: number; confidence: number };
};

function dateKey(time: ChartBar["time"]): string {
  if (typeof time === "number") return new Date(time * 1000).toISOString().slice(0, 10);
  return String(time).slice(0, 10);
}

function atr(bars: ChartBar[], end: number, period = 14): number {
  const start = Math.max(1, end - period + 1);
  let sum = 0;
  let n = 0;
  for (let i = start; i <= end; i += 1) {
    const prev = bars[i - 1];
    const cur = bars[i];
    if (!prev || !cur) continue;
    const tr = Math.max(
      cur.high - cur.low,
      Math.abs(cur.high - prev.close),
      Math.abs(cur.low - prev.close),
    );
    sum += tr;
    n += 1;
  }
  return n ? sum / n : Math.max(bars[end]?.high - (bars[end]?.low ?? 0), 1e-9);
}

function levels(bias: CandleBias, entry: number, stop: number, atrVal: number) {
  const buffer = Math.max(atrVal * 0.05, Math.abs(entry) * 0.001);
  if (bias === "BULLISH") {
    const stopOut = Math.min(stop, entry) - buffer;
    const risk = entry - stopOut;
    if (risk <= 0) return null;
    return { entry, stop: stopOut, t1: entry + risk, t2: entry + 2 * risk, rr: 1 };
  }
  if (bias === "BEARISH") {
    const stopOut = Math.max(stop, entry) + buffer;
    const risk = stopOut - entry;
    if (risk <= 0) return null;
    return { entry, stop: stopOut, t1: entry - risk, t2: entry - 2 * risk, rr: 1 };
  }
  return null;
}

function pushHit(
  out: CandleHit[],
  patternId: string,
  bias: CandleBias,
  confidence: number,
  entry: number,
  stop: number,
  atrVal: number,
  detail: string,
  windowStart: string,
  windowEnd: string,
  age: number,
) {
  const lv = levels(bias, entry, stop, atrVal);
  if (!lv || lv.rr < 0.9) return;
  const meta = CATALOG[patternId];
  if (!meta) return;
  out.push({
    pattern_id: patternId,
    pattern_name: meta.label,
    bias,
    confidence,
    entry_level: lv.entry,
    stop_loss: lv.stop,
    target_1: lv.t1,
    target_2: lv.t2,
    risk_reward_ratio: lv.rr,
    detail,
    pattern_window_start: windowStart,
    pattern_window_end: windowEnd,
    pattern_age: age,
  });
}

/** Detect confirmed candlesticks on daily bars (confirm = bar after pattern). */
export function scanCandlesticksFromBars(
  bars: ChartBar[],
  opts?: { minConfidence?: number; maxAgeDays?: number },
): CandleHit[] {
  if (bars.length < 4) return [];
  const minConfidence = opts?.minConfidence ?? RULES.min_confidence;
  const maxAge = opts?.maxAgeDays ?? RULES.max_age_days;
  const hits: CandleHit[] = [];
  const last = bars.length - 1;
  const hammer = RULES.hammer;
  const star = RULES.shooting_star;
  const engulf = RULES.engulfing;
  const doji = RULES.doji;

  for (let age = 0; age <= maxAge; age += 1) {
    const confirmI = last - age;
    const patternI = confirmI - 1;
    if (patternI < 1) break;
    const prior = bars[patternI - 1]!;
    const pattern = bars[patternI]!;
    const confirm = bars[confirmI]!;
    const atrVal = atr(bars, confirmI);
    const body = Math.abs(pattern.close - pattern.open);
    const rng = Math.max(pattern.high - pattern.low, 1e-9);
    const upper = pattern.high - Math.max(pattern.open, pattern.close);
    const lower = Math.min(pattern.open, pattern.close) - pattern.low;
    const pd = dateKey(pattern.time);
    const cd = dateKey(confirm.time);
    const priorD = dateKey(prior.time);

    if (
      body / rng <= hammer.max_body_to_range &&
      lower >= hammer.min_lower_wick_to_body * Math.max(body, rng * 0.05) &&
      upper <= body &&
      confirm.close > (pattern.low + pattern.high) / 2 &&
      confirm.close > pattern.close
    ) {
      pushHit(
        hits,
        "hammer",
        "BULLISH",
        lower >= hammer.strong_lower_wick_to_body * body
          ? hammer.strong_confidence
          : hammer.confidence,
        confirm.close,
        pattern.low,
        atrVal,
        `Hammer on ${pd}; confirm close above mid`,
        pd,
        cd,
        age,
      );
    }

    if (
      body / rng <= star.max_body_to_range &&
      upper >= star.min_upper_wick_to_body * Math.max(body, rng * 0.05) &&
      lower <= body &&
      confirm.close < (pattern.low + pattern.high) / 2 &&
      confirm.close < pattern.close
    ) {
      pushHit(
        hits,
        "shooting_star",
        "BEARISH",
        upper >= star.strong_upper_wick_to_body * body
          ? star.strong_confidence
          : star.confidence,
        confirm.close,
        pattern.high,
        atrVal,
        `Shooting star on ${pd}; confirm close below mid`,
        pd,
        cd,
        age,
      );
    }

    const priorBear = prior.close < prior.open;
    const priorBull = prior.close > prior.open;
    const patternBull = pattern.close > pattern.open;
    const patternBear = pattern.close < pattern.open;
    const priorBody = Math.abs(prior.close - prior.open);

    if (
      priorBear &&
      patternBull &&
      pattern.close >= prior.open &&
      pattern.open <= prior.close &&
      body > priorBody &&
      confirm.close > pattern.high
    ) {
      pushHit(
        hits,
        "bullish_engulfing",
        "BULLISH",
        engulf.confidence,
        confirm.close,
        Math.min(pattern.low, Math.min(prior.open, prior.close)),
        atrVal,
        `Bullish engulfing ${priorD}/${pd}; confirm above high`,
        priorD,
        cd,
        age,
      );
    }

    if (
      priorBull &&
      patternBear &&
      pattern.open >= prior.close &&
      pattern.close <= prior.open &&
      body > priorBody &&
      confirm.close < pattern.low
    ) {
      pushHit(
        hits,
        "bearish_engulfing",
        "BEARISH",
        engulf.confidence,
        confirm.close,
        Math.max(pattern.high, Math.max(prior.open, prior.close)),
        atrVal,
        `Bearish engulfing ${priorD}/${pd}; confirm below low`,
        priorD,
        cd,
        age,
      );
    }

    if (body / rng <= doji.max_body_to_range) {
      if (confirm.close > pattern.high) {
        pushHit(
          hits,
          "doji",
          "BULLISH",
          doji.confidence,
          confirm.close,
          pattern.low,
          atrVal,
          `Doji on ${pd}; bullish confirm above high`,
          pd,
          cd,
          age,
        );
      } else if (confirm.close < pattern.low) {
        pushHit(
          hits,
          "doji",
          "BEARISH",
          doji.confidence,
          confirm.close,
          pattern.high,
          atrVal,
          `Doji on ${pd}; bearish confirm below low`,
          pd,
          cd,
          age,
        );
      }
    }
  }

  return hits.filter((h) => h.confidence >= minConfidence);
}

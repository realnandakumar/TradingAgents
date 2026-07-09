import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "pattern_forecast", "positions.json");

export function patternForecastBookPath(): string {
  return (
    process.env.PATTERN_FORECAST_BOOK_PATH ??
    process.env.TRADINGAGENTS_PATTERN_FORECAST_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

export function readPatternForecastBook(): SwingBook | null {
  const bookPath = patternForecastBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return JSON.parse(raw) as SwingBook;
  } catch {
    return null;
  }
}

export type PatternForecastPosition = SwingPosition & {
  probability?: number;
  correlation?: number;
  target_max?: number;
  target_max_pct?: number;
  projected_close_5d?: number;
  projected_close_pct?: number;
  analogue_end_date?: string;
  remark?: string;
};

export type { SwingBook as PatternForecastBook };

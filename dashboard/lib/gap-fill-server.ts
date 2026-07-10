import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "gap_fill", "positions.json");

export function gapFillBookPath(): string {
  return (
    process.env.GAP_FILL_BOOK_PATH ??
    process.env.TRADINGAGENTS_GAP_FILL_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

export function readGapFillBook(): SwingBook | null {
  const bookPath = gapFillBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return JSON.parse(raw) as SwingBook;
  } catch {
    return null;
  }
}

export type GapFillPosition = SwingPosition & {
  gap_age?: number;
  gap_pct?: number;
  gap_low?: number;
  gap_high?: number;
  fill_target?: number;
  fill_pct?: number;
  remark?: string;
};

export type { SwingBook as GapFillBook };

import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";
import { parseBookJson } from "./parse-book-json";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "trama", "positions.json");

export function tramaBookPath(): string {
  return (
    process.env.TRAMA_BOOK_PATH ??
    process.env.TRADINGAGENTS_TRAMA_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

export function readTramaBook(): SwingBook | null {
  const bookPath = tramaBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return parseBookJson<SwingBook>(raw);
  } catch {
    return null;
  }
}

export type TramaPosition = SwingPosition & {
  cross_age?: number;
  dist_pct?: number;
  trama_value?: number;
  remark?: string;
};

export type { SwingBook as TramaBook };

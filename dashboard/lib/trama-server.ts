import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "trama", "positions.json");

export function tramaBookPath(): string {
  return (
    process.env.TRAMA_BOOK_PATH ??
    process.env.TRADINGAGENTS_TRAMA_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

function parseTramaBookJson(raw: string): SwingBook {
  try {
    return JSON.parse(raw) as SwingBook;
  } catch {
    // Python json.dumps may emit bare NaN tokens; repair for strict JSON.parse.
    return JSON.parse(
      raw
        .replace(/\bNaN\b/g, "null")
        .replace(/\b-Infinity\b/g, "null")
        .replace(/\bInfinity\b/g, "null"),
    ) as SwingBook;
  }
}

export function readTramaBook(): SwingBook | null {
  const bookPath = tramaBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return parseTramaBookJson(raw);
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

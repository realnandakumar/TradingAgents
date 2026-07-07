import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "supertrend_rsi", "positions.json");

export function strsiBookPath(): string {
  return (
    process.env.STRSI_BOOK_PATH ??
    process.env.TRADINGAGENTS_STRSI_BOOK_PATH ??
    DEFAULT_BOOK
  );
}

export function readStrsiBook(): SwingBook | null {
  const bookPath = strsiBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return JSON.parse(raw) as SwingBook;
  } catch {
    return null;
  }
}

export type { SwingPosition as StrsiPosition, SwingBook as StrsiBook };

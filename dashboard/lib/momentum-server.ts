import fs from "fs";
import os from "os";
import path from "path";

import type { SwingBook, SwingPosition } from "./swing-types";
import { parseBookJson } from "./parse-book-json";

const DEFAULT_BOOK = path.join(os.homedir(), ".tradingagents", "momentum", "positions.json");

export function momentumBookPath(): string {
  return process.env.MOMENTUM_BOOK_PATH ?? process.env.TRADINGAGENTS_MOMENTUM_BOOK_PATH ?? DEFAULT_BOOK;
}

export function readMomentumBook(): SwingBook | null {
  const bookPath = momentumBookPath();
  try {
    const raw = fs.readFileSync(bookPath, "utf-8");
    return parseBookJson<SwingBook>(raw);
  } catch {
    return null;
  }
}

export type { SwingPosition as MomentumPosition, SwingBook as MomentumBook };
